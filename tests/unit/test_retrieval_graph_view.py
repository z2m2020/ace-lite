"""Unit tests for the retrieval_graph_view module (L8506)."""

from __future__ import annotations

import re

import pytest

from ace_lite.retrieval_graph_view import (
    RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
    build_retrieval_graph_view,
    validate_retrieval_graph_view_payload,
)

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _minimal_plan() -> dict:
    return {
        "query": "implement adder",
        "repo": "mini-calc",
        "root": "/tmp/mini-calc",
        "candidate_files": [
            {"path": "src/adder.py", "score": 9.0},
            {"path": "tests/test_adder.py", "score": 3.0},
        ],
        "candidate_chunks": [
            {
                "path": "src/adder.py",
                "qualified_name": "add",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 3,
                "score": 9.0,
                "evidence_confidence": "EXTRACTED",
                "confidence_score": 1.0,
            },
            {
                "path": "src/adder.py",
                "qualified_name": "subtract",
                "kind": "function",
                "lineno": 5,
                "end_lineno": 7,
                "score": 7.5,
                "evidence_confidence": "EXTRACTED",
                "confidence_score": 0.95,
            },
            {
                "path": "tests/test_adder.py",
                "qualified_name": "test_add",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 5,
                "score": 3.0,
                "evidence_confidence": "AMBIGUOUS",
                "confidence_score": 0.35,
            },
        ],
        "index": {
            "candidate_files": [],
        },
        "repomap": {
            "focused_files": ["src/adder.py", "tests/test_adder.py"],
        },
        "subgraph_payload": {
            "enabled": True,
            "reason": "ok",
            "seed_paths": ["src/adder.py"],
            "edge_counts": {"cochange_edges": 2, "xref_edges": 1},
        },
    }


# ----------------------------------------------------------------------
# build_retrieval_graph_view tests
# ----------------------------------------------------------------------


def test_returns_correct_schema_version():
    result = build_retrieval_graph_view(_minimal_plan())
    assert result["schema_version"] == RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION


def test_ok_true_for_non_empty_payload():
    result = build_retrieval_graph_view(_minimal_plan())
    assert result["ok"] is True


def test_nested_source_plan_payload_reads_real_orchestrator_shape():
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

    result = build_retrieval_graph_view(payload, repo="r", root="x", query="q")

    assert result["ok"] is True
    assert result["summary"]["node_count"] >= 2
    assert {node["id"] for node in result["nodes"]} >= {"src/a.py", "src/a.py::f"}
    assert any(edge["kind"] == "grouping" for edge in result["edges"])


def test_ok_false_for_empty_payload():
    result = build_retrieval_graph_view({})
    assert result["ok"] is False


def test_ok_false_when_no_candidates():
    result = build_retrieval_graph_view(
        {
            "query": "test",
            "repo": "r",
            "root": "/",
            "candidate_files": [],
            "candidate_chunks": [],
            "index": {"candidate_files": []},
        }
    )
    assert result["ok"] is False


def test_nodes_are_sorted_by_score():
    result = build_retrieval_graph_view(_minimal_plan())
    nodes = result["nodes"]
    scores = [n["score"] for n in nodes]
    assert scores == sorted(scores, reverse=True)


def test_file_and_chunk_nodes_both_present():
    result = build_retrieval_graph_view(_minimal_plan())
    nodes = result["nodes"]
    kinds = {n["kind"] for n in nodes}
    assert "file" in kinds
    assert "function" in kinds


def test_chunk_nodes_have_lineno_and_end_lineno():
    result = build_retrieval_graph_view(_minimal_plan())
    chunk_nodes = [n for n in result["nodes"] if n["kind"] == "function"]
    for chunk in chunk_nodes:
        assert "lineno" in chunk
        assert "end_lineno" in chunk


