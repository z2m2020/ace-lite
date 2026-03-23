from __future__ import annotations

from ace_lite.validation.result import (
    VALIDATION_RESULT_SCHEMA_VERSION,
    build_validation_result_v1,
    compare_validation_results_v1,
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
