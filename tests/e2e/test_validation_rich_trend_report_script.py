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
    assert output["history_count"] == 2
    assert output["latest"]["generated_at"] == "2026-03-12T00:00:00+00:00"
    assert output["previous"]["generated_at"] == "2026-03-11T00:00:00+00:00"
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
    assert output["latest"]["generated_at"] == "2026-03-12T00:00:00+00:00"
    assert output["previous"]["generated_at"] == "2026-03-11T00:00:00+00:00"
    assert output["delta"]["task_success_rate"]["delta"] == pytest.approx(0.2)


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
