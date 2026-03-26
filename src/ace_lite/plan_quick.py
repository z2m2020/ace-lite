from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.index_stage.policy import resolve_retrieval_policy
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.repomap.builder import build_repo_map, build_stage_repo_map
from ace_lite.retrieval_shared import (
    CandidateSelectionResult,
    build_retrieval_runtime_profile,
    build_selection_observability,
    extract_retrieval_terms,
    load_retrieval_index_snapshot,
    select_initial_candidates,
)

PLAN_QUICK_STEPS: tuple[str, ...] = (
    "Inspect candidate_files in order.",
    "Open highest-fused files and confirm symbol-level relevance.",
    "Escalate to ace_plan only after narrowing to concrete edit targets.",
)

_DOC_SYNC_MARKERS: tuple[str, ...] = (
    "doc",
    "docs",
    "markdown",
    "readme",
    "planning",
    "plan",
    "progress",
    "status",
    "report",
    "roadmap",
    "runbook",
    "sync",
    "update",
    "latest",
    "文档",
    "说明",
    "同步",
    "更新",
    "最新",
    "状态",
    "进展",
    "报告",
    "路线图",
)
_LATEST_MARKERS: tuple[str, ...] = (
    "latest",
    "recent",
    "sync",
    "update",
    "current",
    "最近",
    "最新",
    "同步",
    "更新",
    "当前",
)
_DOC_PREFERRED_PREFIXES: tuple[str, ...] = (
    "docs/",
    "doc/",
    "planning/",
    "plans/",
    "repos/",
    "reports/",
)
_DOC_PREFERRED_NAME_MARKERS: tuple[str, ...] = (
    "readme",
    "progress",
    "status",
    "report",
    "roadmap",
    "runbook",
    "overview",
    "summary",
    "changelog",
)
_DOC_PENALIZED_PREFIXES: tuple[tuple[str, float], ...] = (
    ("tests/", -3.5),
    ("test/", -3.5),
    ("research/", -6.0),
    ("reference/", -6.0),
    ("src/", -2.0),
    ("internal/", -2.0),
    ("pkg/", -2.0),
)
_MARKDOWN_LANGUAGES: frozenset[str] = frozenset({"markdown", "md"})


def _query_flags(query: str) -> dict[str, bool]:
    lowered = str(query or "").lower().strip()
    has_doc_sync_markers = any(marker in lowered for marker in _DOC_SYNC_MARKERS)
    latest_sensitive = any(marker in lowered for marker in _LATEST_MARKERS)
    return {
        "doc_sync": has_doc_sync_markers,
        "latest_sensitive": latest_sensitive,
    }


