from __future__ import annotations

import click

from ace_lite.cli_app.config_resolve import _resolve_shared_plan_config


def _resolve_shared_plan(**config: object) -> dict[str, object]:
    ctx = click.Context(click.Command("unit"))
    return _resolve_shared_plan_config(
        ctx=ctx,
        config=config,
        namespace="plan",
        config_pack=None,
        retrieval_preset="none",
        adaptive_router_enabled=False,
        adaptive_router_mode="observe",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_v1",
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        embedding_enabled=False,
        embedding_provider="hash",
        embedding_model="hash-v1",
        embedding_dimension=256,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        languages="python",
        index_cache_path="context-map/index.json",
        index_incremental=True,
        conventions_files=(),
        plugins_enabled=True,
        remote_slot_policy_mode="strict",
        remote_slot_allowlist="",
        repomap_enabled=True,
        repomap_top_k=8,
        repomap_neighbor_limit=20,
        repomap_budget_tokens=800,
        repomap_ranking_profile="graph",
        repomap_signal_weights=None,
        lsp_enabled=False,
        lsp_top_n=5,
        lsp_cmds=(),
        lsp_xref_enabled=False,
        lsp_xref_top_n=3,
        lsp_time_budget_ms=1500,
        lsp_xref_cmds=(),
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
        precomputed_skills_routing_enabled=True,
        plan_replay_cache_enabled=False,
        plan_replay_cache_path="context-map/plan-replay/cache.json",
        memory_hybrid_limit=10,
        chunk_top_k=24,
        chunk_per_file_limit=3,
        chunk_disclosure="refs",
        chunk_signature=False,
        chunk_snippet_max_lines=18,
        chunk_snippet_max_chars=1200,
        chunk_token_budget=1200,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.20,
        chunk_diversity_symbol_family_penalty=0.30,
        chunk_diversity_kind_penalty=0.10,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
        tokenizer_model="gpt-4o-mini",
        cochange_enabled=True,
        cochange_cache_path="context-map/cochange.json",
        cochange_lookback_commits=400,
        cochange_half_life_days=60.0,
        cochange_top_neighbors=12,
        cochange_boost_weight=1.5,
        retrieval_policy="auto",
        policy_version="v1",
        junit_xml=None,
        coverage_json=None,
        sbfl_json=None,
        sbfl_metric="ochiai",
        scip_enabled=False,
        scip_index_path="context-map/scip/index.json",
        scip_provider="auto",
        scip_generate_fallback=True,
        trace_export_enabled=False,
        trace_export_path="context-map/traces/stage_spans.jsonl",
        trace_otlp_enabled=False,
        trace_otlp_endpoint="",
        trace_otlp_timeout_seconds=1.5,
    )


def test_resolve_shared_plan_config_reads_grouped_plan_replay_cache_fields() -> None:
    resolved = _resolve_shared_plan(
        plan={
            "plan_replay_cache": {
                "enabled": True,
                "cache_path": "custom/plan-replay/cache.json",
            }
        }
    )

    assert resolved["plan_replay_cache_enabled"] is True
    assert resolved["plan_replay_cache_path"] == "custom/plan-replay/cache.json"
    assert resolved["plan_replay_cache"] == {
        "enabled": True,
        "cache_path": "custom/plan-replay/cache.json",
    }


def test_resolve_shared_plan_config_emits_grouped_skills_payload() -> None:
    resolved = _resolve_shared_plan(
        plan={
            "skills": {
                "precomputed_routing_enabled": False,
            }
        }
    )

    assert resolved["precomputed_skills_routing_enabled"] is False
    assert resolved["skills"] == {
        "precomputed_routing_enabled": False,
    }


def test_resolve_shared_plan_grouped_and_flat_auxiliary_config_match() -> None:
    flat = _resolve_shared_plan(
        plan={
            "languages": ["python", "go"],
            "index_cache_path": "context-map/custom-index.json",
            "index_incremental": False,
            "conventions_files": ["STYLE.md"],
            "cochange_enabled": False,
            "cochange_cache_path": "context-map/cochange/custom.json",
            "cochange_lookback_commits": 128,
            "cochange_half_life_days": 14.0,
            "cochange_top_neighbors": 6,
            "cochange_boost_weight": 0.75,
            "junit_xml": "artifacts/junit.xml",
            "coverage_json": "artifacts/coverage.json",
            "sbfl": {
                "json_path": "artifacts/sbfl.json",
                "metric": "dstar",
            },
            "scip_enabled": True,
            "scip_index_path": "context-map/scip/custom-index.json",
            "scip_provider": "scip_lite",
            "scip_generate_fallback": False,
        }
    )
    grouped = _resolve_shared_plan(
        plan={
            "index": {
                "languages": ["python", "go"],
                "cache_path": "context-map/custom-index.json",
                "incremental": False,
                "conventions_files": ["STYLE.md"],
            },
            "cochange": {
                "enabled": False,
                "cache_path": "context-map/cochange/custom.json",
                "lookback_commits": 128,
                "half_life_days": 14.0,
                "top_neighbors": 6,
                "boost_weight": 0.75,
            },
            "tests": {
                "junit_xml": "artifacts/junit.xml",
                "coverage_json": "artifacts/coverage.json",
                "sbfl": {
                    "json_path": "artifacts/sbfl.json",
                    "metric": "dstar",
                },
            },
            "scip": {
                "enabled": True,
                "index_path": "context-map/scip/custom-index.json",
                "provider": "scip_lite",
                "generate_fallback": False,
            },
        }
    )

    for key in (
        "languages",
        "index_cache_path",
        "index_incremental",
        "conventions_files",
        "index",
        "cochange_enabled",
        "cochange_cache_path",
        "cochange_lookback_commits",
        "cochange_half_life_days",
        "cochange_top_neighbors",
        "cochange_boost_weight",
        "cochange",
        "junit_xml",
        "coverage_json",
        "sbfl_json",
        "sbfl_metric",
        "tests",
        "scip_enabled",
        "scip_index_path",
        "scip_provider",
        "scip_generate_fallback",
        "scip",
    ):
        assert grouped[key] == flat[key]
