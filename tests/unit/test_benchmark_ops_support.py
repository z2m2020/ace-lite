from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from ace_lite.benchmark_ops import (
    CommandResult,
    load_yaml,
    read_benchmark_case_fingerprints,
    read_benchmark_case_routing_source,
    read_benchmark_case_rows,
    read_benchmark_comparison_lane_metrics,
    read_benchmark_retrieval_control_plane_gate_summary,
    read_benchmark_metrics,
    read_benchmark_results,
    require_success,
    run_command,
)


def test_benchmark_ops_facade_exports_match_support_module() -> None:
    module = importlib.import_module("ace_lite.benchmark_ops.support")

    assert CommandResult is module.CommandResult
    assert load_yaml is module.load_yaml
    assert read_benchmark_case_fingerprints is module.read_benchmark_case_fingerprints
    assert read_benchmark_case_routing_source is module.read_benchmark_case_routing_source
    assert read_benchmark_case_rows is module.read_benchmark_case_rows
    assert read_benchmark_comparison_lane_metrics is module.read_benchmark_comparison_lane_metrics
    assert (
        read_benchmark_retrieval_control_plane_gate_summary
        is module.read_benchmark_retrieval_control_plane_gate_summary
    )
    assert read_benchmark_metrics is module.read_benchmark_metrics
    assert read_benchmark_results is module.read_benchmark_results
    assert require_success is module.require_success
    assert run_command is module.run_command


def test_run_command_and_require_success_support_env_and_cwd(tmp_path: Path) -> None:
    script = (
        "import os, pathlib; "
        "print(pathlib.Path.cwd().name); "
        "print(os.environ['ACE_LITE_SAMPLE'])"
    )
    result = run_command(
        cmd=[sys.executable, "-c", script],
        cwd=tmp_path,
        env={"ACE_LITE_SAMPLE": "ok"},
    )

    require_success(result, label="sample")

    lines = result.stdout.strip().splitlines()
    assert result.returncode == 0
    assert result.cwd == str(tmp_path)
    assert lines == [tmp_path.name, "ok"]


def test_require_success_raises_runtime_error_with_details() -> None:
    result = CommandResult(
        cmd=["python", "-c", "raise SystemExit(2)"],
        cwd="repo",
        returncode=2,
        stdout="hello\n",
        stderr="boom\n",
    )

    with pytest.raises(RuntimeError) as excinfo:
        require_success(result, label="failing step")

    message = str(excinfo.value)
    assert "failing step failed with exit code 2" in message
    assert "cmd: python -c raise SystemExit(2)" in message
    assert "cwd: repo" in message
    assert "stdout:\nhello" in message
    assert "stderr:\nboom" in message


def test_load_yaml_returns_empty_for_missing_and_non_mapping_payloads(tmp_path: Path) -> None:
    assert load_yaml(tmp_path / "missing.yaml") == {}

    list_path = tmp_path / "list.yaml"
    list_path.write_text("- one\n- two\n", encoding="utf-8")
    assert load_yaml(list_path) == {}


