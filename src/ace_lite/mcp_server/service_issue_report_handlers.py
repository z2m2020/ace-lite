from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from typing_extensions import NotRequired

from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.issue_report_store import IssueReportStore


class IssueReportRecordResponse(TypedDict):
    ok: bool
    root: str
    repo: str
    store_path: str
    report: dict[str, Any]
    workflow_hints: NotRequired[dict[str, Any]]


class IssueReportListResponse(TypedDict):
    ok: bool
    root: str
    repo: str | None
    store_path: str
    count: int
    reports: list[dict[str, Any]]


class IssueReportExportCaseResponse(TypedDict):
    ok: bool
    root: str
    repo: str
    store_path: str
    output_path: str
    case_count: int
    case: dict[str, Any]
    report: dict[str, Any]


class IssueReportApplyFixResponse(TypedDict):
    ok: bool
    root: str
    repo: str
    issue_store_path: str
    dev_feedback_path: str
    report: dict[str, Any]
    fix: dict[str, Any]
    workflow_hints: NotRequired[dict[str, Any]]


def resolve_issue_report_store_path(
    *,
    root_path: Path,
    store_path: str | None,
) -> Path:
    target = (
        Path(store_path).expanduser()
        if store_path
        else root_path / "context-map" / "issue_reports.db"
    )
    if not target.is_absolute():
        target = root_path / target
    return target.resolve()


def _build_issue_report_record_workflow_hints(
    *,
    repo: str,
    issue_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "issue_report_feedback_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_issue_report_list",
                "reason": "确认新 issue 已按预期写入, 并且可以通过筛选条件查询到。",
                "suggested_args": {
                    "repo": repo,
                    "status": "open",
                    "limit": 20,
                },
            },
            {
                "tool": "ace_dev_issue_record",
                "reason": "如果这是工具链或运行时问题, 把它镜像到开发者侧 triage。",
                "suggested_args": {
                    "repo": repo,
                    "query": "<same query>",
                    "title": "<same title>",
                    "reason_code": "general",
                },
            },
            {
                "tool": "ace_issue_report_export_case",
                "reason": "把该 issue 导出为 benchmark case, 便于后续回归跟踪。",
                "suggested_args": {
                    "issue_id": issue_id,
                    "comparison_lane": "issue_report_feedback",
                    "top_k": 8,
                },
            },
        ],
        "template_fields": [
            "title",
            "query",
            "actual_behavior",
            "expected_behavior",
            "category",
            "severity",
            "repro_steps",
            "attachments",
        ],
    }


def _build_issue_report_resolution_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    fix_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "issue_report_resolution_v1",
        "recommended_next_steps": [
            {
                "tool": "ace_issue_report_list",
                "reason": "确认 issue 状态已经从 open triage 迁出。",
                "suggested_args": {
                    "repo": repo,
                    "status": "resolved",
                    "limit": 20,
                },
            },
            {
                "tool": "ace_issue_report_export_case",
                "reason": "把已解决行为沉淀到 benchmark lane。",
                "suggested_args": {
                    "issue_id": issue_id,
                    "comparison_lane": "dev_feedback_resolution",
                    "top_k": 8,
                },
            },
            {
                "tool": "ace_dev_feedback_summary",
                "reason": "在应用 fix 后检查 dev issue 到 fix 的闭环情况。",
                "suggested_args": {
                    "repo": repo,
                },
            },
        ],
        "linked_fix_id": fix_id,
    }


def handle_issue_report_record_request(
    *,
    title: str,
    query: str,
    actual_behavior: str,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    root_path: Path,
    default_repo: str,
    store_path: str | None,
    category: str | None,
    severity: str | None,
    status: str | None,
    expected_behavior: str | None,
    repro_steps: list[str] | None,
    selected_path: str | None,
    plan_payload_ref: str | None,
    attachments: list[str] | None,
    occurred_at: str | None,
    resolved_at: str | None,
    resolution_note: str | None,
    issue_id: str | None = None,
) -> IssueReportRecordResponse:
    resolved_repo = str(repo or default_repo).strip() or default_repo
    path = resolve_issue_report_store_path(root_path=root_path, store_path=store_path)
    store = IssueReportStore(db_path=path)
    report = store.record(
        {
            "issue_id": issue_id,
            "title": title,
            "category": category,
            "severity": severity,
            "status": status,
            "query": query,
            "repo": resolved_repo,
            "root": str(root_path),
            "user_id": user_id,
            "profile_key": profile_key,
            "expected_behavior": expected_behavior,
            "actual_behavior": actual_behavior,
            "repro_steps": list(repro_steps or []),
            "plan_payload_ref": plan_payload_ref,
            "selected_path": selected_path,
            "attachments": list(attachments or []),
            "occurred_at": occurred_at,
            "resolved_at": resolved_at,
            "resolution_note": resolution_note,
        },
        root_path=root_path,
    )
    payload: IssueReportRecordResponse = {
        "ok": True,
        "root": str(root_path),
        "repo": resolved_repo,
        "store_path": str(store.db_path),
        "report": report.to_payload(),
        "workflow_hints": _build_issue_report_record_workflow_hints(
            repo=resolved_repo,
            issue_id=report.issue_id,
        ),
    }
    return payload


