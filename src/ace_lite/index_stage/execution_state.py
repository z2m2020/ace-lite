from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IndexStageExecutionState:
    terms: list[str]
    memory_paths: list[str]
    policy: dict[str, Any]
    adaptive_router_payload: dict[str, Any]
    index_data: dict[str, Any]
    cache_info: dict[str, Any]
    effective_files_map: dict[str, Any]
    corpus_size: int
    effective_corpus_size: int
    index_hash: str
    benchmark_filter_payload: dict[str, Any]
    docs_policy_enabled: bool
    worktree_prior_enabled: bool
    worktree_policy_reason: str
    embedding_runtime: Any
    index_candidate_cache_path: Any
    index_candidate_cache_key: str
    index_candidate_cache_ttl_seconds: int
    index_candidate_cache_required_meta: dict[str, Any]
    index_candidate_cache: dict[str, Any]
    requested_ranker: str = ""
    selected_ranker: str = ""
    ranker_fallbacks: list[str] = field(default_factory=list)
    min_score_used: int = 0
    candidates: list[dict[str, Any]] = field(default_factory=list)
    exact_search_payload: dict[str, Any] = field(default_factory=dict)
    docs_payload: dict[str, Any] = field(default_factory=dict)
    worktree_prior: dict[str, Any] = field(default_factory=dict)
    parallel_payload: dict[str, Any] = field(default_factory=dict)
    prior_payload: dict[str, Any] = field(default_factory=dict)
    second_pass_payload: dict[str, Any] = field(default_factory=dict)
    refine_pass_payload: dict[str, Any] = field(default_factory=dict)
    cochange_payload: dict[str, Any] = field(default_factory=dict)
    scip_payload: dict[str, Any] = field(default_factory=dict)
    graph_lookup_payload: dict[str, Any] = field(default_factory=dict)
    embeddings_payload: dict[str, Any] = field(default_factory=dict)
    feedback_payload: dict[str, Any] = field(default_factory=dict)
    multi_channel_fusion_payload: dict[str, Any] = field(default_factory=dict)
    semantic_embedding_provider_impl: Any = None
    semantic_cross_encoder_provider: Any = None
    candidate_chunks: list[dict[str, Any]] = field(default_factory=list)
    chunk_metrics: dict[str, Any] = field(default_factory=dict)
    chunk_semantic_rerank_payload: dict[str, Any] = field(default_factory=dict)
    topological_shield_payload: dict[str, Any] = field(default_factory=dict)
    chunk_guard_payload: dict[str, Any] = field(default_factory=dict)


def build_index_stage_execution_state(*, bootstrap: Any) -> IndexStageExecutionState:
    return IndexStageExecutionState(
        terms=list(bootstrap.terms),
        memory_paths=list(bootstrap.memory_paths),
        policy=dict(bootstrap.policy),
        adaptive_router_payload=dict(bootstrap.adaptive_router_payload),
        index_data=dict(bootstrap.index_data),
        cache_info=dict(bootstrap.cache_info),
        effective_files_map=dict(bootstrap.effective_files_map),
        corpus_size=int(bootstrap.corpus_size),
        effective_corpus_size=int(bootstrap.effective_corpus_size),
        index_hash=str(bootstrap.index_hash),
        benchmark_filter_payload=dict(bootstrap.benchmark_filter_payload),
        docs_policy_enabled=bool(bootstrap.docs_policy_enabled),
        worktree_prior_enabled=bool(bootstrap.worktree_prior_enabled),
        worktree_policy_reason=str(bootstrap.worktree_policy_reason),
        embedding_runtime=bootstrap.embedding_runtime,
        index_candidate_cache_path=bootstrap.index_candidate_cache_path,
        index_candidate_cache_key=str(bootstrap.index_candidate_cache_key),
        index_candidate_cache_ttl_seconds=int(
            bootstrap.index_candidate_cache_ttl_seconds
        ),
        index_candidate_cache_required_meta=dict(
            bootstrap.index_candidate_cache_required_meta
        ),
        index_candidate_cache=dict(bootstrap.index_candidate_cache),
    )


def apply_candidate_generation_runtime_to_state(
    *,
    state: IndexStageExecutionState,
    candidate_generation_runtime: Any,
    timings_ms: dict[str, float],
    cochange_enabled: bool,
    ctx_state: dict[str, Any],
) -> None:
    initial_candidates = candidate_generation_runtime.initial_candidates
    state.requested_ranker = str(initial_candidates.requested_ranker)
    state.selected_ranker = str(initial_candidates.selected_ranker)
    state.ranker_fallbacks = list(initial_candidates.ranker_fallbacks)
    state.min_score_used = int(initial_candidates.min_score_used)
    state.candidates = list(initial_candidates.candidates)
    state.exact_search_payload = dict(initial_candidates.exact_search_payload)
    state.docs_payload = dict(initial_candidates.docs_payload)
    state.worktree_prior = dict(initial_candidates.worktree_prior)
    state.parallel_payload = dict(initial_candidates.parallel_payload)
    state.prior_payload = dict(initial_candidates.prior_payload)
    timings_ms["docs_signals"] = round(
        float(candidate_generation_runtime.docs_timing_ms),
        3,
    )
    timings_ms["worktree_prior"] = round(
        float(candidate_generation_runtime.worktree_timing_ms),
        3,
    )
    if cochange_enabled and isinstance(candidate_generation_runtime.raw_worktree, dict):
        ctx_state["__vcs_worktree"] = candidate_generation_runtime.raw_worktree


def apply_post_generation_runtime_to_state(
    *,
    state: IndexStageExecutionState,
    post_generation_runtime: Any,
) -> None:
    state.candidates = list(post_generation_runtime.candidates)
    state.second_pass_payload = dict(post_generation_runtime.second_pass_payload)
    state.refine_pass_payload = dict(post_generation_runtime.refine_pass_payload)
    state.cochange_payload = dict(post_generation_runtime.cochange_payload)
    state.scip_payload = dict(post_generation_runtime.scip_payload)
    state.graph_lookup_payload = dict(post_generation_runtime.graph_lookup_payload)
    state.embeddings_payload = dict(post_generation_runtime.embeddings_payload)
    state.feedback_payload = dict(post_generation_runtime.feedback_payload)
    state.multi_channel_fusion_payload = dict(
        post_generation_runtime.multi_channel_fusion_payload
    )
    state.semantic_embedding_provider_impl = (
        post_generation_runtime.semantic_embedding_provider_impl
    )
    state.semantic_cross_encoder_provider = (
        post_generation_runtime.semantic_cross_encoder_provider
    )
    state.benchmark_filter_payload = dict(post_generation_runtime.benchmark_filter_payload)
    state.candidate_chunks = list(post_generation_runtime.candidate_chunks)
    state.chunk_metrics = dict(post_generation_runtime.chunk_metrics)
    state.chunk_semantic_rerank_payload = dict(
        post_generation_runtime.chunk_semantic_rerank_payload
    )
    state.topological_shield_payload = dict(
        post_generation_runtime.topological_shield_payload
    )
    state.chunk_guard_payload = dict(post_generation_runtime.chunk_guard_payload)


__all__ = [
    "IndexStageExecutionState",
    "apply_candidate_generation_runtime_to_state",
    "apply_post_generation_runtime_to_state",
    "build_index_stage_execution_state",
]
