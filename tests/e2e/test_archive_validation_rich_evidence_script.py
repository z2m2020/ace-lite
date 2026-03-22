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
                }
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

    todo = (dated_root / "next_cycle_todo.md").read_text(encoding="utf-8")
    assert "## Q2 Retrieval Control Plane Gate" in todo
    assert "- Gate passed: False" in todo
    assert "- Resolve: need more evidence" in todo
