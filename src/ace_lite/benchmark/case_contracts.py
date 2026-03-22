"""Benchmark case normalization helpers."""

from __future__ import annotations

from typing import Any

from ace_lite.feedback_case_contracts import derive_dev_feedback_case_payload
from ace_lite.feedback_case_contracts import derive_issue_report_feedback_context

_DEV_ISSUE_CAPTURE_SURFACES = {
    "runtime_issue_capture_cli",
    "runtime_issue_capture_mcp",
}

_DEV_FEEDBACK_RESOLUTION_SURFACES = {
    "issue_resolution_cli",
    "issue_resolution_mcp",
}


def derive_benchmark_case_dev_feedback(case: dict[str, Any]) -> dict[str, Any]:
    dev_feedback_raw = case.get("dev_feedback")
    if isinstance(dev_feedback_raw, dict):
        return dict(dev_feedback_raw)

    issue_report_raw = case.get("issue_report")
    issue_report = issue_report_raw if isinstance(issue_report_raw, dict) else {}
    issue_report_context = derive_issue_report_feedback_context(report=issue_report)
    derived_from_issue_report = derive_dev_feedback_case_payload(report=issue_report)
    if derived_from_issue_report is not None:
        return derived_from_issue_report

    comparison_lane = str(case.get("comparison_lane") or "").strip()
    feedback_surface = str(case.get("feedback_surface") or "").strip()

    if (
        comparison_lane == "dev_issue_capture"
        or feedback_surface in _DEV_ISSUE_CAPTURE_SURFACES
    ):
        payload: dict[str, Any] = {"issue_count": 1}
        if issue_report_context["created_at"]:
            payload["created_at"] = issue_report_context["created_at"]
        return payload

    if (
        comparison_lane == "dev_feedback_resolution"
        or feedback_surface in _DEV_FEEDBACK_RESOLUTION_SURFACES
    ):
        payload = {
            "issue_count": 1,
            "linked_fix_issue_count": 1,
            "resolved_issue_count": 1 if issue_report_context["resolved"] or not issue_report else 0,
        }
        if issue_report_context["created_at"]:
            payload["created_at"] = issue_report_context["created_at"]
        if issue_report_context["resolved_at"]:
            payload["resolved_at"] = issue_report_context["resolved_at"]
        return payload

    return {}


def normalize_benchmark_case(case: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(case)
    dev_feedback = derive_benchmark_case_dev_feedback(normalized)
    if dev_feedback:
        normalized["dev_feedback"] = dev_feedback
    return normalized


__all__ = ["derive_benchmark_case_dev_feedback", "normalize_benchmark_case"]
