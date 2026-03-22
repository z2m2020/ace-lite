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


def _write_report(
    path: Path,
    *,
    generated_at: str,
    passed: bool,
    concept_precision: float,
    concept_noise: float,
    external_precision: float,
    external_noise: float,
    embedding_ratio: float,
    failures: list[dict[str, object]],
    validation_rich_q2_gate_summary: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": generated_at,
        "passed": passed,
        "tabiv3_matrix_summary": {
            "latency_metrics_mean": {
                "latency_p95_ms": 120.0,
                "repomap_latency_p95_ms": 15.0,
            }
        },
        "concept_gate": {
            "enabled": True,
            "passed": passed,
            "metrics": {
                "precision_at_k": concept_precision,
                "noise_rate": concept_noise,
            },
            "failures": failures,
        },
        "external_concept_gate": {
            "enabled": True,
            "passed": True,
            "metrics": {
                "precision_at_k": external_precision,
                "noise_rate": external_noise,
            },
            "failures": [],
        },
        "embedding_gate": {
            "enabled": True,
            "passed": True,
            "means": {
                "embedding_enabled_ratio": embedding_ratio,
            },
            "failures": [],
        },
    }
    if validation_rich_q2_gate_summary is not None:
        payload["validation_rich_benchmark"] = {
            "retrieval_control_plane_gate_summary": validation_rich_q2_gate_summary
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_freeze_trend_report_main_writes_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_freeze_trend_report.py")

    history_root = tmp_path / "history"
    report_a = history_root / "run-a" / "freeze_regression.json"
    report_b = history_root / "run-b" / "freeze_regression.json"

    _write_report(
        report_a,
        generated_at="2026-02-14T00:00:00+00:00",
        passed=True,
        concept_precision=0.62,
        concept_noise=0.38,
        external_precision=0.60,
        external_noise=0.40,
        embedding_ratio=0.8,
        failures=[],
        validation_rich_q2_gate_summary={
            "gate_passed": True,
            "adaptive_router_shadow_coverage": 0.86,
            "risk_upgrade_precision_gain": 0.02,
            "latency_p95_ms": 640.0,
            "failed_checks": [],
        },
    )
    _write_report(
        report_b,
        generated_at="2026-02-14T01:00:00+00:00",
        passed=False,
        concept_precision=0.58,
        concept_noise=0.44,
        external_precision=0.59,
        external_noise=0.41,
        embedding_ratio=0.7,
        failures=[
            {
                "repo": "ace-lite-engine",
                "metric": "noise_rate",
                "actual": 0.44,
                "operator": "<=",
                "expected": 0.38,
            }
        ],
        validation_rich_q2_gate_summary={
            "gate_passed": False,
            "adaptive_router_shadow_coverage": 0.74,
            "risk_upgrade_precision_gain": -0.03,
            "latency_p95_ms": 880.0,
            "failed_checks": ["adaptive_router_shadow_coverage"],
        },
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="src/ace_lite/index_stage/graph_lookup.py\nscripts/run_release_freeze_regression.py\n",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_freeze_trend_report.py",
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

    output = json.loads((tmp_path / "trend" / "freeze_trend_report.json").read_text(encoding="utf-8"))

    assert output["history_count"] == 2
    assert output["latest"]["passed"] is False
    assert output["previous"]["passed"] is True
    assert output["latest"]["validation_rich_q2_gate_passed"] is False
    assert output["latest"]["validation_rich_q2_shadow_coverage"] == pytest.approx(0.74)
    assert "validation_rich_q2_gate:adaptive_router_shadow_coverage" in output["latest"]["failure_signatures"]
    assert output["failure_top3"][0]["signature"] == "concept_gate:noise_rate"
    assert output["suspect_files"] == [
        "src/ace_lite/index_stage/graph_lookup.py",
        "scripts/run_release_freeze_regression.py",
    ]

    markdown = (tmp_path / "trend" / "freeze_trend_report.md").read_text(encoding="utf-8")
    assert "Validation-rich Q2 gate: passed=False, shadow_coverage=0.7400, risk_upgrade_gain=-0.0300, latency_p95_ms=880.00" in markdown
    assert "validation_q2_shadow=-0.1200" in markdown
    assert "validation_rich_q2_gate:adaptive_router_shadow_coverage" in markdown or output["failure_top3"][1]["signature"] == "validation_rich_q2_gate:adaptive_router_shadow_coverage"


def test_freeze_trend_report_extract_failure_signatures() -> None:
    module = _load_script("build_freeze_trend_report.py")
    payload = {
        "concept_gate": {
            "enabled": True,
            "passed": False,
            "failures": [{"metric": "precision_at_k"}],
        },
        "embedding_gate": {
            "enabled": True,
            "passed": False,
            "failures": [],
        },
    }

    signatures = module._extract_failure_signatures(payload)
    assert "concept_gate:precision_at_k" in signatures
    assert "embedding_gate:gate_failed" in signatures
