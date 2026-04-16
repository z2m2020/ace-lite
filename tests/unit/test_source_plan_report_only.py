from __future__ import annotations

import json
from pathlib import Path

from ace_lite.source_plan.report_only import (
    append_handoff_payload_note,
    build_candidate_review,
    build_handoff_payload,
    build_handoff_payload_note,
    build_history_hits,
    build_session_end_report,
    build_validation_findings,
    render_handoff_payload_markdown,
    write_handoff_payload_artifacts,
)


def test_build_history_hits_emits_stable_summary() -> None:
    summary = build_history_hits(
        vcs_history={
            "enabled": True,
            "reason": "ok",
            "commit_count": 2,
            "path_count": 1,
            "commits": [
                {
                    "hash": "abc123",
                    "subject": "touch source plan",
                    "author": "dev",
                    "committed_at": "2026-04-14T00:00:00Z",
                    "files": ["src/ace_lite/pipeline/stages/source_plan.py"],
                },
                {
                    "hash": "def456",
                    "subject": "touch docs",
                    "author": "dev",
                    "committed_at": "2026-04-13T00:00:00Z",
                    "files": ["docs/readme.md"],
                },
            ],
        },
        focused_files=["src/ace_lite/pipeline/stages/source_plan.py"],
    )

    assert summary["schema_version"] == "history_hits_v1"
    assert summary["enabled"] is True
    assert summary["hit_count"] == 1
    assert len(summary["hits"]) == 1
    assert summary["hits"][0]["matched_paths"] == ["src/ace_lite/pipeline/stages/source_plan.py"]


def test_build_candidate_review_and_session_end_report_capture_watch_items() -> None:
    review = build_candidate_review(
        focused_files=["src/ace_lite/context_report.py"],
        candidate_chunks=[
            {"path": "src/ace_lite/context_report.py"},
            {"path": "tests/unit/test_context_report.py"},
        ],
        evidence_summary={
            "direct_ratio": 0.2,
            "neighbor_context_ratio": 0.3,
            "hint_only_ratio": 0.6,
        },
        failure_signal_summary={
            "has_failure": True,
            "issue_count": 1,
            "probe_issue_count": 0,
        },
        validation_tests=[],
    )

    session = build_session_end_report(
        query="inspect context report governance",
        focused_files=["src/ace_lite/context_report.py"],
        validation_tests=["pytest tests/unit/test_context_report.py -q"],
        diagnostics=["memory_fallback"],
        candidate_review=review,
        validation_findings={"status": "failed", "warn_count": 1, "blocker_count": 1},
        history_hits={"hit_count": 1},
    )

    assert review["schema_version"] == "candidate_review_v1"
    assert review["status"] == "watch"
    assert "hint_heavy_shortlist" in review["watch_items"]
    assert "missing_validation_tests" in review["watch_items"]
    assert session["schema_version"] == "session_end_report_v1"
    assert session["history_context_present"] is True
    assert "validation_blockers_present" in session["risks"]
    assert session["next_actions"]


def test_build_validation_findings_tracks_warn_and_blocker_counts() -> None:
    findings = build_validation_findings(
        validation_result={
            "syntax": {
                "issues": [
                    {
                        "code": "syntax.error",
                        "message": "invalid syntax",
                        "path": "src/app.py",
                    }
                ]
            },
            "summary": {"status": "failed", "issue_count": 2},
            "probes": {
                "status": "degraded",
                "issue_count": 1,
                "results": [
                    {
                        "name": "compile",
                        "status": "failed",
                        "issues": [
                            {
                                "code": "compile.failed",
                                "message": "compile probe failed",
                                "path": "src/build.py",
                            }
                        ],
                    }
                ],
            },
            "tests": {"selected": ["pytest tests/unit/test_a.py"], "executed": []},
        }
    )

    assert findings["schema_version"] == "validation_findings_v1"
    assert findings["governance_mode"] == "advisory_report_only"
    assert findings["allowed_actions"] == ["request_more_context"]
    assert findings["request_more_context_reason"] == "source_plan_validation_findings"
    assert findings["status"] == "failed"
    assert findings["warn_count"] >= 1
    assert findings["blocker_count"] >= 1
    assert findings["selected_test_count"] == 1
    assert findings["executed_test_count"] == 0
    assert findings["focus_paths"] == ["src/app.py", "src/build.py"]
    assert "invalid syntax" in findings["query_hint"]
    assert findings["needs_followup"] is True
    assert findings["refine_hints"]
    assert findings["recommendations"]


