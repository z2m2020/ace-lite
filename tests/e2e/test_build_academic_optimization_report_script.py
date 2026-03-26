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


def test_build_academic_optimization_summary_groups_surface_and_bucket() -> None:
    module = _load_script("build_academic_optimization_report.py")

    results_payload = {
        "generated_at": "2026-03-26T00:00:00+00:00",
        "repo": "ace-lite",
        "root": "/repo",
        "cases": [
            {
                "case_id": "academic-query-expansion-compounds-01",
                "comparison_lane": "academic_optimization",
                "precision_at_k": 0.8,
                "noise_rate": 0.2,
                "latency_ms": 120.0,
                "hit_at_1": 1.0,
                "reciprocal_rank": 1.0,
                "chunk_hit_at_k": 1.0,
                "dependency_recall": 0.7,
                "task_success_hit": 1.0,
                "embedding_enabled": 1.0,
                "embedding_semantic_rerank_applied": 1.0,
                "embedding_rerank_ratio": 0.5,
                "embedding_similarity_mean": 0.6,
                "embedding_fallback": 0.0,
                "embedding_time_budget_exceeded": 0.0,
                "chunk_semantic_rerank_enabled": 1.0,
                "chunk_semantic_rerank_ratio": 0.5,
                "chunk_semantic_similarity_mean": 0.55,
                "chunk_semantic_fallback": 0.0,
                "chunk_semantic_time_budget_exceeded": 0.0,
                "embedding_runtime_provider": "hash_cross",
                "embedding_strategy_mode": "cross_encoder",
            },
            {
                "case_id": "academic-workspace-summary-routing-09",
                "comparison_lane": "academic_optimization",
                "precision_at_k": 0.6,
                "noise_rate": 0.4,
                "latency_ms": 200.0,
                "hit_at_1": 0.0,
                "reciprocal_rank": 0.5,
                "chunk_hit_at_k": 0.5,
                "dependency_recall": 0.4,
                "task_success_hit": 0.0,
                "embedding_enabled": 1.0,
                "embedding_semantic_rerank_applied": 0.0,
                "embedding_rerank_ratio": 0.0,
                "embedding_similarity_mean": 0.0,
                "embedding_fallback": 1.0,
                "embedding_time_budget_exceeded": 1.0,
                "chunk_semantic_rerank_enabled": 1.0,
                "chunk_semantic_rerank_ratio": 0.0,
                "chunk_semantic_similarity_mean": 0.0,
                "chunk_semantic_fallback": 1.0,
                "chunk_semantic_time_budget_exceeded": 1.0,
                "embedding_runtime_provider": "hash_cross",
                "embedding_strategy_mode": "cross_encoder",
            },
            {
                "case_id": "unknown-case",
                "comparison_lane": "academic_optimization",
                "precision_at_k": 0.2,
                "noise_rate": 0.8,
                "latency_ms": 300.0,
                "hit_at_1": 0.0,
                "reciprocal_rank": 0.0,
                "chunk_hit_at_k": 0.0,
                "dependency_recall": 0.0,
                "task_success_hit": 0.0,
                "embedding_enabled": 0.0,
                "embedding_semantic_rerank_applied": 0.0,
                "embedding_rerank_ratio": 0.0,
                "embedding_similarity_mean": 0.0,
                "embedding_fallback": 0.0,
                "embedding_time_budget_exceeded": 0.0,
                "chunk_semantic_rerank_enabled": 0.0,
                "chunk_semantic_rerank_ratio": 0.0,
                "chunk_semantic_similarity_mean": 0.0,
                "chunk_semantic_fallback": 0.0,
                "chunk_semantic_time_budget_exceeded": 0.0,
                "embedding_runtime_provider": "",
                "embedding_strategy_mode": "",
            },
        ],
    }
    cases_payload = [
        {
            "case_id": "academic-query-expansion-compounds-01",
            "comparison_lane": "academic_optimization",
            "optimization_surface": "query_expansion",
            "query_bucket": "doc_explain",
        },
        {
            "case_id": "academic-workspace-summary-routing-09",
            "comparison_lane": "academic_optimization",
            "optimization_surface": "workspace_summary",
            "query_bucket": "doc_explain",
        },
    ]

    summary = module.build_academic_optimization_summary(
        results_payload=results_payload,
        cases_payload=cases_payload,
        runtime_flags={"query_expansion_enabled": True},
    )

    assert summary["case_count"] == 3
    assert summary["runtime_flags"] == {"query_expansion_enabled": True}
    assert summary["comparison_lanes"] == ["academic_optimization"]
    assert summary["metadata_coverage"]["missing_case_ids"] == ["unknown-case"]
    by_surface = {item["group"]: item for item in summary["by_surface"]}
    assert by_surface["query_expansion"]["metrics"]["precision_at_k_mean"] == 0.8
    assert by_surface["workspace_summary"]["metrics"]["task_success_hit_mean"] == 0.0
    assert by_surface["(unknown)"]["case_count"] == 1

    by_bucket = {item["group"]: item for item in summary["by_query_bucket"]}
    assert by_bucket["doc_explain"]["case_count"] == 2
    assert by_bucket["doc_explain"]["metrics"]["latency_ms_mean"] == 160.0

    matrix = {
        (item["optimization_surface"], item["query_bucket"]): item
        for item in summary["surface_bucket_matrix"]
    }
    assert ("query_expansion", "doc_explain") in matrix
    assert matrix[("workspace_summary", "doc_explain")]["metrics"]["noise_rate_mean"] == 0.4

    semantic_by_bucket = {
        item["query_bucket"]: item for item in summary["semantic_rerank_by_query_bucket"]
    }
    assert semantic_by_bucket["doc_explain"]["dominant_provider"] == "hash_cross"
    assert semantic_by_bucket["doc_explain"]["dominant_mode"] == "cross_encoder"
    assert semantic_by_bucket["doc_explain"]["metrics"]["embedding_enabled_mean"] == 1.0
    assert semantic_by_bucket["doc_explain"]["metrics"]["embedding_fallback_mean"] == 0.5
    assert semantic_by_bucket["doc_explain"]["metrics"]["chunk_semantic_fallback_mean"] == 0.5


