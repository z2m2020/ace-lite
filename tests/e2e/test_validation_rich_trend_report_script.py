from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def _write_validation_rich_summary(
    path: Path,
    *,
    generated_at: str,
    repo: str,
    case_count: int,
    regressed: bool,
    failed_checks: list[str],
    task_success_rate: float,
    precision_at_k: float,
    noise_rate: float,
    validation_test_count: float,
    latency_p95_ms: float,
    evidence_insufficient_rate: float,
    missing_validation_rate: float,
    retrieval_control_plane_gate_summary: dict[str, object] | None = None,
    retrieval_frontier_gate_summary: dict[str, object] | None = None,
    deep_symbol_summary: dict[str, object] | None = None,
    native_scip_summary: dict[str, object] | None = None,
    validation_probe_summary: dict[str, object] | None = None,
    source_plan_validation_feedback_summary: dict[str, object] | None = None,
    source_plan_failure_signal_summary: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": generated_at,
        "repo": repo,
        "case_count": case_count,
        "regressed": regressed,
        "failed_checks": failed_checks,
        "metrics": {
            "task_success_rate": task_success_rate,
            "precision_at_k": precision_at_k,
            "noise_rate": noise_rate,
            "validation_test_count": validation_test_count,
            "latency_p95_ms": latency_p95_ms,
            "evidence_insufficient_rate": evidence_insufficient_rate,
            "missing_validation_rate": missing_validation_rate,
        },
    }
    if retrieval_control_plane_gate_summary is not None:
        payload["retrieval_control_plane_gate_summary"] = (
            retrieval_control_plane_gate_summary
        )
    if retrieval_frontier_gate_summary is not None:
        payload["retrieval_frontier_gate_summary"] = retrieval_frontier_gate_summary
    if deep_symbol_summary is not None:
        payload["deep_symbol_summary"] = deep_symbol_summary
    if native_scip_summary is not None:
        payload["native_scip_summary"] = native_scip_summary
    if validation_probe_summary is not None:
        payload["validation_probe_summary"] = validation_probe_summary
    if source_plan_validation_feedback_summary is not None:
        payload["source_plan_validation_feedback_summary"] = (
            source_plan_validation_feedback_summary
        )
    if source_plan_failure_signal_summary is not None:
        payload["source_plan_failure_signal_summary"] = (
            source_plan_failure_signal_summary
        )
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validation_rich_trend_report_main_writes_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_validation_rich_trend_report.py")

    history_root = tmp_path / "history"
    report_a = history_root / "2026-03-11" / "summary.json"
    report_b = history_root / "2026-03-12" / "summary.json"

    _write_validation_rich_summary(
        report_a,
        generated_at="2026-03-11T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=5,
        regressed=True,
        failed_checks=["precision_at_k", "validation_test_count"],
        task_success_rate=0.8,
        precision_at_k=0.35,
        noise_rate=0.65,
        validation_test_count=4.0,
        latency_p95_ms=692.08,
        evidence_insufficient_rate=0.2,
        missing_validation_rate=0.2,
        retrieval_control_plane_gate_summary={
            "regression_evaluated": True,
            "benchmark_regression_detected": True,
            "benchmark_regression_passed": False,
            "failed_checks": ["benchmark_regression_detected"],
            "adaptive_router_shadow_coverage": 0.75,
            "adaptive_router_shadow_coverage_threshold": 0.8,
            "adaptive_router_shadow_coverage_passed": False,
            "risk_upgrade_precision_gain": -0.01,
            "risk_upgrade_precision_gain_threshold": 0.0,
            "risk_upgrade_precision_gain_passed": False,
            "latency_p95_ms": 692.08,
            "latency_p95_ms_threshold": 850.0,
            "latency_p95_ms_passed": True,
            "gate_passed": False,
        },
        retrieval_frontier_gate_summary={
            "deep_symbol_case_recall": 0.81,
            "native_scip_loaded_rate": 0.68,
            "precision_at_k": 0.35,
            "noise_rate": 0.65,
            "failed_checks": ["deep_symbol_case_recall", "native_scip_loaded_rate"],
            "gate_passed": False,
        },
        deep_symbol_summary={
            "case_count": 2.0,
            "recall": 0.81,
        },
        native_scip_summary={
            "loaded_rate": 0.68,
            "document_count_mean": 4.0,
            "definition_occurrence_count_mean": 6.0,
            "reference_occurrence_count_mean": 10.0,
            "symbol_definition_count_mean": 2.0,
        },
        validation_probe_summary={
            "validation_test_count": 4.0,
            "probe_enabled_ratio": 0.5,
            "probe_executed_count_mean": 1.0,
            "probe_failure_rate": 0.25,
        },
        source_plan_validation_feedback_summary={
            "present_ratio": 1.0,
            "issue_count_mean": 1.0,
            "failure_rate": 0.5,
            "probe_issue_count_mean": 0.5,
            "probe_executed_count_mean": 1.0,
            "probe_failure_rate": 0.25,
            "selected_test_count_mean": 1.0,
            "executed_test_count_mean": 0.5,
        },
        source_plan_failure_signal_summary={
            "present_ratio": 1.0,
            "issue_count_mean": 1.0,
            "failure_rate": 0.5,
            "probe_issue_count_mean": 0.5,
            "probe_executed_count_mean": 1.0,
            "probe_failure_rate": 0.25,
            "selected_test_count_mean": 1.0,
            "executed_test_count_mean": 0.5,
            "replay_cache_origin_ratio": 1.0,
            "observability_origin_ratio": 0.0,
            "source_plan_origin_ratio": 0.0,
            "validate_step_origin_ratio": 0.0,
        },
    )
    _write_validation_rich_summary(
        report_b,
        generated_at="2026-03-12T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=5,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.425,
        noise_rate=0.575,
        validation_test_count=5.0,
        latency_p95_ms=617.66,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
        retrieval_control_plane_gate_summary={
            "regression_evaluated": True,
            "benchmark_regression_detected": False,
            "benchmark_regression_passed": True,
            "failed_checks": [],
            "adaptive_router_shadow_coverage": 0.85,
            "adaptive_router_shadow_coverage_threshold": 0.8,
            "adaptive_router_shadow_coverage_passed": True,
            "risk_upgrade_precision_gain": 0.05,
            "risk_upgrade_precision_gain_threshold": 0.0,
            "risk_upgrade_precision_gain_passed": True,
            "latency_p95_ms": 617.66,
            "latency_p95_ms_threshold": 850.0,
            "latency_p95_ms_passed": True,
            "gate_passed": True,
        },
        retrieval_frontier_gate_summary={
            "deep_symbol_case_recall": 0.92,
            "native_scip_loaded_rate": 0.76,
            "precision_at_k": 0.425,
            "noise_rate": 0.575,
            "failed_checks": [],
            "gate_passed": True,
        },
        deep_symbol_summary={
            "case_count": 3.0,
            "recall": 0.92,
        },
        native_scip_summary={
            "loaded_rate": 0.76,
            "document_count_mean": 5.0,
            "definition_occurrence_count_mean": 7.0,
            "reference_occurrence_count_mean": 11.0,
            "symbol_definition_count_mean": 3.0,
        },
        validation_probe_summary={
            "validation_test_count": 5.0,
            "probe_enabled_ratio": 0.67,
            "probe_executed_count_mean": 1.5,
            "probe_failure_rate": 0.1,
        },
        source_plan_validation_feedback_summary={
            "present_ratio": 1.0,
            "issue_count_mean": 0.25,
            "failure_rate": 0.2,
            "probe_issue_count_mean": 0.25,
            "probe_executed_count_mean": 1.5,
            "probe_failure_rate": 0.1,
            "selected_test_count_mean": 1.0,
            "executed_test_count_mean": 0.75,
        },
        source_plan_failure_signal_summary={
            "present_ratio": 1.0,
            "issue_count_mean": 0.25,
            "failure_rate": 0.2,
            "probe_issue_count_mean": 0.25,
            "probe_executed_count_mean": 1.5,
            "probe_failure_rate": 0.1,
            "selected_test_count_mean": 1.0,
            "executed_test_count_mean": 0.75,
            "replay_cache_origin_ratio": 1.0,
            "observability_origin_ratio": 0.0,
            "source_plan_origin_ratio": 0.0,
            "validate_step_origin_ratio": 0.0,
        },
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="scripts/build_validation_rich_trend_report.py\ndocs/maintainers/BENCHMARKING.md\n",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_validation_rich_trend_report.py",
            "--history-root",
            str(history_root),
            "--latest-report",
            str(report_b),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "validation_rich_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["report_only"] is True
    assert output["latest_report_mode"] == "explicit_override"
    assert output["latest_report_path"] == str(report_b.resolve())
    assert output["history_count"] == 2
    assert output["latest"]["generated_at"] == "2026-03-12T00:00:00+00:00"
    assert output["previous"]["generated_at"] == "2026-03-11T00:00:00+00:00"
    assert output["latest"]["retrieval_control_plane_gate_summary"]["gate_passed"] is True
    assert output["latest"]["retrieval_frontier_gate_summary"]["gate_passed"] is True
    assert output["latest"]["deep_symbol_summary"]["case_count"] == pytest.approx(3.0)
    assert output["latest"]["native_scip_summary"]["document_count_mean"] == pytest.approx(5.0)
    assert output["latest"]["validation_probe_summary"]["probe_failure_rate"] == pytest.approx(0.1)
    assert output["latest"]["source_plan_validation_feedback_summary"][
        "executed_test_count_mean"
    ] == pytest.approx(0.75)
    assert output["latest"]["source_plan_failure_signal_summary"][
        "replay_cache_origin_ratio"
    ] == pytest.approx(1.0)
    assert (
        output["previous"]["retrieval_control_plane_gate_summary"][
            "benchmark_regression_detected"
        ]
        is True
    )
    assert (
        output["previous"]["retrieval_frontier_gate_summary"][
            "native_scip_loaded_rate"
        ]
        == pytest.approx(0.68)
    )
    assert output["previous"]["validation_probe_summary"][
        "probe_executed_count_mean"
    ] == pytest.approx(1.0)
    assert output["previous"]["source_plan_validation_feedback_summary"][
        "failure_rate"
    ] == pytest.approx(0.5)
    assert output["previous"]["source_plan_failure_signal_summary"][
        "failure_rate"
    ] == pytest.approx(0.5)
    assert output["delta"]["task_success_rate"] == {
        "current": 1.0,
        "previous": 0.8,
        "delta": pytest.approx(0.2),
    }
    assert output["delta"]["validation_test_count"] == {
        "current": 5.0,
        "previous": 4.0,
        "delta": 1.0,
    }
    assert output["delta"]["missing_validation_rate"] == {
        "current": 0.0,
        "previous": 0.2,
        "delta": -0.2,
    }
    assert output["failed_check_top3"] == [
        {"check": "precision_at_k", "count": 1},
        {"check": "validation_test_count", "count": 1},
    ]
    assert output["suspect_files"] == [
        "scripts/build_validation_rich_trend_report.py",
        "docs/maintainers/BENCHMARKING.md",
    ]

    markdown = (tmp_path / "trend" / "validation_rich_trend_report.md").read_text(
        encoding="utf-8"
    )
    assert "- Report only: True" in markdown
    assert "- Latest report mode: explicit_override" in markdown
    assert "## Latest Q2 Retrieval Control Plane Gate" in markdown
    assert "- Gate passed: True" in markdown
    assert "- Shadow coverage: 0.8500" in markdown
    assert "## Latest Q3 Retrieval Frontier Gate" in markdown
    assert "- Deep symbol case recall: 0.9200" in markdown
    assert "- Native SCIP loaded rate: 0.7600" in markdown
    assert "## Latest Q3 Frontier Evidence" in markdown
    assert "- Deep symbol case count: 3.0000; recall: 0.9200" in markdown
    assert "document_count_mean=5.0000" in markdown
    assert "## Latest Q4 Validation Probe Summary" in markdown
    assert "## Latest Q4 Source Plan Validation Feedback Summary" in markdown
    assert "## Latest Q1 Source Plan Failure Signal Summary" in markdown
    assert "- Probe failure rate: 0.1000" in markdown
    assert "- Executed test count mean: 0.7500" in markdown
    assert "- Replay cache origin ratio: 1.0000; observability origin ratio: 0.0000; source_plan origin ratio: 0.0000; validate_step origin ratio: 0.0000" in markdown
    assert "## Delta" in markdown
    assert "| task_success_rate | 1.0000 | 0.8000 | +0.2000 |" in markdown
    assert "| validation_test_count | 5.0000 | 4.0000 | +1.0000 |" in markdown
    assert "scripts/build_validation_rich_trend_report.py" in markdown


def test_validation_rich_trend_report_prefers_generated_at_over_file_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_validation_rich_trend_report.py")

    history_root = tmp_path / "history"
    newer_path = history_root / "2026-03-12" / "summary.json"
    older_path = history_root / "2026-03-11" / "summary.json"

    _write_validation_rich_summary(
        newer_path,
        generated_at="2026-03-12T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=5,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.425,
        noise_rate=0.575,
        validation_test_count=5.0,
        latency_p95_ms=617.66,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )
    _write_validation_rich_summary(
        older_path,
        generated_at="2026-03-11T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=5,
        regressed=True,
        failed_checks=["precision_at_k"],
        task_success_rate=0.8,
        precision_at_k=0.35,
        noise_rate=0.65,
        validation_test_count=4.0,
        latency_p95_ms=692.08,
        evidence_insufficient_rate=0.2,
        missing_validation_rate=0.2,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_validation_rich_trend_report.py",
            "--history-root",
            str(history_root),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "validation_rich_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["latest_report_mode"] == "none"
    assert output["latest"]["generated_at"] == "2026-03-12T00:00:00+00:00"
    assert output["previous"]["generated_at"] == "2026-03-11T00:00:00+00:00"
    assert output["delta"]["task_success_rate"]["delta"] == pytest.approx(0.2)


def test_validation_rich_trend_report_defaults_to_canonical_current_latest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_validation_rich_trend_report.py")

    history_root = tmp_path / "history"
    dated_report = history_root / "2026-03-18-wave5-budget-pass" / "summary.json"
    canonical_latest = history_root / "latest" / "summary.json"
    tuned_latest = history_root / "tuned" / "latest" / "summary.json"

    _write_validation_rich_summary(
        dated_report,
        generated_at="2026-03-18T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.56,
        noise_rate=0.44,
        validation_test_count=5.0,
        latency_p95_ms=130.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )
    _write_validation_rich_summary(
        canonical_latest,
        generated_at="2026-03-19T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.59,
        noise_rate=0.41,
        validation_test_count=5.0,
        latency_p95_ms=127.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )
    _write_validation_rich_summary(
        tuned_latest,
        generated_at="2026-03-20T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.61,
        noise_rate=0.39,
        validation_test_count=5.0,
        latency_p95_ms=999.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_validation_rich_trend_report.py",
            "--history-root",
            str(history_root),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "validation_rich_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["latest_report_mode"] == "canonical_current"
    assert output["latest_report_path"] == str(canonical_latest.resolve())
    assert output["canonical_latest_report_path"] == str(canonical_latest.resolve())
    assert output["history_count"] == 2
    assert output["latest"]["path"] == str(canonical_latest.resolve())
    assert output["latest"]["metrics"]["latency_p95_ms"] == pytest.approx(127.0)
    assert all("tuned/latest/summary.json" not in row["path"] for row in output["history"])


def test_validation_rich_trend_report_handles_single_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_validation_rich_trend_report.py")

    history_root = tmp_path / "history"
    report = history_root / "2026-03-12" / "summary.json"
    _write_validation_rich_summary(
        report,
        generated_at="2026-03-12T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=5,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.425,
        noise_rate=0.575,
        validation_test_count=5.0,
        latency_p95_ms=617.66,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_validation_rich_trend_report.py",
            "--history-root",
            str(history_root),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "validation_rich_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["history_count"] == 1
    assert output["latest"]["generated_at"] == "2026-03-12T00:00:00+00:00"
    assert output["previous"] == {}
    assert output["delta"] == {}

    markdown = (tmp_path / "trend" / "validation_rich_trend_report.md").read_text(
        encoding="utf-8"
    )
    assert "## Latest" in markdown
    assert "## Delta" not in markdown


def test_validation_rich_trend_report_ignores_nested_summary_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_validation_rich_trend_report.py")

    history_root = tmp_path / "history"
    direct_report = history_root / "2026-03-19-wave5-latency-trim" / "summary.json"
    nested_report = (
        history_root
        / "stability"
        / "2026-03-19-wave5-latency-trim"
        / "run-01"
        / "summary.json"
    )

    _write_validation_rich_summary(
        direct_report,
        generated_at="2026-03-19T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.5935,
        noise_rate=0.4065,
        validation_test_count=5.0,
        latency_p95_ms=124.03,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )
    _write_validation_rich_summary(
        nested_report,
        generated_at="2026-03-20T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.5935,
        noise_rate=0.4065,
        validation_test_count=5.0,
        latency_p95_ms=80.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_validation_rich_trend_report.py",
            "--history-root",
            str(history_root),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "validation_rich_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["history_count"] == 1
    assert output["latest"]["path"] == str(direct_report)


def test_validation_rich_trend_report_ignores_non_dated_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_validation_rich_trend_report.py")

    history_root = tmp_path / "history"
    direct_report = history_root / "2026-03-19-wave5-latency-trim" / "summary.json"
    pseudo_dated_report = history_root / "ps-warm-vcs-cache" / "summary.json"

    _write_validation_rich_summary(
        direct_report,
        generated_at="2026-03-19T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=False,
        failed_checks=[],
        task_success_rate=1.0,
        precision_at_k=0.5935,
        noise_rate=0.4065,
        validation_test_count=5.0,
        latency_p95_ms=124.03,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )
    _write_validation_rich_summary(
        pseudo_dated_report,
        generated_at="2026-03-20T00:00:00+00:00",
        repo="ace-lite-engine",
        case_count=7,
        regressed=True,
        failed_checks=["latency_p95_ms"],
        task_success_rate=1.0,
        precision_at_k=0.5935,
        noise_rate=0.4065,
        validation_test_count=5.0,
        latency_p95_ms=600.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_validation_rich_trend_report.py",
            "--history-root",
            str(history_root),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "validation_rich_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["history_count"] == 1
    assert output["latest"]["path"] == str(direct_report)
    assert output["failed_check_top3"] == []
