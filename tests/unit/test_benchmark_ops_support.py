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
    read_benchmark_deep_symbol_summary,
    read_benchmark_metrics,
    read_benchmark_native_scip_summary,
    read_benchmark_repomap_seed_summary,
    read_benchmark_results,
    read_benchmark_retrieval_control_plane_gate_summary,
    read_benchmark_retrieval_frontier_gate_summary,
    read_benchmark_source_plan_failure_signal_summary,
    read_benchmark_source_plan_validation_feedback_summary,
    read_benchmark_validation_probe_summary,
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
    assert read_benchmark_deep_symbol_summary is module.read_benchmark_deep_symbol_summary
    assert read_benchmark_native_scip_summary is module.read_benchmark_native_scip_summary
    assert (
        read_benchmark_retrieval_control_plane_gate_summary
        is module.read_benchmark_retrieval_control_plane_gate_summary
    )
    assert (
        read_benchmark_retrieval_frontier_gate_summary
        is module.read_benchmark_retrieval_frontier_gate_summary
    )
    assert read_benchmark_repomap_seed_summary is module.read_benchmark_repomap_seed_summary
    assert (
        read_benchmark_source_plan_failure_signal_summary
        is module.read_benchmark_source_plan_failure_signal_summary
    )
    assert (
        read_benchmark_source_plan_validation_feedback_summary
        is module.read_benchmark_source_plan_validation_feedback_summary
    )
    assert (
        read_benchmark_validation_probe_summary
        is module.read_benchmark_validation_probe_summary
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
    assert read_benchmark_deep_symbol_summary(missing_path) == {}
    assert read_benchmark_native_scip_summary(missing_path) == {}
    assert read_benchmark_retrieval_control_plane_gate_summary(missing_path) == {}
    assert read_benchmark_retrieval_frontier_gate_summary(missing_path) == {}
    assert read_benchmark_repomap_seed_summary(missing_path) == {}
    assert read_benchmark_source_plan_failure_signal_summary(missing_path) == {}
    assert read_benchmark_source_plan_validation_feedback_summary(missing_path) == {}
    assert read_benchmark_validation_probe_summary(missing_path) == {}

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
  },
  "retrieval_frontier_gate_summary": {
    "failed_checks": ["precision_at_k"],
    "deep_symbol_case_recall": 0.95,
    "deep_symbol_case_recall_threshold": 0.9,
    "deep_symbol_case_recall_passed": true,
    "native_scip_loaded_rate": 0.8,
    "native_scip_loaded_rate_threshold": 0.7,
    "native_scip_loaded_rate_passed": true,
    "precision_at_k": 0.61,
    "precision_at_k_threshold": 0.64,
    "precision_at_k_passed": false,
    "noise_rate": 0.31,
    "noise_rate_threshold": 0.36,
    "noise_rate_passed": true,
    "gate_passed": false
  },
  "deep_symbol_summary": {
    "case_count": 2,
    "recall": 0.95
  },
  "native_scip_summary": {
    "loaded_rate": 0.8,
    "document_count_mean": 5,
    "definition_occurrence_count_mean": 7,
    "reference_occurrence_count_mean": 11,
    "symbol_definition_count_mean": 3
  },
  "repomap_seed_summary": {
    "worktree_seed_count_mean": 4,
    "repomap_subgraph_seed_count_mean": 3.5,
    "seed_candidates_count_mean": 6,
    "cache_hit_ratio": 0.5,
    "repomap_precompute_hit_ratio": 0.25
  },
  "validation_probe_summary": {
    "validation_test_count": 1.5,
    "probe_enabled_ratio": 1,
    "probe_executed_count_mean": 2,
    "probe_failure_rate": 0.5
  },
  "source_plan_validation_feedback_summary": {
    "present_ratio": 1,
    "issue_count_mean": 2,
    "failure_rate": 1,
    "probe_issue_count_mean": 1,
    "probe_executed_count_mean": 1,
    "probe_failure_rate": 1,
    "selected_test_count_mean": 1,
    "executed_test_count_mean": 1
  },
  "source_plan_failure_signal_summary": {
    "present_ratio": 1,
    "issue_count_mean": 2,
    "failure_rate": 1,
    "probe_issue_count_mean": 1,
    "probe_executed_count_mean": 1,
    "probe_failure_rate": 1,
    "selected_test_count_mean": 1,
    "executed_test_count_mean": 1,
    "replay_cache_origin_ratio": 1,
    "observability_origin_ratio": 0,
    "source_plan_origin_ratio": 0,
    "validate_step_origin_ratio": 0
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
    assert read_benchmark_retrieval_frontier_gate_summary(payload_path) == {
        "failed_checks": ["precision_at_k"],
        "deep_symbol_case_recall": 0.95,
        "deep_symbol_case_recall_threshold": 0.9,
        "deep_symbol_case_recall_passed": True,
        "native_scip_loaded_rate": 0.8,
        "native_scip_loaded_rate_threshold": 0.7,
        "native_scip_loaded_rate_passed": True,
        "precision_at_k": 0.61,
        "precision_at_k_threshold": 0.64,
        "precision_at_k_passed": False,
        "noise_rate": 0.31,
        "noise_rate_threshold": 0.36,
        "noise_rate_passed": True,
        "gate_passed": False,
    }
    assert read_benchmark_deep_symbol_summary(payload_path) == {
        "case_count": 2.0,
        "recall": 0.95,
    }
    assert read_benchmark_native_scip_summary(payload_path) == {
        "loaded_rate": 0.8,
        "document_count_mean": 5.0,
        "definition_occurrence_count_mean": 7.0,
        "reference_occurrence_count_mean": 11.0,
        "symbol_definition_count_mean": 3.0,
    }
    assert read_benchmark_repomap_seed_summary(payload_path) == {
        "worktree_seed_count_mean": 4.0,
        "subgraph_seed_count_mean": 3.5,
        "seed_candidates_count_mean": 6.0,
        "cache_hit_ratio": 0.5,
        "precompute_hit_ratio": 0.25,
    }
    assert read_benchmark_validation_probe_summary(payload_path) == {
        "validation_test_count": 1.5,
        "probe_enabled_ratio": 1.0,
        "probe_executed_count_mean": 2.0,
        "probe_failure_rate": 0.5,
    }
    assert read_benchmark_source_plan_validation_feedback_summary(payload_path) == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
    }
    assert read_benchmark_source_plan_failure_signal_summary(payload_path) == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
        "replay_cache_origin_ratio": 1.0,
        "observability_origin_ratio": 0.0,
        "source_plan_origin_ratio": 0.0,
        "validate_step_origin_ratio": 0.0,
    }


