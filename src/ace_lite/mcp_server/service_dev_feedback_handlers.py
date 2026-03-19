from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from ace_lite.dev_feedback_store import DevFeedbackStore


class DevIssueRecordResponse(TypedDict):
    ok: bool
    store_path: str
    issue: dict[str, Any]


class DevFixRecordResponse(TypedDict):
    ok: bool
    store_path: str
    fix: dict[str, Any]


class DevFeedbackSummaryResponse(TypedDict):
    ok: bool
    store_path: str
    summary: dict[str, Any]


def resolve_dev_feedback_store_path_for_request(
    *,
    store_path: str | None,
) -> str | None:
    return str(Path(store_path).expanduser().resolve()) if store_path else None


def handle_dev_issue_record_request(
    *,
    title: str,
    reason_code: str,
    repo: str,
    store_path: str | None,
    user_id: str | None,
    profile_key: str | None,
    query: str | None,
    selected_path: str | None,
    related_invocation_id: str | None,
    notes: str | None,
    status: str | None,
    created_at: str | None,
    updated_at: str | None,
    resolved_at: str | None,
    issue_id: str | None,
) -> DevIssueRecordResponse:
    store = DevFeedbackStore(
        db_path=resolve_dev_feedback_store_path_for_request(store_path=store_path)
    )
    issue = store.record_issue(
        {
            "issue_id": issue_id,
            "title": title,
            "reason_code": reason_code,
            "status": status,
            "repo": repo,
            "user_id": user_id,
            "profile_key": profile_key,
            "query": query,
            "selected_path": selected_path,
            "related_invocation_id": related_invocation_id,
            "notes": notes,
            "created_at": created_at,
            "updated_at": updated_at,
            "resolved_at": resolved_at,
        }
    )
    return {"ok": True, "store_path": str(store.db_path), "issue": issue.to_payload()}


def handle_dev_fix_record_request(
    *,
    reason_code: str,
    repo: str,
    resolution_note: str,
    store_path: str | None,
    user_id: str | None,
    profile_key: str | None,
    issue_id: str | None,
    query: str | None,
    selected_path: str | None,
    related_invocation_id: str | None,
    created_at: str | None,
    fix_id: str | None,
) -> DevFixRecordResponse:
    store = DevFeedbackStore(
        db_path=resolve_dev_feedback_store_path_for_request(store_path=store_path)
    )
    fix = store.record_fix(
        {
            "fix_id": fix_id,
            "issue_id": issue_id,
            "reason_code": reason_code,
            "repo": repo,
            "user_id": user_id,
            "profile_key": profile_key,
            "query": query,
            "selected_path": selected_path,
            "related_invocation_id": related_invocation_id,
            "resolution_note": resolution_note,
            "created_at": created_at,
        }
    )
    return {"ok": True, "store_path": str(store.db_path), "fix": fix.to_payload()}


def handle_dev_feedback_summary_request(
    *,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    store_path: str | None,
) -> DevFeedbackSummaryResponse:
    store = DevFeedbackStore(
        db_path=resolve_dev_feedback_store_path_for_request(store_path=store_path)
    )
    summary = store.summarize(repo=repo, user_id=user_id, profile_key=profile_key)
    return {"ok": True, "store_path": str(store.db_path), "summary": summary}


__all__ = [
    "DevFeedbackSummaryResponse",
    "DevFixRecordResponse",
    "DevIssueRecordResponse",
    "handle_dev_feedback_summary_request",
    "handle_dev_fix_record_request",
    "handle_dev_issue_record_request",
]
