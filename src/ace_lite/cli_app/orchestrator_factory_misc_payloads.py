"""Miscellaneous payload builders for orchestrator factory wiring."""

from __future__ import annotations

from typing import Any

from ace_lite.cli_app.orchestrator_factory_payload_core import (
    CanonicalFieldSpec,
    build_canonical_payload,
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


__all__ = [
    "build_cochange_payload",
    "build_embeddings_payload",
    "build_index_payload",
    "build_lsp_payload",
    "build_plan_replay_cache_payload",
    "build_plugins_payload",
    "build_repomap_payload",
    "build_scip_payload",
    "build_skills_payload",
    "build_tests_payload",
    "build_tokenizer_payload",
    "build_trace_payload",
]