def _classify_path_domain(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/").lower()
    if normalized.startswith(("docs/", "doc/")):
        return "docs"
    if normalized.startswith(("planning/", "plans/")) or "/planning/" in normalized:
        return "planning"
    if normalized.startswith("repos/"):
        return "repos"
    if normalized.startswith("reports/"):
        return "reports"
    if normalized.startswith(("research/", "reference/")):
        return "research"
    if normalized.startswith(("tests/", "test/")):
        return "tests"
    if normalized.endswith((".md", ".mdx")):
        return "markdown"
    return "code"


def _doc_sync_intent_boost(*, path: str, language: str, query_flags: dict[str, bool]) -> float:
    if not bool(query_flags.get("doc_sync", False)):
        return 0.0
    normalized_path = str(path or "").strip().replace("\\", "/").lower()
    normalized_language = str(language or "").strip().lower()
    boost = 0.0
    if normalized_language in _MARKDOWN_LANGUAGES or normalized_path.endswith((".md", ".mdx")):
        boost += 4.0
    if normalized_path.startswith(_DOC_PREFERRED_PREFIXES):
        boost += 3.0
    if any(marker in normalized_path for marker in _DOC_PREFERRED_NAME_MARKERS):
        boost += 2.0
    for prefix, penalty in _DOC_PENALIZED_PREFIXES:
        if normalized_path.startswith(prefix):
            boost += penalty
            break
    return boost


def _build_plan_quick_risk_hints(
    *,
    query: str,
    rows: list[PlanQuickScoredRow],
    retrieval_policy_profile: str,
    index_cache: dict[str, Any],
) -> list[dict[str, Any]]:
    query_flags = _query_flags(query)
    hints: list[dict[str, Any]] = []
    top_rows = rows[:5]
    if bool(query_flags.get("doc_sync", False)):
        top_domains = {
            _classify_path_domain(item.path)
            for item in top_rows
            if str(item.path or "").strip()
        }
        if retrieval_policy_profile != "doc_intent":
            hints.append(
                {
                    "code": "doc_sync_policy_mismatch",
                    "severity": "medium",
                    "message": "query 更像文档同步任务, 但当前 retrieval policy 未落到 doc_intent。",
                    "action": "建议追加 docs/planning/progress/status 之类的目录或状态词, 或直接限制目标子目录。",
                }
            )
        if len(top_domains) >= 3 and any(
            domain in top_domains for domain in ("code", "research", "tests")
        ):
            hints.append(
                {
                    "code": "cross_domain_mix",
                    "severity": "high",
                    "message": "前排候选混入多个语义域, 结果可能需要人工纠偏。",
                    "action": "优先阅读前 3 个 markdown/docs/planning 候选, 再决定是否升级到 ace_plan。",
                }
            )
        if top_rows and not any(
            str(item.language or "").lower() in _MARKDOWN_LANGUAGES
            or str(item.path or "").lower().endswith((".md", ".mdx"))
            for item in top_rows[:3]
        ):
            hints.append(
                {
                    "code": "markdown_underweighted",
                    "severity": "medium",
                    "message": "文档同步 query 的前排结果缺少 markdown 入口文档。",
                    "action": "建议把 query 收紧到 docs planning repo progress status latest, 或直接指定 markdown 目录。",
                }
            )
    if str(index_cache.get("mode") or "").strip() == "full_build":
        hints.append(
            {
                "code": "index_cold_start",
                "severity": "low",
                "message": "本次 quick plan 触发了 full build, 首轮耗时会偏高。",
                "action": "若仓库无本地改动, 后续再次运行通常会转为 cache_only; 也可先执行 ace_index 预热索引。",
                "reason": str(
                    index_cache.get("full_build_reason")
                    or index_cache.get("reason")
                    or "cache_missing"
                ),
            }
        )
    return hints


def build_plan_quick_policy_observability(
    *,
    query: str,
) -> tuple[str, dict[str, Any]]:
    policy = resolve_retrieval_policy(
        query=str(query or "").strip(),
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )
    policy_name = str(policy.get("name", "general") or "general")
    return policy_name, {
        "requested": "auto",
        "selected": policy_name,
        "source": str(policy.get("source", "") or ""),
        "version": str(policy.get("version", "") or ""),
        "embedding_enabled": bool(policy.get("embedding_enabled", False)),
        "docs_enabled": bool(policy.get("docs_enabled", False)),
        "repomap_enabled": bool(policy.get("repomap_enabled", False)),
        "graph_lookup_enabled": bool(policy.get("graph_lookup_enabled", False)),
        "chunk_semantic_rerank_enabled": bool(
            policy.get("chunk_semantic_rerank_enabled", False)
        ),
        "semantic_rerank_time_budget_ms": int(
            policy.get("semantic_rerank_time_budget_ms", 0) or 0
        ),
    }


@dataclass(frozen=True, slots=True)
class PlanQuickScoredRow:
    path: str
    module: str
    language: str
    score: float
    lexical_hits: int
    lexical_boost: float
    intent_boost: float
    fused_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "module": self.module,
            "language": self.language,
            "score": float(self.score),
            "lexical_hits": int(self.lexical_hits),
            "lexical_boost": float(self.lexical_boost),
            "intent_boost": float(self.intent_boost),
            "fused_score": float(self.fused_score),
        }