def test_build_handoff_payload_dedupes_signal_lists() -> None:
    payload = build_handoff_payload(
        query="stabilize report signals",
        candidate_review={
            "watch_items": ["watch_a", "watch_a", "watch_b"],
        },
        validation_findings={
            "message_samples": ["issue one", "issue one", "issue two"],
        },
        session_end_report={
            "next_actions": ["run tests", "run tests", "inspect diff"],
            "risks": ["risk_a", "risk_a"],
            "validation_tests": ["pytest tests/unit/test_a.py -q"] * 2,
            "focus_paths": ["./src/a.py", "src\\a.py", "src/b.py"],
            "validation_status": "warn",
        },
    )

    assert payload["schema_version"] == "handoff_payload_v1"
    assert payload["unresolved"] == ["issue one", "issue two", "watch_a", "watch_b"]
    assert payload["next_tasks"] == ["run tests", "inspect diff"]
    assert payload["risks"] == ["risk_a"]
    assert payload["verify"] == ["pytest tests/unit/test_a.py -q"]
    assert payload["focus_paths"] == ["src/a.py", "src/b.py"]
    assert payload["validation_status"] == "warn"


def test_write_handoff_payload_artifacts_writes_json_and_markdown(tmp_path: Path) -> None:
    payload = {
        "schema_version": "handoff_payload_v1",
        "goal": "stabilize report signals",
        "next_tasks": ["run tests", "inspect diff"],
        "focus_paths": ["src/a.py"],
        "unresolved": ["issue one"],
        "verify": ["pytest -q tests/unit/test_a.py"],
        "risks": ["risk_a"],
        "validation_status": "warn",
    }

    result = write_handoff_payload_artifacts(
        payload,
        "artifacts/handoffs/latest",
        root=str(tmp_path),
    )

    json_path = tmp_path / "artifacts" / "handoffs" / "latest" / "handoff_payload.json"
    markdown_path = tmp_path / "artifacts" / "handoffs" / "latest" / "handoff_payload.md"
    assert result["ok"] is True
    assert result["json_path"] == str(json_path.resolve())
    assert result["markdown_path"] == str(markdown_path.resolve())
    assert json.loads(json_path.read_text(encoding="utf-8"))["goal"] == "stabilize report signals"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Handoff Payload" in markdown
    assert "## Next Tasks" in markdown
    assert "run tests" in markdown


def test_build_and_append_handoff_payload_note_preserves_artifact_refs(tmp_path: Path) -> None:
    payload = {
        "schema_version": "handoff_payload_v1",
        "goal": "stabilize report signals",
        "next_tasks": ["run tests"],
        "focus_paths": ["src/a.py"],
        "unresolved": ["issue one"],
        "verify": ["pytest -q tests/unit/test_a.py"],
        "validation_status": "warn",
    }
    note = build_handoff_payload_note(
        query="stabilize report signals",
        repo="demo",
        handoff_payload=payload,
        namespace="repo:demo",
        artifact_refs=["artifacts/handoffs/latest/handoff_payload.json"],
    )

    assert note["source"] == "handoff_payload_v1"
    assert note["namespace"] == "repo:demo"
    assert "handoff: stabilize report signals" in note["text"]
    assert note["artifact_refs"] == ["artifacts/handoffs/latest/handoff_payload.json"]

    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    result = append_handoff_payload_note(
        notes_path=notes_path,
        query="stabilize report signals",
        repo="demo",
        handoff_payload=payload,
        namespace="repo:demo",
        artifact_refs=["artifacts/handoffs/latest/handoff_payload.json"],
    )

    assert result["ok"] is True
    rows = [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    persisted = json.loads(rows[0])
    assert persisted["namespace"] == "repo:demo"
    assert persisted["artifact_refs"] == ["artifacts/handoffs/latest/handoff_payload.json"]


def test_render_handoff_payload_markdown_includes_core_sections() -> None:
    markdown = render_handoff_payload_markdown(
        {
            "schema_version": "handoff_payload_v1",
            "goal": "stabilize report signals",
            "next_tasks": ["run tests"],
            "focus_paths": ["src/a.py"],
            "unresolved": ["issue one"],
            "verify": ["pytest -q tests/unit/test_a.py"],
            "risks": ["risk_a"],
            "validation_status": "warn",
        }
    )

    assert "# Handoff Payload" in markdown
    assert "## Focus Paths" in markdown
    assert "## Next Tasks" in markdown
    assert "## Unresolved" in markdown
    assert "## Verify" in markdown
