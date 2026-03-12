"""Factories for wiring memory providers and orchestrator instances from CLI inputs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click

from ace_lite.cli_app.orchestrator_factory_support import (
    CanonicalFieldSpec as _CanonicalFieldSpec,
    build_canonical_payload as _build_canonical_payload,
    build_cochange_payload,
    build_embeddings_payload,
    build_index_payload,
    build_memory_payload,
    build_scip_payload,
    build_skills_payload,
    build_tests_payload,
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
        return provider_with_cache

    return LocalNotesProvider(
        provider_with_cache,
        notes_path=str(memory_notes_path),
        default_limit=max(1, int(memory_notes_limit)),
        mode=str(memory_notes_mode or "supplement").strip().lower() or "supplement",
        expiry_enabled=bool(memory_notes_expiry_enabled),
        ttl_days=max(1, int(memory_notes_ttl_days)),
        max_age_days=max(1, int(memory_notes_max_age_days)),
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

    retrieval_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("top_k_files",), top_k_files, 8, ((retrieval_group, (("top_k_files",),)),)),
            _CanonicalFieldSpec(("min_candidate_score",), min_candidate_score, 2, ((retrieval_group, (("min_candidate_score",),)),)),
            _CanonicalFieldSpec(
                ("candidate_relative_threshold",),
                candidate_relative_threshold,
                0.0,
                ((retrieval_group, (("candidate_relative_threshold",),)),),
            ),
            _CanonicalFieldSpec(("candidate_ranker",), candidate_ranker, "heuristic", ((retrieval_group, (("candidate_ranker",),)),)),
            _CanonicalFieldSpec(("exact_search_enabled",), exact_search_enabled, False, ((retrieval_group, (("exact_search_enabled",),)),)),
            _CanonicalFieldSpec(
                ("deterministic_refine_enabled",),
                deterministic_refine_enabled,
                True,
                ((retrieval_group, (("deterministic_refine_enabled",),)),),
            ),
            _CanonicalFieldSpec(
                ("exact_search_time_budget_ms",),
                exact_search_time_budget_ms,
                40,
                ((retrieval_group, (("exact_search_time_budget_ms",),)),),
            ),
            _CanonicalFieldSpec(("exact_search_max_paths",), exact_search_max_paths, 24, ((retrieval_group, (("exact_search_max_paths",),)),)),
            _CanonicalFieldSpec(("hybrid_re2_fusion_mode",), hybrid_re2_fusion_mode, "linear", ((retrieval_group, (("hybrid_re2_fusion_mode",),)),)),
            _CanonicalFieldSpec(("hybrid_re2_rrf_k",), hybrid_re2_rrf_k, 60, ((retrieval_group, (("hybrid_re2_rrf_k",),)),)),
            _CanonicalFieldSpec(("hybrid_re2_bm25_weight",), hybrid_re2_bm25_weight, 0.0, ((retrieval_group, (("hybrid_re2_bm25_weight",),)),)),
            _CanonicalFieldSpec(("hybrid_re2_heuristic_weight",), hybrid_re2_heuristic_weight, 0.0, ((retrieval_group, (("hybrid_re2_heuristic_weight",),)),)),
            _CanonicalFieldSpec(("hybrid_re2_coverage_weight",), hybrid_re2_coverage_weight, 0.0, ((retrieval_group, (("hybrid_re2_coverage_weight",),)),)),
            _CanonicalFieldSpec(("hybrid_re2_combined_scale",), hybrid_re2_combined_scale, 0.0, ((retrieval_group, (("hybrid_re2_combined_scale",),)),)),
            _CanonicalFieldSpec(("retrieval_policy",), retrieval_policy, "auto", ((retrieval_group, (("retrieval_policy",),)),)),
            _CanonicalFieldSpec(("policy_version",), policy_version, "v1", ((retrieval_group, (("policy_version",),)),)),
            _CanonicalFieldSpec(
                ("adaptive_router_enabled",),
                adaptive_router_enabled,
                False,
                (
                    (adaptive_router_group, (("enabled",),)),
                    (retrieval_group, (("adaptive_router_enabled",), ("adaptive_router", "enabled"))),
                ),
            ),
            _CanonicalFieldSpec(
                ("adaptive_router_mode",),
                adaptive_router_mode,
                "observe",
                (
                    (adaptive_router_group, (("mode",),)),
                    (retrieval_group, (("adaptive_router_mode",), ("adaptive_router", "mode"))),
                ),
            ),
            _CanonicalFieldSpec(
                ("adaptive_router_model_path",),
                adaptive_router_model_path,
                "context-map/router/model.json",
                (
                    (adaptive_router_group, (("model_path",),)),
                    (retrieval_group, (("adaptive_router_model_path",), ("adaptive_router", "model_path"))),
                ),
            ),
            _CanonicalFieldSpec(
                ("adaptive_router_state_path",),
                adaptive_router_state_path,
                "context-map/router/state.json",
                (
                    (adaptive_router_group, (("state_path",),)),
                    (retrieval_group, (("adaptive_router_state_path",), ("adaptive_router", "state_path"))),
                ),
            ),
            _CanonicalFieldSpec(
                ("adaptive_router_arm_set",),
                adaptive_router_arm_set,
                "retrieval_policy_v1",
                (
                    (adaptive_router_group, (("arm_set",),)),
                    (retrieval_group, (("adaptive_router_arm_set",), ("adaptive_router", "arm_set"))),
                ),
            ),
            _CanonicalFieldSpec(
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
            _CanonicalFieldSpec(
                ("adaptive_router_online_bandit_experiment_enabled",),
                adaptive_router_online_bandit_experiment_enabled,
                False,
                (
                    (adaptive_router_group, (("online_bandit", "experiment_enabled"),)),
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

    repomap_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("enabled",), repomap_enabled, True, ((repomap_group, (("enabled",),)),)),
            _CanonicalFieldSpec(("top_k",), repomap_top_k, 8, ((repomap_group, (("top_k",),)),)),
            _CanonicalFieldSpec(("neighbor_limit",), repomap_neighbor_limit, 20, ((repomap_group, (("neighbor_limit",),)),)),
            _CanonicalFieldSpec(("budget_tokens",), repomap_budget_tokens, 800, ((repomap_group, (("budget_tokens",),)),)),
            _CanonicalFieldSpec(("ranking_profile",), repomap_ranking_profile, "graph", ((repomap_group, (("ranking_profile",),)),)),
            _CanonicalFieldSpec(("signal_weights",), repomap_signal_weights, None, ((repomap_group, (("signal_weights",),)),)),
        ),
    )

    lsp_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("enabled",), lsp_enabled, False, ((lsp_group, (("enabled",),)),)),
            _CanonicalFieldSpec(("top_n",), lsp_top_n, 5, ((lsp_group, (("top_n",),)),)),
            _CanonicalFieldSpec(("commands",), lsp_commands, None, ((lsp_group, (("commands",),)),)),
            _CanonicalFieldSpec(("xref_enabled",), lsp_xref_enabled, False, ((lsp_group, (("xref_enabled",),)),)),
            _CanonicalFieldSpec(("xref_top_n",), lsp_xref_top_n, 3, ((lsp_group, (("xref_top_n",),)),)),
            _CanonicalFieldSpec(("time_budget_ms",), lsp_time_budget_ms, 1500, ((lsp_group, (("time_budget_ms",),)),)),
            _CanonicalFieldSpec(("xref_commands",), lsp_xref_commands, None, ((lsp_group, (("xref_commands",),)),)),
        ),
    )

    plugins_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("enabled",), plugins_enabled, True, ((plugins_group, (("enabled",),)),)),
            _CanonicalFieldSpec(
                ("remote_slot_policy_mode",),
                remote_slot_policy_mode,
                "strict",
                ((plugins_group, (("remote_slot_policy_mode",),)),),
            ),
            _CanonicalFieldSpec(
                ("remote_slot_allowlist",),
                remote_slot_allowlist,
                None,
                ((plugins_group, (("remote_slot_allowlist",),)),),
            ),
        ),
    )

    chunking_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("top_k",), chunk_top_k, 24, ((chunking_group, (("top_k",),)),)),
            _CanonicalFieldSpec(("per_file_limit",), chunk_per_file_limit, 3, ((chunking_group, (("per_file_limit",),)),)),
            _CanonicalFieldSpec(("disclosure",), chunk_disclosure, "refs", ((chunking_group, (("disclosure",),)),)),
            _CanonicalFieldSpec(("signature",), chunk_signature, False, ((chunking_group, (("signature",),)),)),
            _CanonicalFieldSpec(("snippet_max_lines",), chunk_snippet_max_lines, 18, ((chunking_group, (("snippet", "max_lines"), ("snippet_max_lines",))),)),
            _CanonicalFieldSpec(("snippet_max_chars",), chunk_snippet_max_chars, 1200, ((chunking_group, (("snippet", "max_chars"), ("snippet_max_chars",))),)),
            _CanonicalFieldSpec(("token_budget",), chunk_token_budget, 1200, ((chunking_group, (("token_budget",),)),)),
            _CanonicalFieldSpec(
                ("topological_shield", "enabled"),
                False,
                False,
                ((chunking_group, (("topological_shield", "enabled"),)),),
            ),
            _CanonicalFieldSpec(
                ("topological_shield", "mode"),
                "off",
                "off",
                ((chunking_group, (("topological_shield", "mode"),)),),
            ),
            _CanonicalFieldSpec(
                ("topological_shield", "max_attenuation"),
                0.6,
                0.6,
                ((chunking_group, (("topological_shield", "max_attenuation"),)),),
            ),
            _CanonicalFieldSpec(
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
            _CanonicalFieldSpec(
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
            _CanonicalFieldSpec(("guard", "enabled"), chunk_guard_enabled, False, ((chunking_group, (("guard", "enabled"), ("guard_enabled",))),)),
            _CanonicalFieldSpec(("guard", "mode"), chunk_guard_mode, "off", ((chunking_group, (("guard", "mode"), ("guard_mode",))),)),
            _CanonicalFieldSpec(("guard", "lambda_penalty"), chunk_guard_lambda_penalty, 0.8, ((chunking_group, (("guard", "lambda_penalty"), ("guard_lambda_penalty",))),)),
            _CanonicalFieldSpec(("guard", "min_pool"), chunk_guard_min_pool, 4, ((chunking_group, (("guard", "min_pool"), ("guard_min_pool",))),)),
            _CanonicalFieldSpec(("guard", "max_pool"), chunk_guard_max_pool, 32, ((chunking_group, (("guard", "max_pool"), ("guard_max_pool",))),)),
            _CanonicalFieldSpec(("guard", "min_marginal_utility"), chunk_guard_min_marginal_utility, 0.0, ((chunking_group, (("guard", "min_marginal_utility"), ("guard_min_marginal_utility",))),)),
            _CanonicalFieldSpec(("guard", "compatibility_min_overlap"), chunk_guard_compatibility_min_overlap, 0.3, ((chunking_group, (("guard", "compatibility_min_overlap"), ("guard_compatibility_min_overlap",))),)),
            _CanonicalFieldSpec(("diversity_enabled",), chunk_diversity_enabled, True, ((chunking_group, (("diversity_enabled",),)),)),
            _CanonicalFieldSpec(("diversity_path_penalty",), chunk_diversity_path_penalty, 0.20, ((chunking_group, (("diversity_path_penalty",),)),)),
            _CanonicalFieldSpec(("diversity_symbol_family_penalty",), chunk_diversity_symbol_family_penalty, 0.30, ((chunking_group, (("diversity_symbol_family_penalty",),)),)),
            _CanonicalFieldSpec(("diversity_kind_penalty",), chunk_diversity_kind_penalty, 0.10, ((chunking_group, (("diversity_kind_penalty",),)),)),
            _CanonicalFieldSpec(("diversity_locality_penalty",), chunk_diversity_locality_penalty, 0.15, ((chunking_group, (("diversity_locality_penalty",),)),)),
            _CanonicalFieldSpec(("diversity_locality_window",), chunk_diversity_locality_window, 24, ((chunking_group, (("diversity_locality_window",),)),)),
        ),
    )

    tokenizer_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("model",), tokenizer_model, "gpt-4o-mini", ((tokenizer_group, (("model",),)),)),
        ),
    )

    trace_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("export_enabled",), trace_export_enabled, False, ((trace_group, (("export_enabled",),)),)),
            _CanonicalFieldSpec(("export_path",), trace_export_path, "context-map/traces/stage_spans.jsonl", ((trace_group, (("export_path",),)),)),
            _CanonicalFieldSpec(("otlp_enabled",), trace_otlp_enabled, False, ((trace_group, (("otlp_enabled",),)),)),
            _CanonicalFieldSpec(("otlp_endpoint",), trace_otlp_endpoint, "", ((trace_group, (("otlp_endpoint",),)),)),
            _CanonicalFieldSpec(("otlp_timeout_seconds",), trace_otlp_timeout_seconds, 1.5, ((trace_group, (("otlp_timeout_seconds",),)),)),
        ),
    )

    plan_replay_cache_payload = _build_canonical_payload(
        field_specs=(
            _CanonicalFieldSpec(("enabled",), plan_replay_cache_enabled, False, ((plan_replay_cache_group, (("enabled",),)),)),
            _CanonicalFieldSpec(("cache_path",), plan_replay_cache_path, "context-map/plan-replay/cache.json", ((plan_replay_cache_group, (("cache_path",),)),)),
        ),
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

    def attach_group_or_flat(
        *,
        group_key: str,
        group_payload: dict[str, Any],
        flat_payload: dict[str, Any],
    ) -> None:
        if group_payload:
            orchestrator_kwargs[group_key] = dict(group_payload)
        else:
            orchestrator_kwargs.update(flat_payload)

    attach_group_or_flat(
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
    attach_group_or_flat(
        group_key="skills_config",
        group_payload=skills_group,
        flat_payload={
            "skills_dir": skills_dir,
            "precomputed_skills_routing_enabled": precomputed_skills_routing_enabled,
        },
    )
    attach_group_or_flat(
        group_key="index_config",
        group_payload=index_group,
        flat_payload={
            "index_languages": index_languages,
            "index_cache_path": index_cache_path,
            "index_incremental": index_incremental,
            "conventions_files": conventions_files,
        },
    )
    attach_group_or_flat(
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
    )
    attach_group_or_flat(
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
    attach_group_or_flat(
        group_key="tokenizer_config",
        group_payload=tokenizer_group,
        flat_payload={
            "tokenizer_model": tokenizer_model,
        },
    )
    attach_group_or_flat(
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
    attach_group_or_flat(
        group_key="adaptive_router_config",
        group_payload=adaptive_router_group,
        flat_payload={
            "adaptive_router_enabled": adaptive_router_enabled,
            "adaptive_router_mode": adaptive_router_mode,
            "adaptive_router_model_path": adaptive_router_model_path,
            "adaptive_router_state_path": adaptive_router_state_path,
            "adaptive_router_arm_set": adaptive_router_arm_set,
            "adaptive_router_online_bandit_enabled": adaptive_router_online_bandit_enabled,
            "adaptive_router_online_bandit_experiment_enabled": (
                adaptive_router_online_bandit_experiment_enabled
            ),
        },
    )
    attach_group_or_flat(
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
    )
    attach_group_or_flat(
        group_key="tests_config",
        group_payload=tests_group,
        flat_payload={
            "junit_xml": junit_xml,
            "coverage_json": coverage_json,
            "sbfl_json": sbfl_json,
            "sbfl_metric": sbfl_metric,
        },
    )
    attach_group_or_flat(
        group_key="scip_config",
        group_payload=scip_group,
        flat_payload={
            "scip_enabled": scip_enabled,
            "scip_index_path": scip_index_path,
            "scip_provider": scip_provider,
            "scip_generate_fallback": scip_generate_fallback,
        },
    )
    attach_group_or_flat(
        group_key="plugins_config",
        group_payload=plugins_group,
        flat_payload={
            "plugins_enabled": plugins_enabled,
            "remote_slot_policy_mode": remote_slot_policy_mode,
            "remote_slot_allowlist": remote_slot_allowlist,
        },
    )
    attach_group_or_flat(
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
    )
    attach_group_or_flat(
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
    )
    attach_group_or_flat(
        group_key="trace_config",
        group_payload=trace_group,
        flat_payload={
            "trace_export_enabled": trace_export_enabled,
            "trace_export_path": trace_export_path,
            "trace_otlp_enabled": trace_otlp_enabled,
            "trace_otlp_endpoint": trace_otlp_endpoint,
            "trace_otlp_timeout_seconds": trace_otlp_timeout_seconds,
        },
    )
    attach_group_or_flat(
        group_key="plan_replay_cache_config",
        group_payload=plan_replay_cache_group,
        flat_payload={
            "plan_replay_cache_enabled": plan_replay_cache_enabled,
            "plan_replay_cache_path": plan_replay_cache_path,
        },
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
