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
    source_rows = store.fetch(handles=[source_payload["handle"]])
    validation_rows = store.fetch(handles=[validation_payload["handle"]])

    assert source_payload["ok"] is True
    assert validation_payload["ok"] is True
    assert source_payload["signal_count"] == 4
    assert validation_payload["signal_count"] == 3
    assert len(rows) == 2
    assert {row.payload["kind"] for row in rows} == {"source_plan", "validation"}
    assert source_rows[0].payload["metadata"]["capture_gate"] == "accepted"
    assert source_rows[0].payload["metadata"]["attribution_scope"] == "stage_payload_only"
    assert validation_rows[0].payload["metadata"]["signal_count"] == 3


def test_capture_service_skips_low_signal_stage_observation(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    service = LongTermMemoryCaptureService(store=store, enabled=True)

    payload = service.capture_stage_observation(
        stage_name="validation",
        query="fix validation fallback",
        repo="ace-lite",
        root=str(tmp_path),
        source_run_id="session-1",
        stage_payload={"reason": "", "diagnostic_count": 0, "result": {}},
    )

    rows = store.search(query="validation", limit=10)

    assert payload == {
        "ok": True,
        "skipped": True,
        "reason": "no_capture_signal",
        "stage": "validation",
        "signal_count": 0,
    }
    assert rows == []


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
    assert payload["signal_count"] == 1
    assert len(rows) == 1
    assert rows[0].payload["kind"] == "selection_feedback"
    assert rows[0].payload["payload"]["selected_path"] == "src/app.py"
    assert rows[0].payload["metadata"]["capture_gate"] == "accepted"
    assert rows[0].payload["metadata"]["feedback_signal"] == "helpful"
    assert rows[0].payload["metadata"]["attribution_scope"] == "explicit_selection_only"


def test_capture_service_skips_selection_feedback_without_query_or_path(
    tmp_path: Path,
) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    service = LongTermMemoryCaptureService(store=store, enabled=True)

    missing_query = service.capture_selection_feedback(
        query="  ",
        repo="ace-lite",
        root=str(tmp_path),
        selected_path="src/app.py",
    )
    missing_path = service.capture_selection_feedback(
        query="openmemory 405 dimension mismatch",
        repo="ace-lite",
        root=str(tmp_path),
        selected_path=" ",
    )

    rows = store.search(query="openmemory", limit=10)

    assert missing_query == {
        "ok": True,
        "skipped": True,
        "reason": "missing_query",
        "stage": "selection_feedback",
    }
    assert missing_path == {
        "ok": True,
        "skipped": True,
        "reason": "missing_selected_path",
        "stage": "selection_feedback",
    }
    assert rows == []


def test_capture_service_records_dev_feedback_observations_and_resolution_fact(
    tmp_path: Path,
) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    service = LongTermMemoryCaptureService(store=store, enabled=True)

    issue_payload = {
        "issue_id": "devi_memory_fallback",
        "title": "Memory fallback while planning",
        "reason_code": "memory_fallback",
        "status": "open",
        "repo": "demo",
        "user_id": "dev-user",
        "profile_key": "bugfix",
        "query": "why did memory fallback",
        "selected_path": "src/planner.py",
        "related_invocation_id": "inv-123",
        "notes": "first report",
        "created_at": "2026-03-19T00:00:00+00:00",
        "updated_at": "2026-03-19T00:00:00+00:00",
        "resolved_at": "",
    }
    fix_payload = {
        "fix_id": "devf_memory_fallback",
        "issue_id": "devi_memory_fallback",
        "reason_code": "memory_fallback",
        "repo": "demo",
        "user_id": "dev-user",
        "profile_key": "bugfix",
        "query": "why did memory fallback",
        "selected_path": "src/planner.py",
        "related_invocation_id": "inv-123",
        "resolution_note": "added fallback diagnostics",
        "created_at": "2026-03-19T00:05:00+00:00",
    }
    resolved_issue_payload = {
        **issue_payload,
        "status": "fixed",
        "updated_at": "2026-03-19T00:05:00+00:00",
        "resolved_at": "2026-03-19T00:05:00+00:00",
    }

    issue_capture = service.capture_dev_issue(issue=issue_payload, root=str(tmp_path))
    fix_capture = service.capture_dev_fix(fix=fix_payload, root=str(tmp_path))
    resolution_capture = service.capture_dev_issue_resolution(
        issue=resolved_issue_payload,
        fix=fix_payload,
        root=str(tmp_path),
    )

    issue_rows = store.fetch(handles=[issue_capture["handle"]])
    resolution_fact = store.fetch(handles=[resolution_capture["fact_handle"]])

    assert issue_capture["ok"] is True
    assert issue_capture["stage"] == "dev_issue"
    assert fix_capture["ok"] is True
    assert fix_capture["stage"] == "dev_fix"
    assert resolution_capture["ok"] is True
    assert resolution_capture["stage"] == "dev_issue_resolution"
    assert {row.payload["kind"] for row in issue_rows} == {"dev_issue"}
    assert len(resolution_fact) == 1
    assert resolution_fact[0].payload["fact_type"] == "dev_issue_resolution"
    assert resolution_fact[0].payload["subject"] == "dev_issue:devi_memory_fallback"
    assert resolution_fact[0].payload["predicate"] == "resolved_by"
    assert resolution_fact[0].payload["object"] == "dev_fix:devf_memory_fallback"
