"""Resolve retrieval/index/repomap/lsp config sections."""

from __future__ import annotations

from typing import Any

import click
from click.core import ParameterSource

from ace_lite.cli_app.config_resolve_helpers import (
    _resolve_from_config,
    _resolve_from_layers,
)
from ace_lite.cli_app.params import (
    _resolve_retrieval_preset,
    _to_adaptive_router_mode,
    _to_bool,
    _to_candidate_ranker,
    _to_csv_languages,
    _to_embedding_provider,
    _to_float,
    _to_float_dict,
    _to_hybrid_fusion_mode,
    _to_int,
    _to_remote_slot_policy_mode,
    _to_slot_allowlist,
    _to_string_list,
    parse_lsp_command_options,
    parse_lsp_commands_from_config,
)
from ace_lite.config import config_get
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.scoring_config import (
    BM25_B,
    BM25_K1,
    BM25_PATH_PRIOR_FACTOR,
    BM25_SCORE_SCALE,
    BM25_SHORTLIST_FACTOR,
    BM25_SHORTLIST_MIN,
    HEUR_CONTENT_CAP,
    HEUR_CONTENT_IMPORT_FACTOR,
    HEUR_CONTENT_SYMBOL_FACTOR,
    HEUR_DEPTH_BASE,
    HEUR_DEPTH_FACTOR,
    HEUR_IMPORT_CAP,
    HEUR_IMPORT_FACTOR,
    HEUR_MODULE_CONTAINS,
    HEUR_MODULE_EXACT,
    HEUR_MODULE_TAIL,
    HEUR_PATH_CONTAINS,
    HEUR_PATH_EXACT,
    HEUR_SYMBOL_EXACT,
    HEUR_SYMBOL_PARTIAL_CAP,
    HEUR_SYMBOL_PARTIAL_FACTOR,
    HYBRID_SHORTLIST_FACTOR,
    HYBRID_SHORTLIST_MIN,
)


