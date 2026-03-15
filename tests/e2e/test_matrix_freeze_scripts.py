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


def test_benchmark_matrix_summary_helpers(tmp_path: Path) -> None:
    module = _load_script("run_benchmark_matrix.py")

    missing = module._load_summary_payload(summary_path=tmp_path / "missing.json")
    assert missing == {}

    summary_path = tmp_path / "summary.json"
    payload = {
        "regressed": True,
        "failed_checks": ["precision_at_k", " ", "noise_rate"],
    }
    summary_path.write_text(json.dumps(payload), encoding="utf-8")

    parsed = module._load_summary_payload(summary_path=summary_path)
    assert parsed == payload

    failed = module._extract_failed_check_names(parsed)
    assert failed == ["precision_at_k", "noise_rate"]


def test_benchmark_matrix_policy_summary_helpers() -> None:
    module = _load_script("run_benchmark_matrix.py")

    policy = module._extract_retrieval_policy(
        summary={},
        repo_spec={"retrieval_policy": "Feature"},
        defaults={"retrieval_policy": "auto"},
    )
    assert policy == "feature"

    retrieval_rows = module._build_retrieval_policy_summary(
        repos=[
            {
                "retrieval_policy": "auto",
                "benchmark_regressed": False,
                "benchmark_failed_checks": [],
                "metrics": {
                    "precision_at_k": 0.6,
                    "noise_rate": 0.3,
                    "latency_p95_ms": 20.0,
                    "repomap_latency_p95_ms": 4.0,
                },
                "task_success_summary": {
                    "task_success_rate": 0.8,
                    "positive_task_success_rate": 1.0,
                    "retrieval_task_gap_rate": 0.25,
                },
                "slo_budget_summary": {
                    "downgrade_case_rate": 0.5,
                },
            },
            {
                "retrieval_policy": "auto",
                "benchmark_regressed": True,
                "benchmark_failed_checks": [],
                "metrics": {
                    "precision_at_k": 0.7,
                    "noise_rate": 0.2,
                    "latency_p95_ms": 30.0,
                    "repomap_latency_p95_ms": 6.0,
                },
                "task_success_summary": {
                    "task_success_rate": 0.6,
                    "positive_task_success_rate": 0.7,
                    "retrieval_task_gap_rate": 0.5,
                },
                "slo_budget_summary": {
                    "downgrade_case_rate": 0.0,
                },
            },
            {
                "retrieval_policy": "bugfix_test",
                "benchmark_regressed": False,
                "benchmark_failed_checks": ["precision_at_k"],
                "metrics": {
                    "precision_at_k": 0.8,
                    "noise_rate": 0.1,
                    "latency_p95_ms": 15.0,
                    "repomap_latency_p95_ms": 3.0,
                },
                "task_success_summary": {
                    "task_success_rate": 0.9,
                    "positive_task_success_rate": 1.0,
                    "retrieval_task_gap_rate": 0.1,
                },
                "slo_budget_summary": {
                    "downgrade_case_rate": 0.25,
                },
            },
        ]
    )

    assert [row["retrieval_policy"] for row in retrieval_rows] == ["auto", "bugfix_test"]
    assert retrieval_rows[0]["repo_count"] == 2
    assert retrieval_rows[0]["regressed_repo_count"] == 1
    assert retrieval_rows[0]["regressed_repo_rate"] == pytest.approx(0.5)
    assert retrieval_rows[0]["task_success_mean"] == pytest.approx(0.7)
    assert retrieval_rows[0]["positive_task_success_mean"] == pytest.approx(0.85)
    assert retrieval_rows[0]["retrieval_task_gap_rate_mean"] == pytest.approx(0.375)
    assert retrieval_rows[0]["precision_at_k_mean"] == pytest.approx(0.65)
    assert retrieval_rows[0]["noise_rate_mean"] == pytest.approx(0.25)
    assert retrieval_rows[0]["latency_p95_ms_mean"] == pytest.approx(25.0)
    assert retrieval_rows[0]["repomap_latency_p95_ms_mean"] == pytest.approx(5.0)
    assert retrieval_rows[0]["slo_downgrade_case_rate_mean"] == pytest.approx(0.25)
    assert retrieval_rows[1] == {
        "retrieval_policy": "bugfix_test",
        "repo_count": 1,
        "regressed_repo_count": 1,
        "regressed_repo_rate": 1.0,
        "task_success_mean": 0.9,
        "positive_task_success_mean": 1.0,
        "retrieval_task_gap_rate_mean": 0.1,
        "precision_at_k_mean": 0.8,
        "noise_rate_mean": 0.1,
        "latency_p95_ms_mean": 15.0,
        "repomap_latency_p95_ms_mean": 3.0,
        "slo_downgrade_case_rate_mean": 0.25,
    }

    plugin_summary = module._build_plugin_policy_summary(
        repos=[
            {
                "name": "repo-a",
                "plugin_policy_summary": {
                    "mode": "strict",
                    "totals": {
                        "applied": 3,
                        "conflicts": 1,
                        "blocked": 0,
                        "warn": 2,
                        "remote_applied": 1,
                    },
                },
            },
            {
                "name": "repo-b",
                "plugin_policy_summary": {
                    "mode": "permissive",
                    "totals": {
                        "applied": 2,
                        "conflicts": 0,
                        "blocked": 1,
                        "warn": 0,
                        "remote_applied": 0,
                    },
                },
            },
        ]
    )

    assert plugin_summary["totals"] == {
        "applied": 5,
        "conflicts": 1,
        "blocked": 1,
        "warn": 2,
        "remote_applied": 1,
    }
    assert plugin_summary["mode_distribution"] == {"permissive": 1, "strict": 1}
    assert [item["name"] for item in plugin_summary["repos"]] == ["repo-a", "repo-b"]


def test_benchmark_matrix_latency_slo_summary_helpers() -> None:
    module = _load_script("run_benchmark_matrix.py")

    assert module._classify_repo_size_bucket(file_count=36) == "repo_size_small"
    assert module._classify_repo_size_bucket(file_count=394) == "repo_size_medium"
    assert module._classify_repo_size_bucket(file_count=2554) == "repo_size_large"
    assert (
        module._resolve_workload_bucket(
            repo_spec={"workload_bucket": "Perf"},
            file_count=0,
            retrieval_policy="feature",
        )
        == "perf"
    )

    payload = module._build_latency_slo_summary(
        summary={
            "generated_at": "2026-03-06T00:00:00Z",
            "matrix_config": "benchmark/matrix/external_oss.yaml",
            "repo_count": 3,
            "stage_latency_summary": {
                "memory": {"mean_ms": 0.5, "p95_ms": 0.8},
                "index": {"mean_ms": 10.0, "p95_ms": 12.0},
                "repomap": {"mean_ms": 2.5, "p95_ms": 3.0},
                "augment": {"mean_ms": 0.2, "p95_ms": 0.3},
                "skills": {"mean_ms": 1.2, "p95_ms": 1.5},
                "source_plan": {"mean_ms": 0.4, "p95_ms": 0.6},
                "total": {"mean_ms": 14.8, "median_ms": 14.0, "p95_ms": 18.0},
            },
            "slo_budget_summary": {
                "case_count": 3,
                "budget_limits_ms": {
                    "parallel_time_budget_ms_mean": 10.0,
                    "embedding_time_budget_ms_mean": 20.0,
                    "chunk_semantic_time_budget_ms_mean": 30.0,
                    "xref_time_budget_ms_mean": 40.0,
                },
                "downgrade_case_count": 2,
                "downgrade_case_rate": 2.0 / 3.0,
                "signals": {
                    "parallel_docs_timeout_ratio": {"count": 0, "rate": 0.0},
                    "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                    "embedding_time_budget_exceeded_ratio": {"count": 1, "rate": 1.0 / 3.0},
                    "embedding_adaptive_budget_ratio": {"count": 1, "rate": 1.0 / 3.0},
                    "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                    "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                    "chunk_semantic_fallback_ratio": {"count": 1, "rate": 1.0 / 3.0},
                    "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
                },
            },
            "repos": [
                {
                    "name": "requests",
                    "retrieval_policy": "auto",
                    "workload_bucket": "repo_size_small",
                    "index_file_count": 36,
                    "stage_latency_summary": {
                        "memory": {"mean_ms": 0.1, "p95_ms": 0.1},
                        "index": {"mean_ms": 8.0, "p95_ms": 8.5},
                        "repomap": {"mean_ms": 1.0, "p95_ms": 1.1},
                        "augment": {"mean_ms": 0.1, "p95_ms": 0.1},
                        "skills": {"mean_ms": 2.0, "p95_ms": 2.2},
                        "source_plan": {"mean_ms": 0.2, "p95_ms": 0.3},
                        "total": {"mean_ms": 11.4, "median_ms": 11.0, "p95_ms": 12.2},
                    },
                    "slo_budget_summary": {
                        "case_count": 1,
                        "budget_limits_ms": {
                            "parallel_time_budget_ms_mean": 0.0,
                            "embedding_time_budget_ms_mean": 76.0,
                            "chunk_semantic_time_budget_ms_mean": 0.0,
                            "xref_time_budget_ms_mean": 1500.0,
                        },
                        "downgrade_case_count": 1,
                        "downgrade_case_rate": 1.0,
                        "signals": {
                            "parallel_docs_timeout_ratio": {"count": 0, "rate": 0.0},
                            "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                            "embedding_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                            "embedding_adaptive_budget_ratio": {"count": 1, "rate": 1.0},
                            "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                            "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                            "chunk_semantic_fallback_ratio": {"count": 0, "rate": 0.0},
                            "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
                        },
                    },
                },
                {
                    "name": "protobuf-go",
                    "retrieval_policy": "auto",
                    "workload_bucket": "repo_size_medium",
                    "index_file_count": 394,
                    "stage_latency_summary": {
                        "memory": {"mean_ms": 0.4, "p95_ms": 0.5},
                        "index": {"mean_ms": 20.0, "p95_ms": 22.0},
                        "repomap": {"mean_ms": 2.5, "p95_ms": 3.0},
                        "augment": {"mean_ms": 0.2, "p95_ms": 0.3},
                        "skills": {"mean_ms": 2.4, "p95_ms": 3.1},
                        "source_plan": {"mean_ms": 0.5, "p95_ms": 0.6},
                        "total": {"mean_ms": 26.0, "median_ms": 25.5, "p95_ms": 29.5},
                    },
                    "slo_budget_summary": {
                        "case_count": 1,
                        "budget_limits_ms": {
                            "parallel_time_budget_ms_mean": 0.0,
                            "embedding_time_budget_ms_mean": 76.0,
                            "chunk_semantic_time_budget_ms_mean": 0.0,
                            "xref_time_budget_ms_mean": 1500.0,
                        },
                        "downgrade_case_count": 0,
                        "downgrade_case_rate": 0.0,
                        "signals": {
                            "parallel_docs_timeout_ratio": {"count": 0, "rate": 0.0},
                            "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                            "embedding_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                            "embedding_adaptive_budget_ratio": {"count": 0, "rate": 0.0},
                            "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                            "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                            "chunk_semantic_fallback_ratio": {"count": 0, "rate": 0.0},
                            "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
                        },
                    },
                },
                {
                    "name": "blockscout-frontend",
                    "retrieval_policy": "feature",
                    "workload_bucket": "repo_size_large",
                    "index_file_count": 2554,
                    "stage_latency_summary": {
                        "memory": {"mean_ms": 1.0, "p95_ms": 1.2},
                        "index": {"mean_ms": 45.0, "p95_ms": 48.0},
                        "repomap": {"mean_ms": 8.0, "p95_ms": 9.5},
                        "augment": {"mean_ms": 0.5, "p95_ms": 0.6},
                        "skills": {"mean_ms": 4.0, "p95_ms": 4.8},
                        "source_plan": {"mean_ms": 0.8, "p95_ms": 0.9},
                        "total": {"mean_ms": 59.3, "median_ms": 58.0, "p95_ms": 65.0},
                    },
                    "slo_budget_summary": {
                        "case_count": 1,
                        "budget_limits_ms": {
                            "parallel_time_budget_ms_mean": 30.0,
                            "embedding_time_budget_ms_mean": 76.0,
                            "chunk_semantic_time_budget_ms_mean": 0.0,
                            "xref_time_budget_ms_mean": 1500.0,
                        },
                        "downgrade_case_count": 1,
                        "downgrade_case_rate": 1.0,
                        "signals": {
                            "parallel_docs_timeout_ratio": {"count": 1, "rate": 1.0},
                            "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                            "embedding_time_budget_exceeded_ratio": {"count": 1, "rate": 1.0},
                            "embedding_adaptive_budget_ratio": {"count": 0, "rate": 0.0},
                            "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                            "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                            "chunk_semantic_fallback_ratio": {"count": 1, "rate": 1.0},
                            "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
                        },
                    },
                },
            ],
        }
    )

    assert payload["bucket_strategy"]["repo_size_thresholds"] == {
        "repo_size_small_max_file_count": 128,
        "repo_size_medium_max_file_count": 1024,
        "repo_size_large_min_file_count": 1025,
    }
    assert [row["workload_bucket"] for row in payload["workload_buckets"]] == [
        "repo_size_small",
        "repo_size_medium",
        "repo_size_large",
    ]
    assert payload["workload_buckets"][0]["file_count_mean"] == pytest.approx(36.0)
    assert payload["workload_buckets"][1]["stage_latency_summary"]["index"]["p95_ms"] == pytest.approx(
        22.0
    )
    assert payload["workload_buckets"][2]["slo_budget_summary"]["downgrade_case_rate"] == pytest.approx(
        1.0
    )

    markdown = module._build_latency_slo_summary_markdown(payload=payload)
    assert "## Hard Budget Features" in markdown
    assert "parallel_time_budget_ms_mean" in markdown
    assert "## Dynamic Downgrade Features" in markdown
    assert "slo_downgrade_case_rate" in markdown
    assert "## Workload Buckets" in markdown
    assert "| repo_size_large | 1 | 2554.0 | 65.00 | 48.00 | 9.50 | 1.0000 | feature |" in markdown
    assert "### repo_size_medium" in markdown


