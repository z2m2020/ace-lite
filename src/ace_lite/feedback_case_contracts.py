"""Shared lifecycle metadata helpers for feedback-related benchmark cases."""

from __future__ import annotations

from typing import Any, Protocol

_RESOLVED_STATUSES = {"resolved", "fixed", "closed"}


class _PayloadLike(Protocol):
    def to_payload(self) -> dict[str, Any]: ...


def derive_issue_report_feedback_context(
    *,
    report: _PayloadLike | dict[str, Any],
) -> dict[str, Any]:
    report_payload = report.to_payload() if hasattr(report, "to_payload") else dict(report)
    created_at = str(
        report_payload.get("occurred_at") or report_payload.get("created_at") or ""
    ).strip()
    resolved_at = str(report_payload.get("resolved_at") or "").strip()
    resolved = bool(resolved_at) or (
        str(report_payload.get("status") or "").strip().lower() in _RESOLVED_STATUSES
    )
    return {
        "created_at": created_at,
        "resolved_at": resolved_at,
        "resolved": resolved,
    }


def derive_dev_feedback_case_payload(
    *,
    report: _PayloadLike | dict[str, Any],
) -> dict[str, Any] | None:
    report_payload = report.to_payload() if hasattr(report, "to_payload") else dict(report)
    attachments = [
        str(item).strip()
        for item in report_payload.get("attachments", ())
        if str(item).strip()
    ]
    fix_refs = [item for item in attachments if item.startswith("dev-fix://")]
    if not fix_refs:
        return None

    resolved_statuses = {"resolved", "fixed", "closed"}
    resolved = bool(str(report_payload.get("resolved_at") or "").strip()) or (
        str(report_payload.get("status") or "").strip().lower() in resolved_statuses
    )
    payload: dict[str, Any] = {
        "issue_count": 1,
        "linked_fix_issue_count": 1,
        "resolved_issue_count": 1 if resolved else 0,
    }
    context = derive_issue_report_feedback_context(report=report_payload)
    if context["created_at"]:
        payload["created_at"] = context["created_at"]
    if context["resolved_at"]:
        payload["resolved_at"] = context["resolved_at"]
    return payload


__all__ = ["derive_dev_feedback_case_payload", "derive_issue_report_feedback_context"]
