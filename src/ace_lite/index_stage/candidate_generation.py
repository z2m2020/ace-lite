"""Initial candidate-generation orchestration for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ace_lite.retrieval_shared import CandidateSelectionResult, RetrievalRuntimeProfile


@dataclass(frozen=True, slots=True)
class InitialCandidateGenerationDeps:
    """Injected helper dependencies for the candidate-generation seam."""

    build_exact_search_payload: Callable[..., dict[str, Any]]
    select_initial_candidates: Callable[..., CandidateSelectionResult]
    apply_exact_search_boost: Callable[..., Any]
    collect_parallel_signals: Callable[..., Any]
    apply_candidate_priors: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
    collect_docs: Callable[..., dict[str, Any]]
    collect_worktree: Callable[..., dict[str, Any]]
    disabled_docs_payload: Callable[..., dict[str, Any]]
    disabled_worktree_prior: Callable[..., dict[str, Any]]
    get_executor: Callable[[], Any]
    resolve_future: Callable[..., tuple[Any, bool, str]]
    run_exact_search: Callable[..., Any]
    score_exact_hits: Callable[..., dict[str, float]]
    normalize_repo_path: Callable[[str], str]
    mark_timing: Callable[[str, float], None]


@dataclass(slots=True)
class InitialCandidateGenerationResult:
    requested_ranker: str
    selected_ranker: str
    ranker_fallbacks: list[str]
    min_score_used: int
    candidates: list[dict[str, Any]]
    exact_search_payload: dict[str, Any]
    docs_payload: dict[str, Any]
    worktree_prior: dict[str, Any]
    parallel_payload: dict[str, Any]
    prior_payload: dict[str, Any]
    docs_elapsed_ms: float
    worktree_elapsed_ms: float
    raw_worktree: dict[str, Any] | None


def gather_initial_candidates(
    *,
    root: str,
    query: str,
    terms: list[str],
    files_map: dict[str, Any],
    corpus_size: int,
    runtime_profile: RetrievalRuntimeProfile,
    top_k_files: int,
    exact_search_enabled: bool,
    exact_search_time_budget_ms: int,
    exact_search_max_paths: int,
    exact_search_include_globs: list[str],
    docs_policy_enabled: bool,
    worktree_prior_enabled: bool,
    cochange_enabled: bool,
    docs_intent_weight: float,
    parallel_requested: bool,
    parallel_time_budget_ms: int,
    policy: dict[str, Any],
    deps: InitialCandidateGenerationDeps,
) -> InitialCandidateGenerationResult:
    """Gather initial candidates plus additive docs/worktree prior signals."""

    exact_search_payload = deps.build_exact_search_payload(
        time_budget_ms=int(exact_search_time_budget_ms),
        max_paths=int(exact_search_max_paths),
    )

    timing_started = perf_counter()
    selection = deps.select_initial_candidates(
        files_map=files_map,
        terms=terms,
        **runtime_profile.selection_kwargs(corpus_size=corpus_size),
    )
    requested_ranker = selection.requested_ranker
    selected_ranker = selection.selected_ranker
    ranker_fallbacks = list(selection.fallback_reasons)
    min_score_used = int(selection.min_score_used)
    candidates = list(selection.candidates)
    deps.mark_timing("candidate_ranking", timing_started)

    if (
        bool(exact_search_enabled)
        and int(exact_search_time_budget_ms) > 0
        and int(exact_search_max_paths) > 0
        and isinstance(files_map, dict)
    ):
        timing_started = perf_counter()
        exact_search_result = deps.apply_exact_search_boost(
            root=root,
            query=query,
            files_map=files_map,
            candidates=candidates,
            include_globs=list(exact_search_include_globs),
            time_budget_ms=int(exact_search_time_budget_ms),
            max_paths=int(exact_search_max_paths),
            run_exact_search=deps.run_exact_search,
            score_exact_hits=deps.score_exact_hits,
        )
        candidates = list(exact_search_result.candidates)
        exact_search_payload = exact_search_result.payload
        deps.mark_timing("exact_search", timing_started)

    signal_result = deps.collect_parallel_signals(
        root=root,
        query=query,
        terms=terms,
        files_map=files_map,
        top_k_files=int(top_k_files),
        docs_policy_enabled=docs_policy_enabled,
        worktree_prior_enabled=worktree_prior_enabled,
        cochange_enabled=bool(cochange_enabled),
        docs_intent_weight=float(docs_intent_weight),
        parallel_requested=parallel_requested,
        parallel_time_budget_ms=int(parallel_time_budget_ms),
        collect_docs=deps.collect_docs,
        collect_worktree=deps.collect_worktree,
        disabled_docs_payload=deps.disabled_docs_payload,
        disabled_worktree_prior=deps.disabled_worktree_prior,
        get_executor=deps.get_executor,
        resolve_future=deps.resolve_future,
    )
    docs_payload = signal_result.docs_payload
    worktree_prior = signal_result.worktree_prior
    parallel_payload = signal_result.parallel_payload

    timing_started = perf_counter()
    candidates, prior_payload = deps.apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=int(top_k_files),
        query=query,
        query_terms=terms,
    )

    raw_worktree: dict[str, Any] | None = None
    if isinstance(worktree_prior, dict):
        raw_candidate = worktree_prior.get("raw")
        if isinstance(raw_candidate, dict):
            raw_worktree = raw_candidate

        effective_changed = prior_payload.get("worktree_effective_changed_paths")
        if isinstance(effective_changed, list):
            changed_paths: list[str] = []
            for item in effective_changed:
                normalized_path = deps.normalize_repo_path(str(item))
                if normalized_path:
                    changed_paths.append(normalized_path)
            worktree_prior["changed_paths"] = changed_paths
            worktree_prior["changed_count"] = len(worktree_prior["changed_paths"])

        effective_seed = prior_payload.get("worktree_effective_seed_paths")
        if isinstance(effective_seed, list):
            seed_paths: list[str] = []
            for item in effective_seed:
                normalized_path = deps.normalize_repo_path(str(item))
                if normalized_path:
                    seed_paths.append(normalized_path)
            worktree_prior["seed_paths"] = seed_paths

        effective_state_hash = str(
            prior_payload.get("worktree_effective_state_hash") or ""
        ).strip()
        if effective_state_hash:
            worktree_prior["state_hash"] = effective_state_hash

    deps.mark_timing("candidate_priors", timing_started)
    return InitialCandidateGenerationResult(
        requested_ranker=requested_ranker,
        selected_ranker=selected_ranker,
        ranker_fallbacks=ranker_fallbacks,
        min_score_used=min_score_used,
        candidates=list(candidates),
        exact_search_payload=exact_search_payload,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        parallel_payload=parallel_payload,
        prior_payload=prior_payload,
        docs_elapsed_ms=float(signal_result.docs_elapsed_ms),
        worktree_elapsed_ms=float(signal_result.worktree_elapsed_ms),
        raw_worktree=raw_worktree,
    )


__all__ = [
    "InitialCandidateGenerationDeps",
    "InitialCandidateGenerationResult",
    "gather_initial_candidates",
]
