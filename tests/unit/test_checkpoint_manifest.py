from __future__ import annotations

from ace_lite.checkpoint_manifest import (
    build_checkpoint_manifest_payload,
    validate_checkpoint_manifest_payload,
)
from ace_lite.checkpoint_manifest_schema import CHECKPOINT_MANIFEST_SCHEMA_VERSION


def test_checkpoint_manifest_marks_missing_artifacts_and_emits_warnings() -> None:
    payload = build_checkpoint_manifest_payload(
        generated_at="2026-04-12T00:00:00+00:00",
        git_sha="abc1234",
        phase="baseline",
        included_artifacts=[
            {
                "path": "benchmark/results.json",
                "present": True,
                "schema_version": "benchmark_results_v1",
                "notes": "Benchmark summary exists.",
            },
            {
                "path": "benchmark/report.md",
                "present": False,
                "schema_version": "benchmark_report_v1",
                "notes": "Expected later; checkpoint still records it.",
            },
            {
                "path": "benchmark/summary.json",
                "present": True,
                "schema_version": "benchmark_summary_v1",
                "notes": "Baseline summary exists.",
            },
        ],
    )

    validated = validate_checkpoint_manifest_payload(payload)

    assert validated["schema_version"] == CHECKPOINT_MANIFEST_SCHEMA_VERSION
    assert [artifact["status"] for artifact in validated["included_artifacts"]] == [
        "present",
        "missing",
        "present",
    ]
    assert validated["included_artifacts"][1]["present"] is False
    assert validated["warnings"] == ["artifact_missing:benchmark/report.md"]
