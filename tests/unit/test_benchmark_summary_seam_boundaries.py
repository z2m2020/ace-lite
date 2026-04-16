from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_benchmark_summaries_uses_summary_memory_seam() -> None:
    summaries_text = _read_repo_text("src/ace_lite/benchmark/summaries.py")

    expected_tokens = (
        "from ace_lite.benchmark.summary_memory import (",
        "build_chunk_cache_contract_summary as _build_chunk_cache_contract_summary_impl",
        "build_ltm_explainability_summary as _build_ltm_explainability_summary_impl",
        "_build_ltm_explainability_summary_impl(case_results)",
        "_build_chunk_cache_contract_summary_impl(case_results)",
    )
    for token in expected_tokens:
        assert token in summaries_text

    forbidden_local_impl_tokens = (
        'feedback_signal_names = ("helpful", "stale", "harmful")',
        'payload_raw = item.get("ltm_explainability")',
        "present_case_count = 0",
        "fingerprint_present_case_count = 0",
        "metadata_aligned_case_count = 0",
    )
    for token in forbidden_local_impl_tokens:
        assert token not in summaries_text


def test_benchmark_summaries_uses_summary_quality_seam() -> None:
    summaries_text = _read_repo_text("src/ace_lite/benchmark/summaries.py")

    expected_tokens = (
        "from ace_lite.benchmark.summary_quality import (",
        "build_agent_loop_control_plane_summary as _build_agent_loop_control_plane_summary_impl",
        "build_chunk_stage_miss_summary as _build_chunk_stage_miss_summary_impl",
        "build_comparison_lane_summary as _build_comparison_lane_summary_impl",
        "build_context_refine_summary as _build_context_refine_summary_impl",
        "build_decision_observability_summary as _build_decision_observability_summary_impl",
        "build_evidence_insufficiency_summary as _build_evidence_insufficiency_summary_impl",
        "build_feedback_loop_summary as _build_feedback_loop_summary_impl",
        "build_feedback_observability_summary as _build_feedback_observability_summary_impl",
        "build_missing_context_risk_summary as _build_missing_context_risk_summary_impl",
        "build_preference_observability_summary as _build_preference_observability_summary_impl",
        "build_retrieval_context_observability_summary as _build_retrieval_context_observability_summary_impl",
        "build_retrieval_default_strategy_summary as _build_retrieval_default_strategy_summary_impl",
        "build_slo_budget_summary as _build_slo_budget_summary_impl",
        "build_stage_latency_summary as _build_stage_latency_summary_impl",
        "build_wave1_context_governance_summary as _build_wave1_context_governance_summary_impl",
        "is_risk_upgrade_case as _is_risk_upgrade_case_impl",
        "summarize_missing_context_risk_case as _summarize_missing_context_risk_case_impl",
        "_build_evidence_insufficiency_summary_impl(case_results)",
        "_build_missing_context_risk_summary_impl(case_results)",
        "_build_chunk_stage_miss_summary_impl(case_results)",
        "_build_decision_observability_summary_impl(case_results)",
        "_build_retrieval_context_observability_summary_impl(case_results)",
        "_build_retrieval_default_strategy_summary_impl(case_results)",
        "_build_agent_loop_control_plane_summary_impl(case_results)",
        "_build_preference_observability_summary_impl(case_results)",
        "_build_feedback_observability_summary_impl(case_results)",
        "_build_feedback_loop_summary_impl(case_results)",
        "_build_comparison_lane_summary_impl(case_results)",
        "_build_stage_latency_summary_impl(case_results)",
        "_build_slo_budget_summary_impl(case_results)",
        "_build_wave1_context_governance_summary_impl(case_results)",
        "_build_context_refine_summary_impl(case_results)",
    )
    for token in expected_tokens:
        assert token in summaries_text

    forbidden_local_impl_tokens = (
        "applicable_case_count = 0",
        "excluded_negative_control_case_count = 0",
        "elevated_case_count = 0",
        "high_risk_case_count = 0",
        'signals["recall_miss"] = signals.get("recall_miss", 0) + 1',
        "evidence_insufficient_count = 0",
        "classified_case_count = 0",
        "case_with_decisions_count = 0",
        "decision_event_count = 0",
        'return True, score, "high"',
        'return True, score, "elevated"',
        'return True, score, "low"',
    )
    for token in forbidden_local_impl_tokens:
        assert token not in summaries_text
