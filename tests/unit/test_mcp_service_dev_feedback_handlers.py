from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.mcp_server.service_dev_feedback_handlers import (
    handle_dev_feedback_summary_request,
    handle_dev_fix_record_request,
    handle_dev_issue_record_request,
    resolve_dev_feedback_store_path_for_request,
)


def test_resolve_dev_feedback_store_path_for_request_expands_path(tmp_path: Path) -> None:
    resolved = resolve_dev_feedback_store_path_for_request(
        store_path=str(tmp_path / "context-map" / "dev-feedback.db")
    )

    assert resolved == str((tmp_path / "context-map" / "dev-feedback.db").resolve())


def test_handle_dev_feedback_round_trip(tmp_path: Path) -> None:
    store_path = str(tmp_path / "context-map" / "dev-feedback.db")

    recorded_issue = handle_dev_issue_record_request(
        title="Memory fallback while planning",
        reason_code="memory_fallback",
        repo="demo",
        store_path=store_path,
        user_id="mcp-user",
        profile_key="bugfix",
        query="why did memory fallback",
        selected_path=r".\src\planner.py",
        related_invocation_id="inv-123",
        notes="first report",
        status="open",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:00:00+00:00",
        resolved_at=None,
        issue_id="devi_memory_fallback",
    )
    recorded_fix = handle_dev_fix_record_request(
        reason_code="memory_fallback",
        repo="demo",
        resolution_note="added fallback diagnostics",
        store_path=store_path,
        user_id="mcp-user",
        profile_key="bugfix",
        issue_id="devi_memory_fallback",
        query="why did memory fallback",
        selected_path="src/planner.py",
        related_invocation_id="inv-123",
        created_at="2026-03-19T00:05:00+00:00",
        fix_id="devf_memory_fallback",
    )
    summary = handle_dev_feedback_summary_request(
        repo="demo",
        user_id="mcp-user",
        profile_key="bugfix",
        store_path=store_path,
    )

    assert recorded_issue["ok"] is True
    assert recorded_issue["issue"]["selected_path"] == "src/planner.py"
    assert recorded_fix["ok"] is True
    assert recorded_fix["fix"]["issue_id"] == "devi_memory_fallback"
    assert summary["ok"] is True
    assert summary["summary"]["issue_count"] == 1
    assert summary["summary"]["open_issue_count"] == 1
    assert summary["summary"]["fix_count"] == 1
    assert summary["summary"]["by_reason_code"][0]["reason_code"] == "memory_fallback"


def test_handle_dev_feedback_requires_required_fields(tmp_path: Path) -> None:
    store_path = str(tmp_path / "context-map" / "dev-feedback.db")

    with pytest.raises(ValueError, match="title cannot be empty"):
        handle_dev_issue_record_request(
            title=" ",
            reason_code="memory_fallback",
            repo="demo",
            store_path=store_path,
            user_id=None,
            profile_key=None,
            query=None,
            selected_path=None,
            related_invocation_id=None,
            notes=None,
            status=None,
            created_at=None,
            updated_at=None,
            resolved_at=None,
            issue_id=None,
        )

    with pytest.raises(ValueError, match="resolution_note cannot be empty"):
        handle_dev_fix_record_request(
            reason_code="memory_fallback",
            repo="demo",
            resolution_note=" ",
            store_path=store_path,
            user_id=None,
            profile_key=None,
            issue_id=None,
            query=None,
            selected_path=None,
            related_invocation_id=None,
            created_at=None,
            fix_id=None,
        )
