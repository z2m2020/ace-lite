from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_script(name: str):
    module_name = f"script_{name.replace('.', '_')}"
    module_path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_plan_payload() -> dict[str, object]:
    return {
        "pipeline_order": ["memory", "index", "repomap", "augment", "skills", "source_plan"],
        "index": {
            "candidate_files": [
                {"path": "src/ace_lite/orchestrator.py"},
                {"path": "src/ace_lite/cli.py"},
                {"path": "src/ace_lite/repomap/ranking.py"},
                {"path": "tests/integration/test_orchestrator.py"},
            ]
        },
        "source_plan": {
            "stages": ["memory", "index", "repomap", "augment", "skills", "source_plan"],
            "steps": [
                "review candidates",
                "narrow scope",
                "inspect target symbols",
                "apply change",
                "validate",
            ],
            "candidate_chunks": [
                {"path": "src/ace_lite/orchestrator.py", "qualified_name": "AceOrchestrator.plan"},
                {"path": "src/ace_lite/orchestrator.py", "qualified_name": "AceOrchestrator._run_index"},
                {"path": "src/ace_lite/repomap/ranking.py", "qualified_name": "rank_symbols"},
                {"path": "src/ace_lite/cli.py", "qualified_name": "plan_command"},
                {"path": "tests/integration/test_orchestrator.py", "qualified_name": "test_plan"},
                {"path": "src/ace_lite/memory.py", "qualified_name": "DualChannelMemoryProvider.search"},
            ],
            "chunk_steps": [
                "inspect AceOrchestrator.plan",
                "inspect _run_index",
                "inspect rank_symbols",
                "inspect plan_command",
            ],
            "validation_tests": ["pytest -q tests/integration/test_orchestrator.py"],
            "writeback_template": {"summary": "done"},
        },
    }


def test_e2e_case_evaluation_passes_with_expected_shape() -> None:
    module = _load_script("run_e2e_success_slice.py")

    passed, metrics, checks = module._evaluate_case_success(
        case={
            "case_id": "demo",
            "query": "demo",
            "expectations": {
                "min_source_plan_steps": 4,
                "min_candidate_files": 3,
                "min_candidate_chunks": 5,
                "min_chunk_steps": 3,
                "min_validation_tests": 1,
                "require_writeback_template": True,
                "required_stages": [
                    "memory",
                    "index",
                    "repomap",
                    "augment",
                    "skills",
                    "source_plan",
                ],
            },
        },
        plan_payload=_make_plan_payload(),
    )

    assert passed is True
    assert metrics["source_plan_steps"] == 5
    assert metrics["candidate_files"] == 4
    assert metrics["candidate_chunks"] == 6
    assert metrics["chunk_steps"] == 4
    assert metrics["validation_tests"] == 1
    assert all(bool(item.get("passed", False)) for item in checks)


def test_e2e_case_evaluation_reports_failure() -> None:
    module = _load_script("run_e2e_success_slice.py")

    payload = _make_plan_payload()
    payload["source_plan"]["candidate_chunks"] = []

    passed, _, checks = module._evaluate_case_success(
        case={
            "expectations": {
                "min_candidate_chunks": 2,
            }
        },
        plan_payload=payload,
    )

    assert passed is False
    failed_checks = [item for item in checks if not bool(item.get("passed", False))]
    assert any(item.get("metric") == "candidate_chunks" for item in failed_checks)


def test_e2e_case_evaluation_detects_validation_gap_with_retrieval_intact() -> None:
    module = _load_script("run_e2e_success_slice.py")

    payload = _make_plan_payload()
    payload["source_plan"]["validation_tests"] = []

    passed, metrics, checks = module._evaluate_case_success(
        case={
            "expectations": {
                "min_candidate_files": 3,
                "min_candidate_chunks": 4,
                "min_validation_tests": 1,
            }
        },
        plan_payload=payload,
    )

    assert passed is False
    assert metrics["candidate_files"] == 4
    assert metrics["candidate_chunks"] == 6
    assert metrics["validation_tests"] == 0
    failed_checks = [item for item in checks if not bool(item.get("passed", False))]
    assert [item.get("metric") for item in failed_checks] == ["validation_tests"]


def test_internal_docs_lookup_case_does_not_require_validation_tests() -> None:
    cases_path = Path(__file__).resolve().parents[2] / "benchmark" / "cases" / "e2e" / "internal.yaml"
    payload = yaml.safe_load(cases_path.read_text(encoding="utf-8"))

    cases = payload.get("cases") if isinstance(payload, dict) else None
    assert isinstance(cases, list)

    target = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "maintainers-benchmarking-negative-control"
    )
    expectations = target.get("expectations")
    assert isinstance(expectations, dict)
    assert expectations.get("min_validation_tests", 0) == 0


def test_e2e_main_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script("run_e2e_success_slice.py")

    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        """
cases:
  - case_id: c1
    query: one
  - case_id: c2
    query: two
""".lstrip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = (cmd, cwd)
        return module.CommandResult(
            cmd=cmd,
            returncode=0,
            stdout=json.dumps(_make_plan_payload(), ensure_ascii=False),
            stderr="",
            elapsed_ms=12.5,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_e2e_success_slice.py",
            "--cases",
            str(cases_path),
            "--output-dir",
            str(output_dir),
            "--min-success-rate",
            "0.9",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    report = (output_dir / "report.md").read_text(encoding="utf-8")

    assert summary["case_count"] == 2
    assert summary["passed_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["task_success_rate"] == 1.0
    assert summary["threshold_enabled"] is True
    assert summary["threshold_passed"] is True
    assert len(details["results"]) == 2
    assert "# ACE-Lite E2E Success Slice" in report


def test_e2e_main_fail_on_thresholds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script("run_e2e_success_slice.py")

    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        """
cases:
  - case_id: c1
    query: one
""".lstrip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"

    payload = _make_plan_payload()
    payload["source_plan"]["candidate_chunks"] = []

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = (cmd, cwd)
        return module.CommandResult(
            cmd=cmd,
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False),
            stderr="",
            elapsed_ms=10.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_e2e_success_slice.py",
            "--cases",
            str(cases_path),
            "--output-dir",
            str(output_dir),
            "--min-success-rate",
            "1.0",
            "--fail-on-thresholds",
        ],
    )

    exit_code = module.main()
    assert exit_code == 1

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    report = (output_dir / "report.md").read_text(encoding="utf-8")
    assert summary["task_success_rate"] == 0.0
    assert summary["threshold_enabled"] is True
    assert summary["threshold_passed"] is False
    assert summary["failed_cases"] == [
        {
            "case_id": "c1",
            "reason": "validation_failed",
            "failed_checks": ["candidate_chunks"],
            "metrics": {
                "source_plan_steps": 5,
                "candidate_files": 4,
                "candidate_chunks": 0,
                "chunk_steps": 4,
                "validation_tests": 1,
                "writeback_template_present": True,
                "stage_names": [
                    "memory",
                    "index",
                    "repomap",
                    "augment",
                    "skills",
                    "source_plan",
                ],
            },
        }
    ]
    assert "failed_checks: candidate_chunks" in report
    assert "metrics: source_plan_steps=5, candidate_files=4, candidate_chunks=0" in report
