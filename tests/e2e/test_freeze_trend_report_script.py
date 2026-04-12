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
    validation_rich_q3_gate_summary: dict[str, object] | None = None,
    deep_symbol_summary: dict[str, object] | None = None,
    native_scip_summary: dict[str, object] | None = None,
    validation_probe_summary: dict[str, object] | None = None,
    source_plan_validation_feedback_summary: dict[str, object] | None = None,
    source_plan_failure_signal_summary: dict[str, object] | None = None,
    confidence_summary: dict[str, object] | None = None,
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
    if (
        validation_rich_q2_gate_summary is not None
        or validation_rich_q3_gate_summary is not None
    ):
        benchmark_payload: dict[str, object] = {}
        if validation_rich_q2_gate_summary is not None:
            benchmark_payload["retrieval_control_plane_gate_summary"] = (
                validation_rich_q2_gate_summary
            )
        if validation_rich_q3_gate_summary is not None:
            benchmark_payload["retrieval_frontier_gate_summary"] = (
                validation_rich_q3_gate_summary
            )
        if deep_symbol_summary is not None:
            benchmark_payload["deep_symbol_summary"] = deep_symbol_summary
        if native_scip_summary is not None:
            benchmark_payload["native_scip_summary"] = native_scip_summary
        if validation_probe_summary is not None:
            benchmark_payload["validation_probe_summary"] = validation_probe_summary
        if source_plan_validation_feedback_summary is not None:
            benchmark_payload["source_plan_validation_feedback_summary"] = (
                source_plan_validation_feedback_summary
            )
        if source_plan_failure_signal_summary is not None:
            benchmark_payload["source_plan_failure_signal_summary"] = (
                source_plan_failure_signal_summary
            )
        if confidence_summary is not None:
            benchmark_payload["confidence_summary"] = confidence_summary
        payload["validation_rich_benchmark"] = benchmark_payload
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
        validation_rich_q3_gate_summary={
            "gate_passed": True,
            "deep_symbol_case_recall": 0.93,
            "native_scip_loaded_rate": 0.78,
            "precision_at_k": 0.62,
            "noise_rate": 0.34,
            "failed_checks": [],
        },
        deep_symbol_summary={"case_count": 3.0, "recall": 0.93},
        native_scip_summary={"loaded_rate": 0.78, "document_count_mean": 5.0},
        validation_probe_summary={
            "validation_test_count": 5.0,
            "probe_enabled_ratio": 0.67,
            "probe_executed_count_mean": 1.5,
            "probe_failure_rate": 0.1,
        },
        source_plan_validation_feedback_summary={
            "present_ratio": 1.0,
            "failure_rate": 0.2,
            "issue_count_mean": 0.25,
            "probe_issue_count_mean": 0.25,
            "probe_executed_count_mean": 1.5,
            "selected_test_count_mean": 1.0,
            "executed_test_count_mean": 0.75,
        },
        source_plan_failure_signal_summary={
            "present_ratio": 1.0,
            "failure_rate": 0.2,
            "issue_count_mean": 0.25,
            "replay_cache_origin_ratio": 1.0,
        },
        confidence_summary={
            "extracted_count": 3,
            "inferred_count": 1,
            "ambiguous_count": 1,
            "unknown_count": 0,
            "total_count": 5,
            "low_confidence_chunks": ["chunk-a"],
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
        validation_rich_q3_gate_summary={
            "gate_passed": False,
            "deep_symbol_case_recall": 0.84,
            "native_scip_loaded_rate": 0.65,
            "precision_at_k": 0.58,
            "noise_rate": 0.39,
            "failed_checks": ["native_scip_loaded_rate", "noise_rate"],
        },
        deep_symbol_summary={"case_count": 2.0, "recall": 0.84},
        native_scip_summary={"loaded_rate": 0.65, "document_count_mean": 4.0},
        validation_probe_summary={
            "validation_test_count": 4.0,
            "probe_enabled_ratio": 0.5,
            "probe_executed_count_mean": 1.0,
            "probe_failure_rate": 0.25,
        },
        source_plan_validation_feedback_summary={
            "present_ratio": 1.0,
            "failure_rate": 0.5,
            "issue_count_mean": 1.0,
            "probe_issue_count_mean": 0.5,
            "probe_executed_count_mean": 1.0,
            "selected_test_count_mean": 1.0,
            "executed_test_count_mean": 0.5,
        },
        source_plan_failure_signal_summary={
            "present_ratio": 1.0,
            "failure_rate": 0.5,
            "issue_count_mean": 1.0,
            "replay_cache_origin_ratio": 1.0,
        },
        confidence_summary={
            "extracted_count": 2,
            "inferred_count": 1,
            "ambiguous_count": 1,
            "unknown_count": 0,
            "total_count": 4,
            "low_confidence_chunks": ["chunk-b"],
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
    assert output["latest"]["validation_rich_q3_gate_passed"] is False
    assert output["latest"]["validation_rich_q3_native_scip_loaded_rate"] == pytest.approx(0.65)
    assert output["latest"]["validation_rich_q3_deep_symbol_case_count"] == pytest.approx(2.0)
    assert output["latest"]["validation_rich_q3_native_scip_document_count_mean"] == pytest.approx(4.0)
    assert output["latest"]["validation_rich_q4_probe_enabled_ratio"] == pytest.approx(0.5)
    assert output["latest"]["validation_rich_q4_feedback_executed_test_count_mean"] == pytest.approx(0.5)
    assert output["latest"]["validation_probe_summary"]["probe_failure_rate"] == pytest.approx(0.25)
    assert output["latest"]["source_plan_validation_feedback_summary"]["failure_rate"] == pytest.approx(0.5)
    assert output["latest"]["source_plan_failure_signal_summary"]["failure_rate"] == pytest.approx(0.5)
    assert "validation_rich_q3_gate:native_scip_loaded_rate" in output["latest"]["failure_signatures"]
    assert output["failure_top3"][0]["signature"] == "concept_gate:noise_rate"
    assert output["suspect_files"] == [
        "src/ace_lite/index_stage/graph_lookup.py",
        "scripts/run_release_freeze_regression.py",
    ]
    assert output["pq_003_overlay"]["confidence_breakdown"] == {
        "total_candidates": 4,
        "extracted_count": 2,
        "inferred_count": 1,
        "ambiguous_count": 1,
        "unknown_count": 0,
        "extracted_ratio": 0.5,
        "inferred_ratio": 0.25,
        "ambiguous_ratio": 0.25,
        "unknown_ratio": 0.0,
    }
    assert output["pq_003_overlay"]["derived_metrics"] == {
        "evidence_strength_score": 0.75,
        "deep_symbol_case_recall": 0.84,
        "native_scip_loaded_rate": 0.65,
    }
    assert output["pq_003_overlay"]["ratios"] == {
        "hint_only_ratio": 0.25,
        "ambiguous_ratio": 0.25,
        "unknown_ratio": 0.0,
        "grounded_ratio": 0.75,
    }
    assert output["pq_003_overlay"]["low_confidence_chunks"] == ["chunk-b"]

    markdown = (tmp_path / "trend" / "freeze_trend_report.md").read_text(encoding="utf-8")
    assert "Validation-rich Q2 gate: passed=False, shadow_coverage=0.7400, risk_upgrade_gain=-0.0300, latency_p95_ms=880.00" in markdown
    assert "Validation-rich Q3 gate: passed=False, deep_symbol_case_recall=0.8400, native_scip_loaded_rate=0.6500, precision_at_k=0.5800, noise_rate=0.3900" in markdown
    assert "Validation-rich Q3 evidence: deep_symbol_case_count=2.0000, native_scip_document_count_mean=4.0000" in markdown
    assert "Validation-rich Q4 validation probe: probe_enabled_ratio=0.5000, probe_failure_rate=0.2500" in markdown
    assert "Validation-rich Q4 source-plan feedback: present_ratio=1.0000, failure_rate=0.5000, executed_test_count_mean=0.5000" in markdown
    assert "Validation-rich Q1 failure signal: present_ratio=1.0000, failure_rate=0.5000, replay_cache_origin_ratio=1.0000" in markdown
    assert "validation_q2_shadow=-0.1200" in markdown
    assert "validation_q3_native_scip=-0.1300" in markdown
    assert "validation_q3_case_count=-1.0000" in markdown
    assert "validation_q3_document_count=-1.0000" in markdown
    assert "Validation-rich Q4 delta: probe_enabled=-0.1700, probe_failure=+0.1500, feedback_present=+0.0000, feedback_failure=+0.3000, feedback_executed_tests=-0.2500" in markdown
    assert "Validation-rich Q1 delta: failure_present=+0.0000, failure_rate=+0.3000, replay_cache_origin=+0.0000" in markdown
    assert "validation_rich_q2_gate:adaptive_router_shadow_coverage" in markdown or output["failure_top3"][1]["signature"] == "validation_rich_q2_gate:adaptive_router_shadow_coverage"
    assert "validation_rich_q3_gate:native_scip_loaded_rate" in markdown or any(
        item["signature"] == "validation_rich_q3_gate:native_scip_loaded_rate"
        for item in output["failure_top3"]
    )


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


def test_freeze_trend_report_extract_failure_signatures_includes_q3_gate() -> None:
    module = _load_script("build_freeze_trend_report.py")
    payload = {
        "validation_rich_benchmark": {
            "retrieval_frontier_gate_summary": {
                "gate_passed": False,
                "failed_checks": ["native_scip_loaded_rate", "noise_rate"],
            }
        }
    }

    signatures = module._extract_failure_signatures(payload)
    assert "validation_rich_q3_gate:native_scip_loaded_rate" in signatures
    assert "validation_rich_q3_gate:noise_rate" in signatures
