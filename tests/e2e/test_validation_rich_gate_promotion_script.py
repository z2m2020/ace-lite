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


def test_validation_rich_gate_promotion_reports_stay_report_only(tmp_path: Path) -> None:
    module = _load_script("evaluate_validation_rich_gate_promotion.py")

    trend = tmp_path / "trend.json"
    stability = tmp_path / "stability.json"
    comparison = tmp_path / "comparison.json"
    trend.write_text(
        json.dumps(
            {
                "history_count": 1,
                "latest": {
                    "regressed": True,
                    "task_success_rate": 0.8,
                    "precision_at_k": 0.35,
                    "noise_rate": 0.65,
                    "latency_p95_ms": 710.0,
                    "validation_test_count": 4.0,
                    "evidence_insufficient_rate": 0.2,
                    "missing_validation_rate": 0.2,
                },
                "failed_check_top3": [{"check": "precision_at_k", "count": 1}],
            }
        ),
        encoding="utf-8",
    )
    stability.write_text(
        json.dumps({"classification": "mixed", "passed": False, "failure_rate": 0.5}),
        encoding="utf-8",
    )
    comparison.write_text(json.dumps({}), encoding="utf-8")

    module.sys.argv = [
        "evaluate_validation_rich_gate_promotion.py",
        "--trend-report",
        str(trend),
        "--stability-report",
        str(stability),
        "--comparison-report",
        str(comparison),
        "--output",
        str(tmp_path / "decision.json"),
    ]
    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
    assert payload["recommendation"] == "stay_report_only"
    assert payload["eligible"] is False
    assert any("history_count" in reason for reason in payload["reasons"])
    assert any("stability classification" in reason for reason in payload["reasons"])


def test_validation_rich_gate_promotion_reports_eligible(tmp_path: Path) -> None:
    module = _load_script("evaluate_validation_rich_gate_promotion.py")

    trend = tmp_path / "trend.json"
    stability = tmp_path / "stability.json"
    comparison = tmp_path / "comparison.json"
    trend.write_text(
        json.dumps(
            {
                "history_count": 3,
                "latest": {
                    "regressed": False,
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.45,
                    "noise_rate": 0.55,
                    "latency_p95_ms": 590.0,
                    "validation_test_count": 5.0,
                    "evidence_insufficient_rate": 0.0,
                    "missing_validation_rate": 0.0,
                },
                "failed_check_top3": [],
            }
        ),
        encoding="utf-8",
    )
    stability.write_text(
        json.dumps({"classification": "stable_pass", "passed": True, "failure_rate": 0.0}),
        encoding="utf-8",
    )
    comparison.write_text(
        json.dumps(
            {
                "current": {"metrics": {"noise_rate": 0.55, "missing_validation_rate": 0.0, "evidence_insufficient_rate": 0.0}},
                "tuned": {"metrics": {"noise_rate": 0.54, "missing_validation_rate": 0.0, "evidence_insufficient_rate": 0.0}},
            }
        ),
        encoding="utf-8",
    )

    module.sys.argv = [
        "evaluate_validation_rich_gate_promotion.py",
        "--trend-report",
        str(trend),
        "--stability-report",
        str(stability),
        "--comparison-report",
        str(comparison),
        "--output",
        str(tmp_path / "decision.json"),
    ]
    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
    assert payload["recommendation"] == "eligible_for_enforced"
    assert payload["eligible"] is True


def test_validation_rich_gate_promotion_treats_history_failed_checks_as_warning(
    tmp_path: Path,
) -> None:
    module = _load_script("evaluate_validation_rich_gate_promotion.py")

    trend = tmp_path / "trend.json"
    stability = tmp_path / "stability.json"
    comparison = tmp_path / "comparison.json"
    trend.write_text(
        json.dumps(
            {
                "history_count": 4,
                "latest": {
                    "regressed": False,
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.45,
                    "noise_rate": 0.55,
                    "latency_p95_ms": 590.0,
                    "validation_test_count": 5.0,
                    "evidence_insufficient_rate": 0.0,
                    "missing_validation_rate": 0.0,
                },
                "failed_check_top3": [{"check": "latency_p95_ms", "count": 3}],
            }
        ),
        encoding="utf-8",
    )
    stability.write_text(
        json.dumps({"classification": "stable_pass", "passed": True, "failure_rate": 0.0}),
        encoding="utf-8",
    )
    comparison.write_text(
        json.dumps(
            {
                "current": {
                    "metrics": {
                        "noise_rate": 0.55,
                        "missing_validation_rate": 0.0,
                        "evidence_insufficient_rate": 0.0,
                    }
                },
                "tuned": {
                    "metrics": {
                        "noise_rate": 0.54,
                        "missing_validation_rate": 0.0,
                        "evidence_insufficient_rate": 0.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    module.sys.argv = [
        "evaluate_validation_rich_gate_promotion.py",
        "--trend-report",
        str(trend),
        "--stability-report",
        str(stability),
        "--comparison-report",
        str(comparison),
        "--output",
        str(tmp_path / "decision.json"),
    ]
    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
    assert payload["recommendation"] == "eligible_for_enforced"
    assert payload["eligible"] is True
    assert "trend report still shows failed_checks history" not in payload["reasons"]
    assert "trend report still shows failed_checks history" in payload["warnings"]
