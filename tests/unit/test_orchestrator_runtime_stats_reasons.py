from __future__ import annotations

from ace_lite.orchestrator import AceOrchestrator
from ace_lite.pipeline.types import StageMetric


def test_collect_durable_stats_reasons_marks_evidence_insufficient_for_missing_direct_support() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="source_plan",
                elapsed_ms=8.0,
                plugins=[],
                tags={
                    "candidate_chunk_count": 2,
                    "validation_test_count": 1,
                    "evidence_direct_count": 0,
                    "evidence_neighbor_context_count": 1,
                    "evidence_hint_only_count": 1,
                    "evidence_hint_only_ratio": 0.5,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "evidence_insufficient" in reasons
    assert "noisy_hit" not in reasons


def test_collect_durable_stats_reasons_marks_noisy_hit_for_hint_heavy_mixed_support() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="source_plan",
                elapsed_ms=8.0,
                plugins=[],
                tags={
                    "candidate_chunk_count": 4,
                    "validation_test_count": 2,
                    "evidence_direct_count": 1,
                    "evidence_neighbor_context_count": 0,
                    "evidence_hint_only_count": 2,
                    "evidence_hint_only_ratio": 0.5,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "noisy_hit" in reasons
    assert "evidence_insufficient" not in reasons


def test_collect_durable_stats_reasons_marks_evidence_insufficient_for_missing_validation_tests() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="source_plan",
                elapsed_ms=8.0,
                plugins=[],
                tags={
                    "candidate_chunk_count": 2,
                    "validation_test_count": 0,
                    "evidence_direct_count": 2,
                    "evidence_neighbor_context_count": 0,
                    "evidence_hint_only_count": 0,
                    "evidence_hint_only_ratio": 0.0,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "evidence_insufficient" in reasons


def test_collect_durable_stats_reasons_marks_repeated_retry_from_agent_loop_metric() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="agent_loop",
                elapsed_ms=0.0,
                plugins=[],
                tags={
                    "stop_reason": "max_iterations",
                    "iteration_count": 2,
                    "actions_executed": 2,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "repeated_retry" in reasons


def test_collect_durable_stats_reasons_marks_latency_budget_exceeded_from_index_budget_timeout() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="index",
                elapsed_ms=12.0,
                plugins=[],
                tags={
                    "embedding_time_budget_exceeded": True,
                    "chunk_semantic_time_budget_exceeded": False,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "embedding_time_budget_exceeded" in reasons
    assert "latency_budget_exceeded" in reasons


def test_collect_durable_stats_reasons_marks_latency_budget_exceeded_from_parallel_timeout() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="index",
                elapsed_ms=12.0,
                plugins=[],
                tags={
                    "parallel_docs_timed_out": True,
                    "parallel_worktree_timed_out": False,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "parallel_docs_timeout" in reasons
    assert "latency_budget_exceeded" in reasons


def test_collect_durable_stats_reasons_marks_latency_budget_exceeded_from_xref_budget_exhaustion() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="augment",
                elapsed_ms=12.0,
                plugins=[],
                tags={
                    "xref_budget_exhausted": True,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "xref_budget_exhausted" in reasons
    assert "latency_budget_exceeded" in reasons


def test_collect_durable_stats_reasons_marks_skills_budget_exhausted() -> None:
    reasons = AceOrchestrator._collect_durable_stats_reasons(
        stage_metrics=[
            StageMetric(
                stage="skills",
                elapsed_ms=6.0,
                plugins=[],
                tags={
                    "budget_exhausted": True,
                    "skipped_for_budget_count": 2,
                    "token_budget": 1200,
                    "token_budget_used": 900,
                },
            )
        ],
        contract_error=None,
        replay_cache_info=None,
        trace_export={},
    )

    assert "skills_budget_exhausted" in reasons
