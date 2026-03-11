"""Shared canonical payload helpers for orchestrator factory wiring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
    "CanonicalFieldSpec",
    "build_canonical_payload",
    "build_cochange_payload",
    "build_embeddings_payload",
    "build_index_payload",
    "build_memory_payload",
    "build_scip_payload",
    "build_skills_payload",
    "build_tests_payload",
    "normalize_group_mapping",
]