def score_plan_quick_rows(
    *,
    query: str,
    rows: list[dict[str, Any]],
    lexical_boost_per_hit: float = 5.0,
) -> list[PlanQuickScoredRow]:
    normalized_query = str(query or "").strip()
    tokens = [token for token in normalized_query.lower().split() if token]
    boost_per_hit = float(lexical_boost_per_hit)
    query_flags = _query_flags(normalized_query)

    scored: list[PlanQuickScoredRow] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        module = str(item.get("module", "") or "")
        language = str(item.get("language", "") or "")
        base_score = float(item.get("score", 0.0) or 0.0)
        blob = f"{path} {module}".lower()
        lexical_hits = sum(1 for token in tokens if token in blob)
        lexical_boost = float(lexical_hits) * boost_per_hit
        intent_boost = _doc_sync_intent_boost(
            path=path,
            language=language,
            query_flags=query_flags,
        )
        fused_score = base_score + lexical_boost + intent_boost
        scored.append(
            PlanQuickScoredRow(
                path=path,
                module=module,
                language=language,
                score=base_score,
                lexical_hits=lexical_hits,
                lexical_boost=lexical_boost,
                intent_boost=intent_boost,
                fused_score=fused_score,
            )
        )

    scored.sort(key=lambda row: (-float(row.fused_score), str(row.path)))
    return scored


