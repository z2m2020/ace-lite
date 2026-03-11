from __future__ import annotations

from ace_lite.pipeline.stage_tags import build_stage_tags


def test_index_stage_tags_include_adaptive_router_metadata() -> None:
    tags = build_stage_tags(
        stage_name="index",
        output={
            "cache": {"hit": False},
            "candidate_files": [{"path": "src/app.py"}],
            "candidate_chunks": [],
            "chunk_metrics": {
                "candidate_chunk_count": 0,
                "chunk_budget_used": 0,
                "robust_signature_count": 1,
                "robust_signature_coverage_ratio": 1.0,
                "graph_prior_chunk_count": 1,
                "graph_prior_coverage_ratio": 0.5,
                "graph_prior_total": 0.18,
                "graph_seeded_chunk_count": 1,
                "graph_transfer_count": 2,
                "graph_hub_suppressed_chunk_count": 1,
                "graph_hub_penalty_total": 0.08,
                "graph_closure_enabled": 1.0,
                "graph_closure_boosted_chunk_count": 1,
                "graph_closure_coverage_ratio": 0.5,
                "graph_closure_anchor_count": 1,
                "graph_closure_support_edge_count": 2,
                "graph_closure_total": 0.12,
            },
            "chunk_guard": {
                "enabled": True,
                "mode": "report_only",
                "reason": "report_only",
                "candidate_pool": 2,
                "signed_chunk_count": 1,
                "filtered_count": 0,
                "retained_count": 2,
                "pairwise_conflict_count": 0,
                "max_conflict_penalty": 0.0,
                "report_only": True,
                "fallback": False,
            },
            "context_budget": {"chunk_budget_used": 0, "chunk_count": 0},
            "candidate_ranking": {"selected": "rrf_hybrid", "fallbacks": []},
            "docs": {"enabled": False},
            "parallel": {"enabled": False, "docs": {}, "worktree": {}},
            "prior_applied": {},
            "graph_lookup": {},
            "embeddings": {},
            "feedback": {},
            "worktree_prior": {},
            "multi_channel_fusion": {"enabled": False, "applied": False, "reason": ""},
            "adaptive_router": {
                "enabled": True,
                "mode": "shadow",
                "arm_set": "retrieval_policy_shadow",
                "arm_id": "feature",
                "source": "auto",
                "confidence": 0.0,
                "shadow_arm_id": "feature_graph",
                "shadow_confidence": 0.88,
                "online_bandit": {
                    "requested": True,
                    "experiment_enabled": True,
                    "eligible": True,
                    "active": False,
                    "reason": "eligible_pending_runtime",
                    "is_exploration": False,
                    "exploration_probability": 0.0,
                    "fallback_applied": True,
                    "fallback_reason": "heuristic_default",
                },
            },
            "policy_name": "feature",
            "policy_version": "v1",
        },
    )

    assert tags["router_enabled"] is True
    assert tags["router_mode"] == "shadow"
    assert tags["router_arm_set"] == "retrieval_policy_shadow"
    assert tags["router_arm_id"] == "feature"
    assert tags["router_source"] == "auto"
    assert tags["router_shadow_arm_id"] == "feature_graph"
    assert tags["router_shadow_confidence"] == 0.88
    assert tags["router_online_bandit_requested"] is True
    assert tags["router_experiment_enabled"] is True
    assert tags["router_online_bandit_eligible"] is True
    assert tags["router_online_bandit_active"] is False
    assert tags["router_is_exploration"] is False
    assert tags["router_exploration_probability"] == 0.0
    assert tags["router_fallback_applied"] is True
    assert tags["router_fallback_reason"] == "heuristic_default"
    assert tags["router_online_bandit_reason"] == "eligible_pending_runtime"
    assert tags["chunk_guard_enabled"] is True
    assert tags["chunk_guard_mode"] == "report_only"
    assert tags["chunk_guard_candidate_pool"] == 2
    assert tags["robust_signature_count"] == 1
    assert tags["robust_signature_coverage_ratio"] == 1.0
    assert tags["graph_prior_chunk_count"] == 1
    assert tags["graph_prior_coverage_ratio"] == 0.5
    assert tags["graph_transfer_count"] == 2
    assert tags["graph_hub_suppressed_chunk_count"] == 1
    assert tags["graph_closure_enabled"] is True
    assert tags["graph_closure_boosted_chunk_count"] == 1
    assert tags["graph_closure_coverage_ratio"] == 0.5
    assert tags["graph_closure_anchor_count"] == 1
    assert tags["graph_closure_support_edge_count"] == 2
    assert tags["graph_closure_total"] == 0.12


def test_source_plan_stage_tags_include_packing_observability() -> None:
    tags = build_stage_tags(
        stage_name="source_plan",
        output={
            "diagnostics": [],
            "constraints": ["keep deterministic ordering"],
            "steps": [{"stage": "source_plan"}],
            "candidate_chunks": [{"path": "src/a.py"}],
            "chunk_steps": [{"chunk_ref": {"path": "src/a.py"}}],
            "validation_tests": ["pytest -q tests/unit/test_source_plan_properties.py"],
            "chunk_budget_used": 88.0,
            "packing": {
                "graph_closure_preference_enabled": True,
                "graph_closure_bonus_candidate_count": 2,
                "graph_closure_preferred_count": 1,
                "focused_file_promoted_count": 3,
                "packed_path_count": 3,
                "reason": "ok",
            },
            "policy_name": "general",
            "policy_version": "v1",
        },
    )

    assert tags["packing_graph_closure_preference_enabled"] is True
    assert tags["packing_graph_closure_bonus_candidate_count"] == 2
    assert tags["packing_graph_closure_preferred_count"] == 1
    assert tags["packing_focused_file_promoted_count"] == 3
    assert tags["packing_packed_path_count"] == 3
    assert tags["packing_reason"] == "ok"
