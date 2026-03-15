from __future__ import annotations

from typing import Any

import ace_lite.cli_app.orchestrator_factory as orchestrator_factory


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def plan(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        return {"ok": True, "query": kwargs["query"]}


def test_run_plan_prefers_grouped_internal_forwarding(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    fake_orchestrator = _FakeOrchestrator()

    def fake_create_orchestrator(**kwargs: Any) -> _FakeOrchestrator:
        captured.update(kwargs)
        return fake_orchestrator

    monkeypatch.setattr(
        orchestrator_factory,
        "create_orchestrator",
        fake_create_orchestrator,
    )

    retrieval_config = {
        "top_k_files": 5,
        "min_candidate_score": 4,
        "candidate_relative_threshold": 0.2,
        "candidate_ranker": "bm25_lite",
        "exact_search_enabled": True,
        "deterministic_refine_enabled": False,
        "exact_search_time_budget_ms": 90,
        "exact_search_max_paths": 7,
        "hybrid_re2_fusion_mode": "rrf",
        "hybrid_re2_rrf_k": 75,
        "hybrid_re2_bm25_weight": 0.4,
        "hybrid_re2_heuristic_weight": 0.35,
        "hybrid_re2_coverage_weight": 0.25,
        "hybrid_re2_combined_scale": 1.2,
        "retrieval_policy": "feature",
        "policy_version": "v2",
    }
    adaptive_router_config = {
        "enabled": True,
        "mode": "shadow",
        "model_path": "context-map/router/custom-model.json",
        "state_path": "context-map/router/custom-state.json",
        "arm_set": "retrieval_policy_shadow",
    }
    plugins_config = {
        "enabled": False,
        "remote_slot_policy_mode": "warn",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }
    repomap_config = {
        "enabled": False,
        "top_k": 4,
        "neighbor_limit": 11,
        "budget_tokens": 420,
        "ranking_profile": "graph_seeded",
        "signal_weights": {"imports": 1.5, "cochange": 0.75},
    }
    lsp_config = {
        "enabled": True,
        "top_n": 9,
        "commands": {"python": ["pylsp"]},
        "xref_enabled": True,
        "xref_top_n": 6,
        "time_budget_ms": 2200,
        "xref_commands": {"python": ["pylsp-xref"]},
    }
    trace_config = {
        "export_enabled": True,
        "export_path": "context-map/traces/custom-trace.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
        "otlp_timeout_seconds": 2.5,
    }
    plan_replay_cache_config = {
        "enabled": True,
        "cache_path": "custom/plan-replay/cache.json",
    }
    chunking_config = {
        "top_k": 5,
        "per_file_limit": 2,
        "disclosure": "signature",
        "signature": True,
        "token_budget": 640,
        "snippet": {
            "max_lines": 9,
            "max_chars": 420,
        },
        "topological_shield": {
            "enabled": True,
            "mode": "report_only",
            "max_attenuation": 0.6,
            "shared_parent_attenuation": 0.2,
            "adjacency_attenuation": 0.5,
        },
        "guard": {
            "enabled": True,
            "mode": "report_only",
        },
    }
    tokenizer_config = {
        "model": "gpt-4.1-mini",
    }
    skills_config = {
        "dir": "custom-skills",
        "precomputed_routing_enabled": False,
        "top_n": 5,
    }
    index_config = {
        "languages": ["python", "go"],
        "cache_path": "context-map/custom-index.json",
        "incremental": False,
        "conventions_files": ["STYLE.md"],
    }
    embeddings_config = {
        "enabled": True,
        "provider": "ollama",
        "model": "bge-m3",
        "dimension": 1024,
        "index_path": "context-map/embeddings/custom.json",
        "rerank_pool": 32,
        "lexical_weight": 0.55,
        "semantic_weight": 0.45,
        "min_similarity": 0.1,
        "fail_open": False,
    }
    cochange_config = {
        "enabled": False,
        "cache_path": "context-map/cochange/custom.json",
        "lookback_commits": 128,
        "half_life_days": 14.0,
        "top_neighbors": 6,
        "boost_weight": 0.75,
    }
    tests_config = {
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl_json": "artifacts/sbfl.json",
        "sbfl_metric": "tarantula",
    }
    scip_config = {
        "enabled": True,
        "index_path": "context-map/scip/custom-index.json",
        "provider": "scip",
        "generate_fallback": False,
    }
    memory_config = {
        "disclosure_mode": "full",
        "preview_max_chars": 320,
        "strategy": "semantic",
        "timeline": {"enabled": False},
        "gate": {"enabled": True, "mode": "never"},
        "profile": {
            "enabled": True,
            "path": "profile.json",
            "top_n": 6,
            "token_budget": 240,
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
            "hard_min_score": 0.2,
            "diversity_similarity_threshold": 0.75,
        },
    }

    result = orchestrator_factory.run_plan(
        query="q",
        repo="demo",
        root=".",
        memory_config=memory_config,
        skills_config=skills_config,
        index_config=index_config,
        embeddings_config=embeddings_config,
        cochange_config=cochange_config,
        tests_config=tests_config,
        scip_config=scip_config,
        chunking_config=chunking_config,
        tokenizer_config=tokenizer_config,
        retrieval_config=retrieval_config,
        adaptive_router_config=adaptive_router_config,
        plugins_config=plugins_config,
        repomap_config=repomap_config,
        lsp_config=lsp_config,
        trace_config=trace_config,
        plan_replay_cache_config=plan_replay_cache_config,
    )

    assert result == {"ok": True, "query": "q"}
    assert captured["memory_config"] == memory_config
    assert captured["skills_config"] == skills_config
    assert captured["index_config"] == index_config
    assert captured["embeddings_config"] == embeddings_config
    assert captured["cochange_config"] == cochange_config
    assert captured["tests_config"] == tests_config
    assert captured["scip_config"] == scip_config
    assert captured["chunking_config"] == chunking_config
    assert captured["tokenizer_config"] == tokenizer_config
    assert fake_orchestrator.calls == [
        {
            "query": "q",
            "repo": "demo",
            "root": ".",
            "time_range": None,
            "start_date": None,
            "end_date": None,
        }
    ]
    assert captured["retrieval_config"] == retrieval_config
    assert captured["adaptive_router_config"] == adaptive_router_config
    assert captured["plugins_config"] == plugins_config
    assert captured["repomap_config"] == repomap_config
    assert captured["lsp_config"] == lsp_config
    assert captured["trace_config"] == trace_config
    assert captured["plan_replay_cache_config"] == plan_replay_cache_config
    assert set(captured) == {
        "memory_client",
        "memory_provider",
        "memory_config",
        "skills_config",
        "index_config",
        "embeddings_config",
        "cochange_config",
        "tests_config",
        "scip_config",
        "chunking_config",
        "tokenizer_config",
        "retrieval_config",
        "adaptive_router_config",
        "plugins_config",
        "repomap_config",
        "lsp_config",
        "trace_config",
        "plan_replay_cache_config",
    }

    for key in (
        "top_k_files",
        "min_candidate_score",
        "candidate_relative_threshold",
        "candidate_ranker",
        "exact_search_enabled",
        "deterministic_refine_enabled",
        "exact_search_time_budget_ms",
        "exact_search_max_paths",
        "hybrid_re2_fusion_mode",
        "hybrid_re2_rrf_k",
        "hybrid_re2_bm25_weight",
        "hybrid_re2_heuristic_weight",
        "hybrid_re2_coverage_weight",
        "hybrid_re2_combined_scale",
        "retrieval_policy",
        "policy_version",
        "adaptive_router_enabled",
        "adaptive_router_mode",
        "adaptive_router_model_path",
        "adaptive_router_state_path",
        "adaptive_router_arm_set",
        "plugins_enabled",
        "remote_slot_policy_mode",
        "remote_slot_allowlist",
        "repomap_enabled",
        "repomap_top_k",
        "repomap_neighbor_limit",
        "repomap_budget_tokens",
        "repomap_ranking_profile",
        "repomap_signal_weights",
        "lsp_enabled",
        "lsp_top_n",
        "lsp_commands",
        "lsp_xref_enabled",
        "lsp_xref_top_n",
        "lsp_time_budget_ms",
        "lsp_xref_commands",
        "trace_export_enabled",
        "trace_export_path",
        "trace_otlp_enabled",
        "trace_otlp_endpoint",
        "trace_otlp_timeout_seconds",
        "plan_replay_cache_enabled",
        "plan_replay_cache_path",
        "memory_disclosure_mode",
        "memory_preview_max_chars",
        "memory_strategy",
        "memory_gate_enabled",
        "memory_gate_mode",
        "memory_timeline_enabled",
        "memory_profile_enabled",
        "memory_profile_top_n",
        "memory_capture_enabled",
        "memory_notes_mode",
        "memory_postprocess_hard_min_score",
        "skills_dir",
        "precomputed_skills_routing_enabled",
        "index_languages",
        "index_cache_path",
        "index_incremental",
        "conventions_files",
        "embedding_enabled",
        "embedding_provider",
        "embedding_model",
        "embedding_dimension",
        "embedding_index_path",
        "embedding_rerank_pool",
        "embedding_lexical_weight",
        "embedding_semantic_weight",
        "embedding_min_similarity",
        "embedding_fail_open",
        "cochange_enabled",
        "cochange_cache_path",
        "cochange_lookback_commits",
        "cochange_half_life_days",
        "cochange_top_neighbors",
        "cochange_boost_weight",
        "junit_xml",
        "coverage_json",
        "sbfl_json",
        "sbfl_metric",
        "scip_enabled",
        "scip_index_path",
        "scip_provider",
        "scip_generate_fallback",
        "chunk_top_k",
        "chunk_per_file_limit",
        "chunk_disclosure",
        "chunk_signature",
        "chunk_snippet_max_lines",
        "chunk_snippet_max_chars",
        "chunk_token_budget",
        "chunk_guard_enabled",
        "chunk_guard_mode",
        "chunk_guard_lambda_penalty",
        "chunk_guard_min_pool",
        "chunk_guard_max_pool",
        "chunk_guard_min_marginal_utility",
        "chunk_guard_compatibility_min_overlap",
        "chunk_diversity_enabled",
        "chunk_diversity_path_penalty",
        "chunk_diversity_symbol_family_penalty",
        "chunk_diversity_kind_penalty",
        "chunk_diversity_locality_penalty",
        "chunk_diversity_locality_window",
        "tokenizer_model",
    ):
        assert key not in captured


def test_run_plan_preserves_grouped_payloads_when_conflicting_flat_values_are_also_passed(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}
    fake_orchestrator = _FakeOrchestrator()

    def fake_create_orchestrator(**kwargs: Any) -> _FakeOrchestrator:
        captured.update(kwargs)
        return fake_orchestrator

    monkeypatch.setattr(
        orchestrator_factory,
        "create_orchestrator",
        fake_create_orchestrator,
    )

    retrieval_config = {
        "top_k_files": 5,
        "candidate_ranker": "bm25_lite",
        "adaptive_router": {
            "enabled": True,
            "mode": "shadow",
            "model_path": "context-map/router/nested-model.json",
            "state_path": "context-map/router/nested-state.json",
            "arm_set": "retrieval_policy_nested",
        },
    }
    tests_config = {
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl": {
            "json_path": "artifacts/sbfl.json",
            "metric": "dstar",
        },
    }
    trace_config = {
        "export_enabled": True,
        "export_path": "context-map/traces/custom-trace.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/custom-otlp.json",
        "otlp_timeout_seconds": 2.5,
    }
    plan_replay_cache_config = {
        "enabled": True,
        "cache_path": "custom/plan-replay/cache.json",
    }

    result = orchestrator_factory.run_plan(
        query="q",
        repo="demo",
        root=".",
        retrieval_config=retrieval_config,
        tests_config=tests_config,
        trace_config=trace_config,
        plan_replay_cache_config=plan_replay_cache_config,
        top_k_files=99,
        candidate_ranker="heuristic",
        sbfl_json="artifacts/flat-sbfl.json",
        sbfl_metric="ochiai",
        trace_export_path="context-map/traces/flat-trace.jsonl",
        plan_replay_cache_path="flat/plan-replay/cache.json",
    )

    assert result == {"ok": True, "query": "q"}
    assert captured["retrieval_config"] == retrieval_config
    assert captured["tests_config"] == tests_config
    assert captured["trace_config"] == trace_config
    assert captured["plan_replay_cache_config"] == plan_replay_cache_config
    assert "adaptive_router_config" not in captured

    for key in (
        "top_k_files",
        "candidate_ranker",
        "sbfl_json",
        "sbfl_metric",
        "trace_export_path",
        "plan_replay_cache_path",
    ):
        assert key not in captured


def test_run_plan_preserves_flat_forwarding_without_grouped_payloads(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    fake_orchestrator = _FakeOrchestrator()

    def fake_create_orchestrator(**kwargs: Any) -> _FakeOrchestrator:
        captured.update(kwargs)
        return fake_orchestrator

    monkeypatch.setattr(
        orchestrator_factory,
        "create_orchestrator",
        fake_create_orchestrator,
    )

    result = orchestrator_factory.run_plan(
        query="q",
        repo="demo",
        root=".",
        memory_disclosure_mode="full",
        memory_preview_max_chars=320,
        memory_strategy="semantic",
        memory_gate_enabled=True,
        memory_gate_mode="never",
        memory_timeline_enabled=False,
        memory_profile_enabled=True,
        memory_profile_top_n=6,
        memory_capture_enabled=True,
        memory_capture_keywords=["alpha", "beta"],
        memory_notes_enabled=True,
        memory_notes_mode="prefer_local",
        memory_postprocess_enabled=True,
        memory_postprocess_hard_min_score=0.2,
        top_k_files=6,
        min_candidate_score=3,
        candidate_relative_threshold=0.1,
        candidate_ranker="rrf_hybrid",
        exact_search_enabled=True,
        exact_search_time_budget_ms=120,
        exact_search_max_paths=12,
        retrieval_policy="feature",
        policy_version="v2",
        adaptive_router_enabled=True,
        adaptive_router_mode="shadow",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_shadow",
        plugins_enabled=False,
        remote_slot_policy_mode="warn",
        remote_slot_allowlist=["observability.mcp_plugins"],
        repomap_enabled=False,
        repomap_top_k=4,
        repomap_neighbor_limit=11,
        repomap_budget_tokens=420,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights={"imports": 1.5},
        lsp_enabled=True,
        lsp_top_n=9,
        lsp_commands={"python": ["pylsp"]},
        lsp_xref_enabled=True,
        lsp_xref_top_n=6,
        lsp_time_budget_ms=2200,
        lsp_xref_commands={"python": ["pylsp-xref"]},
        trace_export_enabled=True,
        trace_export_path="context-map/traces/custom-trace.jsonl",
        trace_otlp_enabled=True,
        trace_otlp_endpoint="file://context-map/traces/trace-otlp.json",
        trace_otlp_timeout_seconds=2.5,
        plan_replay_cache_enabled=True,
        plan_replay_cache_path="custom/plan-replay/cache.json",
    )

    assert result == {"ok": True, "query": "q"}
    assert fake_orchestrator.calls == [
        {
            "query": "q",
            "repo": "demo",
            "root": ".",
            "time_range": None,
            "start_date": None,
            "end_date": None,
        }
    ]
    assert captured["top_k_files"] == 6
    assert captured["min_candidate_score"] == 3
    assert captured["candidate_relative_threshold"] == 0.1
    assert captured["candidate_ranker"] == "rrf_hybrid"
    assert captured["exact_search_enabled"] is True
    assert captured["exact_search_time_budget_ms"] == 120
    assert captured["exact_search_max_paths"] == 12
    assert captured["retrieval_policy"] == "feature"
    assert captured["policy_version"] == "v2"
    assert captured["adaptive_router_enabled"] is True
    assert captured["adaptive_router_mode"] == "shadow"
    assert captured["adaptive_router_model_path"] == "context-map/router/model.json"
    assert captured["adaptive_router_state_path"] == "context-map/router/state.json"
    assert captured["adaptive_router_arm_set"] == "retrieval_policy_shadow"
    assert captured["plugins_enabled"] is False
    assert captured["remote_slot_policy_mode"] == "warn"
    assert captured["remote_slot_allowlist"] == ["observability.mcp_plugins"]
    assert captured["repomap_enabled"] is False
    assert captured["repomap_top_k"] == 4
    assert captured["repomap_neighbor_limit"] == 11
    assert captured["repomap_budget_tokens"] == 420
    assert captured["repomap_ranking_profile"] == "graph_seeded"
    assert captured["repomap_signal_weights"] == {"imports": 1.5}
    assert captured["lsp_enabled"] is True
    assert captured["lsp_top_n"] == 9
    assert captured["lsp_commands"] == {"python": ["pylsp"]}
    assert captured["lsp_xref_enabled"] is True
    assert captured["lsp_xref_top_n"] == 6
    assert captured["lsp_time_budget_ms"] == 2200
    assert captured["lsp_xref_commands"] == {"python": ["pylsp-xref"]}
    assert captured["trace_export_enabled"] is True
    assert captured["trace_export_path"] == "context-map/traces/custom-trace.jsonl"
    assert captured["trace_otlp_enabled"] is True
    assert (
        captured["trace_otlp_endpoint"]
        == "file://context-map/traces/trace-otlp.json"
    )
    assert captured["trace_otlp_timeout_seconds"] == 2.5
    assert captured["plan_replay_cache_enabled"] is True
    assert captured["plan_replay_cache_path"] == "custom/plan-replay/cache.json"
    assert captured["memory_disclosure_mode"] == "full"
    assert captured["memory_preview_max_chars"] == 320
    assert captured["memory_strategy"] == "semantic"
    assert captured["memory_gate_enabled"] is True
    assert captured["memory_gate_mode"] == "never"
    assert captured["memory_timeline_enabled"] is False
    assert captured["memory_profile_enabled"] is True
    assert captured["memory_profile_top_n"] == 6
    assert captured["memory_capture_enabled"] is True
    assert captured["memory_capture_keywords"] == ["alpha", "beta"]
    assert captured["memory_notes_enabled"] is True
    assert captured["memory_notes_mode"] == "prefer_local"
    assert captured["memory_postprocess_enabled"] is True
    assert captured["memory_postprocess_hard_min_score"] == 0.2

    for key in (
        "memory_config",
        "skills_config",
        "index_config",
        "embeddings_config",
        "cochange_config",
        "tests_config",
        "scip_config",
        "chunking_config",
        "tokenizer_config",
        "retrieval_config",
        "adaptive_router_config",
        "plugins_config",
        "repomap_config",
        "lsp_config",
        "trace_config",
        "plan_replay_cache_config",
    ):
        assert key not in captured
