"""Builder seam for case-evaluation diagnostics inputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.benchmark.case_evaluation_diagnostics import (
    CaseEvaluationDiagnostics,
    build_case_evaluation_diagnostics,
)
from ace_lite.benchmark.case_evaluation_namespace_lookup import (
    lookup_case_evaluation_value,
)


def build_case_evaluation_diagnostics_from_namespace(
    *,
    namespace: Mapping[str, Any],
) -> CaseEvaluationDiagnostics:
    return build_case_evaluation_diagnostics(
        case=_lookup(namespace, "case"),
        expected=_lookup(namespace, "expected"),
        recall_hit=_lookup(namespace, "recall_hit"),
        validation_tests=_lookup(namespace, "validation_tests"),
        candidate_file_count=len(_lookup(namespace, "top_candidates")),
        candidate_chunk_count=len(_lookup(namespace, "candidate_chunks")),
        chunk_hit_at_k=_lookup(namespace, "chunk_hit_at_k"),
        noise_rate=_lookup(namespace, "noise"),
        docs_enabled=_lookup(namespace, "docs_enabled_flag"),
        docs_hit=_lookup(namespace, "docs_hit"),
        dependency_recall=_lookup(namespace, "dependency_recall"),
        neighbor_paths=_lookup(namespace, "neighbor_paths"),
        skills_budget_exhausted=_lookup(namespace, "skills_budget_exhausted"),
        memory_gate_skipped=_lookup(namespace, "memory_gate_skipped"),
        memory_gate_skip_reason=_lookup(namespace, "memory_gate_skip_reason"),
        memory_fallback_reason=_lookup(namespace, "memory_fallback_reason"),
        memory_namespace_fallback=_lookup(
            namespace, "memory_namespace_fallback"
        ),
        candidate_ranker_fallbacks=_lookup(
            namespace, "candidate_ranker_fallbacks"
        ),
        exact_search_payload=_lookup(namespace, "exact_search_payload"),
        second_pass_payload=_lookup(namespace, "second_pass_payload"),
        refine_pass_payload=_lookup(namespace, "refine_pass_payload"),
        docs_backend_fallback_reason=_lookup(
            namespace, "docs_backend_fallback_reason"
        ),
        parallel_docs_timed_out=_lookup(namespace, "parallel_docs_timed_out"),
        parallel_worktree_timed_out=_lookup(
            namespace, "parallel_worktree_timed_out"
        ),
        embedding_adaptive_budget_applied=_lookup(
            namespace, "embedding_adaptive_budget_applied"
        ),
        embedding_time_budget_exceeded=_lookup(
            namespace, "embedding_time_budget_exceeded"
        ),
        embedding_fallback=_lookup(namespace, "embedding_fallback"),
        chunk_semantic_time_budget_exceeded=_lookup(
            namespace, "chunk_semantic_time_budget_exceeded"
        ),
        chunk_semantic_fallback=_lookup(namespace, "chunk_semantic_fallback"),
        chunk_semantic_reason=_lookup(namespace, "chunk_semantic_reason"),
        xref_budget_exhausted=_lookup(namespace, "xref_budget_exhausted"),
        chunk_guard_payload=_lookup(namespace, "chunk_guard_payload"),
    )


def _lookup(namespace: Mapping[str, Any], key: str) -> Any:
    return lookup_case_evaluation_value(
        namespace,
        key,
        error_prefix="case-evaluation diagnostics input",
    )


__all__ = ["build_case_evaluation_diagnostics_from_namespace"]
