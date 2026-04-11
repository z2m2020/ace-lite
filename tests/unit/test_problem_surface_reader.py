from __future__ import annotations

import json
from pathlib import Path

from ace_lite.benchmark.problem_surface_reader import (
    build_problem_surface_from_benchmark_artifacts,
)
from ace_lite.problem_surface_schema import PROBLEM_SURFACE_SCHEMA_VERSION


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_problem_surface_reader_maps_synthetic_results_json_to_pq_surfaces(
    tmp_path: Path,
) -> None:
    results_path = _write_json(
        tmp_path / "artifacts" / "benchmark" / "results.json",
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 0.91,
                "precision_at_k": 0.74,
                "noise_rate": 0.12,
                "validation_test_count": 3,
            },
        },
    )

    payload = build_problem_surface_from_benchmark_artifacts(results_path=results_path)

    assert payload["schema_version"] == PROBLEM_SURFACE_SCHEMA_VERSION
    assert set(payload["surfaces"]) == {f"PQ-00{i}" for i in range(1, 10)} | {"PQ-010"}

    pq001 = payload["surfaces"]["PQ-001"]
    assert pq001["status"] == "observed"
    assert pq001["artifact_paths"] == [str(results_path)]
    assert [entry["metric_name"] for entry in pq001["metric_entries"]] == [
        "task_success_rate",
        "precision_at_k",
        "noise_rate",
    ]
    assert pq001["metric_entries"][0]["value"] == 0.91


def test_problem_surface_reader_maps_freeze_and_summary_artifacts_to_documented_pq_entries(
    tmp_path: Path,
) -> None:
    freeze_path = _write_json(
        tmp_path / "artifacts" / "release-freeze" / "freeze_regression.json",
        {
            "generated_at": "2026-04-12T00:00:00+00:00",
            "passed": False,
            "tabiv3_matrix_summary": {
                "latency_metrics_mean": {
                    "latency_p95_ms": 120.0,
                    "repomap_latency_p95_ms": 15.0,
                }
            },
            "concept_gate": {
                "enabled": True,
                "passed": False,
                "metrics": {
                    "precision_at_k": 0.7,
                    "noise_rate": 0.2,
                },
                "failures": [],
            },
            "embedding_gate": {
                "enabled": True,
                "passed": True,
                "means": {
                    "embedding_enabled_ratio": 0.85,
                },
                "failures": [],
            },
            "validation_rich_benchmark": {
                "retrieval_control_plane_gate_summary": {
                    "gate_passed": True,
                    "adaptive_router_shadow_coverage": 0.86,
                    "risk_upgrade_precision_gain": 0.02,
                },
                "retrieval_frontier_gate_summary": {
                    "gate_passed": True,
                    "deep_symbol_case_recall": 0.93,
                    "native_scip_loaded_rate": 0.78,
                    "precision_at_k": 0.68,
                    "noise_rate": 0.19,
                },
                "validation_probe_summary": {
                    "validation_test_count": 5.0,
                    "probe_enabled_ratio": 0.67,
                    "probe_failure_rate": 0.1,
                },
                "source_plan_validation_feedback_summary": {
                    "present_ratio": 1.0,
                    "failure_rate": 0.2,
                    "executed_test_count_mean": 0.75,
                },
            },
        },
    )
    summary_path = _write_json(
        tmp_path / "artifacts" / "benchmark" / "summary.json",
        {
            "metrics": {
                "validation_test_count": 4,
            }
        },
    )

    payload = build_problem_surface_from_benchmark_artifacts(
        freeze_regression_path=freeze_path,
        summary_path=summary_path,
        generated_at="2026-04-12T00:00:00+00:00",
        phase="benchmark_review",
    )

    pq001 = payload["surfaces"]["PQ-001"]
    assert pq001["status"] == "observed"
    assert pq001["artifact_paths"] == [str(freeze_path)]
    assert [entry["metric_name"] for entry in pq001["metric_entries"]] == [
        "precision_at_k",
        "noise_rate",
    ]

    pq002 = payload["surfaces"]["PQ-002"]
    assert pq002["status"] == "observed"
    assert pq002["artifact_paths"] == [str(freeze_path)]
    assert [entry["metric_name"] for entry in pq002["metric_entries"]] == [
        "adaptive_router_shadow_coverage",
        "risk_upgrade_precision_gain",
    ]

    pq004 = payload["surfaces"]["PQ-004"]
    assert pq004["status"] == "observed"
    assert pq004["artifact_paths"] == [str(freeze_path), str(summary_path)]
    assert [entry["metric_name"] for entry in pq004["metric_entries"]] == [
        "validation_coverage",
        "validation_test_count",
        "validation_test_count",
        "probe_enabled_ratio",
        "feedback_present_ratio",
        "feedback_executed_test_count_mean",
    ]

    pq006 = payload["surfaces"]["PQ-006"]
    assert pq006["status"] == "observed"
    assert pq006["artifact_paths"] == [str(freeze_path)]