def build_plan_quick(
    *,
    query: str,
    root: str | Path,
    languages: str,
    top_k_files: int = 8,
    repomap_top_k: int = 24,
    candidate_ranker: str = "rrf_hybrid",
    index_cache_path: str = "context-map/index.json",
    index_incremental: bool = True,
    repomap_expand: bool = False,
    repomap_neighbor_limit: int = 20,
    repomap_neighbor_depth: int = 1,
    budget_tokens: int = 800,
    ranking_profile: str = "graph",
    include_rows: bool = False,
    tokenizer_model: str | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    root_path = Path(root).expanduser().resolve()
    language_csv = str(languages or "").strip()
    languages_parsed = parse_language_csv(language_csv)

    cache_path = Path(str(index_cache_path or "context-map/index.json")).expanduser()
    if not cache_path.is_absolute():
        cache_path = root_path / cache_path

    snapshot = load_retrieval_index_snapshot(
        root_dir=str(root_path),
        cache_path=str(cache_path),
        languages=languages_parsed,
        incremental=bool(index_incremental),
        fail_open=False,
        include_index_hash=False,
    )
    index_payload = snapshot.index_payload
    cache_info = snapshot.cache_info
    if isinstance(cache_info, dict) and str(cache_info.get("mode") or "") == "full_build":
        cache_info = dict(cache_info)
        cache_info["full_build_reason"] = str(
            cache_info.get("full_build_reason")
            or cache_info.get("reason")
            or "cache_missing"
        )
    repo_map: dict[str, Any] = {}
    files_map = snapshot.files_map

    ranking_source = "ranker"
    pool_size = max(1, int(repomap_top_k))
    top_k = max(1, int(top_k_files))
    candidate_pool_size = max(pool_size, top_k)
    corpus_size = snapshot.corpus_size

    terms = extract_retrieval_terms(query=normalized_query, memory_stage={})
    retrieval_policy_profile, retrieval_policy_observability = (
        build_plan_quick_policy_observability(query=normalized_query)
    )
    runtime_profile = build_retrieval_runtime_profile(
        candidate_ranker=str(candidate_ranker or ""),
        min_candidate_score=1,
        top_k_files=candidate_pool_size,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=60,
        hybrid_weights={},
        index_hash=None,
        allow_empty_terms_fail_open=False,
    )
    selection: CandidateSelectionResult = select_initial_candidates(
        files_map=files_map,
        terms=terms,
        **runtime_profile.selection_kwargs(corpus_size=corpus_size),
    )
    pooled_candidates = list(selection.candidates)[: int(runtime_profile.top_k_files)]
    selection_observability = build_selection_observability(
        requested_ranker=selection.requested_ranker,
        selected_ranker=selection.selected_ranker,
        fallback_reasons=list(selection.fallback_reasons),
        min_score_used=int(selection.min_score_used),
        corpus_size=corpus_size,
        terms_count=len(terms),
    )

    rows: list[dict[str, Any]] = []
    for item in pooled_candidates:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        if not path:
            continue
        entry = files_map.get(path, {})
        if not isinstance(entry, dict):
            entry = {}
        rows.append(
            {
                "path": path,
                "module": str(item.get("module", "") or ""),
                "language": str(item.get("language", "") or ""),
                "score": float(item.get("score", 0.0) or 0.0),
                "generated": bool(entry.get("generated")),
            }
        )

    if not rows:
        # Safety fallback: if heuristic ranking yields nothing (for example, bad
        # language detection or indexing anomalies), fall back to a static repo
        # map so callers still get deterministic suggestions.
        ranking_source = "repomap"
        repo_map = build_repo_map(
            index_payload=index_payload,
            budget_tokens=max(1, int(budget_tokens)),
            top_k=max(1, int(repomap_top_k)),
            ranking_profile=str(ranking_profile or "graph").strip().lower() or "graph",
            tokenizer_model=tokenizer_model,
        )

        rows = repo_map.get("files", [])
        if not isinstance(rows, list):
            rows = []
        rescored_rows = score_plan_quick_rows(
            query=normalized_query,
            rows=rows,
            lexical_boost_per_hit=5.0,
        )
    else:
        rescored_rows = score_plan_quick_rows(
            query=normalized_query,
            rows=rows,
            lexical_boost_per_hit=0.0,
        )

    limited_rows = rescored_rows[:top_k]
    candidate_paths = [row.path for row in limited_rows if row.path]

    repomap_stage: dict[str, Any] | None = None
    if repomap_expand:
        try:
            repomap_stage = build_stage_repo_map(
                index_files=files_map,
                seed_candidates=pooled_candidates,
                ranking_profile=str(ranking_profile or "graph").strip().lower() or "graph",
                top_k=min(top_k, len(pooled_candidates)),
                neighbor_limit=max(0, int(repomap_neighbor_limit)),
                neighbor_depth=max(1, int(repomap_neighbor_depth)),
                budget_tokens=max(1, int(budget_tokens)),
                tokenizer_model=tokenizer_model,
            )
        except Exception:
            repomap_stage = {
                "enabled": False,
                "seed_paths": [],
                "neighbor_paths": [],
                "focused_files": candidate_paths,
                "error": "repomap_expand_failed",
            }

    response: dict[str, Any] = {
        "query": normalized_query,
        "root": str(root_path),
        "languages": language_csv,
        "candidate_files": candidate_paths,
        "source_plan_steps": len(PLAN_QUICK_STEPS),
        "steps": list(PLAN_QUICK_STEPS),
        "ranking_source": ranking_source,
        "candidate_ranker": str(selection_observability["requested"]),
        "candidate_ranker_selected": str(selection_observability["selected"]),
        "candidate_ranker_fallbacks": list(selection_observability["fallbacks"]),
        "candidate_min_score_used": int(selection_observability["min_score_used"]),
        "retrieval_policy_profile": retrieval_policy_profile,
        "retrieval_policy_observability": retrieval_policy_observability,
        "terms": list(terms),
        "index_cache_path": str(cache_path),
        "index_cache": dict(cache_info or {}),
        "repomap_stage": repomap_stage,
        "total_ms": float(
            max(
                0.0,
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000.0,
            )
        ),
        "repomap_used_tokens": int(repo_map.get("used_tokens", 0) or 0) if ranking_source == "repomap" else 0,
        "repomap_budget_tokens": int(repo_map.get("budget_tokens", budget_tokens) or 0) if ranking_source == "repomap" else int(budget_tokens),
        "ranking_profile": str(
            repo_map.get("ranking_profile", "") or str(ranking_profile or "graph")
        )
        if ranking_source == "repomap"
        else str(ranking_profile or "graph"),
        "query_profile": _query_flags(normalized_query),
        "risk_hints": _build_plan_quick_risk_hints(
            query=normalized_query,
            rows=limited_rows,
            retrieval_policy_profile=retrieval_policy_profile,
            index_cache=dict(cache_info or {}),
        ),
    }
    if include_rows:
        response["rows"] = [row.as_dict() for row in limited_rows]
    return response


__all__ = [
    "PLAN_QUICK_STEPS",
    "PlanQuickScoredRow",
    "build_plan_quick",
    "build_plan_quick_policy_observability",
    "score_plan_quick_rows",
]
