from __future__ import annotations

import importlib.util
import json
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


def _write_summary(
    path: Path,
    *,
    generated_at: str,
    task_success_rate: float,
    precision_at_k: float,
    noise_rate: float,
    latency_p95_ms: float,
    validation_test_count: float,
    evidence_insufficient_rate: float,
    missing_validation_rate: float,
    regressed: bool,
    failed_checks: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": generated_at,
        "repo": "ace-lite-engine",
        "case_count": 5,
        "regressed": regressed,
        "failed_checks": failed_checks,
        "metrics": {
            "task_success_rate": task_success_rate,
            "precision_at_k": precision_at_k,
            "noise_rate": noise_rate,
            "latency_p95_ms": latency_p95_ms,
            "validation_test_count": validation_test_count,
            "evidence_insufficient_rate": evidence_insufficient_rate,
            "missing_validation_rate": missing_validation_rate,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validation_rich_comparison_report_main_writes_summary(tmp_path: Path) -> None:
    module = _load_script("build_validation_rich_comparison_report.py")

    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    tuned = tmp_path / "tuned.json"
    _write_summary(
        baseline,
        generated_at="2026-03-10T00:00:00+00:00",
        task_success_rate=0.8,
        precision_at_k=0.35,
        noise_rate=0.65,
        latency_p95_ms=692.08,
        validation_test_count=4.0,
        evidence_insufficient_rate=0.2,
        missing_validation_rate=0.2,
        regressed=True,
        failed_checks=["precision_at_k"],
    )
    _write_summary(
        current,
        generated_at="2026-03-11T00:00:00+00:00",
        task_success_rate=1.0,
        precision_at_k=0.425,
        noise_rate=0.575,
        latency_p95_ms=617.66,
        validation_test_count=5.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
        regressed=False,
        failed_checks=[],
    )
    _write_summary(
        tuned,
        generated_at="2026-03-12T00:00:00+00:00",
        task_success_rate=1.0,
        precision_at_k=0.45,
        noise_rate=0.55,
        latency_p95_ms=590.0,
        validation_test_count=5.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
        regressed=False,
        failed_checks=[],
    )

    module.sys.argv = [
        "build_validation_rich_comparison_report.py",
        "--baseline",
        str(baseline),
        "--current",
        str(current),
        "--tuned",
        str(tuned),
        "--output-dir",
        str(tmp_path / "report"),
    ]
    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads(
        (tmp_path / "report" / "validation_rich_comparison_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["report_only"] is True
    assert payload["baseline"]["regressed"] is True
    assert payload["current"]["metrics"]["task_success_rate"] == pytest.approx(1.0)
    assert payload["tuned"]["metrics"]["precision_at_k"] == pytest.approx(0.45)
    assert payload["comparisons"]["baseline_vs_current"]["precision_at_k"]["delta"] == pytest.approx(
        0.075
    )
    assert payload["comparisons"]["current_vs_tuned"]["latency_p95_ms"]["delta"] == pytest.approx(
        -27.66
    )

    markdown = (
        tmp_path / "report" / "validation_rich_comparison_report.md"
    ).read_text(encoding="utf-8")
    assert "# Validation-Rich Comparison Report" in markdown
    assert "## baseline_vs_current" in markdown
    assert "| precision_at_k | 0.3500 | 0.4250 | +0.0750 |" in markdown


def test_validation_rich_comparison_report_requires_all_inputs(tmp_path: Path) -> None:
    module = _load_script("build_validation_rich_comparison_report.py")

    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_summary(
        baseline,
        generated_at="2026-03-10T00:00:00+00:00",
        task_success_rate=0.8,
        precision_at_k=0.35,
        noise_rate=0.65,
        latency_p95_ms=692.08,
        validation_test_count=4.0,
        evidence_insufficient_rate=0.2,
        missing_validation_rate=0.2,
        regressed=True,
        failed_checks=["precision_at_k"],
    )
    _write_summary(
        current,
        generated_at="2026-03-11T00:00:00+00:00",
        task_success_rate=1.0,
        precision_at_k=0.425,
        noise_rate=0.575,
        latency_p95_ms=617.66,
        validation_test_count=5.0,
        evidence_insufficient_rate=0.0,
        missing_validation_rate=0.0,
        regressed=False,
        failed_checks=[],
    )

    module.sys.argv = [
        "build_validation_rich_comparison_report.py",
        "--baseline",
        str(baseline),
        "--current",
        str(current),
        "--tuned",
        str(tmp_path / "missing.json"),
        "--output-dir",
        str(tmp_path / "report"),
    ]
    exit_code = module.main()
    assert exit_code == 2
