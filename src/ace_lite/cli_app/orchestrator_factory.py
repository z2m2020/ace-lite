"""Factories for wiring memory providers and orchestrator instances from CLI inputs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click

from ace_lite.cli_app.orchestrator_factory_support import (
    GroupedFlatSectionSpec as _GroupedFlatSectionSpec,
    build_adaptive_router_run_plan_section_spec,
    build_chunking_payload,
    build_chunking_run_plan_section_spec,
    build_memory_run_plan_section_spec,
    build_passthrough_run_plan_section_specs,
    build_retrieval_payload,
    build_retrieval_run_plan_section_spec,
    build_cochange_payload,
    build_embeddings_payload,
    build_index_payload,
    build_lsp_payload,
    build_memory_payload,
    merge_group_or_flat_sections as _merge_group_or_flat_sections,
    build_plan_replay_cache_payload,
    build_plugins_payload,
    build_repomap_payload,
    build_scip_payload,
    build_skills_payload,
    build_tests_payload,
    build_tokenizer_payload,
    build_trace_payload,
    normalize_group_mapping as _normalize_group_mapping,
)
from ace_lite.cli_app.params import MEMORY_STRATEGY_CHOICES
from ace_lite.memory import (
    DualChannelMemoryProvider,
    HybridMemoryProvider,
    LocalCacheProvider,
    LocalNotesProvider,
    MemoryChannelRegistry,
    MemoryProvider,
    NullMemoryProvider,
    OpenMemoryClient,
    OpenMemoryMemoryProvider,
)
from ace_lite.memory_long_term import LongTermMemoryProvider, LongTermMemoryStore
from ace_lite.memory_clients.mcp_client import OpenMemoryMcpClient
from ace_lite.memory_clients.rest_client import OpenMemoryRestClient
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.plugins.loader import PluginLoader
from ace_lite.runtime_manager import RuntimeManager


def _provider_from_channel(
    *,
    channel: str,
    registry: MemoryChannelRegistry,
) -> MemoryProvider:
    try:
        return registry.create(channel)
    except KeyError as exc:
        raise click.BadParameter(f"Unsupported memory channel: {channel}") from exc


def _build_memory_channel_registry(
    *,
    mcp_base_url: str,
    rest_base_url: str,
    timeout_seconds: float,
    user_id: str | None,
    app: str | None,
    limit: int,
) -> MemoryChannelRegistry:
    registry = MemoryChannelRegistry()
    registry.register(
        name="none",
        aliases=("off", "disabled"),
        factory=lambda: NullMemoryProvider(),
    )
    registry.register(
        name="mcp",
        factory=lambda: OpenMemoryMemoryProvider(
            OpenMemoryMcpClient(base_url=mcp_base_url, timeout_seconds=timeout_seconds),
            user_id=user_id,
            app=app,
            limit=limit,
            channel_name="mcp",
        ),
    )
    registry.register(
        name="rest",
        factory=lambda: OpenMemoryMemoryProvider(
            OpenMemoryRestClient(
                base_url=rest_base_url, timeout_seconds=timeout_seconds
            ),
            user_id=user_id,
            app=app,
            limit=limit,
            channel_name="rest",
        ),
    )
    return registry


def _is_null_provider(provider: MemoryProvider) -> bool:
    return isinstance(provider, NullMemoryProvider)


def create_memory_provider(
    *,
    primary: str,
    secondary: str,
    memory_strategy: str,
    memory_hybrid_limit: int,
    memory_cache_enabled: bool,
    memory_cache_path: str,
    memory_cache_ttl_seconds: int,
    memory_cache_max_entries: int,
    memory_notes_enabled: bool = False,
    memory_notes_path: str = "context-map/memory_notes.jsonl",
    memory_notes_limit: int = 8,
    memory_notes_mode: str = "supplement",
    memory_notes_expiry_enabled: bool = True,
    memory_notes_ttl_days: int = 90,
    memory_notes_max_age_days: int = 365,
    memory_long_term_enabled: bool = False,
    memory_long_term_path: str = "context-map/long_term_memory.db",
    memory_long_term_top_n: int = 4,
    memory_long_term_token_budget: int = 192,
    memory_long_term_write_enabled: bool = False,
    memory_long_term_as_of_enabled: bool = True,
    mcp_base_url: str,
    rest_base_url: str,
    timeout_seconds: float,
    user_id: str | None,
    app: str | None,
    limit: int,
) -> MemoryProvider:
    primary = primary.lower().strip()
    secondary = secondary.lower().strip()
    strategy = str(memory_strategy or "hybrid").strip().lower() or "hybrid"
    if strategy not in MEMORY_STRATEGY_CHOICES:
        raise click.BadParameter(f"Unsupported memory strategy: {memory_strategy}")

    channel_registry = _build_memory_channel_registry(
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        timeout_seconds=timeout_seconds,
        user_id=user_id,
        app=app,
        limit=limit,
    )

    primary_provider = _provider_from_channel(
        channel=primary,
        registry=channel_registry,
    )
    secondary_provider = _provider_from_channel(
        channel=secondary,
        registry=channel_registry,
    )

    base_provider: MemoryProvider
    if _is_null_provider(primary_provider) and _is_null_provider(secondary_provider):
        base_provider = NullMemoryProvider()
    elif strategy == "hybrid" and not _is_null_provider(secondary_provider):
        semantic_provider = (
            secondary_provider
            if _is_null_provider(primary_provider)
            else primary_provider
        )
        keyword_provider = secondary_provider
        if semantic_provider is keyword_provider and not _is_null_provider(
            primary_provider
        ):
            keyword_provider = primary_provider
        if semantic_provider is keyword_provider:
            base_provider = semantic_provider
        else:
            base_provider = HybridMemoryProvider(
                semantic=semantic_provider,
                keyword=keyword_provider,
                limit=max(1, int(memory_hybrid_limit)),
            )
    elif _is_null_provider(primary_provider):
        base_provider = secondary_provider
    elif _is_null_provider(secondary_provider):
        base_provider = primary_provider
    else:
        base_provider = DualChannelMemoryProvider(
            primary=primary_provider,
            secondary=secondary_provider,
            fallback_on_empty=False,
            merge_on_fallback=True,
        )

    provider_with_cache = base_provider
    if not _is_null_provider(base_provider) and bool(memory_cache_enabled):
        provider_with_cache = LocalCacheProvider(
            base_provider,
            cache_path=memory_cache_path,
            ttl_seconds=max(1, int(memory_cache_ttl_seconds)),
            max_entries=max(16, int(memory_cache_max_entries)),
        )

    if _is_null_provider(provider_with_cache) or not bool(memory_notes_enabled):
        provider_with_notes = provider_with_cache
    else:
        provider_with_notes = LocalNotesProvider(
            provider_with_cache,
            notes_path=str(memory_notes_path),
            default_limit=max(1, int(memory_notes_limit)),
            mode=str(memory_notes_mode or "supplement").strip().lower() or "supplement",
            expiry_enabled=bool(memory_notes_expiry_enabled),
            ttl_days=max(1, int(memory_notes_ttl_days)),
            max_age_days=max(1, int(memory_notes_max_age_days)),
        )

    if not bool(memory_long_term_enabled):
        return provider_with_notes

    long_term_provider = LongTermMemoryProvider(
        LongTermMemoryStore(db_path=memory_long_term_path),
        limit=max(1, int(memory_long_term_top_n)),
        container_tag=None,
        channel_name="long_term",
    )
    setattr(long_term_provider, "token_budget", max(1, int(memory_long_term_token_budget)))
    setattr(long_term_provider, "write_enabled", bool(memory_long_term_write_enabled))
    setattr(long_term_provider, "as_of_enabled", bool(memory_long_term_as_of_enabled))

    if _is_null_provider(provider_with_notes):
        return long_term_provider

    return HybridMemoryProvider(
        semantic=provider_with_notes,
        keyword=long_term_provider,
        limit=max(max(1, int(limit)), max(1, int(memory_long_term_top_n))),
    )


def create_orchestrator(
    *,
    memory_client: OpenMemoryClient | None = None,
    memory_provider: MemoryProvider | None = None,
    plugin_loader: PluginLoader | None = None,
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
    memory_disclosure_mode: str = "compact",
    memory_preview_max_chars: int = 280,
    memory_strategy: str = "hybrid",
    memory_gate_enabled: bool = False,
    memory_gate_mode: str = "auto",
    memory_timeline_enabled: bool = True,
    memory_container_tag: str | None = None,
    memory_auto_tag_mode: str | None = None,
    memory_profile_enabled: bool = False,
    memory_profile_path: str | Path = "~/.ace-lite/profile.json",
    memory_profile_top_n: int = 4,
    memory_profile_token_budget: int = 160,
    memory_profile_expiry_enabled: bool = True,
    memory_profile_ttl_days: int = 90,
    memory_profile_max_age_days: int = 365,
    memory_feedback_enabled: bool = False,
    memory_feedback_path: str | Path = "~/.ace-lite/profile.json",
    memory_feedback_max_entries: int = 512,
    memory_feedback_boost_per_select: float = 0.15,
    memory_feedback_max_boost: float = 0.6,
    memory_feedback_decay_days: float = 60.0,
    memory_long_term_enabled: bool = False,
    memory_long_term_path: str | Path = "context-map/long_term_memory.db",
    memory_long_term_top_n: int = 4,
    memory_long_term_token_budget: int = 192,
    memory_long_term_write_enabled: bool = False,
    memory_long_term_as_of_enabled: bool = True,
    memory_capture_enabled: bool = False,
    memory_capture_notes_path: str | Path = "context-map/memory_notes.jsonl",
    memory_capture_min_query_length: int = 24,
    memory_capture_keywords: list[str] | tuple[str, ...] | None = None,
    memory_notes_enabled: bool = False,
    memory_notes_path: str | Path = "context-map/memory_notes.jsonl",
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
    skills_dir: str | Path = "skills",
    precomputed_skills_routing_enabled: bool = True,
    top_k_files: int = 8,
    index_languages: list[str] | None = None,
    index_cache_path: str | Path = "context-map/index.json",
    index_incremental: bool = True,
    conventions_files: list[str] | None = None,
    min_candidate_score: int = 2,
    candidate_relative_threshold: float = 0.0,
    candidate_ranker: str = "heuristic",
    exact_search_enabled: bool = False,
    deterministic_refine_enabled: bool = True,
    exact_search_time_budget_ms: int = 40,
    exact_search_max_paths: int = 24,
    hybrid_re2_fusion_mode: str = "linear",
    hybrid_re2_rrf_k: int = 60,
    hybrid_re2_bm25_weight: float = 0.0,
    hybrid_re2_heuristic_weight: float = 0.0,
    hybrid_re2_coverage_weight: float = 0.0,
    hybrid_re2_combined_scale: float = 0.0,
    embedding_enabled: bool = False,
    embedding_provider: str = "hash",
    embedding_model: str = "hash-v1",
    embedding_dimension: int = 256,
    embedding_index_path: str | Path = "context-map/embeddings/index.json",
    embedding_rerank_pool: int = 24,
    embedding_lexical_weight: float = 0.7,
    embedding_semantic_weight: float = 0.3,
    embedding_min_similarity: float = 0.0,
    embedding_fail_open: bool = True,
    repomap_enabled: bool = True,
    repomap_top_k: int = 8,
    repomap_neighbor_limit: int = 20,
    repomap_budget_tokens: int = 800,
    repomap_ranking_profile: str = "graph",
    repomap_signal_weights: dict[str, float] | None = None,
    lsp_enabled: bool = False,
    lsp_top_n: int = 5,
    lsp_commands: dict[str, list[str]] | None = None,
    lsp_xref_enabled: bool = False,
    lsp_xref_top_n: int = 3,
    lsp_time_budget_ms: int = 1500,
    lsp_xref_commands: dict[str, list[str]] | None = None,
    plugins_enabled: bool = True,
    remote_slot_policy_mode: str = "strict",
    remote_slot_allowlist: list[str] | tuple[str, ...] | None = None,
    chunk_top_k: int = 24,
    chunk_per_file_limit: int = 3,
    chunk_disclosure: str = "refs",
    chunk_signature: bool = False,
    chunk_snippet_max_lines: int = 18,
    chunk_snippet_max_chars: int = 1200,
    chunk_token_budget: int = 1200,
    chunk_guard_enabled: bool = False,
    chunk_guard_mode: str = "off",
    chunk_guard_lambda_penalty: float = 0.8,
    chunk_guard_min_pool: int = 4,
    chunk_guard_max_pool: int = 32,
    chunk_guard_min_marginal_utility: float = 0.0,
    chunk_guard_compatibility_min_overlap: float = 0.3,
    chunk_diversity_enabled: bool = True,
    chunk_diversity_path_penalty: float = 0.20,
    chunk_diversity_symbol_family_penalty: float = 0.30,
    chunk_diversity_kind_penalty: float = 0.10,
    chunk_diversity_locality_penalty: float = 0.15,
    chunk_diversity_locality_window: int = 24,
    tokenizer_model: str = "gpt-4o-mini",
    cochange_enabled: bool = True,
    cochange_cache_path: str | Path = "context-map/cochange.json",
    cochange_lookback_commits: int = 400,
    cochange_half_life_days: float = 60.0,
    cochange_top_neighbors: int = 12,
    cochange_boost_weight: float = 1.5,
    retrieval_policy: str = "auto",
    policy_version: str = "v1",
    adaptive_router_enabled: bool = False,
    adaptive_router_mode: str = "observe",
    adaptive_router_model_path: str | Path = "context-map/router/model.json",
    adaptive_router_state_path: str | Path = "context-map/router/state.json",
    adaptive_router_arm_set: str = "retrieval_policy_v1",
    adaptive_router_online_bandit_enabled: bool = False,
    adaptive_router_online_bandit_experiment_enabled: bool = False,
    junit_xml: str | None = None,
    coverage_json: str | None = None,
    sbfl_json: str | None = None,
    sbfl_metric: str = "ochiai",
    scip_enabled: bool = False,
    scip_index_path: str | Path = "context-map/scip/index.json",
    scip_provider: str = "auto",
    scip_generate_fallback: bool = True,
    trace_export_enabled: bool = False,
    trace_export_path: str | Path = "context-map/traces/stage_spans.jsonl",
    trace_otlp_enabled: bool = False,
    trace_otlp_endpoint: str = "",
    trace_otlp_timeout_seconds: float = 1.5,
    plan_replay_cache_enabled: bool = False,
    plan_replay_cache_path: str | Path = "context-map/plan-replay/cache.json",
) -> AceOrchestrator:
    if memory_provider is not None:
        provider = memory_provider
    elif memory_client is not None:
        provider = OpenMemoryMemoryProvider(memory_client)
    else:
        provider = NullMemoryProvider()

    retrieval_group = _normalize_group_mapping(retrieval_config)
    adaptive_router_group = _normalize_group_mapping(adaptive_router_config)
    plugins_group = _normalize_group_mapping(plugins_config)
    repomap_group = _normalize_group_mapping(repomap_config)
    lsp_group = _normalize_group_mapping(lsp_config)
    chunking_group = _normalize_group_mapping(chunking_config)
    tokenizer_group = _normalize_group_mapping(tokenizer_config)
    trace_group = _normalize_group_mapping(trace_config)
    plan_replay_cache_group = _normalize_group_mapping(plan_replay_cache_config)
    memory_group = _normalize_group_mapping(memory_config)
    skills_group = _normalize_group_mapping(skills_config)
    index_group = _normalize_group_mapping(index_config)
    embeddings_group = _normalize_group_mapping(embeddings_config)
    cochange_group = _normalize_group_mapping(cochange_config)
    tests_group = _normalize_group_mapping(tests_config)
    scip_group = _normalize_group_mapping(scip_config)

    memory_payload = build_memory_payload(
        memory_group=memory_group,
        memory_disclosure_mode=memory_disclosure_mode,
        memory_preview_max_chars=memory_preview_max_chars,
        memory_strategy=memory_strategy,
        memory_gate_enabled=memory_gate_enabled,
        memory_gate_mode=memory_gate_mode,
        memory_timeline_enabled=memory_timeline_enabled,
        memory_container_tag=(
            str(memory_container_tag) if memory_container_tag is not None else None
        ),
        memory_auto_tag_mode=(
            str(memory_auto_tag_mode) if memory_auto_tag_mode is not None else None
        ),
        memory_profile_enabled=memory_profile_enabled,
        memory_profile_path=str(memory_profile_path),
        memory_profile_top_n=memory_profile_top_n,
        memory_profile_token_budget=memory_profile_token_budget,
        memory_profile_expiry_enabled=memory_profile_expiry_enabled,
        memory_profile_ttl_days=memory_profile_ttl_days,
        memory_profile_max_age_days=memory_profile_max_age_days,
        memory_feedback_enabled=memory_feedback_enabled,
        memory_feedback_path=str(memory_feedback_path),
        memory_feedback_max_entries=memory_feedback_max_entries,
        memory_feedback_boost_per_select=memory_feedback_boost_per_select,
        memory_feedback_max_boost=memory_feedback_max_boost,
        memory_feedback_decay_days=memory_feedback_decay_days,
        memory_long_term_enabled=memory_long_term_enabled,
        memory_long_term_path=str(memory_long_term_path),
        memory_long_term_top_n=memory_long_term_top_n,
        memory_long_term_token_budget=memory_long_term_token_budget,
        memory_long_term_write_enabled=memory_long_term_write_enabled,
        memory_long_term_as_of_enabled=memory_long_term_as_of_enabled,
        memory_capture_enabled=memory_capture_enabled,
        memory_capture_notes_path=str(memory_capture_notes_path),
        memory_capture_min_query_length=memory_capture_min_query_length,
        memory_capture_keywords=memory_capture_keywords,
        memory_notes_enabled=memory_notes_enabled,
        memory_notes_path=str(memory_notes_path),
        memory_notes_limit=memory_notes_limit,
        memory_notes_mode=memory_notes_mode,
        memory_notes_expiry_enabled=memory_notes_expiry_enabled,
        memory_notes_ttl_days=memory_notes_ttl_days,
        memory_notes_max_age_days=memory_notes_max_age_days,
        memory_postprocess_enabled=memory_postprocess_enabled,
        memory_postprocess_noise_filter_enabled=(
            memory_postprocess_noise_filter_enabled
        ),
        memory_postprocess_length_norm_anchor_chars=(
            memory_postprocess_length_norm_anchor_chars
        ),
        memory_postprocess_time_decay_half_life_days=(
            memory_postprocess_time_decay_half_life_days
        ),
        memory_postprocess_hard_min_score=memory_postprocess_hard_min_score,
        memory_postprocess_diversity_enabled=memory_postprocess_diversity_enabled,
        memory_postprocess_diversity_similarity_threshold=(
            memory_postprocess_diversity_similarity_threshold
        ),
    )
    skills_payload = build_skills_payload(
        skills_group=skills_group,
        skills_dir=str(skills_dir),
        precomputed_routing_enabled=precomputed_skills_routing_enabled,
    )

    index_payload = build_index_payload(
        index_group=index_group,
        index_languages=index_languages,
        index_cache_path=str(index_cache_path),
        index_incremental=index_incremental,
        conventions_files=conventions_files,
    )

    embeddings_payload = build_embeddings_payload(
        embeddings_group=embeddings_group,
        embedding_enabled=embedding_enabled,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_index_path=str(embedding_index_path),
        embedding_rerank_pool=embedding_rerank_pool,
        embedding_lexical_weight=embedding_lexical_weight,
        embedding_semantic_weight=embedding_semantic_weight,
        embedding_min_similarity=embedding_min_similarity,
        embedding_fail_open=embedding_fail_open,
    )

    cochange_payload = build_cochange_payload(
        cochange_group=cochange_group,
        cochange_enabled=cochange_enabled,
        cochange_cache_path=str(cochange_cache_path),
        cochange_lookback_commits=cochange_lookback_commits,
        cochange_half_life_days=cochange_half_life_days,
        cochange_top_neighbors=cochange_top_neighbors,
        cochange_boost_weight=cochange_boost_weight,
    )

    tests_payload = build_tests_payload(
        tests_group=tests_group,
        junit_xml=junit_xml,
        coverage_json=coverage_json,
        sbfl_json=sbfl_json,
        sbfl_metric=sbfl_metric,
    )

    scip_payload = build_scip_payload(
        scip_group=scip_group,
        scip_enabled=scip_enabled,
        scip_index_path=str(scip_index_path),
        scip_provider=scip_provider,
        scip_generate_fallback=scip_generate_fallback,
    )

    retrieval_payload = build_retrieval_payload(
        retrieval_group=retrieval_group,
        adaptive_router_group=adaptive_router_group,
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
        adaptive_router_model_path=str(adaptive_router_model_path),
        adaptive_router_state_path=str(adaptive_router_state_path),
        adaptive_router_arm_set=adaptive_router_arm_set,
        adaptive_router_online_bandit_enabled=adaptive_router_online_bandit_enabled,
        adaptive_router_online_bandit_experiment_enabled=adaptive_router_online_bandit_experiment_enabled,
    )

    repomap_payload = build_repomap_payload(
        repomap_group=repomap_group,
        repomap_enabled=repomap_enabled,
        repomap_top_k=repomap_top_k,
        repomap_neighbor_limit=repomap_neighbor_limit,
        repomap_budget_tokens=repomap_budget_tokens,
        repomap_ranking_profile=repomap_ranking_profile,
        repomap_signal_weights=repomap_signal_weights,
    )

    lsp_payload = build_lsp_payload(
        lsp_group=lsp_group,
        lsp_enabled=lsp_enabled,
        lsp_top_n=lsp_top_n,
        lsp_commands=lsp_commands,
        lsp_xref_enabled=lsp_xref_enabled,
        lsp_xref_top_n=lsp_xref_top_n,
        lsp_time_budget_ms=lsp_time_budget_ms,
        lsp_xref_commands=lsp_xref_commands,
    )

    plugins_payload = build_plugins_payload(
        plugins_group=plugins_group,
        plugins_enabled=plugins_enabled,
        remote_slot_policy_mode=remote_slot_policy_mode,
        remote_slot_allowlist=remote_slot_allowlist,
    )

    chunking_payload = build_chunking_payload(
        chunking_group=chunking_group,
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
    )

    tokenizer_payload = build_tokenizer_payload(
        tokenizer_group=tokenizer_group,
        tokenizer_model=tokenizer_model,
    )

    trace_payload = build_trace_payload(
        trace_group=trace_group,
        trace_export_enabled=trace_export_enabled,
        trace_export_path=str(trace_export_path),
        trace_otlp_enabled=trace_otlp_enabled,
        trace_otlp_endpoint=trace_otlp_endpoint,
        trace_otlp_timeout_seconds=trace_otlp_timeout_seconds,
    )

    plan_replay_cache_payload = build_plan_replay_cache_payload(
        plan_replay_cache_group=plan_replay_cache_group,
        plan_replay_cache_enabled=plan_replay_cache_enabled,
        plan_replay_cache_path=str(plan_replay_cache_path),
    )

    config = OrchestratorConfig.model_validate(
        {
            "memory": memory_payload,
            "skills": skills_payload,
            "retrieval": retrieval_payload,
            "index": index_payload,
            "repomap": repomap_payload,
            "lsp": lsp_payload,
            "plugins": plugins_payload,
            "chunking": chunking_payload,
            "tokenizer": tokenizer_payload,
            "cochange": cochange_payload,
            "tests": tests_payload,
            "scip": scip_payload,
            "embeddings": embeddings_payload,
            "trace": trace_payload,
            "plan_replay_cache": plan_replay_cache_payload,
        }
    )

    runtime_manager = RuntimeManager(
        config=config,
        memory_provider=provider,
        plugin_loader=plugin_loader,
    )
    return AceOrchestrator(runtime_manager=runtime_manager)


def run_plan(
    *,
    query: str,
    repo: str,
    root: str,
    skills_dir: str | Path = "skills",
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    memory_client: OpenMemoryClient | None = None,
    memory_provider: MemoryProvider | None = None,
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
    memory_disclosure_mode: str = "compact",
    memory_preview_max_chars: int = 280,
    memory_strategy: str = "hybrid",
    memory_gate_enabled: bool = False,
    memory_gate_mode: str = "auto",
    memory_timeline_enabled: bool = True,
    memory_container_tag: str | None = None,
    memory_auto_tag_mode: str | None = None,
    memory_profile_enabled: bool = False,
    memory_profile_path: str | Path = "~/.ace-lite/profile.json",
    memory_profile_top_n: int = 4,
    memory_profile_token_budget: int = 160,
    memory_profile_expiry_enabled: bool = True,
    memory_profile_ttl_days: int = 90,
    memory_profile_max_age_days: int = 365,
    memory_feedback_enabled: bool = False,
    memory_feedback_path: str | Path = "~/.ace-lite/profile.json",
    memory_feedback_max_entries: int = 512,
    memory_feedback_boost_per_select: float = 0.15,
    memory_feedback_max_boost: float = 0.6,
    memory_feedback_decay_days: float = 60.0,
    memory_long_term_enabled: bool = False,
    memory_long_term_path: str | Path = "context-map/long_term_memory.db",
    memory_long_term_top_n: int = 4,
    memory_long_term_token_budget: int = 192,
    memory_long_term_write_enabled: bool = False,
    memory_long_term_as_of_enabled: bool = True,
    memory_capture_enabled: bool = False,
    memory_capture_notes_path: str | Path = "context-map/memory_notes.jsonl",
    memory_capture_min_query_length: int = 24,
    memory_capture_keywords: list[str] | tuple[str, ...] | None = None,
    memory_notes_enabled: bool = False,
    memory_notes_path: str | Path = "context-map/memory_notes.jsonl",
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
    top_k_files: int = 8,
    precomputed_skills_routing_enabled: bool = True,
    index_languages: list[str] | None = None,
    index_cache_path: str | Path = "context-map/index.json",
    index_incremental: bool = True,
    conventions_files: list[str] | None = None,
    min_candidate_score: int = 2,
    candidate_relative_threshold: float = 0.0,
    candidate_ranker: str = "heuristic",
    exact_search_enabled: bool = False,
    deterministic_refine_enabled: bool = True,
    exact_search_time_budget_ms: int = 40,
    exact_search_max_paths: int = 24,
    hybrid_re2_fusion_mode: str = "linear",
    hybrid_re2_rrf_k: int = 60,
    hybrid_re2_bm25_weight: float = 0.0,
    hybrid_re2_heuristic_weight: float = 0.0,
    hybrid_re2_coverage_weight: float = 0.0,
    hybrid_re2_combined_scale: float = 0.0,
    embedding_enabled: bool = False,
    embedding_provider: str = "hash",
    embedding_model: str = "hash-v1",
    embedding_dimension: int = 256,
    embedding_index_path: str | Path = "context-map/embeddings/index.json",
    embedding_rerank_pool: int = 24,
    embedding_lexical_weight: float = 0.7,
    embedding_semantic_weight: float = 0.3,
    embedding_min_similarity: float = 0.0,
    embedding_fail_open: bool = True,
    repomap_enabled: bool = True,
    repomap_top_k: int = 8,
    repomap_neighbor_limit: int = 20,
    repomap_budget_tokens: int = 800,
    repomap_ranking_profile: str = "graph",
    repomap_signal_weights: dict[str, float] | None = None,
    lsp_enabled: bool = False,
    lsp_top_n: int = 5,
    lsp_commands: dict[str, list[str]] | None = None,
    lsp_xref_enabled: bool = False,
    lsp_xref_top_n: int = 3,
    lsp_time_budget_ms: int = 1500,
    lsp_xref_commands: dict[str, list[str]] | None = None,
    plugins_enabled: bool = True,
    remote_slot_policy_mode: str = "strict",
    remote_slot_allowlist: list[str] | tuple[str, ...] | None = None,
    chunk_top_k: int = 24,
    chunk_per_file_limit: int = 3,
    chunk_disclosure: str = "refs",
    chunk_signature: bool = False,
    chunk_snippet_max_lines: int = 18,
    chunk_snippet_max_chars: int = 1200,
    chunk_token_budget: int = 1200,
    chunk_guard_enabled: bool = False,
    chunk_guard_mode: str = "off",
    chunk_guard_lambda_penalty: float = 0.8,
    chunk_guard_min_pool: int = 4,
    chunk_guard_max_pool: int = 32,
    chunk_guard_min_marginal_utility: float = 0.0,
    chunk_guard_compatibility_min_overlap: float = 0.3,
    chunk_diversity_enabled: bool = True,
    chunk_diversity_path_penalty: float = 0.20,
    chunk_diversity_symbol_family_penalty: float = 0.30,
    chunk_diversity_kind_penalty: float = 0.10,
    chunk_diversity_locality_penalty: float = 0.15,
    chunk_diversity_locality_window: int = 24,
    tokenizer_model: str = "gpt-4o-mini",
    cochange_enabled: bool = True,
    cochange_cache_path: str | Path = "context-map/cochange.json",
    cochange_lookback_commits: int = 400,
    cochange_half_life_days: float = 60.0,
    cochange_top_neighbors: int = 12,
    cochange_boost_weight: float = 1.5,
    retrieval_policy: str = "auto",
    policy_version: str = "v1",
    adaptive_router_enabled: bool = False,
    adaptive_router_mode: str = "observe",
    adaptive_router_model_path: str | Path = "context-map/router/model.json",
    adaptive_router_state_path: str | Path = "context-map/router/state.json",
    adaptive_router_arm_set: str = "retrieval_policy_v1",
    adaptive_router_online_bandit_enabled: bool = False,
    adaptive_router_online_bandit_experiment_enabled: bool = False,
    junit_xml: str | None = None,
    coverage_json: str | None = None,
    sbfl_json: str | None = None,
    sbfl_metric: str = "ochiai",
    scip_enabled: bool = False,
    scip_index_path: str | Path = "context-map/scip/index.json",
    scip_provider: str = "auto",
    scip_generate_fallback: bool = True,
    trace_export_enabled: bool = False,
    trace_export_path: str | Path = "context-map/traces/stage_spans.jsonl",
    trace_otlp_enabled: bool = False,
    trace_otlp_endpoint: str = "",
    trace_otlp_timeout_seconds: float = 1.5,
    plan_replay_cache_enabled: bool = False,
    plan_replay_cache_path: str | Path = "context-map/plan-replay/cache.json",
) -> dict[str, Any]:
    retrieval_group = _normalize_group_mapping(retrieval_config)
    adaptive_router_group = _normalize_group_mapping(adaptive_router_config)
    plugins_group = _normalize_group_mapping(plugins_config)
    repomap_group = _normalize_group_mapping(repomap_config)
    lsp_group = _normalize_group_mapping(lsp_config)
    memory_group = _normalize_group_mapping(memory_config)
    chunking_group = _normalize_group_mapping(chunking_config)
    tokenizer_group = _normalize_group_mapping(tokenizer_config)
    skills_group = _normalize_group_mapping(skills_config)
    index_group = _normalize_group_mapping(index_config)
    embeddings_group = _normalize_group_mapping(embeddings_config)
    cochange_group = _normalize_group_mapping(cochange_config)
    tests_group = _normalize_group_mapping(tests_config)
    scip_group = _normalize_group_mapping(scip_config)
    trace_group = _normalize_group_mapping(trace_config)
    plan_replay_cache_group = _normalize_group_mapping(plan_replay_cache_config)

    orchestrator_kwargs: dict[str, Any] = {
        "memory_client": memory_client,
        "memory_provider": memory_provider,
    }

    section_specs: tuple[_GroupedFlatSectionSpec, ...] = (
        build_memory_run_plan_section_spec(
            memory_group=memory_group,
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
        build_chunking_run_plan_section_spec(
            chunking_group=chunking_group,
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
        build_retrieval_run_plan_section_spec(
            retrieval_group=retrieval_group,
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
        ),
        build_adaptive_router_run_plan_section_spec(
            adaptive_router_group=adaptive_router_group,
            adaptive_router_enabled=adaptive_router_enabled,
            adaptive_router_mode=adaptive_router_mode,
            adaptive_router_model_path=adaptive_router_model_path,
            adaptive_router_state_path=adaptive_router_state_path,
            adaptive_router_arm_set=adaptive_router_arm_set,
            adaptive_router_online_bandit_enabled=adaptive_router_online_bandit_enabled,
            adaptive_router_online_bandit_experiment_enabled=adaptive_router_online_bandit_experiment_enabled,
        ),
    )
    section_specs += build_passthrough_run_plan_section_specs(
        skills_group=skills_group,
        skills_dir=skills_dir,
        precomputed_skills_routing_enabled=precomputed_skills_routing_enabled,
        index_group=index_group,
        index_languages=index_languages,
        index_cache_path=index_cache_path,
        index_incremental=index_incremental,
        conventions_files=conventions_files,
        embeddings_group=embeddings_group,
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
        tokenizer_group=tokenizer_group,
        tokenizer_model=tokenizer_model,
        cochange_group=cochange_group,
        cochange_enabled=cochange_enabled,
        cochange_cache_path=cochange_cache_path,
        cochange_lookback_commits=cochange_lookback_commits,
        cochange_half_life_days=cochange_half_life_days,
        cochange_top_neighbors=cochange_top_neighbors,
        cochange_boost_weight=cochange_boost_weight,
        tests_group=tests_group,
        junit_xml=junit_xml,
        coverage_json=coverage_json,
        sbfl_json=sbfl_json,
        sbfl_metric=sbfl_metric,
        scip_group=scip_group,
        scip_enabled=scip_enabled,
        scip_index_path=scip_index_path,
        scip_provider=scip_provider,
        scip_generate_fallback=scip_generate_fallback,
        plugins_group=plugins_group,
        plugins_enabled=plugins_enabled,
        remote_slot_policy_mode=remote_slot_policy_mode,
        remote_slot_allowlist=remote_slot_allowlist,
        repomap_group=repomap_group,
        repomap_enabled=repomap_enabled,
        repomap_top_k=repomap_top_k,
        repomap_neighbor_limit=repomap_neighbor_limit,
        repomap_budget_tokens=repomap_budget_tokens,
        repomap_ranking_profile=repomap_ranking_profile,
        repomap_signal_weights=repomap_signal_weights,
        lsp_group=lsp_group,
        lsp_enabled=lsp_enabled,
        lsp_top_n=lsp_top_n,
        lsp_commands=lsp_commands,
        lsp_xref_enabled=lsp_xref_enabled,
        lsp_xref_top_n=lsp_xref_top_n,
        lsp_time_budget_ms=lsp_time_budget_ms,
        lsp_xref_commands=lsp_xref_commands,
        trace_group=trace_group,
        trace_export_enabled=trace_export_enabled,
        trace_export_path=trace_export_path,
        trace_otlp_enabled=trace_otlp_enabled,
        trace_otlp_endpoint=trace_otlp_endpoint,
        trace_otlp_timeout_seconds=trace_otlp_timeout_seconds,
        plan_replay_cache_group=plan_replay_cache_group,
        plan_replay_cache_enabled=plan_replay_cache_enabled,
        plan_replay_cache_path=plan_replay_cache_path,
    )
    _merge_group_or_flat_sections(
        target=orchestrator_kwargs,
        sections=section_specs,
    )

    orchestrator = create_orchestrator(**orchestrator_kwargs)
    return orchestrator.plan(
        query=query,
        repo=repo,
        root=root,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
    )


__all__ = [
    "create_memory_provider",
    "create_orchestrator",
    "run_plan",
]
