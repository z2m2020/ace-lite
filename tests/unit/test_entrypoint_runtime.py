from __future__ import annotations

from typing import Any

from ace_lite.entrypoint_runtime import (
    SHARED_RUNTIME_PAYLOAD_KEYS,
    build_memory_provider_kwargs,
    build_memory_provider_kwargs_from_resolved,
    build_orchestrator_kwargs_from_resolved,
    build_run_plan_kwargs_from_resolved,
)


def _make_resolved() -> dict[str, Any]:
    return {
        "memory": {"strategy": "hybrid"},
        "memory_disclosure_mode": "Compact",
        "memory_preview_max_chars": 48,
        "memory_strategy": "hybrid",
        "memory_gate_enabled": True,
        "memory_gate_mode": "AUTO",
        "memory_timeline_enabled": True,
        "memory_container_tag": "repo/demo",
        "memory_auto_tag_mode": "repo",
        "memory_profile_enabled": True,
        "memory_profile_path": "profile.json",
        "memory_profile_top_n": 6,
        "memory_profile_token_budget": 240,
        "memory_profile_expiry_enabled": True,
        "memory_profile_ttl_days": 45,
        "memory_profile_max_age_days": 180,
        "memory_feedback_enabled": True,
        "memory_feedback_path": "feedback.json",
        "memory_feedback_max_entries": 256,
        "memory_feedback_boost_per_select": 0.2,
        "memory_feedback_max_boost": 0.5,
        "memory_feedback_decay_days": 15.0,
        "memory_capture_enabled": True,
        "memory_capture_notes_path": "capture.jsonl",
        "memory_capture_min_query_length": 32,
        "memory_capture_keywords": ("alpha", "beta"),
        "memory_notes_enabled": True,
        "memory_notes_path": "notes.jsonl",
        "memory_notes_limit": 5,
        "memory_notes_mode": "PREFER_LOCAL",
        "memory_notes_expiry_enabled": True,
        "memory_notes_ttl_days": 20,
        "memory_notes_max_age_days": 120,
        "memory_postprocess_enabled": True,
        "memory_postprocess_noise_filter_enabled": True,
        "memory_postprocess_length_norm_anchor_chars": 600,
        "memory_postprocess_time_decay_half_life_days": 7.0,
        "memory_postprocess_hard_min_score": 0.15,
        "memory_postprocess_diversity_enabled": True,
        "memory_postprocess_diversity_similarity_threshold": 0.8,
        "skills": {"top_n": 4},
        "index": {"cache_path": "context-map/index.json"},
        "embedding_enabled": True,
        "embedding_provider": "ollama",
        "embedding_model": "embed",
        "embedding_dimension": 1024,
        "embedding_index_path": "context-map/embeddings/index.json",
        "embedding_rerank_pool": 16,
        "embedding_lexical_weight": 0.6,
        "embedding_semantic_weight": 0.4,
        "embedding_min_similarity": 0.2,
        "embedding_fail_open": False,
        "embeddings": {"enabled": True, "provider": "ollama"},
        "adaptive_router": {"enabled": True},
        "plan_replay_cache": {"enabled": True},
        "retrieval": {"top_k_files": 8},
        "repomap": {"enabled": True},
        "lsp": {"enabled": False},
        "plugins": {"enabled": True},
        "chunk": {"top_k": 12},
        "tokenizer": {"model": "gpt-4o-mini"},
        "cochange": {"enabled": True},
        "policy_version": "v2",
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl_json": "artifacts/sbfl.json",
        "sbfl_metric": "ochiai",
        "tests": {"sbfl_metric": "ochiai"},
        "scip_enabled": True,
        "scip_index_path": "context-map/scip/index.json",
        "scip_provider": "auto",
        "scip_generate_fallback": True,
        "scip": {"enabled": True},
        "trace_export_enabled": True,
        "trace_export_path": "context-map/traces/stage_spans.jsonl",
        "trace_otlp_enabled": False,
        "trace_otlp_endpoint": "",
        "trace_otlp_timeout_seconds": 1.5,
        "trace": {"export_enabled": True},
    }


