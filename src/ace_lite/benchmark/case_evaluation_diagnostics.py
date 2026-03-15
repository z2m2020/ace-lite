"""Diagnostics bundle helpers for benchmark case evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.benchmark.case_evaluation_details import (
    build_decision_trace,
    build_evidence_insufficiency,
)
from ace_lite.benchmark.case_evaluation_expectations import (
    evaluate_chunk_guard_expectation,
    evaluate_task_success,
)


@dataclass(frozen=True, slots=True)
class CaseEvaluationDiagnostics:
    task_success_config: dict[str, Any]
    task_success_failed_checks: list[str]
    task_success_hit: float
    slo_downgrade_signals: list[str]
    evidence_insufficiency: dict[str, Any]
    decision_trace: list[dict[str, Any]]
    chunk_guard_expectation: dict[str, Any]


def build_case_evaluation_diagnostics(
    *,
    case: dict[str, Any],
    expected: list[str],
    recall_hit: float,
    validation_tests: list[Any],
    candidate_file_count: int,
    candidate_chunk_count: int,
    chunk_hit_at_k: float,
    noise_rate: float,
    docs_enabled: bool,
    docs_hit: float,
    dependency_recall: float,
    neighbor_paths: list[str],
    skills_budget_exhausted: bool,
    memory_gate_skipped: bool,
    memory_gate_skip_reason: str,
    memory_fallback_reason: str,
    memory_namespace_fallback: str,
    candidate_ranker_fallbacks: list[str],
    exact_search_payload: dict[str, Any],
    second_pass_payload: dict[str, Any],
    refine_pass_payload: dict[str, Any],
    docs_backend_fallback_reason: str,
    parallel_docs_timed_out: bool,
    parallel_worktree_timed_out: bool,
    embedding_adaptive_budget_applied: bool,
    embedding_time_budget_exceeded: bool,
    embedding_fallback: bool,
    chunk_semantic_time_budget_exceeded: bool,
    chunk_semantic_fallback: bool,
    chunk_semantic_reason: str,
    xref_budget_exhausted: bool,
    chunk_guard_payload: dict[str, Any],
) -> CaseEvaluationDiagnostics:
    task_success = evaluate_task_success(
        case=case,
        expected=expected,
        recall_hit=recall_hit,
        validation_tests=validation_tests,
    )
    task_success_config = dict(task_success["config"])
    task_success_failed_checks = list(task_success["failed_checks"])
    task_success_hit = float(task_success["hit"])
    slo_downgrade_signals = [
        name
        for name, active in (
            ("parallel_docs_timeout", parallel_docs_timed_out),
            ("parallel_worktree_timeout", parallel_worktree_timed_out),
            ("embedding_time_budget_exceeded", embedding_time_budget_exceeded),
            ("embedding_adaptive_budget_applied", embedding_adaptive_budget_applied),
            ("embedding_fallback", embedding_fallback),
            (
                "chunk_semantic_time_budget_exceeded",
                chunk_semantic_time_budget_exceeded,
            ),
            ("chunk_semantic_fallback", chunk_semantic_fallback),
            ("xref_budget_exhausted", xref_budget_exhausted),
        )
        if active
    ]
    evidence_insufficiency = build_evidence_insufficiency(
        task_success_mode=str(task_success_config["mode"]),
        task_success_hit=task_success_hit,
        task_success_failed_checks=task_success_failed_checks,
        candidate_file_count=candidate_file_count,
        candidate_chunk_count=candidate_chunk_count,
        chunk_hit_at_k=chunk_hit_at_k,
        recall_hit=recall_hit,
        noise_rate=noise_rate,
        validation_test_count=len(validation_tests),
        docs_enabled=docs_enabled,
        docs_hit=docs_hit,
        dependency_recall=dependency_recall,
        neighbor_paths=[str(item).strip() for item in neighbor_paths if str(item).strip()],
        skills_budget_exhausted=skills_budget_exhausted,
        slo_downgrade_signals=slo_downgrade_signals,
    )
    decision_trace = build_decision_trace(
        memory_gate_skipped=memory_gate_skipped,
        memory_gate_skip_reason=memory_gate_skip_reason,
        memory_fallback_reason=memory_fallback_reason,
        memory_namespace_fallback=memory_namespace_fallback,
        candidate_ranker_fallbacks=candidate_ranker_fallbacks,
        exact_search_payload=exact_search_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        docs_backend_fallback_reason=docs_backend_fallback_reason,
        parallel_docs_timed_out=parallel_docs_timed_out,
        parallel_worktree_timed_out=parallel_worktree_timed_out,
        embedding_adaptive_budget_applied=embedding_adaptive_budget_applied,
        embedding_time_budget_exceeded=embedding_time_budget_exceeded,
        embedding_fallback=embedding_fallback,
        chunk_semantic_time_budget_exceeded=chunk_semantic_time_budget_exceeded,
        chunk_semantic_fallback=chunk_semantic_fallback,
        chunk_semantic_reason=chunk_semantic_reason,
        xref_budget_exhausted=xref_budget_exhausted,
        skills_budget_exhausted=skills_budget_exhausted,
    )
    chunk_guard_expectation = evaluate_chunk_guard_expectation(
        case=case,
        chunk_guard_payload=chunk_guard_payload,
    )
    return CaseEvaluationDiagnostics(
        task_success_config=task_success_config,
        task_success_failed_checks=task_success_failed_checks,
        task_success_hit=task_success_hit,
        slo_downgrade_signals=slo_downgrade_signals,
        evidence_insufficiency=evidence_insufficiency,
        decision_trace=decision_trace,
        chunk_guard_expectation=chunk_guard_expectation,
    )


__all__ = ["CaseEvaluationDiagnostics", "build_case_evaluation_diagnostics"]
