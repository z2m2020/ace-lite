from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.cli_app.commands.benchmark_support import (
    attach_benchmark_runtime_stats_summary,
    run_benchmark_and_write_outputs,
)


def test_attach_benchmark_runtime_stats_summary_preserves_gate_summaries(
    monkeypatch: Any,
) -> None:
    control_plane_gate_summary = {
        "gate_passed": False,
        "failed_checks": ["latency_p95_ms"],
    }
    frontier_gate_summary = {
        "gate_passed": True,
        "failed_checks": [],
    }
    deep_symbol_summary = {
        "case_count": 2.0,
        "recall": 0.95,
    }
    native_scip_summary = {
        "loaded_rate": 0.8,
        "document_count_mean": 5.0,
        "definition_occurrence_count_mean": 7.0,
        "reference_occurrence_count_mean": 11.0,
        "symbol_definition_count_mean": 3.0,
    }
    repomap_seed_summary = {
        "worktree_seed_count_mean": 1.5,
        "subgraph_seed_count_mean": 2.5,
        "seed_candidates_count_mean": 3.5,
        "cache_hit_ratio": 0.75,
        "precompute_hit_ratio": 0.25,
    }
    validation_probe_summary = {
        "validation_test_count": 1.5,
        "probe_enabled_ratio": 1.0,
        "probe_executed_count_mean": 2.0,
        "probe_failure_rate": 0.5,
    }
    source_plan_validation_feedback_summary = {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
    }

    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark_support.load_runtime_stats_summary",
        lambda **_: {"enabled": True, "session_count": 1},
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark_support._load_durable_preference_capture_snapshot",
        lambda **_: {},
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark_support._record_benchmark_retrieval_preference_event",
        lambda **_: {},
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark_support._record_benchmark_packing_preference_event",
        lambda **_: {},
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark_support._record_benchmark_validation_preference_event",
        lambda **_: {},
    )

    orchestrator = type("FakeOrchestrator", (), {"_durable_stats_session_id": "sess-1"})()
    results = {
        "metrics": {"task_success_rate": 1.0},
        "retrieval_control_plane_gate_summary": control_plane_gate_summary,
        "retrieval_frontier_gate_summary": frontier_gate_summary,
        "deep_symbol_summary": deep_symbol_summary,
        "native_scip_summary": native_scip_summary,
        "repomap_seed_summary": repomap_seed_summary,
        "validation_probe_summary": validation_probe_summary,
        "source_plan_validation_feedback_summary": source_plan_validation_feedback_summary,
    }

    updated = attach_benchmark_runtime_stats_summary(
        results=results,
        orchestrator=orchestrator,
        repo="demo-repo",
        root=".",
        runtime_stats_enabled=True,
        runtime_stats_db_path="runtime_state.db",
        home_path=None,
        user_id=None,
        profile_key=None,
    )

    assert updated["retrieval_control_plane_gate_summary"] == control_plane_gate_summary
    assert updated["retrieval_frontier_gate_summary"] == frontier_gate_summary
    assert updated["deep_symbol_summary"] == deep_symbol_summary
    assert updated["native_scip_summary"] == native_scip_summary
    assert updated["repomap_seed_summary"] == repomap_seed_summary
    assert updated["validation_probe_summary"] == validation_probe_summary
    assert (
        updated["source_plan_validation_feedback_summary"]
        == source_plan_validation_feedback_summary
    )
    assert updated["runtime_stats_summary"] == {"enabled": True, "session_count": 1}
    assert "runtime_stats_summary" not in results


