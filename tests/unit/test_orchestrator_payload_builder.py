from __future__ import annotations

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_payload_builder import (
    build_default_validation_payload,
    build_orchestrator_plan_payload,
)
from ace_lite.pipeline.types import StageContext, StageMetric


def test_build_default_validation_payload_uses_policy_version() -> None:
    payload = build_default_validation_payload(policy_version="policy-v2")

    assert payload["enabled"] is False
    assert payload["reason"] == "disabled"
    assert payload["policy_version"] == "policy-v2"
    assert payload["result"]["summary"]["status"] == "skipped"


def test_build_orchestrator_plan_payload_builds_observability_and_default_validation() -> None:
    ctx = StageContext(query="q", repo="repo", root="/tmp")
    ctx.state["index"] = {"adaptive_router": {"mode": "observe"}}
    ctx.state["source_plan"] = {
        "card_summary": {"candidate_count": 2},
        "steps": [
            {
                "stage": "validate",
                "validation_feedback_summary": {"retry_count": 1},
            }
        ],
    }
    ctx.state["_plugin_action_log"] = [{"stage": "index"}]
    ctx.state["_plugin_conflicts"] = [{"stage": "skills"}]
    ctx.state["_agent_loop"] = {"enabled": True}
    ctx.state["_long_term_capture"] = [{"stage": "memory"}]
    ctx.state["_contract_errors"] = [{"stage": "index", "error_code": "missing"}]

    contract_error = StageContractError(
        stage="index",
        error_code="missing_required_key",
        reason="missing_key",
        message="missing key",
        context={"key": "targets"},
    )

    payload = build_orchestrator_plan_payload(
        query="q",
        repo="repo",
        root="/tmp",
        conventions={
            "count": 1,
            "rules_count": 1,
            "loaded_files": [{"path": "AGENTS.md", "sha256": "abc"}],
            "rules": [{"name": "default", "path": "AGENTS.md", "priority": 1}],
            "cache_hit": True,
        },
        ctx=ctx,
        stage_metrics=[StageMetric(stage="memory", elapsed_ms=1.0, plugins=[], tags={})],
        plugins_loaded=["demo-plugin"],
        total_ms=7.5,
        contract_error=contract_error,
        replay_cache_info={"cache_hit": False},
        pipeline_order=(
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
            "validation",
        ),
        policy_version="policy-v1",
            build_plugin_policy_summary_fn=lambda *, stage_summary, pipeline_order: {
                "stage_summary": dict(stage_summary),
                "pipeline_order": list(pipeline_order),
            },
        extract_source_plan_failure_signal_summary_fn=lambda source_plan_stage: {
            "missing_required_context": bool(source_plan_stage),
        },
        extract_source_plan_validation_feedback_summary_fn=lambda source_plan_stage: {
            "retry_count": len(source_plan_stage.get("steps", []))
            if isinstance(source_plan_stage, dict)
            else 0,
        },
    )

    assert isinstance(payload["schema_version"], str)
    assert payload["validation"]["policy_version"] == "policy-v1"
    assert payload["observability"]["plugins_loaded"] == ["demo-plugin"]
    assert payload["observability"]["plan_replay_cache"] == {"cache_hit": False}
    assert (
        payload["observability"]["learning_router_rollout_decision"]["validation_feedback_present"]
        is True
    )
    assert payload["observability"]["learning_router_rollout_decision"]["router_mode"] == "observe"
    assert payload["observability"]["guarded_rollout"]["enabled"] is False
    assert payload["observability"]["agent_loop"] == {"enabled": True}
    assert payload["observability"]["long_term_capture"] == [{"stage": "memory"}]
    assert payload["observability"]["error"]["stage"] == "index"
    assert payload["observability"]["contract_errors"] == [
        {"stage": "index", "error_code": "missing"}
    ]
    assert payload["index"]["adaptive_router"]["guarded_rollout"]["enabled"] is False


def test_build_orchestrator_plan_payload_fail_opens_projection_inputs() -> None:
    ctx = StageContext(query="q", repo="repo", root="/tmp")
    ctx.state["index"] = {"adaptive_router": "invalid"}
    ctx.state["source_plan"] = {"card_summary": "invalid"}
    ctx.state["validation"] = "invalid"
    ctx.state["_plugin_action_log"] = "invalid"
    ctx.state["_plugin_conflicts"] = [{"stage": "skills"}]

    payload = build_orchestrator_plan_payload(
        query="q",
        repo="repo",
        root="/tmp",
        conventions={},
        ctx=ctx,
        stage_metrics=[],
        plugins_loaded=[],
        total_ms=3.0,
        contract_error=None,
        replay_cache_info=None,
        pipeline_order=(
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
            "validation",
        ),
        policy_version="policy-v1",
        build_plugin_policy_summary_fn=lambda *, stage_summary, pipeline_order: {
            "stage_summary": dict(stage_summary),
            "pipeline_order": list(pipeline_order),
        },
        extract_source_plan_failure_signal_summary_fn=lambda source_plan_stage: {
            "source_plan_keys": sorted(source_plan_stage.keys())
            if isinstance(source_plan_stage, dict)
            else [],
        },
        extract_source_plan_validation_feedback_summary_fn=lambda source_plan_stage: {
            "retry_count": len(source_plan_stage.get("steps", []))
            if isinstance(source_plan_stage, dict)
            else 0,
        },
    )

    assert payload["validation"]["policy_version"] == "policy-v1"
    assert payload["observability"]["plugin_action_log"] == []
    assert payload["observability"]["plugin_conflicts"] == [{"stage": "skills"}]
    assert payload["observability"]["learning_router_rollout_decision"]["router_mode"] == "disabled"