def test_chunk_nodes_have_evidence_confidence():
    result = build_retrieval_graph_view(_minimal_plan())
    chunk_nodes = [n for n in result["nodes"] if n["kind"] == "function"]
    for chunk in chunk_nodes:
        assert "evidence_confidence" in chunk
        assert chunk["evidence_confidence"] in (
            "EXTRACTED",
            "INFERRED",
            "AMBIGUOUS",
            "UNKNOWN",
            None,
        )


def test_limit_applied():
    plan = _minimal_plan()
    result = build_retrieval_graph_view(plan, limit=2)
    assert result["summary"]["node_count"] <= 2
    assert result["summary"]["node_limit_applied"] is True


def test_limit_not_applied_when_under_limit():
    result = build_retrieval_graph_view(_minimal_plan(), limit=100)
    assert result["summary"]["node_limit_applied"] is False


def test_scope_fields_present():
    result = build_retrieval_graph_view(_minimal_plan())
    scope = result["scope"]
    assert "repo" in scope
    assert "root" in scope
    assert "limit" in scope
    assert "max_hops" in scope


def test_edges_have_required_fields():
    result = build_retrieval_graph_view(_minimal_plan())
    for edge in result["edges"]:
        assert "id" in edge
        assert "source" in edge
        assert "target" in edge
        assert "kind" in edge
        assert "predicate" in edge
        assert "confidence" in edge


def test_grouping_edges_connect_file_to_chunks():
    result = build_retrieval_graph_view(_minimal_plan())
    grouping_edges = [e for e in result["edges"] if e["kind"] == "grouping"]
    # src/adder.py should have edges to its chunks
    assert len(grouping_edges) >= 2


def test_graph_signal_edges_from_subgraph_payload():
    result = build_retrieval_graph_view(_minimal_plan())
    graph_edges = [e for e in result["edges"] if e["kind"] == "graph_signal"]
    # Self-loop proxy edges are NOT created — they misrepresented graph connectivity.
    # Instead, a warning is emitted when graph signals are detected but no real
    # neighbor edges exist.
    assert len(graph_edges) == 0, "self-loop proxy edges should not be created"
    # Warning should indicate proxy-only signals
    warnings = result.get("warnings", [])
    assert any("proxy_only" in w.lower() or "no real neighbor" in w.lower() for w in warnings), (
        f"expected proxy_only warning, got: {warnings}"
    )


def test_summary_contains_counts():
    result = build_retrieval_graph_view(_minimal_plan())
    summary = result["summary"]
    assert "node_count" in summary
    assert "edge_count" in summary
    assert "node_limit_applied" in summary
    assert summary["node_count"] == len(result["nodes"])
    assert summary["edge_count"] == len(result["edges"])


def test_node_has_source_field():
    result = build_retrieval_graph_view(_minimal_plan())
    for node in result["nodes"]:
        assert "source" in node
        assert node["source"] in ("source_plan", "index", "repomap")


def test_warnings_present_when_no_data():
    result = build_retrieval_graph_view({})
    assert len(result["warnings"]) >= 1


def test_repo_and_root_override():
    plan = _minimal_plan()
    result = build_retrieval_graph_view(plan, repo="override-repo", root="/override/root")
    assert result["repo"] == "override-repo"
    assert result["root"] == "/override/root"


def test_query_override():
    plan = _minimal_plan()
    result = build_retrieval_graph_view(plan, query="override query")
    assert result["query"] == "override query"


def test_invalid_limit_and_max_hops_fall_back_to_safe_defaults():
    result = build_retrieval_graph_view(_minimal_plan(), limit="bad", max_hops="bad")
    assert result["ok"] is True
    assert result["scope"]["limit"] == 50
    assert result["scope"]["max_hops"] == 1


