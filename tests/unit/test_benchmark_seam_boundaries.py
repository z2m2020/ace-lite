from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestBenchmarkSeamBoundaries:
    def test_benchmark_report_uses_report_observability_seam(self) -> None:
        report_text = _read_repo_text("src/ace_lite/benchmark/report.py")

        expected_tokens = (
            "from ace_lite.benchmark.report_observability import (",
            "append_adaptive_router_observability_summary",
            "append_decision_observability_summary",
            "append_feedback_loop_summary",
            "append_feedback_observability_summary",
            "append_ltm_explainability_summary",
            "append_preference_observability_summary",
            "append_retrieval_control_plane_gate_summary",
            "append_reward_log_summary",
            "format_decision_event",
        )
        for token in expected_tokens:
            assert token in report_text

        forbidden_local_helpers = (
            "def _append_feedback_observability_summary(",
            "def _append_feedback_loop_summary(",
            "def _append_preference_observability_summary(",
            "def _append_retrieval_control_plane_gate_summary(",
            "def _append_reward_log_summary(",
            "def _append_adaptive_router_observability_summary(",
            "def _append_decision_observability_summary(",
        )
        for token in forbidden_local_helpers:
            assert token not in report_text

    def test_case_evaluation_entry_uses_helper_seams(self) -> None:
        case_eval_text = _read_repo_text("src/ace_lite/benchmark/case_evaluation.py")

        expected_tokens = (
            "from ace_lite.benchmark.case_evaluation_context import build_candidate_context",
            "from ace_lite.benchmark.case_evaluation_details import classify_chunk_stage_miss",
            "build_case_evaluation_diagnostics",
            "collect_candidate_match_details",
            "collect_chunk_match_details",
            "build_case_evaluation_metrics",
            "build_case_detail_payload",
            "coerce_chunk_refs",
            "build_case_evaluation_row",
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