def test_build_memory_provider_kwargs_normalizes_values() -> None:
    payload = build_memory_provider_kwargs(
        primary=" MCP ",
        secondary=" ",
        memory_strategy=" Hybrid ",
        memory_hybrid_limit=0,
        memory_cache_enabled=True,
        memory_cache_path="context-map/memory_cache.jsonl",
        memory_cache_ttl_seconds=0,
        memory_cache_max_entries=1,
        memory_notes_enabled=True,
        memory_notes_path=" ",
        memory_notes_limit=0,
        memory_notes_mode=" PREFER_LOCAL ",
        memory_notes_expiry_enabled=True,
        memory_notes_ttl_days=0,
        memory_notes_max_age_days=0,
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        timeout_seconds=3,
        user_id="u",
        app="ace-lite",
        limit=0,
    )

    assert payload["primary"] == "mcp"
    assert payload["secondary"] == "none"
    assert payload["memory_strategy"] == "hybrid"
    assert payload["memory_hybrid_limit"] == 1
    assert payload["memory_cache_ttl_seconds"] == 1
    assert payload["memory_cache_max_entries"] == 16
    assert payload["memory_notes_path"] == "context-map/memory_notes.jsonl"
    assert payload["memory_notes_limit"] == 1
    assert payload["memory_notes_mode"] == "prefer_local"
    assert payload["memory_notes_ttl_days"] == 1
    assert payload["memory_notes_max_age_days"] == 1
    assert payload["limit"] == 1


def test_build_memory_provider_kwargs_from_resolved_normalizes_payload() -> None:
    resolved = _make_resolved()
    resolved["memory_strategy"] = " Hybrid "
    resolved["memory_hybrid_limit"] = 0
    resolved["memory_cache_enabled"] = True
    resolved["memory_cache_path"] = "context-map/memory_cache.jsonl"
    resolved["memory_cache_ttl_seconds"] = 0
    resolved["memory_cache_max_entries"] = 2
    resolved["memory_notes_path"] = " "
    resolved["memory_notes_limit"] = 0
    resolved["memory_notes_mode"] = " PREFER_LOCAL "
    resolved["memory_notes_ttl_days"] = 0
    resolved["memory_notes_max_age_days"] = 0

    payload = build_memory_provider_kwargs_from_resolved(
        resolved=resolved,
        primary=" MCP ",
        secondary=" ",
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        timeout_seconds=3,
        user_id="u",
        app="ace-lite",
        limit=0,
    )

    assert payload["primary"] == "mcp"
    assert payload["secondary"] == "none"
    assert payload["memory_strategy"] == "hybrid"
    assert payload["memory_hybrid_limit"] == 1
    assert payload["memory_cache_ttl_seconds"] == 1
    assert payload["memory_cache_max_entries"] == 16
    assert payload["memory_notes_path"] == "context-map/memory_notes.jsonl"
    assert payload["memory_notes_limit"] == 1
    assert payload["memory_notes_mode"] == "prefer_local"
    assert payload["memory_notes_ttl_days"] == 1
    assert payload["memory_notes_max_age_days"] == 1
    assert payload["limit"] == 1


def test_build_run_plan_kwargs_from_resolved_includes_explicit_and_grouped_fields() -> None:
    resolved = _make_resolved()

    payload = build_run_plan_kwargs_from_resolved(
        resolved=resolved,
        skills_dir="skills",
        retrieval_policy="feature",
    )

    assert payload["memory_config"] == {"strategy": "hybrid"}
    assert payload["memory_disclosure_mode"] == "compact"
    assert payload["memory_gate_mode"] == "auto"
    assert payload["memory_capture_keywords"] == ["alpha", "beta"]
    assert payload["skills_config"] == {"dir": "skills", "top_n": 4}
    assert payload["index_config"] == {"cache_path": "context-map/index.json"}
    assert payload["embedding_enabled"] is True
    assert payload["embedding_dimension"] == 1024
    assert payload["retrieval_policy"] == "feature"
    assert payload["tests_config"] == {"sbfl_metric": "ochiai"}
    assert payload["scip_enabled"] is True
    assert payload["trace_export_enabled"] is True


def test_build_orchestrator_kwargs_from_resolved_keeps_benchmark_shape() -> None:
    resolved = _make_resolved()

    payload = build_orchestrator_kwargs_from_resolved(
        resolved=resolved,
        skills_dir="skills",
        retrieval_policy="refactor",
    )

    assert payload["skills_dir"] == "skills"
    assert payload["skills_config"] == {"dir": "skills", "top_n": 4}
    assert payload["embeddings_config"] == {"enabled": True, "provider": "ollama"}
    assert payload["retrieval_policy"] == "refactor"
    assert payload["tests_config"] == {"sbfl_metric": "ochiai"}
    assert payload["trace_config"] == {"export_enabled": True}
    assert "memory_config" not in payload
    assert "embedding_enabled" not in payload


