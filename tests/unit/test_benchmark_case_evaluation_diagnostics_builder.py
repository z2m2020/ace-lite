from __future__ import annotations

import pytest

from ace_lite.benchmark.case_evaluation_diagnostics import (
    build_case_evaluation_diagnostics,
)
from ace_lite.benchmark.case_evaluation_diagnostics_builder import (
    build_case_evaluation_diagnostics_from_namespace,
)


def test_build_case_evaluation_diagnostics_from_namespace_matches_direct_call() -> None:
    namespace = {
        "case": {"id": "case-1", "task_success": {"mode": "recall_or_validation"}},
        "expected": ["src/app.py"],
        "recall_hit": 1.0,
        "validation_tests": ["pytest tests/unit/test_demo.py"],
        "top_candidates": [{"path": "src/app.py"}, {"path": "src/other.py"}],
        "candidate_chunks": [{"qualified_name": "src.app:demo"}],
        "chunk_hit_at_k": 1.0,
        "noise": 0.1,
        "docs_enabled_flag": True,
        "docs_hit": 0.5,
        "dependency_recall": 0.25,
        "neighbor_paths": ["src/dependency.py"],
        "skills_budget_exhausted": False,
        "memory_gate_skipped": False,
        "memory_gate_skip_reason": "",
        "memory_fallback_reason": "",
        "memory_namespace_fallback": "",
        "candidate_ranker_fallbacks": [],
        "exact_search_payload": {"enabled": True},
        "second_pass_payload": {"enabled": False},
        "refine_pass_payload": {"enabled": True},
        "docs_backend_fallback_reason": "",
        "parallel_docs_timed_out": False,
        "parallel_worktree_timed_out": False,
        "embedding_adaptive_budget_applied": False,
        "embedding_time_budget_exceeded": False,
        "embedding_fallback": False,
        "chunk_semantic_time_budget_exceeded": False,
        "chunk_semantic_fallback": False,
        "chunk_semantic_reason": "",
        "xref_budget_exhausted": False,
        "chunk_guard_payload": {"enabled": False},
    }

    expected = build_case_evaluation_diagnostics(
        case=namespace["case"],
        expected=namespace["expected"],
        recall_hit=namespace["recall_hit"],
        validation_tests=namespace["validation_tests"],
        candidate_file_count=len(namespace["top_candidates"]),
        candidate_chunk_count=len(namespace["candidate_chunks"]),
        chunk_hit_at_k=namespace["chunk_hit_at_k"],
        noise_rate=namespace["noise"],
        docs_enabled=namespace["docs_enabled_flag"],
        docs_hit=namespace["docs_hit"],
        dependency_recall=namespace["dependency_recall"],
        neighbor_paths=namespace["neighbor_paths"],
        skills_budget_exhausted=namespace["skills_budget_exhausted"],
        memory_gate_skipped=namespace["memory_gate_skipped"],
        memory_gate_skip_reason=namespace["memory_gate_skip_reason"],
        memory_fallback_reason=namespace["memory_fallback_reason"],
        memory_namespace_fallback=namespace["memory_namespace_fallback"],
        candidate_ranker_fallbacks=namespace["candidate_ranker_fallbacks"],
        exact_search_payload=namespace["exact_search_payload"],
        second_pass_payload=namespace["second_pass_payload"],
        refine_pass_payload=namespace["refine_pass_payload"],
        docs_backend_fallback_reason=namespace["docs_backend_fallback_reason"],
        parallel_docs_timed_out=namespace["parallel_docs_timed_out"],
        parallel_worktree_timed_out=namespace["parallel_worktree_timed_out"],
        embedding_adaptive_budget_applied=namespace[
            "embedding_adaptive_budget_applied"
        ],
        embedding_time_budget_exceeded=namespace[
            "embedding_time_budget_exceeded"
        ],
        embedding_fallback=namespace["embedding_fallback"],
        chunk_semantic_time_budget_exceeded=namespace[
            "chunk_semantic_time_budget_exceeded"
        ],
        chunk_semantic_fallback=namespace["chunk_semantic_fallback"],
        chunk_semantic_reason=namespace["chunk_semantic_reason"],
        xref_budget_exhausted=namespace["xref_budget_exhausted"],
        chunk_guard_payload=namespace["chunk_guard_payload"],
    )

    actual = build_case_evaluation_diagnostics_from_namespace(namespace=namespace)

    assert actual == expected


def test_build_case_evaluation_diagnostics_from_namespace_raises_for_missing_input() -> None:
    with pytest.raises(KeyError, match="candidate_chunks"):
        build_case_evaluation_diagnostics_from_namespace(
            namespace={
                "case": {},
                "expected": [],
                "recall_hit": 0.0,
                "validation_tests": [],
                "top_candidates": [],
                "chunk_hit_at_k": 0.0,
                "noise": 0.0,
                "docs_enabled_flag": False,
                "docs_hit": 0.0,
                "dependency_recall": 0.0,
                "neighbor_paths": [],
                "skills_budget_exhausted": False,
                "memory_gate_skipped": False,
                "memory_gate_skip_reason": "",
                "memory_fallback_reason": "",
                "memory_namespace_fallback": "",
                "candidate_ranker_fallbacks": [],
                "exact_search_payload": {},
                "second_pass_payload": {},
                "refine_pass_payload": {},
                "docs_backend_fallback_reason": "",
                "parallel_docs_timed_out": False,
                "parallel_worktree_timed_out": False,
                "embedding_adaptive_budget_applied": False,
                "embedding_time_budget_exceeded": False,
                "embedding_fallback": False,
                "chunk_semantic_time_budget_exceeded": False,
                "chunk_semantic_fallback": False,
                "chunk_semantic_reason": "",
                "xref_budget_exhausted": False,
                "chunk_guard_payload": {},
            }
        )
