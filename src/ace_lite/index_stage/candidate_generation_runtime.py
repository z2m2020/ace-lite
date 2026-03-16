from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ace_lite.index_stage.candidate_generation import (
    InitialCandidateGenerationDeps,
    InitialCandidateGenerationResult,
)


@dataclass(slots=True)
class IndexCandidateGenerationRuntimeResult:
    initial_candidates: InitialCandidateGenerationResult
    docs_timing_ms: float
    worktree_timing_ms: float
    raw_worktree: dict[str, Any] | None


def run_index_candidate_generation(
    *,
    root: str,
    query: str,
    terms: list[str],
    files_map: dict[str, Any],
    corpus_size: int,
    runtime_profile: Any,
    top_k_files: int,
    exact_search_enabled: bool,
    exact_search_time_budget_ms: int,
    exact_search_max_paths: int,
    languages: list[str],
    docs_policy_enabled: bool,
    worktree_prior_enabled: bool,
    cochange_enabled: bool,
    docs_intent_weight: float,
    parallel_requested: bool,
    parallel_time_budget_ms: int,
    policy: dict[str, Any],
    gather_initial_candidates_fn: Callable[..., InitialCandidateGenerationResult],
    build_exact_search_payload_fn: Callable[..., dict[str, Any]],
    select_initial_candidates_fn: Callable[..., Any],
    apply_exact_search_boost_fn: Callable[..., Any],
    collect_parallel_signals_fn: Callable[..., Any],
    apply_candidate_priors_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
    collect_docs_fn: Callable[..., dict[str, Any]],
    collect_worktree_fn: Callable[..., dict[str, Any]],
    disabled_docs_payload_fn: Callable[..., dict[str, Any]],
    disabled_worktree_prior_fn: Callable[..., dict[str, Any]],
    get_executor_fn: Callable[[], Any],
    resolve_future_fn: Callable[..., tuple[Any, bool, str]],
    run_exact_search_fn: Callable[..., Any],
    score_exact_hits_fn: Callable[..., dict[str, float]],
    normalize_repo_path_fn: Callable[[str], str],
    supported_extensions_fn: Callable[..., set[str]],
    mark_timing_fn: Callable[[str, float], None],
) -> IndexCandidateGenerationRuntimeResult:
    initial_candidates = gather_initial_candidates_fn(
        root=root,
        query=query,
        terms=terms,
        files_map=files_map,
        corpus_size=corpus_size,
        runtime_profile=runtime_profile,
        top_k_files=int(top_k_files),
        exact_search_enabled=bool(exact_search_enabled),
        exact_search_time_budget_ms=int(exact_search_time_budget_ms),
        exact_search_max_paths=int(exact_search_max_paths),
        exact_search_include_globs=[
            f"*{suffix}"
            for suffix in sorted(supported_extensions_fn(tuple(languages)))
            if suffix
        ][:12],
        docs_policy_enabled=bool(docs_policy_enabled),
        worktree_prior_enabled=bool(worktree_prior_enabled),
        cochange_enabled=bool(cochange_enabled),
        docs_intent_weight=float(docs_intent_weight),
        parallel_requested=bool(parallel_requested),
        parallel_time_budget_ms=int(parallel_time_budget_ms),
        policy=policy,
        deps=InitialCandidateGenerationDeps(
            build_exact_search_payload=build_exact_search_payload_fn,
            select_initial_candidates=select_initial_candidates_fn,
            apply_exact_search_boost=apply_exact_search_boost_fn,
            collect_parallel_signals=collect_parallel_signals_fn,
            apply_candidate_priors=apply_candidate_priors_fn,
            collect_docs=collect_docs_fn,
            collect_worktree=collect_worktree_fn,
            disabled_docs_payload=disabled_docs_payload_fn,
            disabled_worktree_prior=disabled_worktree_prior_fn,
            get_executor=get_executor_fn,
            resolve_future=resolve_future_fn,
            run_exact_search=run_exact_search_fn,
            score_exact_hits=score_exact_hits_fn,
            normalize_repo_path=normalize_repo_path_fn,
            mark_timing=mark_timing_fn,
        ),
    )
    return IndexCandidateGenerationRuntimeResult(
        initial_candidates=initial_candidates,
        docs_timing_ms=float(initial_candidates.docs_elapsed_ms),
        worktree_timing_ms=float(initial_candidates.worktree_elapsed_ms),
        raw_worktree=initial_candidates.raw_worktree
        if isinstance(initial_candidates.raw_worktree, dict)
        else None,
    )


__all__ = [
    "IndexCandidateGenerationRuntimeResult",
    "run_index_candidate_generation",
]
