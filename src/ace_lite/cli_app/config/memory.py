"""Resolve memory-related config sections."""

from __future__ import annotations

from typing import Any

import click

from ace_lite.cli_app.config_resolve_helpers import _resolve_from_config
from ace_lite.cli_app.params import (
    _to_bool,
    _to_float,
    _to_int,
    _to_memory_auto_tag_mode,
    _to_memory_gate_mode,
    _to_optional_str,
    _to_string_list,
    _to_tokenizer_model,
)


def resolve_memory_config(
    *,
    ctx: click.Context,
    config: dict[str, Any],
    namespace: str,
    memory_disclosure_mode: str,
    memory_preview_max_chars: int,
    memory_strategy: str,
    memory_gate_enabled: bool,
    memory_gate_mode: str,
    memory_cache_enabled: bool,
    memory_cache_path: str,
    memory_cache_ttl_seconds: int,
    memory_cache_max_entries: int,
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
    memory_capture_enabled: bool,
    memory_capture_notes_path: str,
    memory_capture_min_query_length: int,
    memory_capture_keywords: list[str] | tuple[str, ...] | str,
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
    memory_hybrid_limit: int,
    tokenizer_model: str,
    memory_long_term_enabled: bool = False,
    memory_long_term_path: str = "context-map/long_term_memory.db",
    memory_long_term_top_n: int = 4,
    memory_long_term_token_budget: int = 192,
    memory_long_term_write_enabled: bool = False,
    memory_long_term_as_of_enabled: bool = True,
) -> dict[str, Any]:
    memory_disclosure_mode = _resolve_from_config(
        ctx=ctx,
        param_name="memory_disclosure_mode",
        current=memory_disclosure_mode,
        config=config,
        paths=[
            (namespace, "memory", "disclosure_mode"),
            ("memory", "disclosure_mode"),
            (namespace, "memory_disclosure_mode"),
            ("memory_disclosure_mode",),
        ],
        transform=str,
    )
    memory_preview_max_chars = _resolve_from_config(
        ctx=ctx,
        param_name="memory_preview_max_chars",
        current=memory_preview_max_chars,
        config=config,
        paths=[
            (namespace, "memory", "preview_max_chars"),
            ("memory", "preview_max_chars"),
            (namespace, "memory_preview_max_chars"),
            ("memory_preview_max_chars",),
        ],
        transform=_to_int,
    )
    memory_strategy = _resolve_from_config(
        ctx=ctx,
        param_name="memory_strategy",
        current=memory_strategy,
        config=config,
        paths=[
            (namespace, "memory", "strategy"),
            ("memory", "strategy"),
            (namespace, "memory_strategy"),
            ("memory_strategy",),
        ],
        transform=lambda value: str(value).strip().lower(),
    )
    memory_gate_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_gate_enabled",
        current=memory_gate_enabled,
        config=config,
        paths=[
            (namespace, "memory", "gate", "enabled"),
            ("memory", "gate", "enabled"),
            (namespace, "memory_gate_enabled"),
            ("memory_gate_enabled",),
        ],
        transform=_to_bool,
    )
    memory_gate_mode = _resolve_from_config(
        ctx=ctx,
        param_name="memory_gate_mode",
        current=memory_gate_mode,
        config=config,
        paths=[
            (namespace, "memory", "gate", "mode"),
            ("memory", "gate", "mode"),
            (namespace, "memory_gate_mode"),
            ("memory_gate_mode",),
        ],
        transform=_to_memory_gate_mode,
    )
    memory_cache_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_cache_enabled",
        current=memory_cache_enabled,
        config=config,
        paths=[
            (namespace, "memory", "cache", "enabled"),
            ("memory", "cache", "enabled"),
            (namespace, "memory_cache_enabled"),
            ("memory_cache_enabled",),
        ],
        transform=_to_bool,
    )
    memory_cache_path = _resolve_from_config(
        ctx=ctx,
        param_name="memory_cache_path",
        current=memory_cache_path,
        config=config,
        paths=[
            (namespace, "memory", "cache", "path"),
            ("memory", "cache", "path"),
            (namespace, "memory_cache_path"),
            ("memory_cache_path",),
        ],
        transform=str,
    )
    memory_cache_ttl_seconds = _resolve_from_config(
        ctx=ctx,
        param_name="memory_cache_ttl_seconds",
        current=memory_cache_ttl_seconds,
        config=config,
        paths=[
            (namespace, "memory", "cache", "ttl_seconds"),
            ("memory", "cache", "ttl_seconds"),
            (namespace, "memory_cache_ttl_seconds"),
            ("memory_cache_ttl_seconds",),
        ],
        transform=_to_int,
    )
    memory_cache_max_entries = _resolve_from_config(
        ctx=ctx,
        param_name="memory_cache_max_entries",
        current=memory_cache_max_entries,
        config=config,
        paths=[
            (namespace, "memory", "cache", "max_entries"),
            ("memory", "cache", "max_entries"),
            (namespace, "memory_cache_max_entries"),
            ("memory_cache_max_entries",),
        ],
        transform=_to_int,
    )
    memory_timeline_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_timeline_enabled",
        current=memory_timeline_enabled,
        config=config,
        paths=[
            (namespace, "memory", "timeline", "enabled"),
            ("memory", "timeline", "enabled"),
            (namespace, "memory_timeline_enabled"),
            ("memory_timeline_enabled",),
        ],
        transform=_to_bool,
    )
    memory_container_tag = _resolve_from_config(
        ctx=ctx,
        param_name="memory_container_tag",
        current=memory_container_tag,
        config=config,
        paths=[
            (namespace, "memory", "namespace", "container_tag"),
            ("memory", "namespace", "container_tag"),
            (namespace, "memory_container_tag"),
            ("memory_container_tag",),
        ],
        transform=_to_optional_str,
    )
    memory_auto_tag_mode = _resolve_from_config(
        ctx=ctx,
        param_name="memory_auto_tag_mode",
        current=memory_auto_tag_mode,
        config=config,
        paths=[
            (namespace, "memory", "namespace", "auto_tag_mode"),
            ("memory", "namespace", "auto_tag_mode"),
            (namespace, "memory_auto_tag_mode"),
            ("memory_auto_tag_mode",),
        ],
        transform=_to_memory_auto_tag_mode,
    )
    memory_profile_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_enabled",
        current=memory_profile_enabled,
        config=config,
        paths=[
            (namespace, "memory", "profile", "enabled"),
            ("memory", "profile", "enabled"),
            (namespace, "memory_profile_enabled"),
            ("memory_profile_enabled",),
        ],
        transform=_to_bool,
    )
    memory_profile_path = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_path",
        current=memory_profile_path,
        config=config,
        paths=[
            (namespace, "memory", "profile", "path"),
            ("memory", "profile", "path"),
            (namespace, "memory_profile_path"),
            ("memory_profile_path",),
        ],
        transform=str,
    )
    memory_profile_top_n = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_top_n",
        current=memory_profile_top_n,
        config=config,
        paths=[
            (namespace, "memory", "profile", "top_n"),
            ("memory", "profile", "top_n"),
            (namespace, "memory_profile_top_n"),
            ("memory_profile_top_n",),
        ],
        transform=_to_int,
    )
    memory_profile_token_budget = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_token_budget",
        current=memory_profile_token_budget,
        config=config,
        paths=[
            (namespace, "memory", "profile", "token_budget"),
            ("memory", "profile", "token_budget"),
            (namespace, "memory_profile_token_budget"),
            ("memory_profile_token_budget",),
        ],
        transform=_to_int,
    )
    memory_profile_expiry_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_expiry_enabled",
        current=memory_profile_expiry_enabled,
        config=config,
        paths=[
            (namespace, "memory", "profile", "expiry_enabled"),
            ("memory", "profile", "expiry_enabled"),
            (namespace, "memory_profile_expiry_enabled"),
            ("memory_profile_expiry_enabled",),
        ],
        transform=_to_bool,
    )
    memory_profile_ttl_days = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_ttl_days",
        current=memory_profile_ttl_days,
        config=config,
        paths=[
            (namespace, "memory", "profile", "ttl_days"),
            ("memory", "profile", "ttl_days"),
            (namespace, "memory_profile_ttl_days"),
            ("memory_profile_ttl_days",),
        ],
        transform=_to_int,
    )
    memory_profile_max_age_days = _resolve_from_config(
        ctx=ctx,
        param_name="memory_profile_max_age_days",
        current=memory_profile_max_age_days,
        config=config,
        paths=[
            (namespace, "memory", "profile", "max_age_days"),
            ("memory", "profile", "max_age_days"),
            (namespace, "memory_profile_max_age_days"),
            ("memory_profile_max_age_days",),
        ],
        transform=_to_int,
    )
    memory_feedback_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_feedback_enabled",
        current=memory_feedback_enabled,
        config=config,
        paths=[
            (namespace, "memory", "feedback", "enabled"),
            ("memory", "feedback", "enabled"),
            (namespace, "memory_feedback_enabled"),
            ("memory_feedback_enabled",),
        ],
        transform=_to_bool,
    )
    memory_feedback_path = _resolve_from_config(
        ctx=ctx,
        param_name="memory_feedback_path",
        current=memory_feedback_path,
        config=config,
        paths=[
            (namespace, "memory", "feedback", "path"),
            ("memory", "feedback", "path"),
            (namespace, "memory_feedback_path"),
            ("memory_feedback_path",),
        ],
        transform=str,
    )
    memory_feedback_max_entries = _resolve_from_config(
        ctx=ctx,
        param_name="memory_feedback_max_entries",
        current=memory_feedback_max_entries,
        config=config,
        paths=[
            (namespace, "memory", "feedback", "max_entries"),
            ("memory", "feedback", "max_entries"),
            (namespace, "memory_feedback_max_entries"),
            ("memory_feedback_max_entries",),
        ],
        transform=_to_int,
    )
    memory_feedback_boost_per_select = _resolve_from_config(
        ctx=ctx,
        param_name="memory_feedback_boost_per_select",
        current=memory_feedback_boost_per_select,
        config=config,
        paths=[
            (namespace, "memory", "feedback", "boost_per_select"),
            ("memory", "feedback", "boost_per_select"),
            (namespace, "memory_feedback_boost_per_select"),
            ("memory_feedback_boost_per_select",),
        ],
        transform=_to_float,
    )
    memory_feedback_max_boost = _resolve_from_config(
        ctx=ctx,
        param_name="memory_feedback_max_boost",
        current=memory_feedback_max_boost,
        config=config,
        paths=[
            (namespace, "memory", "feedback", "max_boost"),
            ("memory", "feedback", "max_boost"),
            (namespace, "memory_feedback_max_boost"),
            ("memory_feedback_max_boost",),
        ],
        transform=_to_float,
    )
    memory_feedback_decay_days = _resolve_from_config(
        ctx=ctx,
        param_name="memory_feedback_decay_days",
        current=memory_feedback_decay_days,
        config=config,
        paths=[
            (namespace, "memory", "feedback", "decay_days"),
            ("memory", "feedback", "decay_days"),
            (namespace, "memory_feedback_decay_days"),
            ("memory_feedback_decay_days",),
        ],
        transform=_to_float,
    )
    memory_long_term_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_long_term_enabled",
        current=memory_long_term_enabled,
        config=config,
        paths=[
            (namespace, "memory", "long_term", "enabled"),
            ("memory", "long_term", "enabled"),
            (namespace, "memory_long_term_enabled"),
            ("memory_long_term_enabled",),
        ],
        transform=_to_bool,
    )
    memory_long_term_path = _resolve_from_config(
        ctx=ctx,
        param_name="memory_long_term_path",
        current=memory_long_term_path,
        config=config,
        paths=[
            (namespace, "memory", "long_term", "path"),
            ("memory", "long_term", "path"),
            (namespace, "memory_long_term_path"),
            ("memory_long_term_path",),
        ],
        transform=str,
    )
    memory_long_term_top_n = _resolve_from_config(
        ctx=ctx,
        param_name="memory_long_term_top_n",
        current=memory_long_term_top_n,
        config=config,
        paths=[
            (namespace, "memory", "long_term", "top_n"),
            ("memory", "long_term", "top_n"),
            (namespace, "memory_long_term_top_n"),
            ("memory_long_term_top_n",),
        ],
        transform=_to_int,
    )
    memory_long_term_token_budget = _resolve_from_config(
        ctx=ctx,
        param_name="memory_long_term_token_budget",
        current=memory_long_term_token_budget,
        config=config,
        paths=[
            (namespace, "memory", "long_term", "token_budget"),
            ("memory", "long_term", "token_budget"),
            (namespace, "memory_long_term_token_budget"),
            ("memory_long_term_token_budget",),
        ],
        transform=_to_int,
    )
    memory_long_term_write_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_long_term_write_enabled",
        current=memory_long_term_write_enabled,
        config=config,
        paths=[
            (namespace, "memory", "long_term", "write_enabled"),
            ("memory", "long_term", "write_enabled"),
            (namespace, "memory_long_term_write_enabled"),
            ("memory_long_term_write_enabled",),
        ],
        transform=_to_bool,
    )
    memory_long_term_as_of_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_long_term_as_of_enabled",
        current=memory_long_term_as_of_enabled,
        config=config,
        paths=[
            (namespace, "memory", "long_term", "as_of_enabled"),
            ("memory", "long_term", "as_of_enabled"),
            (namespace, "memory_long_term_as_of_enabled"),
            ("memory_long_term_as_of_enabled",),
        ],
        transform=_to_bool,
    )
    memory_capture_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_capture_enabled",
        current=memory_capture_enabled,
        config=config,
        paths=[
            (namespace, "memory", "capture", "enabled"),
            ("memory", "capture", "enabled"),
            (namespace, "memory_capture_enabled"),
            ("memory_capture_enabled",),
        ],
        transform=_to_bool,
    )
    memory_capture_notes_path = _resolve_from_config(
        ctx=ctx,
        param_name="memory_capture_notes_path",
        current=memory_capture_notes_path,
        config=config,
        paths=[
            (namespace, "memory", "capture", "notes_path"),
            ("memory", "capture", "notes_path"),
            (namespace, "memory_capture_notes_path"),
            ("memory_capture_notes_path",),
        ],
        transform=str,
    )
    memory_capture_min_query_length = _resolve_from_config(
        ctx=ctx,
        param_name="memory_capture_min_query_length",
        current=memory_capture_min_query_length,
        config=config,
        paths=[
            (namespace, "memory", "capture", "min_query_length"),
            ("memory", "capture", "min_query_length"),
            (namespace, "memory_capture_min_query_length"),
            ("memory_capture_min_query_length",),
        ],
        transform=_to_int,
    )
    memory_capture_keywords = _resolve_from_config(
        ctx=ctx,
        param_name="memory_capture_keywords",
        current=memory_capture_keywords,
        config=config,
        paths=[
            (namespace, "memory", "capture", "keywords"),
            ("memory", "capture", "keywords"),
            (namespace, "memory_capture_keywords"),
            ("memory_capture_keywords",),
        ],
        transform=_to_string_list,
    )
    memory_notes_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_enabled",
        current=memory_notes_enabled,
        config=config,
        paths=[
            (namespace, "memory", "notes", "enabled"),
            ("memory", "notes", "enabled"),
            (namespace, "memory_notes_enabled"),
            ("memory_notes_enabled",),
        ],
        transform=_to_bool,
    )
    memory_notes_path = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_path",
        current=memory_notes_path,
        config=config,
        paths=[
            (namespace, "memory", "notes", "path"),
            ("memory", "notes", "path"),
            (namespace, "memory_notes_path"),
            ("memory_notes_path",),
        ],
        transform=str,
    )
    memory_notes_limit = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_limit",
        current=memory_notes_limit,
        config=config,
        paths=[
            (namespace, "memory", "notes", "limit"),
            ("memory", "notes", "limit"),
            (namespace, "memory_notes_limit"),
            ("memory_notes_limit",),
        ],
        transform=_to_int,
    )
    memory_notes_mode = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_mode",
        current=memory_notes_mode,
        config=config,
        paths=[
            (namespace, "memory", "notes", "mode"),
            ("memory", "notes", "mode"),
            (namespace, "memory_notes_mode"),
            ("memory_notes_mode",),
        ],
        transform=lambda value: str(value).strip().lower(),
    )
    memory_notes_expiry_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_expiry_enabled",
        current=memory_notes_expiry_enabled,
        config=config,
        paths=[
            (namespace, "memory", "notes", "expiry_enabled"),
            ("memory", "notes", "expiry_enabled"),
            (namespace, "memory_notes_expiry_enabled"),
            ("memory_notes_expiry_enabled",),
        ],
        transform=_to_bool,
    )
    memory_notes_ttl_days = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_ttl_days",
        current=memory_notes_ttl_days,
        config=config,
        paths=[
            (namespace, "memory", "notes", "ttl_days"),
            ("memory", "notes", "ttl_days"),
            (namespace, "memory_notes_ttl_days"),
            ("memory_notes_ttl_days",),
        ],
        transform=_to_int,
    )
    memory_notes_max_age_days = _resolve_from_config(
        ctx=ctx,
        param_name="memory_notes_max_age_days",
        current=memory_notes_max_age_days,
        config=config,
        paths=[
            (namespace, "memory", "notes", "max_age_days"),
            ("memory", "notes", "max_age_days"),
            (namespace, "memory_notes_max_age_days"),
            ("memory_notes_max_age_days",),
        ],
        transform=_to_int,
    )
    memory_postprocess_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_enabled",
        current=memory_postprocess_enabled,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "enabled"),
            ("memory", "postprocess", "enabled"),
            (namespace, "memory_postprocess_enabled"),
            ("memory_postprocess_enabled",),
        ],
        transform=_to_bool,
    )
    memory_postprocess_noise_filter_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_noise_filter_enabled",
        current=memory_postprocess_noise_filter_enabled,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "noise_filter_enabled"),
            ("memory", "postprocess", "noise_filter_enabled"),
            (namespace, "memory_postprocess_noise_filter_enabled"),
            ("memory_postprocess_noise_filter_enabled",),
        ],
        transform=_to_bool,
    )
    memory_postprocess_length_norm_anchor_chars = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_length_norm_anchor_chars",
        current=memory_postprocess_length_norm_anchor_chars,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "length_norm_anchor_chars"),
            ("memory", "postprocess", "length_norm_anchor_chars"),
            (namespace, "memory_postprocess_length_norm_anchor_chars"),
            ("memory_postprocess_length_norm_anchor_chars",),
        ],
        transform=_to_int,
    )
    memory_postprocess_time_decay_half_life_days = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_time_decay_half_life_days",
        current=memory_postprocess_time_decay_half_life_days,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "time_decay_half_life_days"),
            ("memory", "postprocess", "time_decay_half_life_days"),
            (namespace, "memory_postprocess_time_decay_half_life_days"),
            ("memory_postprocess_time_decay_half_life_days",),
        ],
        transform=_to_float,
    )
    memory_postprocess_hard_min_score = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_hard_min_score",
        current=memory_postprocess_hard_min_score,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "hard_min_score"),
            ("memory", "postprocess", "hard_min_score"),
            (namespace, "memory_postprocess_hard_min_score"),
            ("memory_postprocess_hard_min_score",),
        ],
        transform=_to_float,
    )
    memory_postprocess_diversity_enabled = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_diversity_enabled",
        current=memory_postprocess_diversity_enabled,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "diversity_enabled"),
            ("memory", "postprocess", "diversity_enabled"),
            (namespace, "memory_postprocess_diversity_enabled"),
            ("memory_postprocess_diversity_enabled",),
        ],
        transform=_to_bool,
    )
    memory_postprocess_diversity_similarity_threshold = _resolve_from_config(
        ctx=ctx,
        param_name="memory_postprocess_diversity_similarity_threshold",
        current=memory_postprocess_diversity_similarity_threshold,
        config=config,
        paths=[
            (namespace, "memory", "postprocess", "diversity_similarity_threshold"),
            ("memory", "postprocess", "diversity_similarity_threshold"),
            (namespace, "memory_postprocess_diversity_similarity_threshold"),
            ("memory_postprocess_diversity_similarity_threshold",),
        ],
        transform=_to_float,
    )
    memory_hybrid_limit = _resolve_from_config(
        ctx=ctx,
        param_name="memory_hybrid_limit",
        current=memory_hybrid_limit,
        config=config,
        paths=[
            (namespace, "memory", "hybrid", "limit"),
            ("memory", "hybrid", "limit"),
            (namespace, "memory_hybrid_limit"),
            ("memory_hybrid_limit",),
        ],
        transform=_to_int,
    )
    tokenizer_model = _resolve_from_config(
        ctx=ctx,
        param_name="tokenizer_model",
        current=tokenizer_model,
        config=config,
        paths=[
            (namespace, "tokenizer", "model"),
            ("tokenizer", "model"),
            (namespace, "tokenizer_model"),
            ("tokenizer_model",),
        ],
        transform=_to_tokenizer_model,
    )

    memory_payload = {
        "disclosure_mode": memory_disclosure_mode,
        "preview_max_chars": memory_preview_max_chars,
        "strategy": memory_strategy,
        "cache": {
            "enabled": bool(memory_cache_enabled),
            "path": memory_cache_path,
            "ttl_seconds": memory_cache_ttl_seconds,
            "max_entries": memory_cache_max_entries,
        },
        "timeline": {
            "enabled": bool(memory_timeline_enabled),
        },
        "hybrid": {
            "limit": memory_hybrid_limit,
        },
        "namespace": {
            "container_tag": memory_container_tag,
            "auto_tag_mode": memory_auto_tag_mode,
        },
        "gate": {
            "enabled": bool(memory_gate_enabled),
            "mode": memory_gate_mode,
        },
        "profile": {
            "enabled": bool(memory_profile_enabled),
            "path": memory_profile_path,
            "top_n": memory_profile_top_n,
            "token_budget": memory_profile_token_budget,
            "expiry_enabled": bool(memory_profile_expiry_enabled),
            "ttl_days": memory_profile_ttl_days,
            "max_age_days": memory_profile_max_age_days,
        },
        "feedback": {
            "enabled": bool(memory_feedback_enabled),
            "path": memory_feedback_path,
            "max_entries": memory_feedback_max_entries,
            "boost_per_select": memory_feedback_boost_per_select,
            "max_boost": memory_feedback_max_boost,
            "decay_days": memory_feedback_decay_days,
        },
        "long_term": {
            "enabled": bool(memory_long_term_enabled),
            "path": memory_long_term_path,
            "top_n": memory_long_term_top_n,
            "token_budget": memory_long_term_token_budget,
            "write_enabled": bool(memory_long_term_write_enabled),
            "as_of_enabled": bool(memory_long_term_as_of_enabled),
        },
        "capture": {
            "enabled": bool(memory_capture_enabled),
            "notes_path": memory_capture_notes_path,
            "min_query_length": memory_capture_min_query_length,
            "keywords": list(_to_string_list(memory_capture_keywords)),
        },
        "notes": {
            "enabled": bool(memory_notes_enabled),
            "path": memory_notes_path,
            "limit": memory_notes_limit,
            "mode": memory_notes_mode,
            "expiry_enabled": bool(memory_notes_expiry_enabled),
            "ttl_days": memory_notes_ttl_days,
            "max_age_days": memory_notes_max_age_days,
        },
        "postprocess": {
            "enabled": bool(memory_postprocess_enabled),
            "noise_filter_enabled": bool(memory_postprocess_noise_filter_enabled),
            "length_norm_anchor_chars": memory_postprocess_length_norm_anchor_chars,
            "time_decay_half_life_days": memory_postprocess_time_decay_half_life_days,
            "hard_min_score": memory_postprocess_hard_min_score,
            "diversity_enabled": bool(memory_postprocess_diversity_enabled),
            "diversity_similarity_threshold": (
                memory_postprocess_diversity_similarity_threshold
            ),
        },
    }

    return {
        "memory_disclosure_mode": memory_disclosure_mode,
        "memory_preview_max_chars": memory_preview_max_chars,
        "memory_strategy": memory_strategy,
        "memory_gate_enabled": memory_gate_enabled,
        "memory_gate_mode": memory_gate_mode,
        "memory_cache_enabled": memory_cache_enabled,
        "memory_cache_path": memory_cache_path,
        "memory_cache_ttl_seconds": memory_cache_ttl_seconds,
        "memory_cache_max_entries": memory_cache_max_entries,
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
        "memory_capture_keywords": list(_to_string_list(memory_capture_keywords)),
        "memory_notes_enabled": memory_notes_enabled,
        "memory_notes_path": memory_notes_path,
        "memory_notes_limit": memory_notes_limit,
        "memory_notes_mode": memory_notes_mode,
        "memory_notes_expiry_enabled": memory_notes_expiry_enabled,
        "memory_notes_ttl_days": memory_notes_ttl_days,
        "memory_notes_max_age_days": memory_notes_max_age_days,
        "memory_postprocess_enabled": memory_postprocess_enabled,
        "memory_postprocess_noise_filter_enabled": memory_postprocess_noise_filter_enabled,
        "memory_postprocess_length_norm_anchor_chars": memory_postprocess_length_norm_anchor_chars,
        "memory_postprocess_time_decay_half_life_days": memory_postprocess_time_decay_half_life_days,
        "memory_postprocess_hard_min_score": memory_postprocess_hard_min_score,
        "memory_postprocess_diversity_enabled": memory_postprocess_diversity_enabled,
        "memory_postprocess_diversity_similarity_threshold": memory_postprocess_diversity_similarity_threshold,
        "memory_hybrid_limit": memory_hybrid_limit,
        "memory": memory_payload,
        "tokenizer_model": tokenizer_model,
        "tokenizer": {"model": tokenizer_model},
    }
