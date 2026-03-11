from __future__ import annotations

import click

from ace_lite.cli_app.config.memory import resolve_memory_config
from ace_lite.config_models import validate_cli_config


def _resolve_memory(**config: object) -> dict[str, object]:
    ctx = click.Context(click.Command("unit"))
    return resolve_memory_config(
        ctx=ctx,
        config=config,
        namespace="plan",
        memory_disclosure_mode="compact",
        memory_preview_max_chars=280,
        memory_strategy="hybrid",
        memory_gate_enabled=False,
        memory_gate_mode="auto",
        memory_cache_enabled=False,
        memory_cache_path="context-map/memory-cache.jsonl",
        memory_cache_ttl_seconds=300,
        memory_cache_max_entries=128,
        memory_timeline_enabled=True,
        memory_container_tag=None,
        memory_auto_tag_mode=None,
        memory_profile_enabled=False,
        memory_profile_path="~/.ace-lite/profile.json",
        memory_profile_top_n=4,
        memory_profile_token_budget=160,
        memory_profile_expiry_enabled=True,
        memory_profile_ttl_days=90,
        memory_profile_max_age_days=365,
        memory_feedback_enabled=False,
        memory_feedback_path="~/.ace-lite/profile.json",
        memory_feedback_max_entries=512,
        memory_feedback_boost_per_select=0.15,
        memory_feedback_max_boost=0.6,
        memory_feedback_decay_days=60.0,
        memory_capture_enabled=False,
        memory_capture_notes_path="context-map/memory_notes.jsonl",
        memory_capture_min_query_length=24,
        memory_capture_keywords=[],
        memory_notes_enabled=False,
        memory_notes_path="context-map/memory_notes.jsonl",
        memory_notes_limit=8,
        memory_notes_mode="supplement",
        memory_notes_expiry_enabled=True,
        memory_notes_ttl_days=90,
        memory_notes_max_age_days=365,
        memory_postprocess_enabled=False,
        memory_postprocess_noise_filter_enabled=True,
        memory_postprocess_length_norm_anchor_chars=500,
        memory_postprocess_time_decay_half_life_days=0.0,
        memory_postprocess_hard_min_score=0.0,
        memory_postprocess_diversity_enabled=True,
        memory_postprocess_diversity_similarity_threshold=0.9,
        memory_hybrid_limit=10,
        tokenizer_model="gpt-4o-mini",
    )


def test_validate_cli_config_accepts_grouped_memory_fields() -> None:
    payload = validate_cli_config(
        {
            "plan": {
                "memory": {
                    "disclosure_mode": "full",
                    "preview_max_chars": 320,
                    "strategy": "semantic",
                    "timeline": {"enabled": False},
                    "gate": {"enabled": True, "mode": "never"},
                    "namespace": {
                        "container_tag": "repo",
                        "auto_tag_mode": "user",
                    },
                    "profile": {
                        "enabled": True,
                        "path": "profile.json",
                        "top_n": 6,
                        "token_budget": 240,
                    },
                    "feedback": {
                        "enabled": True,
                        "path": "feedback.json",
                        "max_entries": 64,
                        "boost_per_select": 0.2,
                    },
                    "capture": {
                        "enabled": True,
                        "notes_path": "notes.jsonl",
                        "min_query_length": 16,
                        "keywords": ["alpha", "beta"],
                    },
                    "notes": {
                        "enabled": True,
                        "path": "notes.jsonl",
                        "limit": 5,
                        "mode": "prefer_local",
                    },
                    "postprocess": {
                        "enabled": True,
                        "noise_filter_enabled": False,
                        "length_norm_anchor_chars": 640,
                        "time_decay_half_life_days": 12.5,
                        "hard_min_score": 0.2,
                        "diversity_enabled": False,
                        "diversity_similarity_threshold": 0.75,
                    },
                }
            }
        }
    )

    assert payload["plan"]["memory"]["disclosure_mode"] == "full"
    assert payload["plan"]["memory"]["timeline"] == {"enabled": False}
    assert payload["plan"]["memory"]["gate"] == {"enabled": True, "mode": "never"}
    assert payload["plan"]["memory"]["capture"]["keywords"] == ["alpha", "beta"]
    assert payload["plan"]["memory"]["notes"]["mode"] == "prefer_local"


