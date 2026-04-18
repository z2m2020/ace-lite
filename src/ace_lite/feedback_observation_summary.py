from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.issue_report_store import IssueReportStore


def _resolve_root_path(root: str | Path | None) -> Path:
    candidate = Path(root or Path.cwd()).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _resolve_issue_store_path(*, root_path: Path, store_path: str | Path | None) -> Path:
    target = Path(store_path).expanduser() if store_path else root_path / "context-map" / "issue_reports.db"
    if not target.is_absolute():
        target = root_path / target
    return target.resolve()


def build_feedback_observation_overview(
    *,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    root: str | Path | None,
    dev_feedback_store_path: str | Path | None,
    issue_store_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, Any]:
    root_was_explicit = root is not None
    root_path = _resolve_root_path(root)
    dev_store = DevFeedbackStore(db_path=dev_feedback_store_path)
    issue_store = IssueReportStore(
        db_path=_resolve_issue_store_path(root_path=root_path, store_path=issue_store_path)
    )
    feedback_store = SelectionFeedbackStore(
        profile_path=profile_path or "~/.ace-lite/profile.json"
    )

    developer_feedback = dev_store.summarize(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
    )
    issue_reports = issue_store.summarize(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
    )
    issue_report_scope = "filtered"
    if (
        int(issue_reports.get("report_count", 0) or 0) <= 0
        and str(repo or "").strip()
        and (str(user_id or "").strip() or str(profile_key or "").strip())
    ):
        issue_reports = issue_store.summarize(repo=repo)
        issue_report_scope = "repo_fallback"
    issue_scope_diagnostics = {
        "root_path": str(root_path),
        "root_source": "explicit" if root_was_explicit else "process_cwd",
        "store_path": str(issue_store.db_path),
        "issue_store_path_source": "explicit" if issue_store_path else "default_under_root",
        "repo_filter": str(repo or "").strip(),
        "user_id_filter": str(user_id or "").strip(),
        "profile_key_filter": str(profile_key or "").strip(),
        "repo_fallback_applied": issue_report_scope == "repo_fallback",
    }
    if (
        int(issue_reports.get("report_count", 0) or 0) <= 0
        and str(repo or "").strip()
        and not root_was_explicit
    ):
        issue_scope_diagnostics["warning"] = (
            "issue reports are scoped by the resolved root; pass root explicitly "
            "when validating another repository"
        )
    selection_feedback = feedback_store.stats(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        top_n=5,
    )
    return {
        "repo": str(repo or "").strip(),
        "root": str(root_path),
        "developer_feedback": {
            "issue_count": int(developer_feedback.get("issue_count", 0) or 0),
            "open_issue_count": int(developer_feedback.get("open_issue_count", 0) or 0),
            "resolved_issue_count": int(developer_feedback.get("resolved_issue_count", 0) or 0),
            "fix_count": int(developer_feedback.get("fix_count", 0) or 0),
            "linked_fix_issue_count": int(
                developer_feedback.get("linked_fix_issue_count", 0) or 0
            ),
        },
        "issue_reports": {
            "report_count": int(issue_reports.get("report_count", 0) or 0),
            "open_issue_count": int(issue_reports.get("open_issue_count", 0) or 0),
            "resolved_issue_count": int(issue_reports.get("resolved_issue_count", 0) or 0),
            "latest_occurred_at": str(issue_reports.get("latest_occurred_at") or ""),
            "scope": issue_report_scope,
            "scope_diagnostics": issue_scope_diagnostics,
            "by_status": list(issue_reports.get("by_status", [])),
            "by_category": list(issue_reports.get("by_category", []))[:5],
        },
        "selection_feedback": {
            "event_count": int(selection_feedback.get("event_count", 0) or 0),
            "matched_event_count": int(selection_feedback.get("matched_event_count", 0) or 0),
            "unique_paths": int(selection_feedback.get("unique_paths", 0) or 0),
            "capture_event_count": int(selection_feedback.get("capture_event_count", 0) or 0),
            "capture_coverage": selection_feedback.get("capture_coverage"),
            "top_paths": list(selection_feedback.get("paths", []))[:5],
        },
        "cross_store_gaps": {
            "issue_report_without_dev_issue_count": max(
                0,
                int(issue_reports.get("open_issue_count", 0) or 0)
                - int(developer_feedback.get("open_issue_count", 0) or 0),
            ),
            "has_split_feedback_signals": bool(
                int(issue_reports.get("report_count", 0) or 0) > 0
                or int(selection_feedback.get("event_count", 0) or 0) > 0
            ),
        },
    }


__all__ = ["build_feedback_observation_overview"]
