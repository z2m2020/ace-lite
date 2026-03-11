from __future__ import annotations

from ace_lite.cli_app.orchestrator_factory import create_orchestrator


def test_create_orchestrator_plumbs_memory_gate_config() -> None:
    orchestrator = create_orchestrator(
        memory_gate_enabled=False,
        memory_gate_mode="never",
    )
    assert orchestrator.config.memory.gate.enabled is False
    assert orchestrator.config.memory.gate.mode == "never"


def test_create_orchestrator_plumbs_memory_postprocess_config() -> None:
    orchestrator = create_orchestrator(
        memory_postprocess_enabled=True,
        memory_postprocess_time_decay_half_life_days=12.5,
        memory_postprocess_hard_min_score=0.25,
        memory_postprocess_diversity_similarity_threshold=0.8,
    )
    assert orchestrator.config.memory.postprocess.enabled is True
    assert orchestrator.config.memory.postprocess.time_decay_half_life_days == 12.5
    assert orchestrator.config.memory.postprocess.hard_min_score == 0.25
    assert orchestrator.config.memory.postprocess.diversity_similarity_threshold == 0.8


def test_create_orchestrator_accepts_grouped_memory_config() -> None:
    orchestrator = create_orchestrator(
        memory_config={
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
    )

    assert orchestrator.config.memory.disclosure_mode == "full"
    assert orchestrator.config.memory.preview_max_chars == 320
    assert orchestrator.config.memory.strategy == "semantic"
    assert orchestrator.config.memory.timeline_enabled is False
    assert orchestrator.config.memory.gate.enabled is True
    assert orchestrator.config.memory.gate.mode == "never"
    assert orchestrator.config.memory.namespace.container_tag == "repo"
    assert orchestrator.config.memory.namespace.auto_tag_mode == "user"
    assert orchestrator.config.memory.profile.enabled is True
    assert orchestrator.config.memory.profile.path == "profile.json"
    assert orchestrator.config.memory.profile.top_n == 6
    assert orchestrator.config.memory.feedback.max_entries == 64
    assert orchestrator.config.memory.capture.keywords == ("alpha", "beta")
    assert orchestrator.config.memory.notes.mode == "prefer_local"
    assert orchestrator.config.memory.postprocess.enabled is True
    assert orchestrator.config.memory.postprocess.noise_filter_enabled is False
    assert orchestrator.config.memory.postprocess.time_decay_half_life_days == 12.5


def test_create_orchestrator_flat_memory_values_override_grouped_defaults() -> None:
    orchestrator = create_orchestrator(
        memory_config={
            "gate": {"enabled": True, "mode": "never"},
            "profile": {
                "enabled": True,
                "top_n": 6,
            },
            "postprocess": {
                "enabled": True,
                "hard_min_score": 0.4,
            },
        },
        memory_gate_mode="always",
        memory_profile_top_n=9,
        memory_postprocess_hard_min_score=0.6,
    )

    assert orchestrator.config.memory.gate.enabled is True
    assert orchestrator.config.memory.gate.mode == "always"
    assert orchestrator.config.memory.profile.enabled is True
    assert orchestrator.config.memory.profile.top_n == 9
    assert orchestrator.config.memory.postprocess.enabled is True
    assert orchestrator.config.memory.postprocess.hard_min_score == 0.6


def test_create_orchestrator_plumbs_deterministic_refine_config() -> None:
    orchestrator = create_orchestrator(deterministic_refine_enabled=False)

    assert orchestrator.config.retrieval.deterministic_refine_enabled is False


def test_create_orchestrator_accepts_grouped_chunking_and_tokenizer_config() -> None:
    orchestrator = create_orchestrator(
        chunking_config={
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
        },
        tokenizer_config={"model": "gpt-4.1-mini"},
    )

    assert orchestrator.config.chunking.top_k == 5
    assert orchestrator.config.chunking.per_file_limit == 2
    assert orchestrator.config.chunking.disclosure == "signature"
    assert orchestrator.config.chunking.signature is True
    assert orchestrator.config.chunking.token_budget == 640
    assert orchestrator.config.chunking.snippet_max_lines == 9
    assert orchestrator.config.chunking.snippet_max_chars == 420
    assert orchestrator.config.chunking.topological_shield.enabled is True
    assert orchestrator.config.chunking.topological_shield.mode == "report_only"
    assert orchestrator.config.chunking.guard.enabled is True
    assert orchestrator.config.chunking.guard.mode == "report_only"
    assert orchestrator.config.tokenizer.model == "gpt-4.1-mini"


def test_create_orchestrator_flat_chunking_values_override_grouped_defaults() -> None:
    orchestrator = create_orchestrator(
        chunking_config={
            "top_k": 5,
            "guard": {
                "mode": "report_only",
            },
        },
        chunk_top_k=7,
        chunk_guard_mode="enforce",
    )

    assert orchestrator.config.chunking.top_k == 7
    assert orchestrator.config.chunking.guard.mode == "enforce"


def test_create_orchestrator_accepts_grouped_retrieval_and_router_config() -> None:
    orchestrator = create_orchestrator(
        retrieval_config={
            "top_k_files": 5,
            "min_candidate_score": 4,
            "candidate_relative_threshold": 0.25,
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
        },
        adaptive_router_config={
            "enabled": True,
            "mode": "shadow",
            "model_path": "context-map/router/custom-model.json",
            "state_path": "context-map/router/custom-state.json",
            "arm_set": "retrieval_policy_shadow",
            "online_bandit": {"enabled": True, "experiment_enabled": True},
        },
    )

    assert orchestrator.config.retrieval.top_k_files == 5
    assert orchestrator.config.retrieval.min_candidate_score == 4
    assert orchestrator.config.retrieval.candidate_relative_threshold == 0.25
    assert orchestrator.config.retrieval.candidate_ranker == "bm25_lite"
    assert orchestrator.config.retrieval.exact_search_enabled is True
    assert orchestrator.config.retrieval.deterministic_refine_enabled is False
    assert orchestrator.config.retrieval.exact_search_time_budget_ms == 90
    assert orchestrator.config.retrieval.exact_search_max_paths == 7
    assert orchestrator.config.retrieval.hybrid_re2_fusion_mode == "rrf"
    assert orchestrator.config.retrieval.hybrid_re2_rrf_k == 75
    assert orchestrator.config.retrieval.hybrid_re2_bm25_weight == 0.4
    assert orchestrator.config.retrieval.hybrid_re2_heuristic_weight == 0.35
    assert orchestrator.config.retrieval.hybrid_re2_coverage_weight == 0.25
    assert orchestrator.config.retrieval.hybrid_re2_combined_scale == 1.2
    assert orchestrator.config.retrieval.retrieval_policy == "feature"
    assert orchestrator.config.retrieval.policy_version == "v2"
    assert orchestrator.config.retrieval.adaptive_router_enabled is True
    assert orchestrator.config.retrieval.adaptive_router_mode == "shadow"
    assert (
        orchestrator.config.retrieval.adaptive_router_model_path
        == "context-map/router/custom-model.json"
    )
    assert (
        orchestrator.config.retrieval.adaptive_router_state_path
        == "context-map/router/custom-state.json"
    )
    assert (
        orchestrator.config.retrieval.adaptive_router_arm_set
        == "retrieval_policy_shadow"
    )
    assert orchestrator.config.retrieval.adaptive_router_online_bandit_enabled is True
    assert (
        orchestrator.config.retrieval.adaptive_router_online_bandit_experiment_enabled
        is True
    )


def test_create_orchestrator_accepts_nested_adaptive_router_inside_retrieval_config() -> None:
    orchestrator = create_orchestrator(
        retrieval_config={
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
    )

    assert orchestrator.config.retrieval.top_k_files == 5
    assert orchestrator.config.retrieval.candidate_ranker == "bm25_lite"
    assert orchestrator.config.retrieval.adaptive_router_enabled is True
    assert orchestrator.config.retrieval.adaptive_router_mode == "shadow"
    assert (
        orchestrator.config.retrieval.adaptive_router_model_path
        == "context-map/router/nested-model.json"
    )
    assert (
        orchestrator.config.retrieval.adaptive_router_state_path
        == "context-map/router/nested-state.json"
    )
    assert (
        orchestrator.config.retrieval.adaptive_router_arm_set
        == "retrieval_policy_nested"
    )


def test_create_orchestrator_flat_retrieval_values_override_grouped_defaults() -> None:
    orchestrator = create_orchestrator(
        retrieval_config={
            "top_k_files": 5,
            "candidate_ranker": "bm25_lite",
            "retrieval_policy": "feature",
            "policy_version": "v2",
        },
        adaptive_router_config={
            "enabled": True,
            "mode": "shadow",
            "arm_set": "retrieval_policy_shadow",
        },
        top_k_files=7,
        candidate_ranker="hybrid_re2",
        retrieval_policy="general",
        policy_version="v9",
        adaptive_router_mode="enforce",
        adaptive_router_arm_set="retrieval_policy_enforce",
    )

    assert orchestrator.config.retrieval.top_k_files == 7
    assert orchestrator.config.retrieval.candidate_ranker == "hybrid_re2"
    assert orchestrator.config.retrieval.retrieval_policy == "general"
    assert orchestrator.config.retrieval.policy_version == "v9"
    assert orchestrator.config.retrieval.adaptive_router_enabled is True
    assert orchestrator.config.retrieval.adaptive_router_mode == "enforce"
    assert orchestrator.config.retrieval.adaptive_router_arm_set == "retrieval_policy_enforce"


def test_create_orchestrator_accepts_grouped_trace_and_replay_config() -> None:
    orchestrator = create_orchestrator(
        trace_config={
            "export_enabled": True,
            "export_path": "context-map/traces/custom-trace.jsonl",
            "otlp_enabled": True,
            "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
            "otlp_timeout_seconds": 2.5,
        },
        plan_replay_cache_config={
            "enabled": True,
            "cache_path": "custom/plan-replay/cache.json",
        },
    )

    assert orchestrator.config.trace.export_enabled is True
    assert orchestrator.config.trace.export_path == "context-map/traces/custom-trace.jsonl"
    assert orchestrator.config.trace.otlp_enabled is True
    assert orchestrator.config.trace.otlp_endpoint == "file://context-map/traces/trace-otlp.json"
    assert orchestrator.config.trace.otlp_timeout_seconds == 2.5
    assert orchestrator.config.plan_replay_cache.enabled is True
    assert orchestrator.config.plan_replay_cache.cache_path == "custom/plan-replay/cache.json"


def test_create_orchestrator_accepts_grouped_plugins_repomap_and_lsp_config() -> None:
    orchestrator = create_orchestrator(
        plugins_config={
            "enabled": False,
            "remote_slot_policy_mode": "warn",
            "remote_slot_allowlist": [
                "observability.mcp_plugins",
                "source_plan.writeback_template",
            ],
        },
        repomap_config={
            "enabled": False,
            "top_k": 4,
            "neighbor_limit": 11,
            "budget_tokens": 420,
            "ranking_profile": "graph_seeded",
            "signal_weights": {"imports": 1.5, "cochange": 0.75},
        },
        lsp_config={
            "enabled": True,
            "top_n": 9,
            "commands": {"python": ["pylsp"]},
            "xref_enabled": True,
            "xref_top_n": 6,
            "time_budget_ms": 2200,
            "xref_commands": {"python": ["pylsp-xref"]},
        },
    )

    assert orchestrator.config.plugins.enabled is False
    assert orchestrator.config.plugins.remote_slot_policy_mode == "warn"
    assert list(orchestrator.config.plugins.remote_slot_allowlist) == [
        "observability.mcp_plugins",
        "source_plan.writeback_template",
    ]
    assert orchestrator.config.repomap.enabled is False
    assert orchestrator.config.repomap.top_k == 4
    assert orchestrator.config.repomap.neighbor_limit == 11
    assert orchestrator.config.repomap.budget_tokens == 420
    assert orchestrator.config.repomap.ranking_profile == "graph_seeded"
    assert orchestrator.config.repomap.signal_weights == {
        "imports": 1.5,
        "cochange": 0.75,
    }
    assert orchestrator.config.lsp.enabled is True
    assert orchestrator.config.lsp.top_n == 9
    assert orchestrator.config.lsp.commands == {"python": ["pylsp"]}
    assert orchestrator.config.lsp.xref_enabled is True
    assert orchestrator.config.lsp.xref_top_n == 6
    assert orchestrator.config.lsp.time_budget_ms == 2200
    assert orchestrator.config.lsp.xref_commands == {"python": ["pylsp-xref"]}


def test_create_orchestrator_accepts_grouped_skills_index_embeddings_and_quality_signals() -> None:
    orchestrator = create_orchestrator(
        skills_config={
            "dir": "custom-skills",
            "precomputed_routing_enabled": False,
            "top_n": 5,
            "token_budget": 900,
        },
        index_config={
            "languages": ["python", "go"],
            "cache_path": "context-map/custom-index.json",
            "incremental": False,
            "conventions_files": ["STYLE.md"],
        },
        embeddings_config={
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
        },
        cochange_config={
            "enabled": False,
            "cache_path": "context-map/cochange/custom.json",
            "lookback_commits": 128,
            "half_life_days": 14.0,
            "top_neighbors": 6,
            "boost_weight": 0.75,
        },
        tests_config={
            "junit_xml": "artifacts/junit.xml",
            "coverage_json": "artifacts/coverage.json",
            "sbfl_json": "artifacts/sbfl.json",
            "sbfl_metric": "dstar",
        },
        scip_config={
            "enabled": True,
            "index_path": "context-map/scip/custom-index.json",
            "provider": "scip_lite",
            "generate_fallback": False,
        },
    )

    assert orchestrator.config.skills.dir == "custom-skills"
    assert orchestrator.config.skills.precomputed_routing_enabled is False
    assert orchestrator.config.skills.top_n == 5
    assert orchestrator.config.skills.token_budget == 900
    assert orchestrator.config.index.languages == ["python", "go"]
    assert orchestrator.config.index.cache_path == "context-map/custom-index.json"
    assert orchestrator.config.index.incremental is False
    assert orchestrator.config.index.conventions_files == ["STYLE.md"]
    assert orchestrator.config.embeddings.enabled is True
    assert orchestrator.config.embeddings.provider == "ollama"
    assert orchestrator.config.embeddings.model == "bge-m3"
    assert orchestrator.config.embeddings.dimension == 1024
    assert orchestrator.config.embeddings.index_path == "context-map/embeddings/custom.json"
    assert orchestrator.config.embeddings.rerank_pool == 32
    assert orchestrator.config.embeddings.lexical_weight == 0.55
    assert orchestrator.config.embeddings.semantic_weight == 0.45
    assert orchestrator.config.embeddings.min_similarity == 0.1
    assert orchestrator.config.embeddings.fail_open is False
    assert orchestrator.config.cochange.enabled is False
    assert orchestrator.config.cochange.cache_path == "context-map/cochange/custom.json"
    assert orchestrator.config.cochange.lookback_commits == 128
    assert orchestrator.config.cochange.half_life_days == 14.0
    assert orchestrator.config.cochange.top_neighbors == 6
    assert orchestrator.config.cochange.boost_weight == 0.75
    assert orchestrator.config.tests.junit_xml == "artifacts/junit.xml"
    assert orchestrator.config.tests.coverage_json == "artifacts/coverage.json"
    assert orchestrator.config.tests.sbfl_json == "artifacts/sbfl.json"
    assert orchestrator.config.tests.sbfl_metric == "dstar"
    assert orchestrator.config.scip.enabled is True
    assert orchestrator.config.scip.index_path == "context-map/scip/custom-index.json"
    assert orchestrator.config.scip.provider == "scip_lite"
    assert orchestrator.config.scip.generate_fallback is False


def test_create_orchestrator_accepts_tests_config_with_nested_sbfl_section() -> None:
    orchestrator = create_orchestrator(
        tests_config={
            "junit_xml": "artifacts/junit.xml",
            "coverage_json": "artifacts/coverage.json",
            "sbfl": {
                "json_path": "artifacts/sbfl.json",
                "metric": "dstar",
            },
        }
    )

    assert orchestrator.config.tests.junit_xml == "artifacts/junit.xml"
    assert orchestrator.config.tests.coverage_json == "artifacts/coverage.json"
    assert orchestrator.config.tests.sbfl_json == "artifacts/sbfl.json"
    assert orchestrator.config.tests.sbfl_metric == "dstar"


def test_create_orchestrator_flat_auxiliary_values_override_grouped_defaults() -> None:
    orchestrator = create_orchestrator(
        plugins_config={
            "enabled": True,
            "remote_slot_policy_mode": "off",
            "remote_slot_allowlist": ["observability.mcp_plugins"],
        },
        repomap_config={
            "enabled": True,
            "top_k": 4,
            "neighbor_limit": 11,
            "budget_tokens": 420,
            "ranking_profile": "graph_seeded",
            "signal_weights": {"imports": 1.5},
        },
        lsp_config={
            "enabled": False,
            "top_n": 2,
            "commands": {"python": ["pylsp"]},
            "xref_enabled": False,
            "xref_top_n": 1,
            "time_budget_ms": 1200,
            "xref_commands": {"python": ["pylsp-xref"]},
        },
        plugins_enabled=False,
        remote_slot_policy_mode="warn",
        remote_slot_allowlist=["source_plan.writeback_template"],
        repomap_enabled=False,
        repomap_top_k=9,
        repomap_neighbor_limit=21,
        repomap_budget_tokens=810,
        repomap_ranking_profile="heuristic",
        repomap_signal_weights={"imports": 2.0},
        lsp_enabled=True,
        lsp_top_n=6,
        lsp_commands={"python": ["basedpyright-langserver", "--stdio"]},
        lsp_xref_enabled=True,
        lsp_xref_top_n=4,
        lsp_time_budget_ms=1600,
        lsp_xref_commands={"python": ["basedpyright-xref"]},
    )

    assert orchestrator.config.plugins.enabled is False
    assert orchestrator.config.plugins.remote_slot_policy_mode == "warn"
    assert list(orchestrator.config.plugins.remote_slot_allowlist) == [
        "source_plan.writeback_template"
    ]
    assert orchestrator.config.repomap.enabled is False
    assert orchestrator.config.repomap.top_k == 9
    assert orchestrator.config.repomap.neighbor_limit == 21
    assert orchestrator.config.repomap.budget_tokens == 810
    assert orchestrator.config.repomap.ranking_profile == "heuristic"
    assert orchestrator.config.repomap.signal_weights == {"imports": 2.0}
    assert orchestrator.config.lsp.enabled is True
    assert orchestrator.config.lsp.top_n == 6
    assert orchestrator.config.lsp.commands == {
        "python": ["basedpyright-langserver", "--stdio"]
    }
    assert orchestrator.config.lsp.xref_enabled is True
    assert orchestrator.config.lsp.xref_top_n == 4
    assert orchestrator.config.lsp.time_budget_ms == 1600
    assert orchestrator.config.lsp.xref_commands == {
        "python": ["basedpyright-xref"]
    }


def test_create_orchestrator_flat_trace_and_replay_values_override_grouped_defaults() -> None:
    orchestrator = create_orchestrator(
        trace_config={
            "export_enabled": True,
            "export_path": "context-map/traces/custom-trace.jsonl",
            "otlp_enabled": True,
            "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
            "otlp_timeout_seconds": 2.5,
        },
        plan_replay_cache_config={
            "enabled": True,
            "cache_path": "custom/plan-replay/cache.json",
        },
        trace_export_path="context-map/traces/override-trace.jsonl",
        trace_otlp_timeout_seconds=4.0,
        plan_replay_cache_path="context-map/plan-replay/override-cache.json",
    )

    assert orchestrator.config.trace.export_enabled is True
    assert orchestrator.config.trace.export_path == "context-map/traces/override-trace.jsonl"
    assert orchestrator.config.trace.otlp_enabled is True
    assert orchestrator.config.trace.otlp_endpoint == "file://context-map/traces/trace-otlp.json"
    assert orchestrator.config.trace.otlp_timeout_seconds == 4.0
    assert orchestrator.config.plan_replay_cache.enabled is True
    assert (
        orchestrator.config.plan_replay_cache.cache_path
        == "context-map/plan-replay/override-cache.json"
    )
