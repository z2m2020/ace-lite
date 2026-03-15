from __future__ import annotations

from ace_lite.benchmark.case_evaluation_diagnostics import (
    build_case_evaluation_diagnostics,
)


def test_build_case_evaluation_diagnostics_contract() -> None:
    diagnostics = build_case_evaluation_diagnostics(
        case={
            "task_success": {"min_validation_tests": 1},
            "chunk_guard_expectation": {
                "scenario": "stale_majority",
                "expected_retained_refs": ["auth.validate"],
                "expected_filtered_refs": ["token.issue"],
            },
        },
        expected=["auth"],
        recall_hit=1.0,
        validation_tests=["tests.test_auth::test_token"],
        candidate_file_count=2,
        candidate_chunk_count=1,
        chunk_hit_at_k=1.0,
        noise_rate=0.0,
        docs_enabled=True,
        docs_hit=1.0,
        dependency_recall=1.0,
        neighbor_paths=["docs/guide.md"],
        skills_budget_exhausted=True,
        memory_gate_skipped=True,
        memory_gate_skip_reason="cold_start",
        memory_fallback_reason="namespace_miss",
        memory_namespace_fallback="global",
        candidate_ranker_fallbacks=["semantic_timeout"],
        exact_search_payload={"enabled": True},
        second_pass_payload={},
        refine_pass_payload={},
        docs_backend_fallback_reason="",
        parallel_docs_timed_out=True,
        parallel_worktree_timed_out=False,
        embedding_adaptive_budget_applied=True,
        embedding_time_budget_exceeded=False,
        embedding_fallback=False,
        chunk_semantic_time_budget_exceeded=True,
        chunk_semantic_fallback=True,
        chunk_semantic_reason="budgeted",
        xref_budget_exhausted=True,
        chunk_guard_payload={
            "retained_refs": ["auth.validate"],
            "filtered_refs": ["token.issue"],
        },
    )

    assert diagnostics.task_success_hit == 1.0
    assert "parallel_docs_timeout" in diagnostics.slo_downgrade_signals
    assert "xref_budget_exhausted" in diagnostics.slo_downgrade_signals
    assert diagnostics.evidence_insufficiency["evidence_insufficient"] == 0.0
    assert diagnostics.decision_trace
    assert diagnostics.chunk_guard_expectation["applicable"] is True
    assert diagnostics.chunk_guard_expectation["expected_retained_hit"] is True
