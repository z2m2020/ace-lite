from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ace_lite.mcp_server.service_memory_handlers import handle_memory_search


def test_handle_memory_search_includes_disclaimer_without_recency_alert(tmp_path: Path) -> None:
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    recent = datetime.now(timezone.utc).isoformat()
    payload = handle_memory_search(
        query="refresh token",
        limit=5,
        namespace="auth",
        path=notes_path,
        notes=[
            {
                "text": "OAuth refresh token fallback",
                "namespace": "auth",
                "captured_at": recent,
            }
        ],
    )

    assert payload["ok"] is True
    assert payload["count"] == 1
    assert isinstance(payload["disclaimer"], str)
    assert payload["disclaimer"]
    assert payload["recency_alert"] is None
    assert payload["staleness_warning"] is None


def test_handle_memory_search_recency_alert_and_staleness_warning(tmp_path: Path) -> None:
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    payload = handle_memory_search(
        query="latest update refresh",
        limit=5,
        namespace="auth",
        path=notes_path,
        notes=[
            {
                "text": "refresh token fallback",
                "namespace": "auth",
                "captured_at": "2020-01-01T00:00:00+00:00",
            }
        ],
    )

    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["recency_alert"] is not None
    assert payload["recency_alert"]["triggered"] is True
    assert "latest" in payload["recency_alert"]["matched_terms"]
    assert payload["staleness_warning"] is not None
    assert payload["staleness_warning"]["triggered"] is True
    assert payload["staleness_warning"]["stale_item_count"] == 1


def test_handle_memory_search_uses_tags_and_keywords_for_abstract_queries(
    tmp_path: Path,
) -> None:
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    payload = handle_memory_search(
        query="repo familiarization feedback impact optimization",
        limit=5,
        namespace="ace",
        path=notes_path,
        notes=[
            {
                "text": "SCHEMA_VERSION SNAPSHOT_VERSION REPORT_VERSION",
                "query": "cli evaluation snapshot",
                "matched_keywords": ["cli", "evaluation", "snapshot"],
                "tags": {
                    "topic": "familiarization",
                    "focus": "feedback optimization",
                },
                "namespace": "ace",
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )

    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["cold_start"] is False
    assert payload["recommended_next_step"] is None


def test_handle_memory_search_reports_namespace_cold_start(
    tmp_path: Path,
) -> None:
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    payload = handle_memory_search(
        query="auth refresh flow",
        limit=5,
        namespace="auth",
        path=notes_path,
        notes=[
            {
                "text": "billing retry rule",
                "namespace": "billing",
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )

    assert payload["ok"] is True
    assert payload["count"] == 0
    assert payload["cold_start"] is True
    assert payload["recommended_next_step"] == "ace_plan_quick"
