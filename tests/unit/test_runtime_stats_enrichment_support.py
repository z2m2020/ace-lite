from __future__ import annotations

from ace_lite.cli_app.runtime_stats_enrichment_support import (
    build_runtime_agent_loop_control_plane_summary,
    build_runtime_memory_health_summary,
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
