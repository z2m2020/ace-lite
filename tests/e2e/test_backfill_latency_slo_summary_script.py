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


def _build_stage_summary(*, total_p95: float, index_p95: float, repomap_p95: float) -> dict[str, dict[str, float]]:
    return {
        "memory": {"mean_ms": 0.05, "p95_ms": 0.06},
        "index": {"mean_ms": index_p95 - 1.0, "p95_ms": index_p95},
        "repomap": {"mean_ms": repomap_p95 - 0.2, "p95_ms": repomap_p95},
        "augment": {"mean_ms": 0.04, "p95_ms": 0.05},
        "skills": {"mean_ms": 2.5, "p95_ms": 2.8},
        "source_plan": {"mean_ms": 0.1, "p95_ms": 0.2},
        "total": {
            "mean_ms": total_p95 - 3.0,
            "median_ms": total_p95 - 2.0,
            "p95_ms": total_p95,
        },
    }


def _build_slo_summary(*, case_count: int, downgrade_case_count: int) -> dict[str, object]:
    return {
        "case_count": case_count,
        "budget_limits_ms": {
            "parallel_time_budget_ms_mean": 10.0,
            "embedding_time_budget_ms_mean": 50.0,
            "chunk_semantic_time_budget_ms_mean": 15.0,
            "xref_time_budget_ms_mean": 1500.0,
        },
        "downgrade_case_count": downgrade_case_count,
        "downgrade_case_rate": float(downgrade_case_count) / float(case_count),
        "signals": {
            "embedding_adaptive_budget_ratio": {
                "count": downgrade_case_count,
                "rate": float(downgrade_case_count) / float(case_count),
            }
        },
    }


def test_backfill_latency_slo_summary_main_materializes_outputs(tmp_path: Path) -> None:
    module = _load_script("backfill_latency_slo_summary.py")

    matrix_summary_path = tmp_path / "history" / "2026-03-06-release-readiness" / "matrix_summary.json"
    matrix_summary_path.parent.mkdir(parents=True, exist_ok=True)
    requests_dir = matrix_summary_path.parent / "requests"
    blockscout_dir = matrix_summary_path.parent / "blockscout-frontend"
    requests_dir.mkdir(parents=True, exist_ok=True)
    blockscout_dir.mkdir(parents=True, exist_ok=True)
    (requests_dir / "index.json").write_text(
        json.dumps({"file_count": 36}),
        encoding="utf-8",
    )
    (blockscout_dir / "index.json").write_text(
        json.dumps({"file_count": 2554}),
        encoding="utf-8",
    )
    matrix_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-06T10:11:39.644784+00:00",
                "matrix_config": "benchmark/matrix/repos.yaml",
                "repo_count": 2,
                "stage_latency_summary": _build_stage_summary(
                    total_p95=26.0,
                    index_p95=19.0,
                    repomap_p95=1.2,
                ),
                "slo_budget_summary": _build_slo_summary(
                    case_count=4,
                    downgrade_case_count=2,
                ),
                "repos": [
                    {
                        "name": "requests",
                        "retrieval_policy": "auto",
                        "summary_json": str(requests_dir / "summary.json"),
                        "stage_latency_summary": _build_stage_summary(
                            total_p95=12.0,
                            index_p95=8.5,
                            repomap_p95=1.0,
                        ),
                        "slo_budget_summary": _build_slo_summary(
                            case_count=2,
                            downgrade_case_count=1,
                        ),
                    },
                    {
                        "name": "blockscout-frontend",
                        "retrieval_policy": "auto",
                        "summary_json": str(blockscout_dir / "summary.json"),
                        "stage_latency_summary": _build_stage_summary(
                            total_p95=41.0,
                            index_p95=31.0,
                            repomap_p95=1.5,
                        ),
                        "slo_budget_summary": _build_slo_summary(
                            case_count=2,
                            downgrade_case_count=1,
                        ),
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    sys.argv = [
        "backfill_latency_slo_summary.py",
        "--matrix-summary",
        str(matrix_summary_path),
    ]
    exit_code = module.main()
    assert exit_code == 0

    payload = json.loads(
        (matrix_summary_path.parent / "latency_slo_summary.json").read_text(encoding="utf-8")
    )
    assert payload["generated_at"] == "2026-03-06T10:11:39.644784+00:00"
    assert payload["repo_count"] == 2
    assert payload["stage_latency_summary"]["total"]["p95_ms"] == 26.0
    assert payload["slo_budget_summary"]["downgrade_case_rate"] == 0.5
    assert [row["workload_bucket"] for row in payload["workload_buckets"]] == [
        "repo_size_small",
        "repo_size_large",
    ]

    markdown = (matrix_summary_path.parent / "latency_slo_summary.md").read_text(
        encoding="utf-8"
    )
    assert "# ACE-Lite Latency and SLO Summary" in markdown
    assert "### repo_size_small" in markdown
    assert "- Repo names: requests" in markdown
    assert "### repo_size_large" in markdown
    assert "- Repo names: blockscout-frontend" in markdown


def test_backfill_latency_slo_summary_main_rejects_incomplete_matrix_summary(
    tmp_path: Path,
) -> None:
    module = _load_script("backfill_latency_slo_summary.py")

    matrix_summary_path = tmp_path / "history" / "2026-02-25" / "matrix_summary.json"
    matrix_summary_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-02-25T14:43:00.038181+00:00",
                "repo_count": 5,
                "repos": [],
            }
        ),
        encoding="utf-8",
    )

    sys.argv = [
        "backfill_latency_slo_summary.py",
        "--matrix-summary",
        str(matrix_summary_path),
    ]
    exit_code = module.main()
    assert exit_code == 2
    assert not (matrix_summary_path.parent / "latency_slo_summary.json").exists()