def test_chunk_score_breakdown_graph_signals():
    plan = {
        "query": "graph signals",
        "repo": "test",
        "root": "/test",
        "candidate_files": [{"path": "src/a.py", "score": 5.0}],
        "candidate_chunks": [
            {
                "path": "src/a.py",
                "qualified_name": "fn",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 5,
                "score": 5.0,
                "score_breakdown": {
                    "cochange_boost": 0.5,
                    "graph_closure_bonus": 0.3,
                },
            },
        ],
        "index": {"candidate_files": []},
        "repomap": {"focused_files": []},
        "subgraph_payload": {"enabled": False, "seed_paths": [], "edge_counts": {}},
    }
    result = build_retrieval_graph_view(plan)
    graph_edges = [e for e in result["edges"] if e["kind"] == "graph_signal"]
    # Chunk boosts do NOT create self-loop edges — they are informational only.
    assert len(graph_edges) == 0, "chunk boost self-loop edges should not be created"
    warnings = result.get("warnings", [])
    assert any(
        "chunk_graph_signals_proxy_only" in w or "no real neighbor" in w for w in warnings
    ), f"expected chunk_graph_signals_proxy_only warning, got: {warnings}"


def test_string_edge_count_is_coerced_without_error():
    plan = {
        "query": "string edge count",
        "repo": "test",
        "root": "/test",
        "source_plan": {
            "candidate_files": [{"path": "src/a.py", "score": 5.0}],
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "fn",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 5,
                    "score": 5.0,
                },
            ],
            "subgraph_payload": {
                "enabled": True,
                "seed_paths": ["src/a.py"],
                "edge_counts": {"cochange_edges": "2"},
            },
        },
        "index": {"candidate_files": []},
        "repomap": {"focused_files": []},
    }

    result = build_retrieval_graph_view(plan)
    assert result["ok"] is True
    assert any("graph_signals_proxy_only" in w for w in result["warnings"])


def test_index_candidate_files_included():
    plan = {
        "query": "index files test",
        "repo": "test",
        "root": "/test",
        "candidate_files": [],
        "candidate_chunks": [],
        "index": {
            "candidate_files": [
                {"path": "lib/util.py", "score": 8.0},
            ],
        },
        "repomap": {"focused_files": []},
    }
    result = build_retrieval_graph_view(plan)
    assert result["ok"] is True
    assert len(result["nodes"]) >= 1


def test_repomap_focused_adds_source_repomap():
    plan = {
        "query": "repomap test",
        "repo": "test",
        "root": "/test",
        "candidate_files": [],
        "candidate_chunks": [],
        "index": {"candidate_files": []},
        "repomap": {
            "focused_files": ["src/core.py", "src/util.py"],
        },
    }
    result = build_retrieval_graph_view(plan)
    node_sources = {n["source"] for n in result["nodes"]}
    assert "repomap" in node_sources


# ----------------------------------------------------------------------
# Truncation governance tests
# ----------------------------------------------------------------------


def test_retrieval_graph_truncation_warning_applied() -> None:
    """When more candidates exist than limit, node_limit_applied is True and a warning is emitted."""
    plan = {
        "query": "truncate test",
        "repo": "test",
        "root": "/test",
        "candidate_files": [
            {"path": f"src/file{i}.py", "score": 10.0 - i * 0.1} for i in range(60)
        ],
        "candidate_chunks": [],
        "index": {"candidate_files": []},
    }
    result = build_retrieval_graph_view(plan, limit=10)
    assert result["summary"]["node_limit_applied"] is True
    assert any("node_limit_applied" in w for w in result["warnings"])


def test_retrieval_graph_no_truncation_warning_when_within_limit() -> None:
    """When fewer candidates than limit, no truncation warning is emitted."""
    plan = {
        "query": "no truncate test",
        "repo": "test",
        "root": "/test",
        "candidate_files": [{"path": "src/one.py", "score": 9.0}],
        "candidate_chunks": [],
        "index": {"candidate_files": []},
    }
    result = build_retrieval_graph_view(plan, limit=50)
    assert result["summary"]["node_limit_applied"] is False
    assert not any("node_limit_applied" in w for w in result["warnings"])


