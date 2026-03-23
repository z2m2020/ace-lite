from __future__ import annotations

from ace_lite.agent_loop.controller import BoundedLoopController
from ace_lite.agent_loop.contracts import build_agent_loop_action_v1
from ace_lite.validation.result import build_validation_result_v1


def test_controller_prefers_explicit_stage_action() -> None:
    controller = BoundedLoopController(enabled=True, max_iterations=1)
    action = build_agent_loop_action_v1(
        action_type="request_validation_retry",
        reason="retry_after_fix",
        selected_tests=["pytest -q tests/unit/test_validation_stage.py"],
    ).as_dict()

    selected = controller.select_action(
        source_plan_stage={"loop_action": action},
        validation_stage={},
    )

    assert selected is not None
    assert selected["action_type"] == "request_validation_retry"
    assert (
        controller.build_incremental_query(
            base_query="draft auth plan",
            action=selected,
        )
        == "draft auth plan"
    )


def test_controller_synthesizes_and_records_validation_driven_iteration() -> None:
    controller = BoundedLoopController(enabled=True, max_iterations=1)

    selected = controller.select_action(
        source_plan_stage={},
        validation_stage={
            "diagnostics": [
                {
                    "path": "src/app.py",
                    "message": "invalid syntax",
                    "severity": "error",
                }
            ]
        },
    )

    assert selected is not None
    assert selected["action_type"] == "request_more_context"
    incremental_query = controller.build_incremental_query(
        base_query="draft auth plan",
        action=selected,
    )
    assert "Focus refinement" in incremental_query
    controller.record_iteration(
        action=selected,
        query=incremental_query,
        rerun_stages=["index", "source_plan", "validation"],
        source_plan_stage={"steps": [{"stage": "source_plan"}]},
        previous_validation_stage={
            "result": build_validation_result_v1(
                syntax_issues=[{"code": "syntax.error", "message": "bad syntax"}],
                replay_key="before",
                status="failed",
            ).as_dict()
        },
        validation_stage={
            "diagnostic_count": 1,
            "result": build_validation_result_v1(
                replay_key="after",
                status="passed",
            ).as_dict(),
        },
    )

    summary = controller.finalize(
        stop_reason="completed",
        last_action=selected,
        final_query=incremental_query,
    )

    assert summary["iteration_count"] == 1
    assert summary["actions_executed"] == 1
    assert summary["iterations"][0]["validation_status"] == "passed"
    assert summary["iterations"][0]["diagnostic_count"] == 1
    assert summary["iterations"][0]["validation_branch_score"]["issue_delta"] == 1
    assert summary["iterations"][0]["validation_branch_score"]["passed"] is True
    assert summary["branch_batch"]["schema_version"] == "agent_loop_branch_batch_v1"
    assert summary["branch_batch"]["candidate_count"] == 1
    assert summary["branch_batch"]["candidates"][0]["branch_id"] == "iteration-1"
    assert summary["branch_selection"]["winner_branch_id"] == "iteration-1"
    assert summary["branch_selection"]["ranked_branch_ids"] == ["iteration-1"]


def test_controller_synthesizes_action_from_failed_validation_probes() -> None:
    controller = BoundedLoopController(enabled=True, max_iterations=1)

    selected = controller.select_action(
        source_plan_stage={},
        validation_stage={
            "diagnostics": [],
            "probes": {
                "status": "failed",
                "results": [
                    {
                        "name": "compile",
                        "status": "failed",
                        "issue_count": 1,
                        "issues": [
                            {
                                "path": "src/app.py",
                                "message": "compile probe failed",
                            }
                        ],
                    }
                ],
            },
        },
    )

    assert selected is not None
    assert selected["action_type"] == "request_more_context"
    assert selected["reason"] == "validation_probes"
    assert selected["focus_paths"] == ["src/app.py"]
    assert selected["metadata"]["probe_issue_count"] == 1
    assert selected["metadata"]["probe_names"] == ["compile"]
