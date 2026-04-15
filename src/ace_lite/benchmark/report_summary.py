from __future__ import annotations

from typing import Any

OPTIONAL_SUMMARY_MAPPING_KEYS = (
    "task_success_summary",
    "evidence_insufficiency_summary",
    "missing_context_risk_summary",
    "feedback_loop_summary",
    "feedback_observability_summary",
    "ltm_explainability_summary",
    "preference_observability_summary",
    "retrieval_default_strategy_summary",
    "agent_loop_control_plane_summary",
    "retrieval_context_observability_summary",
    "chunk_cache_contract_summary",
    "chunk_stage_miss_summary",
    "decision_observability_summary",
    "adaptive_router_arm_summary",
    "learning_router_rollout_summary",
    "adaptive_router_observability_summary",
    "adaptive_router_pair_summary",
    "comparison_lane_summary",
    "repomap_seed_summary",
    "validation_probe_summary",
    "validation_branch_summary",
    "validation_branch_gate_summary",
    "source_plan_card_summary",
    "source_plan_failure_signal_summary",
    "source_plan_validation_feedback_summary",
    "wave1_context_governance_summary",
    "deep_symbol_summary",
    "native_scip_summary",
    "retrieval_control_plane_gate_summary",
    "retrieval_frontier_gate_summary",
    "stage_latency_summary",
    "slo_budget_summary",
    "reward_log_summary",
    "runtime_stats_summary",
    "tuning_context_summary",
    "workload_taxonomy_summary",
)


def get_summary_mapping(*, results: dict[str, Any], key: str) -> dict[str, Any]:
    raw = results.get(key)
    return raw if isinstance(raw, dict) else {}


def get_nested_mapping(*, payload: dict[str, Any], key: str) -> dict[str, Any]:
    raw = payload.get(key)
    return raw if isinstance(raw, dict) else {}


def copy_optional_summary_sections(*, results: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in OPTIONAL_SUMMARY_MAPPING_KEYS:
        summary = get_summary_mapping(results=results, key=key)
        if summary:
            payload[key] = dict(summary)

    policy_profiles = get_summary_mapping(
        results=results, key="policy_profile_distribution"
    )
    if policy_profiles:
        payload["policy_profile_distribution"] = dict(policy_profiles)

    return payload


__all__ = [
    "copy_optional_summary_sections",
    "get_nested_mapping",
    "get_summary_mapping",
]
