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


def test_handle_memory_search_includes_note_type_classification(tmp_path: Path) -> None:
    """ASF-8912: Memory search results include note_type classification."""
    from ace_lite.mcp_server.service_memory_handlers import handle_memory_search

    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    recent = datetime.now(timezone.utc).isoformat()
    payload = handle_memory_search(
        query="project overview architecture note",
        limit=5,
        namespace=None,
        path=notes_path,
        notes=[
            {
                "text": "EXPL-01 must implement explainability for model decisions",
                "namespace": "default",
                "tags": {"req": "EXPL-01"},
                "captured_at": recent,
            },
            {
                "text": "General project overview and architecture",
                "namespace": "default",
                "tags": {"type": "project"},
                "captured_at": recent,
            },
            {
                "text": "Short note",
                "namespace": "default",
                "captured_at": recent,
            },
        ],
    )

    assert payload["ok"] is True
    # At least 2 items should match (project overview and short note)
    assert payload["count"] >= 2

    # Check note types are included
    for item in payload["items"]:
        assert "_note_type" in item
        assert item["_note_type"] in ("req_match", "task_constraint", "project_reminder", "weak_hint")

    # Find req_match item
    req_items = [i for i in payload["items"] if i.get("tags", {}).get("req") == "EXPL-01"]
    if req_items:
        assert req_items[0]["_note_type"] == "req_match"


def test_handle_memory_store_accepts_task_level_slots(tmp_path: Path) -> None:
    """ASF-8911: Memory store accepts task-level slots (req, contract, area, etc.)."""
    from ace_lite.mcp_server.service_memory_handlers import handle_memory_store

    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    rows: list[dict] = []

    def mock_save(path: Path, data: list) -> None:
        rows.extend(data)

    payload = handle_memory_store(
        text="EXPL-01 implementation constraints",
        namespace="requirements",
        tags={"priority": "high"},
        path=notes_path,
        rows=rows,
        save_notes_fn=mock_save,
        req="EXPL-01",
        contract="explainability-v1",
        area="model-decisions",
        decision_type="constraint",
        task_id="TASK-123",
    )

    assert payload["ok"] is True
    stored = payload["stored"]

    # Check slots are stored in tags
    assert stored["tags"]["req"] == "EXPL-01"
    assert stored["tags"]["contract"] == "explainability-v1"
    assert stored["tags"]["area"] == "model-decisions"
    assert stored["tags"]["decision_type"] == "constraint"
    assert stored["tags"]["task_id"] == "TASK-123"

    # Check slots are also at top level
    assert stored["req"] == "EXPL-01"
    assert stored["contract"] == "explainability-v1"


def test_handle_memory_search_boosts_task_level_matches(tmp_path: Path) -> None:
    """ASF-8911: Memory search boosts notes matching query req/contract IDs."""
    from ace_lite.mcp_server.service_memory_handlers import handle_memory_search

    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    recent = datetime.now(timezone.utc).isoformat()
    payload = handle_memory_search(
        query="information EXPL-01 specific",
        limit=5,
        namespace=None,
        path=notes_path,
        notes=[
            {
                "text": "Generic project information about the codebase",
                "namespace": "default",
                "tags": {"type": "project"},
                "captured_at": recent,
            },
            {
                "text": "EXPL-01 specific requirements for explainability",
                "namespace": "default",
                "tags": {"req": "EXPL-01"},
                "captured_at": recent,
            },
        ],
    )

    assert payload["ok"] is True
    assert payload["count"] == 2

    # The EXPL-01 note should have higher score
    req_item = next(i for i in payload["items"] if i.get("tags", {}).get("req") == "EXPL-01")
    generic_item = next(i for i in payload["items"] if "type" in i.get("tags", {}))

    assert req_item["_score"] > generic_item["_score"]
