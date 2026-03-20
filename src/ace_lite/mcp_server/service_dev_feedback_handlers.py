from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.dev_feedback_runtime_linkage import (
    record_dev_issue_from_runtime_invocation,
    resolve_runtime_stats_store_path,
)
from ace_lite.memory_long_term import build_long_term_capture_service_from_runtime


class DevIssueRecordResponse(TypedDict):
    ok: bool
    store_path: str
    issue: dict[str, Any]
    long_term_capture: dict[str, Any] | None


class DevFixRecordResponse(TypedDict):
    ok: bool
    store_path: str
    fix: dict[str, Any]
    long_term_capture: dict[str, Any] | None


class DevFeedbackSummaryResponse(TypedDict):
    ok: bool
    store_path: str
    summary: dict[str, Any]


class DevIssueFromRuntimeResponse(TypedDict):
    ok: bool
    store_path: str
    stats_db_path: str
    issue: dict[str, Any]
    invocation: dict[str, Any]
    long_term_capture: dict[str, Any] | None


class DevIssueApplyFixResponse(TypedDict):
    ok: bool
    store_path: str
    issue: dict[str, Any]
    fix: dict[str, Any]
    long_term_capture: dict[str, Any] | None


def resolve_dev_feedback_store_path_for_request(
    *,
    store_path: str | None,
) -> str | None:
    return str(Path(store_path).expanduser().resolve()) if store_path else None


def _build_long_term_capture_service_for_request(*, root_path: Path | None) -> Any:
    if root_path is None:
        return None
    try:
        return build_long_term_capture_service_from_runtime(root=root_path)
    except Exception:
        return None


def _capture_long_term_event(
    *,
    service: Any,
    stage_name: str,
    operation: Any,
) -> dict[str, Any] | None:
    if service is None:
        return None
    try:
        payload = operation()
    except Exception as exc:
        return {
            "ok": False,
            "skipped": False,
            "stage": stage_name,
            "reason": f"capture_failed:{exc.__class__.__name__}",
        }
    return dict(payload) if isinstance(payload, dict) else None


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
    root_path: Path | None = None,
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
    long_term_capture_service = _build_long_term_capture_service_for_request(
        root_path=root_path
    )
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_issue",
        operation=lambda: long_term_capture_service.capture_dev_issue(
            issue=issue.to_payload(),
            root=str(root_path) if root_path is not None else "",
        ),
    )
    return {
        "ok": True,
        "store_path": str(store.db_path),
        "issue": issue.to_payload(),
        "long_term_capture": long_term_capture,
    }


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
    root_path: Path | None = None,
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
    long_term_capture_service = _build_long_term_capture_service_for_request(
        root_path=root_path
    )
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_fix",
        operation=lambda: long_term_capture_service.capture_dev_fix(
            fix=fix.to_payload(),
            root=str(root_path) if root_path is not None else "",
        ),
    )
    return {
        "ok": True,
        "store_path": str(store.db_path),
        "fix": fix.to_payload(),
        "long_term_capture": long_term_capture,
    }


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


def handle_dev_issue_from_runtime_request(
    *,
    invocation_id: str,
    stats_db_path: str | None,
    store_path: str | None,
    reason_code: str | None,
    title: str | None,
    notes: str | None,
    status: str | None,
    user_id: str | None,
    profile_key: str | None,
    issue_id: str | None,
    root_path: Path | None = None,
) -> DevIssueFromRuntimeResponse:
    issue, invocation, resolved_store_path, resolved_stats_db_path = (
        record_dev_issue_from_runtime_invocation(
            invocation_id=invocation_id,
            stats_db_path=resolve_runtime_stats_store_path(
                stats_db_path=stats_db_path
            ),
            store_path=resolve_dev_feedback_store_path_for_request(
                store_path=store_path
            ),
            reason_code=reason_code,
            title=title,
            notes=notes,
            status=status,
            user_id=user_id,
            profile_key=profile_key,
            issue_id=issue_id,
        )
    )
    long_term_capture_service = _build_long_term_capture_service_for_request(
        root_path=root_path
    )
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_issue",
        operation=lambda: long_term_capture_service.capture_dev_issue(
            issue=issue.to_payload(),
            root=str(root_path) if root_path is not None else "",
        ),
    )
    return {
        "ok": True,
        "store_path": resolved_store_path,
        "stats_db_path": resolved_stats_db_path,
        "issue": issue.to_payload(),
        "invocation": invocation.to_payload(),
        "long_term_capture": long_term_capture,
    }


def handle_dev_issue_apply_fix_request(
    *,
    issue_id: str,
    fix_id: str,
    store_path: str | None,
    status: str | None,
    resolved_at: str | None,
    root_path: Path | None = None,
) -> DevIssueApplyFixResponse:
    store = DevFeedbackStore(
        db_path=resolve_dev_feedback_store_path_for_request(store_path=store_path)
    )
    issue = store.apply_fix(
        issue_id=issue_id,
        fix_id=fix_id,
        status=status or "fixed",
        resolved_at=resolved_at,
    )
    fix = store.get_fix(fix_id)
    if fix is None:
        raise KeyError(f"developer fix not found: {fix_id}")
    long_term_capture_service = _build_long_term_capture_service_for_request(
        root_path=root_path
    )
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_issue_resolution",
        operation=lambda: long_term_capture_service.capture_dev_issue_resolution(
            issue=issue.to_payload(),
            fix=fix.to_payload(),
            root=str(root_path) if root_path is not None else "",
        ),
    )
    return {
        "ok": True,
        "store_path": str(store.db_path),
        "issue": issue.to_payload(),
        "fix": fix.to_payload(),
        "long_term_capture": long_term_capture,
    }


__all__ = [
    "DevFeedbackSummaryResponse",
    "DevIssueApplyFixResponse",
    "DevIssueFromRuntimeResponse",
    "DevFixRecordResponse",
    "DevIssueRecordResponse",
    "handle_dev_issue_apply_fix_request",
    "handle_dev_feedback_summary_request",
    "handle_dev_issue_from_runtime_request",
    "handle_dev_fix_record_request",
    "handle_dev_issue_record_request",
]
