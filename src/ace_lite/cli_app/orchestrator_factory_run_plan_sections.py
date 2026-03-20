"""Grouped run-plan section helpers for orchestrator factory wiring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def normalize_group_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class GroupedFlatSectionSpec:
    group_key: str
    group_payload: dict[str, Any]
    flat_payload: dict[str, Any]


def merge_group_or_flat_sections(
    *,
    target: dict[str, Any],
    sections: tuple[GroupedFlatSectionSpec, ...],
) -> None:
    for spec in sections:
        attach_group_or_flat_section(
            target=target,
            group_key=spec.group_key,
            group_payload=spec.group_payload,
            flat_payload=spec.flat_payload,
        )


def attach_group_or_flat_section(
    *,
    target: dict[str, Any],
    group_key: str,
    group_payload: dict[str, Any],
    flat_payload: dict[str, Any],
) -> None:
    if group_payload:
        target[group_key] = dict(group_payload)
    else:
        target.update(flat_payload)


def build_passthrough_run_plan_section_specs(
    *,
    skills_group: dict[str, Any],
    skills_dir: str | Any,
    precomputed_skills_routing_enabled: bool,
    index_group: dict[str, Any],
    index_languages: list[str] | None,
    index_cache_path: str | Any,
    index_incremental: bool,
    conventions_files: list[str] | None,
    embeddings_group: dict[str, Any],
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_index_path: str | Any,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
    tokenizer_group: dict[str, Any],
    tokenizer_model: str,
    cochange_group: dict[str, Any],
    cochange_enabled: bool,
    cochange_cache_path: str | Any,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    tests_group: dict[str, Any],
    junit_xml: str | None,
    coverage_json: str | None,
    sbfl_json: str | None,
    sbfl_metric: str,
    scip_group: dict[str, Any],
    scip_enabled: bool,
    scip_index_path: str | Any,
    scip_provider: str,
    scip_generate_fallback: bool,
    plugins_group: dict[str, Any],
    plugins_enabled: bool,
    remote_slot_policy_mode: str,
    remote_slot_allowlist: list[str] | tuple[str, ...] | None,
    repomap_group: dict[str, Any],
    repomap_enabled: bool,
    repomap_top_k: int,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
    lsp_group: dict[str, Any],
    lsp_enabled: bool,
    lsp_top_n: int,
    lsp_commands: dict[str, list[str]] | None,
    lsp_xref_enabled: bool,
    lsp_xref_top_n: int,
    lsp_time_budget_ms: int,
    lsp_xref_commands: dict[str, list[str]] | None,
    trace_group: dict[str, Any],
    trace_export_enabled: bool,
    trace_export_path: str | Any,
    trace_otlp_enabled: bool,
    trace_otlp_endpoint: str,
    trace_otlp_timeout_seconds: float,
    plan_replay_cache_group: dict[str, Any],
    plan_replay_cache_enabled: bool,
    plan_replay_cache_path: str | Any,
) -> tuple[GroupedFlatSectionSpec, ...]:
    return (
        GroupedFlatSectionSpec(
            group_key="skills_config",
            group_payload=skills_group,
            flat_payload={
                "skills_dir": skills_dir,
                "precomputed_skills_routing_enabled": precomputed_skills_routing_enabled,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="index_config",
            group_payload=index_group,
            flat_payload={
                "index_languages": index_languages,
                "index_cache_path": index_cache_path,
                "index_incremental": index_incremental,
                "conventions_files": conventions_files,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="embeddings_config",
            group_payload=embeddings_group,
            flat_payload={
                "embedding_enabled": embedding_enabled,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
                "embedding_index_path": embedding_index_path,
                "embedding_rerank_pool": embedding_rerank_pool,
                "embedding_lexical_weight": embedding_lexical_weight,
                "embedding_semantic_weight": embedding_semantic_weight,
                "embedding_min_similarity": embedding_min_similarity,
                "embedding_fail_open": embedding_fail_open,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="tokenizer_config",
            group_payload=tokenizer_group,
            flat_payload={"tokenizer_model": tokenizer_model},
        ),
        GroupedFlatSectionSpec(
            group_key="cochange_config",
            group_payload=cochange_group,
            flat_payload={
                "cochange_enabled": cochange_enabled,
                "cochange_cache_path": cochange_cache_path,
                "cochange_lookback_commits": cochange_lookback_commits,
                "cochange_half_life_days": cochange_half_life_days,
                "cochange_top_neighbors": cochange_top_neighbors,
                "cochange_boost_weight": cochange_boost_weight,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="tests_config",
            group_payload=tests_group,
            flat_payload={
                "junit_xml": junit_xml,
                "coverage_json": coverage_json,
                "sbfl_json": sbfl_json,
                "sbfl_metric": sbfl_metric,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="scip_config",
            group_payload=scip_group,
            flat_payload={
                "scip_enabled": scip_enabled,
                "scip_index_path": scip_index_path,
                "scip_provider": scip_provider,
                "scip_generate_fallback": scip_generate_fallback,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="plugins_config",
            group_payload=plugins_group,
            flat_payload={
                "plugins_enabled": plugins_enabled,
                "remote_slot_policy_mode": remote_slot_policy_mode,
                "remote_slot_allowlist": remote_slot_allowlist,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="repomap_config",
            group_payload=repomap_group,
            flat_payload={
                "repomap_enabled": repomap_enabled,
                "repomap_top_k": repomap_top_k,
                "repomap_neighbor_limit": repomap_neighbor_limit,
                "repomap_budget_tokens": repomap_budget_tokens,
                "repomap_ranking_profile": repomap_ranking_profile,
                "repomap_signal_weights": repomap_signal_weights,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="lsp_config",
            group_payload=lsp_group,
            flat_payload={
                "lsp_enabled": lsp_enabled,
                "lsp_top_n": lsp_top_n,
                "lsp_commands": lsp_commands,
                "lsp_xref_enabled": lsp_xref_enabled,
                "lsp_xref_top_n": lsp_xref_top_n,
                "lsp_time_budget_ms": lsp_time_budget_ms,
                "lsp_xref_commands": lsp_xref_commands,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="trace_config",
            group_payload=trace_group,
            flat_payload={
                "trace_export_enabled": trace_export_enabled,
                "trace_export_path": trace_export_path,
                "trace_otlp_enabled": trace_otlp_enabled,
                "trace_otlp_endpoint": trace_otlp_endpoint,
                "trace_otlp_timeout_seconds": trace_otlp_timeout_seconds,
            },
        ),
        GroupedFlatSectionSpec(
            group_key="plan_replay_cache_config",
            group_payload=plan_replay_cache_group,
            flat_payload={
                "plan_replay_cache_enabled": plan_replay_cache_enabled,
                "plan_replay_cache_path": plan_replay_cache_path,
            },
        ),
    )


def build_chunking_run_plan_section_spec(
    *,
    chunking_group: dict[str, Any],
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_disclosure: str,
    chunk_signature: bool,
    chunk_snippet_max_lines: int,
    chunk_snippet_max_chars: int,
    chunk_token_budget: int,
    chunk_guard_enabled: bool,
    chunk_guard_mode: str,
    chunk_guard_lambda_penalty: float,
    chunk_guard_min_pool: int,
    chunk_guard_max_pool: int,
    chunk_guard_min_marginal_utility: float,
    chunk_guard_compatibility_min_overlap: float,
    chunk_diversity_enabled: bool,
    chunk_diversity_path_penalty: float,
    chunk_diversity_symbol_family_penalty: float,
    chunk_diversity_kind_penalty: float,
    chunk_diversity_locality_penalty: float,
    chunk_diversity_locality_window: int,
) -> GroupedFlatSectionSpec:
    return GroupedFlatSectionSpec(
        group_key="chunking_config",
        group_payload=chunking_group,
        flat_payload={
            "chunk_top_k": chunk_top_k,
            "chunk_per_file_limit": chunk_per_file_limit,
            "chunk_disclosure": chunk_disclosure,
            "chunk_signature": chunk_signature,
            "chunk_snippet_max_lines": chunk_snippet_max_lines,
            "chunk_snippet_max_chars": chunk_snippet_max_chars,
            "chunk_token_budget": chunk_token_budget,
            "chunk_guard_enabled": chunk_guard_enabled,
            "chunk_guard_mode": chunk_guard_mode,
            "chunk_guard_lambda_penalty": chunk_guard_lambda_penalty,
            "chunk_guard_min_pool": chunk_guard_min_pool,
            "chunk_guard_max_pool": chunk_guard_max_pool,
            "chunk_guard_min_marginal_utility": chunk_guard_min_marginal_utility,
            "chunk_guard_compatibility_min_overlap": (
                chunk_guard_compatibility_min_overlap
            ),
            "chunk_diversity_enabled": chunk_diversity_enabled,
            "chunk_diversity_path_penalty": chunk_diversity_path_penalty,
            "chunk_diversity_symbol_family_penalty": (
                chunk_diversity_symbol_family_penalty
            ),
            "chunk_diversity_kind_penalty": chunk_diversity_kind_penalty,
            "chunk_diversity_locality_penalty": chunk_diversity_locality_penalty,
            "chunk_diversity_locality_window": chunk_diversity_locality_window,
        },
    )


def build_retrieval_run_plan_section_spec(
    *,
    retrieval_group: dict[str, Any],
    top_k_files: int,
    min_candidate_score: int,
    candidate_relative_threshold: float,
    candidate_ranker: str,
    exact_search_enabled: bool,
    deterministic_refine_enabled: bool,
    exact_search_time_budget_ms: int,
    exact_search_max_paths: int,
    hybrid_re2_fusion_mode: str,
    hybrid_re2_rrf_k: int,
    hybrid_re2_bm25_weight: float,
    hybrid_re2_heuristic_weight: float,
    hybrid_re2_coverage_weight: float,
    hybrid_re2_combined_scale: float,
    retrieval_policy: str,
    policy_version: str,
) -> GroupedFlatSectionSpec:
    return GroupedFlatSectionSpec(
        group_key="retrieval_config",
        group_payload=retrieval_group,
        flat_payload={
            "top_k_files": top_k_files,
            "min_candidate_score": min_candidate_score,
            "candidate_relative_threshold": candidate_relative_threshold,
            "candidate_ranker": candidate_ranker,
            "exact_search_enabled": exact_search_enabled,
            "deterministic_refine_enabled": deterministic_refine_enabled,
            "exact_search_time_budget_ms": exact_search_time_budget_ms,
            "exact_search_max_paths": exact_search_max_paths,
            "hybrid_re2_fusion_mode": hybrid_re2_fusion_mode,
            "hybrid_re2_rrf_k": hybrid_re2_rrf_k,
            "hybrid_re2_bm25_weight": hybrid_re2_bm25_weight,
            "hybrid_re2_heuristic_weight": hybrid_re2_heuristic_weight,
            "hybrid_re2_coverage_weight": hybrid_re2_coverage_weight,
            "hybrid_re2_combined_scale": hybrid_re2_combined_scale,
            "retrieval_policy": retrieval_policy,
            "policy_version": policy_version,
        },
    )


def build_adaptive_router_run_plan_section_spec(
    *,
    adaptive_router_group: dict[str, Any],
    adaptive_router_enabled: bool,
    adaptive_router_mode: str,
    adaptive_router_model_path: str | Any,
    adaptive_router_state_path: str | Any,
    adaptive_router_arm_set: str,
    adaptive_router_online_bandit_enabled: bool,
    adaptive_router_online_bandit_experiment_enabled: bool,
) -> GroupedFlatSectionSpec:
    return GroupedFlatSectionSpec(
        group_key="adaptive_router_config",
        group_payload=adaptive_router_group,
        flat_payload={
            "adaptive_router_enabled": adaptive_router_enabled,
            "adaptive_router_mode": adaptive_router_mode,
            "adaptive_router_model_path": adaptive_router_model_path,
            "adaptive_router_state_path": adaptive_router_state_path,
            "adaptive_router_arm_set": adaptive_router_arm_set,
            "adaptive_router_online_bandit_enabled": (
                adaptive_router_online_bandit_enabled
            ),
            "adaptive_router_online_bandit_experiment_enabled": (
                adaptive_router_online_bandit_experiment_enabled
            ),
        },
    )


def build_memory_run_plan_section_spec(
    *,
    memory_group: dict[str, Any],
    memory_disclosure_mode: str,
    memory_preview_max_chars: int,
    memory_strategy: str,
    memory_gate_enabled: bool,
    memory_gate_mode: str,
    memory_timeline_enabled: bool,
    memory_container_tag: str | None,
    memory_auto_tag_mode: str | None,
    memory_profile_enabled: bool,
    memory_profile_path: str | Any,
    memory_profile_top_n: int,
    memory_profile_token_budget: int,
    memory_profile_expiry_enabled: bool,
    memory_profile_ttl_days: int,
    memory_profile_max_age_days: int,
    memory_feedback_enabled: bool,
    memory_feedback_path: str | Any,
    memory_feedback_max_entries: int,
    memory_feedback_boost_per_select: float,
    memory_feedback_max_boost: float,
    memory_feedback_decay_days: float,
    memory_long_term_enabled: bool,
    memory_long_term_path: str | Any,
    memory_long_term_top_n: int,
    memory_long_term_token_budget: int,
    memory_long_term_write_enabled: bool,
    memory_long_term_as_of_enabled: bool,
    memory_capture_enabled: bool,
    memory_capture_notes_path: str | Any,
    memory_capture_min_query_length: int,
    memory_capture_keywords: list[str] | tuple[str, ...] | None,
    memory_notes_enabled: bool,
    memory_notes_path: str | Any,
    memory_notes_limit: int,
    memory_notes_mode: str,
    memory_notes_expiry_enabled: bool,
    memory_notes_ttl_days: int,
    memory_notes_max_age_days: int,
    memory_postprocess_enabled: bool,
    memory_postprocess_noise_filter_enabled: bool,
    memory_postprocess_length_norm_anchor_chars: int,
    memory_postprocess_time_decay_half_life_days: float,
    memory_postprocess_hard_min_score: float,
    memory_postprocess_diversity_enabled: bool,
    memory_postprocess_diversity_similarity_threshold: float,
) -> GroupedFlatSectionSpec:
    return GroupedFlatSectionSpec(
        group_key="memory_config",
        group_payload=memory_group,
        flat_payload={
            "memory_disclosure_mode": memory_disclosure_mode,
            "memory_preview_max_chars": memory_preview_max_chars,
            "memory_strategy": memory_strategy,
            "memory_gate_enabled": memory_gate_enabled,
            "memory_gate_mode": memory_gate_mode,
            "memory_timeline_enabled": memory_timeline_enabled,
            "memory_container_tag": memory_container_tag,
            "memory_auto_tag_mode": memory_auto_tag_mode,
            "memory_profile_enabled": memory_profile_enabled,
            "memory_profile_path": memory_profile_path,
            "memory_profile_top_n": memory_profile_top_n,
            "memory_profile_token_budget": memory_profile_token_budget,
            "memory_profile_expiry_enabled": memory_profile_expiry_enabled,
            "memory_profile_ttl_days": memory_profile_ttl_days,
            "memory_profile_max_age_days": memory_profile_max_age_days,
            "memory_feedback_enabled": memory_feedback_enabled,
            "memory_feedback_path": memory_feedback_path,
            "memory_feedback_max_entries": memory_feedback_max_entries,
            "memory_feedback_boost_per_select": memory_feedback_boost_per_select,
            "memory_feedback_max_boost": memory_feedback_max_boost,
            "memory_feedback_decay_days": memory_feedback_decay_days,
            "memory_long_term_enabled": memory_long_term_enabled,
            "memory_long_term_path": memory_long_term_path,
            "memory_long_term_top_n": memory_long_term_top_n,
            "memory_long_term_token_budget": memory_long_term_token_budget,
            "memory_long_term_write_enabled": memory_long_term_write_enabled,
            "memory_long_term_as_of_enabled": memory_long_term_as_of_enabled,
            "memory_capture_enabled": memory_capture_enabled,
            "memory_capture_notes_path": memory_capture_notes_path,
            "memory_capture_min_query_length": memory_capture_min_query_length,
            "memory_capture_keywords": memory_capture_keywords,
            "memory_notes_enabled": memory_notes_enabled,
            "memory_notes_path": memory_notes_path,
            "memory_notes_limit": memory_notes_limit,
            "memory_notes_mode": memory_notes_mode,
            "memory_notes_expiry_enabled": memory_notes_expiry_enabled,
            "memory_notes_ttl_days": memory_notes_ttl_days,
            "memory_notes_max_age_days": memory_notes_max_age_days,
            "memory_postprocess_enabled": memory_postprocess_enabled,
            "memory_postprocess_noise_filter_enabled": (
                memory_postprocess_noise_filter_enabled
            ),
            "memory_postprocess_length_norm_anchor_chars": (
                memory_postprocess_length_norm_anchor_chars
            ),
            "memory_postprocess_time_decay_half_life_days": (
                memory_postprocess_time_decay_half_life_days
            ),
            "memory_postprocess_hard_min_score": memory_postprocess_hard_min_score,
            "memory_postprocess_diversity_enabled": (
                memory_postprocess_diversity_enabled
            ),
            "memory_postprocess_diversity_similarity_threshold": (
                memory_postprocess_diversity_similarity_threshold
            ),
        },
    )


__all__ = [
    "GroupedFlatSectionSpec",
    "attach_group_or_flat_section",
    "build_adaptive_router_run_plan_section_spec",
    "build_chunking_run_plan_section_spec",
    "build_memory_run_plan_section_spec",
    "build_passthrough_run_plan_section_specs",
    "build_retrieval_run_plan_section_spec",
    "merge_group_or_flat_sections",
    "normalize_group_mapping",
]