def test_benchmark_readers_are_fail_open_and_normalize_results(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    assert read_benchmark_results(missing_path) == {}
    assert read_benchmark_metrics(missing_path) == {"task_success_rate": 0.0}
    assert read_benchmark_case_rows(missing_path) == {}
    assert read_benchmark_case_fingerprints(missing_path) == {}
    assert read_benchmark_case_routing_source(missing_path) == ""
    assert read_benchmark_comparison_lane_metrics(missing_path, lane="x") == {}
    assert read_benchmark_retrieval_control_plane_gate_summary(missing_path) == {}

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{", encoding="utf-8")
    assert read_benchmark_results(invalid_path) == {}

    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "utility_rate": 0.75,
    "precision_at_k": 0.5
  },
  "cases": [
    {
      "case_id": "case-1",
      "utility_hit": 1,
      "precision_at_k": 0.25,
      "noise_rate": 0.5,
      "dependency_recall": 0.75,
      "latency_ms": 9.87654321,
      "nested": {
        "model_latency_ms": 4.4444444,
        "score": 0.333333333
      },
      "plan": {
        "skills": {
          "routing_source": "precomputed"
        }
      }
    },
    {
      "case_id": "case-2",
      "task_success_hit": 0,
      "precision_at_k": 0.125,
      "noise_rate": 0.875,
      "comparison_lane": "same_stage",
      "plan": {
        "skills": {
          "routing_source": "same_stage"
        }
      }
    }
  ],
  "comparison_lane_summary": {
    "lanes": [
      {
        "comparison_lane": "same_stage",
        "task_success_rate": 0.5,
        "precision_at_k": "0.3125",
        "ignored": "x"
      }
    ]
  },
  "retrieval_control_plane_gate_summary": {
    "regression_evaluated": true,
    "benchmark_regression_detected": false,
    "benchmark_regression_passed": true,
    "failed_checks": [],
    "adaptive_router_shadow_coverage": 0.9,
    "adaptive_router_shadow_coverage_threshold": 0.8,
    "adaptive_router_shadow_coverage_passed": true,
    "risk_upgrade_precision_gain": 0.12,
    "risk_upgrade_precision_gain_threshold": 0.0,
    "risk_upgrade_precision_gain_passed": true,
    "latency_p95_ms": 640.0,
    "latency_p95_ms_threshold": 850.0,
    "latency_p95_ms_passed": true,
    "gate_passed": true
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_metrics(payload_path) == {
        "utility_rate": 0.75,
        "precision_at_k": 0.5,
        "task_success_rate": 0.75,
    }
    assert read_benchmark_case_rows(payload_path) == {
        "case-1": {
            "task_success_hit": 1.0,
            "precision_at_k": 0.25,
            "noise_rate": 0.5,
            "recall_hit": 0.0,
            "dependency_recall": 0.75,
        },
        "case-2": {
            "task_success_hit": 0.0,
            "precision_at_k": 0.125,
            "noise_rate": 0.875,
            "recall_hit": 0.0,
            "dependency_recall": 0.0,
        },
    }
    assert read_benchmark_case_fingerprints(payload_path) == {
        "case-1": {
            "case_id": "case-1",
            "dependency_recall": 0.75,
            "nested": {"score": 0.333333},
            "noise_rate": 0.5,
            "plan": {"skills": {"routing_source": "precomputed"}},
            "precision_at_k": 0.25,
            "utility_hit": 1,
        },
        "case-2": {
            "case_id": "case-2",
            "comparison_lane": "same_stage",
            "noise_rate": 0.875,
            "plan": {"skills": {"routing_source": "same_stage"}},
            "precision_at_k": 0.125,
            "task_success_hit": 0,
        },
    }
    assert read_benchmark_case_routing_source(payload_path) == "precomputed,same_stage"
    assert read_benchmark_comparison_lane_metrics(payload_path, lane="same_stage") == {
        "task_success_rate": 0.5,
        "precision_at_k": 0.3125,
    }
    assert read_benchmark_retrieval_control_plane_gate_summary(payload_path) == {
        "regression_evaluated": True,
        "benchmark_regression_detected": False,
        "benchmark_regression_passed": True,
        "failed_checks": [],
        "adaptive_router_shadow_coverage": 0.9,
        "adaptive_router_shadow_coverage_threshold": 0.8,
        "adaptive_router_shadow_coverage_passed": True,
        "risk_upgrade_precision_gain": 0.12,
        "risk_upgrade_precision_gain_threshold": 0.0,
        "risk_upgrade_precision_gain_passed": True,
        "latency_p95_ms": 640.0,
        "latency_p95_ms_threshold": 850.0,
        "latency_p95_ms_passed": True,
        "gate_passed": True,
    }
