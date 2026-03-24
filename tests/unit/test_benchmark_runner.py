from __future__ import annotations

import json
from pathlib import Path

import yaml

from ace_lite.benchmark.runner import BenchmarkRunner
from ace_lite.benchmark.runner import load_baseline_metrics
from ace_lite.benchmark.runner import load_cases


class _StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        self.calls.append((query, repo, root))
        return {
            "index": {"candidate_files": [{"path": "src/app.py", "module": "src.app"}]},
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
            "observability": {
                "plugin_policy_summary": {
                    "mode": "strict",
                    "allowlist": ["observability.mcp_plugins"],
                    "totals": {
                        "applied": 0,
                        "conflicts": 0,
                        "blocked": 0,
                        "warn": 0,
                        "remote_applied": 0,
                    },
                }
            },
        }


def test_benchmark_runner_warmup_runs_are_excluded_from_case_count() -> None:
    orchestrator = _StubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
        {"case_id": "c2", "query": "find src", "expected_keys": ["src"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".", warmup_runs=2)

    assert results["case_count"] == 2
    assert results["warmup_runs"] == 2
    assert results["warmup_plan_calls"] == 4
    assert len(orchestrator.calls) == 6


def test_load_baseline_metrics_preserves_full_metric_contract_from_summary_json(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "hit_at_1": 0.75,
                    "mrr": 0.88,
                    "skills_route_latency_p95_ms": 1.2,
                    "retrieval_context_chunk_count_mean": 13.5,
                    "retrieval_context_coverage_ratio": 1.0,
                    "contextual_sidecar_parent_symbol_chunk_count_mean": 4.5,
                    "contextual_sidecar_parent_symbol_coverage_ratio": 0.3,
                    "contextual_sidecar_reference_hint_chunk_count_mean": 10.0,
                    "contextual_sidecar_reference_hint_coverage_ratio": 0.8,
                    "robust_signature_count_mean": 13.5,
                    "task_success_rate": 1.0,
                    "utility_rate": 1.0,
                }
            }
        ),
        encoding="utf-8",
    )

    metrics = load_baseline_metrics(summary_path)

    assert metrics is not None
    assert metrics["hit_at_1"] == 0.75
    assert metrics["mrr"] == 0.88
    assert metrics["skills_route_latency_p95_ms"] == 1.2
    assert metrics["retrieval_context_chunk_count_mean"] == 13.5
    assert metrics["retrieval_context_coverage_ratio"] == 1.0
    assert metrics["contextual_sidecar_parent_symbol_chunk_count_mean"] == 4.5
    assert metrics["contextual_sidecar_parent_symbol_coverage_ratio"] == 0.3
    assert metrics["contextual_sidecar_reference_hint_chunk_count_mean"] == 10.0
    assert metrics["contextual_sidecar_reference_hint_coverage_ratio"] == 0.8
    assert metrics["robust_signature_count_mean"] == 13.5


