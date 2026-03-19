from __future__ import annotations

from typing import Any


OPTIONAL_SUMMARY_MAPPING_KEYS = (
    "task_success_summary",
    "evidence_insufficiency_summary",
    "feedback_loop_summary",
    "feedback_observability_summary",
    "preference_observability_summary",
    "retrieval_context_observability_summary",
    "chunk_stage_miss_summary",
    "decision_observability_summary",
    "adaptive_router_arm_summary",
    "adaptive_router_observability_summary",
    "adaptive_router_pair_summary",
    "comparison_lane_summary",
    "stage_latency_summary",
    "slo_budget_summary",
    "reward_log_summary",
    "runtime_stats_summary",
)


def copy_optional_summary_sections(*, results: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in OPTIONAL_SUMMARY_MAPPING_KEYS:
        raw = results.get(key)
        if isinstance(raw, dict):
            payload[key] = dict(raw)

    policy_profiles = results.get("policy_profile_distribution")
    if isinstance(policy_profiles, dict) and policy_profiles:
        payload["policy_profile_distribution"] = dict(policy_profiles)

    return payload


__all__ = ["copy_optional_summary_sections"]
