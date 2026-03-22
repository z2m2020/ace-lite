from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.parsers.languages import parse_language_csv
from ace_lite.index_stage.policy import resolve_retrieval_policy
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
    fused_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "module": self.module,
            "language": self.language,
            "score": float(self.score),
            "lexical_hits": int(self.lexical_hits),
            "lexical_boost": float(self.lexical_boost),
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

    scored: list[PlanQuickScoredRow] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        module = str(item.get("module", "") or "")
        base_score = float(item.get("score", 0.0) or 0.0)
        blob = f"{path} {module}".lower()
        lexical_hits = sum(1 for token in tokens if token in blob)
        lexical_boost = float(lexical_hits) * boost_per_hit
        fused_score = base_score + lexical_boost
        scored.append(
            PlanQuickScoredRow(
                path=path,
                module=module,
                language=str(item.get("language", "") or ""),
                score=base_score,
                lexical_hits=lexical_hits,
                lexical_boost=lexical_boost,
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
    }
    if include_rows:
        response["rows"] = [row.as_dict() for row in limited_rows]
    return response


__all__ = [
    "PLAN_QUICK_STEPS",
    "PlanQuickScoredRow",
    "build_plan_quick_policy_observability",
    "build_plan_quick",
    "score_plan_quick_rows",
]
