from __future__ import annotations

from ace_lite.cli_app.runtime_stats_enrichment_support import (
    attach_runtime_memory_ltm_signal_summary,
    build_runtime_agent_loop_control_plane_summary,
    build_runtime_memory_health_summary,
    build_runtime_memory_ltm_signal_summary,
    build_runtime_top_pain_summary,
)


def test_runtime_stats_enrichment_support_builds_top_pain_and_memory_health() -> None:
    runtime_scope_map = {
        "repo_profile": {
            "degraded_states": [
                {
                    "reason_code": "memory_fallback",
                    "event_count": 2,
                    "last_seen_at": "2026-03-21T00:00:00+00:00",
                },
                {
                    "reason_code": "git_unavailable",
                    "event_count": 1,
                    "last_seen_at": "2026-03-21T00:01:00+00:00",
                },
            ],
            "stage_latencies": [
                {
                    "stage_name": "memory",
                    "invocation_count": 2,
                    "latency_ms_sum": 40.0,
                    "latency_ms_avg": 20.0,
                },
                {
                    "stage_name": "agent_loop",
                    "invocation_count": 2,
                    "latency_ms_sum": 24.0,
                    "latency_ms_avg": 12.0,
                }
            ],
        }
    }
    dev_feedback_summary = {
        "by_reason_code": [
            {
                "reason_code": "memory_fallback",
                "issue_count": 1,
                "open_issue_count": 1,
                "resolved_issue_count": 0,
                "fix_count": 1,
                "linked_fix_issue_count": 1,
                "issue_time_to_fix_case_count": 0,
                "issue_time_to_fix_hours_mean": 0.0,
                "last_seen_at": "2026-03-21T00:02:00+00:00",
            }
        ]
    }

    top_pain_summary = build_runtime_top_pain_summary(
        runtime_scope_map=runtime_scope_map,
        dev_feedback_summary=dev_feedback_summary,
    )
    memory_health_summary = build_runtime_memory_health_summary(
        runtime_scope_map=runtime_scope_map,
        top_pain_summary=top_pain_summary,
    )
    agent_loop_control_plane_summary = build_runtime_agent_loop_control_plane_summary(
        runtime_scope_map=runtime_scope_map,
    )

    assert top_pain_summary["count"] == 2
    assert top_pain_summary["items"][0]["reason_code"] == "memory_fallback"
    assert top_pain_summary["items"][0]["runtime_event_count"] == 2
    assert top_pain_summary["items"][0]["fix_count"] == 1
    assert memory_health_summary["scope_kind"] == "repo_profile"
    assert memory_health_summary["reason_count"] == 1
    assert memory_health_summary["runtime_event_count"] == 2
    assert memory_health_summary["memory_stage_latency_ms_avg"] == 20.0
    assert agent_loop_control_plane_summary["scope_kind"] == "repo_profile"
    assert agent_loop_control_plane_summary["source_plan_retry_supported"] is True
    assert agent_loop_control_plane_summary["observed_stage"] is True
    assert agent_loop_control_plane_summary["agent_loop_stage_latency_ms_avg"] == 12.0
    assert agent_loop_control_plane_summary["source_plan_retry_rerun_stages"] == [
        "source_plan",
        "validation",
    ]


def test_runtime_stats_enrichment_support_builds_memory_ltm_signal_summary() -> None:
    ltm_explainability_summary = {
        "case_count": 3,
        "feedback_signal_observed_case_count": 2,
        "feedback_signal_observed_case_rate": 2.0 / 3.0,
        "feedback_signals": [
            {
                "feedback_signal": "helpful",
                "case_count": 1,
                "case_rate": 1.0 / 3.0,
                "total_count": 2,
                "count_mean": 2.0 / 3.0,
            },
            {
                "feedback_signal": "stale",
                "case_count": 1,
                "case_rate": 1.0 / 3.0,
                "total_count": 1,
                "count_mean": 1.0 / 3.0,
            },
            {
                "feedback_signal": "harmful",
                "case_count": 1,
                "case_rate": 1.0 / 3.0,
                "total_count": 1,
                "count_mean": 1.0 / 3.0,
            },
        ],
        "attribution_scope_count": 2,
        "attribution_scope_observed_case_count": 2,
        "attribution_scope_observed_case_rate": 2.0 / 3.0,
        "attribution_scopes": [
            {
                "attribution_scope": "selected",
                "case_count": 2,
                "case_rate": 2.0 / 3.0,
                "total_count": 2,
                "count_mean": 2.0 / 3.0,
            },
            {
                "attribution_scope": "graph",
                "case_count": 1,
                "case_rate": 1.0 / 3.0,
                "total_count": 1,
                "count_mean": 1.0 / 3.0,
            },
        ],
    }

    ltm_signal_summary = build_runtime_memory_ltm_signal_summary(
        ltm_explainability_summary=ltm_explainability_summary,
    )

    assert ltm_signal_summary["case_count"] == 3
    assert ltm_signal_summary["feedback_signal_observed_case_count"] == 2
    assert ltm_signal_summary["feedback_signals"][0]["feedback_signal"] == "helpful"
    assert ltm_signal_summary["feedback_signals"][0]["total_count"] == 2
    assert ltm_signal_summary["attribution_scope_count"] == 2
    assert ltm_signal_summary["attribution_scopes"][0]["attribution_scope"] == "selected"

    attached = attach_runtime_memory_ltm_signal_summary(
        memory_health_summary={"scope_kind": "repo_profile", "reason_count": 1},
        ltm_explainability_summary=ltm_explainability_summary,
    )
    assert attached["scope_kind"] == "repo_profile"
    assert attached["ltm_signal_summary"] == ltm_signal_summary
