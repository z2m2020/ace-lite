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


def test_checkpoint_manifest_phase1_includes_gap_report() -> None:
    """Phase 1 checkpoint must track the retrieval-to-task gap report artifact."""
    payload = build_checkpoint_manifest_payload(
        generated_at="2026-04-26T00:00:00+00:00",
        git_sha="abc5678",
        phase="phase1",
        included_artifacts=[
            {
                "path": "artifacts/checkpoints/phase1/2026-04-26/problem_ledger.json",
                "present": True,
                "schema_version": "problem_ledger_v1",
                "notes": "Phase 1 problem ledger.",
            },
            {
                "path": "artifacts/gap-reports/2026-04-26/gap_report.json",
                "present": True,
                "schema_version": "retrieval_task_gap_report_v1",
                "notes": "Retrieval-to-task gap report for Phase 1.",
            },
            {
                "path": "artifacts/gap-reports/2026-04-26/gap_report.md",
                "present": True,
                "schema_version": "retrieval_task_gap_report_v1",
                "notes": "Gap report markdown summary.",
            },
        ],
    )

    validated = validate_checkpoint_manifest_payload(payload)
    assert validated["phase"] == "phase1"
    gap_artifacts = [a for a in validated["included_artifacts"] if "gap_report" in a["path"]]
    assert len(gap_artifacts) == 2
    assert all(a["present"] for a in gap_artifacts)
    assert all(a["status"] == "present" for a in gap_artifacts)
    # No warnings because all artifacts are present
    assert validated["warnings"] == []
