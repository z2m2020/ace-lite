"""Resolve chunk/cochange/policy/test/scip/trace config sections."""

from __future__ import annotations

from typing import Any

import click

from ace_lite.cli_app.config_resolve_helpers import (
    _parameter_is_default,
    _resolve_from_config,
)
from ace_lite.cli_app.params import (
    _to_bool,
    _to_chunk_disclosure,
    _to_chunk_guard_mode,
    _to_float,
    _to_int,
    _to_retrieval_policy,
    _to_sbfl_metric,
    _to_scip_provider,
)
from ace_lite.scoring_config import (
    CHUNK_FILE_PRIOR_WEIGHT,
    CHUNK_MODULE_MATCH,
    CHUNK_PATH_MATCH,
    CHUNK_REFERENCE_CAP,
    CHUNK_REFERENCE_FACTOR,
    CHUNK_SIGNATURE_MATCH,
    CHUNK_SYMBOL_EXACT,
    CHUNK_SYMBOL_PARTIAL,
    SCIP_BASE_WEIGHT,
)


def resolve_quality_config(
    *,
    ctx: click.Context,
    config: dict[str, Any],
    namespace: str,
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
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    retrieval_policy: str,
    policy_version: str,
    junit_xml: str | None,
    coverage_json: str | None,
    sbfl_json: str | None,
    sbfl_metric: str,
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
    trace_export_enabled: bool,
    trace_export_path: str,
    trace_otlp_enabled: bool,
    trace_otlp_endpoint: str,
    trace_otlp_timeout_seconds: float,
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

    chunk_top_k = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_top_k",
        current=chunk_top_k,
        config=config,
        paths=[
            (namespace, "chunk", "top_k"),
            ("chunk", "top_k"),
            (namespace, "chunk_top_k"),
            ("chunk_top_k",),
        ],
        transform=_to_int,
    )
    chunk_per_file_limit = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_per_file_limit",
        current=chunk_per_file_limit,
        config=config,
        paths=[
            (namespace, "chunk", "per_file_limit"),
            ("chunk", "per_file_limit"),
            (namespace, "chunk_per_file_limit"),
            ("chunk_per_file_limit",),
        ],
        transform=_to_int,
    )
    chunk_disclosure = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_disclosure",
        current=chunk_disclosure,
        config=config,
        paths=[
            (namespace, "chunk", "disclosure"),
            ("chunk", "disclosure"),
            (namespace, "chunk_disclosure"),
            ("chunk_disclosure",),
        ],
        transform=_to_chunk_disclosure,
    )
    if _parameter_is_default(ctx, "chunk_disclosure") and not _parameter_is_default(
        ctx, "chunk_signature"
    ):
        chunk_disclosure = "signature" if chunk_signature else chunk_disclosure
    chunk_signature = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_signature",
        current=chunk_signature,
        config=config,
        paths=[
            (namespace, "chunk", "signature"),
            ("chunk", "signature"),
            (namespace, "chunk_signature"),
            ("chunk_signature",),
        ],
        transform=_to_bool,
    )
    chunk_snippet_max_lines = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_snippet_max_lines",
        current=chunk_snippet_max_lines,
        config=config,
        paths=[
            (namespace, "chunk", "snippet", "max_lines"),
            ("chunk", "snippet", "max_lines"),
            (namespace, "chunk_snippet_max_lines"),
            ("chunk_snippet_max_lines",),
        ],
        transform=_to_int,
    )
    chunk_snippet_max_chars = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_snippet_max_chars",
        current=chunk_snippet_max_chars,
        config=config,
        paths=[
            (namespace, "chunk", "snippet", "max_chars"),
            ("chunk", "snippet", "max_chars"),
            (namespace, "chunk_snippet_max_chars"),
            ("chunk_snippet_max_chars",),
        ],
        transform=_to_int,
    )
    chunk_token_budget = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_token_budget",
        current=chunk_token_budget,
        config=config,
        paths=[
            (namespace, "chunk", "token_budget"),
            ("chunk", "token_budget"),
            (namespace, "chunk_token_budget"),
            ("chunk_token_budget",),
        ],
        transform=_to_int,
    )
    chunk_topological_shield_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_topological_shield_enabled",
        current=False,
        config=config,
        paths=[
            (namespace, "chunk", "topological_shield", "enabled"),
            ("chunk", "topological_shield", "enabled"),
        ],
        transform=_to_bool,
    )
    chunk_topological_shield_mode = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_topological_shield_mode",
        current="off",
        config=config,
        paths=[
            (namespace, "chunk", "topological_shield", "mode"),
            ("chunk", "topological_shield", "mode"),
        ],
        transform=lambda value: str(value or "off").strip().lower() or "off",
    )
    chunk_topological_shield_max_attenuation = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_topological_shield_max_attenuation",
        current=0.6,
        config=config,
        paths=[
            (namespace, "chunk", "topological_shield", "max_attenuation"),
            ("chunk", "topological_shield", "max_attenuation"),
        ],
        transform=_to_float,
    )
    chunk_topological_shield_shared_parent_attenuation = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_topological_shield_shared_parent_attenuation",
        current=0.2,
        config=config,
        paths=[
            (
                namespace,
                "chunk",
                "topological_shield",
                "shared_parent_attenuation",
            ),
            ("chunk", "topological_shield", "shared_parent_attenuation"),
        ],
        transform=_to_float,
    )
    chunk_topological_shield_adjacency_attenuation = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_topological_shield_adjacency_attenuation",
        current=0.5,
        config=config,
        paths=[
            (namespace, "chunk", "topological_shield", "adjacency_attenuation"),
            ("chunk", "topological_shield", "adjacency_attenuation"),
        ],
        transform=_to_float,
    )
    chunk_topological_shield_mode = (
        str(chunk_topological_shield_mode).strip().lower() or "off"
    )
    if chunk_topological_shield_mode not in {"off", "report_only", "enforce"}:
        chunk_topological_shield_mode = "off"
    if bool(chunk_topological_shield_enabled) and chunk_topological_shield_mode == "off":
        chunk_topological_shield_mode = "report_only"
    chunk_topological_shield_enabled = chunk_topological_shield_mode != "off"
    chunk_topological_shield_max_attenuation = max(
        0.0, min(1.0, float(chunk_topological_shield_max_attenuation))
    )
    chunk_topological_shield_shared_parent_attenuation = max(
        0.0,
        min(
            float(chunk_topological_shield_max_attenuation),
            float(chunk_topological_shield_shared_parent_attenuation),
        ),
    )
    chunk_topological_shield_adjacency_attenuation = max(
        float(chunk_topological_shield_shared_parent_attenuation),
        min(
            float(chunk_topological_shield_max_attenuation),
            float(chunk_topological_shield_adjacency_attenuation),
        ),
    )
    chunk_guard_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_enabled",
        current=chunk_guard_enabled,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "enabled"),
            ("chunk", "guard", "enabled"),
            (namespace, "chunk_guard_enabled"),
            ("chunk_guard_enabled",),
        ],
        transform=_to_bool,
    )
    chunk_guard_mode = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_mode",
        current=chunk_guard_mode,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "mode"),
            ("chunk", "guard", "mode"),
            (namespace, "chunk_guard_mode"),
            ("chunk_guard_mode",),
        ],
        transform=_to_chunk_guard_mode,
    )
    chunk_guard_lambda_penalty = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_lambda_penalty",
        current=chunk_guard_lambda_penalty,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "lambda_penalty"),
            ("chunk", "guard", "lambda_penalty"),
            (namespace, "chunk_guard_lambda_penalty"),
            ("chunk_guard_lambda_penalty",),
        ],
        transform=_to_float,
    )
    chunk_guard_min_pool = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_min_pool",
        current=chunk_guard_min_pool,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "min_pool"),
            ("chunk", "guard", "min_pool"),
            (namespace, "chunk_guard_min_pool"),
            ("chunk_guard_min_pool",),
        ],
        transform=_to_int,
    )
    chunk_guard_max_pool = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_max_pool",
        current=chunk_guard_max_pool,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "max_pool"),
            ("chunk", "guard", "max_pool"),
            (namespace, "chunk_guard_max_pool"),
            ("chunk_guard_max_pool",),
        ],
        transform=_to_int,
    )
    chunk_guard_min_marginal_utility = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_min_marginal_utility",
        current=chunk_guard_min_marginal_utility,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "min_marginal_utility"),
            ("chunk", "guard", "min_marginal_utility"),
            (namespace, "chunk_guard_min_marginal_utility"),
            ("chunk_guard_min_marginal_utility",),
        ],
        transform=_to_float,
    )
    chunk_guard_compatibility_min_overlap = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_guard_compatibility_min_overlap",
        current=chunk_guard_compatibility_min_overlap,
        config=config,
        paths=[
            (namespace, "chunk", "guard", "compatibility_min_overlap"),
            ("chunk", "guard", "compatibility_min_overlap"),
            (namespace, "chunk_guard_compatibility_min_overlap"),
            ("chunk_guard_compatibility_min_overlap",),
        ],
        transform=_to_float,
    )
    if bool(chunk_guard_enabled) and str(chunk_guard_mode).strip().lower() == "off":
        chunk_guard_mode = "report_only"
    chunk_guard_enabled = str(chunk_guard_mode).strip().lower() != "off"
    chunk_guard_min_pool = max(1, int(chunk_guard_min_pool))
    chunk_guard_max_pool = max(chunk_guard_min_pool, int(chunk_guard_max_pool))
    chunk_guard_lambda_penalty = max(0.0, float(chunk_guard_lambda_penalty))
    chunk_guard_min_marginal_utility = max(
        0.0, float(chunk_guard_min_marginal_utility)
    )
    chunk_guard_compatibility_min_overlap = max(
        0.0, min(1.0, float(chunk_guard_compatibility_min_overlap))
    )
    chunk_diversity_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_diversity_enabled",
        current=chunk_diversity_enabled,
        config=config,
        paths=list(scoped("chunk_diversity_enabled")),
        transform=_to_bool,
    )
    chunk_diversity_path_penalty = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_diversity_path_penalty",
        current=chunk_diversity_path_penalty,
        config=config,
        paths=list(scoped("chunk_diversity_path_penalty")),
        transform=_to_float,
    )
    chunk_diversity_symbol_family_penalty = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_diversity_symbol_family_penalty",
        current=chunk_diversity_symbol_family_penalty,
        config=config,
        paths=list(scoped("chunk_diversity_symbol_family_penalty")),
        transform=_to_float,
    )
    chunk_diversity_kind_penalty = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_diversity_kind_penalty",
        current=chunk_diversity_kind_penalty,
        config=config,
        paths=list(scoped("chunk_diversity_kind_penalty")),
        transform=_to_float,
    )
    chunk_diversity_locality_penalty = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_diversity_locality_penalty",
        current=chunk_diversity_locality_penalty,
        config=config,
        paths=list(scoped("chunk_diversity_locality_penalty")),
        transform=_to_float,
    )
    chunk_diversity_locality_window = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_diversity_locality_window",
        current=chunk_diversity_locality_window,
        config=config,
        paths=list(scoped("chunk_diversity_locality_window")),
        transform=_to_int,
    )
    chunk_file_prior_weight = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_file_prior_weight",
        current=CHUNK_FILE_PRIOR_WEIGHT,
        config=config,
        paths=section_paths("chunk", "file_prior_weight", flat_key="chunk_file_prior_weight"),
        transform=_to_float,
    )
    chunk_path_match = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_path_match",
        current=CHUNK_PATH_MATCH,
        config=config,
        paths=section_paths("chunk", "path_match", flat_key="chunk_path_match"),
        transform=_to_float,
    )
    chunk_module_match = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_module_match",
        current=CHUNK_MODULE_MATCH,
        config=config,
        paths=section_paths("chunk", "module_match", flat_key="chunk_module_match"),
        transform=_to_float,
    )
    chunk_symbol_exact = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_symbol_exact",
        current=CHUNK_SYMBOL_EXACT,
        config=config,
        paths=section_paths("chunk", "symbol_exact", flat_key="chunk_symbol_exact"),
        transform=_to_float,
    )
    chunk_symbol_partial = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_symbol_partial",
        current=CHUNK_SYMBOL_PARTIAL,
        config=config,
        paths=section_paths("chunk", "symbol_partial", flat_key="chunk_symbol_partial"),
        transform=_to_float,
    )
    chunk_signature_match = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_signature_match",
        current=CHUNK_SIGNATURE_MATCH,
        config=config,
        paths=section_paths("chunk", "signature_match", flat_key="chunk_signature_match"),
        transform=_to_float,
    )
    chunk_reference_factor = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_reference_factor",
        current=CHUNK_REFERENCE_FACTOR,
        config=config,
        paths=section_paths("chunk", "reference_factor", flat_key="chunk_reference_factor"),
        transform=_to_float,
    )
    chunk_reference_cap = _resolve_from_config(
        ctx=ctx,
        param_name="chunk_reference_cap",
        current=CHUNK_REFERENCE_CAP,
        config=config,
        paths=section_paths("chunk", "reference_cap", flat_key="chunk_reference_cap"),
        transform=_to_float,
    )
    cochange_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="cochange_enabled",
        current=cochange_enabled,
        config=config,
        paths=section_paths("cochange", "enabled", flat_key="cochange_enabled"),
        transform=_to_bool,
    )
    cochange_cache_path = _resolve_from_config(
        ctx=ctx,
        param_name="cochange_cache_path",
        current=cochange_cache_path,
        config=config,
        paths=section_paths("cochange", "cache_path", flat_key="cochange_cache_path"),
        transform=str,
    )
    cochange_lookback_commits = _resolve_from_config(
        ctx=ctx,
        param_name="cochange_lookback_commits",
        current=cochange_lookback_commits,
        config=config,
        paths=section_paths(
            "cochange",
            "lookback_commits",
            flat_key="cochange_lookback_commits",
        ),
        transform=_to_int,
    )
    cochange_half_life_days = _resolve_from_config(
        ctx=ctx,
        param_name="cochange_half_life_days",
        current=cochange_half_life_days,
        config=config,
        paths=section_paths(
            "cochange",
            "half_life_days",
            flat_key="cochange_half_life_days",
        ),
        transform=_to_float,
    )
    cochange_top_neighbors = _resolve_from_config(
        ctx=ctx,
        param_name="cochange_top_neighbors",
        current=cochange_top_neighbors,
        config=config,
        paths=section_paths(
            "cochange",
            "top_neighbors",
            flat_key="cochange_top_neighbors",
        ),
        transform=_to_int,
    )
    cochange_boost_weight = _resolve_from_config(
        ctx=ctx,
        param_name="cochange_boost_weight",
        current=cochange_boost_weight,
        config=config,
        paths=section_paths(
            "cochange",
            "boost_weight",
            flat_key="cochange_boost_weight",
        ),
        transform=_to_float,
    )
    retrieval_policy = _resolve_from_config(
        ctx=ctx,
        param_name="retrieval_policy",
        current=retrieval_policy,
        config=config,
        paths=list(scoped("retrieval_policy")),
        transform=_to_retrieval_policy,
    )
    policy_version = _resolve_from_config(
        ctx=ctx,
        param_name="policy_version",
        current=policy_version,
        config=config,
        paths=list(scoped("policy_version")),
        transform=str,
    )
    junit_xml = _resolve_from_config(
        ctx=ctx,
        param_name="junit_xml",
        current=junit_xml,
        config=config,
        paths=[
            (namespace, "tests", "junit_xml"),
            ("tests", "junit_xml"),
            (namespace, "failed_test_report"),
            ("failed_test_report",),
            (namespace, "junit_xml"),
            ("junit_xml",),
        ],
        transform=str,
    )
    coverage_json = _resolve_from_config(
        ctx=ctx,
        param_name="coverage_json",
        current=coverage_json,
        config=config,
        paths=section_paths("tests", "coverage_json", flat_key="coverage_json"),
        transform=str,
    )
    sbfl_json = _resolve_from_config(
        ctx=ctx,
        param_name="sbfl_json",
        current=sbfl_json,
        config=config,
        paths=[
            (namespace, "tests", "sbfl", "json_path"),
            ("tests", "sbfl", "json_path"),
            (namespace, "tests", "sbfl", "json"),
            ("tests", "sbfl", "json"),
            (namespace, "tests", "sbfl_json"),
            ("tests", "sbfl_json"),
            (namespace, "sbfl", "json_path"),
            ("sbfl", "json_path"),
            (namespace, "sbfl", "json"),
            ("sbfl", "json"),
            (namespace, "sbfl_json"),
            ("sbfl_json",),
        ],
        transform=str,
    )
    sbfl_metric = _resolve_from_config(
        ctx=ctx,
        param_name="sbfl_metric",
        current=sbfl_metric,
        config=config,
        paths=[
            (namespace, "tests", "sbfl", "metric"),
            ("tests", "sbfl", "metric"),
            (namespace, "tests", "sbfl_metric"),
            ("tests", "sbfl_metric"),
            (namespace, "sbfl", "metric"),
            ("sbfl", "metric"),
            (namespace, "sbfl_metric"),
            ("sbfl_metric",),
        ],
        transform=_to_sbfl_metric,
    )
    scip_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="scip_enabled",
        current=scip_enabled,
        config=config,
        paths=section_paths("scip", "enabled", flat_key="scip_enabled"),
        transform=_to_bool,
    )
    scip_index_path = _resolve_from_config(
        ctx=ctx,
        param_name="scip_index_path",
        current=scip_index_path,
        config=config,
        paths=section_paths("scip", "index_path", flat_key="scip_index_path"),
        transform=str,
    )
    scip_provider = _resolve_from_config(
        ctx=ctx,
        param_name="scip_provider",
        current=scip_provider,
        config=config,
        paths=section_paths("scip", "provider", flat_key="scip_provider"),
        transform=_to_scip_provider,
    )
    scip_generate_fallback = _resolve_from_config(
        ctx=ctx,
        param_name="scip_generate_fallback",
        current=scip_generate_fallback,
        config=config,
        paths=section_paths(
            "scip",
            "generate_fallback",
            flat_key="scip_generate_fallback",
        ),
        transform=_to_bool,
    )
    scip_base_weight = _resolve_from_config(
        ctx=ctx,
        param_name="scip_base_weight",
        current=SCIP_BASE_WEIGHT,
        config=config,
        paths=section_paths("scip", "base_weight", flat_key="scip_base_weight"),
        transform=_to_float,
    )
    trace_export_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="trace_export_enabled",
        current=trace_export_enabled,
        config=config,
        paths=[
            (namespace, "trace", "export_enabled"),
            ("trace", "export_enabled"),
            (namespace, "trace_export_enabled"),
            ("trace_export_enabled",),
        ],
        transform=_to_bool,
    )
    trace_export_path = _resolve_from_config(
        ctx=ctx,
        param_name="trace_export_path",
        current=trace_export_path,
        config=config,
        paths=[
            (namespace, "trace", "export_path"),
            ("trace", "export_path"),
            (namespace, "trace_export_path"),
            ("trace_export_path",),
        ],
        transform=str,
    )
    trace_otlp_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="trace_otlp_enabled",
        current=trace_otlp_enabled,
        config=config,
        paths=[
            (namespace, "trace", "otlp_enabled"),
            ("trace", "otlp_enabled"),
            (namespace, "trace_otlp_enabled"),
            ("trace_otlp_enabled",),
        ],
        transform=_to_bool,
    )
    trace_otlp_endpoint = _resolve_from_config(
        ctx=ctx,
        param_name="trace_otlp_endpoint",
        current=trace_otlp_endpoint,
        config=config,
        paths=[
            (namespace, "trace", "otlp_endpoint"),
            ("trace", "otlp_endpoint"),
            (namespace, "trace_otlp_endpoint"),
            ("trace_otlp_endpoint",),
        ],
        transform=str,
    )
    trace_otlp_timeout_seconds = _resolve_from_config(
        ctx=ctx,
        param_name="trace_otlp_timeout_seconds",
        current=trace_otlp_timeout_seconds,
        config=config,
        paths=[
            (namespace, "trace", "otlp_timeout_seconds"),
            ("trace", "otlp_timeout_seconds"),
            (namespace, "trace_otlp_timeout_seconds"),
            ("trace_otlp_timeout_seconds",),
        ],
        transform=_to_float,
    )

    normalized_chunk_guard_mode = str(chunk_guard_mode).strip().lower() or "off"
    normalized_chunk_payload = {
        "top_k": max(1, int(chunk_top_k)),
        "per_file_limit": max(1, int(chunk_per_file_limit)),
        "disclosure": chunk_disclosure,
        "signature": bool(chunk_signature),
        "snippet": {
            "max_lines": max(1, int(chunk_snippet_max_lines)),
            "max_chars": max(1, int(chunk_snippet_max_chars)),
        },
        "token_budget": max(1, int(chunk_token_budget)),
        "topological_shield": {
            "enabled": bool(chunk_topological_shield_enabled),
            "mode": chunk_topological_shield_mode,
            "max_attenuation": chunk_topological_shield_max_attenuation,
            "shared_parent_attenuation": (
                chunk_topological_shield_shared_parent_attenuation
            ),
            "adjacency_attenuation": (
                chunk_topological_shield_adjacency_attenuation
            ),
        },
        "guard": {
            "enabled": bool(chunk_guard_enabled),
            "mode": normalized_chunk_guard_mode,
            "lambda_penalty": chunk_guard_lambda_penalty,
            "min_pool": chunk_guard_min_pool,
            "max_pool": chunk_guard_max_pool,
            "min_marginal_utility": chunk_guard_min_marginal_utility,
            "compatibility_min_overlap": chunk_guard_compatibility_min_overlap,
        },
        "file_prior_weight": max(0.0, float(chunk_file_prior_weight)),
        "path_match": max(0.0, float(chunk_path_match)),
        "module_match": max(0.0, float(chunk_module_match)),
        "symbol_exact": max(0.0, float(chunk_symbol_exact)),
        "symbol_partial": max(0.0, float(chunk_symbol_partial)),
        "signature_match": max(0.0, float(chunk_signature_match)),
        "reference_factor": max(0.0, float(chunk_reference_factor)),
        "reference_cap": max(0.0, float(chunk_reference_cap)),
    }
    trace_payload = {
        "export_enabled": bool(trace_export_enabled),
        "export_path": str(trace_export_path),
        "otlp_enabled": bool(trace_otlp_enabled),
        "otlp_endpoint": str(trace_otlp_endpoint),
        "otlp_timeout_seconds": float(trace_otlp_timeout_seconds),
    }
    cochange_payload = {
        "enabled": bool(cochange_enabled),
        "cache_path": str(cochange_cache_path),
        "lookback_commits": max(1, int(cochange_lookback_commits)),
        "half_life_days": max(1.0, float(cochange_half_life_days)),
        "top_neighbors": max(0, int(cochange_top_neighbors)),
        "boost_weight": max(0.0, float(cochange_boost_weight)),
    }
    tests_payload = {
        "junit_xml": str(junit_xml).strip() if junit_xml else None,
        "coverage_json": str(coverage_json).strip() if coverage_json else None,
        "sbfl_json": str(sbfl_json).strip() if sbfl_json else None,
        "sbfl_metric": str(sbfl_metric).strip().lower() or "ochiai",
    }
    scip_payload = {
        "enabled": bool(scip_enabled),
        "index_path": str(scip_index_path),
        "provider": str(scip_provider).strip().lower() or "auto",
        "generate_fallback": bool(scip_generate_fallback),
        "base_weight": max(0.0, float(scip_base_weight)),
    }

    snippet_value = normalized_chunk_payload.get("snippet")
    snippet_payload = dict(snippet_value) if isinstance(snippet_value, dict) else {}
    return {
        "chunk_top_k": normalized_chunk_payload["top_k"],
        "chunk_per_file_limit": normalized_chunk_payload["per_file_limit"],
        "chunk_disclosure": chunk_disclosure,
        "chunk_signature": bool(chunk_signature),
        "chunk_snippet_max_lines": snippet_payload.get("max_lines", 0),
        "chunk_snippet_max_chars": snippet_payload.get("max_chars", 0),
        "chunk_token_budget": normalized_chunk_payload["token_budget"],
        "chunk_guard_enabled": bool(chunk_guard_enabled),
        "chunk_guard_mode": normalized_chunk_guard_mode,
        "chunk_guard_lambda_penalty": chunk_guard_lambda_penalty,
        "chunk_guard_min_pool": chunk_guard_min_pool,
        "chunk_guard_max_pool": chunk_guard_max_pool,
        "chunk_guard_min_marginal_utility": chunk_guard_min_marginal_utility,
        "chunk_guard_compatibility_min_overlap": (
            chunk_guard_compatibility_min_overlap
        ),
        "chunk": normalized_chunk_payload,
        "chunk_diversity_enabled": chunk_diversity_enabled,
        "chunk_diversity_path_penalty": chunk_diversity_path_penalty,
        "chunk_diversity_symbol_family_penalty": chunk_diversity_symbol_family_penalty,
        "chunk_diversity_kind_penalty": chunk_diversity_kind_penalty,
        "chunk_diversity_locality_penalty": chunk_diversity_locality_penalty,
        "chunk_diversity_locality_window": max(1, int(chunk_diversity_locality_window)),
        "chunk_file_prior_weight": normalized_chunk_payload["file_prior_weight"],
        "chunk_path_match": normalized_chunk_payload["path_match"],
        "chunk_module_match": normalized_chunk_payload["module_match"],
        "chunk_symbol_exact": normalized_chunk_payload["symbol_exact"],
        "chunk_symbol_partial": normalized_chunk_payload["symbol_partial"],
        "chunk_signature_match": normalized_chunk_payload["signature_match"],
        "chunk_reference_factor": normalized_chunk_payload["reference_factor"],
        "chunk_reference_cap": normalized_chunk_payload["reference_cap"],
        "cochange_enabled": cochange_payload["enabled"],
        "cochange_cache_path": cochange_payload["cache_path"],
        "cochange_lookback_commits": cochange_payload["lookback_commits"],
        "cochange_half_life_days": cochange_payload["half_life_days"],
        "cochange_top_neighbors": cochange_payload["top_neighbors"],
        "cochange_boost_weight": cochange_payload["boost_weight"],
        "cochange": cochange_payload,
        "retrieval_policy": retrieval_policy,
        "policy_version": policy_version,
        "junit_xml": tests_payload["junit_xml"],
        "coverage_json": tests_payload["coverage_json"],
        "sbfl_json": tests_payload["sbfl_json"],
        "sbfl_metric": tests_payload["sbfl_metric"],
        "tests": tests_payload,
        "scip_enabled": scip_payload["enabled"],
        "scip_index_path": scip_payload["index_path"],
        "scip_provider": scip_payload["provider"],
        "scip_generate_fallback": scip_payload["generate_fallback"],
        "scip_base_weight": scip_payload["base_weight"],
        "scip": scip_payload,
        "trace_export_enabled": trace_payload["export_enabled"],
        "trace_export_path": trace_payload["export_path"],
        "trace_otlp_enabled": trace_payload["otlp_enabled"],
        "trace_otlp_endpoint": trace_payload["otlp_endpoint"],
        "trace_otlp_timeout_seconds": trace_payload["otlp_timeout_seconds"],
        "trace": trace_payload,
    }
