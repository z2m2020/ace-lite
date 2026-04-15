from __future__ import annotations

from ace_lite.agent_loop.contracts import build_agent_loop_action_v1
from ace_lite.agent_loop.controller import BoundedLoopController
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


def test_controller_source_plan_retry_keeps_query_and_exposes_rerun_policy() -> None:
    controller = BoundedLoopController(enabled=True, max_iterations=1)
    action = build_agent_loop_action_v1(
        action_type="request_source_plan_retry",
        reason="repack_source_plan",
        selected_tests=["pytest -q tests/unit/test_source_plan.py"],
    ).as_dict()

    assert controller.build_incremental_query(
        base_query="draft auth plan",
        action=action,
    ) == "draft auth plan"

    rerun_policy = controller.build_rerun_policy(
        action=action,
        rerun_stages=["source_plan", "validation"],
        iteration_index=1,
    )

    assert rerun_policy["policy_id"] == "source_plan_refresh"
    assert rerun_policy["action_category"] == "source_plan"
    assert rerun_policy["query_mode"] == "reuse"
    assert rerun_policy["rerun_stages"] == ["source_plan", "validation"]


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
        rerun_policy=controller.build_rerun_policy(
            action=selected,
            rerun_stages=["index", "source_plan", "validation"],
            iteration_index=1,
        ),
        retrieval_refinement=controller.build_retrieval_refinement(
            action=selected,
            iteration_index=1,
        ),
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
    assert summary["iterations"][0]["rerun_policy"]["policy_id"] == "retrieval_refresh"
    assert summary["iterations"][0]["retrieval_refinement"]["schema_version"] == (
        "agent_loop_retrieval_refinement_v1"
    )
    assert summary["iterations"][0]["retrieval_refinement"]["focus_paths"] == [
        "src/app.py"
    ]
    assert summary["iterations"][0]["validation_branch_score"]["issue_delta"] == 1
    assert summary["iterations"][0]["validation_branch_score"]["passed"] is True
    assert summary["branch_batch"]["schema_version"] == "agent_loop_branch_batch_v1"
    assert summary["branch_batch"]["candidate_count"] == 1
    assert summary["branch_batch"]["candidates"][0]["branch_id"] == "iteration-1"
    assert summary["branch_selection"]["winner_branch_id"] == "iteration-1"
    assert summary["branch_selection"]["ranked_branch_ids"] == ["iteration-1"]
    assert summary["last_rerun_policy"]["policy_id"] == "retrieval_refresh"
    assert summary["action_type_counts"] == {"request_more_context": 1}


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


def test_controller_builds_structured_retrieval_refinement() -> None:
    controller = BoundedLoopController(
        enabled=True,
        max_iterations=1,
        max_focus_paths=2,
        query_hint_max_chars=32,
    )

    payload = controller.build_retrieval_refinement(
        action=build_agent_loop_action_v1(
            action_type="request_more_context",
            reason="validation_diagnostics",
            query_hint="focus auth flow and syntax cleanup",
            focus_paths=["src/app/auth.py", "src/app/auth.py", "src/app/session.py"],
            metadata={"diagnostic_count": 2},
        ).as_dict(),
        iteration_index=3,
    )

    assert payload["schema_version"] == "agent_loop_retrieval_refinement_v1"
    assert payload["iteration_index"] == 3
    assert payload["focus_paths"] == ["src/app/auth.py", "src/app/session.py"]
    assert payload["query_hint"] == "focus auth flow and syntax clean"
    assert payload["metadata"] == {"diagnostic_count": 2}


def test_controller_synthesizes_action_from_source_plan_validation_findings() -> None:
    controller = BoundedLoopController(enabled=True, max_iterations=1, max_focus_paths=2)

    selected = controller.select_action(
        source_plan_stage={
            "validation_findings": {
                "schema_version": "validation_findings_v1",
                "governance_mode": "advisory_report_only",
                "needs_followup": True,
                "status": "failed",
                "probe_status": "degraded",
                "warn_count": 1,
                "blocker_count": 1,
                "selected_test_count": 1,
                "executed_test_count": 0,
                "focus_paths": ["src/app.py", "src/build.py", "src/ignored.py"],
                "query_hint": "Focus on validation-linked paths: src/app.py. invalid syntax",
                "recommendations": ["Inspect validation-linked paths first."],
            }
        },
        validation_stage={},
    )

    assert selected is not None
    assert selected["action_type"] == "request_more_context"
    assert selected["reason"] == "source_plan_validation_findings"
    assert selected["focus_paths"] == ["src/app.py", "src/build.py"]
    assert selected["metadata"]["source"] == "source_plan.validation_findings"
    assert selected["metadata"]["schema_version"] == "validation_findings_v1"
    assert selected["metadata"]["governance_mode"] == "advisory_report_only"
    assert selected["metadata"]["allowed_effect"] == "request_more_context_only"
    assert selected["metadata"]["blocker_count"] == 1