def test_run_benchmark_and_write_outputs_preserves_gate_summaries_for_writer() -> None:
    control_plane_gate_summary = {
        "gate_passed": False,
        "failed_checks": ["adaptive_router_shadow_coverage"],
    }
    frontier_gate_summary = {
        "gate_passed": True,
        "failed_checks": [],
    }
    deep_symbol_summary = {
        "case_count": 2.0,
        "recall": 0.95,
    }
    native_scip_summary = {
        "loaded_rate": 0.8,
        "document_count_mean": 5.0,
        "definition_occurrence_count_mean": 7.0,
        "reference_occurrence_count_mean": 11.0,
        "symbol_definition_count_mean": 3.0,
    }
    repomap_seed_summary = {
        "worktree_seed_count_mean": 1.5,
        "subgraph_seed_count_mean": 2.5,
        "seed_candidates_count_mean": 3.5,
        "cache_hit_ratio": 0.75,
        "precompute_hit_ratio": 0.25,
    }
    validation_probe_summary = {
        "validation_test_count": 1.5,
        "probe_enabled_ratio": 1.0,
        "probe_executed_count_mean": 2.0,
        "probe_failure_rate": 0.5,
    }
    source_plan_validation_feedback_summary = {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
    }
    captured: dict[str, Any] = {}

    class FakeRunner:
        def __init__(
            self,
            orchestrator: Any,
            *,
            reward_log_writer: Any,
            reward_log_enabled: bool,
            reward_log_path: str,
            reward_log_init_error: str,
        ) -> None:
            captured["runner_init"] = {
                "orchestrator": orchestrator,
                "reward_log_writer": reward_log_writer,
                "reward_log_enabled": reward_log_enabled,
                "reward_log_path": reward_log_path,
                "reward_log_init_error": reward_log_init_error,
            }

        def run(self, **kwargs: Any) -> dict[str, Any]:
            captured["runner_kwargs"] = kwargs
            return {
                "metrics": {"task_success_rate": 0.5},
                "retrieval_control_plane_gate_summary": control_plane_gate_summary,
                "retrieval_frontier_gate_summary": frontier_gate_summary,
                "deep_symbol_summary": deep_symbol_summary,
                "native_scip_summary": native_scip_summary,
                "repomap_seed_summary": repomap_seed_summary,
                "validation_probe_summary": validation_probe_summary,
                "source_plan_validation_feedback_summary": source_plan_validation_feedback_summary,
            }

    def fake_attach_runtime_stats_summary(**kwargs: Any) -> dict[str, Any]:
        results = dict(kwargs["results"])
        results["runtime_stats_summary"] = {"enabled": True}
        captured["attached_results"] = results
        return results

    def fake_write_results(results: dict[str, Any], *, output_dir: str) -> dict[str, str]:
        captured["written_results"] = results
        captured["output_dir"] = output_dir
        return {
            "results_json": str(Path(output_dir) / "results.json"),
            "report_md": str(Path(output_dir) / "report.md"),
            "summary_json": str(Path(output_dir) / "summary.json"),
        }

    def fake_echo_json(outputs: dict[str, str]) -> None:
        captured["echoed_outputs"] = outputs

    results = run_benchmark_and_write_outputs(
        orchestrator=object(),
        cases=[{"case_id": "case-1"}],
        repo="demo-repo",
        root=".",
        time_range=None,
        start_date=None,
        end_date=None,
        baseline_metrics=None,
        threshold_profile="default",
        threshold_overrides={},
        warmup_runs=0,
        include_plan_payload=False,
        include_case_details=False,
        reward_log_enabled=False,
        reward_log_path="reward-log.jsonl",
        runtime_stats_enabled=True,
        runtime_stats_db_path="runtime_state.db",
        home_path=None,
        user_id=None,
        profile_key=None,
        output_dir="artifacts/benchmark/latest",
        runner_cls=FakeRunner,
        reward_log_writer_cls=object,
        write_results_fn=fake_write_results,
        echo_json_fn=fake_echo_json,
        merge_reward_log_summary_fn=lambda *_args, **_kwargs: None,
        attach_runtime_stats_summary_fn=fake_attach_runtime_stats_summary,
    )

    assert captured["runner_kwargs"]["cases"] == [{"case_id": "case-1"}]
    assert (
        captured["attached_results"]["retrieval_control_plane_gate_summary"]
        == control_plane_gate_summary
    )
    assert (
        captured["attached_results"]["retrieval_frontier_gate_summary"]
        == frontier_gate_summary
    )
    assert captured["attached_results"]["deep_symbol_summary"] == deep_symbol_summary
    assert captured["attached_results"]["native_scip_summary"] == native_scip_summary
    assert captured["attached_results"]["repomap_seed_summary"] == repomap_seed_summary
    assert (
        captured["attached_results"]["validation_probe_summary"]
        == validation_probe_summary
    )
    assert (
        captured["attached_results"]["source_plan_validation_feedback_summary"]
        == source_plan_validation_feedback_summary
    )
    assert (
        captured["written_results"]["retrieval_control_plane_gate_summary"]
        == control_plane_gate_summary
    )
    assert (
        captured["written_results"]["retrieval_frontier_gate_summary"]
        == frontier_gate_summary
    )
    assert captured["written_results"]["deep_symbol_summary"] == deep_symbol_summary
    assert captured["written_results"]["native_scip_summary"] == native_scip_summary
    assert captured["written_results"]["repomap_seed_summary"] == repomap_seed_summary
    assert (
        captured["written_results"]["validation_probe_summary"]
        == validation_probe_summary
    )
    assert (
        captured["written_results"]["source_plan_validation_feedback_summary"]
        == source_plan_validation_feedback_summary
    )
    assert captured["written_results"]["runtime_stats_summary"] == {"enabled": True}
    assert captured["echoed_outputs"]["summary_json"].endswith("summary.json")
    assert results["retrieval_control_plane_gate_summary"] == control_plane_gate_summary
    assert results["retrieval_frontier_gate_summary"] == frontier_gate_summary
    assert results["deep_symbol_summary"] == deep_symbol_summary
    assert results["native_scip_summary"] == native_scip_summary
    assert results["repomap_seed_summary"] == repomap_seed_summary
    assert results["validation_probe_summary"] == validation_probe_summary
    assert (
        results["source_plan_validation_feedback_summary"]
        == source_plan_validation_feedback_summary
    )