def test_build_academic_optimization_report_main_writes_outputs(tmp_path: Path) -> None:
    module = _load_script("build_academic_optimization_report.py")

    results_path = tmp_path / "results.json"
    cases_path = tmp_path / "cases.yaml"
    output_dir = tmp_path / "academic"
    results_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-26T00:00:00+00:00",
                "repo": "ace-lite",
                "root": "/repo",
                "cases": [
                    {
                        "case_id": "academic-query-expansion-compounds-01",
                        "comparison_lane": "academic_optimization",
                        "precision_at_k": 0.8,
                        "noise_rate": 0.2,
                        "latency_ms": 120.0,
                        "hit_at_1": 1.0,
                        "reciprocal_rank": 1.0,
                        "chunk_hit_at_k": 1.0,
                        "dependency_recall": 0.7,
                        "task_success_hit": 1.0,
                        "embedding_enabled": 1.0,
                        "embedding_semantic_rerank_applied": 1.0,
                        "embedding_rerank_ratio": 0.5,
                        "embedding_similarity_mean": 0.6,
                        "embedding_fallback": 0.0,
                        "embedding_time_budget_exceeded": 0.0,
                        "chunk_semantic_rerank_enabled": 1.0,
                        "chunk_semantic_rerank_ratio": 0.5,
                        "chunk_semantic_similarity_mean": 0.55,
                        "chunk_semantic_fallback": 0.0,
                        "chunk_semantic_time_budget_exceeded": 0.0,
                        "embedding_runtime_provider": "hash_cross",
                        "embedding_strategy_mode": "cross_encoder",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        "\n".join(
            [
                "cases:",
                "  - case_id: academic-query-expansion-compounds-01",
                "    comparison_lane: academic_optimization",
                "    optimization_surface: query_expansion",
                "    query_bucket: doc_explain",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--results",
            str(results_path),
            "--cases",
            str(cases_path),
            "--output-dir",
            str(output_dir),
            "--query-expansion-enabled",
            "true",
        ]
    )

    assert exit_code == 0
    summary_path = output_dir / "academic_summary.json"
    report_path = output_dir / "academic_report.md"
    assert summary_path.exists()
    assert report_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["case_count"] == 1
    assert summary["runtime_flags"] == {"query_expansion_enabled": True}
    assert summary["by_surface"][0]["group"] == "query_expansion"

    report = report_path.read_text(encoding="utf-8")
    assert "# Academic Optimization Benchmark Summary" in report
    assert "Runtime flags: query_expansion_enabled=True" in report
    assert "## By Surface" in report
    assert "## Semantic Rerank By Query Bucket" in report
    assert "query_expansion" in report


def test_build_academic_optimization_report_main_writes_comparison_outputs(
    tmp_path: Path,
) -> None:
    module = _load_script("build_academic_optimization_report.py")

    results_path = tmp_path / "results.json"
    cases_path = tmp_path / "cases.yaml"
    baseline_summary_path = tmp_path / "baseline_academic_summary.json"
    output_dir = tmp_path / "academic"
    results_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-26T00:00:00+00:00",
                "repo": "ace-lite",
                "root": "/repo",
                "cases": [
                    {
                        "case_id": "academic-query-expansion-compounds-01",
                        "comparison_lane": "academic_optimization",
                        "precision_at_k": 0.6,
                        "noise_rate": 0.4,
                        "latency_ms": 140.0,
                        "hit_at_1": 0.0,
                        "reciprocal_rank": 0.5,
                        "chunk_hit_at_k": 1.0,
                        "dependency_recall": 1.0,
                        "task_success_hit": 1.0,
                        "embedding_enabled": 1.0,
                        "embedding_semantic_rerank_applied": 1.0,
                        "embedding_rerank_ratio": 0.5,
                        "embedding_similarity_mean": 0.6,
                        "embedding_fallback": 0.0,
                        "embedding_time_budget_exceeded": 0.0,
                        "chunk_semantic_rerank_enabled": 0.0,
                        "chunk_semantic_rerank_ratio": 0.0,
                        "chunk_semantic_similarity_mean": 0.0,
                        "chunk_semantic_fallback": 0.0,
                        "chunk_semantic_time_budget_exceeded": 0.0,
                        "embedding_runtime_provider": "hash_cross",
                        "embedding_strategy_mode": "cross_encoder",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        "\n".join(
            [
                "cases:",
                "  - case_id: academic-query-expansion-compounds-01",
                "    comparison_lane: academic_optimization",
                "    optimization_surface: query_expansion",
                "    query_bucket: doc_explain",
            ]
        ),
        encoding="utf-8",
    )
    baseline_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-26T00:00:00+00:00",
                "repo": "ace-lite",
                "case_count": 1,
                "overall": {
                    "metrics": {
                        "precision_at_k_mean": 0.8,
                        "noise_rate_mean": 0.2,
                        "latency_ms_mean": 120.0,
                        "hit_at_1_mean": 1.0,
                        "reciprocal_rank_mean": 1.0,
                        "task_success_hit_mean": 1.0,
                    }
                },
                "by_surface": [
                    {
                        "group": "query_expansion",
                        "case_count": 1,
                        "metrics": {
                            "precision_at_k_mean": 0.8,
                            "noise_rate_mean": 0.2,
                            "latency_ms_mean": 120.0,
                            "hit_at_1_mean": 1.0,
                            "reciprocal_rank_mean": 1.0,
                            "task_success_hit_mean": 1.0,
                        },
                    }
                ],
                "by_query_bucket": [
                    {
                        "group": "doc_explain",
                        "case_count": 1,
                        "metrics": {
                            "precision_at_k_mean": 0.8,
                            "noise_rate_mean": 0.2,
                            "latency_ms_mean": 120.0,
                            "hit_at_1_mean": 1.0,
                            "reciprocal_rank_mean": 1.0,
                            "task_success_hit_mean": 1.0,
                        },
                    }
                ],
                "semantic_rerank_by_query_bucket": [
                    {
                        "query_bucket": "doc_explain",
                        "dominant_provider": "hash",
                        "dominant_mode": "embedding",
                        "metrics": {
                            "embedding_enabled_mean": 0.0,
                            "embedding_semantic_rerank_applied_mean": 0.0,
                            "embedding_fallback_mean": 0.0,
                            "embedding_time_budget_exceeded_mean": 0.0,
                            "chunk_semantic_rerank_enabled_mean": 0.0,
                            "chunk_semantic_fallback_mean": 0.0,
                            "chunk_semantic_time_budget_exceeded_mean": 0.0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--results",
            str(results_path),
            "--cases",
            str(cases_path),
            "--output-dir",
            str(output_dir),
            "--baseline-summary",
            str(baseline_summary_path),
            "--query-expansion-enabled",
            "false",
        ]
    )

    assert exit_code == 0
    comparison_path = output_dir / "academic_comparison.json"
    comparison_report_path = output_dir / "academic_comparison.md"
    assert comparison_path.exists()
    assert comparison_report_path.exists()

    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["baseline_runtime_flags"] == {}
    assert comparison["current_runtime_flags"] == {"query_expansion_enabled": False}
    assert comparison["overall_metrics"]["precision_at_k_mean"]["delta"] == pytest.approx(-0.2)
    assert comparison["overall_metrics"]["latency_ms_mean"]["delta"] == pytest.approx(20.0)
    surface = comparison["by_surface"][0]
    assert surface["optimization_surface"] == "query_expansion"
    assert surface["metrics"]["precision_at_k_mean"]["delta"] == pytest.approx(-0.2)
    bucket = comparison["by_query_bucket"][0]
    assert bucket["query_bucket"] == "doc_explain"
    assert bucket["metrics"]["hit_at_1_mean"]["delta"] == pytest.approx(-1.0)

    report = comparison_report_path.read_text(encoding="utf-8")
    assert "# Academic Optimization Benchmark Comparison" in report
    assert "Current runtime flags: query_expansion_enabled=False" in report
    assert "## Overall Delta" in report
    assert "## Surface Delta" in report
    assert "| query_expansion | -0.2000 | +0.2000 | +20.0000 | -1.0000 | -0.5000 | +0.0000 |" in report
    assert "hash_cross" in report
