"""Docs retrieval channel for concept/architecture style queries."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path, PurePath
from time import perf_counter
from typing import Any

from ace_lite.index_stage.docs_channel_cache import (
    load_repo_glossary as _cache_load_repo_glossary,
)
from ace_lite.index_stage.docs_channel_cache import (
    load_repo_glossary_from_disk_cache as _cache_load_repo_glossary_from_disk_cache,
)
from ace_lite.index_stage.docs_channel_cache import (
    load_sections as _cache_load_sections,
)
from ace_lite.index_stage.docs_channel_cache import (
    load_sections_from_disk_cache as _cache_load_sections_from_disk_cache,
)
from ace_lite.index_stage.docs_channel_cache import (
    resolve_repo_glossary_cache_path as _cache_resolve_repo_glossary_cache_path,
)
from ace_lite.index_stage.docs_channel_cache import (
    resolve_sections_cache_path as _cache_resolve_sections_cache_path,
)
from ace_lite.index_stage.docs_channel_cache import (
    store_repo_glossary_to_disk_cache as _cache_store_repo_glossary_to_disk_cache,
)
from ace_lite.index_stage.docs_channel_cache import (
    store_sections_to_disk_cache as _cache_store_sections_to_disk_cache,
)
from ace_lite.index_stage.docs_channel_glossary import (
    build_repo_glossary as _glossary_build_repo_glossary,
)
from ace_lite.index_stage.docs_channel_glossary import (
    derive_glossary_terms as _glossary_derive_glossary_terms,
)
from ace_lite.index_stage.docs_channel_glossary import (
    is_glossary_token as _glossary_is_glossary_token,
)
from ace_lite.index_stage.docs_channel_hints import (
    extract_code_fence_values as _hint_extract_code_fence_values,
)
from ace_lite.index_stage.docs_channel_hints import (
    extract_code_hints as _hint_extract_code_hints,
)
from ace_lite.index_stage.docs_channel_loading import (
    collect_docs_paths as _loading_collect_docs_paths,
)
from ace_lite.index_stage.docs_channel_loading import (
    docs_fingerprint as _loading_docs_fingerprint,
)
from ace_lite.index_stage.docs_channel_loading import (
    normalize_cached_section as _loading_normalize_cached_section,
)
from ace_lite.index_stage.docs_channel_loading import (
    parse_markdown_sections as _loading_parse_markdown_sections,
)
from ace_lite.index_stage.docs_channel_loading import (
    serialize_section_for_cache as _loading_serialize_section_for_cache,
)
from ace_lite.index_stage.docs_channel_ranking import (
    build_fts5_query as _ranking_build_fts5_query,
)
from ace_lite.index_stage.docs_channel_ranking import (
    build_query_tokens as _ranking_build_query_tokens,
)
from ace_lite.index_stage.docs_channel_ranking import (
    normalize_fts5_score as _ranking_normalize_fts5_score,
)
from ace_lite.index_stage.docs_channel_ranking import (
    rank_sections as _ranking_rank_sections,
)
from ace_lite.index_stage.docs_channel_ranking import (
    rank_sections_fts5 as _ranking_rank_sections_fts5,
)
from ace_lite.index_stage.docs_channel_ranking import (
    rank_sections_mirror_fts5 as _ranking_rank_sections_mirror_fts5,
)
from ace_lite.index_stage.docs_channel_ranking import (
    sqlite_supports_fts5 as _ranking_sqlite_supports_fts5,
)
from ace_lite.index_stage.docs_channel_ranking import (
    term_frequency as _ranking_term_frequency,
)
from ace_lite.sqlite_mirror import ensure_docs_fts_mirror, query_docs_fts, resolve_mirror_db_path

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CODE_FENCE_RE = re.compile(r"`([^`]{1,160})`")
_PATH_HINT_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+\.(?:py|ts|tsx|js|jsx|go|java|kt|rs))(?:[:#][A-Za-z0-9_:-]+)?"
)
_MODULE_HINT_RE = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*){1,8})\b")
_SYMBOL_HINT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b")

_DOC_INTENT_MARKERS: frozenset[str] = frozenset(
    {
        "how",
        "why",
        "architecture",
        "design",
        "mechanism",
        "workflow",
        "principle",
        "overview",
        "explain",
    }
)
_MODULE_STOPWORDS: frozenset[str] = frozenset(
    {
        "e.g",
        "etc",
        "i.e",
        "readme.md",
        "docs",
        "src",
    }
)
_GLOSSARY_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "then",
        "when",
        "where",
        "what",
        "how",
        "why",
        "does",
        "into",
        "over",
        "under",
        "through",
        "about",
        "architecture",
        "design",
        "workflow",
        "mechanism",
        "overview",
        "explain",
    }
)

_SECTION_CACHE: dict[tuple[str, int, int], tuple[str, list[dict[str, Any]]]] = {}
_REPO_GLOSSARY_CACHE: dict[tuple[str, int], tuple[str, list[str]]] = {}
_FTS5_AVAILABLE: bool | None = None
_DOCS_SECTION_CACHE_SCHEMA = "docs-sections-cache-v1"
_DOCS_SECTION_CACHE_PATH = "context-map/docs_sections_cache.json"
_DOCS_REPO_GLOSSARY_CACHE_SCHEMA = "docs-repo-glossary-cache-v1"
_DOCS_REPO_GLOSSARY_CACHE_PATH = "context-map/docs_repo_glossary_cache.json"


def collect_docs_signals(
    *,
    root: str | Path,
    query: str,
    terms: list[str],
    enabled: bool,
    intent_weight: float,
    max_sections: int = 8,
    max_files: int = 160,
    max_section_chars: int = 2600,
) -> dict[str, Any]:
    started = perf_counter()
    root_path = Path(root)
    if not enabled:
        return _disabled_payload(reason="policy_disabled", elapsed_ms=_elapsed_ms(started))

    (
        sections,
        docs_fingerprint,
        cache_hit,
        cache_layer,
        cache_store_written,
        cache_path,
    ) = _load_sections(
        root=root_path,
        max_files=max_files,
        max_section_chars=max_section_chars,
    )
    (
        repo_glossary,
        repo_glossary_cache_hit,
        repo_glossary_cache_layer,
        repo_glossary_cache_store_written,
        repo_glossary_cache_path,
    ) = _load_repo_glossary(
        root=root_path,
        docs_fingerprint=docs_fingerprint,
        sections=sections,
    )
    if not sections:
        return {
            **_disabled_payload(reason="no_docs_sections", elapsed_ms=_elapsed_ms(started)),
            "enabled": True,
            "backend": "none",
            "backend_fallback_reason": "",
            "cache_hit": bool(cache_hit),
            "cache_layer": str(cache_layer or "none"),
            "cache_store_written": bool(cache_store_written),
            "cache_path": str(cache_path or ""),
            "docs_fingerprint": docs_fingerprint,
            "section_pool_size": 0,
            "repo_glossary_size": 0,
            "repo_glossary_sample": [],
            "repo_glossary_cache_hit": bool(repo_glossary_cache_hit),
            "repo_glossary_cache_layer": str(repo_glossary_cache_layer or "none"),
            "repo_glossary_cache_store_written": bool(repo_glossary_cache_store_written),
            "repo_glossary_cache_path": str(repo_glossary_cache_path or ""),
            "explainability": _build_docs_explainability(
                reason="no_docs_sections",
                backend="none",
                fallback_reason="",
                evidence=[],
                hints={},
            ),
        }

    query_tokens = _build_query_tokens(query=query, terms=terms)
    if not query_tokens:
        return {
            **_disabled_payload(reason="empty_query_terms", elapsed_ms=_elapsed_ms(started)),
            "enabled": True,
            "backend": "none",
            "backend_fallback_reason": "",
            "cache_hit": bool(cache_hit),
            "cache_layer": str(cache_layer or "none"),
            "cache_store_written": bool(cache_store_written),
            "cache_path": str(cache_path or ""),
            "docs_fingerprint": docs_fingerprint,
            "section_pool_size": len(sections),
            "repo_glossary_size": len(repo_glossary),
            "repo_glossary_sample": list(repo_glossary[:12]),
            "repo_glossary_cache_hit": bool(repo_glossary_cache_hit),
            "repo_glossary_cache_layer": str(repo_glossary_cache_layer or "none"),
            "repo_glossary_cache_store_written": bool(repo_glossary_cache_store_written),
            "repo_glossary_cache_path": str(repo_glossary_cache_path or ""),
            "explainability": _build_docs_explainability(
                reason="empty_query_terms",
                backend="none",
                fallback_reason="",
                evidence=[],
                hints={},
            ),
        }

    normalized_intent_weight = max(0.0, float(intent_weight))
    fts5_available = _sqlite_supports_fts5()

    mirror_db_path = resolve_mirror_db_path(root=root_path)
    mirror_payload: dict[str, Any] = {
        "enabled": False,
        "reason": "not_attempted",
        "path": str(mirror_db_path),
    }
    mirror_enabled = False
    if fts5_available:
        mirror_result = ensure_docs_fts_mirror(
            db_path=mirror_db_path,
            docs_fingerprint=docs_fingerprint,
            sections=sections,
        )
        mirror_payload = mirror_result.to_dict()
        mirror_enabled = bool(mirror_result.enabled)

    backend = "python_bm25"
    backend_fallback_reason = ""
    if fts5_available:
        try:
            scored: list[dict[str, Any]] = []
            if mirror_enabled:
                scored = _rank_sections_mirror_fts5(
                    sections=sections,
                    query_tokens=query_tokens,
                    intent_weight=normalized_intent_weight,
                    db_path=mirror_db_path,
                    limit=min(len(sections), max(32, int(max_sections) * 12)),
                )
                if scored:
                    backend = "mirror_fts5_bm25"
            if not scored:
                scored = _rank_sections_fts5(
                    sections=sections,
                    query_tokens=query_tokens,
                    intent_weight=normalized_intent_weight,
                )
                backend = "fts5_bm25"
            if not scored:
                backend = "python_bm25"
                backend_fallback_reason = "fts5_empty_result"
                scored = _rank_sections(
                    sections=sections,
                    query_tokens=query_tokens,
                    intent_weight=normalized_intent_weight,
                )
        except Exception as exc:  # pragma: no cover - fail-open protection
            backend = "python_bm25"
            backend_fallback_reason = f"fts5_error:{exc.__class__.__name__}"
            scored = _rank_sections(
                sections=sections,
                query_tokens=query_tokens,
                intent_weight=normalized_intent_weight,
            )
    else:
        backend_fallback_reason = "fts5_unavailable"
        scored = _rank_sections(
            sections=sections,
            query_tokens=query_tokens,
            intent_weight=normalized_intent_weight,
        )

    evidence: list[dict[str, Any]] = []
    hint_sources: list[dict[str, Any]] = []
    repo_glossary_set = {str(token).strip().lower() for token in repo_glossary}
    for row in scored[: max(1, int(max_sections))]:
        body = str(row["body"])
        doc_title = _derive_doc_title(
            path=str(row["path"]),
            heading=str(row["heading"]),
            heading_path=str(row["heading_path"]),
        )
        glossary_terms = _derive_glossary_terms(
            heading_path=str(row["heading_path"]),
            body=body,
            matched_terms=list(row["matched_terms"]),
            query_tokens=query_tokens,
            repo_glossary=repo_glossary,
        )
        payload = {
            "path": str(row["path"]),
            "heading": str(row["heading"]),
            "heading_path": str(row["heading_path"]),
            "line_start": int(row["line_start"]),
            "line_end": int(row["line_end"]),
            "score": float(round(row["score"], 8)),
            "matched_terms": list(row["matched_terms"]),
            "doc_title": doc_title,
            "glossary_terms": glossary_terms,
            "repo_glossary_terms": [
                token
                for token in glossary_terms
                if str(token).strip().lower() in repo_glossary_set
            ][:4],
            "snippet": _build_contextual_snippet(
                path=str(row["path"]),
                heading=str(row["heading"]),
                heading_path=str(row["heading_path"]),
                body=body,
                matched_terms=list(row["matched_terms"]),
                query_tokens=query_tokens,
                doc_title=doc_title,
                glossary_terms=glossary_terms,
                repo_glossary=repo_glossary,
            ),
        }
        evidence.append(payload)

        hint_sources.append({**payload, "body": body})

    hints = _hint_extract_code_hints(
        evidence=hint_sources,
        query_tokens=query_tokens,
        path_hint_re=_PATH_HINT_RE,
        module_hint_re=_MODULE_HINT_RE,
        symbol_hint_re=_SYMBOL_HINT_RE,
        normalize_path=_normalize_path,
        normalize_module=_normalize_module,
        normalize_symbol=_normalize_symbol,
        normalize_score_table=_normalize_score_table,
        extract_code_fence_values=lambda blob: _hint_extract_code_fence_values(
            blob, code_fence_re=_CODE_FENCE_RE
        ),
    )
    explainability = _build_docs_explainability(
        reason="ok",
        backend=backend,
        fallback_reason=backend_fallback_reason,
        evidence=evidence,
        hints=hints,
    )
    return {
        "enabled": True,
        "reason": "ok",
        "backend": backend,
        "backend_fallback_reason": backend_fallback_reason,
        "cache_hit": bool(cache_hit),
        "cache_layer": str(cache_layer or "none"),
        "cache_store_written": bool(cache_store_written),
        "cache_path": str(cache_path or ""),
        "mirror": mirror_payload,
        "docs_fingerprint": docs_fingerprint,
        "section_pool_size": len(sections),
        "section_count": len(evidence),
        "query_token_count": len(query_tokens),
        "repo_glossary_size": len(repo_glossary),
        "repo_glossary_sample": list(repo_glossary[:12]),
        "repo_glossary_cache_hit": bool(repo_glossary_cache_hit),
        "repo_glossary_cache_layer": str(repo_glossary_cache_layer or "none"),
        "repo_glossary_cache_store_written": bool(repo_glossary_cache_store_written),
        "repo_glossary_cache_path": str(repo_glossary_cache_path or ""),
        "evidence": evidence,
        "hints": hints,
        "explainability": explainability,
        "elapsed_ms": _elapsed_ms(started),
    }


def _disabled_payload(*, reason: str, elapsed_ms: float) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "backend": "disabled",
        "backend_fallback_reason": "",
        "cache_hit": False,
        "cache_layer": "none",
        "cache_store_written": False,
        "cache_path": "",
        "docs_fingerprint": "",
        "section_pool_size": 0,
        "section_count": 0,
        "query_token_count": 0,
        "repo_glossary_size": 0,
        "repo_glossary_sample": [],
        "repo_glossary_cache_hit": False,
        "repo_glossary_cache_layer": "none",
        "repo_glossary_cache_store_written": False,
        "repo_glossary_cache_path": "",
        "evidence": [],
        "hints": {
            "paths": [],
            "modules": [],
            "symbols": [],
            "path_scores": [],
            "module_scores": [],
            "symbol_scores": [],
        },
        "explainability": _build_docs_explainability(
            reason=reason,
            backend="disabled",
            fallback_reason="",
            evidence=[],
            hints={},
        ),
        "elapsed_ms": round(float(elapsed_ms), 3),
    }


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000.0, 3)


def _build_docs_explainability(
    *,
    reason: str,
    backend: str,
    fallback_reason: str,
    evidence: list[dict[str, Any]],
    hints: dict[str, Any],
) -> dict[str, Any]:
    matched_term_counts: Counter[str] = Counter()
    evidence_sources: list[dict[str, Any]] = []
    for item in evidence[:6]:
        if not isinstance(item, dict):
            continue
        matched_terms = [
            str(term).strip()
            for term in item.get("matched_terms", [])
            if str(term).strip()
        ][:6]
        matched_term_counts.update(matched_terms)
        evidence_sources.append(
            {
                "path": str(item.get("path", "")),
                "heading_path": str(item.get("heading_path", "")),
                "doc_title": str(item.get("doc_title", "")),
                "score": float(item.get("score", 0.0) or 0.0),
                "matched_terms": matched_terms,
            }
        )

    top_matched_terms = [
        {"value": term, "count": count}
        for term, count in sorted(
            matched_term_counts.items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[:6]
    ]
    path_hints = _limit_hint_scores(hints.get("path_scores"))
    module_hints = _limit_hint_scores(hints.get("module_scores"))
    symbol_hints = _limit_hint_scores(hints.get("symbol_scores"))

    notes: list[str] = []
    for note in (
        f"reason:{str(reason).strip()}",
        f"backend:{str(backend).strip()}",
        f"fallback:{str(fallback_reason).strip()}" if str(fallback_reason).strip() else "",
        (
            "matched:" + ",".join(str(item["value"]) for item in top_matched_terms[:4])
            if top_matched_terms
            else ""
        ),
        (
            f"hinted_path:{path_hints[0]['value']}"
            if path_hints and str(path_hints[0].get("value", "")).strip()
            else ""
        ),
        (
            f"hinted_module:{module_hints[0]['value']}"
            if module_hints and str(module_hints[0].get("value", "")).strip()
            else ""
        ),
        (
            f"hinted_symbol:{symbol_hints[0]['value']}"
            if symbol_hints and str(symbol_hints[0].get("value", "")).strip()
            else ""
        ),
    ):
        normalized = str(note or "").strip()
        if normalized and normalized not in notes:
            notes.append(normalized)

    return {
        "reason": str(reason or ""),
        "backend": str(backend or ""),
        "fallback_reason": str(fallback_reason or ""),
        "top_matched_terms": top_matched_terms,
        "evidence_sources": evidence_sources,
        "path_hints": path_hints,
        "module_hints": module_hints,
        "symbol_hints": symbol_hints,
        "selection_notes": notes,
    }


def _limit_hint_scores(raw_rows: Any, *, limit: int = 4) -> list[dict[str, Any]]:
    rows = raw_rows if isinstance(raw_rows, list) else []
    output: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        score = item.get("score", 0.0)
        if not value or not isinstance(score, (int, float)):
            continue
        output.append(
            {
                "value": value,
                "score": round(float(score), 6),
            }
        )
        if len(output) >= max(1, int(limit)):
            break
    return output


def _load_sections(
    *,
    root: Path,
    max_files: int,
    max_section_chars: int,
) -> tuple[list[dict[str, Any]], str, bool, str, bool, str]:
    return _cache_load_sections(
        root=root,
        max_files=max_files,
        max_section_chars=max_section_chars,
        section_cache=_SECTION_CACHE,
        sections_cache_path=_DOCS_SECTION_CACHE_PATH,
        collect_docs_paths=_loading_collect_docs_paths,
        docs_fingerprint=_loading_docs_fingerprint,
        parse_markdown_sections=_loading_parse_markdown_sections,
        load_sections_from_disk_cache=_load_sections_from_disk_cache,
        store_sections_to_disk_cache=_store_sections_to_disk_cache,
    )


def _resolve_sections_cache_path(*, root: Path) -> Path:
    return _cache_resolve_sections_cache_path(
        root=root,
        relative_cache_path=_DOCS_SECTION_CACHE_PATH,
    )


def _resolve_repo_glossary_cache_path(*, root: Path) -> Path:
    return _cache_resolve_repo_glossary_cache_path(
        root=root,
        relative_cache_path=_DOCS_REPO_GLOSSARY_CACHE_PATH,
    )


def _load_repo_glossary(
    *,
    root: Path,
    docs_fingerprint: str,
    sections: list[dict[str, Any]],
    max_terms: int = 128,
) -> tuple[list[str], bool, str, bool, str]:
    return _cache_load_repo_glossary(
        root=root,
        docs_fingerprint=docs_fingerprint,
        sections=sections,
        repo_glossary_cache=_REPO_GLOSSARY_CACHE,
        glossary_cache_path=_DOCS_REPO_GLOSSARY_CACHE_PATH,
        load_repo_glossary_from_disk_cache=_load_repo_glossary_from_disk_cache,
        store_repo_glossary_to_disk_cache=_store_repo_glossary_to_disk_cache,
        build_repo_glossary=_build_repo_glossary,
        max_terms=max_terms,
    )


def _load_repo_glossary_from_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_terms: int,
) -> list[str] | None:
    return _cache_load_repo_glossary_from_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=docs_fingerprint,
        max_terms=max_terms,
        schema_version=_DOCS_REPO_GLOSSARY_CACHE_SCHEMA,
        is_glossary_token=_is_glossary_token,
    )


def _store_repo_glossary_to_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_terms: int,
    glossary: list[str],
) -> bool:
    return _cache_store_repo_glossary_to_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=docs_fingerprint,
        max_terms=max_terms,
        glossary=glossary,
        schema_version=_DOCS_REPO_GLOSSARY_CACHE_SCHEMA,
        is_glossary_token=_is_glossary_token,
    )


def _build_repo_glossary(
    *,
    sections: list[dict[str, Any]],
    max_terms: int,
) -> list[str]:
    return _glossary_build_repo_glossary(
        sections=sections,
        max_terms=max_terms,
        is_glossary_token=_is_glossary_token,
    )


def _load_sections_from_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_files: int,
    max_section_chars: int,
) -> list[dict[str, Any]] | None:
    return _cache_load_sections_from_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=docs_fingerprint,
        max_files=max_files,
        max_section_chars=max_section_chars,
        schema_version=_DOCS_SECTION_CACHE_SCHEMA,
        normalize_cached_section=_loading_normalize_cached_section,
    )


def _store_sections_to_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_files: int,
    max_section_chars: int,
    sections: list[dict[str, Any]],
) -> bool:
    return _cache_store_sections_to_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=docs_fingerprint,
        max_files=max_files,
        max_section_chars=max_section_chars,
        sections=sections,
        schema_version=_DOCS_SECTION_CACHE_SCHEMA,
        serialize_section_for_cache=_loading_serialize_section_for_cache,
    )


def _build_query_tokens(*, query: str, terms: list[str]) -> list[str]:
    return _ranking_build_query_tokens(
        query=query,
        terms=terms,
        token_re=_TOKEN_RE,
    )


def _rank_sections(
    *,
    sections: list[dict[str, Any]],
    query_tokens: list[str],
    intent_weight: float,
) -> list[dict[str, Any]]:
    return _ranking_rank_sections(
        sections=sections,
        query_tokens=query_tokens,
        intent_weight=intent_weight,
        doc_intent_markers=_DOC_INTENT_MARKERS,
        term_frequency=_term_frequency,
    )


def _rank_sections_fts5(
    *,
    sections: list[dict[str, Any]],
    query_tokens: list[str],
    intent_weight: float,
) -> list[dict[str, Any]]:
    return _ranking_rank_sections_fts5(
        sections=sections,
        query_tokens=query_tokens,
        intent_weight=intent_weight,
        doc_intent_markers=_DOC_INTENT_MARKERS,
        build_fts5_query=_build_fts5_query,
        term_frequency=_term_frequency,
        normalize_fts5_score=_normalize_fts5_score,
    )


def _rank_sections_mirror_fts5(
    *,
    sections: list[dict[str, Any]],
    query_tokens: list[str],
    intent_weight: float,
    db_path: Path,
    limit: int,
) -> list[dict[str, Any]]:
    return _ranking_rank_sections_mirror_fts5(
        sections=sections,
        query_tokens=query_tokens,
        intent_weight=intent_weight,
        db_path=db_path,
        limit=limit,
        doc_intent_markers=_DOC_INTENT_MARKERS,
        build_fts5_query=_build_fts5_query,
        term_frequency=_term_frequency,
        normalize_fts5_score=_normalize_fts5_score,
        query_docs_fts=query_docs_fts,
    )


def _build_fts5_query(*, query_tokens: list[str]) -> str:
    return _ranking_build_fts5_query(query_tokens=query_tokens)


def _normalize_fts5_score(raw_score: float) -> float:
    return _ranking_normalize_fts5_score(raw_score)


def _sqlite_supports_fts5() -> bool:
    global _FTS5_AVAILABLE
    if _FTS5_AVAILABLE is None:
        _FTS5_AVAILABLE = _ranking_sqlite_supports_fts5()
    return bool(_FTS5_AVAILABLE)


def _term_frequency(*, item: dict[str, Any], token: str) -> float:
    return _ranking_term_frequency(item=item, token=token)


def _build_snippet(*, text: str, query_tokens: list[str], max_chars: int = 240) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    lowered_tokens = tuple(query_tokens)
    for line in lines:
        lowered = line.lower()
        if any(token in lowered for token in lowered_tokens):
            return line[:max_chars].rstrip()

    return lines[0][:max_chars].rstrip()


def _build_contextual_snippet(
    *,
    path: str,
    heading: str,
    heading_path: str,
    body: str,
    matched_terms: list[str],
    query_tokens: list[str],
    doc_title: str,
    glossary_terms: list[str],
    repo_glossary: list[str] | None = None,
    max_chars: int = 240,
) -> str:
    limit = max(1, int(max_chars))
    normalized_path = str(path or "").strip()
    normalized_heading = str(heading or "").strip()
    normalized_heading_path = str(heading_path or "").strip()
    if not normalized_heading_path:
        normalized_heading_path = normalized_heading
    if not normalized_heading_path:
        normalized_heading_path = PurePath(normalized_path).name

    normalized_doc_title = str(doc_title or "").strip()
    if not normalized_doc_title:
        normalized_doc_title = _derive_doc_title(
            path=normalized_path,
            heading=normalized_heading,
            heading_path=normalized_heading_path,
        )

    prefix_lines: list[str] = []
    seen_prefix: set[str] = set()
    for line in (
        normalized_doc_title,
        normalized_heading_path,
        normalized_path,
    ):
        normalized = str(line or "").strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen_prefix:
            continue
        seen_prefix.add(key)
        prefix_lines.append(normalized)

    terms = glossary_terms or _derive_glossary_terms(
        heading_path=normalized_heading_path,
        body=body,
        matched_terms=matched_terms,
        query_tokens=query_tokens,
        repo_glossary=repo_glossary,
    )
    if terms:
        prefix_lines.append(f"terms: {', '.join(terms[:6])}")

    prefix = "\n".join(prefix_lines).strip()
    snippet = _build_snippet(text=body, query_tokens=query_tokens, max_chars=limit)
    combined = f"{prefix}\n{snippet}" if snippet and prefix else snippet or prefix
    return combined[:limit].rstrip()


def _derive_doc_title(*, path: str, heading: str, heading_path: str) -> str:
    normalized_heading_path = str(heading_path or "").strip()
    if normalized_heading_path:
        title = str(normalized_heading_path.split(" > ", 1)[0]).strip()
        if title:
            return title

    normalized_heading = str(heading or "").strip()
    if normalized_heading:
        return normalized_heading

    normalized_path = str(path or "").strip()
    if normalized_path:
        return PurePath(normalized_path).name
    return ""


def _derive_glossary_terms(
    *,
    heading_path: str,
    body: str,
    matched_terms: list[str],
    query_tokens: list[str],
    repo_glossary: list[str] | None = None,
    max_terms: int = 6,
) -> list[str]:
    return _glossary_derive_glossary_terms(
        heading_path=heading_path,
        body=body,
        matched_terms=matched_terms,
        query_tokens=query_tokens,
        repo_glossary=repo_glossary,
        max_terms=max_terms,
        token_re=_TOKEN_RE,
        module_hint_re=_MODULE_HINT_RE,
        symbol_hint_re=_SYMBOL_HINT_RE,
        is_glossary_token=_is_glossary_token,
        build_snippet=_build_snippet,
    )


def _is_glossary_token(token: str) -> bool:
    return _glossary_is_glossary_token(
        token=token,
        glossary_stopwords=_GLOSSARY_STOPWORDS,
        module_stopwords=_MODULE_STOPWORDS,
    )


def _normalize_score_table(raw_scores: dict[str, float], *, limit: int = 12) -> list[dict[str, Any]]:
    if not raw_scores:
        return []
    max_score = max(float(value) for value in raw_scores.values())
    if max_score <= 0.0:
        return []

    pairs: list[tuple[str, float]] = [
        (key, round(float(value) / max_score, 6))
        for key, value in raw_scores.items()
        if float(value) > 0.0
    ]
    pairs.sort(key=lambda item: (-float(item[1]), str(item[0])))
    limit_effective = max(1, int(limit))
    return [{"value": key, "score": score} for key, score in pairs[:limit_effective]]


def _normalize_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _normalize_module(value: str) -> str:
    module = str(value or "").strip().strip(".")
    if not module or "/" in module or module.lower() in _MODULE_STOPWORDS:
        return ""
    if module.endswith(
        (
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".go",
            ".md",
            ".mdx",
            ".rst",
            ".txt",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
            ".jsonl",
        )
    ):
        return ""
    parts = [item for item in module.split(".") if item]
    if len(parts) < 2:
        return ""
    if any(len(item) > 64 for item in parts):
        return ""
    return ".".join(parts)


def _normalize_symbol(value: str) -> str:
    symbol = str(value or "").strip()
    if len(symbol) < 3:
        return ""
    lowered = symbol.lower()
    if lowered in _MODULE_STOPWORDS:
        return ""
    if lowered in _DOC_INTENT_MARKERS:
        return ""
    return symbol


__all__ = ["collect_docs_signals"]
