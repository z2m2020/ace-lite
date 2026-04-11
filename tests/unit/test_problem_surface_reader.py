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
            "task_success_mean": 0.88,
            "retrieval_metrics_mean": {
                "precision_at_k": 0.7,
                "noise_rate": 0.2,
            },
            "memory_metrics_mean": {
                "notes_hit_ratio": 0.55,
                "capture_trigger_ratio": 0.4,
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
        "task_success_rate",
        "precision_at_k",
        "noise_rate",
    ]

    pq004 = payload["surfaces"]["PQ-004"]
    assert pq004["status"] == "observed"
    assert pq004["artifact_paths"] == [str(summary_path)]
    assert pq004["metric_entries"][0]["metric_name"] == "validation_test_count"

    pq005 = payload["surfaces"]["PQ-005"]
    assert pq005["status"] == "observed"
    assert pq005["artifact_paths"] == [str(freeze_path)]

    pq006 = payload["surfaces"]["PQ-006"]
    assert pq006["status"] == "observed"
    assert pq006["artifact_paths"] == [str(freeze_path)]
