from __future__ import annotations

from pathlib import Path

from ace_lite.memory_long_term import LongTermMemoryCaptureService, LongTermMemoryStore


def test_capture_service_records_source_plan_and_validation_observations(
    tmp_path: Path,
) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    service = LongTermMemoryCaptureService(store=store, enabled=True)

    source_payload = service.capture_stage_observation(
        stage_name="source_plan",
        query="fix validation fallback",
        repo="ace-lite",
        root=str(tmp_path),
        source_run_id="session-1",
        stage_payload={
            "candidate_files": [{"path": "src/app.py"}],
            "candidate_chunks": [{"path": "src/app.py"}],
            "validation_tests": ["tests/test_app.py"],
            "patch_artifact": {"schema_version": "patch_artifact_v1"},
        },
    )
    validation_payload = service.capture_stage_observation(
        stage_name="validation",
        query="fix validation fallback",
        repo="ace-lite",
        root=str(tmp_path),
        source_run_id="session-1",
        stage_payload={
            "reason": "",
            "diagnostic_count": 2,
            "patch_artifact_present": True,
            "result": {
                "summary": {"status": "failed"},
                "tests": {"selected": ["tests/test_app.py"]},
                "environment": {"sandboxed": True},
            },
        },
    )

    rows = store.search(query="validation", limit=10)

    assert source_payload["ok"] is True
    assert validation_payload["ok"] is True
    assert len(rows) == 2
    assert {row.payload["kind"] for row in rows} == {"source_plan", "validation"}


def test_capture_service_records_selection_feedback_observation(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    service = LongTermMemoryCaptureService(store=store, enabled=True)

    payload = service.capture_selection_feedback(
        query="openmemory 405 dimension mismatch",
        repo="ace-lite",
        root=str(tmp_path),
        selected_path="src/app.py",
        position=1,
        captured_at="2026-03-19T00:00:00+00:00",
        user_id="bench-user",
        profile_key="bugfix",
    )

    rows = store.search(query="openmemory", limit=10)

    assert payload["ok"] is True
    assert payload["stage"] == "selection_feedback"
    assert len(rows) == 1
    assert rows[0].payload["kind"] == "selection_feedback"
    assert rows[0].payload["payload"]["selected_path"] == "src/app.py"