def resolve_retrieval_and_lsp_config(
    *,
    ctx: click.Context,
    config: dict[str, Any],
    namespace: str,
    retrieval_preset: str,
    adaptive_router_enabled: bool,
    adaptive_router_mode: str,
    adaptive_router_model_path: str,
    adaptive_router_state_path: str,
    adaptive_router_arm_set: str,
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
    hybrid_re2_bm25_weight: float = 0.0,
    hybrid_re2_heuristic_weight: float = 0.0,
    hybrid_re2_coverage_weight: float = 0.0,
    hybrid_re2_combined_scale: float = 0.0,
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
    languages: str,
    index_cache_path: str,
    index_incremental: bool,
    conventions_files: tuple[str, ...],
    plugins_enabled: bool,
    remote_slot_policy_mode: str,
    remote_slot_allowlist: str,
    repomap_enabled: bool,
    repomap_top_k: int,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
    lsp_enabled: bool,
    lsp_top_n: int,
    lsp_cmds: tuple[str, ...],
    lsp_xref_enabled: bool,
    lsp_xref_top_n: int,
    lsp_time_budget_ms: int,
    lsp_xref_cmds: tuple[str, ...],
) -> dict[str, Any]:
    def scoped(*rest: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return (namespace, *rest), (*rest,)

    def section_paths(
        section: str,
        *rest: str,
        flat_key: str | None = None,
    ) -> list[tuple[str, ...]]:
        paths = [
            (namespace, section, *rest),
            (section, *rest),
        ]
        if flat_key:
            paths.extend(
                [
                    (namespace, flat_key),
                    (flat_key,),
                ]
            )
        return paths

    def retrieval_paths(*rest: str) -> list[tuple[str, ...]]:
        return [
            (namespace, "retrieval", *rest),
            ("retrieval", *rest),
            (namespace, *rest),
            (*rest,),
        ]

    def first_config_value(*paths: tuple[str, ...]) -> Any:
        for path in paths:
            candidate = config_get(config, *path, default=None)
            if candidate is not None:
                return candidate
        return None

    preset_payload = _resolve_retrieval_preset(retrieval_preset)
    adaptive_router_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="adaptive_router_enabled",
        current=adaptive_router_enabled,
        config=config,
        paths=[
            (namespace, "adaptive_router", "enabled"),
            (namespace, "adaptive_router_enabled"),
            ("adaptive_router", "enabled"),
            ("adaptive_router_enabled",),
        ],
        transform=_to_bool,
    )
    adaptive_router_mode = _resolve_from_config(
        ctx=ctx,
        param_name="adaptive_router_mode",
        current=adaptive_router_mode,
        config=config,
        paths=[
            (namespace, "adaptive_router", "mode"),
            (namespace, "adaptive_router_mode"),
            ("adaptive_router", "mode"),
            ("adaptive_router_mode",),
        ],
        transform=_to_adaptive_router_mode,
    )
    adaptive_router_model_path = _resolve_from_config(
        ctx=ctx,
        param_name="adaptive_router_model_path",
        current=adaptive_router_model_path,
        config=config,
        paths=[
            (namespace, "adaptive_router", "model_path"),
            (namespace, "adaptive_router_model_path"),
            ("adaptive_router", "model_path"),
            ("adaptive_router_model_path",),
        ],
        transform=str,
    )
    adaptive_router_state_path = _resolve_from_config(
        ctx=ctx,
        param_name="adaptive_router_state_path",
        current=adaptive_router_state_path,
        config=config,
        paths=[
            (namespace, "adaptive_router", "state_path"),
            (namespace, "adaptive_router_state_path"),
            ("adaptive_router", "state_path"),
            ("adaptive_router_state_path",),
        ],
        transform=str,
    )
    adaptive_router_arm_set = _resolve_from_config(
        ctx=ctx,
        param_name="adaptive_router_arm_set",
        current=adaptive_router_arm_set,
        config=config,
        paths=[
            (namespace, "adaptive_router", "arm_set"),
            (namespace, "adaptive_router_arm_set"),
            ("adaptive_router", "arm_set"),
            ("adaptive_router_arm_set",),
        ],
        transform=str,
    )
    adaptive_router_online_bandit_enabled = first_config_value(
        (namespace, "adaptive_router", "online_bandit", "enabled"),
        (namespace, "adaptive_router_online_bandit_enabled"),
        ("adaptive_router", "online_bandit", "enabled"),
        ("adaptive_router_online_bandit_enabled",),
    )
    if adaptive_router_online_bandit_enabled is not None:
        adaptive_router_online_bandit_enabled = _to_bool(
            adaptive_router_online_bandit_enabled
        )
    adaptive_router_online_bandit_experiment_enabled = first_config_value(
        (namespace, "adaptive_router", "online_bandit", "experiment_enabled"),
        (namespace, "adaptive_router_online_bandit_experiment_enabled"),
        ("adaptive_router", "online_bandit", "experiment_enabled"),
        ("adaptive_router_online_bandit_experiment_enabled",),
    )
    if adaptive_router_online_bandit_experiment_enabled is not None:
        adaptive_router_online_bandit_experiment_enabled = _to_bool(
            adaptive_router_online_bandit_experiment_enabled
        )
    top_k_files = _resolve_from_layers(
        ctx=ctx,
        param_name="top_k_files",
        current=top_k_files,
        preset=preset_payload,
        preset_key="top_k_files",
        config=config,
        paths=retrieval_paths("top_k_files"),
        transform=_to_int,
    )
    min_candidate_score = _resolve_from_layers(
        ctx=ctx,
        param_name="min_candidate_score",
        current=min_candidate_score,
        preset=preset_payload,
        preset_key="min_candidate_score",
        config=config,
        paths=retrieval_paths("min_candidate_score"),
        transform=_to_int,
    )
    candidate_relative_threshold = _resolve_from_layers(
        ctx=ctx,
        param_name="candidate_relative_threshold",
        current=candidate_relative_threshold,
        preset=preset_payload,
        preset_key="candidate_relative_threshold",
        config=config,
        paths=retrieval_paths("candidate_relative_threshold"),
        transform=_to_float,
    )
    candidate_ranker = _resolve_from_layers(
        ctx=ctx,
        param_name="candidate_ranker",
        current=candidate_ranker,
        preset=preset_payload,
        preset_key="candidate_ranker",
        config=config,
        paths=retrieval_paths("candidate_ranker"),
        transform=_to_candidate_ranker,
    )
    exact_search_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="exact_search_enabled",
        current=exact_search_enabled,
        config=config,
        paths=retrieval_paths("exact_search_enabled")
        + [
            (namespace, "exact_search"),
            ("exact_search",),
        ],
        transform=_to_bool,
    )
    deterministic_refine_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="deterministic_refine_enabled",
        current=deterministic_refine_enabled,
        config=config,
        paths=retrieval_paths("deterministic_refine_enabled")
        + [
            (namespace, "deterministic_refine"),
            ("deterministic_refine",),
        ],
        transform=_to_bool,
    )
    exact_search_time_budget_ms = _resolve_from_config(
        ctx=ctx,
        param_name="exact_search_time_budget_ms",
        current=exact_search_time_budget_ms,
        config=config,
        paths=retrieval_paths("exact_search_time_budget_ms")
        + [
            (namespace, "exact_search_time_budget"),
            ("exact_search_time_budget",),
        ],
        transform=_to_int,
    )
    exact_search_max_paths = _resolve_from_config(
        ctx=ctx,
        param_name="exact_search_max_paths",
        current=exact_search_max_paths,
        config=config,
        paths=retrieval_paths("exact_search_max_paths")
        + [
            (namespace, "exact_search_max_files"),
            ("exact_search_max_files",),
        ],
        transform=_to_int,
    )
    hybrid_re2_fusion_mode = _resolve_from_layers(
        ctx=ctx,
        param_name="hybrid_re2_fusion_mode",
        current=hybrid_re2_fusion_mode,
        preset=preset_payload,
        preset_key="hybrid_re2_fusion_mode",
        config=config,
        paths=retrieval_paths("hybrid_re2_fusion_mode"),
        transform=_to_hybrid_fusion_mode,
    )
    hybrid_re2_rrf_k = _resolve_from_layers(
        ctx=ctx,
        param_name="hybrid_re2_rrf_k",
        current=hybrid_re2_rrf_k,
        preset=preset_payload,
        preset_key="hybrid_re2_rrf_k",
        config=config,
        paths=retrieval_paths("hybrid_re2_rrf_k"),
        transform=_to_int,
    )
    hybrid_re2_shortlist_min = _resolve_from_config(
        ctx=ctx,
        param_name="hybrid_re2_shortlist_min",
        current=HYBRID_SHORTLIST_MIN,
        config=config,
        paths=retrieval_paths("hybrid_re2_shortlist_min"),
        transform=_to_int,
    )
    hybrid_re2_shortlist_factor = _resolve_from_config(
        ctx=ctx,
        param_name="hybrid_re2_shortlist_factor",
        current=HYBRID_SHORTLIST_FACTOR,
        config=config,
        paths=retrieval_paths("hybrid_re2_shortlist_factor"),
        transform=_to_int,
    )
    hybrid_re2_bm25_weight = _resolve_from_config(
        ctx=ctx,
        param_name="hybrid_re2_bm25_weight",
        current=hybrid_re2_bm25_weight,
        config=config,
        paths=retrieval_paths("hybrid_re2_bm25_weight"),
        transform=_to_float,
    )
    hybrid_re2_heuristic_weight = _resolve_from_config(
        ctx=ctx,
        param_name="hybrid_re2_heuristic_weight",
        current=hybrid_re2_heuristic_weight,
        config=config,
        paths=retrieval_paths("hybrid_re2_heuristic_weight"),
        transform=_to_float,
    )
    hybrid_re2_coverage_weight = _resolve_from_config(
        ctx=ctx,
        param_name="hybrid_re2_coverage_weight",
        current=hybrid_re2_coverage_weight,
        config=config,
        paths=retrieval_paths("hybrid_re2_coverage_weight"),
        transform=_to_float,
    )
    hybrid_re2_combined_scale = _resolve_from_config(
        ctx=ctx,
        param_name="hybrid_re2_combined_scale",
        current=hybrid_re2_combined_scale,
        config=config,
        paths=retrieval_paths("hybrid_re2_combined_scale"),
        transform=_to_float,
    )
    bm25_k1 = _resolve_from_config(
        ctx=ctx,
        param_name="bm25_k1",
        current=BM25_K1,
        config=config,
        paths=retrieval_paths("bm25_k1"),
        transform=_to_float,
    )
    bm25_b = _resolve_from_config(
        ctx=ctx,
        param_name="bm25_b",
        current=BM25_B,
        config=config,
        paths=retrieval_paths("bm25_b"),
        transform=_to_float,
    )
    bm25_score_scale = _resolve_from_config(
        ctx=ctx,
        param_name="bm25_score_scale",
        current=BM25_SCORE_SCALE,
        config=config,
        paths=retrieval_paths("bm25_score_scale"),
        transform=_to_float,
    )
    bm25_path_prior_factor = _resolve_from_config(
        ctx=ctx,
        param_name="bm25_path_prior_factor",
        current=BM25_PATH_PRIOR_FACTOR,
        config=config,
        paths=retrieval_paths("bm25_path_prior_factor"),
        transform=_to_float,
    )
    bm25_shortlist_min = _resolve_from_config(
        ctx=ctx,
        param_name="bm25_shortlist_min",
        current=BM25_SHORTLIST_MIN,
        config=config,
        paths=retrieval_paths("bm25_shortlist_min"),
        transform=_to_int,
    )
    bm25_shortlist_factor = _resolve_from_config(
        ctx=ctx,
        param_name="bm25_shortlist_factor",
        current=BM25_SHORTLIST_FACTOR,
        config=config,
        paths=retrieval_paths("bm25_shortlist_factor"),
        transform=_to_int,
    )
    heur_path_exact = _resolve_from_config(
        ctx=ctx,
        param_name="heur_path_exact",
        current=HEUR_PATH_EXACT,
        config=config,
        paths=retrieval_paths("heur_path_exact"),
        transform=_to_float,
    )
    heur_path_contains = _resolve_from_config(
        ctx=ctx,
        param_name="heur_path_contains",
        current=HEUR_PATH_CONTAINS,
        config=config,
        paths=retrieval_paths("heur_path_contains"),
        transform=_to_float,
    )
    heur_module_exact = _resolve_from_config(
        ctx=ctx,
        param_name="heur_module_exact",
        current=HEUR_MODULE_EXACT,
        config=config,
        paths=retrieval_paths("heur_module_exact"),
        transform=_to_float,
    )
    heur_module_tail = _resolve_from_config(
        ctx=ctx,
        param_name="heur_module_tail",
        current=HEUR_MODULE_TAIL,
        config=config,
        paths=retrieval_paths("heur_module_tail"),
        transform=_to_float,
    )
    heur_module_contains = _resolve_from_config(
        ctx=ctx,
        param_name="heur_module_contains",
        current=HEUR_MODULE_CONTAINS,
        config=config,
        paths=retrieval_paths("heur_module_contains"),
        transform=_to_float,
    )
    heur_symbol_exact = _resolve_from_config(
        ctx=ctx,
        param_name="heur_symbol_exact",
        current=HEUR_SYMBOL_EXACT,
        config=config,
        paths=retrieval_paths("heur_symbol_exact"),
        transform=_to_float,
    )
    heur_symbol_partial_factor = _resolve_from_config(
        ctx=ctx,
        param_name="heur_symbol_partial_factor",
        current=HEUR_SYMBOL_PARTIAL_FACTOR,
        config=config,
        paths=retrieval_paths("heur_symbol_partial_factor"),
        transform=_to_float,
    )
    heur_symbol_partial_cap = _resolve_from_config(
        ctx=ctx,
        param_name="heur_symbol_partial_cap",
        current=HEUR_SYMBOL_PARTIAL_CAP,
        config=config,
        paths=retrieval_paths("heur_symbol_partial_cap"),
        transform=_to_float,
    )
    heur_import_factor = _resolve_from_config(
        ctx=ctx,
        param_name="heur_import_factor",
        current=HEUR_IMPORT_FACTOR,
        config=config,
        paths=retrieval_paths("heur_import_factor"),
        transform=_to_float,
    )
    heur_import_cap = _resolve_from_config(
        ctx=ctx,
        param_name="heur_import_cap",
        current=HEUR_IMPORT_CAP,
        config=config,
        paths=retrieval_paths("heur_import_cap"),
        transform=_to_float,
    )
    heur_content_symbol_factor = _resolve_from_config(
        ctx=ctx,
        param_name="heur_content_symbol_factor",
        current=HEUR_CONTENT_SYMBOL_FACTOR,
        config=config,
        paths=retrieval_paths("heur_content_symbol_factor"),
        transform=_to_float,
    )
    heur_content_import_factor = _resolve_from_config(
        ctx=ctx,
        param_name="heur_content_import_factor",
        current=HEUR_CONTENT_IMPORT_FACTOR,
        config=config,
        paths=retrieval_paths("heur_content_import_factor"),
        transform=_to_float,
    )
    heur_content_cap = _resolve_from_config(
        ctx=ctx,
        param_name="heur_content_cap",
        current=HEUR_CONTENT_CAP,
        config=config,
        paths=retrieval_paths("heur_content_cap"),
        transform=_to_float,
    )
    heur_depth_base = _resolve_from_config(
        ctx=ctx,
        param_name="heur_depth_base",
        current=HEUR_DEPTH_BASE,
        config=config,
        paths=retrieval_paths("heur_depth_base"),
        transform=_to_float,
    )
    heur_depth_factor = _resolve_from_config(
        ctx=ctx,
        param_name="heur_depth_factor",
        current=HEUR_DEPTH_FACTOR,
        config=config,
        paths=retrieval_paths("heur_depth_factor"),
        transform=_to_float,
    )
    embedding_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_enabled",
        current=embedding_enabled,
        config=config,
        paths=[
            (namespace, "embeddings", "enabled"),
            ("embeddings", "enabled"),
            (namespace, "embedding_enabled"),
            ("embedding_enabled",),
        ],
        transform=_to_bool,
    )
    embedding_provider = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_provider",
        current=embedding_provider,
        config=config,
        paths=[
            (namespace, "embeddings", "provider"),
            ("embeddings", "provider"),
            (namespace, "embedding_provider"),
            ("embedding_provider",),
        ],
        transform=_to_embedding_provider,
    )
    embedding_model = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_model",
        current=embedding_model,
        config=config,
        paths=[
            (namespace, "embeddings", "model"),
            ("embeddings", "model"),
            (namespace, "embedding_model"),
            ("embedding_model",),
        ],
        transform=str,
    )
    embedding_dimension = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_dimension",
        current=embedding_dimension,
        config=config,
        paths=[
            (namespace, "embeddings", "dimension"),
            ("embeddings", "dimension"),
            (namespace, "embedding_dimension"),
            ("embedding_dimension",),
        ],
        transform=_to_int,
    )
    embedding_index_path = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_index_path",
        current=embedding_index_path,
        config=config,
        paths=[
            (namespace, "embeddings", "index_path"),
            ("embeddings", "index_path"),
            (namespace, "embedding_index_path"),
            ("embedding_index_path",),
        ],
        transform=str,
    )
    embedding_rerank_pool = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_rerank_pool",
        current=embedding_rerank_pool,
        config=config,
        paths=[
            (namespace, "embeddings", "rerank_pool"),
            ("embeddings", "rerank_pool"),
            (namespace, "embedding_rerank_pool"),
            ("embedding_rerank_pool",),
        ],
        transform=_to_int,
    )
    embedding_lexical_weight = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_lexical_weight",
        current=embedding_lexical_weight,
        config=config,
        paths=[
            (namespace, "embeddings", "lexical_weight"),
            ("embeddings", "lexical_weight"),
            (namespace, "embedding_lexical_weight"),
            ("embedding_lexical_weight",),
        ],
        transform=_to_float,
    )
    embedding_semantic_weight = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_semantic_weight",
        current=embedding_semantic_weight,
        config=config,
        paths=[
            (namespace, "embeddings", "semantic_weight"),
            ("embeddings", "semantic_weight"),
            (namespace, "embedding_semantic_weight"),
            ("embedding_semantic_weight",),
        ],
        transform=_to_float,
    )
    embedding_min_similarity = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_min_similarity",
        current=embedding_min_similarity,
        config=config,
        paths=[
            (namespace, "embeddings", "min_similarity"),
            ("embeddings", "min_similarity"),
            (namespace, "embedding_min_similarity"),
            ("embedding_min_similarity",),
        ],
        transform=_to_float,
    )
    embedding_fail_open = _resolve_from_config(
        ctx=ctx,
        param_name="embedding_fail_open",
        current=embedding_fail_open,
        config=config,
        paths=[
            (namespace, "embeddings", "fail_open"),
            ("embeddings", "fail_open"),
            (namespace, "embedding_fail_open"),
            ("embedding_fail_open",),
        ],
        transform=_to_bool,
    )

    languages = _resolve_from_config(
        ctx=ctx,
        param_name="languages",
        current=languages,
        config=config,
        paths=section_paths("index", "languages", flat_key="languages"),
        transform=_to_csv_languages,
    )
    index_cache_path = _resolve_from_config(
        ctx=ctx,
        param_name="index_cache_path",
        current=index_cache_path,
        config=config,
        paths=section_paths("index", "cache_path", flat_key="index_cache_path"),
        transform=str,
    )
    index_incremental = _resolve_from_config(
        ctx=ctx,
        param_name="index_incremental",
        current=index_incremental,
        config=config,
        paths=section_paths("index", "incremental", flat_key="index_incremental"),
        transform=_to_bool,
    )
    conventions_files = _resolve_from_config(
        ctx=ctx,
        param_name="conventions_files",
        current=conventions_files,
        config=config,
        paths=section_paths(
            "index",
            "conventions_files",
            flat_key="conventions_files",
        ),
        transform=_to_string_list,
    )
    plugins_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="plugins_enabled",
        current=plugins_enabled,
        config=config,
        paths=section_paths("plugins", "enabled", flat_key="plugins_enabled"),
        transform=_to_bool,
    )

    remote_slot_policy_paths = section_paths(
        "plugins",
        "remote_slot_policy_mode",
        flat_key="remote_slot_policy_mode",
    )
    if (
        ctx.get_parameter_source("remote_slot_policy_mode")
        == ParameterSource.COMMANDLINE
    ):
        remote_slot_policy_mode = _to_remote_slot_policy_mode(remote_slot_policy_mode)
    else:
        resolved_remote_mode: Any = remote_slot_policy_mode
        for path in remote_slot_policy_paths:
            candidate = config_get(config, *path, default=None)
            if candidate is None:
                continue
            resolved_remote_mode = candidate
            break
        remote_slot_policy_mode = _to_remote_slot_policy_mode(resolved_remote_mode)

    remote_slot_allowlist_paths = section_paths(
        "plugins",
        "remote_slot_allowlist",
        flat_key="remote_slot_allowlist",
    )
    if ctx.get_parameter_source("remote_slot_allowlist") == ParameterSource.COMMANDLINE:
        remote_slot_allowlist = ",".join(_to_slot_allowlist(remote_slot_allowlist))
    else:
        resolved_allowlist: Any = remote_slot_allowlist
        for path in remote_slot_allowlist_paths:
            candidate = config_get(config, *path, default=None)
            if candidate is None:
                continue
            resolved_allowlist = candidate
            break
        remote_slot_allowlist = ",".join(_to_slot_allowlist(resolved_allowlist))

    repomap_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="repomap_enabled",
        current=repomap_enabled,
        config=config,
        paths=section_paths("repomap", "enabled", flat_key="repomap_enabled"),
        transform=_to_bool,
    )
    repomap_top_k = _resolve_from_config(
        ctx=ctx,
        param_name="repomap_top_k",
        current=repomap_top_k,
        config=config,
        paths=section_paths("repomap", "top_k", flat_key="repomap_top_k"),
        transform=_to_int,
    )
    repomap_neighbor_limit = _resolve_from_config(
        ctx=ctx,
        param_name="repomap_neighbor_limit",
        current=repomap_neighbor_limit,
        config=config,
        paths=section_paths(
            "repomap",
            "neighbor_limit",
            flat_key="repomap_neighbor_limit",
        ),
        transform=_to_int,
    )
    repomap_budget_tokens = _resolve_from_config(
        ctx=ctx,
        param_name="repomap_budget_tokens",
        current=repomap_budget_tokens,
        config=config,
        paths=section_paths("repomap", "budget_tokens", flat_key="repomap_budget_tokens"),
        transform=_to_int,
    )
    repomap_ranking_profile = _resolve_from_config(
        ctx=ctx,
        param_name="repomap_ranking_profile",
        current=repomap_ranking_profile,
        config=config,
        paths=section_paths(
            "repomap",
            "ranking_profile",
            flat_key="repomap_ranking_profile",
        ),
        transform=lambda value: str(value).strip().lower(),
    )
    repomap_signal_weights = _resolve_from_layers(
        ctx=ctx,
        param_name="repomap_signal_weights",
        current=repomap_signal_weights,
        preset=preset_payload,
        preset_key="repomap_signal_weights",
        config=config,
        paths=section_paths(
            "repomap",
            "signal_weights",
            flat_key="repomap_signal_weights",
        ),
        transform=_to_float_dict,
    )

    lsp_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="lsp_enabled",
        current=lsp_enabled,
        config=config,
        paths=section_paths("lsp", "enabled", flat_key="lsp_enabled"),
        transform=_to_bool,
    )
    lsp_top_n = _resolve_from_config(
        ctx=ctx,
        param_name="lsp_top_n",
        current=lsp_top_n,
        config=config,
        paths=section_paths("lsp", "top_n", flat_key="lsp_top_n"),
        transform=_to_int,
    )
    lsp_xref_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="lsp_xref_enabled",
        current=lsp_xref_enabled,
        config=config,
        paths=section_paths("lsp", "xref_enabled", flat_key="lsp_xref_enabled"),
        transform=_to_bool,
    )
    lsp_xref_top_n = _resolve_from_config(
        ctx=ctx,
        param_name="lsp_xref_top_n",
        current=lsp_xref_top_n,
        config=config,
        paths=section_paths("lsp", "xref_top_n", flat_key="lsp_xref_top_n"),
        transform=_to_int,
    )
    lsp_time_budget_ms = _resolve_from_config(
        ctx=ctx,
        param_name="lsp_time_budget_ms",
        current=lsp_time_budget_ms,
        config=config,
        paths=section_paths("lsp", "time_budget_ms", flat_key="lsp_time_budget_ms"),
        transform=_to_int,
    )

    config_lsp_commands = parse_lsp_commands_from_config(
        first_config_value(
            (namespace, "lsp", "commands"),
            ("lsp", "commands"),
            (namespace, "lsp_commands"),
        )
    )
    default_lsp_commands = parse_lsp_command_options(lsp_cmds)
    lsp_commands = dict(config_lsp_commands)
    if default_lsp_commands:
        lsp_commands.update(default_lsp_commands)

    config_xref_commands = parse_lsp_commands_from_config(
        first_config_value(
            (namespace, "lsp", "xref_commands"),
            ("lsp", "xref_commands"),
            (namespace, "lsp_xref_commands"),
        )
    )
    default_xref_commands = parse_lsp_command_options(lsp_xref_cmds)
    lsp_xref_commands = dict(config_xref_commands)
    if default_xref_commands:
        lsp_xref_commands.update(default_xref_commands)

    adaptive_router_payload = {
        "enabled": bool(adaptive_router_enabled),
        "mode": _to_adaptive_router_mode(adaptive_router_mode),
        "model_path": str(adaptive_router_model_path).strip()
        or "context-map/router/model.json",
        "state_path": str(adaptive_router_state_path).strip()
        or "context-map/router/state.json",
        "arm_set": str(adaptive_router_arm_set).strip()
        or "retrieval_policy_v1",
    }
    if (
        adaptive_router_online_bandit_enabled is not None
        or adaptive_router_online_bandit_experiment_enabled is not None
    ):
        adaptive_router_payload["online_bandit"] = {
            "enabled": bool(adaptive_router_online_bandit_enabled)
        }
        if adaptive_router_online_bandit_experiment_enabled is not None:
            adaptive_router_payload["online_bandit"]["experiment_enabled"] = bool(
                adaptive_router_online_bandit_experiment_enabled
            )
    retrieval_payload = {
        "top_k_files": top_k_files,
        "min_candidate_score": min_candidate_score,
        "candidate_relative_threshold": candidate_relative_threshold,
        "candidate_ranker": candidate_ranker,
        "exact_search_enabled": bool(exact_search_enabled),
        "deterministic_refine_enabled": bool(deterministic_refine_enabled),
        "exact_search_time_budget_ms": max(0, int(exact_search_time_budget_ms)),
        "exact_search_max_paths": max(0, int(exact_search_max_paths)),
        "hybrid_re2_fusion_mode": hybrid_re2_fusion_mode,
        "hybrid_re2_rrf_k": max(1, int(hybrid_re2_rrf_k)),
        "hybrid_re2_shortlist_min": max(1, int(hybrid_re2_shortlist_min)),
        "hybrid_re2_shortlist_factor": max(1, int(hybrid_re2_shortlist_factor)),
        "hybrid_re2_bm25_weight": max(0.0, float(hybrid_re2_bm25_weight)),
        "hybrid_re2_heuristic_weight": max(0.0, float(hybrid_re2_heuristic_weight)),
        "hybrid_re2_coverage_weight": max(0.0, float(hybrid_re2_coverage_weight)),
        "hybrid_re2_combined_scale": max(0.0, float(hybrid_re2_combined_scale)),
        "bm25_k1": max(0.0, float(bm25_k1)),
        "bm25_b": max(0.0, float(bm25_b)),
        "bm25_score_scale": max(0.0, float(bm25_score_scale)),
        "bm25_path_prior_factor": max(0.0, float(bm25_path_prior_factor)),
        "bm25_shortlist_min": max(1, int(bm25_shortlist_min)),
        "bm25_shortlist_factor": max(1, int(bm25_shortlist_factor)),
        "heur_path_exact": max(0.0, float(heur_path_exact)),
        "heur_path_contains": max(0.0, float(heur_path_contains)),
        "heur_module_exact": max(0.0, float(heur_module_exact)),
        "heur_module_tail": max(0.0, float(heur_module_tail)),
        "heur_module_contains": max(0.0, float(heur_module_contains)),
        "heur_symbol_exact": max(0.0, float(heur_symbol_exact)),
        "heur_symbol_partial_factor": max(0.0, float(heur_symbol_partial_factor)),
        "heur_symbol_partial_cap": max(0.0, float(heur_symbol_partial_cap)),
        "heur_import_factor": max(0.0, float(heur_import_factor)),
        "heur_import_cap": max(0.0, float(heur_import_cap)),
        "heur_content_symbol_factor": max(0.0, float(heur_content_symbol_factor)),
        "heur_content_import_factor": max(0.0, float(heur_content_import_factor)),
        "heur_content_cap": max(0.0, float(heur_content_cap)),
        "heur_depth_base": max(0.0, float(heur_depth_base)),
        "heur_depth_factor": max(0.0, float(heur_depth_factor)),
        "adaptive_router": dict(adaptive_router_payload),
    }
    plugins_payload = {
        "enabled": bool(plugins_enabled),
        "remote_slot_policy_mode": _to_remote_slot_policy_mode(remote_slot_policy_mode),
        "remote_slot_allowlist": _to_slot_allowlist(remote_slot_allowlist),
    }
    repomap_payload = {
        "enabled": bool(repomap_enabled),
        "top_k": max(1, int(repomap_top_k)),
        "neighbor_limit": max(0, int(repomap_neighbor_limit)),
        "budget_tokens": max(1, int(repomap_budget_tokens)),
        "ranking_profile": str(repomap_ranking_profile).strip().lower(),
        "signal_weights": dict(repomap_signal_weights or {}),
    }
    lsp_payload = {
        "enabled": bool(lsp_enabled),
        "top_n": max(0, int(lsp_top_n)),
        "commands": dict(lsp_commands),
        "xref_enabled": bool(lsp_xref_enabled),
        "xref_top_n": max(0, int(lsp_xref_top_n)),
        "time_budget_ms": max(1, int(lsp_time_budget_ms)),
        "xref_commands": dict(lsp_xref_commands),
    }
    embeddings_payload = {
        "enabled": bool(embedding_enabled),
        "provider": str(embedding_provider).strip().lower() or "hash",
        "model": str(embedding_model).strip() or "hash-v1",
        "dimension": max(8, int(embedding_dimension)),
        "index_path": str(embedding_index_path),
        "rerank_pool": max(1, int(embedding_rerank_pool)),
        "lexical_weight": max(0.0, float(embedding_lexical_weight)),
        "semantic_weight": max(0.0, float(embedding_semantic_weight)),
        "min_similarity": float(embedding_min_similarity),
        "fail_open": bool(embedding_fail_open),
    }
    index_payload = {
        "languages": parse_language_csv(str(languages)),
        "cache_path": str(index_cache_path),
        "incremental": bool(index_incremental),
        "conventions_files": list(conventions_files),
    }

    return {
        "adaptive_router_enabled": adaptive_router_payload["enabled"],
        "adaptive_router_mode": adaptive_router_payload["mode"],
        "adaptive_router_model_path": adaptive_router_payload["model_path"],
        "adaptive_router_state_path": adaptive_router_payload["state_path"],
        "adaptive_router_arm_set": adaptive_router_payload["arm_set"],
        "adaptive_router_online_bandit_enabled": adaptive_router_online_bandit_enabled,
        "adaptive_router_online_bandit_experiment_enabled": (
            adaptive_router_online_bandit_experiment_enabled
        ),
        "adaptive_router": adaptive_router_payload,
        "top_k_files": retrieval_payload["top_k_files"],
        "min_candidate_score": retrieval_payload["min_candidate_score"],
        "candidate_relative_threshold": retrieval_payload["candidate_relative_threshold"],
        "candidate_ranker": retrieval_payload["candidate_ranker"],
        "exact_search_enabled": retrieval_payload["exact_search_enabled"],
        "deterministic_refine_enabled": retrieval_payload["deterministic_refine_enabled"],
        "exact_search_time_budget_ms": retrieval_payload["exact_search_time_budget_ms"],
        "exact_search_max_paths": retrieval_payload["exact_search_max_paths"],
        "hybrid_re2_fusion_mode": retrieval_payload["hybrid_re2_fusion_mode"],
        "hybrid_re2_rrf_k": retrieval_payload["hybrid_re2_rrf_k"],
        "hybrid_re2_bm25_weight": retrieval_payload["hybrid_re2_bm25_weight"],
        "hybrid_re2_heuristic_weight": retrieval_payload["hybrid_re2_heuristic_weight"],
        "hybrid_re2_coverage_weight": retrieval_payload["hybrid_re2_coverage_weight"],
        "hybrid_re2_combined_scale": retrieval_payload["hybrid_re2_combined_scale"],
        "retrieval": retrieval_payload,
        "embedding_enabled": embeddings_payload["enabled"],
        "embedding_provider": embeddings_payload["provider"],
        "embedding_model": embeddings_payload["model"],
        "embedding_dimension": embeddings_payload["dimension"],
        "embedding_index_path": embeddings_payload["index_path"],
        "embedding_rerank_pool": embeddings_payload["rerank_pool"],
        "embedding_lexical_weight": embeddings_payload["lexical_weight"],
        "embedding_semantic_weight": embeddings_payload["semantic_weight"],
        "embedding_min_similarity": embeddings_payload["min_similarity"],
        "embedding_fail_open": embeddings_payload["fail_open"],
        "embeddings": embeddings_payload,
        "languages": languages,
        "index_cache_path": index_payload["cache_path"],
        "index_incremental": index_payload["incremental"],
        "conventions_files": tuple(index_payload["conventions_files"]),
        "index": index_payload,
        "plugins_enabled": plugins_payload["enabled"],
        "remote_slot_policy_mode": plugins_payload["remote_slot_policy_mode"],
        "remote_slot_allowlist": list(plugins_payload["remote_slot_allowlist"]),
        "plugins": plugins_payload,
        "repomap_enabled": repomap_payload["enabled"],
        "repomap_top_k": repomap_payload["top_k"],
        "repomap_neighbor_limit": repomap_payload["neighbor_limit"],
        "repomap_budget_tokens": repomap_payload["budget_tokens"],
        "repomap_ranking_profile": repomap_payload["ranking_profile"],
        "repomap_signal_weights": dict(repomap_payload["signal_weights"]),
        "repomap": repomap_payload,
        "lsp_enabled": lsp_payload["enabled"],
        "lsp_top_n": lsp_payload["top_n"],
        "lsp_commands": dict(lsp_payload["commands"]),
        "lsp_xref_enabled": lsp_payload["xref_enabled"],
        "lsp_xref_top_n": lsp_payload["xref_top_n"],
        "lsp_time_budget_ms": lsp_payload["time_budget_ms"],
        "lsp_xref_commands": dict(lsp_payload["xref_commands"]),
        "lsp": lsp_payload,
    }
