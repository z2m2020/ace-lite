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


def _write_latency_slo_summary(
    path: Path,
    *,
    generated_at: str,
    total_p95: float,
    index_p95: float,
    repomap_p95: float,
    downgrade_case_rate: float,
    adaptive_budget_rate: float,
    small_total_p95: float,
    large_total_p95: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": generated_at,
        "repo_count": 2,
        "stage_latency_summary": {
            "memory": {"mean_ms": 0.05, "p95_ms": 0.06},
            "index": {"mean_ms": index_p95 - 2.0, "p95_ms": index_p95},
            "repomap": {"mean_ms": repomap_p95 - 0.2, "p95_ms": repomap_p95},
            "augment": {"mean_ms": 0.04, "p95_ms": 0.05},
            "skills": {"mean_ms": 3.5, "p95_ms": 3.9},
            "source_plan": {"mean_ms": 0.1, "p95_ms": 0.2},
            "total": {"mean_ms": total_p95 - 4.0, "median_ms": total_p95 - 3.0, "p95_ms": total_p95},
        },
                "slo_budget_summary": {
                    "case_count": 10,
                    "downgrade_case_count": round(downgrade_case_rate * 10),
                    "downgrade_case_rate": downgrade_case_rate,
                    "signals": {
                        "embedding_adaptive_budget_ratio": {
                            "count": round(adaptive_budget_rate * 10),
                            "rate": adaptive_budget_rate,
                        }
                    },
        },
        "workload_buckets": [
            {
                "workload_bucket": "repo_size_small",
                "repo_count": 1,
                "repo_names": ["requests"],
                "file_count_mean": 36.0,
                "stage_latency_summary": {
                    "memory": {"mean_ms": 0.05, "p95_ms": 0.05},
                    "index": {"mean_ms": small_total_p95 - 6.0, "p95_ms": small_total_p95 - 4.0},
                    "repomap": {"mean_ms": 1.0, "p95_ms": 1.1},
                    "augment": {"mean_ms": 0.04, "p95_ms": 0.05},
                    "skills": {"mean_ms": 3.0, "p95_ms": 3.2},
                    "source_plan": {"mean_ms": 0.1, "p95_ms": 0.2},
                    "total": {"mean_ms": small_total_p95 - 3.0, "median_ms": small_total_p95 - 2.0, "p95_ms": small_total_p95},
                },
                "slo_budget_summary": {
                    "case_count": 5,
                    "downgrade_case_count": round(downgrade_case_rate * 5),
                    "downgrade_case_rate": downgrade_case_rate,
                },
            },
            {
                "workload_bucket": "repo_size_large",
                "repo_count": 1,
                "repo_names": ["blockscout-frontend"],
                "file_count_mean": 2554.0,
                "stage_latency_summary": {
                    "memory": {"mean_ms": 0.05, "p95_ms": 0.05},
                    "index": {"mean_ms": large_total_p95 - 8.0, "p95_ms": large_total_p95 - 5.0},
                    "repomap": {"mean_ms": 1.4, "p95_ms": 1.6},
                    "augment": {"mean_ms": 0.04, "p95_ms": 0.05},
                    "skills": {"mean_ms": 3.8, "p95_ms": 4.0},
                    "source_plan": {"mean_ms": 0.1, "p95_ms": 0.2},
                    "total": {"mean_ms": large_total_p95 - 3.0, "median_ms": large_total_p95 - 2.0, "p95_ms": large_total_p95},
                },
                "slo_budget_summary": {
                    "case_count": 5,
                    "downgrade_case_count": round(downgrade_case_rate * 5),
                    "downgrade_case_rate": downgrade_case_rate,
                },
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_latency_slo_trend_report_main_writes_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_latency_slo_trend_report.py")

    history_root = tmp_path / "history"
    report_a = history_root / "2026-02-25" / "latency_slo_summary.json"
    report_b = history_root / "2026-03-06" / "latency_slo_summary.json"

    _write_latency_slo_summary(
        report_a,
        generated_at="2026-02-25T00:00:00+00:00",
        total_p95=24.0,
        index_p95=18.0,
        repomap_p95=1.0,
        downgrade_case_rate=0.8,
        adaptive_budget_rate=0.8,
        small_total_p95=16.0,
        large_total_p95=38.0,
    )
    _write_latency_slo_summary(
        report_b,
        generated_at="2026-03-06T00:00:00+00:00",
        total_p95=30.0,
        index_p95=24.0,
        repomap_p95=1.3,
        downgrade_case_rate=1.0,
        adaptive_budget_rate=1.0,
        small_total_p95=18.5,
        large_total_p95=46.0,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="scripts/build_latency_slo_trend_report.py\ndocs/maintainers/BENCHMARKING.md\n",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_latency_slo_trend_report.py",
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

    output = json.loads(
        (tmp_path / "trend" / "latency_slo_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["report_only"] is True
    assert output["history_count"] == 2
    assert output["latest"]["downgrade_case_rate"] == pytest.approx(1.0)
    assert output["previous"]["downgrade_case_rate"] == pytest.approx(0.8)
    assert output["delta"]["stage_p95_ms"]["total"] == pytest.approx(6.0)
    assert output["delta"]["stage_p95_ms"]["index"] == pytest.approx(6.0)
    assert output["delta"]["downgrade_case_rate"] == pytest.approx(0.2)
    assert output["bucket_deltas"] == [
        {
            "workload_bucket": "repo_size_large",
            "latest_repo_count": 1,
            "previous_repo_count": 1,
            "latest_file_count_mean": 2554.0,
            "previous_file_count_mean": 2554.0,
            "stage_p95_delta_ms": {
                "memory": 0.0,
                "index": 8.0,
                "repomap": 0.0,
                "augment": 0.0,
                "skills": 0.0,
                "source_plan": 0.0,
                "total": 8.0,
            },
            "downgrade_case_rate_delta": pytest.approx(0.2),
        },
        {
            "workload_bucket": "repo_size_small",
            "latest_repo_count": 1,
            "previous_repo_count": 1,
            "latest_file_count_mean": 36.0,
            "previous_file_count_mean": 36.0,
            "stage_p95_delta_ms": {
                "memory": 0.0,
                "index": 2.5,
                "repomap": 0.0,
                "augment": 0.0,
                "skills": 0.0,
                "source_plan": 0.0,
                "total": 2.5,
            },
            "downgrade_case_rate_delta": pytest.approx(0.2),
        },
    ]
    assert output["suspect_files"] == [
        "scripts/build_latency_slo_trend_report.py",
        "docs/maintainers/BENCHMARKING.md",
    ]

    markdown = (tmp_path / "trend" / "latency_slo_trend_report.md").read_text(
        encoding="utf-8"
    )
    assert "- Report only: True" in markdown
    assert "## Bucket Deltas" in markdown
    assert "| repo_size_small | 1 | 1 | +2.50 | +2.50 | +0.00 | +0.2000 |" in markdown
    assert "scripts/build_latency_slo_trend_report.py" in markdown


def test_latency_slo_trend_report_prefers_generated_at_over_file_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("build_latency_slo_trend_report.py")

    history_root = tmp_path / "history"
    newer_path = history_root / "2026-03-06" / "latency_slo_summary.json"
    older_path = history_root / "2026-02-25" / "latency_slo_summary.json"

    _write_latency_slo_summary(
        newer_path,
        generated_at="2026-03-06T00:00:00+00:00",
        total_p95=30.0,
        index_p95=24.0,
        repomap_p95=1.3,
        downgrade_case_rate=1.0,
        adaptive_budget_rate=1.0,
        small_total_p95=18.5,
        large_total_p95=46.0,
    )
    _write_latency_slo_summary(
        older_path,
        generated_at="2026-02-25T00:00:00+00:00",
        total_p95=24.0,
        index_p95=18.0,
        repomap_p95=1.0,
        downgrade_case_rate=0.8,
        adaptive_budget_rate=0.8,
        small_total_p95=16.0,
        large_total_p95=38.0,
    )

    def fake_git_diff(cmd, cwd, check, capture_output, text):
        _ = (cmd, cwd, check, capture_output, text)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_git_diff)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "build_latency_slo_trend_report.py",
            "--history-root",
            str(history_root),
            "--output-dir",
            str(tmp_path / "trend"),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(
        (tmp_path / "trend" / "latency_slo_trend_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["latest"]["generated_at"] == "2026-03-06T00:00:00+00:00"
    assert output["previous"]["generated_at"] == "2026-02-25T00:00:00+00:00"
    assert output["delta"]["stage_p95_ms"]["total"] == pytest.approx(6.0)
