from __future__ import annotations

import json
from pathlib import Path

from ace_lite.pipeline.stages.augment import run_diagnostics_augment


def test_run_diagnostics_augment_collects_test_signals(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    junit_path = reports / "junit.xml"
    junit_path.write_text(
        """
<testsuite tests="1" failures="1">
  <testcase classname="tests.test_auth" name="test_token_failure" file="src\\app\\core.py" line="42">
    <failure message="assert False">Traceback\nFile "src\\app\\core.py", line 45\nAssertionError</failure>
  </testcase>
</testsuite>
""".strip(),
        encoding="utf-8",
    )

    coverage_path = reports / "coverage.json"
    coverage_path.write_text(
        json.dumps({"files": {r"src\\app\\core.py": {"executed_lines": [44, 45, 46]}}}),
        encoding="utf-8",
    )

    sbfl_path = reports / "sbfl.json"
    sbfl_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "path": r"src\\app\\core.py",
                        "line": 45,
                        "score": 0.9,
                        "test": "tests/test_auth.py::test_token_failure",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="pytest failure in token flow",
        index_stage={"candidate_files": []},
        enabled=False,
        top_n=5,
        broker=None,
        xref_enabled=False,
        xref_top_n=2,
        xref_time_budget_ms=100,
        candidate_chunks=[
            {
                "path": "src/app/core.py",
                "qualified_name": "src.app.core.validate_token",
                "kind": "function",
                "lineno": 40,
                "end_lineno": 52,
                "score": 4.0,
                "score_breakdown": {},
            }
        ],
        junit_xml_path=str(junit_path),
        coverage_json_path=str(coverage_path),
        sbfl_json_path=str(sbfl_path),
    )

    tests_payload = payload["tests"]

    assert tests_payload["enabled"] is True
    assert tests_payload["reason"] == "provided"
    assert len(tests_payload["failures"]) == 1
    assert tests_payload["stack_frames"]
    assert tests_payload["suspicious_chunks"]
    assert tests_payload["suspicious_chunks"][0]["path"] == "src/app/core.py"
    assert "tests.test_auth::test_token_failure" in tests_payload["suggested_tests"]
    assert "tests/test_auth.py::test_token_failure" in tests_payload["suggested_tests"]


def test_run_diagnostics_augment_supports_configurable_sbfl_metric(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    sbfl_path = reports / "sbfl-counts.json"
    sbfl_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "path": "src/app/core.py",
                        "line": 45,
                        "ef": 3,
                        "ep": 1,
                        "nf": 2,
                        "test": "tests/test_auth.py::test_token_failure",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    candidate_chunks = [
        {
            "path": "src/app/core.py",
            "qualified_name": "src.app.core.validate_token",
            "kind": "function",
            "lineno": 40,
            "end_lineno": 52,
            "score": 4.0,
            "score_breakdown": {},
        }
    ]

    ochiai_payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="pytest failure in token flow",
        index_stage={"candidate_files": []},
        enabled=False,
        top_n=5,
        broker=None,
        xref_enabled=False,
        xref_top_n=2,
        xref_time_budget_ms=100,
        candidate_chunks=candidate_chunks,
        sbfl_json_path=str(sbfl_path),
        sbfl_metric="ochiai",
    )

    dstar_payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="pytest failure in token flow",
        index_stage={"candidate_files": []},
        enabled=False,
        top_n=5,
        broker=None,
        xref_enabled=False,
        xref_top_n=2,
        xref_time_budget_ms=100,
        candidate_chunks=candidate_chunks,
        sbfl_json_path=str(sbfl_path),
        sbfl_metric="dstar",
    )

    ochiai_tests = ochiai_payload["tests"]
    dstar_tests = dstar_payload["tests"]

    assert ochiai_tests["sbfl_metric"] == "ochiai"
    assert dstar_tests["sbfl_metric"] == "dstar"
    assert ochiai_tests["suspicious_chunks"]
    assert dstar_tests["suspicious_chunks"]
    assert dstar_tests["suspicious_chunks"][0]["score"] > ochiai_tests["suspicious_chunks"][0]["score"]


def test_run_diagnostics_augment_reads_json_failed_test_report(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    report_path = reports / "failed-tests.json"
    report_path.write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "suite": "tests.test_api",
                        "name": "test_create_user",
                        "file": "src/app/core.py",
                        "line": 19,
                        "message": "assert status == 201",
                        "stacktrace": 'Traceback\nFile "src/app/core.py", line 21\nAssertionError',
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="test failure",
        index_stage={"candidate_files": []},
        enabled=False,
        top_n=5,
        broker=None,
        xref_enabled=False,
        xref_top_n=2,
        xref_time_budget_ms=100,
        candidate_chunks=[
            {
                "path": "src/app/core.py",
                "qualified_name": "src.app.core.create_user",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 30,
                "score": 2.0,
                "score_breakdown": {},
            }
        ],
        junit_xml_path=str(report_path),
    )

    tests_payload = payload["tests"]
    assert tests_payload["inputs"]["report_format"] == "json"
    assert tests_payload["failures"][0]["suite"] == "tests.test_api"
    assert tests_payload["stack_frames"]


def test_run_diagnostics_augment_ranks_suggested_tests_by_signal_weight(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    junit_path = reports / "junit.xml"
    junit_path.write_text(
        """
<testsuite tests="1" failures="1">
  <testcase classname="tests.test_auth" name="test_token_failure">
    <failure message="assert false">Traceback\nFile "src/app/core.py", line 45</failure>
  </testcase>
</testsuite>
""".strip(),
        encoding="utf-8",
    )

    sbfl_path = reports / "sbfl.json"
    sbfl_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "path": "src/app/core.py",
                        "line": 45,
                        "score": 0.8,
                        "test": "tests/test_other.py::test_secondary",
                    },
                    {
                        "path": "src/app/core.py",
                        "line": 45,
                        "score": 0.7,
                        "test": "tests.test_auth::test_token_failure",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="test failure",
        index_stage={"candidate_files": []},
        enabled=False,
        top_n=5,
        broker=None,
        xref_enabled=False,
        xref_top_n=2,
        xref_time_budget_ms=100,
        candidate_chunks=[
            {
                "path": "src/app/core.py",
                "qualified_name": "src.app.core.validate_token",
                "kind": "function",
                "lineno": 40,
                "end_lineno": 50,
                "score": 2.0,
                "score_breakdown": {},
            }
        ],
        junit_xml_path=str(junit_path),
        sbfl_json_path=str(sbfl_path),
    )

    suggestions = payload["tests"]["suggested_tests"]
    assert suggestions
    assert suggestions[0] == "tests.test_auth::test_token_failure"
