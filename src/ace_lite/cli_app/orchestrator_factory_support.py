"""Shared canonical payload helpers for orchestrator factory wiring."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


def normalize_group_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def resolve_grouped_value(
    *,
    current: Any,
    default: Any,
    specs: tuple[tuple[dict[str, Any], tuple[tuple[str, ...], ...]], ...],
) -> Any:
    if current != default:
        return current
    for payload, paths in specs:
        if not payload:
            continue
        for path in paths:
            candidate: Any = payload
            missing = False
            for key in path:
                if not isinstance(candidate, Mapping) or key not in candidate:
                    missing = True
                    break
                candidate = candidate[key]
            if not missing:
                return candidate
    return current


@dataclass(frozen=True)
class CanonicalFieldSpec:
    output_path: tuple[str, ...]
    current: Any
    default: Any
    group_specs: tuple[tuple[dict[str, Any], tuple[tuple[str, ...], ...]], ...]


@dataclass(frozen=True)
class GroupedFlatSectionSpec:
    group_key: str
    group_payload: dict[str, Any]
    flat_payload: dict[str, Any]


@dataclass(frozen=True)
class PayloadFamilyDescriptor:
    family: str
    builder: Callable[..., dict[str, Any]]
    grouped_inputs: tuple[str, ...]


def set_nested_mapping_value(
    target: dict[str, Any],
    path: tuple[str, ...],
    value: Any,
) -> None:
    node = target
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = value


def build_canonical_payload(
    *,
    field_specs: tuple[CanonicalFieldSpec, ...],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for spec in field_specs:
        value = resolve_grouped_value(
            current=spec.current,
            default=spec.default,
            specs=spec.group_specs,
        )
        set_nested_mapping_value(payload, spec.output_path, value)
    return payload


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


def build_memory_payload(
    *,
    memory_group: dict[str, Any],
    memory_disclosure_mode: str = "compact",
    memory_preview_max_chars: int = 280,
    memory_strategy: str = "hybrid",
    memory_gate_enabled: bool = False,
    memory_gate_mode: str = "auto",
    memory_timeline_enabled: bool = True,
    memory_container_tag: str | None = None,
    memory_auto_tag_mode: str | None = None,
    memory_profile_enabled: bool = False,
    memory_profile_path: str = "~/.ace-lite/profile.json",
    memory_profile_top_n: int = 4,
    memory_profile_token_budget: int = 160,
    memory_profile_expiry_enabled: bool = True,
    memory_profile_ttl_days: int = 90,
    memory_profile_max_age_days: int = 365,
    memory_feedback_enabled: bool = False,
    memory_feedback_path: str = "~/.ace-lite/profile.json",
    memory_feedback_max_entries: int = 512,
    memory_feedback_boost_per_select: float = 0.15,
    memory_feedback_max_boost: float = 0.6,
    memory_feedback_decay_days: float = 60.0,
    memory_capture_enabled: bool = False,
    memory_capture_notes_path: str = "context-map/memory_notes.jsonl",
    memory_capture_min_query_length: int = 24,
    memory_capture_keywords: list[str] | tuple[str, ...] | None = None,
    memory_notes_enabled: bool = False,
    memory_notes_path: str = "context-map/memory_notes.jsonl",
    memory_notes_limit: int = 8,
    memory_notes_mode: str = "supplement",
    memory_notes_expiry_enabled: bool = True,
    memory_notes_ttl_days: int = 90,
    memory_notes_max_age_days: int = 365,
    memory_postprocess_enabled: bool = False,
    memory_postprocess_noise_filter_enabled: bool = True,
    memory_postprocess_length_norm_anchor_chars: int = 500,
    memory_postprocess_time_decay_half_life_days: float = 0.0,
    memory_postprocess_hard_min_score: float = 0.0,
    memory_postprocess_diversity_enabled: bool = True,
    memory_postprocess_diversity_similarity_threshold: float = 0.9,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(
                ("disclosure_mode",),
                memory_disclosure_mode,
                "compact",
                ((memory_group, (("disclosure_mode",),)),),
            ),
            CanonicalFieldSpec(
                ("preview_max_chars",),
                memory_preview_max_chars,
                280,
                ((memory_group, (("preview_max_chars",),)),),
            ),
            CanonicalFieldSpec(
                ("strategy",),
                memory_strategy,
                "hybrid",
                ((memory_group, (("strategy",),)),),
            ),
            CanonicalFieldSpec(
                ("gate", "enabled"),
                memory_gate_enabled,
                False,
                ((memory_group, (("gate", "enabled"), ("gate_enabled",))),),
            ),
            CanonicalFieldSpec(
                ("gate", "mode"),
                memory_gate_mode,
                "auto",
                ((memory_group, (("gate", "mode"), ("gate_mode",))),),
            ),
            CanonicalFieldSpec(
                ("timeline_enabled",),
                memory_timeline_enabled,
                True,
                ((memory_group, (("timeline", "enabled"), ("timeline_enabled",))),),
            ),
            CanonicalFieldSpec(
                ("namespace", "container_tag"),
                memory_container_tag,
                None,
                ((memory_group, (("namespace", "container_tag"),)),),
            ),
            CanonicalFieldSpec(
                ("namespace", "auto_tag_mode"),
                memory_auto_tag_mode,
                None,
                ((memory_group, (("namespace", "auto_tag_mode"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "enabled"),
                memory_profile_enabled,
                False,
                ((memory_group, (("profile", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "path"),
                memory_profile_path,
                "~/.ace-lite/profile.json",
                ((memory_group, (("profile", "path"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "top_n"),
                memory_profile_top_n,
                4,
                ((memory_group, (("profile", "top_n"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "token_budget"),
                memory_profile_token_budget,
                160,
                ((memory_group, (("profile", "token_budget"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "expiry_enabled"),
                memory_profile_expiry_enabled,
                True,
                ((memory_group, (("profile", "expiry_enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "ttl_days"),
                memory_profile_ttl_days,
                90,
                ((memory_group, (("profile", "ttl_days"),)),),
            ),
            CanonicalFieldSpec(
                ("profile", "max_age_days"),
                memory_profile_max_age_days,
                365,
                ((memory_group, (("profile", "max_age_days"),)),),
            ),
            CanonicalFieldSpec(
                ("feedback", "enabled"),
                memory_feedback_enabled,
                False,
                ((memory_group, (("feedback", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("feedback", "path"),
                memory_feedback_path,
                "~/.ace-lite/profile.json",
                ((memory_group, (("feedback", "path"),)),),
            ),
            CanonicalFieldSpec(
                ("feedback", "max_entries"),
                memory_feedback_max_entries,
                512,
                ((memory_group, (("feedback", "max_entries"),)),),
            ),
            CanonicalFieldSpec(
                ("feedback", "boost_per_select"),
                memory_feedback_boost_per_select,
                0.15,
                ((memory_group, (("feedback", "boost_per_select"),)),),
            ),
            CanonicalFieldSpec(
                ("feedback", "max_boost"),
                memory_feedback_max_boost,
                0.6,
                ((memory_group, (("feedback", "max_boost"),)),),
            ),
            CanonicalFieldSpec(
                ("feedback", "decay_days"),
                memory_feedback_decay_days,
                60.0,
                ((memory_group, (("feedback", "decay_days"),)),),
            ),
            CanonicalFieldSpec(
                ("capture", "enabled"),
                memory_capture_enabled,
                False,
                ((memory_group, (("capture", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("capture", "notes_path"),
                memory_capture_notes_path,
                "context-map/memory_notes.jsonl",
                ((memory_group, (("capture", "notes_path"),)),),
            ),
            CanonicalFieldSpec(
                ("capture", "min_query_length"),
                memory_capture_min_query_length,
                24,
                ((memory_group, (("capture", "min_query_length"),)),),
            ),
            CanonicalFieldSpec(
                ("capture", "keywords"),
                memory_capture_keywords,
                None,
                ((memory_group, (("capture", "keywords"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "enabled"),
                memory_notes_enabled,
                False,
                ((memory_group, (("notes", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "path"),
                memory_notes_path,
                "context-map/memory_notes.jsonl",
                ((memory_group, (("notes", "path"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "limit"),
                memory_notes_limit,
                8,
                ((memory_group, (("notes", "limit"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "mode"),
                memory_notes_mode,
                "supplement",
                ((memory_group, (("notes", "mode"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "expiry_enabled"),
                memory_notes_expiry_enabled,
                True,
                ((memory_group, (("notes", "expiry_enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "ttl_days"),
                memory_notes_ttl_days,
                90,
                ((memory_group, (("notes", "ttl_days"),)),),
            ),
            CanonicalFieldSpec(
                ("notes", "max_age_days"),
                memory_notes_max_age_days,
                365,
                ((memory_group, (("notes", "max_age_days"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "enabled"),
                memory_postprocess_enabled,
                False,
                ((memory_group, (("postprocess", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "noise_filter_enabled"),
                memory_postprocess_noise_filter_enabled,
                True,
                ((memory_group, (("postprocess", "noise_filter_enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "length_norm_anchor_chars"),
                memory_postprocess_length_norm_anchor_chars,
                500,
                ((memory_group, (("postprocess", "length_norm_anchor_chars"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "time_decay_half_life_days"),
                memory_postprocess_time_decay_half_life_days,
                0.0,
                ((memory_group, (("postprocess", "time_decay_half_life_days"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "hard_min_score"),
                memory_postprocess_hard_min_score,
                0.0,
                ((memory_group, (("postprocess", "hard_min_score"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "diversity_enabled"),
                memory_postprocess_diversity_enabled,
                True,
                ((memory_group, (("postprocess", "diversity_enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("postprocess", "diversity_similarity_threshold"),
                memory_postprocess_diversity_similarity_threshold,
                0.9,
                (
                    (
                        memory_group,
                        (("postprocess", "diversity_similarity_threshold"),),
                    ),
                ),
            ),
        ),
    )


def build_retrieval_payload(
    *,
    retrieval_group: dict[str, Any],
    adaptive_router_group: dict[str, Any],
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
    adaptive_router_enabled: bool,
    adaptive_router_mode: str,
    adaptive_router_model_path: str,
    adaptive_router_state_path: str,
    adaptive_router_arm_set: str,
    adaptive_router_online_bandit_enabled: bool,
    adaptive_router_online_bandit_experiment_enabled: bool,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("top_k_files",), top_k_files, 8, ((retrieval_group, (("top_k_files",),)),)),
            CanonicalFieldSpec(("min_candidate_score",), min_candidate_score, 2, ((retrieval_group, (("min_candidate_score",),)),)),
            CanonicalFieldSpec(
                ("candidate_relative_threshold",),
                candidate_relative_threshold,
                0.0,
                ((retrieval_group, (("candidate_relative_threshold",),)),),
            ),
            CanonicalFieldSpec(("candidate_ranker",), candidate_ranker, "heuristic", ((retrieval_group, (("candidate_ranker",),)),)),
            CanonicalFieldSpec(("exact_search_enabled",), exact_search_enabled, False, ((retrieval_group, (("exact_search_enabled",),)),)),
            CanonicalFieldSpec(
                ("deterministic_refine_enabled",),
                deterministic_refine_enabled,
                True,
                ((retrieval_group, (("deterministic_refine_enabled",),)),),
            ),
            CanonicalFieldSpec(
                ("exact_search_time_budget_ms",),
                exact_search_time_budget_ms,
                40,
                ((retrieval_group, (("exact_search_time_budget_ms",),)),),
            ),
            CanonicalFieldSpec(("exact_search_max_paths",), exact_search_max_paths, 24, ((retrieval_group, (("exact_search_max_paths",),)),)),
            CanonicalFieldSpec(("hybrid_re2_fusion_mode",), hybrid_re2_fusion_mode, "linear", ((retrieval_group, (("hybrid_re2_fusion_mode",),)),)),
            CanonicalFieldSpec(("hybrid_re2_rrf_k",), hybrid_re2_rrf_k, 60, ((retrieval_group, (("hybrid_re2_rrf_k",),)),)),
            CanonicalFieldSpec(("hybrid_re2_bm25_weight",), hybrid_re2_bm25_weight, 0.0, ((retrieval_group, (("hybrid_re2_bm25_weight",),)),)),
            CanonicalFieldSpec(("hybrid_re2_heuristic_weight",), hybrid_re2_heuristic_weight, 0.0, ((retrieval_group, (("hybrid_re2_heuristic_weight",),)),)),
            CanonicalFieldSpec(("hybrid_re2_coverage_weight",), hybrid_re2_coverage_weight, 0.0, ((retrieval_group, (("hybrid_re2_coverage_weight",),)),)),
            CanonicalFieldSpec(("hybrid_re2_combined_scale",), hybrid_re2_combined_scale, 0.0, ((retrieval_group, (("hybrid_re2_combined_scale",),)),)),
            CanonicalFieldSpec(("retrieval_policy",), retrieval_policy, "auto", ((retrieval_group, (("retrieval_policy",),)),)),
            CanonicalFieldSpec(("policy_version",), policy_version, "v1", ((retrieval_group, (("policy_version",),)),)),
            CanonicalFieldSpec(
                ("adaptive_router_enabled",),
                adaptive_router_enabled,
                False,
                (
                    (adaptive_router_group, (("enabled",),)),
                    (retrieval_group, (("adaptive_router_enabled",), ("adaptive_router", "enabled"))),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_mode",),
                adaptive_router_mode,
                "observe",
                (
                    (adaptive_router_group, (("mode",),)),
                    (retrieval_group, (("adaptive_router_mode",), ("adaptive_router", "mode"))),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_model_path",),
                adaptive_router_model_path,
                "context-map/router/model.json",
                (
                    (adaptive_router_group, (("model_path",),)),
                    (retrieval_group, (("adaptive_router_model_path",), ("adaptive_router", "model_path"))),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_state_path",),
                adaptive_router_state_path,
                "context-map/router/state.json",
                (
                    (adaptive_router_group, (("state_path",),)),
                    (retrieval_group, (("adaptive_router_state_path",), ("adaptive_router", "state_path"))),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_arm_set",),
                adaptive_router_arm_set,
                "retrieval_policy_v1",
                (
                    (adaptive_router_group, (("arm_set",),)),
                    (retrieval_group, (("adaptive_router_arm_set",), ("adaptive_router", "arm_set"))),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_online_bandit_enabled",),
                adaptive_router_online_bandit_enabled,
                False,
                (
                    (adaptive_router_group, (("online_bandit", "enabled"),)),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_online_bandit_enabled",),
                            ("adaptive_router", "online_bandit", "enabled"),
                        ),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_online_bandit_experiment_enabled",),
                adaptive_router_online_bandit_experiment_enabled,
                False,
                (
                    (
                        adaptive_router_group,
                        (("online_bandit", "experiment_enabled"),),
                    ),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_online_bandit_experiment_enabled",),
                            ("adaptive_router", "online_bandit", "experiment_enabled"),
                        ),
                    ),
                ),
            ),
        ),
    )


def build_chunking_payload(
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
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("top_k",), chunk_top_k, 24, ((chunking_group, (("top_k",),)),)),
            CanonicalFieldSpec(("per_file_limit",), chunk_per_file_limit, 3, ((chunking_group, (("per_file_limit",),)),)),
            CanonicalFieldSpec(("disclosure",), chunk_disclosure, "refs", ((chunking_group, (("disclosure",),)),)),
            CanonicalFieldSpec(("signature",), chunk_signature, False, ((chunking_group, (("signature",),)),)),
            CanonicalFieldSpec(("snippet_max_lines",), chunk_snippet_max_lines, 18, ((chunking_group, (("snippet", "max_lines"), ("snippet_max_lines",))),)),
            CanonicalFieldSpec(("snippet_max_chars",), chunk_snippet_max_chars, 1200, ((chunking_group, (("snippet", "max_chars"), ("snippet_max_chars",))),)),
            CanonicalFieldSpec(("token_budget",), chunk_token_budget, 1200, ((chunking_group, (("token_budget",),)),)),
            CanonicalFieldSpec(
                ("topological_shield", "enabled"),
                False,
                False,
                ((chunking_group, (("topological_shield", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "mode"),
                "off",
                "off",
                ((chunking_group, (("topological_shield", "mode"),)),),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "max_attenuation"),
                0.6,
                0.6,
                ((chunking_group, (("topological_shield", "max_attenuation"),)),),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "shared_parent_attenuation"),
                0.2,
                0.2,
                (
                    (
                        chunking_group,
                        (("topological_shield", "shared_parent_attenuation"),),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "adjacency_attenuation"),
                0.5,
                0.5,
                (
                    (
                        chunking_group,
                        (("topological_shield", "adjacency_attenuation"),),
                    ),
                ),
            ),
            CanonicalFieldSpec(("guard", "enabled"), chunk_guard_enabled, False, ((chunking_group, (("guard", "enabled"), ("guard_enabled",))),)),
            CanonicalFieldSpec(("guard", "mode"), chunk_guard_mode, "off", ((chunking_group, (("guard", "mode"), ("guard_mode",))),)),
            CanonicalFieldSpec(("guard", "lambda_penalty"), chunk_guard_lambda_penalty, 0.8, ((chunking_group, (("guard", "lambda_penalty"), ("guard_lambda_penalty",))),)),
            CanonicalFieldSpec(("guard", "min_pool"), chunk_guard_min_pool, 4, ((chunking_group, (("guard", "min_pool"), ("guard_min_pool",))),)),
            CanonicalFieldSpec(("guard", "max_pool"), chunk_guard_max_pool, 32, ((chunking_group, (("guard", "max_pool"), ("guard_max_pool",))),)),
            CanonicalFieldSpec(("guard", "min_marginal_utility"), chunk_guard_min_marginal_utility, 0.0, ((chunking_group, (("guard", "min_marginal_utility"), ("guard_min_marginal_utility",))),)),
            CanonicalFieldSpec(("guard", "compatibility_min_overlap"), chunk_guard_compatibility_min_overlap, 0.3, ((chunking_group, (("guard", "compatibility_min_overlap"), ("guard_compatibility_min_overlap",))),)),
            CanonicalFieldSpec(("diversity_enabled",), chunk_diversity_enabled, True, ((chunking_group, (("diversity_enabled",),)),)),
            CanonicalFieldSpec(("diversity_path_penalty",), chunk_diversity_path_penalty, 0.20, ((chunking_group, (("diversity_path_penalty",),)),)),
            CanonicalFieldSpec(("diversity_symbol_family_penalty",), chunk_diversity_symbol_family_penalty, 0.30, ((chunking_group, (("diversity_symbol_family_penalty",),)),)),
            CanonicalFieldSpec(("diversity_kind_penalty",), chunk_diversity_kind_penalty, 0.10, ((chunking_group, (("diversity_kind_penalty",),)),)),
            CanonicalFieldSpec(("diversity_locality_penalty",), chunk_diversity_locality_penalty, 0.15, ((chunking_group, (("diversity_locality_penalty",),)),)),
            CanonicalFieldSpec(("diversity_locality_window",), chunk_diversity_locality_window, 24, ((chunking_group, (("diversity_locality_window",),)),)),
        ),
    )


def build_skills_payload(
    *,
    skills_group: dict[str, Any],
    skills_dir: str,
    precomputed_routing_enabled: bool,
    top_n: int = 3,
    token_budget: int = 1200,
) -> dict[str, Any]:
    payload = build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("dir",), skills_dir, "skills", ((skills_group, (("dir",),)),)),
            CanonicalFieldSpec(
                ("precomputed_routing_enabled",),
                precomputed_routing_enabled,
                True,
                ((skills_group, (("precomputed_routing_enabled",),)),),
            ),
            CanonicalFieldSpec(("top_n",), top_n, 3, ((skills_group, (("top_n",),)),)),
            CanonicalFieldSpec(
                ("token_budget",),
                token_budget,
                1200,
                ((skills_group, (("token_budget",),)),),
            ),
        ),
    )
    if "manifest" in skills_group:
        payload["manifest"] = skills_group["manifest"]
    return payload


def build_index_payload(
    *,
    index_group: dict[str, Any],
    index_languages: list[str] | None,
    index_cache_path: str,
    index_incremental: bool,
    conventions_files: list[str] | None,
) -> dict[str, Any]:
    payload = build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("languages",), index_languages, None, ((index_group, (("languages",),)),)),
            CanonicalFieldSpec(
                ("cache_path",),
                index_cache_path,
                "context-map/index.json",
                ((index_group, (("cache_path",),)),),
            ),
            CanonicalFieldSpec(
                ("incremental",),
                index_incremental,
                True,
                ((index_group, (("incremental",),)),),
            ),
            CanonicalFieldSpec(
                ("conventions_files",),
                conventions_files,
                None,
                ((index_group, (("conventions_files",),)),),
            ),
        ),
    )
    if isinstance(payload.get("languages"), str):
        payload["languages"] = [
            item.strip() for item in str(payload["languages"]).split(",") if item.strip()
        ]
    if isinstance(payload.get("conventions_files"), str):
        payload["conventions_files"] = [
            item.strip()
            for item in str(payload["conventions_files"]).split(",")
            if item.strip()
        ]
    return payload


def build_repomap_payload(
    *,
    repomap_group: dict[str, Any],
    repomap_enabled: bool,
    repomap_top_k: int,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("enabled",), repomap_enabled, True, ((repomap_group, (("enabled",),)),)),
            CanonicalFieldSpec(("top_k",), repomap_top_k, 8, ((repomap_group, (("top_k",),)),)),
            CanonicalFieldSpec(
                ("neighbor_limit",),
                repomap_neighbor_limit,
                20,
                ((repomap_group, (("neighbor_limit",),)),),
            ),
            CanonicalFieldSpec(
                ("budget_tokens",),
                repomap_budget_tokens,
                800,
                ((repomap_group, (("budget_tokens",),)),),
            ),
            CanonicalFieldSpec(
                ("ranking_profile",),
                repomap_ranking_profile,
                "graph",
                ((repomap_group, (("ranking_profile",),)),),
            ),
            CanonicalFieldSpec(
                ("signal_weights",),
                repomap_signal_weights,
                None,
                ((repomap_group, (("signal_weights",),)),),
            ),
        ),
    )


def build_lsp_payload(
    *,
    lsp_group: dict[str, Any],
    lsp_enabled: bool,
    lsp_top_n: int,
    lsp_commands: dict[str, list[str]] | None,
    lsp_xref_enabled: bool,
    lsp_xref_top_n: int,
    lsp_time_budget_ms: int,
    lsp_xref_commands: dict[str, list[str]] | None,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("enabled",), lsp_enabled, False, ((lsp_group, (("enabled",),)),)),
            CanonicalFieldSpec(("top_n",), lsp_top_n, 5, ((lsp_group, (("top_n",),)),)),
            CanonicalFieldSpec(("commands",), lsp_commands, None, ((lsp_group, (("commands",),)),)),
            CanonicalFieldSpec(("xref_enabled",), lsp_xref_enabled, False, ((lsp_group, (("xref_enabled",),)),)),
            CanonicalFieldSpec(("xref_top_n",), lsp_xref_top_n, 3, ((lsp_group, (("xref_top_n",),)),)),
            CanonicalFieldSpec(
                ("time_budget_ms",),
                lsp_time_budget_ms,
                1500,
                ((lsp_group, (("time_budget_ms",),)),),
            ),
            CanonicalFieldSpec(
                ("xref_commands",),
                lsp_xref_commands,
                None,
                ((lsp_group, (("xref_commands",),)),),
            ),
        ),
    )


def build_plugins_payload(
    *,
    plugins_group: dict[str, Any],
    plugins_enabled: bool,
    remote_slot_policy_mode: str,
    remote_slot_allowlist: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("enabled",), plugins_enabled, True, ((plugins_group, (("enabled",),)),)),
            CanonicalFieldSpec(
                ("remote_slot_policy_mode",),
                remote_slot_policy_mode,
                "strict",
                ((plugins_group, (("remote_slot_policy_mode",),)),),
            ),
            CanonicalFieldSpec(
                ("remote_slot_allowlist",),
                remote_slot_allowlist,
                None,
                ((plugins_group, (("remote_slot_allowlist",),)),),
            ),
        ),
    )


def build_embeddings_payload(
    *,
    embeddings_group: dict[str, Any],
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_index_path: str,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("enabled",), embedding_enabled, False, ((embeddings_group, (("enabled",),)),)),
            CanonicalFieldSpec(("provider",), embedding_provider, "hash", ((embeddings_group, (("provider",),)),)),
            CanonicalFieldSpec(("model",), embedding_model, "hash-v1", ((embeddings_group, (("model",),)),)),
            CanonicalFieldSpec(("dimension",), embedding_dimension, 256, ((embeddings_group, (("dimension",),)),)),
            CanonicalFieldSpec(
                ("index_path",),
                embedding_index_path,
                "context-map/embeddings/index.json",
                ((embeddings_group, (("index_path",),)),),
            ),
            CanonicalFieldSpec(("rerank_pool",), embedding_rerank_pool, 24, ((embeddings_group, (("rerank_pool",),)),)),
            CanonicalFieldSpec(("lexical_weight",), embedding_lexical_weight, 0.7, ((embeddings_group, (("lexical_weight",),)),)),
            CanonicalFieldSpec(("semantic_weight",), embedding_semantic_weight, 0.3, ((embeddings_group, (("semantic_weight",),)),)),
            CanonicalFieldSpec(("min_similarity",), embedding_min_similarity, 0.0, ((embeddings_group, (("min_similarity",),)),)),
            CanonicalFieldSpec(("fail_open",), embedding_fail_open, True, ((embeddings_group, (("fail_open",),)),)),
        ),
    )


def build_tokenizer_payload(
    *,
    tokenizer_group: dict[str, Any],
    tokenizer_model: str,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("model",), tokenizer_model, "gpt-4o-mini", ((tokenizer_group, (("model",),)),)),
        ),
    )


def build_cochange_payload(
    *,
    cochange_group: dict[str, Any],
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("enabled",), cochange_enabled, True, ((cochange_group, (("enabled",),)),)),
            CanonicalFieldSpec(
                ("cache_path",),
                cochange_cache_path,
                "context-map/cochange.json",
                ((cochange_group, (("cache_path",),)),),
            ),
            CanonicalFieldSpec(
                ("lookback_commits",),
                cochange_lookback_commits,
                400,
                ((cochange_group, (("lookback_commits",),)),),
            ),
            CanonicalFieldSpec(
                ("half_life_days",),
                cochange_half_life_days,
                60.0,
                ((cochange_group, (("half_life_days",),)),),
            ),
            CanonicalFieldSpec(
                ("top_neighbors",),
                cochange_top_neighbors,
                12,
                ((cochange_group, (("top_neighbors",),)),),
            ),
            CanonicalFieldSpec(
                ("boost_weight",),
                cochange_boost_weight,
                1.5,
                ((cochange_group, (("boost_weight",),)),),
            ),
        ),
    )


def build_trace_payload(
    *,
    trace_group: dict[str, Any],
    trace_export_enabled: bool,
    trace_export_path: str,
    trace_otlp_enabled: bool,
    trace_otlp_endpoint: str,
    trace_otlp_timeout_seconds: float,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("export_enabled",), trace_export_enabled, False, ((trace_group, (("export_enabled",),)),)),
            CanonicalFieldSpec(
                ("export_path",),
                trace_export_path,
                "context-map/traces/stage_spans.jsonl",
                ((trace_group, (("export_path",),)),),
            ),
            CanonicalFieldSpec(("otlp_enabled",), trace_otlp_enabled, False, ((trace_group, (("otlp_enabled",),)),)),
            CanonicalFieldSpec(("otlp_endpoint",), trace_otlp_endpoint, "", ((trace_group, (("otlp_endpoint",),)),)),
            CanonicalFieldSpec(
                ("otlp_timeout_seconds",),
                trace_otlp_timeout_seconds,
                1.5,
                ((trace_group, (("otlp_timeout_seconds",),)),),
            ),
        ),
    )


def build_plan_replay_cache_payload(
    *,
    plan_replay_cache_group: dict[str, Any],
    plan_replay_cache_enabled: bool,
    plan_replay_cache_path: str,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(
                ("enabled",),
                plan_replay_cache_enabled,
                False,
                ((plan_replay_cache_group, (("enabled",),)),),
            ),
            CanonicalFieldSpec(
                ("cache_path",),
                plan_replay_cache_path,
                "context-map/plan-replay/cache.json",
                ((plan_replay_cache_group, (("cache_path",),)),),
            ),
        ),
    )


def build_tests_payload(
    *,
    tests_group: dict[str, Any],
    junit_xml: str | None,
    coverage_json: str | None,
    sbfl_json: str | None,
    sbfl_metric: str,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("junit_xml",), junit_xml, None, ((tests_group, (("junit_xml",),)),)),
            CanonicalFieldSpec(("coverage_json",), coverage_json, None, ((tests_group, (("coverage_json",),)),)),
            CanonicalFieldSpec(
                ("sbfl_json",),
                sbfl_json,
                None,
                ((tests_group, (("sbfl_json",), ("sbfl", "json_path"), ("sbfl", "json"))),),
            ),
            CanonicalFieldSpec(
                ("sbfl_metric",),
                sbfl_metric,
                "ochiai",
                ((tests_group, (("sbfl_metric",), ("sbfl", "metric"))),),
            ),
        ),
    )


def build_scip_payload(
    *,
    scip_group: dict[str, Any],
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("enabled",), scip_enabled, False, ((scip_group, (("enabled",),)),)),
            CanonicalFieldSpec(
                ("index_path",),
                scip_index_path,
                "context-map/scip/index.json",
                ((scip_group, (("index_path",),)),),
            ),
            CanonicalFieldSpec(("provider",), scip_provider, "auto", ((scip_group, (("provider",),)),)),
            CanonicalFieldSpec(
                ("generate_fallback",),
                scip_generate_fallback,
                True,
                ((scip_group, (("generate_fallback",),)),),
            ),
        ),
    )


def _build_payload_family_registry() -> dict[str, PayloadFamilyDescriptor]:
    descriptors = (
        PayloadFamilyDescriptor(
            family="memory",
            builder=build_memory_payload,
            grouped_inputs=("memory_group",),
        ),
        PayloadFamilyDescriptor(
            family="retrieval",
            builder=build_retrieval_payload,
            grouped_inputs=("retrieval_group", "adaptive_router_group"),
        ),
        PayloadFamilyDescriptor(
            family="chunking",
            builder=build_chunking_payload,
            grouped_inputs=("chunking_group",),
        ),
        PayloadFamilyDescriptor(
            family="skills",
            builder=build_skills_payload,
            grouped_inputs=("skills_group",),
        ),
        PayloadFamilyDescriptor(
            family="index",
            builder=build_index_payload,
            grouped_inputs=("index_group",),
        ),
        PayloadFamilyDescriptor(
            family="repomap",
            builder=build_repomap_payload,
            grouped_inputs=("repomap_group",),
        ),
        PayloadFamilyDescriptor(
            family="lsp",
            builder=build_lsp_payload,
            grouped_inputs=("lsp_group",),
        ),
        PayloadFamilyDescriptor(
            family="plugins",
            builder=build_plugins_payload,
            grouped_inputs=("plugins_group",),
        ),
        PayloadFamilyDescriptor(
            family="embeddings",
            builder=build_embeddings_payload,
            grouped_inputs=("embeddings_group",),
        ),
        PayloadFamilyDescriptor(
            family="tokenizer",
            builder=build_tokenizer_payload,
            grouped_inputs=("tokenizer_group",),
        ),
        PayloadFamilyDescriptor(
            family="cochange",
            builder=build_cochange_payload,
            grouped_inputs=("cochange_group",),
        ),
        PayloadFamilyDescriptor(
            family="trace",
            builder=build_trace_payload,
            grouped_inputs=("trace_group",),
        ),
        PayloadFamilyDescriptor(
            family="plan_replay_cache",
            builder=build_plan_replay_cache_payload,
            grouped_inputs=("plan_replay_cache_group",),
        ),
        PayloadFamilyDescriptor(
            family="tests",
            builder=build_tests_payload,
            grouped_inputs=("tests_group",),
        ),
        PayloadFamilyDescriptor(
            family="scip",
            builder=build_scip_payload,
            grouped_inputs=("scip_group",),
        ),
    )
    return {descriptor.family: descriptor for descriptor in descriptors}


PAYLOAD_FAMILY_REGISTRY: Mapping[str, PayloadFamilyDescriptor] = MappingProxyType(
    _build_payload_family_registry()
)


def iter_payload_family_descriptors() -> tuple[PayloadFamilyDescriptor, ...]:
    return tuple(PAYLOAD_FAMILY_REGISTRY.values())


def get_payload_family_descriptor(family: str) -> PayloadFamilyDescriptor:
    try:
        return PAYLOAD_FAMILY_REGISTRY[family]
    except KeyError as exc:
        raise KeyError(f"Unknown payload family: {family}") from exc


def build_payload_family(
    family: str,
    **kwargs: Any,
) -> dict[str, Any]:
    descriptor = get_payload_family_descriptor(family)
    return descriptor.builder(**kwargs)


__all__ = [
    "CanonicalFieldSpec",
    "build_canonical_payload",
    "build_chunking_payload",
    "build_cochange_payload",
    "build_embeddings_payload",
    "build_index_payload",
    "build_lsp_payload",
    "build_memory_payload",
    "build_plan_replay_cache_payload",
    "build_plugins_payload",
    "build_repomap_payload",
    "build_retrieval_payload",
    "build_scip_payload",
    "build_skills_payload",
    "build_tests_payload",
    "build_tokenizer_payload",
    "build_trace_payload",
    "normalize_group_mapping",
]
