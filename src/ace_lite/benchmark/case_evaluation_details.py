"""Observability and detail-shaping helpers for benchmark case evaluation."""

from __future__ import annotations

from typing import Any


def _normalize_repo_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").lower()


def _coerce_chunk_stage_oracle(
    case: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    oracle_file_path = str(
        case.get("oracle_file_path", case.get("oracle_file", "")) or ""
    ).strip()
    raw_oracle = case.get("oracle_chunk_ref", case.get("oracle_chunk"))
    oracle_chunk: dict[str, str] = {}
    if isinstance(raw_oracle, dict):
        for key in ("path", "qualified_name", "signature"):
            value = str(raw_oracle.get(key) or "").strip()
            if value:
                oracle_chunk[key] = value
    elif isinstance(raw_oracle, str):
        value = raw_oracle.strip()
        if value:
            oracle_chunk["qualified_name"] = value
    if oracle_file_path and not oracle_chunk.get("path"):
        oracle_chunk["path"] = oracle_file_path
    return oracle_file_path, oracle_chunk


def _candidate_file_matches(*, item: dict[str, Any], oracle_file_path: str) -> bool:
    normalized_oracle_path = _normalize_repo_path(oracle_file_path)
    if not normalized_oracle_path:
        return False
    return _normalize_repo_path(item.get("path")) == normalized_oracle_path


def _candidate_chunk_matches(
    *,
    item: dict[str, Any],
    oracle_file_path: str,
    oracle_chunk: dict[str, str],
) -> bool:
    normalized_oracle_path = _normalize_repo_path(
        oracle_chunk.get("path") or oracle_file_path
    )
    if (
        normalized_oracle_path
        and _normalize_repo_path(item.get("path")) != normalized_oracle_path
    ):
        return False
    for key in ("qualified_name", "signature"):
        expected = str(oracle_chunk.get(key) or "").strip()
        if expected and str(item.get(key) or "").strip() != expected:
            return False
    return bool(normalized_oracle_path or oracle_chunk)


def classify_chunk_stage_miss(
    *,
    case: dict[str, Any],
    candidate_files: list[Any],
    raw_candidate_chunks: list[dict[str, Any]],
    source_plan_candidate_chunks: list[dict[str, Any]],
    source_plan_has_candidate_chunks: bool,
) -> dict[str, Any]:
    oracle_file_path, oracle_chunk = _coerce_chunk_stage_oracle(case)
    if not oracle_file_path:
        return {
            "applicable": False,
            "label": "",
            "oracle_file_path": "",
            "oracle_chunk_ref": {},
            "file_present": False,
            "raw_chunk_present": False,
            "source_plan_chunk_present": False,
        }

    file_present = any(
        isinstance(item, dict)
        and _candidate_file_matches(item=item, oracle_file_path=oracle_file_path)
        for item in candidate_files
    )
    raw_chunk_present = any(
        _candidate_chunk_matches(
            item=item,
            oracle_file_path=oracle_file_path,
            oracle_chunk=oracle_chunk,
        )
        for item in raw_candidate_chunks
        if isinstance(item, dict)
    )
    source_plan_chunk_present = any(
        _candidate_chunk_matches(
            item=item,
            oracle_file_path=oracle_file_path,
            oracle_chunk=oracle_chunk,
        )
        for item in source_plan_candidate_chunks
        if isinstance(item, dict)
    )

    label = ""
    if not file_present:
        label = "candidate_files_miss"
    elif not raw_chunk_present:
        label = "candidate_chunks_miss"
    elif source_plan_has_candidate_chunks and not source_plan_chunk_present:
        label = "source_plan_pack_miss"

    return {
        "applicable": True,
        "label": label,
        "oracle_file_path": oracle_file_path,
        "oracle_chunk_ref": oracle_chunk,
        "file_present": file_present,
        "raw_chunk_present": raw_chunk_present,
        "source_plan_chunk_present": (
            source_plan_chunk_present if source_plan_has_candidate_chunks else False
        ),
    }


def build_evidence_insufficiency(
    *,
    task_success_mode: str,
    task_success_hit: float,
    task_success_failed_checks: list[str],
    candidate_file_count: int,
    candidate_chunk_count: int,
    chunk_hit_at_k: float,
    recall_hit: float,
    noise_rate: float,
    validation_test_count: int,
    docs_enabled: bool,
    docs_hit: float,
    dependency_recall: float,
    neighbor_paths: list[str],
    skills_budget_exhausted: bool,
    slo_downgrade_signals: list[str],
) -> dict[str, Any]:
    normalized_mode = str(task_success_mode or "").strip().lower() or "positive"
    signals: list[str] = []

    if normalized_mode != "negative_control" and float(task_success_hit) <= 0.0:
        if candidate_file_count <= 0:
            signals.append("no_candidate_files")
        if candidate_chunk_count <= 0:
            signals.append("missing_candidate_chunks")
        if float(recall_hit) > 0.0 and float(chunk_hit_at_k) <= 0.0:
            signals.append("low_chunk_support")
        if "validation_tests" in task_success_failed_checks:
            signals.append("missing_validation_tests")
        if docs_enabled and float(docs_hit) <= 0.0:
            signals.append("missing_docs_evidence")
        if float(dependency_recall) <= 0.0 and not neighbor_paths:
            signals.append("missing_repomap_neighbors")
        if float(recall_hit) > 0.0 and float(noise_rate) > 0.0:
            signals.append("noisy_hit")
        if skills_budget_exhausted or slo_downgrade_signals:
            signals.append("budget_limited")

    primary_reason = ""
    if "no_candidate_files" in signals:
        primary_reason = "no_hit"
    elif (
        "missing_candidate_chunks" in signals
        or "low_chunk_support" in signals
        or "missing_docs_evidence" in signals
        or "missing_repomap_neighbors" in signals
    ):
        primary_reason = "low_support"
    elif "missing_validation_tests" in signals:
        primary_reason = "missing_validation"
    elif "budget_limited" in signals:
        primary_reason = "budget_limited"
    elif "noisy_hit" in signals:
        primary_reason = "noisy_hit"

    return {
        "evidence_insufficient": 1.0 if primary_reason else 0.0,
        "evidence_insufficiency_reason": primary_reason,
        "evidence_insufficiency_signals": signals,
        "evidence_no_candidate": 1.0 if "no_candidate_files" in signals else 0.0,
        "evidence_low_support_chunk": (
            1.0
            if any(
                signal in signals
                for signal in (
                    "missing_candidate_chunks",
                    "low_chunk_support",
                    "missing_docs_evidence",
                    "missing_repomap_neighbors",
                )
            )
            else 0.0
        ),
        "evidence_missing_validation": (
            1.0 if "missing_validation_tests" in signals else 0.0
        ),
        "evidence_budget_limited": 1.0 if "budget_limited" in signals else 0.0,
        "evidence_noisy_hit": 1.0 if "noisy_hit" in signals else 0.0,
    }


def _append_decision_trace_event(
    decision_trace: list[dict[str, Any]],
    *,
    stage: str,
    action: str,
    target: str,
    reason: str,
    outcome: str = "",
) -> None:
    normalized_stage = str(stage or "").strip().lower()
    normalized_action = str(action or "").strip().lower()
    normalized_target = str(target or "").strip().lower()
    normalized_reason = str(reason or "").strip()
    normalized_outcome = str(outcome or "").strip().lower()
    if not normalized_stage or not normalized_action or not normalized_target:
        return

    event: dict[str, Any] = {
        "stage": normalized_stage,
        "action": normalized_action,
        "target": normalized_target,
        "reason": normalized_reason,
    }
    if normalized_outcome:
        event["outcome"] = normalized_outcome
    decision_trace.append(event)


def build_decision_trace(
    *,
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
    skills_budget_exhausted: bool,
) -> list[dict[str, Any]]:
    decision_trace: list[dict[str, Any]] = []

    if memory_gate_skipped:
        _append_decision_trace_event(
            decision_trace,
            stage="memory",
            action="skip",
            target="memory_retrieval",
            reason=memory_gate_skip_reason or "gate_skipped",
        )
    if str(memory_fallback_reason).strip():
        _append_decision_trace_event(
            decision_trace,
            stage="memory",
            action="fallback",
            target="memory_provider",
            reason=memory_fallback_reason,
        )
    if str(memory_namespace_fallback).strip():
        _append_decision_trace_event(
            decision_trace,
            stage="memory",
            action="fallback",
            target="memory_namespace",
            reason=memory_namespace_fallback,
        )

    for fallback_reason in candidate_ranker_fallbacks:
        normalized_reason = str(fallback_reason or "").strip()
        if not normalized_reason:
            continue
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="fallback",
            target="candidate_ranker",
            reason=normalized_reason,
        )

    exact_search_enabled = bool(exact_search_payload.get("enabled", False))
    exact_search_reason = str(exact_search_payload.get("reason", "") or "").strip()
    exact_search_applied = bool(exact_search_payload.get("applied", False))
    if exact_search_enabled and (
        exact_search_applied
        or exact_search_reason not in {"", "disabled", "pending"}
    ):
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="boost",
            target="exact_search",
            reason=exact_search_reason or "executed",
            outcome="applied" if exact_search_applied else "no_change",
        )

    refine_trigger_condition_met = bool(
        refine_pass_payload.get("trigger_condition_met", False)
    )
    if refine_trigger_condition_met:
        refine_enabled = bool(refine_pass_payload.get("enabled", False))
        refine_triggered = bool(refine_pass_payload.get("triggered", False))
        refine_reason = str(refine_pass_payload.get("reason", "") or "").strip()
        if refine_triggered:
            _append_decision_trace_event(
                decision_trace,
                stage="index",
                action="retry",
                target="deterministic_refine",
                reason=refine_reason or "triggered",
                outcome="applied"
                if bool(refine_pass_payload.get("applied", False))
                else "no_change",
            )
        elif not refine_enabled:
            _append_decision_trace_event(
                decision_trace,
                stage="index",
                action="skip",
                target="deterministic_refine",
                reason=refine_reason or "disabled",
            )
    elif bool(second_pass_payload.get("triggered", False)):
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="retry",
            target="candidate_postprocess",
            reason=str(second_pass_payload.get("reason", "") or "").strip()
            or "triggered",
            outcome="applied"
            if bool(second_pass_payload.get("applied", False))
            else "no_change",
        )

    if str(docs_backend_fallback_reason).strip():
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="fallback",
            target="docs_backend",
            reason=docs_backend_fallback_reason,
        )
    if parallel_docs_timed_out:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="downgrade",
            target="parallel_docs",
            reason="timeout",
        )
    if parallel_worktree_timed_out:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="downgrade",
            target="parallel_worktree",
            reason="timeout",
        )
    if embedding_adaptive_budget_applied:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="downgrade",
            target="embedding_budget",
            reason="adaptive_budget_applied",
        )
    if embedding_time_budget_exceeded:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="downgrade",
            target="embeddings",
            reason="time_budget_exceeded",
        )
    if embedding_fallback:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="fallback",
            target="embeddings",
            reason=(
                "time_budget_exceeded"
                if embedding_time_budget_exceeded
                else "fallback"
            ),
        )
    if chunk_semantic_time_budget_exceeded:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="downgrade",
            target="chunk_semantic",
            reason="time_budget_exceeded",
        )
    if chunk_semantic_fallback:
        _append_decision_trace_event(
            decision_trace,
            stage="index",
            action="fallback",
            target="chunk_semantic",
            reason=str(chunk_semantic_reason or "").strip()
            or (
                "time_budget_exceeded"
                if chunk_semantic_time_budget_exceeded
                else "fallback"
            ),
        )

    if xref_budget_exhausted:
        _append_decision_trace_event(
            decision_trace,
            stage="augment",
            action="skip",
            target="xref",
            reason="budget_exhausted",
        )
    if skills_budget_exhausted:
        _append_decision_trace_event(
            decision_trace,
            stage="skills",
            action="skip",
            target="skills_hydration",
            reason="token_budget_exhausted",
        )

    return decision_trace


__all__ = [
    "build_decision_trace",
    "build_evidence_insufficiency",
    "classify_chunk_stage_miss",
]
