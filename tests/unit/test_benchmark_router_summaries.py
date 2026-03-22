from __future__ import annotations

from ace_lite.benchmark.scoring import build_adaptive_router_arm_summary


def test_build_adaptive_router_arm_summary_surfaces_fallback_and_downgrade_by_arm() -> None:
    case_results = [
        {
            "router_enabled": 1.0,
            "router_arm_id": "feature",
            "router_shadow_arm_id": "feature_graph",
            "router_shadow_source": "model",
            "task_success_hit": 1.0,
            "reciprocal_rank": 1.0,
            "latency_ms": 10.0,
            "index_latency_ms": 4.0,
            "decision_trace": [
                {"action": "fallback", "target": "embeddings"},
                {"action": "downgrade", "target": "parallel_docs"},
            ],
        },
        {
            "router_enabled": 1.0,
            "router_arm_id": "feature",
            "router_shadow_arm_id": "feature_graph",
            "router_shadow_source": "fallback",
            "task_success_hit": 0.0,
            "reciprocal_rank": 0.5,
            "latency_ms": 20.0,
            "index_latency_ms": 6.0,
            "decision_trace": [
                {"action": "fallback", "target": "embeddings"},
            ],
        },
    ]

    summary = build_adaptive_router_arm_summary(case_results)
    executed_arm = summary["executed"]["arms"][0]
    shadow_arm = summary["shadow"]["arms"][0]

    assert executed_arm["arm_id"] == "feature"
    assert executed_arm["fallback_case_count"] == 2
    assert executed_arm["fallback_case_rate"] == 1.0
    assert executed_arm["fallback_event_count"] == 2
    assert executed_arm["fallback_targets"] == {"embeddings": 2}
    assert executed_arm["downgrade_case_count"] == 1
    assert executed_arm["downgrade_case_rate"] == 0.5
    assert executed_arm["downgrade_event_count"] == 1
    assert executed_arm["downgrade_targets"] == {"parallel_docs": 1}
    assert shadow_arm["arm_id"] == "feature_graph"
    assert shadow_arm["fallback_case_count"] == 2
    assert shadow_arm["downgrade_case_count"] == 1


def test_build_adaptive_router_observability_summary_surfaces_shadow_source_counts() -> None:
    from ace_lite.benchmark.scoring import build_adaptive_router_observability_summary

    summary = build_adaptive_router_observability_summary(
        [
            {
                "router_enabled": 1.0,
                "router_arm_id": "feature",
                "router_shadow_arm_id": "feature_graph",
                "router_shadow_source": "model",
            },
            {
                "router_enabled": 1.0,
                "router_arm_id": "general",
                "router_shadow_arm_id": "general_hybrid",
                "router_shadow_source": "fallback",
            },
            {
                "router_enabled": 1.0,
                "router_arm_id": "general",
                "router_shadow_arm_id": "general_hybrid",
                "router_shadow_source": "fallback",
            },
        ]
    )

    assert summary["shadow_source_counts"] == {
        "fallback": 2,
        "model": 1,
    }
    assert summary["shadow_coverage_case_count"] == 3
    assert summary["shadow_coverage_rate"] == 1.0