def test_resolve_memory_config_reads_grouped_memory_fields_and_emits_grouped_payload() -> None:
    resolved = _resolve_memory(
        plan={
            "memory": {
                "disclosure_mode": "full",
                "preview_max_chars": 320,
                "strategy": "semantic",
                "cache": {
                    "enabled": True,
                    "path": "context-map/custom-memory-cache.jsonl",
                    "ttl_seconds": 120,
                    "max_entries": 48,
                },
                "timeline": {"enabled": False},
                "hybrid": {"limit": 6},
                "gate": {"enabled": True, "mode": "never"},
                "namespace": {
                    "container_tag": "repo",
                    "auto_tag_mode": "user",
                },
                "profile": {
                    "enabled": True,
                    "path": "profile.json",
                    "top_n": 6,
                    "token_budget": 240,
                    "expiry_enabled": False,
                    "ttl_days": 30,
                    "max_age_days": 45,
                },
                "feedback": {
                    "enabled": True,
                    "path": "feedback.json",
                    "max_entries": 64,
                    "boost_per_select": 0.2,
                    "max_boost": 0.7,
                    "decay_days": 30.0,
                },
                "capture": {
                    "enabled": True,
                    "notes_path": "notes.jsonl",
                    "min_query_length": 16,
                    "keywords": ["alpha", "beta"],
                },
                "notes": {
                    "enabled": True,
                    "path": "notes.jsonl",
                    "limit": 5,
                    "mode": "prefer_local",
                    "expiry_enabled": False,
                    "ttl_days": 15,
                    "max_age_days": 20,
                },
                "postprocess": {
                    "enabled": True,
                    "noise_filter_enabled": False,
                    "length_norm_anchor_chars": 640,
                    "time_decay_half_life_days": 12.5,
                    "hard_min_score": 0.2,
                    "diversity_enabled": False,
                    "diversity_similarity_threshold": 0.75,
                },
            },
            "tokenizer": {"model": "gpt-4.1-mini"},
        }
    )

    assert resolved["memory_disclosure_mode"] == "full"
    assert resolved["memory_preview_max_chars"] == 320
    assert resolved["memory_strategy"] == "semantic"
    assert resolved["memory_cache_enabled"] is True
    assert resolved["memory_cache_path"] == "context-map/custom-memory-cache.jsonl"
    assert resolved["memory_hybrid_limit"] == 6
    assert resolved["memory_gate_mode"] == "never"
    assert resolved["memory_capture_keywords"] == ["alpha", "beta"]
    assert resolved["memory_notes_mode"] == "prefer_local"
    assert resolved["memory_postprocess_diversity_enabled"] is False
    assert resolved["tokenizer_model"] == "gpt-4.1-mini"
    assert resolved["tokenizer"] == {"model": "gpt-4.1-mini"}
    assert resolved["memory"] == {
        "disclosure_mode": "full",
        "preview_max_chars": 320,
        "strategy": "semantic",
        "cache": {
            "enabled": True,
            "path": "context-map/custom-memory-cache.jsonl",
            "ttl_seconds": 120,
            "max_entries": 48,
        },
        "timeline": {"enabled": False},
        "hybrid": {"limit": 6},
        "namespace": {
            "container_tag": "repo",
            "auto_tag_mode": "user",
        },
        "gate": {"enabled": True, "mode": "never"},
        "profile": {
            "enabled": True,
            "path": "profile.json",
            "top_n": 6,
            "token_budget": 240,
            "expiry_enabled": False,
            "ttl_days": 30,
            "max_age_days": 45,
        },
        "feedback": {
            "enabled": True,
            "path": "feedback.json",
            "max_entries": 64,
            "boost_per_select": 0.2,
            "max_boost": 0.7,
            "decay_days": 30.0,
        },
        "capture": {
            "enabled": True,
            "notes_path": "notes.jsonl",
            "min_query_length": 16,
            "keywords": ["alpha", "beta"],
        },
        "notes": {
            "enabled": True,
            "path": "notes.jsonl",
            "limit": 5,
            "mode": "prefer_local",
            "expiry_enabled": False,
            "ttl_days": 15,
            "max_age_days": 20,
        },
        "postprocess": {
            "enabled": True,
            "noise_filter_enabled": False,
            "length_norm_anchor_chars": 640,
            "time_decay_half_life_days": 12.5,
            "hard_min_score": 0.2,
            "diversity_enabled": False,
            "diversity_similarity_threshold": 0.75,
        },
    }