def test_load_cases_normalizes_feedback_loop_metadata(tmp_path: Path) -> None:
    cases_path = tmp_path / "benchmark" / "cases.yaml"
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(
        yaml.safe_dump(
            {
                "cases": [
                    {
                        "case_id": "issue-derived",
                        "query": "issue export",
                        "expected_keys": ["issue"],
                        "top_k": 8,
                        "issue_report": {
                            "status": "resolved",
                            "occurred_at": "2026-03-19T00:00:00+00:00",
                            "resolved_at": "2026-03-19T00:05:00+00:00",
                            "attachments": [
                                "artifact://validation.json",
                                "dev-fix://devf_demo1234",
                            ],
                        },
                    },
                    {
                        "case_id": "runtime-derived",
                        "query": "runtime capture",
                        "expected_keys": ["runtime"],
                        "top_k": 8,
                        "comparison_lane": "dev_issue_capture",
                        "feedback_surface": "runtime_issue_capture_cli",
                        "issue_report": {
                            "occurred_at": "2026-03-19T01:00:00+00:00",
                        },
                    },
                    {
                        "case_id": "resolution-derived",
                        "query": "issue resolution",
                        "expected_keys": ["resolution"],
                        "top_k": 8,
                        "comparison_lane": "dev_feedback_resolution",
                        "feedback_surface": "issue_resolution_cli",
                        "issue_report": {
                            "status": "resolved",
                            "occurred_at": "2026-03-19T02:00:00+00:00",
                            "resolved_at": "2026-03-19T03:30:00+00:00",
                        },
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    cases = load_cases(cases_path)

    assert cases[0]["dev_feedback"] == {
        "issue_count": 1,
        "linked_fix_issue_count": 1,
        "resolved_issue_count": 1,
        "created_at": "2026-03-19T00:00:00+00:00",
        "resolved_at": "2026-03-19T00:05:00+00:00",
    }
    assert cases[1]["dev_feedback"] == {
        "issue_count": 1,
        "created_at": "2026-03-19T01:00:00+00:00",
    }
    assert cases[2]["dev_feedback"] == {
        "issue_count": 1,
        "linked_fix_issue_count": 1,
        "resolved_issue_count": 1,
        "created_at": "2026-03-19T02:00:00+00:00",
        "resolved_at": "2026-03-19T03:30:00+00:00",
    }


def test_benchmark_runner_can_omit_plan_payloads() -> None:
    orchestrator = _StubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(
        cases=cases,
        repo="demo",
        root=".",
        include_plan_payload=False,
    )

    assert results["include_plan_payload"] is False
    assert len(results["cases"]) == 1
    assert "plan" not in results["cases"][0]
    assert results["task_success_summary"]["case_count"] == 1
    assert results["task_success_summary"]["task_success_rate"] == 1.0
    assert results["evidence_insufficiency_summary"] == {
        "case_count": 1,
        "applicable_case_count": 0,
        "excluded_negative_control_case_count": 0,
        "evidence_insufficient_count": 0,
        "evidence_insufficient_rate": 0.0,
        "reasons": {},
        "signals": {},
    }
    assert results["chunk_stage_miss_summary"] == {
        "case_count": 1,
        "oracle_case_count": 0,
        "classified_case_count": 0,
        "classified_case_rate": 0.0,
        "labels": {},
    }


def test_benchmark_runner_can_omit_case_details() -> None:
    orchestrator = _StubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(
        cases=cases,
        repo="demo",
        root=".",
        include_case_details=False,
    )

    assert results["include_case_details"] is False
    assert len(results["cases"]) == 1
    case_payload = results["cases"][0]
    assert "candidate_paths" not in case_payload
    assert "candidate_chunk_refs" not in case_payload
    assert "expected_hits" not in case_payload
    assert "chunk_hits" not in case_payload
    assert "validation_tests" not in case_payload


def test_benchmark_runner_emits_agent_loop_control_plane_summary() -> None:
    class _AgentLoopStubOrchestrator:
        def plan(self, **kwargs) -> dict[str, object]:
            return {
                "index": {
                    "candidate_files": [{"path": "src/app.py", "module": "src.app"}]
                },
                "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
                "repomap": {"dependency_recall": {"hit_rate": 1.0}},
                "observability": {
                    "agent_loop": {
                        "enabled": True,
                        "attempted": True,
                        "actions_requested": 1,
                        "actions_executed": 1,
                        "stop_reason": "completed",
                        "replay_safe": True,
                        "last_rerun_policy": {"policy_id": "source_plan_refresh"},
                        "action_type_counts": {"request_source_plan_retry": 1},
                    }
                },
            }

    runner = BenchmarkRunner(_AgentLoopStubOrchestrator())
    results = runner.run(
        cases=[
            {
                "case_id": "c1",
                "query": "find app",
                "expected_keys": ["app"],
                "top_k": 4,
            }
        ],
        repo="demo",
        root=".",
    )

    assert results["agent_loop_control_plane_summary"] == {
        "case_count": 1,
        "observed_case_count": 1,
        "observed_case_rate": 1.0,
        "enabled_case_count": 1,
        "enabled_case_rate": 1.0,
        "attempted_case_count": 1,
        "attempted_case_rate": 1.0,
        "replay_safe_case_count": 1,
        "replay_safe_case_rate": 1.0,
        "actions_requested_mean": 1.0,
        "actions_executed_mean": 1.0,
        "request_more_context_case_count": 0,
        "request_more_context_case_rate": 0.0,
        "request_source_plan_retry_case_count": 1,
        "request_source_plan_retry_case_rate": 1.0,
        "request_validation_retry_case_count": 0,
        "request_validation_retry_case_rate": 0.0,
        "dominant_stop_reason": "completed",
        "dominant_last_policy_id": "source_plan_refresh",
    }


def test_benchmark_runner_passes_case_filters_to_orchestrator() -> None:
    class _FilterAwareStub:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def plan(
            self,
            *,
            query: str,
            repo: str,
            root: str,
            time_range: str | None = None,
            start_date: str | None = None,
            end_date: str | None = None,
            filters: dict[str, object] | None = None,
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "query": query,
                    "repo": repo,
                    "root": root,
                    "time_range": time_range,
                    "start_date": start_date,
                    "end_date": end_date,
                    "filters": filters,
                }
            )
            return {
                "index": {"candidate_files": [{"path": "src/app.py", "module": "src.app"}]},
                "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
                "repomap": {"dependency_recall": {"hit_rate": 1.0}},
                "observability": {
                    "plugin_policy_summary": {
                        "mode": "strict",
                        "allowlist": ["observability.mcp_plugins"],
                        "totals": {
                            "applied": 0,
                            "conflicts": 0,
                            "blocked": 0,
                            "warn": 0,
                            "remote_applied": 0,
                        },
                    }
                },
            }

    orchestrator = _FilterAwareStub()
    runner = BenchmarkRunner(orchestrator)
    case_filters = {"exclude_paths": ["tests/e2e/test_benchmark_case_files.py"]}

    runner.run(
        cases=[
            {
                "case_id": "c1",
                "query": "find app",
                "expected_keys": ["app"],
                "top_k": 4,
                "filters": case_filters,
            }
        ],
        repo="demo",
        root=".",
    )

    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0]["filters"] == case_filters


class _PolicyStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        payload = super().plan(
            query=query,
            repo=repo,
            root=root,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
        )
        totals = {
            "applied": 2,
            "conflicts": 1,
            "blocked": 1 if "block" in query else 0,
            "warn": 1 if "warn" in query else 0,
            "remote_applied": 1,
        }
        payload["observability"] = {
            "plugin_policy_summary": {
                "mode": "strict",
                "allowlist": [
                    "observability.mcp_plugins",
                    "source_plan.writeback_template",
                ],
                "totals": totals,
                "by_stage": [
                    {
                        "stage": "source_plan",
                        "applied": 2,
                        "conflicts": 1,
                        "blocked": totals["blocked"],
                        "warn": totals["warn"],
                        "remote_applied": 1,
                    }
                ],
            }
        }
        return payload


def test_benchmark_runner_aggregates_plugin_policy_summary() -> None:
    orchestrator = _PolicyStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find block", "expected_keys": ["app"], "top_k": 4},
        {"case_id": "c2", "query": "find warn", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    summary = results["plugin_policy_summary"]
    assert summary["mode"] == "strict"
    assert summary["allowlist"] == [
        "observability.mcp_plugins",
        "source_plan.writeback_template",
    ]
    assert summary["totals"] == {
        "applied": 4,
        "conflicts": 2,
        "blocked": 1,
        "warn": 1,
        "remote_applied": 2,
    }
    assert summary["per_case_mean"] == {
        "applied": 2.0,
        "conflicts": 1.0,
        "blocked": 0.5,
        "warn": 0.5,
        "remote_applied": 1.0,
    }
    assert summary["mode_distribution"] == {"strict": 2}
    assert summary["by_stage"] == [
        {
            "stage": "source_plan",
            "applied": 4,
            "conflicts": 2,
            "blocked": 1,
            "warn": 1,
            "remote_applied": 2,
        }
    ]
    assert summary["by_stage_per_case_mean"] == [
        {
            "stage": "source_plan",
            "applied": 2.0,
            "conflicts": 1.0,
            "blocked": 0.5,
            "warn": 0.5,
            "remote_applied": 1.0,
        }
    ]
    assert results["task_success_summary"] == {
        "case_count": 2,
        "positive_case_count": 2,
        "negative_control_case_count": 0,
        "task_success_rate": 1.0,
        "positive_task_success_rate": 1.0,
        "negative_control_task_success_rate": 0.0,
        "retrieval_task_gap_count": 0,
        "retrieval_task_gap_rate": 0.0,
    }
    assert results["evidence_insufficiency_summary"] == {
        "case_count": 2,
        "applicable_case_count": 0,
        "excluded_negative_control_case_count": 0,
        "evidence_insufficient_count": 0,
        "evidence_insufficient_rate": 0.0,
        "reasons": {},
        "signals": {},
    }
    assert results["chunk_stage_miss_summary"] == {
        "case_count": 2,
        "oracle_case_count": 0,
        "classified_case_count": 0,
        "classified_case_rate": 0.0,
        "labels": {},
    }


class _RouterStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (time_range, start_date, end_date)
        self.calls.append((query, repo, root))
        if "feature" in query:
            arm_id = "feature"
            shadow_arm_id = "feature_graph"
        else:
            arm_id = "general"
            shadow_arm_id = "general_hybrid"
        return {
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
                "policy_name": arm_id,
                "adaptive_router": {
                    "enabled": True,
                    "mode": "shadow",
                    "arm_set": "retrieval_policy_shadow",
                    "arm_id": arm_id,
                    "confidence": 0.0,
                    "shadow_arm_id": shadow_arm_id,
                    "shadow_source": "fallback",
                    "shadow_confidence": 0.75,
                    "online_bandit": {
                        "requested": True,
                        "experiment_enabled": False,
                        "eligible": True,
                        "active": False,
                        "reason": "experiment_mode_required",
                        "is_exploration": False,
                        "exploration_probability": 0.0,
                        "fallback_applied": True,
                        "fallback_reason": "experiment_mode_disabled",
                        "executed_mode": "heuristic",
                    },
                },
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
            "observability": {
                "plugin_policy_summary": {
                    "mode": "strict",
                    "allowlist": ["observability.mcp_plugins"],
                    "totals": {
                        "applied": 0,
                        "conflicts": 0,
                        "blocked": 0,
                        "warn": 0,
                        "remote_applied": 0,
                    },
                }
            },
        }


class _RewardWriter:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.flush_calls = 0

    def submit(self, *, event: dict[str, object]) -> bool:
        self.events.append(event)
        return True

    def flush(self) -> dict[str, object]:
        self.flush_calls += 1
        return {
            "pending_count": 0,
            "written_count": len(self.events),
            "error_count": 0,
            "last_error": "",
        }


class _FailingRewardWriter:
    def __init__(self) -> None:
        self.flush_calls = 0

    def submit(self, *, event: dict[str, object]) -> bool:
        _ = event
        raise RuntimeError("disk full")

    def flush(self) -> dict[str, object]:
        self.flush_calls += 1
        return {
            "pending_count": 0,
            "written_count": 0,
            "error_count": 0,
            "last_error": "",
        }


def test_benchmark_runner_reports_reward_log_disabled_by_default() -> None:
    orchestrator = _StubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["reward_log_summary"] == {
        "enabled": False,
        "active": False,
        "status": "disabled",
        "path": "",
        "eligible_case_count": 0,
        "submitted_count": 0,
        "pending_count": 0,
        "written_count": 0,
        "error_count": 0,
        "last_error": "",
    }


def test_benchmark_runner_surfaces_router_arm_case_rows_and_summary(monkeypatch) -> None:
    time_points = iter([0.0, 0.010, 0.020, 0.050])
    monkeypatch.setattr(
        "ace_lite.benchmark.runner.perf_counter",
        lambda: next(time_points),
    )
    orchestrator = _RouterStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "feature route", "expected_keys": ["app"], "top_k": 4},
        {"case_id": "c2", "query": "general lookup", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["cases"][0]["router_arm_id"] == "feature"
    assert results["cases"][0]["router_shadow_arm_id"] == "feature_graph"
    assert results["cases"][1]["router_arm_id"] == "general"
    assert results["cases"][1]["router_shadow_arm_id"] == "general_hybrid"
    arm_summary = results["adaptive_router_arm_summary"]
    assert arm_summary["case_count"] == 2
    assert arm_summary["enabled_case_count"] == 2
    assert arm_summary["executed"]["arm_count"] == 2
    assert arm_summary["shadow"]["arm_count"] == 2
    assert arm_summary["executed"]["arms"] == [
        {
            "arm_id": "feature",
            "case_count": 1,
            "case_rate": 0.5,
            "task_success_rate": 1.0,
            "mrr": 1.0,
            "fallback_case_count": 0,
            "fallback_case_rate": 0.0,
            "fallback_event_count": 0,
            "fallback_targets": {},
            "downgrade_case_count": 0,
            "downgrade_case_rate": 0.0,
            "downgrade_event_count": 0,
            "downgrade_targets": {},
            "latency_mean_ms": 10.0,
            "latency_p95_ms": 10.0,
            "index_latency_mean_ms": 0.0,
            "index_latency_p95_ms": 0.0,
        },
        {
            "arm_id": "general",
            "case_count": 1,
            "case_rate": 0.5,
            "task_success_rate": 1.0,
            "mrr": 1.0,
            "fallback_case_count": 0,
            "fallback_case_rate": 0.0,
            "fallback_event_count": 0,
            "fallback_targets": {},
            "downgrade_case_count": 0,
            "downgrade_case_rate": 0.0,
            "downgrade_event_count": 0,
            "downgrade_targets": {},
            "latency_mean_ms": 30.0,
            "latency_p95_ms": 30.0,
            "index_latency_mean_ms": 0.0,
            "index_latency_p95_ms": 0.0,
        },
    ]
    assert arm_summary["shadow"]["arms"] == [
        {
            "arm_id": "feature_graph",
            "case_count": 1,
            "case_rate": 0.5,
            "task_success_rate": 1.0,
            "mrr": 1.0,
            "fallback_case_count": 0,
            "fallback_case_rate": 0.0,
            "fallback_event_count": 0,
            "fallback_targets": {},
            "downgrade_case_count": 0,
            "downgrade_case_rate": 0.0,
            "downgrade_event_count": 0,
            "downgrade_targets": {},
            "latency_mean_ms": 10.0,
            "latency_p95_ms": 10.0,
            "index_latency_mean_ms": 0.0,
            "index_latency_p95_ms": 0.0,
        },
        {
            "arm_id": "general_hybrid",
            "case_count": 1,
            "case_rate": 0.5,
            "task_success_rate": 1.0,
            "mrr": 1.0,
            "fallback_case_count": 0,
            "fallback_case_rate": 0.0,
            "fallback_event_count": 0,
            "fallback_targets": {},
            "downgrade_case_count": 0,
            "downgrade_case_rate": 0.0,
            "downgrade_event_count": 0,
            "downgrade_targets": {},
            "latency_mean_ms": 30.0,
            "latency_p95_ms": 30.0,
            "index_latency_mean_ms": 0.0,
            "index_latency_p95_ms": 0.0,
        },
    ]
    pair_summary = results["adaptive_router_pair_summary"]
    assert pair_summary["case_count"] == 2
    assert pair_summary["comparable_case_count"] == 2
    assert pair_summary["disagreement_case_count"] == 2
    assert pair_summary["disagreement_rate"] == 1.0
    assert [
        (item["executed_arm_id"], item["shadow_arm_id"])
        for item in pair_summary["pairs"]
    ] == [
        ("feature", "feature_graph"),
        ("general", "general_hybrid"),
    ]
    assert all(item["latency_mean_ms"] >= 0.0 for item in pair_summary["pairs"])
    assert all(item["index_latency_mean_ms"] >= 0.0 for item in pair_summary["pairs"])
    assert results["adaptive_router_observability_summary"] == {
        "case_count": 2,
        "enabled_case_count": 2,
        "enabled_case_rate": 1.0,
        "shadow_coverage_case_count": 2,
        "shadow_coverage_rate": 1.0,
        "comparable_case_count": 2,
        "comparable_case_rate": 1.0,
        "agreement_case_count": 0,
        "agreement_rate": 0.0,
        "disagreement_case_count": 2,
        "disagreement_rate": 1.0,
        "executed_arm_count": 2,
        "shadow_arm_count": 2,
        "shadow_source_counts": {"fallback": 2},
        "executed_arms": [
            {
                "arm_id": "feature",
                "case_count": 1,
                "case_rate": 0.5,
                "task_success_rate": 1.0,
                "mrr": 1.0,
                "fallback_case_count": 0,
                "fallback_case_rate": 0.0,
                "fallback_event_count": 0,
                "fallback_targets": {},
                "downgrade_case_count": 0,
                "downgrade_case_rate": 0.0,
                "downgrade_event_count": 0,
                "downgrade_targets": {},
                "latency_mean_ms": 10.0,
                "latency_p95_ms": 10.0,
                "index_latency_mean_ms": 0.0,
                "index_latency_p95_ms": 0.0,
            },
            {
                "arm_id": "general",
                "case_count": 1,
                "case_rate": 0.5,
                "task_success_rate": 1.0,
                "mrr": 1.0,
                "fallback_case_count": 0,
                "fallback_case_rate": 0.0,
                "fallback_event_count": 0,
                "fallback_targets": {},
                "downgrade_case_count": 0,
                "downgrade_case_rate": 0.0,
                "downgrade_event_count": 0,
                "downgrade_targets": {},
                "latency_mean_ms": 30.0,
                "latency_p95_ms": 30.0,
                "index_latency_mean_ms": 0.0,
                "index_latency_p95_ms": 0.0,
            },
        ],
        "shadow_arms": [
            {
                "arm_id": "feature_graph",
                "case_count": 1,
                "case_rate": 0.5,
                "task_success_rate": 1.0,
                "mrr": 1.0,
                "fallback_case_count": 0,
                "fallback_case_rate": 0.0,
                "fallback_event_count": 0,
                "fallback_targets": {},
                "downgrade_case_count": 0,
                "downgrade_case_rate": 0.0,
                "downgrade_event_count": 0,
                "downgrade_targets": {},
                "latency_mean_ms": 10.0,
                "latency_p95_ms": 10.0,
                "index_latency_mean_ms": 0.0,
                "index_latency_p95_ms": 0.0,
            },
            {
                "arm_id": "general_hybrid",
                "case_count": 1,
                "case_rate": 0.5,
                "task_success_rate": 1.0,
                "mrr": 1.0,
                "fallback_case_count": 0,
                "fallback_case_rate": 0.0,
                "fallback_event_count": 0,
                "fallback_targets": {},
                "downgrade_case_count": 0,
                "downgrade_case_rate": 0.0,
                "downgrade_event_count": 0,
                "downgrade_targets": {},
                "latency_mean_ms": 30.0,
                "latency_p95_ms": 30.0,
                "index_latency_mean_ms": 0.0,
                "index_latency_p95_ms": 0.0,
            },
        ],
    }
    assert results["metrics"]["adaptive_router_shadow_coverage"] == 1.0
    assert results["retrieval_control_plane_gate_summary"] == {
        "regression_evaluated": False,
        "benchmark_regression_detected": False,
        "benchmark_regression_passed": False,
        "failed_checks": [],
        "adaptive_router_shadow_coverage": 1.0,
        "adaptive_router_shadow_coverage_threshold": 0.8,
        "adaptive_router_shadow_coverage_passed": True,
        "risk_upgrade_precision_gain": 0.0,
        "risk_upgrade_precision_gain_threshold": 0.0,
        "risk_upgrade_precision_gain_passed": True,
        "latency_p95_ms": 30.0,
        "latency_p95_ms_threshold": 850.0,
        "latency_p95_ms_passed": True,
        "gate_passed": False,
    }
    assert results["retrieval_frontier_gate_summary"] == {
        "failed_checks": [
            "deep_symbol_case_recall",
            "native_scip_loaded_rate",
        ],
        "deep_symbol_case_recall": 0.0,
        "deep_symbol_case_recall_threshold": 0.9,
        "deep_symbol_case_recall_passed": False,
        "native_scip_loaded_rate": 0.0,
        "native_scip_loaded_rate_threshold": 0.7,
        "native_scip_loaded_rate_passed": False,
        "precision_at_k": 1.0,
        "precision_at_k_threshold": 0.64,
        "precision_at_k_passed": True,
        "noise_rate": 0.0,
        "noise_rate_threshold": 0.36,
        "noise_rate_passed": True,
        "gate_passed": False,
    }
    assert results["repomap_seed_summary"] == {
        "worktree_seed_count_mean": 0.0,
        "subgraph_seed_count_mean": 0.0,
        "seed_candidates_count_mean": 0.0,
        "cache_hit_ratio": 0.0,
        "precompute_hit_ratio": 0.0,
    }
    assert results["validation_probe_summary"] == {
        "validation_test_count": 1.0,
        "probe_enabled_ratio": 0.0,
        "probe_executed_count_mean": 0.0,
        "probe_failure_rate": 0.0,
    }
    assert results["validation_branch_summary"] == {
        "case_count": 0.0,
        "case_rate": 0.0,
        "candidate_count_mean": 0.0,
        "rejected_count_mean": 0.0,
        "selection_present_ratio": 0.0,
        "patch_artifact_present_ratio": 0.0,
        "archive_present_ratio": 0.0,
        "parallel_case_rate": 0.0,
        "winner_pass_rate": 0.0,
        "winner_regressed_rate": 0.0,
        "winner_score_mean": 0.0,
        "winner_after_issue_count_mean": 0.0,
    }
    assert results["validation_branch_gate_summary"] == {
        "failed_checks": [
            "validation_branch_case_count",
            "validation_branch_selection_present_ratio",
            "validation_branch_patch_artifact_present_ratio",
            "validation_branch_archive_present_ratio",
            "validation_branch_parallel_case_rate",
        ],
        "case_count": 0.0,
        "case_rate": 0.0,
        "case_count_threshold": 1.0,
        "case_count_passed": False,
        "selection_present_ratio": 0.0,
        "selection_present_ratio_threshold": 1.0,
        "selection_present_ratio_passed": False,
        "patch_artifact_present_ratio": 0.0,
        "patch_artifact_present_ratio_threshold": 1.0,
        "patch_artifact_present_ratio_passed": False,
        "archive_present_ratio": 0.0,
        "archive_present_ratio_threshold": 1.0,
        "archive_present_ratio_passed": False,
        "parallel_case_rate": 0.0,
        "parallel_case_rate_threshold": 1.0,
        "parallel_case_rate_passed": False,
        "gate_passed": False,
    }
    assert results["source_plan_card_summary"] == {
        "evidence_card_count_mean": 0.0,
        "file_card_count_mean": 0.0,
        "chunk_card_count_mean": 0.0,
        "validation_card_present_ratio": 0.0,
    }
    assert results["source_plan_validation_feedback_summary"] == {
        "present_ratio": 0.0,
        "issue_count_mean": 0.0,
        "failure_rate": 0.0,
        "probe_issue_count_mean": 0.0,
        "probe_executed_count_mean": 0.0,
        "probe_failure_rate": 0.0,
        "selected_test_count_mean": 0.0,
        "executed_test_count_mean": 0.0,
    }
    assert results["source_plan_failure_signal_summary"] == {
        "present_ratio": 0.0,
        "issue_count_mean": 0.0,
        "failure_rate": 0.0,
        "probe_issue_count_mean": 0.0,
        "probe_executed_count_mean": 0.0,
        "probe_failure_rate": 0.0,
        "selected_test_count_mean": 0.0,
        "executed_test_count_mean": 0.0,
        "replay_cache_origin_ratio": 0.0,
        "observability_origin_ratio": 0.0,
        "source_plan_origin_ratio": 0.0,
        "validate_step_origin_ratio": 0.0,
    }
    assert results["deep_symbol_summary"] == {
        "case_count": 0.0,
        "recall": 0.0,
    }
    assert results["native_scip_summary"] == {
        "loaded_rate": 0.0,
        "document_count_mean": 0.0,
        "definition_occurrence_count_mean": 0.0,
        "reference_occurrence_count_mean": 0.0,
        "symbol_definition_count_mean": 0.0,
    }


def test_benchmark_runner_submits_router_reward_events_when_writer_is_present() -> None:
    orchestrator = _RouterStubOrchestrator()
    writer = _RewardWriter()
    runner = BenchmarkRunner(
        orchestrator,
        reward_log_writer=writer,
        reward_log_enabled=True,
        reward_log_path="context-map/router/rewards.jsonl",
    )
    cases = [
        {
            "case_id": "router-case-01",
            "query": "feature route",
            "expected_keys": ["app"],
            "top_k": 4,
            "comparison_lane": "router_eval",
        }
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["case_count"] == 1
    assert writer.flush_calls == 1
    assert len(writer.events) == 1
    event = writer.events[0]
    assert event["query_id"] == "router-case-01"
    assert event["chosen_arm_id"] == "feature"
    assert event["shadow_arm_id"] == "feature_graph"
    assert event["router_mode"] == "shadow"
    assert event["is_exploration"] is False
    assert event["reward_source"] == "benchmark_task_success"
    assert event["reward_value"] == 1.0
    assert event["context_features"]["comparison_lane"] == "router_eval"
    assert event["context_features"]["router_experiment_enabled"] is False
    assert event["context_features"]["router_fallback_applied"] is True
    assert event["context_features"]["router_fallback_reason"] == "experiment_mode_disabled"
    assert results["reward_log_summary"] == {
        "enabled": True,
        "active": True,
        "status": "enabled",
        "path": "context-map/router/rewards.jsonl",
        "eligible_case_count": 1,
        "submitted_count": 1,
        "pending_count": 0,
        "written_count": 1,
        "error_count": 0,
        "last_error": "",
    }


def test_benchmark_runner_preserves_failed_retrieval_control_plane_gate_summary(
    monkeypatch,
) -> None:
    time_points = iter([0.0, 0.010, 0.020, 0.050])
    monkeypatch.setattr(
        "ace_lite.benchmark.runner.perf_counter",
        lambda: next(time_points),
    )
    orchestrator = _RouterStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {
            "case_id": "c1",
            "query": "feature route",
            "expected_keys": ["app"],
            "top_k": 4,
        },
        {
            "case_id": "c2",
            "query": "general lookup",
            "expected_keys": ["app"],
            "top_k": 4,
        },
    ]

    monkeypatch.setattr(
        "ace_lite.benchmark.runner.detect_regression",
        lambda **kwargs: {
            "regressed": True,
            "failed_checks": ["precision_at_k", "latency_p95_ms"],
        },
    )

    results = runner.run(
        cases=cases,
        repo="demo",
        root=".",
        baseline_metrics={"task_success_rate": 1.0},
    )

    assert results["regression"] == {
        "regressed": True,
        "failed_checks": ["precision_at_k", "latency_p95_ms"],
    }
    assert results["retrieval_control_plane_gate_summary"] == {
        "regression_evaluated": True,
        "benchmark_regression_detected": True,
        "benchmark_regression_passed": False,
        "failed_checks": ["precision_at_k", "latency_p95_ms"],
        "adaptive_router_shadow_coverage": 1.0,
        "adaptive_router_shadow_coverage_threshold": 0.8,
        "adaptive_router_shadow_coverage_passed": True,
        "risk_upgrade_precision_gain": 0.0,
        "risk_upgrade_precision_gain_threshold": 0.0,
        "risk_upgrade_precision_gain_passed": True,
        "latency_p95_ms": 30.0,
        "latency_p95_ms_threshold": 850.0,
        "latency_p95_ms_passed": True,
        "gate_passed": False,
    }


def test_benchmark_runner_surfaces_reward_log_degraded_when_submit_fails() -> None:
    orchestrator = _RouterStubOrchestrator()
    writer = _FailingRewardWriter()
    runner = BenchmarkRunner(
        orchestrator,
        reward_log_writer=writer,
        reward_log_enabled=True,
        reward_log_path="context-map/router/rewards.jsonl",
    )
    cases = [
        {
            "case_id": "router-case-01",
            "query": "feature route",
            "expected_keys": ["app"],
            "top_k": 4,
            "comparison_lane": "router_eval",
        }
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert writer.flush_calls == 1
    assert results["reward_log_summary"]["enabled"] is True
    assert results["reward_log_summary"]["active"] is True
    assert results["reward_log_summary"]["status"] == "degraded"
    assert results["reward_log_summary"]["eligible_case_count"] == 1
    assert results["reward_log_summary"]["submitted_count"] == 0
    assert results["reward_log_summary"]["written_count"] == 0
    assert results["reward_log_summary"]["error_count"] == 1
    assert "disk full" in results["reward_log_summary"]["last_error"]


class _SloStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (time_range, start_date, end_date)
        self.calls.append((query, repo, root))
        return {
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
                "embeddings": {
                    "time_budget_ms": 60,
                    "time_budget_exceeded": True,
                    "adaptive_budget_applied": True,
                    "fallback": False,
                },
                "chunk_semantic_rerank": {
                    "time_budget_ms": 25,
                    "time_budget_exceeded": False,
                    "fallback": True,
                },
                "parallel": {
                    "time_budget_ms": 30,
                    "docs": {"timed_out": True},
                    "worktree": {"timed_out": False},
                },
            },
            "augment": {
                "xref": {
                    "time_budget_ms": 15,
                    "budget_exhausted": True,
                }
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
            "observability": {
                "plugin_policy_summary": {
                    "mode": "strict",
                    "allowlist": ["observability.mcp_plugins"],
                    "totals": {
                        "applied": 0,
                        "conflicts": 0,
                        "blocked": 0,
                        "warn": 0,
                        "remote_applied": 0,
                    },
                },
                "stage_metrics": [
                    {"stage": "memory", "elapsed_ms": 2.0},
                    {"stage": "index", "elapsed_ms": 4.0},
                    {"stage": "repomap", "elapsed_ms": 3.0},
                    {"stage": "augment", "elapsed_ms": 1.0},
                    {"stage": "skills", "elapsed_ms": 0.5},
                    {"stage": "source_plan", "elapsed_ms": 2.5},
                ],
            },
        }


def test_benchmark_runner_emits_stage_latency_and_slo_budget_summaries() -> None:
    orchestrator = _SloStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["stage_latency_summary"]["index"]["p95_ms"] == 4.0
    assert results["stage_latency_summary"]["total"]["p95_ms"] >= 0.0
    assert results["slo_budget_summary"]["budget_limits_ms"] == {
        "parallel_time_budget_ms_mean": 30.0,
        "embedding_time_budget_ms_mean": 60.0,
        "chunk_semantic_time_budget_ms_mean": 25.0,
        "xref_time_budget_ms_mean": 15.0,
    }
    assert results["slo_budget_summary"]["downgrade_case_count"] == 1
    assert results["slo_budget_summary"]["signals"]["parallel_docs_timeout_ratio"] == {
        "count": 1,
        "rate": 1.0,
    }
    assert results["metrics"]["embedding_time_budget_exceeded_ratio"] == 1.0
    assert results["metrics"]["chunk_semantic_fallback_ratio"] == 1.0


class _DecisionStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (time_range, start_date, end_date)
        self.calls.append((query, repo, root))
        return {
            "memory": {
                "gate": {
                    "skipped": True,
                    "skip_reason": "greeting",
                }
            },
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
                "docs": {
                    "enabled": True,
                    "section_count": 1,
                    "backend_fallback_reason": "fts5_unavailable",
                },
                "candidate_ranking": {
                    "fallbacks": ["tiny_corpus"],
                    "exact_search": {
                        "enabled": True,
                        "reason": "applied",
                        "applied": True,
                    },
                    "refine_pass": {
                        "enabled": True,
                        "trigger_condition_met": True,
                        "triggered": True,
                        "applied": True,
                        "reason": "low_candidate_count",
                    },
                    "second_pass": {
                        "triggered": True,
                        "applied": True,
                        "reason": "low_candidate_count",
                    },
                },
                "parallel": {
                    "docs": {"timed_out": True},
                },
            },
            "skills": {
                "budget_exhausted": True,
                "skipped_for_budget": [{"name": "skill-a"}],
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
        }


def test_benchmark_runner_aggregates_decision_observability_summary() -> None:
    orchestrator = _DecisionStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["cases"][0]["decision_trace"] == [
        {
            "stage": "memory",
            "action": "skip",
            "target": "memory_retrieval",
            "reason": "greeting",
        },
        {
            "stage": "index",
            "action": "fallback",
            "target": "candidate_ranker",
            "reason": "tiny_corpus",
        },
        {
            "stage": "index",
            "action": "boost",
            "target": "exact_search",
            "reason": "applied",
            "outcome": "applied",
        },
        {
            "stage": "index",
            "action": "retry",
            "target": "deterministic_refine",
            "reason": "low_candidate_count",
            "outcome": "applied",
        },
        {
            "stage": "index",
            "action": "fallback",
            "target": "docs_backend",
            "reason": "fts5_unavailable",
        },
        {
            "stage": "index",
            "action": "downgrade",
            "target": "parallel_docs",
            "reason": "timeout",
        },
        {
            "stage": "skills",
            "action": "skip",
            "target": "skills_hydration",
            "reason": "token_budget_exhausted",
        },
    ]
    assert results["decision_observability_summary"] == {
        "case_count": 1,
        "case_with_decisions_count": 1,
        "case_with_decisions_rate": 1.0,
        "decision_event_count": 7,
        "actions": {
            "boost": 1,
            "downgrade": 1,
            "fallback": 2,
            "retry": 1,
            "skip": 2,
        },
        "targets": {
            "candidate_ranker": 1,
            "deterministic_refine": 1,
            "docs_backend": 1,
            "exact_search": 1,
            "memory_retrieval": 1,
            "parallel_docs": 1,
            "skills_hydration": 1,
        },
        "reasons": {
            "applied": 1,
            "fts5_unavailable": 1,
            "greeting": 1,
            "low_candidate_count": 1,
            "timeout": 1,
            "tiny_corpus": 1,
            "token_budget_exhausted": 1,
        },
        "outcomes": {
            "applied": 2,
        },
    }


class _RetrievalContextStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (query, repo, root, time_range, start_date, end_date)
        return {
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
                "chunk_metrics": {
                    "retrieval_context_chunk_count": 2.0,
                    "retrieval_context_coverage_ratio": 1.0,
                    "retrieval_context_char_count_mean": 84.0,
                    "contextual_sidecar_parent_symbol_chunk_count": 2.0,
                    "contextual_sidecar_parent_symbol_coverage_ratio": 1.0,
                    "contextual_sidecar_reference_hint_chunk_count": 1.0,
                    "contextual_sidecar_reference_hint_coverage_ratio": 0.5,
                },
                "chunk_semantic_rerank": {
                    "reason": "ok",
                    "retrieval_context_pool_chunk_count": 1.0,
                    "retrieval_context_pool_coverage_ratio": 0.5,
                },
                "embeddings": {
                    "enabled": True,
                    "runtime_provider": "hash_cross",
                    "semantic_rerank_applied": True,
                },
                "graph_lookup": {
                    "enabled": True,
                    "reason": "candidate_count_guarded",
                    "guarded": True,
                    "boosted_count": 2,
                    "weights": {
                        "scip": 0.3,
                        "xref": 0.2,
                        "query_xref": 0.2,
                        "symbol": 0.1,
                        "import": 0.1,
                        "coverage": 0.1,
                    },
                    "candidate_count": 6,
                    "pool_size": 4,
                    "query_terms_count": 3,
                    "normalization": "log1p",
                    "guard_max_candidates": 4,
                    "guard_min_query_terms": 1,
                    "guard_max_query_terms": 5,
                },
                "topological_shield": {
                    "enabled": True,
                    "mode": "report_only",
                    "report_only": True,
                    "max_attenuation": 0.6,
                    "shared_parent_attenuation": 0.2,
                    "adjacency_attenuation": 0.5,
                    "attenuated_chunk_count": 1,
                    "coverage_ratio": 0.5,
                    "attenuation_total": 0.2,
                },
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
        }


def test_benchmark_runner_aggregates_retrieval_context_observability_summary() -> None:
    orchestrator = _RetrievalContextStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["retrieval_context_observability_summary"] == {
        "case_count": 1,
        "available_case_count": 1,
        "available_case_rate": 1.0,
        "parent_symbol_available_case_count": 1,
        "parent_symbol_available_case_rate": 1.0,
        "reference_hint_available_case_count": 1,
        "reference_hint_available_case_rate": 1.0,
        "pool_available_case_count": 1,
        "pool_available_case_rate": 1.0,
        "chunk_count_mean": 2.0,
        "coverage_ratio_mean": 1.0,
        "parent_symbol_chunk_count_mean": 2.0,
        "parent_symbol_coverage_ratio_mean": 1.0,
        "reference_hint_chunk_count_mean": 1.0,
        "reference_hint_coverage_ratio_mean": 0.5,
        "pool_chunk_count_mean": 1.0,
        "pool_coverage_ratio_mean": 0.5,
    }


def test_benchmark_runner_aggregates_retrieval_default_strategy_summary() -> None:
    orchestrator = _RetrievalContextStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["retrieval_default_strategy_summary"] == {
        "case_count": 1,
        "retrieval_context_available_case_count": 1,
        "retrieval_context_available_case_rate": 1.0,
        "parent_symbol_available_case_count": 1,
        "parent_symbol_available_case_rate": 1.0,
        "reference_hint_available_case_count": 1,
        "reference_hint_available_case_rate": 1.0,
        "semantic_rerank_configured_case_count": 1,
        "semantic_rerank_configured_case_rate": 1.0,
        "semantic_rerank_enabled_case_count": 1,
        "semantic_rerank_enabled_case_rate": 1.0,
        "semantic_rerank_applied_case_count": 1,
        "semantic_rerank_applied_case_rate": 1.0,
        "semantic_rerank_cross_encoder_case_count": 1,
        "semantic_rerank_cross_encoder_case_rate": 1.0,
        "semantic_rerank_dominant_provider": "hash_cross",
        "semantic_rerank_dominant_mode": "cross_encoder",
        "semantic_rerank_provider_case_counts": {"hash_cross": 1},
        "graph_lookup_enabled_case_count": 1,
        "graph_lookup_enabled_case_rate": 1.0,
        "graph_lookup_guarded_case_count": 1,
        "graph_lookup_guarded_case_rate": 1.0,
        "graph_lookup_dominant_normalization": "log1p",
        "graph_lookup_pool_size_mean": 4.0,
        "graph_lookup_guard_max_candidates_mean": 4.0,
        "graph_lookup_guard_min_query_terms_mean": 1.0,
        "graph_lookup_guard_max_query_terms_mean": 5.0,
        "graph_lookup_weight_means": {
            "scip": 0.3,
            "xref": 0.2,
            "query_xref": 0.2,
            "symbol": 0.1,
            "import": 0.1,
            "coverage": 0.1,
        },
        "topological_shield_enabled_case_count": 1,
        "topological_shield_enabled_case_rate": 1.0,
        "topological_shield_report_only_case_count": 1,
        "topological_shield_report_only_case_rate": 1.0,
        "topological_shield_dominant_mode": "report_only",
        "topological_shield_max_attenuation_mean": 0.6,
        "topological_shield_shared_parent_attenuation_mean": 0.2,
        "topological_shield_adjacency_attenuation_mean": 0.5,
    }


class _PreferenceObservabilityStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (query, repo, root, time_range, start_date, end_date)
        return {
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
            },
            "memory": {
                "count": 1,
                "notes": {"selected_count": 1},
                "profile": {"selected_count": 2},
                "capture": {"triggered": True},
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
        }


def test_benchmark_runner_aggregates_preference_observability_summary() -> None:
    orchestrator = _PreferenceObservabilityStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 2},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["preference_observability_summary"] == {
        "case_count": 1,
        "observed_case_count": 1,
        "observed_case_rate": 1.0,
        "notes_hit_case_count": 1,
        "notes_hit_case_rate": 1.0,
        "profile_selected_case_count": 1,
        "profile_selected_case_rate": 1.0,
        "capture_triggered_case_count": 1,
        "capture_triggered_case_rate": 1.0,
        "notes_hit_ratio_mean": 1.0,
        "profile_selected_count_mean": 2.0,
    }


class _FeedbackObservabilityStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (query, repo, root, time_range, start_date, end_date)
        return {
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
                "candidate_ranking": {
                    "feedback_enabled": True,
                    "feedback_reason": "ok",
                    "feedback_event_count": 5,
                    "feedback_matched_event_count": 3,
                    "feedback_boosted_count": 2,
                    "feedback_boosted_paths": 1,
                },
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
        }


def test_benchmark_runner_aggregates_feedback_observability_summary() -> None:
    orchestrator = _FeedbackObservabilityStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 2},
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["feedback_observability_summary"] == {
        "case_count": 1,
        "enabled_case_count": 1,
        "enabled_case_rate": 1.0,
        "matched_case_count": 1,
        "matched_case_rate": 1.0,
        "boosted_case_count": 1,
        "boosted_case_rate": 1.0,
        "event_count_mean": 5.0,
        "matched_event_count_mean": 3.0,
        "boosted_candidate_count_mean": 2.0,
        "boosted_unique_paths_mean": 1.0,
        "reasons": {"ok": 1},
    }


class _DecisionSkipStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (query, repo, root, time_range, start_date, end_date)
        return {
            "index": {
                "candidate_files": [{"path": "src/app.py", "module": "src.app"}],
                "candidate_ranking": {
                    "fallbacks": [],
                    "exact_search": {"enabled": False},
                    "refine_pass": {
                        "enabled": False,
                        "trigger_condition_met": True,
                        "triggered": False,
                        "applied": False,
                        "reason": "disabled",
                    },
                    "second_pass": {
                        "triggered": False,
                        "applied": False,
                        "reason": "",
                    },
                },
            },
            "source_plan": {"validation_tests": ["tests.test_app::test_smoke"]},
            "repomap": {"dependency_recall": {"hit_rate": 1.0}},
        }


def test_benchmark_runner_traces_disabled_deterministic_refine() -> None:
    runner = BenchmarkRunner(_DecisionSkipStubOrchestrator())

    results = runner.run(
        cases=[{"case_id": "c1", "query": "find app", "expected_keys": ["app"], "top_k": 4}],
        repo="demo",
        root=".",
    )

    assert results["cases"][0]["decision_trace"] == [
        {
            "stage": "index",
            "action": "skip",
            "target": "deterministic_refine",
            "reason": "disabled",
        }
    ]


class _InsufficiencyStubOrchestrator(_StubOrchestrator):
    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        _ = (time_range, start_date, end_date)
        self.calls.append((query, repo, root))
        return {
            "index": {
                "candidate_files": [
                    {
                        "path": "docs/maintainers/BENCHMARKING.md",
                        "module": "docs.maintainers.benchmarking",
                    }
                ],
                "docs": {"enabled": True, "section_count": 0},
                "metadata": {
                    "docs_enabled": True,
                    "docs_section_count": 0,
                    "docs_injected_count": 0,
                },
            },
            "source_plan": {"candidate_chunks": [], "validation_tests": []},
            "repomap": {
                "dependency_recall": {"hit_rate": 0.0},
                "neighbor_paths": [],
            },
        }


def test_benchmark_runner_aggregates_evidence_insufficiency_summary() -> None:
    orchestrator = _InsufficiencyStubOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    cases = [
        {
            "case_id": "c1",
            "query": "where benchmark guide lives",
            "expected_keys": ["benchmarking", "docs"],
            "top_k": 4,
            "task_success": {
                "mode": "positive",
                "min_validation_tests": 1,
            },
        },
        {
            "case_id": "c2",
            "query": "where benchmark guide lives",
            "expected_keys": ["benchmarking", "docs"],
            "top_k": 4,
            "task_success": {
                "mode": "negative_control",
                "min_validation_tests": 1,
            },
        },
    ]

    results = runner.run(cases=cases, repo="demo", root=".")

    assert results["metrics"]["evidence_insufficient_rate"] == 0.5
    assert results["metrics"]["missing_validation_rate"] == 0.5
    assert results["metrics"]["risk_upgrade_precision_gain"] == 0.0
    assert results["evidence_insufficiency_summary"] == {
        "case_count": 2,
        "applicable_case_count": 1,
        "excluded_negative_control_case_count": 1,
        "evidence_insufficient_count": 1,
        "evidence_insufficient_rate": 1.0,
        "reasons": {"low_support": 1},
        "signals": {
            "low_chunk_support": 1,
            "missing_candidate_chunks": 1,
            "missing_docs_evidence": 1,
            "missing_repomap_neighbors": 1,
            "missing_validation_tests": 1,
        },
    }
    assert results["missing_context_risk_summary"] == {
        "case_count": 2,
        "applicable_case_count": 1,
        "excluded_negative_control_case_count": 1,
        "elevated_case_count": 1,
        "high_risk_case_count": 0,
        "elevated_case_rate": 1.0,
        "high_risk_case_rate": 0.0,
        "risk_score_mean": 0.5,
        "risk_score_p95": 0.5,
        "risk_upgrade_case_count": 0,
        "risk_upgrade_case_rate": 0.0,
        "risk_upgrade_precision_mean": 0.0,
        "risk_baseline_precision_mean": 1.0,
        "risk_upgrade_precision_gain": 0.0,
        "levels": {"elevated": 1},
        "signals": {
            "chunk_miss_after_recall": 1,
            "evidence_insufficient": 1,
        },
    }
