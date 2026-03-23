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
                    "retrieval_control_plane_gate_summary": {
                        "gate_passed": False,
                        "regression_evaluated": True,
                        "benchmark_regression_detected": True,
                        "failed_checks": ["benchmark_regression_detected"],
                    },
                    "retrieval_frontier_gate_summary": {
                        "gate_passed": False,
                        "failed_checks": ["native_scip_loaded_rate", "noise_rate"],
                        "deep_symbol_case_recall": 0.81,
                        "native_scip_loaded_rate": 0.68,
                    },
                    "deep_symbol_summary": {
                        "case_count": 2.0,
                        "recall": 0.81,
                    },
                    "native_scip_summary": {
                        "loaded_rate": 0.68,
                        "document_count_mean": 4.0,
                        "definition_occurrence_count_mean": 6.0,
                        "reference_occurrence_count_mean": 10.0,
                        "symbol_definition_count_mean": 2.0,
                    },
                    "validation_probe_summary": {
                        "validation_test_count": 4.0,
                        "probe_enabled_ratio": 0.5,
                        "probe_executed_count_mean": 1.0,
                        "probe_failure_rate": 0.25,
                    },
                    "source_plan_validation_feedback_summary": {
                        "present_ratio": 1.0,
                        "failure_rate": 0.5,
                        "issue_count_mean": 1.0,
                        "probe_issue_count_mean": 0.5,
                        "probe_executed_count_mean": 1.0,
                        "selected_test_count_mean": 1.0,
                        "executed_test_count_mean": 0.5,
                    },
                    "source_plan_failure_signal_summary": {
                        "present_ratio": 1.0,
                        "failure_rate": 0.5,
                        "issue_count_mean": 1.0,
                        "probe_issue_count_mean": 0.5,
                        "probe_executed_count_mean": 1.0,
                        "selected_test_count_mean": 1.0,
                        "executed_test_count_mean": 0.5,
                        "replay_cache_origin_ratio": 1.0,
                    },
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
    assert any(
        "retrieval control plane gate is not passed" in reason
        for reason in payload["reasons"]
    )
    assert any(
        "retrieval frontier gate is not passed" in reason
        for reason in payload["reasons"]
    )
    assert any("stability classification" in reason for reason in payload["reasons"])
    assert any(
        gate["name"] == "retrieval_control_plane" and gate["passed"] is False
        for gate in payload["gates"]
    )
    assert any(
        gate["name"] == "retrieval_frontier" and gate["passed"] is False
        for gate in payload["gates"]
    )
    retrieval_frontier_gate = next(
        gate for gate in payload["gates"] if gate["name"] == "retrieval_frontier"
    )
    assert retrieval_frontier_gate["deep_symbol_summary"]["case_count"] == pytest.approx(2.0)
    assert retrieval_frontier_gate["native_scip_summary"]["document_count_mean"] == pytest.approx(4.0)
    validation_probe_gate = next(
        gate for gate in payload["gates"] if gate["name"] == "validation_probe_summary"
    )
    assert validation_probe_gate["probe_failure_rate"] == pytest.approx(0.25)
    source_plan_feedback_gate = next(
        gate
        for gate in payload["gates"]
        if gate["name"] == "source_plan_validation_feedback"
    )
    assert source_plan_feedback_gate["executed_test_count_mean"] == pytest.approx(0.5)
    source_plan_failure_gate = next(
        gate for gate in payload["gates"] if gate["name"] == "source_plan_failure_signal"
    )
    assert source_plan_failure_gate["replay_cache_origin_ratio"] == pytest.approx(1.0)


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
                    "retrieval_control_plane_gate_summary": {
                        "gate_passed": True,
                        "regression_evaluated": True,
                        "benchmark_regression_detected": False,
                        "failed_checks": [],
                    },
                    "retrieval_frontier_gate_summary": {
                        "gate_passed": True,
                        "failed_checks": [],
                        "deep_symbol_case_recall": 0.92,
                        "native_scip_loaded_rate": 0.76,
                    },
                    "deep_symbol_summary": {
                        "case_count": 3.0,
                        "recall": 0.92,
                    },
                    "native_scip_summary": {
                        "loaded_rate": 0.76,
                        "document_count_mean": 5.0,
                        "definition_occurrence_count_mean": 7.0,
                        "reference_occurrence_count_mean": 11.0,
                        "symbol_definition_count_mean": 3.0,
                    },
                    "validation_probe_summary": {
                        "validation_test_count": 5.0,
                        "probe_enabled_ratio": 0.67,
                        "probe_executed_count_mean": 1.5,
                        "probe_failure_rate": 0.1,
                    },
                    "source_plan_validation_feedback_summary": {
                        "present_ratio": 1.0,
                        "failure_rate": 0.2,
                        "issue_count_mean": 0.25,
                        "probe_issue_count_mean": 0.25,
                        "probe_executed_count_mean": 1.5,
                        "selected_test_count_mean": 1.0,
                        "executed_test_count_mean": 0.75,
                    },
                    "source_plan_failure_signal_summary": {
                        "present_ratio": 1.0,
                        "failure_rate": 0.2,
                        "issue_count_mean": 0.25,
                        "probe_issue_count_mean": 0.25,
                        "probe_executed_count_mean": 1.5,
                        "selected_test_count_mean": 1.0,
                        "executed_test_count_mean": 0.75,
                        "replay_cache_origin_ratio": 1.0,
                    },
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
    assert any(
        gate["name"] == "retrieval_control_plane" and gate["passed"] is True
        for gate in payload["gates"]
    )
    assert any(
        gate["name"] == "retrieval_frontier" and gate["passed"] is True
        for gate in payload["gates"]
    )
    retrieval_frontier_gate = next(
        gate for gate in payload["gates"] if gate["name"] == "retrieval_frontier"
    )
    assert retrieval_frontier_gate["deep_symbol_summary"]["recall"] == pytest.approx(0.92)
    assert retrieval_frontier_gate["native_scip_summary"]["loaded_rate"] == pytest.approx(0.76)
    validation_probe_gate = next(
        gate for gate in payload["gates"] if gate["name"] == "validation_probe_summary"
    )
    assert validation_probe_gate["probe_executed_count_mean"] == pytest.approx(1.5)
    source_plan_feedback_gate = next(
        gate
        for gate in payload["gates"]
        if gate["name"] == "source_plan_validation_feedback"
    )
    assert source_plan_feedback_gate["failure_rate"] == pytest.approx(0.2)
    source_plan_failure_gate = next(
        gate for gate in payload["gates"] if gate["name"] == "source_plan_failure_signal"
    )
    assert source_plan_failure_gate["failure_rate"] == pytest.approx(0.2)


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
                    "retrieval_control_plane_gate_summary": {
                        "gate_passed": True,
                        "regression_evaluated": True,
                        "benchmark_regression_detected": False,
                        "failed_checks": [],
                    },
                    "retrieval_frontier_gate_summary": {
                        "gate_passed": True,
                        "failed_checks": [],
                        "deep_symbol_case_recall": 0.93,
                        "native_scip_loaded_rate": 0.78,
                    },
                    "deep_symbol_summary": {
                        "case_count": 3.0,
                        "recall": 0.93,
                    },
                    "native_scip_summary": {
                        "loaded_rate": 0.78,
                        "document_count_mean": 5.5,
                        "definition_occurrence_count_mean": 7.5,
                        "reference_occurrence_count_mean": 11.5,
                        "symbol_definition_count_mean": 3.5,
                    },
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
