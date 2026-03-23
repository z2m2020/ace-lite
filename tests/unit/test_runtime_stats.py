from __future__ import annotations

from ace_lite.runtime_stats import build_learning_router_rollout_decision_payload
from ace_lite.runtime_stats_schema import build_runtime_stats_schema_document


def test_build_learning_router_rollout_decision_payload_marks_disabled_router() -> None:
    payload = build_learning_router_rollout_decision_payload(
        adaptive_router={"enabled": False, "mode": "observe"},
        card_summary={"evidence_card_count": 2, "validation_card_present": True},
        validation_feedback_summary={
            "selected_test_count": 1,
            "executed_test_count": 1,
        },
        failure_signal_summary={
            "status": "skipped",
            "issue_count": 0,
            "probe_issue_count": 0,
            "has_failure": False,
            "source": "source_plan.validate_step",
        },
    )

    assert payload["phase"] == "report_only"
    assert payload["decision"] == "stay_report_only"
    assert payload["reason"] == "adaptive_router_disabled"
    assert payload["eligible_for_guarded_rollout"] is False
    assert payload["router_enabled"] is False


def test_build_learning_router_rollout_decision_payload_marks_guarded_rollout_eligible() -> None:
    payload = build_learning_router_rollout_decision_payload(
        adaptive_router={
            "enabled": True,
            "mode": "shadow",
            "arm_id": "feature",
            "source": "configured",
            "shadow_arm_id": "feature_graph",
            "shadow_source": "fallback",
            "online_bandit": {
                "requested": True,
                "eligible": True,
                "active": False,
            },
        },
        card_summary={"evidence_card_count": 3, "validation_card_present": True},
        validation_feedback_summary={
            "selected_test_count": 2,
            "executed_test_count": 2,
        },
        failure_signal_summary={
            "status": "passed",
            "issue_count": 0,
            "probe_issue_count": 0,
            "has_failure": False,
            "source": "source_plan.validate_step",
        },
    )

    assert payload["reason"] == "eligible_pending_guarded_rollout"
    assert payload["eligible_for_guarded_rollout"] is True
    assert payload["router_mode"] == "shadow"
    assert payload["shadow_arm_id"] == "feature_graph"
    assert payload["validation_selected_test_count"] == 2
    assert payload["failure_signal_has_failure"] is False


def test_runtime_stats_schema_document_includes_learning_router_rollout_contract() -> None:
    payload = build_runtime_stats_schema_document()

    rollout = payload["learning_router_rollout"]
    assert rollout["phase_values"] == ["report_only", "guarded_rollout", "default"]
    assert rollout["decision_values"] == [
        "stay_report_only",
        "apply_guarded_rollout",
        "default_active",
    ]
    assert "eligible_pending_guarded_rollout" in rollout["reason_codes"]
    assert "index.adaptive_router" in rollout["source_signals"]
