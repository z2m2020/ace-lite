from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.memory_long_term import LongTermMemoryStore
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.mcp_server.service_dev_feedback_handlers import (
    handle_dev_issue_apply_fix_request,
    handle_dev_feedback_summary_request,
    handle_dev_issue_from_runtime_request,
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
    assert summary["summary"]["resolved_issue_count"] == 0
    assert summary["summary"]["fix_count"] == 1
    assert summary["summary"]["linked_fix_issue_count"] == 1
    assert summary["summary"]["dev_issue_to_fix_rate"] == 1.0
    assert summary["summary"]["by_reason_code"][0]["reason_code"] == "memory_fallback"


def test_handle_dev_feedback_can_capture_long_term_memory_when_enabled(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    long_term:\n"
            "      enabled: true\n"
            "      write_enabled: true\n"
            "      path: context-map/long_term_memory.db\n"
        ),
        encoding="utf-8",
    )
    store_path = str(tmp_path / "context-map" / "dev-feedback.db")

    recorded_issue = handle_dev_issue_record_request(
        title="Memory fallback while planning",
        reason_code="memory_fallback",
        repo="demo",
        store_path=store_path,
        user_id="mcp-user",
        profile_key="bugfix",
        query="why did memory fallback",
        selected_path="src/planner.py",
        related_invocation_id="inv-123",
        notes="first report",
        status="open",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:00:00+00:00",
        resolved_at=None,
        issue_id="devi_memory_fallback",
        root_path=tmp_path,
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
        root_path=tmp_path,
    )
    resolved_issue = handle_dev_issue_apply_fix_request(
        issue_id="devi_memory_fallback",
        fix_id="devf_memory_fallback",
        store_path=store_path,
        status="fixed",
        resolved_at=None,
        root_path=tmp_path,
    )
    long_term_store = LongTermMemoryStore(db_path=tmp_path / "context-map" / "long_term_memory.db")
    resolution_fact = long_term_store.fetch(
        handles=[resolved_issue["long_term_capture"]["fact_handle"]]
    )

    assert recorded_issue["long_term_capture"]["ok"] is True
    assert recorded_issue["long_term_capture"]["stage"] == "dev_issue"
    assert recorded_fix["long_term_capture"]["ok"] is True
    assert recorded_fix["long_term_capture"]["stage"] == "dev_fix"
    assert resolved_issue["long_term_capture"]["ok"] is True
    assert resolved_issue["long_term_capture"]["stage"] == "dev_issue_resolution"
    assert len(resolution_fact) == 1
    assert resolution_fact[0].payload["object"] == "dev_fix:devf_memory_fallback"


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


def test_handle_dev_issue_from_runtime_promotes_auto_captured_event(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    long_term:\n"
            "      enabled: true\n"
            "      write_enabled: true\n"
            "      path: context-map/long_term_memory.db\n"
        ),
        encoding="utf-8",
    )
    stats_db_path = tmp_path / "context-map" / "runtime-stats.db"
    store_path = str(tmp_path / "context-map" / "dev-feedback.db")
    DurableStatsStore(db_path=stats_db_path).record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-runtime-1",
            session_id="sess-1",
            repo_key="demo",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=18.0,
            started_at="2026-03-19T00:00:00+00:00",
            finished_at="2026-03-19T00:00:02+00:00",
            degraded_reason_codes=("memory_fallback",),
        )
    )

    recorded_issue = handle_dev_issue_from_runtime_request(
        invocation_id="inv-runtime-1",
        stats_db_path=str(stats_db_path),
        store_path=store_path,
        reason_code=None,
        title=None,
        notes="confirmed by runtime doctor",
        status="open",
        user_id="mcp-user",
        profile_key=None,
        issue_id="devi_runtime_1",
        root_path=tmp_path,
    )

    assert recorded_issue["ok"] is True
    assert recorded_issue["issue"]["issue_id"] == "devi_runtime_1"
    assert recorded_issue["issue"]["reason_code"] == "memory_fallback"
    assert recorded_issue["issue"]["repo"] == "demo"
    assert recorded_issue["issue"]["related_invocation_id"] == "inv-runtime-1"
    assert "auto_captured_from=runtime_stats" in recorded_issue["issue"]["notes"]
    assert "reason_family=memory" in recorded_issue["issue"]["notes"]
    assert "capture_class=fallback" in recorded_issue["issue"]["notes"]
    assert recorded_issue["invocation"]["invocation_id"] == "inv-runtime-1"
    assert recorded_issue["long_term_capture"]["ok"] is True
    assert recorded_issue["long_term_capture"]["stage"] == "dev_issue"


def test_handle_dev_issue_apply_fix_updates_open_issue_count(tmp_path: Path) -> None:
    store_path = str(tmp_path / "context-map" / "dev-feedback.db")

    handle_dev_issue_record_request(
        title="Memory fallback while planning",
        reason_code="memory_fallback",
        repo="demo",
        store_path=store_path,
        user_id="mcp-user",
        profile_key="bugfix",
        query=None,
        selected_path=None,
        related_invocation_id="inv-123",
        notes="first report",
        status="open",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:00:00+00:00",
        resolved_at=None,
        issue_id="devi_memory_fallback",
    )
    handle_dev_fix_record_request(
        reason_code="memory_fallback",
        repo="demo",
        resolution_note="added fallback diagnostics",
        store_path=store_path,
        user_id="mcp-user",
        profile_key="bugfix",
        issue_id="devi_memory_fallback",
        query=None,
        selected_path=None,
        related_invocation_id="inv-123",
        created_at="2026-03-19T00:05:00+00:00",
        fix_id="devf_memory_fallback",
    )

    resolved_issue = handle_dev_issue_apply_fix_request(
        issue_id="devi_memory_fallback",
        fix_id="devf_memory_fallback",
        store_path=store_path,
        status="fixed",
        resolved_at=None,
    )
    summary = handle_dev_feedback_summary_request(
        repo="demo",
        user_id="mcp-user",
        profile_key="bugfix",
        store_path=store_path,
    )

    assert resolved_issue["ok"] is True
    assert resolved_issue["issue"]["status"] == "fixed"
    assert summary["summary"]["issue_count"] == 1
    assert summary["summary"]["open_issue_count"] == 0
    assert summary["summary"]["resolved_issue_count"] == 1
    assert summary["summary"]["linked_fix_issue_count"] == 1
    assert summary["summary"]["dev_issue_to_fix_rate"] == 1.0
    assert summary["summary"]["issue_time_to_fix_case_count"] == 1