def test_retrieval_graph_max_hops_boundary_warning() -> None:
    """When max_hops exceeds 3, a warning is emitted and value is capped at 3."""
    plan = {
        "query": "max hops test",
        "repo": "test",
        "root": "/test",
        "candidate_files": [],
        "candidate_chunks": [],
        "index": {"candidate_files": []},
        "repomap": {"focused_files": ["a.py", "b.py"]},
    }
    result = build_retrieval_graph_view(plan, max_hops=10)
    assert result["scope"]["max_hops"] == 3
    assert result["summary"]["max_hops"] == 3
    assert any("max_hops_capped" in w for w in result["warnings"])


def test_retrieval_graph_max_hops_no_warning_within_boundary() -> None:
    """When max_hops is within 1-3, no capping warning is emitted."""
    plan = {
        "query": "max hops ok",
        "repo": "test",
        "root": "/test",
        "candidate_files": [],
        "candidate_chunks": [],
        "index": {"candidate_files": []},
        "repomap": {"focused_files": ["a.py"]},
    }
    result = build_retrieval_graph_view(plan, max_hops=2)
    assert result["scope"]["max_hops"] == 2
    assert not any("max_hops_capped" in w for w in result["warnings"])


# ----------------------------------------------------------------------
# Schema guard tests
# ----------------------------------------------------------------------


def test_retrieval_graph_schema_guard_accepts_valid_payload() -> None:
    payload = {
        "ok": True,
        "schema_version": RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
        "repo": "test-repo",
        "root": "/test/root",
        "query": "find auth",
        "scope": {"repo": "test-repo", "root": "/test/root", "limit": 50, "max_hops": 1},
        "summary": {
            "node_count": 3,
            "edge_count": 2,
            "node_limit_applied": False,
            "max_hops": 1,
            "limit": 50,
        },
        "nodes": [],
        "edges": [],
        "warnings": [],
    }
    validated = validate_retrieval_graph_view_payload(payload)
    assert validated["schema_version"] == RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION


def test_retrieval_graph_schema_guard_rejects_wrong_schema_version() -> None:
    payload = {
        "ok": True,
        "schema_version": "wrong_version",
        "repo": "test",
        "root": "/test",
        "query": "x",
        "scope": {"repo": "test", "root": "/test", "limit": 50, "max_hops": 1},
        "summary": {
            "node_count": 0,
            "edge_count": 0,
            "node_limit_applied": False,
            "max_hops": 1,
            "limit": 50,
        },
        "nodes": [],
        "edges": [],
        "warnings": [],
    }
    with pytest.raises(ValueError, match="schema_version must be"):
        validate_retrieval_graph_view_payload(payload)


def test_retrieval_graph_schema_guard_rejects_missing_scope() -> None:
    payload = {
        "ok": True,
        "schema_version": RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
        "repo": "test",
        "root": "/test",
        "query": "x",
        "summary": {
            "node_count": 0,
            "edge_count": 0,
            "node_limit_applied": False,
            "max_hops": 1,
            "limit": 50,
        },
        "nodes": [],
        "edges": [],
        "warnings": [],
    }
    with pytest.raises(ValueError, match="scope is required"):
        validate_retrieval_graph_view_payload(payload)


def test_retrieval_graph_schema_guard_rejects_missing_summary_keys() -> None:
    payload = {
        "ok": True,
        "schema_version": RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
        "repo": "test",
        "root": "/test",
        "query": "x",
        "scope": {"repo": "test", "root": "/test", "limit": 50, "max_hops": 1},
        "summary": {"node_count": 0, "edge_count": 0},
        "nodes": [],
        "edges": [],
        "warnings": [],
    }
    with pytest.raises(
        ValueError,
        match=re.escape("summary.node_limit_applied is required"),
    ):
        validate_retrieval_graph_view_payload(payload)
