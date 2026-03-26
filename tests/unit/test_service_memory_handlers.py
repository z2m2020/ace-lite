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
