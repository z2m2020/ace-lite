"""Index-stage helper modules.

This package contains pure helpers used by the `index` pipeline stage:
- term extraction
- memory-path extraction
- retrieval policy resolution
- optional boost signals (exact-search, co-change, SCIP)

Exports are resolved lazily so packages that only need a narrow helper
(`ace_lite.index_stage.terms`, for example) do not pay the import cost or
trigger unrelated dependency cycles during package initialization.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "apply_candidate_priors": ("ace_lite.index_stage.priors", "apply_candidate_priors"),
    "apply_cochange_neighbors": ("ace_lite.index_stage.cochange", "apply_cochange_neighbors"),
    "apply_exact_search_boost": (
        "ace_lite.index_stage.exact_search_boost",
        "apply_exact_search_boost",
    ),
    "apply_chunk_selection": (
        "ace_lite.index_stage.chunk_selection",
        "apply_chunk_selection",
    ),
    "apply_graph_lookup_rerank": (
        "ace_lite.index_stage.graph_lookup",
        "apply_graph_lookup_rerank",
    ),
    "apply_scip_boost": ("ace_lite.index_stage.scip_boost", "apply_scip_boost"),
    "build_exact_search_payload": (
        "ace_lite.index_stage.exact_search_boost",
        "build_exact_search_payload",
    ),
    "collect_docs_signals": ("ace_lite.index_stage.docs_channel", "collect_docs_signals"),
    "collect_parallel_signals": (
        "ace_lite.index_stage.parallel_signals",
        "collect_parallel_signals",
    ),
    "collect_worktree_prior": ("ace_lite.index_stage.priors", "collect_worktree_prior"),
    "extract_memory_paths": ("ace_lite.index_stage.memory_paths", "extract_memory_paths"),
    "extract_terms": ("ace_lite.index_stage.terms", "extract_terms"),
    "postprocess_candidates": (
        "ace_lite.index_stage.candidate_postprocess",
        "postprocess_candidates",
    ),
    "apply_semantic_candidate_rerank": (
        "ace_lite.index_stage.semantic_candidate_rerank",
        "apply_semantic_candidate_rerank",
    ),
    "resolve_online_bandit_gate": (
        "ace_lite.index_stage.policy",
        "resolve_online_bandit_gate",
    ),
    "resolve_retrieval_policy": ("ace_lite.index_stage.policy", "resolve_retrieval_policy"),
    "resolve_shadow_router_arm": ("ace_lite.index_stage.policy", "resolve_shadow_router_arm"),
    "select_initial_candidates": (
        "ace_lite.index_stage.candidate_selection",
        "select_initial_candidates",
    ),
    "apply_structural_rerank": (
        "ace_lite.index_stage.structural_rerank",
        "apply_structural_rerank",
    ),
    "build_index_stage_result": (
        "ace_lite.index_stage.result_payload",
        "build_index_stage_result",
    ),
    "build_index_stage_output": (
        "ace_lite.index_stage.result_payload",
        "build_index_stage_output",
    ),
    "CandidateFusionDeps": (
        "ace_lite.index_stage.candidate_fusion",
        "CandidateFusionDeps",
    ),
    "ChunkSelectionDeps": (
        "ace_lite.index_stage.chunk_pipeline",
        "ChunkSelectionDeps",
    ),
    "ChunkSelectionRuntimeConfig": (
        "ace_lite.index_stage.chunk_pipeline",
        "ChunkSelectionRuntimeConfig",
    ),
    "gather_initial_candidates": (
        "ace_lite.index_stage.candidate_generation",
        "gather_initial_candidates",
    ),
    "InitialCandidateGenerationDeps": (
        "ace_lite.index_stage.candidate_generation",
        "InitialCandidateGenerationDeps",
    ),
    "refine_candidate_pool": (
        "ace_lite.index_stage.candidate_fusion",
        "refine_candidate_pool",
    ),
    "select_index_chunks": (
        "ace_lite.index_stage.chunk_pipeline",
        "select_index_chunks",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))
