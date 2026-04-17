from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from typing_extensions import NotRequired

from ace_lite.dev_feedback_runtime_linkage import (
    record_dev_issue_from_runtime_invocation,
    resolve_runtime_stats_store_path,
)
from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_observation_summary import build_feedback_observation_overview
from ace_lite.memory_long_term import build_long_term_capture_service_from_runtime


class DevIssueRecordResponse(TypedDict):
    ok: bool
    store_path: str
    issue: dict[str, Any]
    long_term_capture: dict[str, Any] | None
    workflow_hints: NotRequired[dict[str, Any]]


class DevFixRecordResponse(TypedDict):
    ok: bool
    store_path: str
    fix: dict[str, Any]
    long_term_capture: dict[str, Any] | None
    workflow_hints: NotRequired[dict[str, Any]]


class DevFeedbackSummaryResponse(TypedDict):
    ok: bool
    store_path: str
    summary: dict[str, Any]
    observation_overview: NotRequired[dict[str, Any]]
    workflow_hints: NotRequired[dict[str, Any]]


class DevIssueFromRuntimeResponse(TypedDict):
    ok: bool
    store_path: str
    stats_db_path: str
    issue: dict[str, Any]
    invocation: dict[str, Any]
    long_term_capture: dict[str, Any] | None
    workflow_hints: NotRequired[dict[str, Any]]


class DevIssueApplyFixResponse(TypedDict):
    ok: bool
    store_path: str
    issue: dict[str, Any]
    fix: dict[str, Any]
    long_term_capture: dict[str, Any] | None
    workflow_hints: NotRequired[dict[str, Any]]


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


def _build_dev_issue_workflow_hints(
    *,
    repo: str,
    issue_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "dev_issue_triage_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_dev_feedback_summary",
                "reason": "先看聚合后的问题压力, 再决定优先修哪一类。",
                "suggested_args": {"repo": repo},
            },
            {
                "tool": "ace_dev_fix_record",
                "reason": "一旦有明确修复或缓解措施, 就先记录 fix。",
                "suggested_args": {
                    "repo": repo,
                    "issue_id": issue_id,
                    "reason_code": "general",
                    "resolution_note": "<what was changed>",
                },
            },
            {
                "tool": "ace_dev_issue_apply_fix",
                "reason": "在 fix 关联并验证后, 关闭 issue 状态。",
                "suggested_args": {
                    "issue_id": issue_id,
                    "fix_id": "<dev_fix_id>",
                    "status": "fixed",
                },
            },
        ],
    }


def _build_dev_fix_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    fix_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "dev_fix_linking_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_dev_issue_apply_fix",
                "reason": "把当前 fix 应用到一个 open 的开发者 issue 上。",
                "suggested_args": {
                    "issue_id": issue_id or "<dev_issue_id>",
                    "fix_id": fix_id,
                    "status": "fixed",
                },
            },
            {
                "tool": "ace_dev_feedback_summary",
                "reason": "确认关联 fix 之后 open issue 数量是否下降。",
                "suggested_args": {"repo": repo},
            },
        ],
    }


def _build_dev_summary_workflow_hints(
    *,
    repo: str | None,
    summary: dict[str, Any],
    observation_overview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_repo = str(repo or "").strip()
    issue_count = int(summary.get("issue_count", 0) or 0)
    open_issue_count = int(summary.get("open_issue_count", 0) or 0)
    observation = dict(observation_overview or {})
    issue_reports = dict(observation.get("issue_reports", {}))
    selection_feedback = dict(observation.get("selection_feedback", {}))
    cross_store_gaps = dict(observation.get("cross_store_gaps", {}))
    issue_report_open_count = int(issue_reports.get("open_issue_count", 0) or 0)
    selection_event_count = int(selection_feedback.get("event_count", 0) or 0)
    if issue_count <= 0 and issue_report_open_count > 0:
        return {
            "workflow": "dev_feedback_issue_bridge_v1",
            "recommended_next_steps": [
                {
                    "tool": "ace_issue_report_list",
                    "reason": "先看用户侧 open issues，再决定哪些需要镜像到开发侧 triage。",
                    "suggested_args": {
                        "repo": normalized_repo or None,
                        "status": "open",
                        "limit": 20,
                    },
                },
                {
                    "tool": "ace_dev_issue_record",
                    "reason": "把高价值 issue_report 镜像到开发者 issue 闭环。",
                    "suggested_args": {
                        "repo": normalized_repo or "<repo>",
                        "title": "<issue title>",
                        "reason_code": "general",
                    },
                },
            ],
        }
    if issue_count <= 0:
        return {
            "workflow": "dev_feedback_bootstrap_v1",
            "recommended_next_steps": [
                {
                    "tool": "ace_dev_issue_record",
                    "reason": "先沉淀第一条开发或运行时痛点。",
                    "suggested_args": {
                        "repo": normalized_repo or "<repo>",
                        "title": "<issue title>",
                        "reason_code": "general",
                    },
                },
                {
                    "tool": "ace_dev_issue_from_runtime",
                    "reason": "把降级运行时调用提升为 triage issue。",
                    "suggested_args": {
                        "invocation_id": "<runtime_invocation_id>",
                        "repo": normalized_repo or "<repo>",
                    },
                },
            ],
        }
    if open_issue_count > 0:
        return {
            "workflow": "dev_feedback_closure_v1",
            "recommended_next_steps": [
                {
                    "tool": "ace_dev_fix_record",
                    "reason": "为尚未解决的 issue 记录 fix 或缓解措施。",
                    "suggested_args": {
                        "repo": normalized_repo or "<repo>",
                        "issue_id": "<open_issue_id>",
                        "reason_code": "general",
                        "resolution_note": "<what was changed>",
                    },
                },
                {
                    "tool": "ace_dev_issue_apply_fix",
                    "reason": "在 fix 验证通过后, 把 issue 标记为 fixed。",
                    "suggested_args": {
                        "issue_id": "<open_issue_id>",
                        "fix_id": "<dev_fix_id>",
                        "status": "fixed",
                    },
                },
            ],
        }
    if selection_event_count > 0 or int(
        cross_store_gaps.get("issue_report_without_dev_issue_count", 0) or 0
    ) > 0:
        return {
            "workflow": "feedback_observability_v1",
            "recommended_next_steps": [
                {
                    "tool": "ace_issue_report_list",
                    "reason": "对照 issue_report 和 dev_feedback 的落差，确认是否还有未镜像的问题。",
                    "suggested_args": {
                        "repo": normalized_repo or None,
                        "limit": 20,
                    },
                },
                {
                    "tool": "ace_dev_feedback_summary",
                    "reason": "继续跟踪统一观察面里的闭环差距。",
                    "suggested_args": {"repo": normalized_repo or None},
                },
            ],
        }
    return {
        "workflow": "dev_feedback_maintenance_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_dev_feedback_summary",
                "reason": "继续跟踪 reason-code 趋势和闭环率。",
                "suggested_args": {"repo": normalized_repo or None},
            }
        ],
    }


