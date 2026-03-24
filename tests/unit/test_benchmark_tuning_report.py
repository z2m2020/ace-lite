from __future__ import annotations

import json
from pathlib import Path

from ace_lite.benchmark.tuning_report import (
    build_benchmark_tuning_report,
    write_tuning_report,
)


def test_build_benchmark_tuning_report_emits_conservative_overlay_candidates() -> None:
    summary = {
        "repo": "demo",
        "case_count": 4,
        "threshold_profile": "default",
        "metrics": {
            "recall_at_k": 0.82,
            "dependency_recall": 0.74,
            "chunk_hit_at_k": 0.78,
            "precision_at_k": 0.54,
            "noise_rate": 0.51,
            "latency_p95_ms": 980.0,
            "graph_source_provider_loaded_ratio": 0.75,
            "embedding_fallback_ratio": 0.2,
        },
        "tuning_context_summary": {
            "report_only": True,
            "threshold_profile": "default",
            "retrieval": {
                "top_k_files": 8,
                "min_candidate_score": 2,
            },
            "chunk": {
                "top_k": 10,
            },
            "scip": {
                "enabled": True,
                "base_weight": 0.5,
            },
        },
    }

    report = build_benchmark_tuning_report(summary=summary)
    recommendation_ids = [item["id"] for item in report.recommendations]

    assert "recall_recovery" in recommendation_ids
    assert "precision_noise_balance" in recommendation_ids
    assert "graph_signal_promotion" in recommendation_ids
    assert any("embedding_fallback_ratio" in note for note in report.operational_notes)


def test_write_tuning_report_writes_json_and_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "summary.json"
    output_dir = tmp_path / "artifacts" / "benchmark" / "tune-report"
    input_path.write_text(
        json.dumps(
            {
                "repo": "demo",
                "case_count": 1,
                "metrics": {
                    "recall_at_k": 0.95,
                    "dependency_recall": 0.91,
                    "chunk_hit_at_k": 0.92,
                    "precision_at_k": 0.72,
                    "noise_rate": 0.28,
                    "latency_p95_ms": 1500.0,
                },
                "tuning_context_summary": {
                    "retrieval": {"top_k_files": 6},
                    "chunk": {"top_k": 8},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outputs = write_tuning_report(input_path=input_path, output_dir=output_dir)

    json_path = Path(outputs["tuning_report_json"])
    md_path = Path(outputs["tuning_report_md"])
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report_only"] is True
    assert payload["recommendation_count"] >= 1
    assert "latency_recovery" in [item["id"] for item in payload["recommendations"]]
