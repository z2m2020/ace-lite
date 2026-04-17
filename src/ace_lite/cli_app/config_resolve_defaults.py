"""Shared default payloads for plan/benchmark config resolution."""

from __future__ import annotations

from typing import Any

PLAN_MEMORY_PROFILE_DEFAULTS: dict[str, Any] = {
    "memory_profile_enabled": False,
    "memory_profile_path": "~/.ace-lite/profile.json",
    "memory_profile_top_n": 4,
    "memory_profile_token_budget": 160,
    "memory_profile_expiry_enabled": True,
    "memory_profile_ttl_days": 90,
    "memory_profile_max_age_days": 365,
}


PLAN_MEMORY_CAPTURE_DEFAULTS: dict[str, Any] = {
    "memory_capture_enabled": False,
    "memory_capture_notes_path": "context-map/memory_notes.jsonl",
    "memory_capture_min_query_length": 24,
    "memory_capture_keywords": (),
}


PLAN_MEMORY_NOTES_DEFAULTS: dict[str, Any] = {
    "memory_notes_enabled": False,
    "memory_notes_path": "context-map/memory_notes.jsonl",
    "memory_notes_limit": 8,
    "memory_notes_mode": "supplement",
    "memory_notes_expiry_enabled": True,
    "memory_notes_ttl_days": 90,
    "memory_notes_max_age_days": 365,
}


PLAN_MEMORY_FEEDBACK_DEFAULTS: dict[str, Any] = {
    "memory_feedback_enabled": False,
    "memory_feedback_path": "~/.ace-lite/profile.json",
    "memory_feedback_max_entries": 512,
    "memory_feedback_boost_per_select": 0.15,
    "memory_feedback_max_boost": 0.6,
    "memory_feedback_decay_days": 60.0,
}


PLAN_MEMORY_LONG_TERM_DEFAULTS: dict[str, Any] = {
    "memory_long_term_enabled": False,
    "memory_long_term_path": "context-map/long_term_memory.db",
    "memory_long_term_top_n": 4,
    "memory_long_term_token_budget": 192,
    "memory_long_term_write_enabled": False,
    "memory_long_term_as_of_enabled": True,
}


PLAN_MEMORY_GATE_DEFAULTS: dict[str, Any] = {
    "memory_gate_enabled": False,
    "memory_gate_mode": "auto",
}


PLAN_MEMORY_NAMESPACE_DEFAULTS: dict[str, Any] = {
    "memory_auto_tag_mode": "repo",
}


PLAN_MEMORY_POSTPROCESS_DEFAULTS: dict[str, Any] = {
    "memory_postprocess_enabled": False,
    "memory_postprocess_noise_filter_enabled": True,
    "memory_postprocess_length_norm_anchor_chars": 500,
    "memory_postprocess_time_decay_half_life_days": 0.0,
    "memory_postprocess_hard_min_score": 0.0,
    "memory_postprocess_diversity_enabled": True,
    "memory_postprocess_diversity_similarity_threshold": 0.9,
}