def _build_dev_issue_from_runtime_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    invocation_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "runtime_issue_promotion_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_dev_fix_record",
                "reason": "记录与当前运行时调用关联的 fix 或缓解措施。",
                "suggested_args": {
                    "repo": repo,
                    "issue_id": issue_id,
                    "related_invocation_id": invocation_id,
                    "resolution_note": "<mitigation summary>",
                },
            },
            {
                "tool": "ace_dev_issue_apply_fix",
                "reason": "在 mitigation 确认后关闭该 promoted issue。",
                "suggested_args": {
                    "issue_id": issue_id,
                    "fix_id": "<dev_fix_id>",
                    "status": "fixed",
                },
            },
        ],
    }


def _build_dev_issue_resolution_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    fix_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "dev_issue_resolution_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_dev_feedback_summary",
                "reason": "在 issue 解决后检查闭环指标。",
                "suggested_args": {"repo": repo},
            },
            {
                "tool": "ace_issue_report_apply_fix",
                "reason": "如有需要, 把同一个 fix 传播到关联 issue report。",
                "suggested_args": {
                    "issue_id": issue_id,
                    "fix_id": fix_id,
                    "status": "resolved",
                },
            },
        ],
    }


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
    payload: DevIssueRecordResponse = {
        "ok": True,
        "store_path": str(store.db_path),
        "issue": issue.to_payload(),
        "long_term_capture": long_term_capture,
        "workflow_hints": _build_dev_issue_workflow_hints(
            repo=issue.repo,
            issue_id=issue.issue_id,
        ),
    }
    return payload


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
    payload: DevFixRecordResponse = {
        "ok": True,
        "store_path": str(store.db_path),
        "fix": fix.to_payload(),
        "long_term_capture": long_term_capture,
        "workflow_hints": _build_dev_fix_workflow_hints(
            repo=fix.repo,
            issue_id=fix.issue_id,
            fix_id=fix.fix_id,
        ),
    }
    return payload


def handle_dev_feedback_summary_request(
    *,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    store_path: str | None,
    root_path: Path | None = None,
    issue_store_path: str | None = None,
    profile_path: str | None = None,
) -> DevFeedbackSummaryResponse:
    store = DevFeedbackStore(
        db_path=resolve_dev_feedback_store_path_for_request(store_path=store_path)
    )
    summary = store.summarize(repo=repo, user_id=user_id, profile_key=profile_key)
    observation_overview = build_feedback_observation_overview(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        root=root_path,
        dev_feedback_store_path=str(store.db_path),
        issue_store_path=issue_store_path,
        profile_path=profile_path,
    )
    payload: DevFeedbackSummaryResponse = {
        "ok": True,
        "store_path": str(store.db_path),
        "summary": summary,
        "observation_overview": observation_overview,
        "workflow_hints": _build_dev_summary_workflow_hints(
            repo=repo,
            summary=summary,
            observation_overview=observation_overview,
        ),
    }
    return payload


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
    payload: DevIssueFromRuntimeResponse = {
        "ok": True,
        "store_path": resolved_store_path,
        "stats_db_path": resolved_stats_db_path,
        "issue": issue.to_payload(),
        "invocation": invocation.to_payload(),
        "long_term_capture": long_term_capture,
        "workflow_hints": _build_dev_issue_from_runtime_workflow_hints(
            repo=issue.repo,
            issue_id=issue.issue_id,
            invocation_id=invocation.invocation_id,
        ),
    }
    return payload


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
    payload: DevIssueApplyFixResponse = {
        "ok": True,
        "store_path": str(store.db_path),
        "issue": issue.to_payload(),
        "fix": fix.to_payload(),
        "long_term_capture": long_term_capture,
        "workflow_hints": _build_dev_issue_resolution_workflow_hints(
            repo=issue.repo,
            issue_id=issue.issue_id,
            fix_id=fix.fix_id,
        ),
    }
    return payload


__all__ = [
    "DevFeedbackSummaryResponse",
    "DevFixRecordResponse",
    "DevIssueApplyFixResponse",
    "DevIssueFromRuntimeResponse",
    "DevIssueRecordResponse",
    "handle_dev_feedback_summary_request",
    "handle_dev_fix_record_request",
    "handle_dev_issue_apply_fix_request",
    "handle_dev_issue_from_runtime_request",
    "handle_dev_issue_record_request",
]