def handle_issue_report_list_request(
    *,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    root_path: Path,
    store_path: str | None,
    status: str | None,
    category: str | None,
    severity: str | None,
    limit: int,
) -> IssueReportListResponse:
    path = resolve_issue_report_store_path(root_path=root_path, store_path=store_path)
    store = IssueReportStore(db_path=path)
    reports = store.list_reports(
        repo=repo,
        status=status,
        user_id=user_id,
        profile_key=profile_key,
        category=category,
        severity=severity,
        limit=limit,
    )
    return {
        "ok": True,
        "root": str(root_path),
        "repo": repo,
        "store_path": str(store.db_path),
        "count": len(reports),
        "reports": [item.to_payload() for item in reports],
    }


def handle_issue_report_export_case_request(
    *,
    issue_id: str,
    root_path: Path,
    store_path: str | None,
    output_path: str,
    case_id: str | None,
    comparison_lane: str,
    top_k: int,
    min_validation_tests: int,
    append: bool,
) -> IssueReportExportCaseResponse:
    path = resolve_issue_report_store_path(root_path=root_path, store_path=store_path)
    target_output_path = Path(output_path).expanduser()
    if not target_output_path.is_absolute():
        target_output_path = (root_path / target_output_path).resolve()
    store = IssueReportStore(db_path=path)
    payload = store.export_case(
        issue_id=issue_id,
        output_path=target_output_path,
        case_id=case_id,
        comparison_lane=comparison_lane,
        top_k=top_k,
        min_validation_tests=min_validation_tests,
        append=append,
    )
    report = payload["report"]
    return {
        "ok": True,
        "root": str(root_path),
        "repo": str(report.get("repo") or ""),
        "store_path": str(store.db_path),
        "output_path": str(payload["output_path"]),
        "case_count": int(payload["case_count"]),
        "case": dict(payload["case"]),
        "report": dict(report),
    }


def handle_issue_report_apply_fix_request(
    *,
    issue_id: str,
    fix_id: str,
    root_path: Path,
    issue_store_path: str | None,
    dev_feedback_path: str | None,
    status: str,
    resolved_at: str | None,
) -> IssueReportApplyFixResponse:
    issue_path = resolve_issue_report_store_path(
        root_path=root_path,
        store_path=issue_store_path,
    )
    issue_store = IssueReportStore(db_path=issue_path)
    dev_store = DevFeedbackStore(db_path=dev_feedback_path)
    fix = dev_store.get_fix(fix_id)
    if fix is None:
        raise KeyError(f"dev fix not found: {fix_id}")
    report = issue_store.resolve_with_fix(
        issue_id=issue_id,
        fix=fix,
        resolved_at=resolved_at,
        status=status,
    )
    payload: IssueReportApplyFixResponse = {
        "ok": True,
        "root": str(root_path),
        "repo": report.repo,
        "issue_store_path": str(issue_store.db_path),
        "dev_feedback_path": str(dev_store.db_path),
        "report": report.to_payload(),
        "fix": fix.to_payload(),
        "workflow_hints": _build_issue_report_resolution_workflow_hints(
            repo=report.repo,
            issue_id=report.issue_id,
            fix_id=fix.fix_id,
        ),
    }
    return payload


__all__ = [
    "IssueReportApplyFixResponse",
    "IssueReportExportCaseResponse",
    "IssueReportListResponse",
    "IssueReportRecordResponse",
    "handle_issue_report_apply_fix_request",
    "handle_issue_report_export_case_request",
    "handle_issue_report_list_request",
    "handle_issue_report_record_request",
    "resolve_issue_report_store_path",
]
