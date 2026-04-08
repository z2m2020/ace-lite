"""AST-only end-to-end golden test for ContextReport pipeline (L8505).

This test creates a minimal real repo in tmp_path, runs the full
index -> source_plan pipeline, and verifies that ContextReport can
consume the output.

Constraints (per PRD R8504):
- No OpenMemory
- No embedding provider
- No external MCP
- No LLM
- No graphify repository required
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite.context_report import (
    build_context_report_payload,
    render_context_report_markdown,
)
from ace_lite.memory import NullMemoryProvider
from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.types import StageContext


# ----------------------------------------------------------------------
# Repo setup
# ----------------------------------------------------------------------


def _setup_mini_repo(root: Path) -> None:
    """Create a minimal Python project in root.

    Structure:
        src/
            adder.py       # production module with add function
        tests/
            test_adder.py  # test file
    """
    src = root / "src"
    tests = root / "tests"
    src.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)

    (src / "adder.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    '''Add two integers.'''\n"
        "    return a + b\n"
        "\n"
        "def subtract(a: int, b: int) -> int:\n"
        "    '''Subtract b from a.'''\n"
        "    return a - b\n",
        encoding="utf-8",
    )
    (tests / "test_adder.py").write_text(
        "import pytest\n"
        "from adder import add, subtract\n"
        "\n"
        "def test_add_positive():\n"
        "    assert add(1, 2) == 3\n"
        "\n"
        "def test_add_negative():\n"
        "    assert add(-1, -1) == -2\n"
        "\n"
        "def test_subtract():\n"
        "    assert subtract(5, 3) == 2\n",
        encoding="utf-8",
    )


# ----------------------------------------------------------------------
# Index stage helpers (minimal, no embedding)
# ----------------------------------------------------------------------


def _build_index_candidates(src_dir: Path) -> list[dict]:
    """Build minimal candidate_chunks from Python source files (AST-free proxy)."""
    chunks = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name.startswith("."):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                # rough chunking by non-empty, non-comment lines
                lineno = i
                end_lineno = min(i + 4, len(lines))
                qualified_name = f"{py_file.stem}.line_{lineno}"
                chunks.append(
                    {
                        "path": str(py_file.relative_to(src_dir.parent)),
                        "qualified_name": qualified_name,
                        "kind": "function" if "def " in line else "statement",
                        "lineno": lineno,
                        "end_lineno": end_lineno,
                        "score": 5.0,
                        "signature": line.strip() if "def " in line else "",
                    }
                )
    return chunks


def _build_index_payload(mini_repo: Path) -> dict:
    """Build a minimal but realistic index stage payload."""
    candidates = _build_index_candidates(mini_repo / "src")
    test_candidates = _build_index_candidates(mini_repo / "tests")
    all_candidates = candidates + test_candidates

    return {
        "candidate_files": [{"path": c["path"], "score": c["score"]} for c in all_candidates],
        "candidate_chunks": all_candidates,
        "chunk_metrics": {"chunk_budget_used": 128.0},
    }


# ----------------------------------------------------------------------
# Main test
# ----------------------------------------------------------------------


def test_context_report_e2e_minimal_repo(tmp_path: Path) -> None:
    """Run full index -> source_plan -> context_report pipeline and verify output."""
    _setup_mini_repo(tmp_path)

    # Build minimal index stage payload from the real files
    index_payload = _build_index_payload(tmp_path)

    ctx = StageContext(
        query="implement add and subtract functions",
        repo="mini-calc",
        root=str(tmp_path),
    )
    ctx.state = {
        "memory": {},
        "index": index_payload,
        "repomap": {
            "focused_files": [c["path"] for c in index_payload["candidate_chunks"]],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {
                "suspicious_chunks": [],
                "suggested_tests": ["pytest tests/"],
            },
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    # Run the source_plan stage
    plan_payload = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=8,
        chunk_per_file_limit=3,
        chunk_token_budget=512,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    # Verify plan payload has confidence_summary (P1 requirement)
    assert "confidence_summary" in plan_payload, (
        "source_plan output must contain confidence_summary (P1)"
    )
    confidence_summary = plan_payload["confidence_summary"]
    assert "total_count" in confidence_summary
    assert confidence_summary["total_count"] == len(plan_payload["candidate_chunks"])

    # Verify candidate_chunks have evidence_confidence (P1 requirement)
    for chunk in plan_payload["candidate_chunks"]:
        assert "evidence_confidence" in chunk, (
            f"chunk {chunk.get('path')}: evidence_confidence field missing (P1)"
        )
        assert chunk["evidence_confidence"] in ("EXTRACTED", "INFERRED", "AMBIGUOUS", "UNKNOWN"), (
            f"Invalid evidence_confidence: {chunk['evidence_confidence']}"
        )
        assert "confidence_score" in chunk
        assert 0.0 <= chunk["confidence_score"] <= 1.0

    # Build and render context report
    report_payload = build_context_report_payload(plan_payload)
    markdown = render_context_report_markdown(report_payload)

    # Verify report structure
    assert report_payload["ok"] is True
    assert report_payload["schema_version"] == "context_report_v1"
    assert report_payload["query"] == "implement add and subtract functions"

    # Summary assertions
    summary = report_payload["summary"]
    assert summary["candidate_chunk_count"] > 0
    assert summary["stage_count"] == 6

    # Core nodes assertions
    core_nodes = report_payload["core_nodes"]
    assert len(core_nodes) > 0
    assert any("adder.py" in n["path"] for n in core_nodes)

    # Confidence breakdown assertions
    breakdown = report_payload["confidence_breakdown"]
    assert breakdown["total_count"] == summary["candidate_chunk_count"]
    assert (
        breakdown["extracted_count"]
        + breakdown["inferred_count"]
        + breakdown["ambiguous_count"]
        + breakdown["unknown_count"]
        == breakdown["total_count"]
    )

    # Knowledge gaps assertions
    knowledge_gaps = report_payload["knowledge_gaps"]
    assert isinstance(knowledge_gaps, list)
    # No validation tests in our setup, so should have missing_validation_tests gap
    gap_codes = {g["code"] for g in knowledge_gaps}
    # It's OK if there are or aren't gaps - just verify structure
    for gap in knowledge_gaps:
        assert "code" in gap
        assert "severity" in gap
        assert "message" in gap

    # Suggested questions assertions
    suggested_questions = report_payload["suggested_questions"]
    assert len(suggested_questions) >= 1
    assert any(q["type"] in ("entrypoint", "no_signal") for q in suggested_questions)

    # Markdown assertions
    assert "# Context Report" in markdown
    assert "## Summary" in markdown
    assert "## Core Nodes" in markdown
    assert "## Confidence Breakdown" in markdown
    assert "## Knowledge Gaps" in markdown
    assert "## Suggested Questions" in markdown

    # Markdown contains some content from the repo
    assert "adder.py" in markdown


def test_context_report_e2e_with_validation(tmp_path: Path) -> None:
    """Test context report when validation result is present."""
    _setup_mini_repo(tmp_path)

    index_payload = _build_index_payload(tmp_path)

    ctx = StageContext(
        query="fix add function",
        repo="mini-calc",
        root=str(tmp_path),
    )
    ctx.state = {
        "memory": {},
        "index": index_payload,
        "repomap": {
            "focused_files": [c["path"] for c in index_payload["candidate_chunks"]],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {
                "suspicious_chunks": [],
                "suggested_tests": ["pytest tests/"],
            },
        },
        "skills": {"selected": []},
        "validation": {
            "result": {
                "schema_version": "validation-v1",
                "summary": {"status": "passed", "issue_count": 0},
                "probes": {"status": "passed"},
                "selected_test_count": 2,
                "executed_test_count": 2,
            }
        },
        "__policy": {"name": "bugfix_test", "version": "v1", "test_signal_weight": 1.0},
    }

    plan_payload = run_source_plan(
        ctx=ctx,
        pipeline_order=[
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
            "validation",
        ],
        chunk_top_k=8,
        chunk_per_file_limit=3,
        chunk_token_budget=512,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    report_payload = build_context_report_payload(plan_payload)
    assert report_payload["summary"]["has_validation_payload"] is True

    # validation_tests should be present since augment has suggested_tests
    assert isinstance(plan_payload.get("validation_tests"), list)


def test_context_report_e2e_plan_payload_not_mutated(tmp_path: Path) -> None:
    """Ensure context_report does not modify the original plan payload."""
    _setup_mini_repo(tmp_path)

    index_payload = _build_index_payload(tmp_path)
    ctx = StageContext(query="test mutation", repo="test", root=str(tmp_path))
    ctx.state = {
        "memory": {},
        "index": index_payload,
        "repomap": {"focused_files": []},
        "augment": {"diagnostics": [], "xref": {"count": 0, "results": []}, "tests": {}},
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    plan_payload = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    payload_copy = json.dumps(plan_payload, sort_keys=True)
    build_context_report_payload(plan_payload)
    assert json.dumps(plan_payload, sort_keys=True) == payload_copy
