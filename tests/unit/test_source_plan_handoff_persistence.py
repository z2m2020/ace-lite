from __future__ import annotations

import json
from pathlib import Path

from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.types import StageContext


def test_run_source_plan_persists_handoff_payload_when_paths_are_provided(tmp_path: Path) -> None:
    ctx = StageContext(query="stabilize report signals", repo="demo", root=str(tmp_path))
    ctx.state = {
        "memory": {"hits_preview": []},
        "index": {
            "candidate_files": [{"path": "src/a.py"}],
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "do_work",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 2.0,
                    "score_breakdown": {"candidate": 1.0},
                }
            ],
            "chunk_metrics": {"chunk_budget_used": 10.0},
            "policy_name": "general",
            "policy_version": "v1",
        },
        "repomap": {"focused_files": ["src/a.py"]},
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {
                "suspicious_chunks": [],
                "suggested_tests": ["pytest -q tests/unit/test_a.py"],
            },
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=128,
        chunk_disclosure="refs",
        policy_version="v1",
        handoff_artifact_dir="artifacts/handoffs/latest",
        handoff_notes_path="context-map/memory_notes.jsonl",
        handoff_note_namespace="repo:demo",
    )

    assert result["handoff_payload"]["schema_version"] == "handoff_payload_v1"
    json_path = tmp_path / "artifacts" / "handoffs" / "latest" / "handoff_payload.json"
    markdown_path = tmp_path / "artifacts" / "handoffs" / "latest" / "handoff_payload.md"
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    assert json_path.exists()
    assert markdown_path.exists()
    assert notes_path.exists()
    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "handoff_payload_v1"
    note_rows = [
        line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(note_rows) == 1
    note_payload = json.loads(note_rows[0])
    assert note_payload["namespace"] == "repo:demo"
    assert any("handoff_payload.json" in ref for ref in note_payload["artifact_refs"])
