from __future__ import annotations

from typing import Any

from ace_lite.benchmark_application import create_benchmark_orchestrator_from_resolved


def _make_resolved() -> dict[str, Any]:
    return {
        "memory_strategy": "hybrid",
        "memory_hybrid_limit": 10,
        "memory_cache_enabled": True,
        "memory_cache_path": "context-map/memory_cache.jsonl",
        "memory_cache_ttl_seconds": 600,
        "memory_cache_max_entries": 256,
        "memory_notes_enabled": True,
        "memory_notes_path": "context-map/memory_notes.jsonl",
        "memory_notes_limit": 6,
        "memory_notes_mode": "supplement",
        "memory_notes_expiry_enabled": True,
        "memory_notes_ttl_days": 90,
        "memory_notes_max_age_days": 365,
        "memory_disclosure_mode": "compact",
        "memory_preview_max_chars": 280,
        "memory_gate_enabled": False,
        "memory_gate_mode": "auto",
        "memory_timeline_enabled": True,
        "memory_container_tag": None,
        "memory_auto_tag_mode": None,
        "memory_profile_enabled": False,
        "memory_profile_path": "~/.ace-lite/profile.json",
        "memory_profile_top_n": 4,
        "memory_profile_token_budget": 160,
        "memory_profile_expiry_enabled": True,
        "memory_profile_ttl_days": 90,
        "memory_profile_max_age_days": 365,
        "memory_feedback_enabled": False,
        "memory_feedback_path": "~/.ace-lite/profile.json",
        "memory_feedback_max_entries": 512,
        "memory_feedback_boost_per_select": 0.15,
        "memory_feedback_max_boost": 0.6,
        "memory_feedback_decay_days": 60.0,
        "memory_capture_enabled": False,
        "memory_capture_notes_path": "context-map/memory_notes.jsonl",
        "memory_capture_min_query_length": 24,
        "memory_capture_keywords": [],
        "memory_postprocess_enabled": False,
        "memory_postprocess_noise_filter_enabled": True,
        "memory_postprocess_length_norm_anchor_chars": 500,
        "memory_postprocess_time_decay_half_life_days": 0.0,
        "memory_postprocess_hard_min_score": 0.0,
        "memory_postprocess_diversity_enabled": True,
        "memory_postprocess_diversity_similarity_threshold": 0.9,
        "skills": {"top_n": 4},
        "index": {"cache_path": "context-map/index.json"},
        "embeddings": {"enabled": False},
        "adaptive_router": {"enabled": False},
        "plan_replay_cache": {"enabled": False},
        "retrieval": {"top_k_files": 8},
        "repomap": {"enabled": True},
        "lsp": {"enabled": False},
        "plugins": {"enabled": False},
        "chunk": {"top_k": 12},
        "tokenizer": {"model": "gpt-4o-mini"},
        "cochange": {"enabled": True},
        "policy_version": "v1",
        "tests": {"sbfl_metric": "ochiai"},
        "scip": {"enabled": False},
        "trace": {"export_enabled": False},
    }


def test_create_benchmark_orchestrator_from_resolved_wires_shared_builders() -> None:
    resolved = _make_resolved()
    captured_memory: dict[str, Any] = {}
    captured_orchestrator: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> str:
        captured_memory.update(kwargs)
        return "memory-provider"

    def fake_create_orchestrator(**kwargs: Any) -> dict[str, Any]:
        captured_orchestrator.update(kwargs)
        return {"orchestrator": True}

    result = create_benchmark_orchestrator_from_resolved(
        create_memory_provider_fn=fake_create_memory_provider,
        create_orchestrator_fn=fake_create_orchestrator,
        resolved=resolved,
        skills_dir="skills",
        retrieval_policy="feature",
        memory_primary="none",
        memory_secondary="rest",
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        memory_timeout=3.0,
        user_id="u",
        app="ace-lite",
        memory_limit=8,
    )

    assert result == {"orchestrator": True}
    assert captured_memory["primary"] == "none"
    assert captured_memory["secondary"] == "rest"
    assert captured_memory["memory_notes_enabled"] is True
    assert captured_orchestrator["memory_provider"] == "memory-provider"
    assert captured_orchestrator["skills_dir"] == "skills"
    assert captured_orchestrator["retrieval_policy"] == "feature"
    assert captured_orchestrator["skills_config"] == {"dir": "skills", "top_n": 4}
