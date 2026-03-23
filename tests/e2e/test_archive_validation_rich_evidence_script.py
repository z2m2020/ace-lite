from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def test_archive_validation_rich_evidence_main_copies_files(tmp_path: Path) -> None:
    module = _load_script("archive_validation_rich_evidence.py")

    summary = tmp_path / "latest" / "summary.json"
    results = tmp_path / "latest" / "results.json"
    report = tmp_path / "latest" / "report.md"
    trend_dir = tmp_path / "latest" / "trend"
    stability_dir = tmp_path / "latest" / "stability"
    comparison_dir = tmp_path / "latest" / "comparison"
    decision = tmp_path / "latest" / "promotion_decision.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "retrieval_control_plane_gate_summary": {
                    "regression_evaluated": True,
                    "benchmark_regression_detected": True,
                    "failed_checks": [
                        "benchmark_regression_detected",
                        "adaptive_router_shadow_coverage",
                    ],
                    "adaptive_router_shadow_coverage": 0.75,
                    "risk_upgrade_precision_gain": -0.01,
                    "latency_p95_ms": 692.08,
                    "gate_passed": False,
                },
                "retrieval_frontier_gate_summary": {
                    "deep_symbol_case_recall": 0.81,
                    "native_scip_loaded_rate": 0.68,
                    "precision_at_k": 0.35,
                    "noise_rate": 0.65,
                    "failed_checks": [
                        "deep_symbol_case_recall",
                        "native_scip_loaded_rate",
                    ],
                    "gate_passed": False,
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
                    "issue_count_mean": 1.0,
                    "failure_rate": 0.5,
                    "probe_issue_count_mean": 0.5,
                    "probe_executed_count_mean": 1.0,
                    "probe_failure_rate": 0.25,
                    "selected_test_count_mean": 1.0,
                    "executed_test_count_mean": 0.5,
                },
                "source_plan_failure_signal_summary": {
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
            }
        ),
        encoding="utf-8",
    )
    results.write_text("{}", encoding="utf-8")
    report.write_text("# report\n", encoding="utf-8")
    trend_dir.mkdir(parents=True, exist_ok=True)
    (trend_dir / "validation_rich_trend_report.json").write_text("{}", encoding="utf-8")
    stability_dir.mkdir(parents=True, exist_ok=True)
    (stability_dir / "stability_summary.json").write_text("{}", encoding="utf-8")
    comparison_dir.mkdir(parents=True, exist_ok=True)
    (comparison_dir / "validation_rich_comparison_report.json").write_text("{}", encoding="utf-8")
    decision.write_text(
        json.dumps({"recommendation": "stay_report_only", "reasons": ["need more evidence"]}),
        encoding="utf-8",
    )
    decision.with_suffix(".md").write_text("# decision\n", encoding="utf-8")

    module.sys.argv = [
        "archive_validation_rich_evidence.py",
        "--date",
        "2026-09-30",
        "--summary",
        str(summary),
        "--results",
        str(results),
        "--report",
        str(report),
        "--trend-dir",
        str(trend_dir),
        "--stability-dir",
        str(stability_dir),
        "--comparison-dir",
        str(comparison_dir),
        "--promotion-decision",
        str(decision),
        "--output-root",
        str(tmp_path / "archive"),
    ]
    exit_code = module.main()
    assert exit_code == 0

    dated_root = tmp_path / "archive" / "2026-09-30"
    assert (dated_root / "summary.json").exists()
    assert (dated_root / "results.json").exists()
    assert (dated_root / "report.md").exists()
    assert (dated_root / "trend" / "validation_rich_trend_report.json").exists()
    assert (dated_root / "stability" / "stability_summary.json").exists()
    assert (dated_root / "comparison" / "validation_rich_comparison_report.json").exists()
    assert (dated_root / "promotion_decision.json").exists()
    assert (dated_root / "archive_manifest.json").exists()
    assert (dated_root / "next_cycle_todo.md").exists()

    manifest = json.loads((dated_root / "archive_manifest.json").read_text(encoding="utf-8"))
    assert manifest["retrieval_control_plane_gate_summary"]["gate_passed"] is False
    assert (
        manifest["retrieval_control_plane_gate_summary"][
            "benchmark_regression_detected"
        ]
        is True
    )
    assert manifest["retrieval_frontier_gate_summary"]["gate_passed"] is False
    assert (
        manifest["retrieval_frontier_gate_summary"]["native_scip_loaded_rate"] == 0.68
    )
    assert manifest["deep_symbol_summary"] == {
        "case_count": 2.0,
        "recall": 0.81,
    }
    assert manifest["native_scip_summary"]["document_count_mean"] == 4.0
    assert manifest["validation_probe_summary"]["probe_failure_rate"] == 0.25
    assert (
        manifest["source_plan_validation_feedback_summary"]["executed_test_count_mean"]
        == 0.5
    )
    assert manifest["source_plan_failure_signal_summary"]["failure_rate"] == 0.5

    todo = (dated_root / "next_cycle_todo.md").read_text(encoding="utf-8")
    assert "## Q2 Retrieval Control Plane Gate" in todo
    assert "## Q3 Retrieval Frontier Gate" in todo
    assert "## Q3 Frontier Evidence" in todo
    assert "## Q4 Validation Probe Summary" in todo
    assert "## Q4 Source Plan Validation Feedback" in todo
    assert "## Q1 Source Plan Failure Signal Summary" in todo
    assert "- Gate passed: False" in todo
    assert "- Native SCIP loaded rate: 0.6800" in todo
    assert "- Deep symbol case count: 2.0000; recall: 0.8100" in todo
    assert "- Probe failure rate: 0.2500" in todo
    assert "- Executed test count mean: 0.5000" in todo
    assert "- Replay cache origin ratio: 1.0000; observability origin ratio: 0.0000; source_plan origin ratio: 0.0000; validate_step origin ratio: 0.0000" in todo
    assert "- Resolve: need more evidence" in todo
