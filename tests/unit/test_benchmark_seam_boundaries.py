from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestBenchmarkSeamBoundaries:
    def test_report_observability_uses_memory_seam(self) -> None:
        observability_text = _read_repo_text("src/ace_lite/benchmark/report_observability.py")

        expected_tokens = (
            "from ace_lite.benchmark.report_observability_memory import (",
            "append_feedback_loop_summary as _append_feedback_loop_summary_impl",
            "append_feedback_observability_summary as _append_feedback_observability_summary_impl",
            "append_ltm_explainability_summary as _append_ltm_explainability_summary_impl",
            "append_preference_observability_summary as _append_preference_observability_summary_impl",
            "_append_preference_observability_summary_impl(lines, results)",
            "_append_feedback_observability_summary_impl(lines, results)",
            "_append_ltm_explainability_summary_impl(lines, results)",
            "_append_feedback_loop_summary_impl(lines, results)",
        )
        for token in expected_tokens:
            assert token in observability_text

        forbidden_local_impl_tokens = (
            'summary = get_summary_mapping(results=results, key="preference_observability_summary")',
            'summary = get_summary_mapping(results=results, key="feedback_observability_summary")',
            'summary = get_summary_mapping(results=results, key="ltm_explainability_summary")',
            'summary = get_summary_mapping(results=results, key="feedback_loop_summary")',
            'feedback_rows_raw = summary.get("feedback_signals")',
            'feedback_surfaces = get_nested_mapping(payload=summary, key="feedback_surfaces")',
            'lines.append("## Preference Observability Summary")',
            'lines.append("## Feedback Observability Summary")',
            'lines.append("## Long-Term Explainability Summary")',
            'lines.append("## Feedback Loop Summary")',
        )
        for token in forbidden_local_impl_tokens:
            assert token not in observability_text

    def test_report_observability_uses_core_summary_seam(self) -> None:
        observability_text = _read_repo_text("src/ace_lite/benchmark/report_observability.py")

        expected_tokens = (
            "from ace_lite.benchmark.report_observability_core import (",
            "append_evidence_insufficiency_summary as _append_evidence_insufficiency_summary_impl",
            "append_missing_context_risk_summary as _append_missing_context_risk_summary_impl",
            "append_reward_log_summary as _append_reward_log_summary_impl",
            "format_decision_event as _format_decision_event_impl",
            "_append_evidence_insufficiency_summary_impl(lines, results)",
            "_append_missing_context_risk_summary_impl(lines, results)",
            "_append_reward_log_summary_impl(lines, results)",
            "return _format_decision_event_impl(event)",
        )
        for token in expected_tokens:
            assert token in observability_text

        forbidden_local_impl_tokens = (
            'summary = get_summary_mapping(results=results, key="evidence_insufficiency_summary")',
            'summary = get_summary_mapping(results=results, key="missing_context_risk_summary")',
            'summary_raw = results.get("reward_log_summary")',
            'lines.append("## Evidence Insufficiency Summary")',
            'lines.append("## Missing-Context Risk Summary")',
            'lines.append("## Reward Log Summary")',
            "parts = [part for part in (stage, action, target) if part]",
        )
        for token in forbidden_local_impl_tokens:
            assert token not in observability_text

    def test_report_observability_uses_routing_seam(self) -> None:
        observability_text = _read_repo_text("src/ace_lite/benchmark/report_observability.py")

        expected_tokens = (
            "from ace_lite.benchmark.report_observability_routing import (",
            "append_adaptive_router_observability_summary as _append_adaptive_router_observability_summary_impl",
            "append_context_refine_summary as _append_context_refine_summary_impl",
            "append_retrieval_context_observability_summary as _append_retrieval_context_observability_summary_impl",
            "append_retrieval_default_strategy_summary as _append_retrieval_default_strategy_summary_impl",
            "_append_retrieval_context_observability_summary_impl(lines, results)",
            "_append_retrieval_default_strategy_summary_impl(lines, results)",
            "_append_adaptive_router_observability_summary_impl(lines, results)",
            "_append_context_refine_summary_impl(lines, results)",
        )
        for token in expected_tokens:
            assert token in observability_text

        forbidden_local_impl_tokens = (
            'summary_raw = results.get("retrieval_context_observability_summary")',
            'summary_raw = results.get("retrieval_default_strategy_summary")',
            'summary_raw = results.get("adaptive_router_observability_summary")',
            'summary = get_summary_mapping(results=results, key="context_refine_summary")',
            'weights_raw = summary.get("graph_lookup_weight_means")',
            'shadow_source_counts_raw = summary.get("shadow_source_counts")',
            'lines.append("## Retrieval Context Observability Summary")',
            'lines.append("## Retrieval Default Strategy Summary")',
            'lines.append("## Adaptive Router Observability")',
            'lines.append("## Context Refine Summary")',
        )
        for token in forbidden_local_impl_tokens:
            assert token not in observability_text

    def test_report_observability_uses_governance_seam(self) -> None:
        observability_text = _read_repo_text("src/ace_lite/benchmark/report_observability.py")

        expected_tokens = (
            "from ace_lite.benchmark.report_observability_governance import (",
            "append_decision_observability_summary as _append_decision_observability_summary_impl",
            "append_retrieval_control_plane_gate_summary as _append_retrieval_control_plane_gate_summary_impl",
            "append_wave1_context_governance_summary as _append_wave1_context_governance_summary_impl",
            "append_workload_taxonomy_summary as _append_workload_taxonomy_summary_impl",
            "_append_wave1_context_governance_summary_impl(lines, results)",
            "_append_retrieval_control_plane_gate_summary_impl(lines, results)",
            "_append_decision_observability_summary_impl(lines, results)",
            "_append_workload_taxonomy_summary_impl(lines, results)",
        )
        for token in expected_tokens:
            assert token in observability_text

        forbidden_local_impl_tokens = (
            'summary = get_summary_mapping(results=results, key="wave1_context_governance_summary")',
            'summary_raw = results.get("retrieval_control_plane_gate_summary")',
            'summary_raw = results.get("decision_observability_summary")',
            'summary = get_summary_mapping(results=results, key="workload_taxonomy_summary")',
            'lines.append("## Wave 1 Context Governance Summary")',
            'lines.append("## Retrieval Control Plane Gate Summary")',
            'lines.append("## Decision Observability Summary")',
            'lines.append("## Workload Taxonomy Summary")',
        )
        for token in forbidden_local_impl_tokens:
            assert token not in observability_text

    def test_benchmark_report_uses_report_observability_seam(self) -> None:
        report_text = _read_repo_text("src/ace_lite/benchmark/report.py")

        expected_tokens = (
            "from ace_lite.benchmark.report_observability import (",
            "from ace_lite.benchmark.report_sections import (",
            "append_adaptive_router_observability_summary",
            "append_decision_observability_summary",
            "append_evidence_insufficiency_summary",
            "append_feedback_loop_summary",
            "append_feedback_observability_summary",
            "append_ltm_explainability_summary",
            "append_missing_context_risk_summary",
            "append_preference_observability_summary",
            "append_retrieval_control_plane_gate_summary",
            "append_retrieval_context_observability_summary",
            "append_retrieval_default_strategy_summary",
            "append_retrieval_frontier_gate_summary",
            "append_reward_log_summary",
            "append_validation_branch_gate_summary",
            "append_validation_branch_summary",
            "format_decision_event",
        )
        for token in expected_tokens:
            assert token in report_text

        forbidden_local_helpers = (
            "def _append_feedback_observability_summary(",
            "def _append_feedback_loop_summary(",
            "def _append_evidence_insufficiency_summary(",
            "def _append_missing_context_risk_summary(",
            "def _append_preference_observability_summary(",
            "def _append_retrieval_control_plane_gate_summary(",
            "def _append_retrieval_context_observability_summary(",
            "def _append_retrieval_default_strategy_summary(",
            "def _append_retrieval_frontier_gate_summary(",
            "def _append_reward_log_summary(",
            "def _append_adaptive_router_observability_summary(",
            "def _append_decision_observability_summary(",
            "def _append_validation_branch_gate_summary(",
            "def _append_validation_branch_summary(",
        )
        for token in forbidden_local_helpers:
            assert token not in report_text

    def test_case_evaluation_entry_uses_helper_seams(self) -> None:
        case_eval_text = _read_repo_text("src/ace_lite/benchmark/case_evaluation.py")

        expected_tokens = (
            "from ace_lite.benchmark.case_evaluation_context import build_candidate_context",
            "from ace_lite.benchmark.case_evaluation_details import classify_chunk_stage_miss",
            "from ace_lite.benchmark.case_evaluation_diagnostics_builder import (",
            "build_case_evaluation_diagnostics_from_namespace",
            "from ace_lite.benchmark.case_evaluation_payload_builders import (",
            "build_case_detail_payload_from_namespace",
            "build_case_evaluation_row_from_namespace",
            "from ace_lite.benchmark.case_evaluation_inputs import build_case_evaluation_inputs",
            "collect_candidate_match_details",
            "collect_chunk_match_details",
            "build_case_evaluation_metrics",
            "coerce_chunk_refs",
        )
        for token in expected_tokens:
            assert token in case_eval_text

        forbidden_local_helpers = (
            "def _build_candidate_context(",
            "def _classify_chunk_stage_miss(",
            "def _build_case_evaluation_diagnostics(",
            "def _collect_candidate_match_details(",
            "def _collect_chunk_match_details(",
            "def _build_case_evaluation_metrics(",
            "def _build_case_detail_payload(",
            "def _build_case_evaluation_row(",
        )
        for token in forbidden_local_helpers:
            assert token not in case_eval_text
