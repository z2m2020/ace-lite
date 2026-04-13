from __future__ import annotations

from ace_lite.validation.result import (
    VALIDATION_BRANCH_SCORE_SCHEMA_VERSION,
    VALIDATION_BRANCH_SELECTION_SCHEMA_VERSION,
    VALIDATION_RESULT_SCHEMA_VERSION,
    build_validation_result_v1,
    compare_validation_results_v1,
    score_validation_branch_result_v1,
    select_best_validation_branch_candidate_v1,
    validate_validation_result_v1,
)


def test_build_validation_result_v1_emits_required_sections() -> None:
    payload = build_validation_result_v1(
        syntax_issues=[{"code": "syntax.missing_colon", "message": "expected ':'", "path": "src/app.py"}],
        type_issues=[],
        test_issues=[{"code": "tests.failed", "message": "assertion failed", "path": "tests/test_app.py"}],
        selected_tests=["tests/test_app.py::test_main"],
        executed_tests=["tests/test_app.py::test_main"],
        available_probes=["compile", "import", "tests"],
        sandboxed=True,
        runner="temp-tree",
        artifacts=["artifacts/junit.xml"],
        replay_key="validation-run-001",
    ).as_dict()

    assert payload["schema_version"] == VALIDATION_RESULT_SCHEMA_VERSION
    assert set(payload.keys()) == {
        "schema_version",
        "syntax",
        "type",
        "tests",
        "probes",
        "environment",
        "summary",
    }
    assert payload["summary"]["issue_count"] == 2
    assert payload["summary"]["comparison_key"]
    assert payload["probes"]["status"] == "disabled"
    assert payload["probes"]["available"] == ["compile", "import", "tests"]


def test_build_validation_result_v1_supports_probe_results() -> None:
    payload = build_validation_result_v1(
        available_probes=["compile", "import", "tests"],
        probes=[
            {
                "name": "compile",
                "status": "failed",
                "selected": True,
                "executed": True,
                "issues": [{"code": "probe.compile", "message": "compile failed"}],
            }
        ],
        replay_key="validation-run-002",
        status="failed",
    ).as_dict()

    assert payload["probes"]["enabled"] is True
    assert payload["probes"]["selected_count"] == 1
    assert payload["probes"]["executed_count"] == 1
    assert payload["probes"]["issue_count"] == 1
    assert payload["probes"]["status"] == "failed"
    assert payload["summary"]["issue_count"] == 1


def test_compare_validation_results_v1_detects_new_and_resolved_issue_codes() -> None:
    before = build_validation_result_v1(
        syntax_issues=[{"code": "syntax.error", "message": "bad syntax"}],
        replay_key="run-a",
    )
    after = build_validation_result_v1(
        type_issues=[{"code": "type.error", "message": "bad type"}],
        replay_key="run-b",
    )

    diff = compare_validation_results_v1(before=before, after=after)

    assert diff["changed"] is True
    assert diff["new_issue_codes"] == ["type.error"]
    assert diff["resolved_issue_codes"] == ["syntax.error"]


def test_validate_validation_result_v1_rejects_invalid_summary_status() -> None:
    payload = build_validation_result_v1(
        replay_key="run-1",
    ).as_dict()
    payload["summary"]["status"] = "unknown"

    result = validate_validation_result_v1(
        contract=payload,
        strict=True,
        fail_closed=True,
    )

    assert result["ok"] is False
    assert "validation_result_summary_status_invalid" in result["violations"]


def test_score_validation_branch_result_v1_rewards_fixing_issues() -> None:
    before = build_validation_result_v1(
        syntax_issues=[{"code": "syntax.error", "message": "bad syntax"}],
        type_issues=[{"code": "type.error", "message": "bad type"}],
        replay_key="run-before",
    )
    after = build_validation_result_v1(
        replay_key="run-after",
    )

    score = score_validation_branch_result_v1(before=before, after=after)

    assert score["schema_version"] == VALIDATION_BRANCH_SCORE_SCHEMA_VERSION
    assert score["passed"] is True
    assert score["issue_delta"] == 2
    assert score["resolved_issue_count"] == 2
    assert score["new_issue_count"] == 0
    assert score["regressed"] is False
    assert score["score"] > 100.0


def test_score_validation_branch_result_v1_penalizes_degraded_new_issues() -> None:
    before = build_validation_result_v1(
        replay_key="run-before",
    )
    after = build_validation_result_v1(
        type_issues=[{"code": "type.error", "message": "bad type"}],
        degraded_reasons=["missing_optional_tool"],
        replay_key="run-after",
        status="degraded",
    )

    score = score_validation_branch_result_v1(before=before, after=after)

    assert score["degraded"] is True
    assert score["degraded_penalty"] == 10.0
    assert score["new_issue_count"] == 1
    assert score["new_issue_penalty"] == 20.0
    assert score["regressed"] is True
    assert score["score"] < 0.0


def test_select_best_validation_branch_candidate_v1_prefers_higher_score() -> None:
    better_after = build_validation_result_v1(replay_key="better-after")
    worse_after = build_validation_result_v1(
        type_issues=[{"code": "type.error", "message": "bad type"}],
        replay_key="worse-after",
        status="failed",
    )
    before = build_validation_result_v1(
        type_issues=[{"code": "type.error", "message": "bad type"}],
        replay_key="before",
        status="failed",
    )

    selection = select_best_validation_branch_candidate_v1(
        candidates=[
            {
                "branch_id": "branch-better",
                "before": before.as_dict(),
                "after": better_after.as_dict(),
                "patch_scope_lines": 12,
            },
            {
                "branch_id": "branch-worse",
                "before": before.as_dict(),
                "after": worse_after.as_dict(),
                "patch_scope_lines": 4,
            },
        ]
    )

    assert selection["schema_version"] == VALIDATION_BRANCH_SELECTION_SCHEMA_VERSION
    assert selection["winner_branch_id"] == "branch-better"
    assert selection["ranked_branch_ids"] == ["branch-better", "branch-worse"]
    assert selection["rejected"][0]["branch_id"] == "branch-worse"
    assert selection["rejected"][0]["rejected_reason"] == "lower_pass_status"


def test_select_best_validation_branch_candidate_v1_breaks_ties_by_patch_scope() -> None:
    shared_score = {
        "schema_version": VALIDATION_BRANCH_SCORE_SCHEMA_VERSION,
        "before_status": "failed",
        "after_status": "passed",
        "before_issue_count": 1,
        "after_issue_count": 0,
        "issue_delta": 1,
        "resolved_issue_count": 1,
        "new_issue_count": 0,
        "resolved_issue_codes": ["type.error"],
        "new_issue_codes": [],
        "passed": True,
        "degraded": False,
        "failed": False,
        "skipped": False,
        "degraded_penalty": 0.0,
        "new_issue_penalty": 0.0,
        "regressed": False,
        "score": 112.0,
    }

    selection = select_best_validation_branch_candidate_v1(
        candidates=[
            {
                "branch_id": "branch-large",
                "validation_branch_score": shared_score,
                "patch_scope_lines": 20,
            },
            {
                "branch_id": "branch-small",
                "validation_branch_score": shared_score,
                "patch_scope_lines": 5,
            },
        ]
    )

    assert selection["winner_branch_id"] == "branch-small"
    assert selection["winner_patch_scope_lines"] == 5
    assert selection["rejected"][0]["branch_id"] == "branch-large"
    assert selection["rejected"][0]["rejected_reason"] == "larger_patch_scope"
