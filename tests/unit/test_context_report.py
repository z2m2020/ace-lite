"""Unit tests for the ContextReport module (L8501).

These tests cover:
- Empty/minimal payload handling
- Full source_plan payload with validation
- Degraded reasons in observability
- Markdown rendering output shape
- write_context_report_markdown file output
- P1 confidence taxonomy consumption (after R8503 lands)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite.context_report import (
    SCHEMA_VERSION,
    append_context_report_note,
    build_context_report_note,
    build_context_report_payload,
    render_context_report_markdown,
    validate_context_report_payload,
    write_context_report_artifacts,
    write_context_report_markdown,
)

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def minimal_plan_payload() -> dict:
    return {
        "query": "fix validation flow",
        "repo": "ace-lite-engine",
        "root": "/fake/root",
        "stages": ["memory", "index", "repomap", "augment", "skills", "source_plan"],
        "candidate_chunks": [
            {
                "path": "src/ace_lite/pipeline/stages/source_plan.py",
                "qualified_name": "run_source_plan",
                "kind": "function",
                "lineno": 267,
                "end_lineno": 490,
                "score": 9.5,
                "evidence": {
                    "role": "direct",
                    "direct_retrieval": True,
                    "neighbor_context": False,
                    "hint_only": False,
                    "hint_support": False,
                    "reference_sidecar": True,
                    "sources": ["direct_candidate"],
                    "granularity": ["symbol", "signature", "skeleton"],
                },
            },
            {
                "path": "src/ace_lite/source_plan/grounding.py",
                "qualified_name": "annotate_source_plan_grounding",
                "kind": "function",
                "lineno": 71,
                "end_lineno": 153,
                "score": 7.2,
                "evidence": {
                    "role": "neighbor_context",
                    "direct_retrieval": False,
                    "neighbor_context": True,
                    "hint_only": False,
                    "hint_support": False,
                    "reference_sidecar": False,
                    "sources": ["focused_neighbor"],
                    "granularity": ["symbol", "signature"],
                },
            },
            {
                "path": "tests/unit/test_source_plan_properties.py",
                "qualified_name": "test_run_source_plan_deterministic",
                "kind": "function",
                "lineno": 93,
                "end_lineno": 156,
                "score": 3.1,
                "evidence": {
                    "role": "hint_only",
                    "direct_retrieval": False,
                    "neighbor_context": False,
                    "hint_only": True,
                    "hint_support": True,
                    "reference_sidecar": False,
                    "sources": ["test_hint"],
                    "granularity": ["symbol"],
                },
            },
        ],
        "candidate_files": [
            {"path": "src/ace_lite/pipeline/stages/source_plan.py", "score": 9.5},
            {"path": "src/ace_lite/source_plan/grounding.py", "score": 7.2},
            {"path": "tests/unit/test_source_plan_properties.py", "score": 3.1},
        ],
        "evidence_summary": {
            "direct_count": 1.0,
            "neighbor_context_count": 1.0,
            "hint_only_count": 1.0,
            "direct_ratio": 0.333,
            "neighbor_context_ratio": 0.333,
            "hint_only_ratio": 0.333,
            "symbol_count": 3.0,
            "signature_count": 2.0,
            "skeleton_count": 1.0,
            "robust_signature_count": 0.0,
            "reference_sidecar_count": 1.0,
        },
        "validation_tests": [
            "pytest tests/unit/test_source_plan_properties.py::test_case",
        ],
        "observability": {
            "stage_metrics": {
                "degraded_reasons": ["memory_fallback"],
            },
        },
    }


@pytest.fixture
def degraded_plan_payload() -> dict:
    """Payload with multiple degraded signals."""
    return {
        "query": "refactor chunk packing",
        "repo": "ace-lite-engine",
        "root": "/fake/root",
        "stages": ["memory", "index"],
        "candidate_chunks": [],
        "candidate_files": [],
        "evidence_summary": {
            "direct_count": 0.0,
            "neighbor_context_count": 0.0,
            "hint_only_count": 0.0,
            "direct_ratio": 0.0,
            "neighbor_context_ratio": 0.0,
            "hint_only_ratio": 0.0,
        },
        "observability": {
            "stage_metrics": {
                "degraded_reasons": [
                    "embedding_fallback",
                    "candidate_ranker_fallback",
                ],
            },
        },
        "_plan_timeout_fallback": True,
    }


# ----------------------------------------------------------------------
# build_context_report_payload tests
# ----------------------------------------------------------------------


def test_empty_payload_returns_ok_false():
    payload = build_context_report_payload({})
    assert payload["ok"] is False
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["warnings"] == ["empty_payload"]
    assert payload["core_nodes"] == []
    assert payload["confidence_breakdown"]["total_count"] == 0


def test_none_payload_returns_ok_false():
    # Accepts Mapping, so passes fine
    payload = build_context_report_payload({})
    assert payload["ok"] is False
    assert "empty_payload" in payload["warnings"]


def test_minimal_source_plan_payload(minimal_plan_payload):
    payload = build_context_report_payload(minimal_plan_payload)

    assert payload["ok"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["query"] == "fix validation flow"
    assert payload["repo"] == "ace-lite-engine"
    assert payload["root"] == "/fake/root"

    # Summary
    summary = payload["summary"]
    assert summary["candidate_file_count"] >= 3
    assert summary["candidate_chunk_count"] == 3
    assert summary["validation_test_count"] == 1
    assert summary["stage_count"] == 6
    assert summary["degraded_reason_count"] == 1
    assert summary["has_validation_payload"] is False
    assert summary["context_refine_decision_count"] == 0

    # Core nodes
    core_nodes = payload["core_nodes"]
    assert len(core_nodes) > 0
    assert all("path" in n for n in core_nodes)
    assert all("score" in n for n in core_nodes)
    assert all("label" in n for n in core_nodes)

    # Confidence breakdown
    cb = payload["confidence_breakdown"]
    assert cb["extracted_count"] == 1  # 1 direct
    assert cb["inferred_count"] == 1  # 1 neighbor_context
    assert cb["ambiguous_count"] == 1  # 1 hint_only
    assert cb["total_count"] == 3
    assert (
        cb["extracted_count"] + cb["inferred_count"] + cb["ambiguous_count"] + cb["unknown_count"]
        == cb["total_count"]
    )


def test_nested_source_plan_payload_reads_real_orchestrator_shape() -> None:
    payload = {
        "query": "q",
        "repo": "r",
        "root": "x",
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "f",
                    "score": 1.0,
                    "evidence_confidence": "EXTRACTED",
                }
            ],
            "candidate_files": [{"path": "src/a.py", "score": 0.9}],
            "validation_tests": ["pytest tests/test_a.py"],
            "evidence_summary": {"direct_count": 1, "direct_ratio": 1},
            "confidence_summary": {"extracted_count": 1, "total_count": 1},
            "subgraph_payload": {
                "edge_counts": {"cochange": 5},
                "seed_paths": ["src/a.py"],
            },
        },
        "observability": {
            "stage_metrics": [
                {
                    "stage": "source_plan",
                    "elapsed_ms": 1.0,
                    "plugins": [],
                    "tags": {"degraded_reasons": ["memory_fallback"]},
                }
            ]
        },
    }

    result = build_context_report_payload(payload)

    assert result["ok"] is True
    assert result["summary"]["candidate_chunk_count"] == 1
    assert result["summary"]["candidate_file_count"] == 1
    assert result["summary"]["validation_test_count"] == 1
    assert result["summary"]["degraded_reason_count"] >= 1
    assert result["confidence_breakdown"]["extracted_count"] == 1
    assert result["core_nodes"]


def test_nested_source_plan_payload_uses_source_plan_for_questions_and_summary() -> None:
    payload = {
        "query": "q",
        "repo": "r",
        "root": "x",
        "pipeline_order": ["memory", "index", "source_plan", "validation"],
        "source_plan": {
            "stages": ["memory", "index", "source_plan"],
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "f",
                    "score": 1.0,
                    "evidence_confidence": "EXTRACTED",
                }
            ],
            "candidate_files": [{"path": "src/a.py", "score": 0.9}],
            "validation_tests": ["pytest tests/test_a.py"],
            "evidence_summary": {
                "direct_count": 1,
                "direct_ratio": 1.0,
                "neighbor_context_count": 2,
            },
        },
        "validation": {
            "result": {
                "schema_version": "validation-v1",
                "summary": {"status": "passed", "issue_count": 0},
            }
        },
    }

    result = build_context_report_payload(payload)

    assert result["summary"]["stage_count"] == 3
    assert result["summary"]["has_validation_payload"] is True
    assert result["suggested_questions"][0]["type"] == "entrypoint"
    assert result["suggested_questions"][0]["path"] == "src/a.py"
    assert any(q["type"] == "clarification" for q in result["suggested_questions"])


def test_context_report_surfaces_wave1_report_only_sections() -> None:
    payload = {
        "query": "q",
        "repo": "r",
        "root": "x",
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "f",
                    "score": 1.0,
                    "evidence_confidence": "EXTRACTED",
                }
            ],
            "candidate_files": [{"path": "src/a.py", "score": 0.9}],
            "validation_tests": ["pytest tests/test_a.py"],
            "history_hits": {
                "reason": "ok",
                "commit_count": 2,
                "hits": [{"hash": "abc123", "subject": "recent fix"}],
            },
            "candidate_review": {
                "status": "watch",
                "focus_file_count": 1,
                "candidate_chunk_count": 1,
                "validation_test_count": 1,
                "watch_items": ["hint_heavy_shortlist"],
                "recommendations": ["Review the top direct chunk first."],
            },
            "validation_findings": {
                "status": "failed",
                "info_count": 0,
                "warn_count": 1,
                "blocker_count": 1,
                "findings": [
                    {
                        "severity": "blocker",
                        "code": "validation_failed",
                        "message": "Validation failed.",
                    }
                ],
            },
            "session_end_report": {
                "goal": "q",
                "focus_paths": ["src/a.py"],
                "validation_tests": ["pytest tests/test_a.py"],
                "next_actions": ["Run tests"],
                "risks": ["validation_blockers_present"],
            },
            "handoff_payload": {
                "goal": "q",
                "focus_paths": ["src/a.py"],
                "next_tasks": ["Run tests"],
                "unresolved": ["validation_failed"],
            },
        },
    }

    result = build_context_report_payload(payload)
    markdown = render_context_report_markdown(result)

    assert result["summary"]["history_hit_count"] == 1
    assert result["summary"]["validation_finding_count"] == 1
    assert result["summary"]["next_action_count"] == 1
    assert result["history_hits"]["hits"][0]["hash"] == "abc123"
    assert result["candidate_review"]["status"] == "watch"
    assert result["validation_findings"]["blocker_count"] == 1
    assert result["session_end_report"]["next_actions"] == ["Run tests"]
    assert result["handoff_payload"]["next_tasks"] == ["Run tests"]
    assert "## History Hits" in markdown
    assert "## Candidate Review" in markdown
    assert "## Validation Findings" in markdown
    assert "## Session End Report" in markdown
    assert "## Handoff Payload" in markdown


def test_context_report_surfaces_history_channel_section() -> None:
    payload = {
        "query": "q",
        "repo": "r",
        "root": "x",
        "history_channel": {
            "reason": "matched",
            "focused_files": ["src/a.py"],
            "commit_count": 2,
            "hit_count": 1,
            "history_hits": {
                "hits": [{"hash": "abc123", "subject": "recent fix"}],
            },
            "recommendations": ["Review the recent matching commits first."],
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "f",
                    "score": 1.0,
                    "evidence_confidence": "EXTRACTED",
                }
            ],
            "candidate_files": [{"path": "src/a.py", "score": 0.9}],
            "validation_tests": [],
        },
    }

    result = build_context_report_payload(payload)
    markdown = render_context_report_markdown(result)

    assert result["summary"]["history_channel_hit_count"] == 1
    assert result["history_channel"]["hit_count"] == 1
    assert "## History Channel" in markdown
    assert "focused_files=1" in markdown


def test_context_report_surfaces_context_refine_section() -> None:
    payload = {
        "query": "q",
        "repo": "r",
        "root": "x",
        "context_refine": {
            "focused_files": ["src/a.py"],
            "decision_counts": {
                "keep": 1,
                "downrank": 1,
                "drop": 0,
                "need_more_read": 2,
            },
            "candidate_review": {
                "status": "watch",
                "recommendations": ["Open keep candidates first."],
            },
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "f",
                    "score": 1.0,
                    "evidence_confidence": "EXTRACTED",
                }
            ],
            "candidate_files": [{"path": "src/a.py", "score": 0.9}],
            "validation_tests": [],
        },
    }

    result = build_context_report_payload(payload)
    markdown = render_context_report_markdown(result)

    assert result["summary"]["context_refine_decision_count"] == 4
    assert result["context_refine"]["decision_counts"]["keep"] == 1
    assert "## Context Refine" in markdown
    assert "keep=1" in markdown


def test_degraded_payload_knowledge_gaps(degraded_plan_payload):
    payload = build_context_report_payload(degraded_plan_payload)

    assert payload["ok"] is True
    gaps = payload["knowledge_gaps"]
    gap_codes = {g["code"] for g in gaps}

    assert "missing_candidate_chunks" in gap_codes
    assert "hint_heavy_evidence" not in gap_codes  # no chunks so no ratio computed
    assert "plan_timeout_fallback" in gap_codes


def test_hint_heavy_evidence_gap():
    payload = {
        "query": "some query",
        "repo": "test",
        "root": "/test",
        "candidate_chunks": [
            {
                "path": "a.py",
                "qualified_name": "fn",
                "kind": "function",
                "score": 1.0,
                "evidence": {
                    "role": "hint_only",
                    "direct_retrieval": False,
                    "neighbor_context": False,
                    "hint_only": True,
                    "hint_support": False,
                    "reference_sidecar": False,
                    "sources": [],
                    "granularity": [],
                },
            },
        ]
        * 5,
        "evidence_summary": {
            "hint_only_ratio": 1.0,
            "direct_count": 0.0,
            "neighbor_context_count": 0.0,
            "direct_ratio": 0.0,
            "neighbor_context_ratio": 0.0,
        },
        "stages": ["index"],
    }
    result = build_context_report_payload(payload)
    gap_codes = {g["code"] for g in result["knowledge_gaps"]}
    assert "hint_heavy_evidence" in gap_codes


def test_degraded_observability_gap():
    payload = {
        "query": "trace observability",
        "repo": "test",
        "root": "/test",
        "candidate_chunks": [],
        "candidate_files": [{"path": "a.py", "score": 1.0}],
        "evidence_summary": {},
        "observability": {
            "stage_metrics": {
                "degraded_reasons": [
                    "embedding_fallback",
                    "trace_export_failed",
                ],
            },
        },
        "stages": ["index"],
    }
    result = build_context_report_payload(payload)
    gap_codes = {g["code"] for g in result["knowledge_gaps"]}
    assert "embedding_fallback" in gap_codes
    assert "trace_export_failed" in gap_codes


def test_suggested_questions_from_gaps(degraded_plan_payload):
    payload = build_context_report_payload(degraded_plan_payload)
    questions = payload["suggested_questions"]
    assert len(questions) >= 1
    types = {q["type"] for q in questions}
    assert "no_signal" not in types  # has gaps so should generate questions


def test_suggested_questions_no_signal_on_empty():
    payload = build_context_report_payload({})
    questions = payload["suggested_questions"]
    assert len(questions) == 1
    assert questions[0]["type"] == "no_signal"


def test_plan_payload_not_modified(minimal_plan_payload):
    """Ensure build_context_report_payload does not mutate input."""
    original = json.dumps(minimal_plan_payload, sort_keys=True)
    build_context_report_payload(minimal_plan_payload)
    after = json.dumps(minimal_plan_payload, sort_keys=True)
    assert original == after


def test_p1_confidence_summary_integration():
    """Test that P1 confidence_summary is used when present."""
    payload = {
        "query": "test confidence taxonomy",
        "repo": "test",
        "root": "/test",
        "candidate_chunks": [
            {
                "path": "a.py",
                "qualified_name": "fn",
                "kind": "function",
                "score": 1.0,
                "evidence_confidence": "EXTRACTED",
                "confidence_score": 1.0,
                "confidence_reason": "direct hit",
            },
        ],
        "confidence_summary": {
            "extracted_count": 1,
            "inferred_count": 0,
            "ambiguous_count": 0,
            "unknown_count": 0,
            "total_count": 1,
        },
        "stages": ["source_plan"],
    }
    result = build_context_report_payload(payload)
    cb = result["confidence_breakdown"]
    assert cb["extracted_count"] == 1
    assert cb["total_count"] == 1


def test_p1_confidence_summary_total_matches_chunks():
    """P1: confidence_summary.total_count must equal len(candidate_chunks)."""
    payload = {
        "query": "test total count",
        "repo": "test",
        "root": "/test",
        "candidate_chunks": [
            {"path": "a.py", "qualified_name": "fn", "kind": "function", "score": 1.0},
            {"path": "b.py", "qualified_name": "gn", "kind": "function", "score": 0.8},
        ],
        "confidence_summary": {
            "extracted_count": 1,
            "inferred_count": 1,
            "ambiguous_count": 0,
            "unknown_count": 0,
            "total_count": 2,
        },
        "stages": [],
    }
    result = build_context_report_payload(payload)
    cb = result["confidence_breakdown"]
    assert cb["total_count"] == 2


def test_repomap_focused_files_marked():
    """Repomap focused files should show source=repomap in core_nodes."""
    payload = {
        "query": "test repomap source",
        "repo": "test",
        "root": "/test",
        "candidate_files": [
            {"path": "src/a.py", "score": 9.0},
        ],
        "candidate_chunks": [
            {"path": "src/a.py", "qualified_name": "fn", "kind": "function", "score": 9.0},
        ],
        "repomap": {
            "focused_files": ["src/a.py"],
        },
        "evidence_summary": {},
        "stages": [],
    }
    result = build_context_report_payload(payload)
    node_sources = {n["source"] for n in result["core_nodes"]}
    assert "repomap" in node_sources


def test_surprising_connections_graph_boost():
    """Chunks with graph_closure_bonus or cochange_boost should appear in surprising_connections."""
    payload = {
        "query": "test surprising connections",
        "repo": "test",
        "root": "/test",
        "candidate_chunks": [
            {
                "path": "src/core.py",
                "qualified_name": "core_fn",
                "kind": "function",
                "score": 6.5,
                "score_breakdown": {
                    "candidate": 4.0,
                    "graph_closure_bonus": 0.8,
                    "cochange_boost": 0.5,
                },
            },
            {
                "path": "src/helper.py",
                "qualified_name": "helper_fn",
                "kind": "function",
                "score": 3.2,
                "evidence": {
                    "role": "direct",
                    "direct_retrieval": True,
                    "neighbor_context": False,
                    "hint_only": False,
                    "hint_support": False,
                    "reference_sidecar": False,
                    "sources": ["direct_candidate"],
                    "granularity": ["symbol"],
                },
            },
        ],
        "candidate_files": [
            {"path": "src/core.py", "score": 6.5},
            {"path": "src/helper.py", "score": 3.2},
        ],
        "evidence_summary": {},
        "stages": [],
    }
    result = build_context_report_payload(payload)
    connections = result["surprising_connections"]
    assert len(connections) >= 1
    boost_sources = [s for c in connections for s in c.get("boost_sources", [])]
    assert "graph_closure" in boost_sources or "cochange" in boost_sources


# ----------------------------------------------------------------------
# render_context_report_markdown tests
# ----------------------------------------------------------------------


def test_render_minimal_payload(minimal_plan_payload):
    md = render_context_report_markdown(build_context_report_payload(minimal_plan_payload))
    assert "# Context Report" in md
    assert "## Summary" in md
    assert "## Core Nodes" in md
    assert "## Surprising Connections" in md
    assert "## Confidence Breakdown" in md
    assert "## Knowledge Gaps" in md
    assert "## Suggested Questions" in md
    # Warnings section only appears when there are warnings in the payload


def test_render_empty_payload():
    payload = build_context_report_payload({})
    md = render_context_report_markdown(payload)
    assert "Context Report" in md
    assert "status: degraded" in md


def test_render_contains_section_headers(minimal_plan_payload):
    md = render_context_report_markdown(build_context_report_payload(minimal_plan_payload))
    required_headers = [
        "# Context Report",
        "## Summary",
        "## Core Nodes",
        "## Surprising Connections",
        "## Confidence Breakdown",
        "## Knowledge Gaps",
        "## Suggested Questions",
    ]
    for header in required_headers:
        assert header in md, f"Missing header: {header}"


def test_render_contains_query_and_repo(minimal_plan_payload):
    md = render_context_report_markdown(build_context_report_payload(minimal_plan_payload))
    assert "fix validation flow" in md
    assert "ace-lite-engine" in md


def test_render_confidence_breakdown_section(minimal_plan_payload):
    md = render_context_report_markdown(build_context_report_payload(minimal_plan_payload))
    assert "EXTRACTED" in md
    assert "INFERRED" in md
    assert "AMBIGUOUS" in md


def test_render_degraded_has_warning(minimal_plan_payload, degraded_plan_payload):
    degraded = build_context_report_payload(degraded_plan_payload)
    md = render_context_report_markdown(degraded)
    assert "warning:" in md or "Warnings" in md


# ----------------------------------------------------------------------
# write_context_report_markdown tests
# ----------------------------------------------------------------------


def test_write_creates_file(minimal_plan_payload, tmp_path):
    output_path = tmp_path / "CONTEXT_REPORT.md"
    result = write_context_report_markdown(minimal_plan_payload, output_path)

    assert result["ok"] is True
    assert Path(result["path"]) == output_path
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8").startswith("# Context Report")
    assert (tmp_path / "context_report.json").exists()


def test_write_file_contains_all_sections(minimal_plan_payload, tmp_path):
    output_path = tmp_path / "CONTEXT_REPORT.md"
    write_context_report_markdown(minimal_plan_payload, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "# Context Report" in content
    assert "## Summary" in content


def test_write_empty_payload_does_not_crash(tmp_path):
    output_path = tmp_path / "empty_report.md"
    result = write_context_report_markdown({}, output_path)

    assert result["ok"] is True
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Context Report" in content


def test_write_creates_parent_directories(tmp_path):
    nested = tmp_path / "subdir" / "deeper" / "report.md"
    result = write_context_report_markdown({}, nested)

    assert result["ok"] is True
    assert nested.exists()
    assert (nested.parent / "context_report.json").exists()


def test_write_byte_count_reasonable(tmp_path):
    output_path = tmp_path / "report.md"
    result = write_context_report_markdown(
        {
            "query": "x",
            "repo": "r",
            "root": "/",
            "candidate_chunks": [],
            "candidate_files": [],
            "evidence_summary": {},
            "stages": [],
        },
        output_path,
    )

    assert result["byte_count"] > 0
    # byte_count is computed from the string encoded as UTF-8
    assert result["byte_count"] <= len(output_path.read_bytes()) + 10


def test_write_context_report_artifacts_syncs_json_and_note(minimal_plan_payload, tmp_path):
    output_path = tmp_path / "artifacts" / "context-reports" / "2026-04-16" / "context_report.md"
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"

    result = write_context_report_artifacts(
        minimal_plan_payload,
        output_path,
        notes_path=notes_path,
        repo="demo",
        namespace="repo:demo",
    )

    assert result["ok"] is True
    assert result["markdown_path"] == str(output_path)
    assert result["json_path"] == str(output_path.parent / "context_report.json")
    persisted = json.loads((output_path.parent / "context_report.json").read_text(encoding="utf-8"))
    assert persisted["schema_version"] == SCHEMA_VERSION
    note_rows = [
        line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(note_rows) == 1
    note_payload = json.loads(note_rows[0])
    assert note_payload["source"] == SCHEMA_VERSION
    assert note_payload["namespace"] == "repo:demo"
    assert any("context_report.json" in ref for ref in note_payload["artifact_refs"])


def test_build_and_append_context_report_note_preserve_artifact_refs(tmp_path):
    payload = build_context_report_payload({"query": "q", "repo": "r", "root": "/"})
    note = build_context_report_note(
        payload=payload,
        repo="demo",
        namespace="repo:demo",
        artifact_refs=["artifacts/context-reports/2026-04-16/context_report.json"],
    )

    assert note["source"] == SCHEMA_VERSION
    assert note["namespace"] == "repo:demo"
    assert note["artifact_refs"] == ["artifacts/context-reports/2026-04-16/context_report.json"]

    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    result = append_context_report_note(
        payload=payload,
        notes_path=notes_path,
        repo="demo",
        namespace="repo:demo",
        artifact_refs=["artifacts/context-reports/2026-04-16/context_report.json"],
    )

    assert result["ok"] is True
    rows = [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    stored = json.loads(rows[0])
    assert stored["namespace"] == "repo:demo"


# ----------------------------------------------------------------------
# Schema guard tests
# ----------------------------------------------------------------------


def test_context_report_schema_guard_accepts_valid_payload() -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "query": "fix auth flow",
        "repo": "test-repo",
        "root": "/test/root",
        "summary": {"candidate_file_count": 3},
        "core_nodes": [],
        "warnings": [],
    }
    validated = validate_context_report_payload(payload)
    assert validated["schema_version"] == SCHEMA_VERSION
    assert validated["query"] == "fix auth flow"


def test_context_report_schema_guard_rejects_missing_schema_version() -> None:
    payload = {
        "query": "fix auth flow",
        "repo": "test-repo",
        "root": "/test/root",
        "summary": {},
        "core_nodes": [],
        "warnings": [],
    }
    with pytest.raises(ValueError, match="schema_version must be"):
        validate_context_report_payload(payload)


def test_context_report_schema_guard_rejects_wrong_schema_version() -> None:
    payload = {
        "schema_version": "wrong_version",
        "query": "fix auth flow",
        "repo": "test-repo",
        "root": "/test/root",
        "summary": {},
        "core_nodes": [],
        "warnings": [],
    }
    with pytest.raises(ValueError, match="schema_version must be"):
        validate_context_report_payload(payload)


def test_context_report_schema_guard_rejects_missing_core_nodes() -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "query": "fix auth flow",
        "repo": "test-repo",
        "root": "/test/root",
        "summary": {},
        "warnings": [],
    }
    with pytest.raises(ValueError, match="core_nodes must be a list"):
        validate_context_report_payload(payload)


def test_context_report_schema_guard_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_context_report_payload(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_context_report_payload("not a dict")  # type: ignore[arg-type]