def test_runtime_payload_builders_share_canonical_config_slice() -> None:
    resolved = _make_resolved()

    run_plan_payload = build_run_plan_kwargs_from_resolved(
        resolved=resolved,
        skills_dir="skills",
        retrieval_policy="feature",
    )
    orchestrator_payload = build_orchestrator_kwargs_from_resolved(
        resolved=resolved,
        skills_dir="skills",
        retrieval_policy="feature",
    )

    assert {key: run_plan_payload[key] for key in SHARED_RUNTIME_PAYLOAD_KEYS} == {
        key: orchestrator_payload[key] for key in SHARED_RUNTIME_PAYLOAD_KEYS
    }


def test_shared_runtime_payload_keys_exclude_run_plan_and_orchestrator_only_fields() -> None:
    for key in (
        "skills_config",
        "index_config",
        "embeddings_config",
        "adaptive_router_config",
        "plan_replay_cache_config",
        "retrieval_config",
        "chunking_config",
        "trace_config",
        "retrieval_policy",
        "policy_version",
    ):
        assert key in SHARED_RUNTIME_PAYLOAD_KEYS

    for key in (
        "memory_config",
        "embedding_enabled",
        "junit_xml",
        "trace_export_enabled",
        "skills_dir",
    ):
        assert key not in SHARED_RUNTIME_PAYLOAD_KEYS


def test_runtime_payload_builders_preserve_grouped_runtime_contracts() -> None:
    resolved = _make_resolved()
    resolved["skills"] = {"top_n": 4, "manifest": "context-map/skills.json"}
    resolved["retrieval"] = {
        "top_k_files": 6,
        "candidate_ranker": "rrf_hybrid",
        "adaptive_router": {"enabled": True},
    }
    resolved["adaptive_router"] = {
        "enabled": True,
        "mode": "shadow",
        "arm_set": "retrieval_policy_shadow",
    }
    resolved["plan_replay_cache"] = {
        "enabled": True,
        "cache_path": "context-map/plan-replay/cache.json",
    }
    resolved["chunk"] = {
        "top_k": 11,
        "guard": {"enabled": True, "mode": "report_only"},
        "topological_shield": {"enabled": True, "mode": "report_only"},
    }
    resolved["trace"] = {
        "export_enabled": True,
        "export_path": "context-map/traces/stage_spans.jsonl",
    }

    run_plan_payload = build_run_plan_kwargs_from_resolved(
        resolved=resolved,
        skills_dir="custom-skills",
        retrieval_policy="feature",
    )
    orchestrator_payload = build_orchestrator_kwargs_from_resolved(
        resolved=resolved,
        skills_dir="custom-skills",
        retrieval_policy="feature",
    )

    for payload in (run_plan_payload, orchestrator_payload):
        assert payload["skills_config"] == {
            "dir": "custom-skills",
            "top_n": 4,
            "manifest": "context-map/skills.json",
        }
        assert payload["retrieval_config"] == {
            "top_k_files": 6,
            "candidate_ranker": "rrf_hybrid",
            "adaptive_router": {"enabled": True},
        }
        assert payload["adaptive_router_config"] == {
            "enabled": True,
            "mode": "shadow",
            "arm_set": "retrieval_policy_shadow",
        }
        assert payload["plan_replay_cache_config"] == {
            "enabled": True,
            "cache_path": "context-map/plan-replay/cache.json",
        }
        assert payload["chunking_config"] == {
            "top_k": 11,
            "guard": {"enabled": True, "mode": "report_only"},
            "topological_shield": {"enabled": True, "mode": "report_only"},
        }
        assert payload["trace_config"] == {
            "export_enabled": True,
            "export_path": "context-map/traces/stage_spans.jsonl",
        }
        assert payload["retrieval_policy"] == "feature"
        assert payload["policy_version"] == "v2"

    assert run_plan_payload["skills_config"] is not resolved["skills"]
    assert run_plan_payload["retrieval_config"] is not resolved["retrieval"]
    assert run_plan_payload["chunking_config"] is not resolved["chunk"]
    assert run_plan_payload["trace_config"] is not resolved["trace"]