def test_benchmark_matrix_thresholds_support_repomap_latency() -> None:
    module = _load_script("run_benchmark_matrix.py")
    failures = module._evaluate_thresholds(
        metrics={
            "latency_p95_ms": 160.0,
            "repomap_latency_p95_ms": 125.0,
        },
        thresholds={
            "latency_p95_ms_max": 170.0,
            "repomap_latency_p95_ms_max": 110.0,
        },
    )

    assert failures == [
        {
            "metric": "repomap_latency_p95_ms",
            "operator": "<=",
            "expected": 110.0,
            "actual": 125.0,
        }
    ]


def test_benchmark_matrix_markdown_includes_regression_signals() -> None:
    module = _load_script("run_benchmark_matrix.py")
    summary = {
        "generated_at": "2026-02-12T00:00:00Z",
        "matrix_config": "benchmark/matrix/repos.yaml",
        "passed": True,
        "repo_count": 1,
        "retrieval_policy_summary": [
            {
                "retrieval_policy": "feature",
                "repo_count": 1,
                "regressed_repo_count": 1,
                "regressed_repo_rate": 1.0,
                "task_success_mean": 0.75,
                "positive_task_success_mean": 1.0,
                "retrieval_task_gap_rate_mean": 0.5,
                "precision_at_k_mean": 0.5,
                "noise_rate_mean": 0.5,
                "latency_p95_ms_mean": 11.0,
                "repomap_latency_p95_ms_mean": 12.5,
                "slo_downgrade_case_rate_mean": 0.5,
            }
        ],
        "plugin_policy_summary": {
            "totals": {
                "applied": 2,
                "conflicts": 1,
                "blocked": 0,
                "warn": 0,
                "remote_applied": 0,
            },
            "mode_distribution": {"strict": 1},
            "repos": [
                {
                    "name": "demo",
                    "mode": "strict",
                    "applied": 2,
                    "conflicts": 1,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            ],
        },
        "stage_latency_summary": {
            "memory": {"mean_ms": 2.0, "p95_ms": 2.0},
            "index": {"mean_ms": 4.0, "p95_ms": 4.5},
            "repomap": {"mean_ms": 3.0, "p95_ms": 3.0},
            "augment": {"mean_ms": 1.0, "p95_ms": 1.0},
            "skills": {"mean_ms": 0.5, "p95_ms": 0.5},
            "source_plan": {"mean_ms": 2.5, "p95_ms": 2.5},
            "total": {"mean_ms": 11.0, "median_ms": 11.0, "p95_ms": 11.0},
        },
        "slo_budget_summary": {
            "case_count": 2,
            "budget_limits_ms": {
                "parallel_time_budget_ms_mean": 30.0,
                "embedding_time_budget_ms_mean": 60.0,
                "chunk_semantic_time_budget_ms_mean": 20.0,
                "xref_time_budget_ms_mean": 15.0,
            },
            "downgrade_case_count": 1,
            "downgrade_case_rate": 0.5,
            "signals": {
                "parallel_docs_timeout_ratio": {"count": 1, "rate": 0.5},
                "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                "embedding_time_budget_exceeded_ratio": {"count": 1, "rate": 0.5},
                "embedding_adaptive_budget_ratio": {"count": 0, "rate": 0.0},
                "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                "chunk_semantic_fallback_ratio": {"count": 1, "rate": 0.5},
                "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
            },
        },
        "repos": [
            {
                "name": "demo",
                "passed": True,
                "retrieval_policy": "feature",
                "metrics": {
                    "recall_at_k": 1.0,
                    "task_success_rate": 0.75,
                    "precision_at_k": 0.5,
                    "noise_rate": 0.5,
                    "dependency_recall": 0.8,
                    "repomap_latency_p95_ms": 12.5,
                    "latency_p95_ms": 11.0,
                    "chunk_hit_at_k": 0.5,
                },
                "task_success_summary": {
                    "case_count": 2,
                    "positive_case_count": 1,
                    "negative_control_case_count": 1,
                    "task_success_rate": 0.75,
                    "positive_task_success_rate": 1.0,
                    "negative_control_task_success_rate": 0.5,
                    "retrieval_task_gap_count": 1,
                    "retrieval_task_gap_rate": 0.5,
                },
                "failed_checks": [],
                "benchmark_regressed": True,
                "benchmark_failed_checks": ["precision_at_k"],
            }
        ],
    }

    report = module._build_summary_markdown(summary=summary)

    assert "| Repo | Retrieval Policy | Passed | Regressed | Failed Checks |" in report
    assert "Task Success" in report
    assert "Gap Rate" in report
    assert "Repomap p95 (ms)" in report
    assert "Notes Hit" in report
    assert "Profile Selected" in report
    assert "Capture Trigger" in report
    assert "## Benchmark Regression Signals" in report
    assert "### demo" in report
    assert "failed_checks: precision_at_k" in report
    assert "## Retrieval Policy Summary" in report
    assert "| Retrieval Policy | Repo Count | Regressed Repo Count | Regressed Rate | Task Success | Positive Task | Gap Rate | Precision | Noise | Latency p95 (ms) | Repomap p95 (ms) | SLO Downgrade |" in report
    assert "| feature | 1 | 1 | 1.0000 | 0.7500 | 1.0000 | 0.5000 | 0.5000 | 0.5000 | 11.00 | 12.50 | 0.5000 |" in report
    assert "## Plugin Policy Summary" in report
    assert "mode_distribution: strict=1" in report
    assert "## Stage Latency Summary" in report
    assert "## SLO Budget Summary" in report
    assert "downgrade_case_rate=0.5000" in report
    assert "| demo | strict | 2 | 1 | 0 | 0 | 0 |" in report


def test_benchmark_matrix_run_repo_benchmark_passes_embedding_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_benchmark_matrix.py")
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    cases_path = project_root / "cases.yaml"
    cases_path.write_text(
        "cases:\n  - case_id: c1\n    query: where x\n    expected_keys: [x]\n    top_k: 4\n",
        encoding="utf-8",
    )
    repo_root = tmp_path / "repo-root"
    repo_root.mkdir(parents=True, exist_ok=True)
    output_root = tmp_path / "out"
    output_root.mkdir(parents=True, exist_ok=True)

    captured_cmds: list[list[str]] = []

    monkeypatch.setattr(
        module,
        "_ensure_checkout",
        lambda workspace, spec: {
            "name": "repo-a",
            "root": str(repo_root),
            "ref": "main",
            "resolved_commit": "abc123",
        },
    )

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = cwd
        captured_cmds.append(list(cmd))
        if len(cmd) >= 3 and cmd[1:3] == ["benchmark", "run"]:
            out_idx = cmd.index("--output")
            repo_output = Path(cmd[out_idx + 1])
            repo_output.mkdir(parents=True, exist_ok=True)
            (repo_output / "index.json").write_text(
                json.dumps({"file_count": 42}),
                encoding="utf-8",
            )
            (repo_output / "results.json").write_text(
                json.dumps(
                    {
                        "metrics": {
                            "task_success_rate": 0.6,
                            "precision_at_k": 0.7,
                            "noise_rate": 0.3,
                        },
                        "task_success_summary": {
                            "case_count": 2,
                            "positive_case_count": 1,
                            "negative_control_case_count": 1,
                            "task_success_rate": 0.6,
                            "positive_task_success_rate": 1.0,
                            "negative_control_task_success_rate": 0.2,
                            "retrieval_task_gap_count": 1,
                            "retrieval_task_gap_rate": 0.5,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (repo_output / "summary.json").write_text(
                json.dumps(
                    {
                        "regressed": False,
                        "failed_checks": [],
                        "task_success_summary": {
                            "case_count": 2,
                            "positive_case_count": 1,
                            "negative_control_case_count": 1,
                            "task_success_rate": 0.6,
                            "positive_task_success_rate": 1.0,
                            "negative_control_task_success_rate": 0.2,
                            "retrieval_task_gap_count": 1,
                            "retrieval_task_gap_rate": 0.5,
                        },
                    }
                ),
                encoding="utf-8",
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    repo_result = module._run_repo_benchmark(
        project_root=project_root,
        cli_bin="ace-lite",
        repo_spec={
            "name": "repo-a",
            "repo": "repo-a",
            "url": "https://example.invalid/repo-a.git",
            "ref": "main",
            "cases": "cases.yaml",
        },
        defaults={
            "skills_dir": "skills",
            "top_k_files": 6,
            "min_candidate_score": 2,
            "candidate_relative_threshold": 0.2,
            "candidate_ranker": "heuristic",
            "chunk_top_k": 12,
            "cochange": False,
            "repomap": True,
            "index_incremental": False,
            "memory_primary": "none",
            "memory_secondary": "none",
            "warmup_runs": 0,
            "app": "codex",
            "embedding_enabled": True,
            "embedding_provider": "hash_cross",
            "embedding_model": "hash-cross-v1",
            "embedding_dimension": 1,
            "embedding_rerank_pool": 12,
            "embedding_fail_open": True,
        },
        global_thresholds={},
        repos_workspace=tmp_path / "workspace",
        output_root=output_root,
    )

    benchmark_cmd = next(cmd for cmd in captured_cmds if len(cmd) >= 3 and cmd[1:3] == ["benchmark", "run"])
    assert "--embedding-enabled" in benchmark_cmd
    assert "--embedding-provider" in benchmark_cmd
    assert "hash_cross" in benchmark_cmd
    assert "--embedding-rerank-pool" in benchmark_cmd
    assert "--embedding-fail-open" in benchmark_cmd
    assert repo_result["passed"] is True
    assert repo_result["index_file_count"] == 42
    assert repo_result["workload_bucket"] == "repo_size_small"
    assert repo_result["task_success_summary"] == {
        "case_count": 2,
        "positive_case_count": 1,
        "negative_control_case_count": 1,
        "task_success_rate": 0.6,
        "positive_task_success_rate": 1.0,
        "negative_control_task_success_rate": 0.2,
        "retrieval_task_gap_count": 1,
        "retrieval_task_gap_rate": 0.5,
    }


def test_benchmark_matrix_checkout_retries_transient_fetch_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_benchmark_matrix.py")
    workspace = tmp_path / "workspace"
    target = workspace / "repo-a"
    (target / ".git").mkdir(parents=True, exist_ok=True)

    calls: list[list[str]] = []
    fetch_attempts = {"count": 0}

    def fake_sleep(_: float) -> None:
        return None

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = cwd
        calls.append(list(cmd))

        if "fetch" in cmd:
            fetch_attempts["count"] += 1
            if fetch_attempts["count"] == 1:
                return module.CommandResult(
                    cmd=cmd,
                    cwd=None,
                    returncode=128,
                    stdout="",
                    stderr=(
                        "fatal: unable to access "
                        "'https://github.com/protocolbuffers/protobuf-go.git/': "
                        "schannel: failed to receive handshake, "
                        "SSL/TLS connection failed"
                    ),
                )

        if "rev-parse" in cmd:
            return module.CommandResult(
                cmd=cmd,
                cwd=None,
                returncode=0,
                stdout="abc123\n",
                stderr="",
            )

        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "sleep", fake_sleep)
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    checkout = module._ensure_checkout(
        workspace=workspace,
        spec={
            "name": "repo-a",
            "url": "https://example.invalid/repo-a.git",
            "ref": "main",
        },
    )

    assert checkout["resolved_commit"] == "abc123"
    assert fetch_attempts["count"] == 2
    assert any("checkout" in cmd for cmd in calls)
    assert any("rev-parse" in cmd for cmd in calls)


def test_benchmark_matrix_checkout_updates_configured_submodules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_benchmark_matrix.py")
    workspace = tmp_path / "workspace"
    target = workspace / "repo-a"
    (target / ".git").mkdir(parents=True, exist_ok=True)

    calls: list[list[str]] = []

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = cwd
        calls.append(list(cmd))
        if "rev-parse" in cmd:
            return module.CommandResult(
                cmd=cmd,
                cwd=None,
                returncode=0,
                stdout="abc123\n",
                stderr="",
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    checkout = module._ensure_checkout(
        workspace=workspace,
        spec={
            "name": "repo-a",
            "url": "https://example.invalid/repo-a.git",
            "ref": "main",
            "submodules": [
                "lib/forge-std",
                "lib/solmate",
                "lib/openzeppelin-contracts",
            ],
        },
    )

    assert checkout["resolved_commit"] == "abc123"
    assert checkout["submodules"] == {
        "enabled": True,
        "paths": [
            "lib/forge-std",
            "lib/solmate",
            "lib/openzeppelin-contracts",
        ],
    }
    assert [
        "git",
        "-C",
        str(target),
        "submodule",
        "sync",
        "--recursive",
    ] in calls
    assert [
        "git",
        "-C",
        str(target),
        "submodule",
        "update",
        "--init",
        "--depth",
        "1",
        "--recursive",
        "--",
        "lib/forge-std",
        "lib/solmate",
        "lib/openzeppelin-contracts",
    ] in calls


def test_benchmark_matrix_checkout_retries_transient_submodule_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_benchmark_matrix.py")
    workspace = tmp_path / "workspace"
    target = workspace / "repo-a"
    (target / ".git").mkdir(parents=True, exist_ok=True)

    submodule_attempts = {"count": 0}

    def fake_sleep(_: float) -> None:
        return None

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = cwd
        if cmd[-6:] == ["submodule", "update", "--init", "--depth", "1", "--recursive"]:
            submodule_attempts["count"] += 1
            if submodule_attempts["count"] == 1:
                return module.CommandResult(
                    cmd=cmd,
                    cwd=None,
                    returncode=128,
                    stdout="",
                    stderr=(
                        "fatal: unable to access "
                        "'https://github.com/foundry-rs/forge-std.git/': "
                        "schannel: failed to receive handshake, "
                        "SSL/TLS connection failed"
                    ),
                )
        if "rev-parse" in cmd:
            return module.CommandResult(
                cmd=cmd,
                cwd=None,
                returncode=0,
                stdout="abc123\n",
                stderr="",
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "sleep", fake_sleep)
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    checkout = module._ensure_checkout(
        workspace=workspace,
        spec={
            "name": "repo-a",
            "url": "https://example.invalid/repo-a.git",
            "ref": "main",
            "submodules": True,
        },
    )

    assert checkout["resolved_commit"] == "abc123"
    assert checkout["submodules"] == {"enabled": True, "paths": []}
    assert submodule_attempts["count"] == 2


def test_release_freeze_plugin_gate_evaluation() -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_summary = {
        "plugin_policy_summary": {
            "totals": {
                "applied": 5,
                "conflicts": 2,
                "blocked": 1,
                "warn": 3,
                "remote_applied": 0,
            }
        }
    }

    failures = module._evaluate_plugin_policy_gate(
        matrix_summary=matrix_summary,
        max_conflicts=1,
        max_blocked=1,
        max_warn=2,
    )

    assert failures == [
        {
            "metric": "plugin_conflicts",
            "actual": 2,
            "operator": "<=",
            "expected": 1,
        },
        {
            "metric": "plugin_warn",
            "actual": 3,
            "operator": "<=",
            "expected": 2,
        },
    ]


def test_release_freeze_gate_threshold_from_mapping_preserves_zero() -> None:
    module = _load_script("run_release_freeze_regression.py")

    assert module._gate_threshold_from_mapping({"max_conflicts": 0}, "max_conflicts") == 0
    assert module._gate_threshold_from_mapping({"max_warn": "3"}, "max_warn") == 3
    assert module._gate_threshold_from_mapping({}, "max_warn") == -1


def test_release_freeze_plugin_gate_config_resolution(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        "\n".join(
            [
                "freeze:",
                "  plugin_policy_gate_default_profile: strict",
                "  plugin_policy_gate_profiles:",
                "    strict:",
                "      max_conflicts: 2",
                "      max_blocked: 1",
                "      max_warn: 5",
                "    relaxed:",
                "      max_conflicts: 4",
                "      max_blocked: 3",
                "      max_warn: 10",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resolved_default = module._resolve_plugin_gate_config(
        matrix_config_path=matrix_config,
        profile="",
        cli_max_conflicts=-1,
        cli_max_blocked=-1,
        cli_max_warn=-1,
    )
    assert resolved_default == {
        "profile": "strict",
        "profile_from_config": True,
        "source": "profile",
        "thresholds": {
            "max_conflicts": 2,
            "max_blocked": 1,
            "max_warn": 5,
        },
    }

    resolved_override = module._resolve_plugin_gate_config(
        matrix_config_path=matrix_config,
        profile="relaxed",
        cli_max_conflicts=0,
        cli_max_blocked=-1,
        cli_max_warn=2,
    )
    assert resolved_override == {
        "profile": "relaxed",
        "profile_from_config": True,
        "source": "mixed",
        "thresholds": {
            "max_conflicts": 0,
            "max_blocked": 3,
            "max_warn": 2,
        },
    }

    resolved_disabled = module._resolve_plugin_gate_config(
        matrix_config_path=matrix_config,
        profile="missing",
        cli_max_conflicts=-1,
        cli_max_blocked=-1,
        cli_max_warn=-1,
    )
    assert resolved_disabled == {
        "profile": "",
        "profile_from_config": False,
        "source": "disabled",
        "thresholds": {
            "max_conflicts": -1,
            "max_blocked": -1,
            "max_warn": -1,
        },
    }


def test_release_freeze_tabiv3_gate_config_and_evaluation(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  tabiv3_gate:
    enabled: true
    matrix_config: benchmark/matrix/tabiv3.yaml
    latency_p95_ms_max: 170
    repomap_latency_p95_ms_max: 110
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_tabiv3_gate_config(matrix_config_path=matrix_config)
    assert resolved == {
        "enabled": True,
        "source": "config",
        "matrix_config": "benchmark/matrix/tabiv3.yaml",
        "thresholds": {
            "latency_p95_ms_max": 170.0,
            "repomap_latency_p95_ms_max": 110.0,
        },
        "retry_count": 0,
    }

    failures = module._evaluate_tabiv3_gate(
        matrix_summary={
            "latency_metrics_repos": [
                {
                    "name": "flask-tabiv3",
                    "latency_p95_ms": 166.0,
                    "repomap_latency_p95_ms": 100.0,
                },
                {
                    "name": "flask-tabiv3-slow",
                    "latency_p95_ms": 171.2,
                    "repomap_latency_p95_ms": 115.3,
                },
            ]
        },
        latency_p95_ms_max=170.0,
        repomap_latency_p95_ms_max=110.0,
    )
    assert failures == [
        {
            "repo": "flask-tabiv3-slow",
            "metric": "latency_p95_ms",
            "actual": 171.2,
            "operator": "<=",
            "expected": 170.0,
        },
        {
            "repo": "flask-tabiv3-slow",
            "metric": "repomap_latency_p95_ms",
            "actual": 115.3,
            "operator": "<=",
            "expected": 110.0,
        },
    ]


def test_release_freeze_concept_gate_config_and_threshold_evaluation(
    tmp_path: Path,
) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  concept_gate:
    enabled: true
    cases: benchmark/cases/p1_concepts.yaml
    repo: ace-lite-engine
    root: .
    skills_dir: skills
    top_k_files: 6
    min_candidate_score: 2
    candidate_ranker: heuristic
    retrieval_policy: auto
    chunk_top_k: 24
    cochange: true
    thresholds:
      precision_at_k_min: 0.55
      noise_rate_max: 0.45
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_concept_gate_config(matrix_config_path=matrix_config)
    assert resolved["enabled"] is True
    assert resolved["source"] == "config"
    assert resolved["cases"] == "benchmark/cases/p1_concepts.yaml"
    assert resolved["repo"] == "ace-lite-engine"
    assert resolved["top_k_files"] == 6
    assert resolved["cochange_enabled"] is True
    assert resolved["retry_count"] == 0
    assert resolved["thresholds"] == {
        "precision_at_k_min": 0.55,
        "noise_rate_max": 0.45,
    }

    failures = module._evaluate_metric_thresholds(
        metrics={"precision_at_k": 0.50, "noise_rate": 0.52},
        thresholds=resolved["thresholds"],
        repo_name="ace-lite-engine",
    )
    assert failures == [
        {
            "repo": "ace-lite-engine",
            "metric": "precision_at_k",
            "actual": 0.5,
            "operator": ">=",
            "expected": 0.55,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "noise_rate",
            "actual": 0.52,
            "operator": "<=",
            "expected": 0.45,
        },
    ]


def test_release_freeze_external_concept_gate_config_and_evaluation(
    tmp_path: Path,
) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  external_concept_gate:
    enabled: true
    matrix_config: benchmark/matrix/external_howwhy.yaml
    thresholds:
      precision_at_k_min: 0.58
      noise_rate_max: 0.42
      latency_p95_ms_max: 450
      chunk_hit_at_k_min: 0.80
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_external_concept_gate_config(
        matrix_config_path=matrix_config
    )
    assert resolved == {
        "enabled": True,
        "source": "config",
        "matrix_config": "benchmark/matrix/external_howwhy.yaml",
        "thresholds": {
            "precision_at_k_min": 0.58,
            "noise_rate_max": 0.42,
            "latency_p95_ms_max": 450.0,
            "chunk_hit_at_k_min": 0.8,
        },
    }

    failures, metrics = module._evaluate_external_concept_gate(
        matrix_summary={
            "repo_count": 3,
            "retrieval_metrics_mean": {
                "precision_at_k": 0.59,
                "noise_rate": 0.41,
                "latency_p95_ms": 220.0,
                "chunk_hit_at_k": 0.83,
            },
        },
        thresholds=resolved["thresholds"],
    )
    assert failures == []
    assert metrics == {
        "precision_at_k": 0.59,
        "noise_rate": 0.41,
        "latency_p95_ms": 220.0,
        "chunk_hit_at_k": 0.83,
    }

    failures_no_repo, _ = module._evaluate_external_concept_gate(
        matrix_summary={
            "repo_count": 0,
            "retrieval_metrics_mean": {
                "precision_at_k": 0.59,
                "noise_rate": 0.41,
                "latency_p95_ms": 220.0,
                "chunk_hit_at_k": 0.83,
            },
        },
        thresholds=resolved["thresholds"],
    )
    assert failures_no_repo == [
        {
            "repo": "external_concept_gate",
            "metric": "repo_count",
            "actual": 0.0,
            "operator": ">=",
            "expected": 1.0,
        }
    ]


def test_release_freeze_feature_slices_gate_config_resolution(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  feature_slices_gate:
    enabled: true
    config: benchmark/matrix/feature_slices.yaml
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_feature_slices_gate_config(matrix_config_path=matrix_config)
    assert resolved == {
        "enabled": True,
        "source": "config",
        "config": "benchmark/matrix/feature_slices.yaml",
    }

    disabled_config = tmp_path / "matrix-disabled.yaml"
    disabled_config.write_text(
        """
freeze:
  feature_slices_gate:
    enabled: false
""".lstrip(),
        encoding="utf-8",
    )
    resolved_disabled = module._resolve_feature_slices_gate_config(
        matrix_config_path=disabled_config
    )
    assert resolved_disabled == {
        "enabled": False,
        "source": "disabled",
        "config": "benchmark/matrix/feature_slices.yaml",
    }


def test_release_freeze_feature_slices_gate_evaluation() -> None:
    module = _load_script("run_release_freeze_regression.py")

    assert module._evaluate_feature_slices_gate(summary={}) == [
        {
            "repo": "feature_slices_gate",
            "metric": "summary",
            "actual": "missing",
            "operator": "==",
            "expected": "present",
            "reason": "summary_missing",
        }
    ]

    assert module._evaluate_feature_slices_gate(
        summary={"passed": False, "slices": []}
    ) == [
        {
            "repo": "feature_slices_gate",
            "metric": "slices",
            "actual": 0.0,
            "operator": ">=",
            "expected": 1.0,
            "reason": "no_slices",
        }
    ]

    assert module._evaluate_feature_slices_gate(
        summary={
            "passed": False,
            "slices": [
                {
                    "name": "feedback",
                    "passed": False,
                    "failures": [
                        {
                            "metric": "precision_delta",
                            "actual": 0.1,
                            "operator": ">=",
                            "expected": 0.5,
                        }
                    ],
                }
            ],
        }
    ) == [
        {
            "repo": "feature_slices_gate",
            "metric": "precision_delta",
            "slice": "feedback",
            "actual": 0.1,
            "operator": ">=",
            "expected": 0.5,
        }
    ]


def test_release_freeze_main_includes_feature_slices_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  feature_slices_gate:
    enabled: true
    config: benchmark/matrix/feature_slices.yaml
""".lstrip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "freeze-output"

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        _ = command
        _ = cwd
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=["step"],
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {"totals": {}},
            "retrieval_metrics_mean": {},
            "memory_metrics_mean": {},
            "embedding_metrics_mean": {},
        }

    def fake_load_feature_slices_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "slices": [
                {"name": "feedback", "passed": True},
                {"name": "temporal", "passed": True},
                {"name": "index_batch", "passed": True},
                {"name": "late_interaction", "passed": True},
                {"name": "dependency_recall", "passed": True},
                {"name": "perturbation", "passed": True},
                {"name": "repomap_perturbation", "passed": True},
            ],
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(module, "_load_feature_slices_summary", fake_load_feature_slices_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert [step["name"] for step in payload["steps"]] == [
        "functional_pytest",
        "config_compatibility",
        "runtime_regression",
        "e2e_success_slice",
        "benchmark_matrix",
        "feature_slices_gate",
    ]
    assert payload["feature_slices_gate"] == {
        "enabled": True,
        "passed": True,
        "source": "config",
        "config": str(
            (Path(__file__).resolve().parents[2] / "benchmark" / "matrix" / "feature_slices.yaml").resolve()
        ),
        "summary_path": str((output_dir / "feature-slices" / "feature_slices_summary.json").resolve()),
        "summary_passed": True,
        "slice_count": 7,
        "failures": [],
    }


def test_release_freeze_main_includes_skill_validation_step_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text("freeze:\n  runtime_gate: true\n", encoding="utf-8")
    output_dir = tmp_path / "freeze-output"
    captured_commands: dict[str, list[str]] = {}

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        _ = cwd
        captured_commands[name] = list(command)
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {"totals": {}},
            "retrieval_metrics_mean": {},
            "memory_metrics_mean": {},
            "embedding_metrics_mean": {},
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skill-validation-apps",
            "codex,claude-code",
            "--skill-validation-min-pass-rate",
            "0.75",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert "skill_validation_matrix" in [step["name"] for step in payload["steps"]]
    skill_command = captured_commands["skill_validation_matrix"]
    assert skill_command[1].endswith("run_skill_validation.py")
    assert "--apps" in skill_command
    assert "codex,claude-code" in skill_command
    assert "--min-pass-rate" in skill_command
    assert "0.75" in skill_command
    assert "--fail-on-miss" in skill_command


def test_release_freeze_main_profile_override_source_mixed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        "\n".join(
            [
                "freeze:",
                "  plugin_policy_gate_default_profile: strict",
                "  plugin_policy_gate_profiles:",
                "    strict:",
                "      max_conflicts: 0",
                "      max_blocked: 0",
                "      max_warn: 1",
                "    balanced:",
                "      max_conflicts: 2",
                "      max_blocked: 1",
                "      max_warn: 5",
                "",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "freeze-output"

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 3,
                    "conflicts": 0,
                    "blocked": 1,
                    "warn": 5,
                    "remote_applied": 0,
                }
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
            "--plugin-gate-profile",
            "balanced",
            "--max-plugin-conflicts",
            "0",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    plugin_gate = payload["plugin_policy_gate"]

    assert plugin_gate == {
        "enabled": True,
        "passed": True,
        "profile": "balanced",
        "profile_from_config": True,
        "source": "mixed",
        "thresholds": {
            "max_conflicts": 0,
            "max_blocked": 1,
            "max_warn": 5,
        },
        "failures": [],
    }
    assert [step["name"] for step in payload["steps"]] == [
        "functional_pytest",
        "config_compatibility",
        "runtime_regression",
        "e2e_success_slice",
        "benchmark_matrix",
    ]


def test_release_freeze_main_includes_tabiv3_and_concept_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        "\n".join(
            [
                "freeze:",
                "  tabiv3_gate:",
                "    enabled: true",
                "    matrix_config: benchmark/matrix/tabiv3.yaml",
                "    latency_p95_ms_max: 170.0",
                "    repomap_latency_p95_ms_max: 110.0",
                "  concept_gate:",
                "    enabled: true",
                "    cases: benchmark/cases/p1_concepts.yaml",
                "    repo: ace-lite-engine",
                "    root: .",
                "    skills_dir: skills",
                "    thresholds:",
                "      precision_at_k_min: 0.55",
                "      noise_rate_max: 0.45",
                "",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "freeze-output"

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        path = str(summary_path).replace("\\", "/")
        if "benchmark-matrix-tabiv3" in path:
            return {
                "passed": True,
                "repo_count": 1,
                "latency_metrics_repos": [
                    {
                        "name": "flask-tabiv3",
                        "latency_p95_ms": 166.3,
                        "repomap_latency_p95_ms": 1.4,
                    }
                ],
            }
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 0,
                    "conflicts": 0,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            },
        }

    def fake_load_benchmark_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "repo": "ace-lite-engine",
            "case_count": 5,
            "metrics": {
                "precision_at_k": 0.66,
                "noise_rate": 0.34,
                "chunk_hit_at_k": 0.9,
                "latency_p95_ms": 120.0,
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(module, "_load_benchmark_summary", fake_load_benchmark_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert payload["tabiv3_gate"]["enabled"] is True
    assert payload["tabiv3_gate"]["passed"] is True
    assert payload["tabiv3_gate"]["failures"] == []
    assert payload["tabiv3_gate"]["retry_count"] == 0
    assert payload["tabiv3_gate"]["retry_attempts_executed"] == 0
    assert payload["concept_gate"]["enabled"] is True
    assert payload["concept_gate"]["passed"] is True
    assert payload["concept_gate"]["failures"] == []
    project_root = Path(__file__).resolve().parents[2]
    assert payload["concept_gate"]["execution_config"] == {
        "root": str(project_root.resolve()),
        "skills_dir": str((project_root / "skills").resolve()),
        "top_k_files": 6,
        "min_candidate_score": 2,
        "candidate_ranker": "heuristic",
        "retrieval_policy": "auto",
        "chunk_top_k": 24,
        "cochange": False,
    }
    assert [step["name"] for step in payload["steps"]] == [
        "benchmark_matrix_tabiv3",
        "functional_pytest",
        "config_compatibility",
        "runtime_regression",
        "e2e_success_slice",
        "benchmark_matrix",
        "benchmark_concept_gate",
    ]
    concept_step = next(
        step for step in payload["steps"] if step["name"] == "benchmark_concept_gate"
    )
    assert "--no-cochange" in concept_step["command_line"]


def test_release_freeze_main_includes_external_concept_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        "\n".join(
            [
                "freeze:",
                "  external_concept_gate:",
                "    enabled: true",
                "    matrix_config: benchmark/matrix/external_howwhy.yaml",
                "    thresholds:",
                "      precision_at_k_min: 0.58",
                "      noise_rate_max: 0.42",
                "      latency_p95_ms_max: 450.0",
                "      chunk_hit_at_k_min: 0.80",
                "",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "freeze-output"

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        path = str(summary_path).replace("\\", "/")
        if "benchmark-matrix-external-concept" in path:
            return {
                "passed": True,
                "repo_count": 3,
                "retrieval_metrics_mean": {
                    "precision_at_k": 0.60,
                    "noise_rate": 0.40,
                    "latency_p95_ms": 230.0,
                    "chunk_hit_at_k": 0.82,
                },
            }
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 0,
                    "conflicts": 0,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
            "--no-runtime-gate",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert payload["external_concept_gate"] == {
        "enabled": True,
        "passed": True,
        "source": "config",
        "matrix_config": str((Path(__file__).resolve().parents[2] / "benchmark/matrix/external_howwhy.yaml").resolve()),
        "repo_count": 3,
        "matrix_summary_passed": True,
        "thresholds": {
            "precision_at_k_min": 0.58,
            "noise_rate_max": 0.42,
            "latency_p95_ms_max": 450.0,
            "chunk_hit_at_k_min": 0.8,
        },
        "metrics": {
            "precision_at_k": 0.6,
            "noise_rate": 0.4,
            "latency_p95_ms": 230.0,
            "chunk_hit_at_k": 0.82,
        },
        "failures": [],
    }
    assert "benchmark_matrix_external_concept" in [step["name"] for step in payload["steps"]]


def test_release_freeze_runtime_gate_config_resolution(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        "\n".join(
            [
                "freeze:",
                "  runtime_gate:",
                "    enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resolved_default = module._resolve_runtime_gate_config(
        matrix_config_path=matrix_config,
        cli_enabled=None,
    )
    assert resolved_default == {
        "enabled": False,
        "source": "config",
    }

    resolved_cli = module._resolve_runtime_gate_config(
        matrix_config_path=matrix_config,
        cli_enabled=True,
    )
    assert resolved_cli == {
        "enabled": True,
        "source": "cli",
    }


def test_release_freeze_load_matrix_summary_and_render(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")

    payload = {
        "passed": False,
        "benchmark_regression_detected": True,
        "repo_count": 2,
        "retrieval_policy_summary": [
            {
                "retrieval_policy": "feature",
                "repo_count": 1,
                "regressed_repo_count": 1,
                "regressed_repo_rate": 1.0,
                "task_success_mean": 0.7,
                "positive_task_success_mean": 0.8,
                "retrieval_task_gap_rate_mean": 0.4,
                "precision_at_k_mean": 0.55,
                "noise_rate_mean": 0.35,
                "latency_p95_ms_mean": 28.0,
                "repomap_latency_p95_ms_mean": 10.0,
                "slo_downgrade_case_rate_mean": 0.25,
            }
        ],
        "plugin_policy_summary": {
            "totals": {
                "applied": 5,
                "conflicts": 1,
                "blocked": 1,
                "warn": 2,
                "remote_applied": 1,
            },
            "mode_distribution": {"strict": 1, "permissive": 1},
            "repos": [
                {
                    "name": "repo-b",
                    "mode": "strict",
                    "applied": 3,
                    "conflicts": 1,
                    "blocked": 0,
                    "warn": 2,
                    "remote_applied": 1,
                }
            ],
        },
        "stage_latency_summary": {
            "index": {"mean_ms": 5.0, "p95_ms": 5.5},
            "repomap": {"mean_ms": 2.0, "p95_ms": 2.5},
            "source_plan": {"mean_ms": 3.0, "p95_ms": 3.0},
            "total": {"mean_ms": 12.0, "median_ms": 12.0, "p95_ms": 13.0},
        },
        "slo_budget_summary": {
            "case_count": 2,
            "budget_limits_ms": {
                "parallel_time_budget_ms_mean": 30.0,
                "embedding_time_budget_ms_mean": 55.0,
                "chunk_semantic_time_budget_ms_mean": 20.0,
                "xref_time_budget_ms_mean": 15.0,
            },
            "downgrade_case_count": 1,
            "downgrade_case_rate": 0.5,
            "signals": {
                "parallel_docs_timeout_ratio": {"count": 1, "rate": 0.5},
                "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                "embedding_time_budget_exceeded_ratio": {"count": 1, "rate": 0.5},
                "embedding_adaptive_budget_ratio": {"count": 0, "rate": 0.0},
                "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                "chunk_semantic_fallback_ratio": {"count": 1, "rate": 0.5},
                "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
            },
        },
        "repos": [
            {
                "name": "repo-a",
                "metrics": {"task_success_rate": 0.93, "utility_rate": 0.95},
                "failed_checks": [{"metric": "precision_at_k"}],
                "benchmark_regressed": False,
                "benchmark_failed_checks": [],
            },
            {
                "name": "repo-b",
                "metrics": {"utility_rate": 0.70},
                "failed_checks": [],
                "benchmark_regressed": True,
                "benchmark_failed_checks": ["validation_test_count"],
            },
        ],
    }

    temp_path = tmp_path / "matrix_summary.json"
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        summary = module._load_matrix_summary(summary_path=temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    assert summary["passed"] is False
    assert summary["benchmark_regression_detected"] is True
    assert summary["repo_count"] == 2
    assert summary["threshold_failed_repos"] == [{"name": "repo-a", "failure_count": 1}]
    assert summary["regressed_repos"] == [
        {
            "name": "repo-b",
            "regressed": True,
            "failed_checks": ["validation_test_count"],
        }
    ]
    assert summary["task_success_repos"] == [
        {"name": "repo-a", "task_success_rate": 0.93},
        {"name": "repo-b", "task_success_rate": 0.7},
    ]
    assert summary["latency_metrics_repos"] == [
        {
            "name": "repo-a",
            "latency_p95_ms": 0.0,
            "repomap_latency_p95_ms": 0.0,
        },
        {
            "name": "repo-b",
            "latency_p95_ms": 0.0,
            "repomap_latency_p95_ms": 0.0,
        },
    ]
    assert summary["latency_metrics_mean"] == {
        "latency_p95_ms": 0.0,
        "repomap_latency_p95_ms": 0.0,
    }
    assert summary["retrieval_metrics_repos"] == [
        {
            "name": "repo-a",
            "precision_at_k": 0.0,
            "noise_rate": 0.0,
            "latency_p95_ms": 0.0,
            "chunk_hit_at_k": 0.0,
        },
        {
            "name": "repo-b",
            "precision_at_k": 0.0,
            "noise_rate": 0.0,
            "latency_p95_ms": 0.0,
            "chunk_hit_at_k": 0.0,
        },
    ]
    assert summary["retrieval_metrics_mean"] == {
        "precision_at_k": 0.0,
        "noise_rate": 0.0,
        "latency_p95_ms": 0.0,
        "chunk_hit_at_k": 0.0,
    }
    assert summary["memory_metrics_repos"] == [
        {
            "name": "repo-a",
            "notes_hit_ratio": 0.0,
            "profile_selected_mean": 0.0,
            "capture_trigger_ratio": 0.0,
        },
        {
            "name": "repo-b",
            "notes_hit_ratio": 0.0,
            "profile_selected_mean": 0.0,
            "capture_trigger_ratio": 0.0,
        },
    ]
    assert summary["embedding_metrics_repos"] == [
        {
            "name": "repo-a",
            "embedding_similarity_mean": 0.0,
            "embedding_rerank_ratio": 0.0,
            "embedding_cache_hit_ratio": 0.0,
            "embedding_fallback_ratio": 0.0,
            "embedding_enabled_ratio": 0.0,
        },
        {
            "name": "repo-b",
            "embedding_similarity_mean": 0.0,
            "embedding_rerank_ratio": 0.0,
            "embedding_cache_hit_ratio": 0.0,
            "embedding_fallback_ratio": 0.0,
            "embedding_enabled_ratio": 0.0,
        },
    ]
    assert summary["retrieval_policy_summary"] == [
        {
            "retrieval_policy": "feature",
            "repo_count": 1,
            "regressed_repo_count": 1,
            "regressed_repo_rate": 1.0,
            "task_success_mean": 0.7,
            "positive_task_success_mean": 0.8,
            "retrieval_task_gap_rate_mean": 0.4,
            "precision_at_k_mean": 0.55,
            "noise_rate_mean": 0.35,
            "latency_p95_ms_mean": 28.0,
            "repomap_latency_p95_ms_mean": 10.0,
            "slo_downgrade_case_rate_mean": 0.25,
        }
    ]
    assert summary["plugin_policy_summary"] == {
        "totals": {
            "applied": 5,
            "conflicts": 1,
            "blocked": 1,
            "warn": 2,
            "remote_applied": 1,
        },
        "mode_distribution": {"permissive": 1, "strict": 1},
        "repos": [
            {
                "name": "repo-b",
                "mode": "strict",
                "applied": 3,
                "conflicts": 1,
                "blocked": 0,
                "warn": 2,
                "remote_applied": 1,
            }
        ],
    }
    assert summary["embedding_metrics_mean"] == {
        "embedding_similarity_mean": 0.0,
        "embedding_rerank_ratio": 0.0,
        "embedding_cache_hit_ratio": 0.0,
        "embedding_fallback_ratio": 0.0,
        "embedding_enabled_ratio": 0.0,
    }
    assert summary["stage_latency_summary"]["index"]["p95_ms"] == 5.5
    assert summary["slo_budget_summary"]["downgrade_case_rate"] == 0.5

    markdown = module._render_markdown(
        payload={
            "generated_at": "2026-02-12T00:00:00Z",
            "passed": False,
            "elapsed_seconds": 1.23,
            "root": ".",
            "steps": [
                {
                    "name": "functional_pytest",
                    "passed": True,
                    "returncode": 0,
                    "elapsed_seconds": 0.5,
                    "command_line": "pytest -q",
                    "stdout_path": "a",
                    "stderr_path": "b",
                }
            ],
            "benchmark_matrix_summary": summary,
            "plugin_policy_gate": {
                "enabled": True,
                "passed": False,
                "profile": "strict",
                "source": "profile",
                "thresholds": {
                    "max_conflicts": 0,
                    "max_blocked": 0,
                    "max_warn": 1,
                },
                "failures": [
                    {
                        "metric": "plugin_conflicts",
                        "actual": 1,
                        "operator": "<=",
                        "expected": 0,
                    }
                ],
            },
            "retrieval_policy_guard": {
                "enabled": True,
                "passed": False,
                "mode": "enforced",
                "report_only": False,
                "enforced": True,
                "source": "config",
                "thresholds": {
                    "max_regressed_repo_rate": 0.0,
                    "min_task_success_mean": 0.8,
                    "max_retrieval_task_gap_rate_mean": 0.25,
                    "max_noise_rate_mean": 0.3,
                    "max_latency_p95_ms_mean": 20.0,
                    "max_slo_downgrade_case_rate_mean": 0.2,
                },
                "failures": [
                    {
                        "policy": "feature",
                        "metric": "task_success_mean",
                        "actual": 0.7,
                        "operator": ">=",
                        "expected": 0.8,
                    }
                ],
            },
            "runtime_gate": {
                "enabled": True,
                "passed": False,
                "source": "config",
                "step": "runtime_regression",
                "failures": [
                    {
                        "metric": "runtime_regression_step",
                        "actual": 1,
                        "operator": "==",
                        "expected": 0,
                        "reason": "step_failed",
                    }
                ],
            },
            "tabiv3_gate": {
                "enabled": True,
                "passed": False,
                "source": "config",
                "matrix_config": "benchmark/matrix/tabiv3.yaml",
                "repo_count": 1,
                "matrix_summary_passed": False,
                "thresholds": {
                    "latency_p95_ms_max": 170.0,
                    "repomap_latency_p95_ms_max": 110.0,
                },
                "failures": [
                    {
                        "repo": "flask-tabiv3",
                        "metric": "latency_p95_ms",
                        "actual": 176.4,
                        "operator": "<=",
                        "expected": 170.0,
                    }
                ],
            },
            "concept_gate": {
                "enabled": True,
                "passed": False,
                "source": "config",
                "cases": "benchmark/cases/p1_concepts.yaml",
                "case_count": 5,
                "thresholds": {
                    "precision_at_k_min": 0.55,
                    "noise_rate_max": 0.45,
                },
                "metrics": {
                    "precision_at_k": 0.5,
                    "noise_rate": 0.5,
                    "chunk_hit_at_k": 0.9,
                    "latency_p95_ms": 120.0,
                },
                "failures": [
                    {
                        "repo": "ace-lite-engine",
                        "metric": "precision_at_k",
                        "actual": 0.5,
                        "operator": ">=",
                        "expected": 0.55,
                    }
                ],
            },
            "external_concept_gate": {
                "enabled": True,
                "passed": False,
                "source": "config",
                "matrix_config": "benchmark/matrix/external_howwhy.yaml",
                "repo_count": 3,
                "thresholds": {
                    "precision_at_k_min": 0.58,
                    "noise_rate_max": 0.42,
                },
                "metrics": {
                    "precision_at_k": 0.56,
                    "noise_rate": 0.44,
                    "chunk_hit_at_k": 0.81,
                    "latency_p95_ms": 220.0,
                },
                "failures": [
                    {
                        "repo": "external_concept_gate",
                        "metric": "precision_at_k",
                        "actual": 0.56,
                        "operator": ">=",
                        "expected": 0.58,
                    }
                ],
            },
        }
    )

    assert "| functional_pytest | PASS |" in markdown
    assert "## Benchmark Matrix Summary" in markdown
    assert "Benchmark regression detected: True" in markdown
    assert "repo-b: regressed=True, failed_checks=validation_test_count" in markdown
    assert "Retrieval policy summary:" in markdown
    assert "feature: repos=1, regressed=1, regressed_rate=1.0000, task_success=0.7000, positive_task=0.8000, gap_rate=0.4000, precision=0.5500, noise=0.3500, latency_p95_ms=28.00, repomap_p95_ms=10.00, slo_downgrade=0.2500" in markdown
    assert "Plugin policy totals: applied=5, conflicts=1, blocked=1, warn=2, remote_applied=1" in markdown
    assert "Plugin policy modes: permissive=1, strict=1" in markdown
    assert "repo-b: mode=strict, applied=3, conflicts=1, blocked=0, warn=2, remote_applied=1" in markdown
    assert "Stage latency summary: total_mean=12.00ms, total_p95=13.00ms, index_p95=5.50ms, repomap_p95=2.50ms, source_plan_p95=3.00ms" in markdown
    assert "SLO budget summary: downgrade_case_rate=0.5000, parallel_budget=30.00ms, embedding_budget=55.00ms, chunk_semantic_budget=20.00ms, xref_budget=15.00ms" in markdown
    assert "SLO signal rates: parallel_docs_timeout=0.5000, embedding_budget_exceeded=0.5000, embedding_fallback=0.0000, chunk_semantic_fallback=0.5000, xref_budget_exhausted=0.0000" in markdown
    assert "Embedding means:" in markdown
    assert "## Plugin Policy Gate" in markdown
    assert "Profile: strict" in markdown
    assert "Source: profile" in markdown
    assert "Thresholds: conflicts<=0, blocked<=0, warn<=1" in markdown
    assert "plugin_conflicts: actual=1, expected <= 0" in markdown
    assert "## Retrieval Policy Guard" in markdown
    assert "Mode: enforced" in markdown
    assert "Enforced: True" in markdown
    assert "regressed_repo_rate<=0.0000" in markdown
    assert "task_success_mean>=0.8000" in markdown
    assert "retrieval_task_gap_rate_mean<=0.2500" in markdown
    assert "noise_rate_mean<=0.3000" in markdown
    assert "latency_p95_ms_mean<=20.00" in markdown
    assert "slo_downgrade_case_rate_mean<=0.2000" in markdown
    assert "feature: task_success_mean=0.7, expected >= 0.8" in markdown
    assert "## TabIV3 Gate" in markdown
    assert "Matrix config: benchmark/matrix/tabiv3.yaml" in markdown
    assert "latency_p95_ms=176.4000, expected <= 170.0000" in markdown
    assert "## Concept Benchmark Gate" in markdown
    assert "Cases: benchmark/cases/p1_concepts.yaml" in markdown
    assert "precision_at_k=0.5000, expected >= 0.5500" in markdown
    assert "## External Concept Gate" in markdown
    assert "Matrix config: benchmark/matrix/external_howwhy.yaml" in markdown
    assert "external_concept_gate: precision_at_k=0.5600, expected >= 0.5800" in markdown
    assert "## Runtime Gate" in markdown
    assert "Step: runtime_regression" in markdown
    assert "runtime_regression_step: actual=1, expected == 0 (step_failed)" in markdown


def test_release_freeze_markdown_includes_feature_slices_gate() -> None:
    module = _load_script("run_release_freeze_regression.py")
    markdown = module._render_markdown(
        payload={
            "generated_at": "2026-02-12T00:00:00Z",
            "passed": False,
            "elapsed_seconds": 1.23,
            "root": ".",
            "steps": [],
            "benchmark_matrix_summary": {},
            "feature_slices_gate": {
                "enabled": True,
                "passed": False,
                "source": "config",
                "config": "benchmark/matrix/feature_slices.yaml",
                "summary_path": "feature_slices_summary.json",
                "summary_passed": False,
                "slice_count": 7,
                "failures": [
                    {
                        "repo": "feature_slices_gate",
                        "metric": "precision_delta",
                        "slice": "feedback",
                        "actual": 0.1,
                        "operator": ">=",
                        "expected": 0.5,
                        "reason": "slice_failed",
                    }
                ],
            },
        }
    )

    assert "## Feature Slices Gate" in markdown
    assert "Config: benchmark/matrix/feature_slices.yaml" in markdown
    assert "Summary passed: False" in markdown
    assert "Slice count: 7" in markdown
    assert "precision_delta: slice=feedback actual=0.1, expected >= 0.5 (slice_failed)" in markdown


def test_release_freeze_markdown_includes_validation_rich_summary() -> None:
    module = _load_script("run_release_freeze_regression.py")
    markdown = module._render_markdown(
        payload={
            "generated_at": "2026-03-12T00:00:00Z",
            "passed": True,
            "elapsed_seconds": 1.23,
            "root": ".",
            "steps": [],
            "validation_rich_benchmark": {
                "enabled": True,
                "report_only": True,
                "summary_path": "artifacts/benchmark/validation_rich/latest/summary.json",
                "previous_summary_path": "artifacts/benchmark/validation_rich/previous/summary.json",
                "loaded": True,
                "previous_loaded": True,
                "repo": "ace-lite-engine",
                "case_count": 5,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.425,
                    "noise_rate": 0.575,
                    "validation_test_count": 5.0,
                    "latency_p95_ms": 617.66,
                    "evidence_insufficient_rate": 0.0,
                    "missing_validation_rate": 0.0,
                },
                "previous_metrics": {
                    "task_success_rate": 0.8,
                    "precision_at_k": 0.35,
                    "noise_rate": 0.65,
                    "validation_test_count": 4.0,
                    "latency_p95_ms": 692.08,
                    "evidence_insufficient_rate": 0.2,
                    "missing_validation_rate": 0.2,
                },
                "delta": {
                    "task_success_rate": {
                        "current": 1.0,
                        "previous": 0.8,
                        "delta": 0.2,
                    },
                    "precision_at_k": {
                        "current": 0.425,
                        "previous": 0.35,
                        "delta": 0.075,
                    },
                    "noise_rate": {
                        "current": 0.575,
                        "previous": 0.65,
                        "delta": -0.075,
                    },
                    "latency_p95_ms": {
                        "current": 617.66,
                        "previous": 692.08,
                        "delta": -74.42,
                    },
                    "validation_test_count": {
                        "current": 5.0,
                        "previous": 4.0,
                        "delta": 1.0,
                    },
                    "evidence_insufficient_rate": {
                        "current": 0.0,
                        "previous": 0.2,
                        "delta": -0.2,
                    },
                    "missing_validation_rate": {
                        "current": 0.0,
                        "previous": 0.2,
                        "delta": -0.2,
                    },
                },
            },
        }
    )

    assert "## Validation-Rich Benchmark" in markdown
    assert "Report only: True" in markdown
    assert "Summary: artifacts/benchmark/validation_rich/latest/summary.json" in markdown
    assert "Previous summary: artifacts/benchmark/validation_rich/previous/summary.json" in markdown
    assert "Loaded previous summary: True" in markdown
    assert "Repo: ace-lite-engine" in markdown
    assert "Case count: 5" in markdown
    assert "Failed checks: (none)" in markdown
    assert "Metrics: task_success=1.0000, precision=0.4250, noise=0.5750, validation_test_count=5.0000, latency_p95_ms=617.66, evidence_insufficient=0.0000, missing_validation=0.0000" in markdown
    assert "Previous metrics: task_success=0.8000, precision=0.3500, noise=0.6500, validation_test_count=4.0000, latency_p95_ms=692.08, evidence_insufficient=0.2000, missing_validation=0.2000" in markdown
    assert "Delta summary:" in markdown
    assert "precision_at_k: current=0.4250, previous=0.3500, delta=+0.0750" in markdown
    assert "latency_p95_ms: current=617.6600, previous=692.0800, delta=-74.4200" in markdown


def test_release_freeze_validation_rich_gate_config_and_evaluation(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  validation_rich_gate:
    mode: report_only
    thresholds:
      task_success_rate_min: 0.90
      precision_at_k_min: 0.40
      noise_rate_max: 0.60
      latency_p95_ms_max: 700.0
      validation_test_count_min: 5.0
      missing_validation_rate_max: 0.0
      evidence_insufficient_rate_max: 0.0
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_validation_rich_gate_config(
        matrix_config_path=matrix_config
    )
    assert resolved == {
        "enabled": True,
        "mode": "report_only",
        "report_only": True,
        "enforced": False,
        "source": "config_mode",
        "thresholds": {
            "task_success_rate_min": 0.9,
            "precision_at_k_min": 0.4,
            "noise_rate_max": 0.6,
            "latency_p95_ms_max": 700.0,
            "validation_test_count_min": 5.0,
            "missing_validation_rate_max": 0.0,
            "evidence_insufficient_rate_max": 0.0,
        },
    }

    failures = module._evaluate_validation_rich_gate(
        benchmark_summary={
            "repo": "ace-lite-engine",
            "case_count": 5,
            "metrics": {
                "task_success_rate": 0.8,
                "precision_at_k": 0.35,
                "noise_rate": 0.65,
                "latency_p95_ms": 710.0,
                "validation_test_count": 4.0,
                "missing_validation_rate": 0.2,
                "evidence_insufficient_rate": 0.2,
            },
        },
        thresholds=resolved["thresholds"],
    )
    assert failures == [
        {
            "repo": "ace-lite-engine",
            "metric": "task_success_rate",
            "actual": 0.8,
            "operator": ">=",
            "expected": 0.9,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "precision_at_k",
            "actual": 0.35,
            "operator": ">=",
            "expected": 0.4,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "noise_rate",
            "actual": 0.65,
            "operator": "<=",
            "expected": 0.6,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "latency_p95_ms",
            "actual": 710.0,
            "operator": "<=",
            "expected": 700.0,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "validation_test_count",
            "actual": 4.0,
            "operator": ">=",
            "expected": 5.0,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "missing_validation_rate",
            "actual": 0.2,
            "operator": "<=",
            "expected": 0.0,
        },
        {
            "repo": "ace-lite-engine",
            "metric": "evidence_insufficient_rate",
            "actual": 0.2,
            "operator": "<=",
            "expected": 0.0,
        },
    ]


def test_release_freeze_markdown_includes_validation_rich_gate() -> None:
    module = _load_script("run_release_freeze_regression.py")
    markdown = module._render_markdown(
        payload={
            "generated_at": "2026-03-12T00:00:00Z",
            "passed": True,
            "elapsed_seconds": 1.23,
            "root": ".",
            "steps": [],
            "validation_rich_gate": {
                "enabled": True,
                "passed": False,
                "mode": "report_only",
                "report_only": True,
                "enforced": False,
                "source": "config_mode",
                "summary_path": "artifacts/benchmark/validation_rich/latest/summary.json",
                "thresholds": {
                    "task_success_rate_min": 0.9,
                    "precision_at_k_min": 0.4,
                    "noise_rate_max": 0.6,
                    "latency_p95_ms_max": 700.0,
                    "validation_test_count_min": 5.0,
                    "missing_validation_rate_max": 0.0,
                    "evidence_insufficient_rate_max": 0.0,
                },
                "failures": [
                    {
                        "metric": "precision_at_k",
                        "actual": 0.35,
                        "operator": ">=",
                        "expected": 0.4,
                    }
                ],
            },
        }
    )

    assert "## Validation-Rich Gate" in markdown
    assert "Passed: False" in markdown
    assert "Mode: report_only" in markdown
    assert "Enforced: False" in markdown
    assert "Summary: artifacts/benchmark/validation_rich/latest/summary.json" in markdown
    assert "task_success_rate>=0.9000" in markdown
    assert "validation_test_count>=5.0000" in markdown
    assert "precision_at_k: actual=0.35, expected >= 0.4" in markdown


def test_release_freeze_main_includes_validation_rich_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  validation_rich_gate:
    mode: report_only
    thresholds:
      task_success_rate_min: 0.90
      precision_at_k_min: 0.40
      noise_rate_max: 0.60
      latency_p95_ms_max: 700.0
      validation_test_count_min: 5.0
      missing_validation_rate_max: 0.0
      evidence_insufficient_rate_max: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "freeze-output"
    validation_summary = tmp_path / "validation-rich-summary.json"
    validation_summary.write_text(
        json.dumps(
            {
                "repo": "ace-lite-engine",
                "case_count": 5,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.425,
                    "noise_rate": 0.575,
                    "validation_test_count": 5.0,
                    "latency_p95_ms": 617.66,
                    "evidence_insufficient_rate": 0.0,
                    "missing_validation_rate": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 0,
                    "conflicts": 0,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
            "--validation-rich-summary",
            str(validation_summary),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert payload["validation_rich_gate"] == {
        "enabled": True,
        "passed": True,
        "mode": "report_only",
        "report_only": True,
        "enforced": False,
        "source": "config_mode",
        "summary_path": str(validation_summary.resolve()),
        "thresholds": {
            "task_success_rate_min": 0.9,
            "precision_at_k_min": 0.4,
            "noise_rate_max": 0.6,
            "latency_p95_ms_max": 700.0,
            "validation_test_count_min": 5.0,
            "missing_validation_rate_max": 0.0,
            "evidence_insufficient_rate_max": 0.0,
        },
        "failures": [],
    }


def test_release_freeze_main_fails_when_validation_rich_gate_enforced_and_thresholds_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  validation_rich_gate:
    mode: enforced
    thresholds:
      task_success_rate_min: 0.90
      precision_at_k_min: 0.40
      noise_rate_max: 0.60
      latency_p95_ms_max: 700.0
      validation_test_count_min: 5.0
      missing_validation_rate_max: 0.0
      evidence_insufficient_rate_max: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "freeze-output"
    validation_summary = tmp_path / "validation-rich-summary.json"
    validation_summary.write_text(
        json.dumps(
            {
                "repo": "ace-lite-engine",
                "case_count": 5,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 0.8,
                    "precision_at_k": 0.35,
                    "noise_rate": 0.65,
                    "validation_test_count": 4.0,
                    "latency_p95_ms": 710.0,
                    "evidence_insufficient_rate": 0.2,
                    "missing_validation_rate": 0.2,
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 0,
                    "conflicts": 0,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
            "--validation-rich-summary",
            str(validation_summary),
        ],
    )

    exit_code = module.main()
    assert exit_code == 1

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert payload["validation_rich_gate"]["enabled"] is True
    assert payload["validation_rich_gate"]["mode"] == "enforced"
    assert payload["validation_rich_gate"]["report_only"] is False
    assert payload["validation_rich_gate"]["enforced"] is True
    assert payload["validation_rich_gate"]["passed"] is False
    assert {
        failure["metric"] for failure in payload["validation_rich_gate"]["failures"]
    } == {
        "task_success_rate",
        "precision_at_k",
        "noise_rate",
        "latency_p95_ms",
        "validation_test_count",
        "missing_validation_rate",
        "evidence_insufficient_rate",
    }


def test_release_freeze_main_reports_only_when_validation_rich_gate_report_only_and_thresholds_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  validation_rich_gate:
    mode: report_only
    thresholds:
      task_success_rate_min: 0.90
      precision_at_k_min: 0.40
      noise_rate_max: 0.60
      latency_p95_ms_max: 700.0
      validation_test_count_min: 5.0
      missing_validation_rate_max: 0.0
      evidence_insufficient_rate_max: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "freeze-output"
    validation_summary = tmp_path / "validation-rich-summary.json"
    validation_summary.write_text(
        json.dumps(
            {
                "repo": "ace-lite-engine",
                "case_count": 5,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 0.8,
                    "precision_at_k": 0.35,
                    "noise_rate": 0.65,
                    "validation_test_count": 4.0,
                    "latency_p95_ms": 710.0,
                    "evidence_insufficient_rate": 0.2,
                    "missing_validation_rate": 0.2,
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 0,
                    "conflicts": 0,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
            "--validation-rich-summary",
            str(validation_summary),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["validation_rich_gate"]["enabled"] is True
    assert payload["validation_rich_gate"]["mode"] == "report_only"
    assert payload["validation_rich_gate"]["report_only"] is True
    assert payload["validation_rich_gate"]["enforced"] is False
    assert payload["validation_rich_gate"]["passed"] is False
    assert len(payload["validation_rich_gate"]["failures"]) == 7


def test_release_freeze_memory_gate_config_and_evaluation(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  memory_gate:
    min_notes_hit_ratio: 0.25
    min_profile_selected_mean: 0.50
    min_capture_trigger_ratio: 0.20
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_memory_gate_config(matrix_config_path=matrix_config)
    assert resolved == {
        "enabled": True,
        "source": "config",
        "thresholds": {
            "min_notes_hit_ratio": 0.25,
            "min_profile_selected_mean": 0.5,
            "min_capture_trigger_ratio": 0.2,
        },
    }

    failures = module._evaluate_memory_gate(
        matrix_summary={
            "memory_metrics_repos": [
                {
                    "name": "repo-a",
                    "notes_hit_ratio": 0.30,
                    "profile_selected_mean": 0.8,
                    "capture_trigger_ratio": 0.25,
                },
                {
                    "name": "repo-b",
                    "notes_hit_ratio": 0.10,
                    "profile_selected_mean": 0.4,
                    "capture_trigger_ratio": 0.15,
                },
            ]
        },
        min_notes_hit_ratio=0.25,
        min_profile_selected_mean=0.5,
        min_capture_trigger_ratio=0.2,
    )
    assert failures == [
        {
            "repo": "repo-b",
            "metric": "notes_hit_ratio",
            "actual": 0.1,
            "operator": ">=",
            "expected": 0.25,
        },
        {
            "repo": "repo-b",
            "metric": "profile_selected_mean",
            "actual": 0.4,
            "operator": ">=",
            "expected": 0.5,
        },
        {
            "repo": "repo-b",
            "metric": "capture_trigger_ratio",
            "actual": 0.15,
            "operator": ">=",
            "expected": 0.2,
        },
    ]


def test_release_freeze_main_includes_validation_rich_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text("", encoding="utf-8")
    output_dir = tmp_path / "freeze-output"
    validation_summary = tmp_path / "validation-rich-summary.json"
    validation_previous_summary = tmp_path / "validation-rich-previous-summary.json"
    validation_summary.write_text(
        json.dumps(
            {
                "repo": "ace-lite-engine",
                "case_count": 5,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.425,
                    "noise_rate": 0.575,
                    "validation_test_count": 5.0,
                    "latency_p95_ms": 617.66,
                    "evidence_insufficient_rate": 0.0,
                    "missing_validation_rate": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    validation_previous_summary.write_text(
        json.dumps(
            {
                "repo": "ace-lite-engine",
                "case_count": 5,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 0.8,
                    "precision_at_k": 0.35,
                    "noise_rate": 0.65,
                    "validation_test_count": 4.0,
                    "latency_p95_ms": 692.08,
                    "evidence_insufficient_rate": 0.2,
                    "missing_validation_rate": 0.2,
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return module.StepResult(
            name=name,
            command=command,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def fake_load_matrix_summary(*, summary_path: Path):
        _ = summary_path
        return {
            "passed": True,
            "benchmark_regression_detected": False,
            "repo_count": 1,
            "plugin_policy_summary": {
                "totals": {
                    "applied": 0,
                    "conflicts": 0,
                    "blocked": 0,
                    "warn": 0,
                    "remote_applied": 0,
                }
            },
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_load_matrix_summary", fake_load_matrix_summary)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_release_freeze_regression.py",
            "--matrix-config",
            str(matrix_config),
            "--output-dir",
            str(output_dir),
            "--skip-skill-validation",
            "--validation-rich-summary",
            str(validation_summary),
            "--validation-rich-previous-summary",
            str(validation_previous_summary),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads((output_dir / "freeze_regression.json").read_text(encoding="utf-8"))
    validation_payload = payload["validation_rich_benchmark"]
    assert validation_payload["enabled"] is True
    assert validation_payload["report_only"] is True
    assert validation_payload["summary_path"] == str(validation_summary.resolve())
    assert validation_payload["previous_summary_path"] == str(
        validation_previous_summary.resolve()
    )
    assert validation_payload["loaded"] is True
    assert validation_payload["previous_loaded"] is True
    assert validation_payload["repo"] == "ace-lite-engine"
    assert validation_payload["case_count"] == 5
    assert validation_payload["regressed"] is False
    assert validation_payload["previous_repo"] == "ace-lite-engine"
    assert validation_payload["previous_case_count"] == 5
    assert validation_payload["previous_regressed"] is False
    assert validation_payload["failed_checks"] == []
    assert validation_payload["previous_failed_checks"] == []
    assert validation_payload["metrics"] == {
        "task_success_rate": 1.0,
        "precision_at_k": 0.425,
        "noise_rate": 0.575,
        "validation_test_count": 5.0,
        "latency_p95_ms": 617.66,
        "evidence_insufficient_rate": 0.0,
        "missing_validation_rate": 0.0,
    }
    assert validation_payload["previous_metrics"] == {
        "task_success_rate": 0.8,
        "precision_at_k": 0.35,
        "noise_rate": 0.65,
        "validation_test_count": 4.0,
        "latency_p95_ms": 692.08,
        "evidence_insufficient_rate": 0.2,
        "missing_validation_rate": 0.2,
    }
    assert validation_payload["delta"]["task_success_rate"] == {
        "current": 1.0,
        "previous": 0.8,
        "delta": pytest.approx(0.2),
    }
    assert validation_payload["delta"]["precision_at_k"] == {
        "current": 0.425,
        "previous": 0.35,
        "delta": pytest.approx(0.075),
    }
    assert validation_payload["delta"]["noise_rate"] == {
        "current": 0.575,
        "previous": 0.65,
        "delta": pytest.approx(-0.075),
    }
    assert validation_payload["delta"]["latency_p95_ms"] == {
        "current": 617.66,
        "previous": 692.08,
        "delta": pytest.approx(-74.42),
    }
    assert validation_payload["delta"]["validation_test_count"] == {
        "current": 5.0,
        "previous": 4.0,
        "delta": 1.0,
    }
    assert validation_payload["delta"]["evidence_insufficient_rate"] == {
        "current": 0.0,
        "previous": 0.2,
        "delta": -0.2,
    }
    assert validation_payload["delta"]["missing_validation_rate"] == {
        "current": 0.0,
        "previous": 0.2,
        "delta": -0.2,
    }


def test_release_freeze_embedding_gate_config_and_evaluation(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  embedding_gate:
    min_embedding_enabled_ratio: 0.30
    min_embedding_similarity_mean: 0.20
    min_embedding_rerank_ratio: 0.40
    min_embedding_cache_hit_ratio: 0.30
    max_embedding_fallback_ratio: 0.10
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_embedding_gate_config(matrix_config_path=matrix_config)
    assert resolved == {
        "enabled": True,
        "source": "config",
        "thresholds": {
            "min_embedding_enabled_ratio": 0.3,
            "min_embedding_similarity_mean": 0.2,
            "min_embedding_rerank_ratio": 0.4,
            "min_embedding_cache_hit_ratio": 0.3,
            "max_embedding_fallback_ratio": 0.1,
        },
    }

    failures = module._evaluate_embedding_gate(
        matrix_summary={
            "embedding_metrics_repos": [
                {
                    "name": "repo-a",
                    "embedding_similarity_mean": 0.25,
                    "embedding_rerank_ratio": 0.5,
                    "embedding_cache_hit_ratio": 0.4,
                    "embedding_fallback_ratio": 0.05,
                },
                {
                    "name": "repo-b",
                    "embedding_similarity_mean": 0.1,
                    "embedding_rerank_ratio": 0.2,
                    "embedding_cache_hit_ratio": 0.1,
                    "embedding_fallback_ratio": 0.3,
                },
            ],
            "embedding_metrics_mean": {
                "embedding_enabled_ratio": 0.2,
            },
        },
        min_embedding_enabled_ratio=0.3,
        min_embedding_similarity_mean=0.2,
        min_embedding_rerank_ratio=0.4,
        min_embedding_cache_hit_ratio=0.3,
        max_embedding_fallback_ratio=0.1,
    )
    assert failures == [
        {
            "repo": "repo-b",
            "metric": "embedding_similarity_mean",
            "actual": 0.1,
            "operator": ">=",
            "expected": 0.2,
        },
        {
            "repo": "repo-b",
            "metric": "embedding_rerank_ratio",
            "actual": 0.2,
            "operator": ">=",
            "expected": 0.4,
        },
        {
            "repo": "repo-b",
            "metric": "embedding_cache_hit_ratio",
            "actual": 0.1,
            "operator": ">=",
            "expected": 0.3,
        },
        {
            "repo": "repo-b",
            "metric": "embedding_fallback_ratio",
            "actual": 0.3,
            "operator": "<=",
            "expected": 0.1,
        },
        {
            "repo": "matrix",
            "metric": "embedding_enabled_ratio",
            "actual": 0.2,
            "operator": ">=",
            "expected": 0.3,
            "source": "matrix_mean",
        },
    ]


def test_release_freeze_policy_guard_config_and_evaluation(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")
    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  policy_guard:
    mode: enforced
    max_regressed_repo_rate: 0.0
    min_task_success_mean: 0.80
    max_retrieval_task_gap_rate_mean: 0.25
    max_noise_rate_mean: 0.30
    max_latency_p95_ms_mean: 20.0
    max_slo_downgrade_case_rate_mean: 0.20
""".lstrip(),
        encoding="utf-8",
    )

    resolved = module._resolve_policy_guard_config(matrix_config_path=matrix_config)
    assert resolved == {
        "enabled": True,
        "mode": "enforced",
        "report_only": False,
        "enforced": True,
        "source": "config_mode",
        "thresholds": {
            "max_regressed_repo_rate": 0.0,
            "min_task_success_mean": 0.8,
            "max_retrieval_task_gap_rate_mean": 0.25,
            "max_noise_rate_mean": 0.3,
            "max_latency_p95_ms_mean": 20.0,
            "max_slo_downgrade_case_rate_mean": 0.2,
        },
    }

    failures = module._evaluate_retrieval_policy_guard(
        matrix_summary={
            "retrieval_policy_summary": [
                {
                    "retrieval_policy": "feature",
                    "regressed_repo_rate": 1.0,
                    "task_success_mean": 0.7,
                    "retrieval_task_gap_rate_mean": 0.4,
                    "noise_rate_mean": 0.35,
                    "latency_p95_ms_mean": 28.0,
                    "slo_downgrade_case_rate_mean": 0.25,
                },
                {
                    "retrieval_policy": "general",
                    "regressed_repo_rate": 0.0,
                    "task_success_mean": 0.92,
                    "retrieval_task_gap_rate_mean": 0.1,
                    "noise_rate_mean": 0.2,
                    "latency_p95_ms_mean": 14.0,
                    "slo_downgrade_case_rate_mean": 0.05,
                },
            ]
        },
        max_regressed_repo_rate=0.0,
        min_task_success_mean=0.8,
        max_retrieval_task_gap_rate_mean=0.25,
        max_noise_rate_mean=0.3,
        max_latency_p95_ms_mean=20.0,
        max_slo_downgrade_case_rate_mean=0.2,
    )

    assert failures == [
        {
            "policy": "feature",
            "metric": "regressed_repo_rate",
            "actual": 1.0,
            "operator": "<=",
            "expected": 0.0,
        },
        {
            "policy": "feature",
            "metric": "task_success_mean",
            "actual": 0.7,
            "operator": ">=",
            "expected": 0.8,
        },
        {
            "policy": "feature",
            "metric": "retrieval_task_gap_rate_mean",
            "actual": 0.4,
            "operator": "<=",
            "expected": 0.25,
        },
        {
            "policy": "feature",
            "metric": "noise_rate_mean",
            "actual": 0.35,
            "operator": "<=",
            "expected": 0.3,
        },
        {
            "policy": "feature",
            "metric": "latency_p95_ms_mean",
            "actual": 28.0,
            "operator": "<=",
            "expected": 20.0,
        },
        {
            "policy": "feature",
            "metric": "slo_downgrade_case_rate_mean",
            "actual": 0.25,
            "operator": "<=",
            "expected": 0.2,
        },
    ]


def test_release_freeze_policy_guard_can_disable_slo_downgrade_threshold() -> None:
    module = _load_script("run_release_freeze_regression.py")

    failures = module._evaluate_retrieval_policy_guard(
        matrix_summary={
            "retrieval_policy_summary": [
                {
                    "retrieval_policy": "auto",
                    "regressed_repo_rate": 0.0,
                    "task_success_mean": 1.0,
                    "retrieval_task_gap_rate_mean": 0.0,
                    "noise_rate_mean": 0.1,
                    "latency_p95_ms_mean": 18.0,
                    "slo_downgrade_case_rate_mean": 1.0,
                }
            ]
        },
        max_regressed_repo_rate=0.0,
        min_task_success_mean=0.8,
        max_retrieval_task_gap_rate_mean=0.25,
        max_noise_rate_mean=0.3,
        max_latency_p95_ms_mean=20.0,
        max_slo_downgrade_case_rate_mean=-1.0,
    )

    assert failures == []


def test_release_freeze_policy_guard_modes_and_legacy_enabled_flag(
    tmp_path: Path,
) -> None:
    module = _load_script("run_release_freeze_regression.py")

    disabled_config = tmp_path / "disabled.yaml"
    disabled_config.write_text(
        """
freeze:
  policy_guard:
    mode: disabled
    max_regressed_repo_rate: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    assert module._resolve_policy_guard_config(matrix_config_path=disabled_config) == {
        "enabled": False,
        "mode": "disabled",
        "report_only": False,
        "enforced": False,
        "source": "config_mode",
        "thresholds": {
            "max_regressed_repo_rate": 0.0,
            "min_task_success_mean": -1.0,
            "max_retrieval_task_gap_rate_mean": -1.0,
            "max_noise_rate_mean": -1.0,
            "max_latency_p95_ms_mean": -1.0,
            "max_slo_downgrade_case_rate_mean": -1.0,
        },
    }

    report_only_config = tmp_path / "report_only.yaml"
    report_only_config.write_text(
        """
freeze:
  policy_guard:
    mode: report_only
    max_regressed_repo_rate: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    assert module._resolve_policy_guard_config(
        matrix_config_path=report_only_config
    ) == {
        "enabled": True,
        "mode": "report_only",
        "report_only": True,
        "enforced": False,
        "source": "config_mode",
        "thresholds": {
            "max_regressed_repo_rate": 0.0,
            "min_task_success_mean": -1.0,
            "max_retrieval_task_gap_rate_mean": -1.0,
            "max_noise_rate_mean": -1.0,
            "max_latency_p95_ms_mean": -1.0,
            "max_slo_downgrade_case_rate_mean": -1.0,
        },
    }

    legacy_config = tmp_path / "legacy.yaml"
    legacy_config.write_text(
        """
freeze:
  policy_guard:
    enabled: true
    max_regressed_repo_rate: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    assert module._resolve_policy_guard_config(matrix_config_path=legacy_config) == {
        "enabled": True,
        "mode": "enforced",
        "report_only": False,
        "enforced": True,
        "source": "config_flag",
        "thresholds": {
            "max_regressed_repo_rate": 0.0,
            "min_task_success_mean": -1.0,
            "max_retrieval_task_gap_rate_mean": -1.0,
            "max_noise_rate_mean": -1.0,
            "max_latency_p95_ms_mean": -1.0,
            "max_slo_downgrade_case_rate_mean": -1.0,
        },
    }


def test_release_freeze_policy_guard_blocking_behavior_by_mode() -> None:
    module = _load_script("run_release_freeze_regression.py")
    failures = [{"policy": "feature", "metric": "task_success_mean"}]

    assert (
        module._policy_guard_blocks_release(
            config={"enabled": False, "mode": "disabled", "enforced": False},
            failures=failures,
        )
        is False
    )
    assert (
        module._policy_guard_blocks_release(
            config={"enabled": True, "mode": "report_only", "enforced": False},
            failures=failures,
        )
        is False
    )
    assert (
        module._policy_guard_blocks_release(
            config={"enabled": True, "mode": "enforced", "enforced": True},
            failures=failures,
        )
        is True
    )




def test_release_freeze_e2e_success_gate_evaluation() -> None:
    module = _load_script("run_release_freeze_regression.py")

    failures = module._evaluate_e2e_success_gate(
        matrix_summary={
            "task_success_repos": [
                {"name": "repo-a", "task_success_rate": 0.92},
                {"name": "repo-b", "task_success_rate": 0.65},
            ]
        },
        min_success_rate=0.8,
    )

    assert failures == [
        {
            "repo": "repo-b",
            "metric": "task_success_rate",
            "actual": 0.65,
            "operator": ">=",
            "expected": 0.8,
            "source": "benchmark_matrix",
        }
    ]


def test_release_freeze_resolve_e2e_success_gate(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")

    matrix_config = tmp_path / "matrix.yaml"
    matrix_config.write_text(
        """
freeze:
  e2e_success_floor: 0.88
""".lstrip(),
        encoding="utf-8",
    )

    resolved_from_config = module._resolve_e2e_success_gate(
        matrix_config_path=matrix_config,
        cli_success_floor=-1.0,
    )
    assert resolved_from_config == {
        "enabled": True,
        "source": "config",
        "min_success_rate": 0.88,
    }

    resolved_from_cli = module._resolve_e2e_success_gate(
        matrix_config_path=matrix_config,
        cli_success_floor=0.91,
    )
    assert resolved_from_cli == {
        "enabled": True,
        "source": "cli",
        "min_success_rate": 0.91,
    }


def test_release_freeze_e2e_success_gate_uses_e2e_summary() -> None:
    module = _load_script("run_release_freeze_regression.py")

    failures = module._evaluate_e2e_success_gate(
        matrix_summary={
            "task_success_repos": [
                {"name": "repo-a", "task_success_rate": 0.99},
            ]
        },
        min_success_rate=0.9,
        e2e_summary={
            "case_count": 3,
            "task_success_rate": 0.66,
        },
    )

    assert failures == [
        {
            "repo": "e2e_success_slice",
            "metric": "task_success_rate",
            "actual": 0.66,
            "operator": ">=",
            "expected": 0.9,
            "source": "e2e_success_slice",
        }
    ]


def test_release_freeze_load_e2e_success_summary(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")

    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "passed": True,
                "case_count": 5,
                "passed_count": 4,
                "failed_count": 1,
                "task_success_rate": 0.8,
                "failed_cases": [{"case_id": "c1", "reason": "validation_failed"}],
            }
        ),
        encoding="utf-8",
    )

    summary = module._load_e2e_success_summary(summary_path=summary_path)

    assert summary == {
        "path": str(summary_path),
        "passed": True,
        "case_count": 5,
        "passed_count": 4,
        "failed_count": 1,
        "task_success_rate": 0.8,
        "failed_cases": [{"case_id": "c1", "reason": "validation_failed"}],
    }


def test_release_freeze_load_benchmark_summary(tmp_path: Path) -> None:
    module = _load_script("run_release_freeze_regression.py")

    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "repo": "ace-lite-engine",
                "case_count": 4,
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "precision_at_k": 0.61,
                    "noise_rate": 0.39,
                    "latency_p95_ms": 132.0,
                },
            }
        ),
        encoding="utf-8",
    )

    summary = module._load_benchmark_summary(summary_path=summary_path)
    assert summary == {
        "path": str(summary_path),
        "repo": "ace-lite-engine",
        "case_count": 4,
        "regressed": False,
        "failed_checks": [],
        "metrics": {
            "precision_at_k": 0.61,
            "noise_rate": 0.39,
            "latency_p95_ms": 132.0,
        },
    }
