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
    assert (
        captured["written_results"]["retrieval_control_plane_gate_summary"]
        == control_plane_gate_summary
    )
    assert (
        captured["written_results"]["retrieval_frontier_gate_summary"]
        == frontier_gate_summary
    )
    assert captured["written_results"]["runtime_stats_summary"] == {"enabled": True}
    assert captured["echoed_outputs"]["summary_json"].endswith("summary.json")
    assert results["retrieval_control_plane_gate_summary"] == control_plane_gate_summary
    assert results["retrieval_frontier_gate_summary"] == frontier_gate_summary