def test_read_benchmark_repomap_seed_summary_prefers_top_level_summary_over_metrics(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "repomap_worktree_seed_count_mean": 1,
    "repomap_subgraph_seed_count_mean": 2,
    "repomap_seed_candidates_count_mean": 3,
    "repomap_cache_hit_ratio": 0.1,
    "repomap_precompute_hit_ratio": 0.2
  },
  "repomap_seed_summary": {
    "worktree_seed_count_mean": 4,
    "subgraph_seed_count_mean": 5,
    "seed_candidates_count_mean": 6,
    "cache_hit_ratio": 0.7,
    "precompute_hit_ratio": 0.8
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_repomap_seed_summary(payload_path) == {
        "worktree_seed_count_mean": 4.0,
        "subgraph_seed_count_mean": 5.0,
        "seed_candidates_count_mean": 6.0,
        "cache_hit_ratio": 0.7,
        "precompute_hit_ratio": 0.8,
    }


def test_read_benchmark_deep_symbol_summary_prefers_top_level_summary_over_metrics(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "deep_symbol_case_count": 1,
    "deep_symbol_case_recall": 0.4
  },
  "deep_symbol_summary": {
    "case_count": 2,
    "recall": 0.95
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_deep_symbol_summary(payload_path) == {
        "case_count": 2.0,
        "recall": 0.95,
    }


def test_read_benchmark_validation_probe_summary_prefers_top_level_summary_over_metrics(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "validation_test_count": 0.25,
    "validation_probe_enabled_ratio": 0.1,
    "validation_probe_executed_count_mean": 1,
    "validation_probe_failure_rate": 0.9
  },
  "validation_probe_summary": {
    "validation_test_count": 1.5,
    "probe_enabled_ratio": 1,
    "probe_executed_count_mean": 2,
    "probe_failure_rate": 0.5
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_validation_probe_summary(payload_path) == {
        "validation_test_count": 1.5,
        "probe_enabled_ratio": 1.0,
        "probe_executed_count_mean": 2.0,
        "probe_failure_rate": 0.5,
    }


def test_read_benchmark_source_plan_validation_feedback_summary_prefers_top_level_summary_over_metrics(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "source_plan_validation_feedback_present_ratio": 0.0,
    "source_plan_validation_feedback_issue_count_mean": 0.5,
    "source_plan_validation_feedback_failure_rate": 0.5,
    "source_plan_validation_feedback_probe_issue_count_mean": 0.25,
    "source_plan_validation_feedback_probe_executed_count_mean": 0.25,
    "source_plan_validation_feedback_probe_failure_rate": 0.5,
    "source_plan_validation_feedback_selected_test_count_mean": 0.25,
    "source_plan_validation_feedback_executed_test_count_mean": 0.25
  },
  "source_plan_validation_feedback_summary": {
    "present_ratio": 1,
    "issue_count_mean": 2,
    "failure_rate": 1,
    "probe_issue_count_mean": 1,
    "probe_executed_count_mean": 1,
    "probe_failure_rate": 1,
    "selected_test_count_mean": 1,
    "executed_test_count_mean": 1
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_source_plan_validation_feedback_summary(payload_path) == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
    }


def test_read_benchmark_source_plan_failure_signal_summary_prefers_top_level_summary_over_metrics(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "source_plan_failure_signal_present_ratio": 0.0,
    "source_plan_failure_signal_issue_count_mean": 0.5,
    "source_plan_failure_signal_failure_rate": 0.5,
    "source_plan_failure_signal_probe_issue_count_mean": 0.25,
    "source_plan_failure_signal_probe_executed_count_mean": 0.25,
    "source_plan_failure_signal_probe_failure_rate": 0.5,
    "source_plan_failure_signal_selected_test_count_mean": 0.25,
    "source_plan_failure_signal_executed_test_count_mean": 0.25,
    "source_plan_failure_signal_replay_cache_origin_ratio": 0.0,
    "source_plan_failure_signal_observability_origin_ratio": 1.0,
    "source_plan_failure_signal_source_plan_origin_ratio": 0.0,
    "source_plan_failure_signal_validate_step_origin_ratio": 0.0
  },
  "source_plan_failure_signal_summary": {
    "present_ratio": 1,
    "issue_count_mean": 2,
    "failure_rate": 1,
    "probe_issue_count_mean": 1,
    "probe_executed_count_mean": 1,
    "probe_failure_rate": 1,
    "selected_test_count_mean": 1,
    "executed_test_count_mean": 1,
    "replay_cache_origin_ratio": 1,
    "observability_origin_ratio": 0,
    "source_plan_origin_ratio": 0,
    "validate_step_origin_ratio": 0
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_source_plan_failure_signal_summary(payload_path) == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
        "replay_cache_origin_ratio": 1.0,
        "observability_origin_ratio": 0.0,
        "source_plan_origin_ratio": 0.0,
        "validate_step_origin_ratio": 0.0,
    }


def test_read_benchmark_native_scip_summary_prefers_top_level_summary_over_metrics(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "results.json"
    payload_path.write_text(
        """
{
  "metrics": {
    "native_scip_loaded_rate": 0.1,
    "native_scip_document_count_mean": 1,
    "native_scip_definition_occurrence_count_mean": 2,
    "native_scip_reference_occurrence_count_mean": 3,
    "native_scip_symbol_definition_count_mean": 4
  },
  "native_scip_summary": {
    "loaded_rate": 0.8,
    "document_count_mean": 5,
    "definition_occurrence_count_mean": 7,
    "reference_occurrence_count_mean": 11,
    "symbol_definition_count_mean": 3
  }
}
""".strip(),
        encoding="utf-8",
    )

    assert read_benchmark_native_scip_summary(payload_path) == {
        "loaded_rate": 0.8,
        "document_count_mean": 5.0,
        "definition_occurrence_count_mean": 7.0,
        "reference_occurrence_count_mean": 11.0,
        "symbol_definition_count_mean": 3.0,
    }
