"""Shared canonical payload helpers for orchestrator factory wiring."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ace_lite.cli_app.orchestrator_factory_memory_payload import (
    build_memory_payload,
)
from ace_lite.cli_app.orchestrator_factory_misc_payloads import (
    build_cochange_payload,
    build_embeddings_payload,
    build_index_payload,
    build_lsp_payload,
    build_plan_replay_cache_payload,
    build_plugins_payload,
    build_repomap_payload,
    build_scip_payload,
    build_skills_payload,
    build_tests_payload,
    build_tokenizer_payload,
    build_trace_payload,
)
from ace_lite.cli_app.orchestrator_factory_payload_core import (
    CanonicalFieldSpec,
    build_canonical_payload,
    resolve_grouped_value,
)
from ace_lite.cli_app.orchestrator_factory_retrieval_payloads import (
    build_chunking_payload,
    build_retrieval_payload,
)
from ace_lite.cli_app.orchestrator_factory_run_plan_sections import (
    GroupedFlatSectionSpec,
    build_adaptive_router_run_plan_section_spec,
    build_chunking_run_plan_section_spec,
    build_memory_run_plan_section_spec,
    build_passthrough_run_plan_section_specs,
    build_retrieval_run_plan_section_spec,
    merge_group_or_flat_sections,
    normalize_group_mapping,
)


@dataclass(frozen=True)
class PayloadFamilyDescriptor:
    family: str
    builder: Callable[..., dict[str, Any]]
    grouped_inputs: tuple[str, ...]


@dataclass(frozen=True)
class OrchestratorGroupedConfigs:
    retrieval_group: dict[str, Any]
    adaptive_router_group: dict[str, Any]
    plugins_group: dict[str, Any]
    repomap_group: dict[str, Any]
    lsp_group: dict[str, Any]
    chunking_group: dict[str, Any]
    tokenizer_group: dict[str, Any]
    trace_group: dict[str, Any]
    plan_replay_cache_group: dict[str, Any]
    memory_group: dict[str, Any]
    skills_group: dict[str, Any]
    index_group: dict[str, Any]
    embeddings_group: dict[str, Any]
    cochange_group: dict[str, Any]
    tests_group: dict[str, Any]
    scip_group: dict[str, Any]


def normalize_orchestrator_group_configs(
    *,
    memory_config: Mapping[str, Any] | None = None,
    skills_config: Mapping[str, Any] | None = None,
    index_config: Mapping[str, Any] | None = None,
    embeddings_config: Mapping[str, Any] | None = None,
    cochange_config: Mapping[str, Any] | None = None,
    tests_config: Mapping[str, Any] | None = None,
    scip_config: Mapping[str, Any] | None = None,
    retrieval_config: Mapping[str, Any] | None = None,
    adaptive_router_config: Mapping[str, Any] | None = None,
    plugins_config: Mapping[str, Any] | None = None,
    repomap_config: Mapping[str, Any] | None = None,
    lsp_config: Mapping[str, Any] | None = None,
    chunking_config: Mapping[str, Any] | None = None,
    tokenizer_config: Mapping[str, Any] | None = None,
    trace_config: Mapping[str, Any] | None = None,
    plan_replay_cache_config: Mapping[str, Any] | None = None,
) -> OrchestratorGroupedConfigs:
    return OrchestratorGroupedConfigs(
        retrieval_group=normalize_group_mapping(retrieval_config),
        adaptive_router_group=normalize_group_mapping(adaptive_router_config),
        plugins_group=normalize_group_mapping(plugins_config),
        repomap_group=normalize_group_mapping(repomap_config),
        lsp_group=normalize_group_mapping(lsp_config),
        chunking_group=normalize_group_mapping(chunking_config),
        tokenizer_group=normalize_group_mapping(tokenizer_config),
        trace_group=normalize_group_mapping(trace_config),
        plan_replay_cache_group=normalize_group_mapping(plan_replay_cache_config),
        memory_group=normalize_group_mapping(memory_config),
        skills_group=normalize_group_mapping(skills_config),
        index_group=normalize_group_mapping(index_config),
        embeddings_group=normalize_group_mapping(embeddings_config),
        cochange_group=normalize_group_mapping(cochange_config),
        tests_group=normalize_group_mapping(tests_config),
        scip_group=normalize_group_mapping(scip_config),
    )


def build_orchestrator_projection_payload_map(
    *,
    groups: OrchestratorGroupedConfigs,
    memory_disclosure_mode: str,
    memory_preview_max_chars: int,
    memory_strategy: str,
    memory_gate_enabled: bool,
    memory_gate_mode: str,
    memory_timeline_enabled: bool,
    memory_container_tag: str | None,
    memory_auto_tag_mode: str | None,
    memory_profile_enabled: bool,
    memory_profile_path: str,
    memory_profile_top_n: int,
    memory_profile_token_budget: int,
    memory_profile_expiry_enabled: bool,
    memory_profile_ttl_days: int,
    memory_profile_max_age_days: int,
    memory_feedback_enabled: bool,
    memory_feedback_path: str,
    memory_feedback_max_entries: int,
    memory_feedback_boost_per_select: float,
    memory_feedback_max_boost: float,
    memory_feedback_decay_days: float,
    memory_long_term_enabled: bool,
    memory_long_term_path: str,
    memory_long_term_top_n: int,
    memory_long_term_token_budget: int,
    memory_long_term_write_enabled: bool,
    memory_long_term_as_of_enabled: bool,
    memory_capture_enabled: bool,
    memory_capture_notes_path: str,
    memory_capture_min_query_length: int,
    memory_capture_keywords: list[str] | tuple[str, ...] | None,
    memory_notes_enabled: bool,
    memory_notes_path: str,
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
    skills_dir: str,
    precomputed_routing_enabled: bool,
    top_k_files: int,
    index_languages: list[str] | None,
    index_cache_path: str,
    index_incremental: bool,
    conventions_files: list[str] | None,
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
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    junit_xml: str | None,
    coverage_json: str | None,
    sbfl_json: str | None,
    sbfl_metric: str,
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
    repomap_enabled: bool,
    repomap_top_k: int,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
    lsp_enabled: bool,
    lsp_top_n: int,
    lsp_commands: dict[str, list[str]] | None,
    lsp_xref_enabled: bool,
    lsp_xref_top_n: int,
    lsp_time_budget_ms: int,
    lsp_xref_commands: dict[str, list[str]] | None,
    plugins_enabled: bool,
    remote_slot_policy_mode: str,
    remote_slot_allowlist: list[str] | tuple[str, ...] | None,
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
    tokenizer_model: str,
    trace_export_enabled: bool,
    trace_export_path: str,
    trace_otlp_enabled: bool,
    trace_otlp_endpoint: str,
    trace_otlp_timeout_seconds: float,
    plan_replay_cache_enabled: bool,
    plan_replay_cache_path: str,
) -> dict[str, dict[str, Any]]:
    return {
        "memory": build_memory_payload(
            memory_group=groups.memory_group,
            memory_disclosure_mode=memory_disclosure_mode,
            memory_preview_max_chars=memory_preview_max_chars,
            memory_strategy=memory_strategy,
            memory_gate_enabled=memory_gate_enabled,
            memory_gate_mode=memory_gate_mode,
            memory_timeline_enabled=memory_timeline_enabled,
            memory_container_tag=memory_container_tag,
            memory_auto_tag_mode=memory_auto_tag_mode,
            memory_profile_enabled=memory_profile_enabled,
            memory_profile_path=memory_profile_path,
            memory_profile_top_n=memory_profile_top_n,
            memory_profile_token_budget=memory_profile_token_budget,
            memory_profile_expiry_enabled=memory_profile_expiry_enabled,
            memory_profile_ttl_days=memory_profile_ttl_days,
            memory_profile_max_age_days=memory_profile_max_age_days,
            memory_feedback_enabled=memory_feedback_enabled,
            memory_feedback_path=memory_feedback_path,
            memory_feedback_max_entries=memory_feedback_max_entries,
            memory_feedback_boost_per_select=memory_feedback_boost_per_select,
            memory_feedback_max_boost=memory_feedback_max_boost,
            memory_feedback_decay_days=memory_feedback_decay_days,
            memory_long_term_enabled=memory_long_term_enabled,
            memory_long_term_path=memory_long_term_path,
            memory_long_term_top_n=memory_long_term_top_n,
            memory_long_term_token_budget=memory_long_term_token_budget,
            memory_long_term_write_enabled=memory_long_term_write_enabled,
            memory_long_term_as_of_enabled=memory_long_term_as_of_enabled,
            memory_capture_enabled=memory_capture_enabled,
            memory_capture_notes_path=memory_capture_notes_path,
            memory_capture_min_query_length=memory_capture_min_query_length,
            memory_capture_keywords=memory_capture_keywords,
            memory_notes_enabled=memory_notes_enabled,
            memory_notes_path=memory_notes_path,
            memory_notes_limit=memory_notes_limit,
            memory_notes_mode=memory_notes_mode,
            memory_notes_expiry_enabled=memory_notes_expiry_enabled,
            memory_notes_ttl_days=memory_notes_ttl_days,
            memory_notes_max_age_days=memory_notes_max_age_days,
            memory_postprocess_enabled=memory_postprocess_enabled,
            memory_postprocess_noise_filter_enabled=memory_postprocess_noise_filter_enabled,
            memory_postprocess_length_norm_anchor_chars=memory_postprocess_length_norm_anchor_chars,
            memory_postprocess_time_decay_half_life_days=memory_postprocess_time_decay_half_life_days,
            memory_postprocess_hard_min_score=memory_postprocess_hard_min_score,
            memory_postprocess_diversity_enabled=memory_postprocess_diversity_enabled,
            memory_postprocess_diversity_similarity_threshold=memory_postprocess_diversity_similarity_threshold,
        ),
        "skills": build_skills_payload(
            skills_group=groups.skills_group,
            skills_dir=skills_dir,
            precomputed_routing_enabled=precomputed_routing_enabled,
        ),
        "retrieval": build_retrieval_payload(
            retrieval_group=groups.retrieval_group,
            adaptive_router_group=groups.adaptive_router_group,
            top_k_files=top_k_files,
            min_candidate_score=min_candidate_score,
            candidate_relative_threshold=candidate_relative_threshold,
            candidate_ranker=candidate_ranker,
            exact_search_enabled=exact_search_enabled,
            deterministic_refine_enabled=deterministic_refine_enabled,
            exact_search_time_budget_ms=exact_search_time_budget_ms,
            exact_search_max_paths=exact_search_max_paths,
            hybrid_re2_fusion_mode=hybrid_re2_fusion_mode,
            hybrid_re2_rrf_k=hybrid_re2_rrf_k,
            hybrid_re2_bm25_weight=hybrid_re2_bm25_weight,
            hybrid_re2_heuristic_weight=hybrid_re2_heuristic_weight,
            hybrid_re2_coverage_weight=hybrid_re2_coverage_weight,
            hybrid_re2_combined_scale=hybrid_re2_combined_scale,
            retrieval_policy=retrieval_policy,
            policy_version=policy_version,
            adaptive_router_enabled=adaptive_router_enabled,
            adaptive_router_mode=adaptive_router_mode,
            adaptive_router_model_path=adaptive_router_model_path,
            adaptive_router_state_path=adaptive_router_state_path,
            adaptive_router_arm_set=adaptive_router_arm_set,
            adaptive_router_online_bandit_enabled=adaptive_router_online_bandit_enabled,
            adaptive_router_online_bandit_experiment_enabled=adaptive_router_online_bandit_experiment_enabled,
        ),
        "index": build_index_payload(
            index_group=groups.index_group,
            index_languages=index_languages,
            index_cache_path=index_cache_path,
            index_incremental=index_incremental,
            conventions_files=conventions_files,
        ),
        "repomap": build_repomap_payload(
            repomap_group=groups.repomap_group,
            repomap_enabled=repomap_enabled,
            repomap_top_k=repomap_top_k,
            repomap_neighbor_limit=repomap_neighbor_limit,
            repomap_budget_tokens=repomap_budget_tokens,
            repomap_ranking_profile=repomap_ranking_profile,
            repomap_signal_weights=repomap_signal_weights,
        ),
        "lsp": build_lsp_payload(
            lsp_group=groups.lsp_group,
            lsp_enabled=lsp_enabled,
            lsp_top_n=lsp_top_n,
            lsp_commands=lsp_commands,
            lsp_xref_enabled=lsp_xref_enabled,
            lsp_xref_top_n=lsp_xref_top_n,
            lsp_time_budget_ms=lsp_time_budget_ms,
            lsp_xref_commands=lsp_xref_commands,
        ),
        "plugins": build_plugins_payload(
            plugins_group=groups.plugins_group,
            plugins_enabled=plugins_enabled,
            remote_slot_policy_mode=remote_slot_policy_mode,
            remote_slot_allowlist=remote_slot_allowlist,
        ),
        "chunking": build_chunking_payload(
            chunking_group=groups.chunking_group,
            chunk_top_k=chunk_top_k,
            chunk_per_file_limit=chunk_per_file_limit,
            chunk_disclosure=chunk_disclosure,
            chunk_signature=chunk_signature,
            chunk_snippet_max_lines=chunk_snippet_max_lines,
            chunk_snippet_max_chars=chunk_snippet_max_chars,
            chunk_token_budget=chunk_token_budget,
            chunk_guard_enabled=chunk_guard_enabled,
            chunk_guard_mode=chunk_guard_mode,
            chunk_guard_lambda_penalty=chunk_guard_lambda_penalty,
            chunk_guard_min_pool=chunk_guard_min_pool,
            chunk_guard_max_pool=chunk_guard_max_pool,
            chunk_guard_min_marginal_utility=chunk_guard_min_marginal_utility,
            chunk_guard_compatibility_min_overlap=chunk_guard_compatibility_min_overlap,
            chunk_diversity_enabled=chunk_diversity_enabled,
            chunk_diversity_path_penalty=chunk_diversity_path_penalty,
            chunk_diversity_symbol_family_penalty=chunk_diversity_symbol_family_penalty,
            chunk_diversity_kind_penalty=chunk_diversity_kind_penalty,
            chunk_diversity_locality_penalty=chunk_diversity_locality_penalty,
            chunk_diversity_locality_window=chunk_diversity_locality_window,
        ),
        "tokenizer": build_tokenizer_payload(
            tokenizer_group=groups.tokenizer_group,
            tokenizer_model=tokenizer_model,
        ),
        "cochange": build_cochange_payload(
            cochange_group=groups.cochange_group,
            cochange_enabled=cochange_enabled,
            cochange_cache_path=cochange_cache_path,
            cochange_lookback_commits=cochange_lookback_commits,
            cochange_half_life_days=cochange_half_life_days,
            cochange_top_neighbors=cochange_top_neighbors,
            cochange_boost_weight=cochange_boost_weight,
        ),
        "tests": build_tests_payload(
            tests_group=groups.tests_group,
            junit_xml=junit_xml,
            coverage_json=coverage_json,
            sbfl_json=sbfl_json,
            sbfl_metric=sbfl_metric,
        ),
        "scip": build_scip_payload(
            scip_group=groups.scip_group,
            scip_enabled=scip_enabled,
            scip_index_path=scip_index_path,
            scip_provider=scip_provider,
            scip_generate_fallback=scip_generate_fallback,
        ),
        "embeddings": build_embeddings_payload(
            embeddings_group=groups.embeddings_group,
            embedding_enabled=embedding_enabled,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            embedding_index_path=embedding_index_path,
            embedding_rerank_pool=embedding_rerank_pool,
            embedding_lexical_weight=embedding_lexical_weight,
            embedding_semantic_weight=embedding_semantic_weight,
            embedding_min_similarity=embedding_min_similarity,
            embedding_fail_open=embedding_fail_open,
        ),
        "trace": build_trace_payload(
            trace_group=groups.trace_group,
            trace_export_enabled=trace_export_enabled,
            trace_export_path=trace_export_path,
            trace_otlp_enabled=trace_otlp_enabled,
            trace_otlp_endpoint=trace_otlp_endpoint,
            trace_otlp_timeout_seconds=trace_otlp_timeout_seconds,
        ),
        "plan_replay_cache": build_plan_replay_cache_payload(
            plan_replay_cache_group=groups.plan_replay_cache_group,
            plan_replay_cache_enabled=plan_replay_cache_enabled,
            plan_replay_cache_path=plan_replay_cache_path,
        ),
    }

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
    "GroupedFlatSectionSpec",
    "OrchestratorGroupedConfigs",
    "build_adaptive_router_run_plan_section_spec",
    "build_canonical_payload",
    "build_chunking_payload",
    "build_chunking_run_plan_section_spec",
    "build_cochange_payload",
    "build_embeddings_payload",
    "build_index_payload",
    "build_lsp_payload",
    "build_memory_payload",
    "build_memory_run_plan_section_spec",
    "build_orchestrator_projection_payload_map",
    "build_passthrough_run_plan_section_specs",
    "build_plan_replay_cache_payload",
    "build_plugins_payload",
    "build_repomap_payload",
    "build_retrieval_payload",
    "build_retrieval_run_plan_section_spec",
    "build_scip_payload",
    "build_skills_payload",
    "build_tests_payload",
    "build_tokenizer_payload",
    "build_trace_payload",
    "merge_group_or_flat_sections",
    "normalize_group_mapping",
    "normalize_orchestrator_group_configs",
    "resolve_grouped_value",
]
