"""Non-router benchmark summary builders."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from ace_lite.benchmark.summary_common import PIPELINE_STAGE_ORDER, p95


def summarize_missing_context_risk_case(item: dict[str, Any]) -> tuple[bool, float, str]:
    mode = str(item.get("task_success_mode") or "").strip().lower() or "positive"
    if mode == "negative_control":
        return False, 0.0, ""

    recall_hit = float(item.get("recall_hit", 0.0) or 0.0)
    chunk_hit_at_k = float(item.get("chunk_hit_at_k", 0.0) or 0.0)
    noise_rate = float(item.get("noise_rate", 0.0) or 0.0)
    evidence_insufficient = float(item.get("evidence_insufficient", 0.0) or 0.0)
    budget_exhausted = max(
        float(item.get("skills_budget_exhausted", 0.0) or 0.0),
        float(item.get("xref_budget_exhausted", 0.0) or 0.0),
    )

    score = 0.0
    if recall_hit <= 0.0:
        score += 0.35
    if recall_hit > 0.0 and chunk_hit_at_k <= 0.0:
        score += 0.25
    if noise_rate > 0.0:
        score += min(0.2, noise_rate * 0.2)
    if evidence_insufficient > 0.0:
        score += 0.25
    if budget_exhausted > 0.0:
        score += 0.15

    score = max(0.0, min(1.0, score))
    if score >= 0.75:
        return True, score, "high"
    if score >= 0.40:
        return True, score, "elevated"
    return True, score, "low"


def is_risk_upgrade_case(item: dict[str, Any]) -> bool:
    trace_raw = item.get("decision_trace", [])
    decision_trace = trace_raw if isinstance(trace_raw, list) else []
    for event in decision_trace:
        if not isinstance(event, dict):
            continue
        if str(event.get("stage") or "").strip() != "index":
            continue
        if str(event.get("action") or "").strip() not in {"boost", "retry"}:
            continue
        return True
    return False


def build_missing_context_risk_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "applicable_case_count": 0,
            "excluded_negative_control_case_count": 0,
            "elevated_case_count": 0,
            "high_risk_case_count": 0,
            "elevated_case_rate": 0.0,
            "high_risk_case_rate": 0.0,
            "risk_score_mean": 0.0,
            "risk_score_p95": 0.0,
            "risk_upgrade_case_count": 0,
            "risk_upgrade_case_rate": 0.0,
            "risk_upgrade_precision_mean": 0.0,
            "risk_baseline_precision_mean": 0.0,
            "risk_upgrade_precision_gain": 0.0,
            "levels": {},
            "signals": {},
        }

    applicable_case_count = 0
    excluded_negative_control_case_count = 0
    elevated_case_count = 0
    high_risk_case_count = 0
    risk_scores: list[float] = []
    risk_upgrade_precisions: list[float] = []
    risk_baseline_precisions: list[float] = []
    levels: dict[str, int] = {}
    signals: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        applicable, score, level = summarize_missing_context_risk_case(item)
        if not applicable:
            excluded_negative_control_case_count += 1
            continue

        applicable_case_count += 1

        recall_hit = float(item.get("recall_hit", 0.0) or 0.0)
        chunk_hit_at_k = float(item.get("chunk_hit_at_k", 0.0) or 0.0)
        noise_rate = float(item.get("noise_rate", 0.0) or 0.0)
        evidence_insufficient = float(item.get("evidence_insufficient", 0.0) or 0.0)
        budget_exhausted = max(
            float(item.get("skills_budget_exhausted", 0.0) or 0.0),
            float(item.get("xref_budget_exhausted", 0.0) or 0.0),
        )

        score = 0.0
        if recall_hit <= 0.0:
            score += 0.35
            signals["recall_miss"] = signals.get("recall_miss", 0) + 1
        if recall_hit > 0.0 and chunk_hit_at_k <= 0.0:
            score += 0.25
            signals["chunk_miss_after_recall"] = (
                signals.get("chunk_miss_after_recall", 0) + 1
            )
        if noise_rate > 0.0:
            score += min(0.2, noise_rate * 0.2)
            signals["noisy_candidates"] = signals.get("noisy_candidates", 0) + 1
        if evidence_insufficient > 0.0:
            score += 0.25
            signals["evidence_insufficient"] = (
                signals.get("evidence_insufficient", 0) + 1
            )
        if budget_exhausted > 0.0:
            score += 0.15
            signals["budget_exhausted"] = signals.get("budget_exhausted", 0) + 1

        risk_scores.append(score)

        if score >= 0.75:
            high_risk_case_count += 1
            elevated_case_count += 1
        elif score >= 0.40:
            elevated_case_count += 1
        levels[level] = levels.get(level, 0) + 1
        if level in {"elevated", "high"}:
            precision = float(item.get("precision_at_k", 0.0) or 0.0)
            if is_risk_upgrade_case(item):
                risk_upgrade_precisions.append(precision)
            else:
                risk_baseline_precisions.append(precision)

    return {
        "case_count": case_count,
        "applicable_case_count": applicable_case_count,
        "excluded_negative_control_case_count": excluded_negative_control_case_count,
        "elevated_case_count": elevated_case_count,
        "high_risk_case_count": high_risk_case_count,
        "elevated_case_rate": (
            float(elevated_case_count) / float(applicable_case_count)
            if applicable_case_count > 0
            else 0.0
        ),
        "high_risk_case_rate": (
            float(high_risk_case_count) / float(applicable_case_count)
            if applicable_case_count > 0
            else 0.0
        ),
        "risk_score_mean": mean(risk_scores) if risk_scores else 0.0,
        "risk_score_p95": p95(risk_scores),
        "risk_upgrade_case_count": len(risk_upgrade_precisions),
        "risk_upgrade_case_rate": (
            float(len(risk_upgrade_precisions)) / float(elevated_case_count)
            if elevated_case_count > 0
            else 0.0
        ),
        "risk_upgrade_precision_mean": (
            mean(risk_upgrade_precisions) if risk_upgrade_precisions else 0.0
        ),
        "risk_baseline_precision_mean": (
            mean(risk_baseline_precisions) if risk_baseline_precisions else 0.0
        ),
        "risk_upgrade_precision_gain": (
            mean(risk_upgrade_precisions) - mean(risk_baseline_precisions)
            if risk_upgrade_precisions and risk_baseline_precisions
            else 0.0
        ),
        "levels": dict(sorted(levels.items())),
        "signals": dict(sorted(signals.items())),
    }


def build_evidence_insufficiency_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "applicable_case_count": 0,
            "excluded_negative_control_case_count": 0,
            "evidence_insufficient_count": 0,
            "evidence_insufficient_rate": 0.0,
            "reasons": {},
            "signals": {},
        }

    applicable_case_count = 0
    excluded_negative_control_case_count = 0
    evidence_insufficient_count = 0
    reasons: dict[str, int] = {}
    signals: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("task_success_mode") or "").strip().lower() or "positive"
        if mode == "negative_control":
            excluded_negative_control_case_count += 1
            continue
        task_success_hit = float(
            item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
        )
        if task_success_hit > 0.0:
            continue

        applicable_case_count += 1
        if float(item.get("evidence_insufficient", 0.0) or 0.0) <= 0.0:
            continue

        evidence_insufficient_count += 1
        reason = str(item.get("evidence_insufficiency_reason") or "").strip()
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1

        raw_signals = item.get("evidence_insufficiency_signals", [])
        signal_rows = raw_signals if isinstance(raw_signals, list) else []
        for signal in signal_rows:
            normalized = str(signal).strip()
            if not normalized:
                continue
            signals[normalized] = signals.get(normalized, 0) + 1

    return {
        "case_count": case_count,
        "applicable_case_count": applicable_case_count,
        "excluded_negative_control_case_count": excluded_negative_control_case_count,
        "evidence_insufficient_count": evidence_insufficient_count,
        "evidence_insufficient_rate": (
            float(evidence_insufficient_count) / float(applicable_case_count)
            if applicable_case_count > 0
            else 0.0
        ),
        "reasons": dict(sorted(reasons.items())),
        "signals": dict(sorted(signals.items())),
    }


def build_chunk_stage_miss_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "oracle_case_count": 0,
            "classified_case_count": 0,
            "classified_case_rate": 0.0,
            "labels": {},
        }

    oracle_case_count = 0
    classified_case_count = 0
    labels: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        applicable = float(item.get("chunk_stage_miss_applicable", 0.0) or 0.0) > 0.0
        if not applicable:
            continue
        oracle_case_count += 1
        label = str(item.get("chunk_stage_miss") or "").strip()
        if not label:
            continue
        classified_case_count += 1
        labels[label] = labels.get(label, 0) + 1

    return {
        "case_count": case_count,
        "oracle_case_count": oracle_case_count,
        "classified_case_count": classified_case_count,
        "classified_case_rate": (
            float(classified_case_count) / float(oracle_case_count)
            if oracle_case_count > 0
            else 0.0
        ),
        "labels": dict(sorted(labels.items())),
    }


def build_decision_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "case_with_decisions_count": 0,
            "case_with_decisions_rate": 0.0,
            "decision_event_count": 0,
            "actions": {},
            "targets": {},
            "reasons": {},
            "outcomes": {},
        }

    case_with_decisions_count = 0
    decision_event_count = 0
    actions: dict[str, int] = {}
    targets: dict[str, int] = {}
    reasons: dict[str, int] = {}
    outcomes: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        trace_raw = item.get("decision_trace", [])
        trace = trace_raw if isinstance(trace_raw, list) else []
        decision_events = [event for event in trace if isinstance(event, dict)]
        if decision_events:
            case_with_decisions_count += 1
        for event in decision_events:
            decision_event_count += 1
            action = str(event.get("action") or "").strip()
            target = str(event.get("target") or "").strip()
            reason = str(event.get("reason") or "").strip()
            outcome = str(event.get("outcome") or "").strip()
            if action:
                actions[action] = actions.get(action, 0) + 1
            if target:
                targets[target] = targets.get(target, 0) + 1
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
            if outcome:
                outcomes[outcome] = outcomes.get(outcome, 0) + 1

    return {
        "case_count": case_count,
        "case_with_decisions_count": case_with_decisions_count,
        "case_with_decisions_rate": (
            float(case_with_decisions_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "decision_event_count": decision_event_count,
        "actions": dict(sorted(actions.items())),
        "targets": dict(sorted(targets.items())),
        "reasons": dict(sorted(reasons.items())),
        "outcomes": dict(sorted(outcomes.items())),
    }


def build_retrieval_context_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "available_case_count": 0,
            "available_case_rate": 0.0,
            "parent_symbol_available_case_count": 0,
            "parent_symbol_available_case_rate": 0.0,
            "reference_hint_available_case_count": 0,
            "reference_hint_available_case_rate": 0.0,
            "pool_available_case_count": 0,
            "pool_available_case_rate": 0.0,
            "chunk_count_mean": 0.0,
            "coverage_ratio_mean": 0.0,
            "parent_symbol_chunk_count_mean": 0.0,
            "parent_symbol_coverage_ratio_mean": 0.0,
            "reference_hint_chunk_count_mean": 0.0,
            "reference_hint_coverage_ratio_mean": 0.0,
            "pool_chunk_count_mean": 0.0,
            "pool_coverage_ratio_mean": 0.0,
        }

    available_case_count = 0
    parent_symbol_available_case_count = 0
    reference_hint_available_case_count = 0
    pool_available_case_count = 0
    chunk_counts: list[float] = []
    coverage_ratios: list[float] = []
    parent_symbol_chunk_counts: list[float] = []
    parent_symbol_coverage_ratios: list[float] = []
    reference_hint_chunk_counts: list[float] = []
    reference_hint_coverage_ratios: list[float] = []
    pool_chunk_counts: list[float] = []
    pool_coverage_ratios: list[float] = []

    for item in case_results:
        if not isinstance(item, dict):
            continue
        chunk_count = float(item.get("retrieval_context_chunk_count", 0.0) or 0.0)
        coverage_ratio = float(
            item.get("retrieval_context_coverage_ratio", 0.0) or 0.0
        )
        parent_symbol_chunk_count = float(
            item.get("contextual_sidecar_parent_symbol_chunk_count", 0.0) or 0.0
        )
        parent_symbol_coverage_ratio = float(
            item.get("contextual_sidecar_parent_symbol_coverage_ratio", 0.0) or 0.0
        )
        reference_hint_chunk_count = float(
            item.get("contextual_sidecar_reference_hint_chunk_count", 0.0) or 0.0
        )
        reference_hint_coverage_ratio = float(
            item.get("contextual_sidecar_reference_hint_coverage_ratio", 0.0) or 0.0
        )
        pool_chunk_count = float(
            item.get("retrieval_context_pool_chunk_count", 0.0) or 0.0
        )
        pool_coverage_ratio = float(
            item.get("retrieval_context_pool_coverage_ratio", 0.0) or 0.0
        )
        if chunk_count > 0.0:
            available_case_count += 1
        if parent_symbol_chunk_count > 0.0:
            parent_symbol_available_case_count += 1
        if reference_hint_chunk_count > 0.0:
            reference_hint_available_case_count += 1
        if pool_chunk_count > 0.0:
            pool_available_case_count += 1
        chunk_counts.append(chunk_count)
        coverage_ratios.append(coverage_ratio)
        parent_symbol_chunk_counts.append(parent_symbol_chunk_count)
        parent_symbol_coverage_ratios.append(parent_symbol_coverage_ratio)
        reference_hint_chunk_counts.append(reference_hint_chunk_count)
        reference_hint_coverage_ratios.append(reference_hint_coverage_ratio)
        pool_chunk_counts.append(pool_chunk_count)
        pool_coverage_ratios.append(pool_coverage_ratio)

    return {
        "case_count": case_count,
        "available_case_count": available_case_count,
        "available_case_rate": (
            float(available_case_count) / float(case_count) if case_count > 0 else 0.0
        ),
        "parent_symbol_available_case_count": parent_symbol_available_case_count,
        "parent_symbol_available_case_rate": (
            float(parent_symbol_available_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "reference_hint_available_case_count": reference_hint_available_case_count,
        "reference_hint_available_case_rate": (
            float(reference_hint_available_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "pool_available_case_count": pool_available_case_count,
        "pool_available_case_rate": (
            float(pool_available_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "chunk_count_mean": mean(chunk_counts) if chunk_counts else 0.0,
        "coverage_ratio_mean": mean(coverage_ratios) if coverage_ratios else 0.0,
        "parent_symbol_chunk_count_mean": (
            mean(parent_symbol_chunk_counts) if parent_symbol_chunk_counts else 0.0
        ),
        "parent_symbol_coverage_ratio_mean": (
            mean(parent_symbol_coverage_ratios)
            if parent_symbol_coverage_ratios
            else 0.0
        ),
        "reference_hint_chunk_count_mean": (
            mean(reference_hint_chunk_counts)
            if reference_hint_chunk_counts
            else 0.0
        ),
        "reference_hint_coverage_ratio_mean": (
            mean(reference_hint_coverage_ratios)
            if reference_hint_coverage_ratios
            else 0.0
        ),
        "pool_chunk_count_mean": mean(pool_chunk_counts) if pool_chunk_counts else 0.0,
        "pool_coverage_ratio_mean": (
            mean(pool_coverage_ratios) if pool_coverage_ratios else 0.0
        ),
    }


def build_wave1_context_governance_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "plan_available_case_count": 0,
            "plan_available_case_rate": 0.0,
            "history_hits_case_count": 0,
            "history_hits_case_rate": 0.0,
            "candidate_review_case_count": 0,
            "candidate_review_case_rate": 0.0,
            "candidate_review_watch_case_count": 0,
            "candidate_review_watch_case_rate": 0.0,
            "validation_findings_case_count": 0,
            "validation_findings_case_rate": 0.0,
            "validation_blocker_case_count": 0,
            "validation_blocker_case_rate": 0.0,
            "session_end_report_case_count": 0,
            "session_end_report_case_rate": 0.0,
            "history_hit_count_mean": 0.0,
            "validation_warn_count_mean": 0.0,
            "validation_blocker_count_mean": 0.0,
            "session_next_action_count_mean": 0.0,
            "session_risk_count_mean": 0.0,
        }

    plan_available_case_count = 0
    history_hits_case_count = 0
    candidate_review_case_count = 0
    candidate_review_watch_case_count = 0
    validation_findings_case_count = 0
    validation_blocker_case_count = 0
    session_end_report_case_count = 0
    history_hit_counts: list[float] = []
    validation_warn_counts: list[float] = []
    validation_blocker_counts: list[float] = []
    session_next_action_counts: list[float] = []
    session_risk_counts: list[float] = []

    for item in case_results:
        if not isinstance(item, dict):
            continue
        plan = item.get("plan")
        if not isinstance(plan, dict):
            continue
        source_plan = plan.get("source_plan")
        if not isinstance(source_plan, dict):
            continue
        plan_available_case_count += 1

        history_hits = source_plan.get("history_hits")
        if isinstance(history_hits, dict) and history_hits:
            hits = history_hits.get("hits")
            hit_rows = hits if isinstance(hits, list) else []
            if hit_rows:
                history_hits_case_count += 1
                history_hit_counts.append(float(len(hit_rows)))

        candidate_review = source_plan.get("candidate_review")
        if isinstance(candidate_review, dict) and candidate_review:
            candidate_review_case_count += 1
            status = str(candidate_review.get("status") or "").strip().lower()
            if status and status != "ok":
                candidate_review_watch_case_count += 1

        validation_findings = source_plan.get("validation_findings")
        if isinstance(validation_findings, dict) and validation_findings:
            validation_findings_case_count += 1
            warn_count = float(validation_findings.get("warn_count", 0.0) or 0.0)
            blocker_count = float(
                validation_findings.get("blocker_count", 0.0) or 0.0
            )
            validation_warn_counts.append(warn_count)
            validation_blocker_counts.append(blocker_count)
            if blocker_count > 0.0:
                validation_blocker_case_count += 1

        session_end_report = source_plan.get("session_end_report")
        if isinstance(session_end_report, dict) and session_end_report:
            session_end_report_case_count += 1
            next_actions = session_end_report.get("next_actions")
            risks = session_end_report.get("risks")
            next_action_rows = next_actions if isinstance(next_actions, list) else []
            risk_rows = risks if isinstance(risks, list) else []
            session_next_action_counts.append(float(len(next_action_rows)))
            session_risk_counts.append(float(len(risk_rows)))

    return {
        "case_count": case_count,
        "plan_available_case_count": plan_available_case_count,
        "plan_available_case_rate": (
            float(plan_available_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "history_hits_case_count": history_hits_case_count,
        "history_hits_case_rate": (
            float(history_hits_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "candidate_review_case_count": candidate_review_case_count,
        "candidate_review_case_rate": (
            float(candidate_review_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "candidate_review_watch_case_count": candidate_review_watch_case_count,
        "candidate_review_watch_case_rate": (
            float(candidate_review_watch_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "validation_findings_case_count": validation_findings_case_count,
        "validation_findings_case_rate": (
            float(validation_findings_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "validation_blocker_case_count": validation_blocker_case_count,
        "validation_blocker_case_rate": (
            float(validation_blocker_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "session_end_report_case_count": session_end_report_case_count,
        "session_end_report_case_rate": (
            float(session_end_report_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "history_hit_count_mean": mean(history_hit_counts) if history_hit_counts else 0.0,
        "validation_warn_count_mean": (
            mean(validation_warn_counts) if validation_warn_counts else 0.0
        ),
        "validation_blocker_count_mean": (
            mean(validation_blocker_counts) if validation_blocker_counts else 0.0
        ),
        "session_next_action_count_mean": (
            mean(session_next_action_counts) if session_next_action_counts else 0.0
        ),
        "session_risk_count_mean": (
            mean(session_risk_counts) if session_risk_counts else 0.0
        ),
    }


def build_retrieval_default_strategy_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "retrieval_context_available_case_count": 0,
            "retrieval_context_available_case_rate": 0.0,
            "parent_symbol_available_case_count": 0,
            "parent_symbol_available_case_rate": 0.0,
            "reference_hint_available_case_count": 0,
            "reference_hint_available_case_rate": 0.0,
            "semantic_rerank_configured_case_count": 0,
            "semantic_rerank_configured_case_rate": 0.0,
            "semantic_rerank_enabled_case_count": 0,
            "semantic_rerank_enabled_case_rate": 0.0,
            "semantic_rerank_applied_case_count": 0,
            "semantic_rerank_applied_case_rate": 0.0,
            "semantic_rerank_cross_encoder_case_count": 0,
            "semantic_rerank_cross_encoder_case_rate": 0.0,
            "semantic_rerank_dominant_provider": "",
            "semantic_rerank_dominant_mode": "",
            "semantic_rerank_provider_case_counts": {},
            "graph_lookup_enabled_case_count": 0,
            "graph_lookup_enabled_case_rate": 0.0,
            "graph_lookup_guarded_case_count": 0,
            "graph_lookup_guarded_case_rate": 0.0,
            "graph_lookup_dominant_normalization": "",
            "graph_lookup_pool_size_mean": 0.0,
            "graph_lookup_guard_max_candidates_mean": 0.0,
            "graph_lookup_guard_min_query_terms_mean": 0.0,
            "graph_lookup_guard_max_query_terms_mean": 0.0,
            "graph_lookup_weight_means": {
                "scip": 0.0,
                "xref": 0.0,
                "query_xref": 0.0,
                "symbol": 0.0,
                "import": 0.0,
                "coverage": 0.0,
            },
            "topological_shield_enabled_case_count": 0,
            "topological_shield_enabled_case_rate": 0.0,
            "topological_shield_report_only_case_count": 0,
            "topological_shield_report_only_case_rate": 0.0,
            "topological_shield_dominant_mode": "",
            "topological_shield_max_attenuation_mean": 0.0,
            "topological_shield_shared_parent_attenuation_mean": 0.0,
            "topological_shield_adjacency_attenuation_mean": 0.0,
        }

    retrieval_context_available_case_count = 0
    parent_symbol_available_case_count = 0
    reference_hint_available_case_count = 0
    semantic_rerank_configured_case_count = 0
    semantic_rerank_enabled_case_count = 0
    semantic_rerank_applied_case_count = 0
    semantic_rerank_cross_encoder_case_count = 0
    semantic_rerank_provider_case_counts: dict[str, int] = {}
    semantic_rerank_mode_counts: dict[str, int] = {}
    graph_lookup_enabled_case_count = 0
    graph_lookup_guarded_case_count = 0
    graph_lookup_normalization_counts: dict[str, int] = {}
    graph_lookup_pool_sizes: list[float] = []
    graph_lookup_guard_max_candidates: list[float] = []
    graph_lookup_guard_min_query_terms: list[float] = []
    graph_lookup_guard_max_query_terms: list[float] = []
    graph_lookup_weight_scip: list[float] = []
    graph_lookup_weight_xref: list[float] = []
    graph_lookup_weight_query_xref: list[float] = []
    graph_lookup_weight_symbol: list[float] = []
    graph_lookup_weight_import: list[float] = []
    graph_lookup_weight_coverage: list[float] = []
    topological_shield_enabled_case_count = 0
    topological_shield_report_only_case_count = 0
    topological_shield_mode_counts: dict[str, int] = {}
    topological_shield_max_attenuations: list[float] = []
    topological_shield_shared_parent_attenuations: list[float] = []
    topological_shield_adjacency_attenuations: list[float] = []

    for item in case_results:
        if not isinstance(item, dict):
            continue
        if float(item.get("retrieval_context_chunk_count", 0.0) or 0.0) > 0.0:
            retrieval_context_available_case_count += 1
        if (
            float(
                item.get("contextual_sidecar_parent_symbol_chunk_count", 0.0) or 0.0
            )
            > 0.0
        ):
            parent_symbol_available_case_count += 1
        if (
            float(
                item.get("contextual_sidecar_reference_hint_chunk_count", 0.0) or 0.0
            )
            > 0.0
        ):
            reference_hint_available_case_count += 1
        provider = str(item.get("embedding_runtime_provider") or "").strip().lower()
        mode = str(item.get("embedding_strategy_mode") or "").strip().lower()
        semantic_rerank_enabled = (
            float(item.get("embedding_enabled", 0.0) or 0.0) > 0.0
        )
        semantic_rerank_applied = (
            float(item.get("embedding_semantic_rerank_applied", 0.0) or 0.0) > 0.0
        )
        if provider:
            semantic_rerank_configured_case_count += 1
            semantic_rerank_provider_case_counts[provider] = (
                semantic_rerank_provider_case_counts.get(provider, 0) + 1
            )
        if semantic_rerank_enabled:
            semantic_rerank_enabled_case_count += 1
        if semantic_rerank_applied:
            semantic_rerank_applied_case_count += 1
        if mode == "cross_encoder":
            semantic_rerank_cross_encoder_case_count += 1
        if mode:
            semantic_rerank_mode_counts[mode] = (
                semantic_rerank_mode_counts.get(mode, 0) + 1
            )

        if float(item.get("graph_lookup_enabled", 0.0) or 0.0) > 0.0:
            graph_lookup_enabled_case_count += 1
        if float(item.get("graph_lookup_guarded", 0.0) or 0.0) > 0.0:
            graph_lookup_guarded_case_count += 1
        normalization = str(item.get("graph_lookup_normalization") or "").strip().lower()
        if normalization:
            graph_lookup_normalization_counts[normalization] = (
                graph_lookup_normalization_counts.get(normalization, 0) + 1
            )
        graph_lookup_pool_sizes.append(
            float(item.get("graph_lookup_pool_size", 0.0) or 0.0)
        )
        graph_lookup_guard_max_candidates.append(
            float(item.get("graph_lookup_guard_max_candidates", 0.0) or 0.0)
        )
        graph_lookup_guard_min_query_terms.append(
            float(item.get("graph_lookup_guard_min_query_terms", 0.0) or 0.0)
        )
        graph_lookup_guard_max_query_terms.append(
            float(item.get("graph_lookup_guard_max_query_terms", 0.0) or 0.0)
        )
        graph_lookup_weight_scip.append(
            float(item.get("graph_lookup_weight_scip", 0.0) or 0.0)
        )
        graph_lookup_weight_xref.append(
            float(item.get("graph_lookup_weight_xref", 0.0) or 0.0)
        )
        graph_lookup_weight_query_xref.append(
            float(item.get("graph_lookup_weight_query_xref", 0.0) or 0.0)
        )
        graph_lookup_weight_symbol.append(
            float(item.get("graph_lookup_weight_symbol", 0.0) or 0.0)
        )
        graph_lookup_weight_import.append(
            float(item.get("graph_lookup_weight_import", 0.0) or 0.0)
        )
        graph_lookup_weight_coverage.append(
            float(item.get("graph_lookup_weight_coverage", 0.0) or 0.0)
        )

        if float(item.get("topological_shield_enabled", 0.0) or 0.0) > 0.0:
            topological_shield_enabled_case_count += 1
        if float(item.get("topological_shield_report_only", 0.0) or 0.0) > 0.0:
            topological_shield_report_only_case_count += 1
        mode = str(item.get("topological_shield_mode") or "").strip().lower()
        if mode:
            topological_shield_mode_counts[mode] = (
                topological_shield_mode_counts.get(mode, 0) + 1
            )
        topological_shield_max_attenuations.append(
            float(item.get("topological_shield_max_attenuation", 0.0) or 0.0)
        )
        topological_shield_shared_parent_attenuations.append(
            float(
                item.get("topological_shield_shared_parent_attenuation", 0.0) or 0.0
            )
        )
        topological_shield_adjacency_attenuations.append(
            float(item.get("topological_shield_adjacency_attenuation", 0.0) or 0.0)
        )

    def _dominant_label(counts: dict[str, int]) -> str:
        if not counts:
            return ""
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    return {
        "case_count": case_count,
        "retrieval_context_available_case_count": retrieval_context_available_case_count,
        "retrieval_context_available_case_rate": (
            float(retrieval_context_available_case_count) / float(case_count)
        ),
        "parent_symbol_available_case_count": parent_symbol_available_case_count,
        "parent_symbol_available_case_rate": (
            float(parent_symbol_available_case_count) / float(case_count)
        ),
        "reference_hint_available_case_count": reference_hint_available_case_count,
        "reference_hint_available_case_rate": (
            float(reference_hint_available_case_count) / float(case_count)
        ),
        "semantic_rerank_configured_case_count": semantic_rerank_configured_case_count,
        "semantic_rerank_configured_case_rate": (
            float(semantic_rerank_configured_case_count) / float(case_count)
        ),
        "semantic_rerank_enabled_case_count": semantic_rerank_enabled_case_count,
        "semantic_rerank_enabled_case_rate": (
            float(semantic_rerank_enabled_case_count) / float(case_count)
        ),
        "semantic_rerank_applied_case_count": semantic_rerank_applied_case_count,
        "semantic_rerank_applied_case_rate": (
            float(semantic_rerank_applied_case_count) / float(case_count)
        ),
        "semantic_rerank_cross_encoder_case_count": (
            semantic_rerank_cross_encoder_case_count
        ),
        "semantic_rerank_cross_encoder_case_rate": (
            float(semantic_rerank_cross_encoder_case_count) / float(case_count)
        ),
        "semantic_rerank_dominant_provider": _dominant_label(
            semantic_rerank_provider_case_counts
        ),
        "semantic_rerank_dominant_mode": _dominant_label(
            semantic_rerank_mode_counts
        ),
        "semantic_rerank_provider_case_counts": dict(
            sorted(semantic_rerank_provider_case_counts.items())
        ),
        "graph_lookup_enabled_case_count": graph_lookup_enabled_case_count,
        "graph_lookup_enabled_case_rate": (
            float(graph_lookup_enabled_case_count) / float(case_count)
        ),
        "graph_lookup_guarded_case_count": graph_lookup_guarded_case_count,
        "graph_lookup_guarded_case_rate": (
            float(graph_lookup_guarded_case_count) / float(case_count)
        ),
        "graph_lookup_dominant_normalization": _dominant_label(
            graph_lookup_normalization_counts
        ),
        "graph_lookup_pool_size_mean": (
            mean(graph_lookup_pool_sizes) if graph_lookup_pool_sizes else 0.0
        ),
        "graph_lookup_guard_max_candidates_mean": (
            mean(graph_lookup_guard_max_candidates)
            if graph_lookup_guard_max_candidates
            else 0.0
        ),
        "graph_lookup_guard_min_query_terms_mean": (
            mean(graph_lookup_guard_min_query_terms)
            if graph_lookup_guard_min_query_terms
            else 0.0
        ),
        "graph_lookup_guard_max_query_terms_mean": (
            mean(graph_lookup_guard_max_query_terms)
            if graph_lookup_guard_max_query_terms
            else 0.0
        ),
        "graph_lookup_weight_means": {
            "scip": mean(graph_lookup_weight_scip) if graph_lookup_weight_scip else 0.0,
            "xref": mean(graph_lookup_weight_xref) if graph_lookup_weight_xref else 0.0,
            "query_xref": (
                mean(graph_lookup_weight_query_xref)
                if graph_lookup_weight_query_xref
                else 0.0
            ),
            "symbol": (
                mean(graph_lookup_weight_symbol)
                if graph_lookup_weight_symbol
                else 0.0
            ),
            "import": (
                mean(graph_lookup_weight_import)
                if graph_lookup_weight_import
                else 0.0
            ),
            "coverage": (
                mean(graph_lookup_weight_coverage)
                if graph_lookup_weight_coverage
                else 0.0
            ),
        },
        "topological_shield_enabled_case_count": topological_shield_enabled_case_count,
        "topological_shield_enabled_case_rate": (
            float(topological_shield_enabled_case_count) / float(case_count)
        ),
        "topological_shield_report_only_case_count": (
            topological_shield_report_only_case_count
        ),
        "topological_shield_report_only_case_rate": (
            float(topological_shield_report_only_case_count) / float(case_count)
        ),
        "topological_shield_dominant_mode": _dominant_label(
            topological_shield_mode_counts
        ),
        "topological_shield_max_attenuation_mean": (
            mean(topological_shield_max_attenuations)
            if topological_shield_max_attenuations
            else 0.0
        ),
        "topological_shield_shared_parent_attenuation_mean": (
            mean(topological_shield_shared_parent_attenuations)
            if topological_shield_shared_parent_attenuations
            else 0.0
        ),
        "topological_shield_adjacency_attenuation_mean": (
            mean(topological_shield_adjacency_attenuations)
            if topological_shield_adjacency_attenuations
            else 0.0
        ),
    }


def build_agent_loop_control_plane_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "observed_case_count": 0,
            "observed_case_rate": 0.0,
            "enabled_case_count": 0,
            "enabled_case_rate": 0.0,
            "attempted_case_count": 0,
            "attempted_case_rate": 0.0,
            "replay_safe_case_count": 0,
            "replay_safe_case_rate": 0.0,
            "actions_requested_mean": 0.0,
            "actions_executed_mean": 0.0,
            "request_more_context_case_count": 0,
            "request_more_context_case_rate": 0.0,
            "request_source_plan_retry_case_count": 0,
            "request_source_plan_retry_case_rate": 0.0,
            "request_validation_retry_case_count": 0,
            "request_validation_retry_case_rate": 0.0,
            "dominant_stop_reason": "",
            "dominant_last_policy_id": "",
        }

    observed_case_count = 0
    enabled_case_count = 0
    attempted_case_count = 0
    replay_safe_case_count = 0
    actions_requested: list[float] = []
    actions_executed: list[float] = []
    request_more_context_case_count = 0
    request_source_plan_retry_case_count = 0
    request_validation_retry_case_count = 0
    stop_reason_counts: dict[str, int] = {}
    policy_id_counts: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        if float(item.get("agent_loop_observed", 0.0) or 0.0) > 0.0:
            observed_case_count += 1
        if float(item.get("agent_loop_enabled", 0.0) or 0.0) > 0.0:
            enabled_case_count += 1
        if float(item.get("agent_loop_attempted", 0.0) or 0.0) > 0.0:
            attempted_case_count += 1
        if float(item.get("agent_loop_replay_safe", 0.0) or 0.0) > 0.0:
            replay_safe_case_count += 1
        actions_requested.append(
            float(item.get("agent_loop_actions_requested", 0.0) or 0.0)
        )
        actions_executed.append(
            float(item.get("agent_loop_actions_executed", 0.0) or 0.0)
        )
        if float(item.get("agent_loop_request_more_context_count", 0.0) or 0.0) > 0.0:
            request_more_context_case_count += 1
        if (
            float(item.get("agent_loop_request_source_plan_retry_count", 0.0) or 0.0)
            > 0.0
        ):
            request_source_plan_retry_case_count += 1
        if (
            float(item.get("agent_loop_request_validation_retry_count", 0.0) or 0.0)
            > 0.0
        ):
            request_validation_retry_case_count += 1
        stop_reason = str(item.get("agent_loop_stop_reason") or "").strip().lower()
        if stop_reason:
            stop_reason_counts[stop_reason] = stop_reason_counts.get(stop_reason, 0) + 1
        policy_id = str(item.get("agent_loop_last_policy_id") or "").strip().lower()
        if policy_id:
            policy_id_counts[policy_id] = policy_id_counts.get(policy_id, 0) + 1

    def _dominant_label(counts: dict[str, int]) -> str:
        if not counts:
            return ""
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    return {
        "case_count": case_count,
        "observed_case_count": observed_case_count,
        "observed_case_rate": float(observed_case_count) / float(case_count),
        "enabled_case_count": enabled_case_count,
        "enabled_case_rate": float(enabled_case_count) / float(case_count),
        "attempted_case_count": attempted_case_count,
        "attempted_case_rate": float(attempted_case_count) / float(case_count),
        "replay_safe_case_count": replay_safe_case_count,
        "replay_safe_case_rate": float(replay_safe_case_count) / float(case_count),
        "actions_requested_mean": mean(actions_requested) if actions_requested else 0.0,
        "actions_executed_mean": mean(actions_executed) if actions_executed else 0.0,
        "request_more_context_case_count": request_more_context_case_count,
        "request_more_context_case_rate": (
            float(request_more_context_case_count) / float(case_count)
        ),
        "request_source_plan_retry_case_count": request_source_plan_retry_case_count,
        "request_source_plan_retry_case_rate": (
            float(request_source_plan_retry_case_count) / float(case_count)
        ),
        "request_validation_retry_case_count": (
            request_validation_retry_case_count
        ),
        "request_validation_retry_case_rate": (
            float(request_validation_retry_case_count) / float(case_count)
        ),
        "dominant_stop_reason": _dominant_label(stop_reason_counts),
        "dominant_last_policy_id": _dominant_label(policy_id_counts),
    }


def build_preference_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "observed_case_count": 0,
            "observed_case_rate": 0.0,
            "notes_hit_case_count": 0,
            "notes_hit_case_rate": 0.0,
            "profile_selected_case_count": 0,
            "profile_selected_case_rate": 0.0,
            "capture_triggered_case_count": 0,
            "capture_triggered_case_rate": 0.0,
            "notes_hit_ratio_mean": 0.0,
            "profile_selected_count_mean": 0.0,
        }

    observed_case_count = 0
    notes_hit_case_count = 0
    profile_selected_case_count = 0
    capture_triggered_case_count = 0
    notes_hit_ratios: list[float] = []
    profile_selected_counts: list[float] = []

    for item in case_results:
        if not isinstance(item, dict):
            continue
        notes_hit_ratio = float(item.get("notes_hit_ratio", 0.0) or 0.0)
        profile_selected_count = float(
            item.get("profile_selected_count", 0.0) or 0.0
        )
        capture_triggered = float(item.get("capture_triggered", 0.0) or 0.0)
        if (
            notes_hit_ratio > 0.0
            or profile_selected_count > 0.0
            or capture_triggered > 0.0
        ):
            observed_case_count += 1
        if notes_hit_ratio > 0.0:
            notes_hit_case_count += 1
        if profile_selected_count > 0.0:
            profile_selected_case_count += 1
        if capture_triggered > 0.0:
            capture_triggered_case_count += 1
        notes_hit_ratios.append(notes_hit_ratio)
        profile_selected_counts.append(profile_selected_count)

    return {
        "case_count": case_count,
        "observed_case_count": observed_case_count,
        "observed_case_rate": (
            float(observed_case_count) / float(case_count) if case_count > 0 else 0.0
        ),
        "notes_hit_case_count": notes_hit_case_count,
        "notes_hit_case_rate": (
            float(notes_hit_case_count) / float(case_count) if case_count > 0 else 0.0
        ),
        "profile_selected_case_count": profile_selected_case_count,
        "profile_selected_case_rate": (
            float(profile_selected_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "capture_triggered_case_count": capture_triggered_case_count,
        "capture_triggered_case_rate": (
            float(capture_triggered_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "notes_hit_ratio_mean": mean(notes_hit_ratios) if notes_hit_ratios else 0.0,
        "profile_selected_count_mean": (
            mean(profile_selected_counts) if profile_selected_counts else 0.0
        ),
    }


def build_feedback_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "enabled_case_count": 0,
            "enabled_case_rate": 0.0,
            "matched_case_count": 0,
            "matched_case_rate": 0.0,
            "boosted_case_count": 0,
            "boosted_case_rate": 0.0,
            "event_count_mean": 0.0,
            "matched_event_count_mean": 0.0,
            "boosted_candidate_count_mean": 0.0,
            "boosted_unique_paths_mean": 0.0,
            "reasons": {},
        }

    enabled_case_count = 0
    matched_case_count = 0
    boosted_case_count = 0
    event_counts: list[float] = []
    matched_event_counts: list[float] = []
    boosted_counts: list[float] = []
    boosted_paths_counts: list[float] = []
    reasons: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        enabled = float(item.get("feedback_enabled", 0.0) or 0.0) > 0.0
        matched_event_count = float(
            item.get("feedback_matched_event_count", 0.0) or 0.0
        )
        boosted_count = float(item.get("feedback_boosted_count", 0.0) or 0.0)
        event_count = float(item.get("feedback_event_count", 0.0) or 0.0)
        boosted_paths = float(item.get("feedback_boosted_paths", 0.0) or 0.0)
        reason = str(item.get("feedback_reason") or "").strip()
        if enabled:
            enabled_case_count += 1
        if matched_event_count > 0.0:
            matched_case_count += 1
        if boosted_count > 0.0:
            boosted_case_count += 1
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        event_counts.append(event_count)
        matched_event_counts.append(matched_event_count)
        boosted_counts.append(boosted_count)
        boosted_paths_counts.append(boosted_paths)

    return {
        "case_count": case_count,
        "enabled_case_count": enabled_case_count,
        "enabled_case_rate": (
            float(enabled_case_count) / float(case_count) if case_count > 0 else 0.0
        ),
        "matched_case_count": matched_case_count,
        "matched_case_rate": (
            float(matched_case_count) / float(case_count) if case_count > 0 else 0.0
        ),
        "boosted_case_count": boosted_case_count,
        "boosted_case_rate": (
            float(boosted_case_count) / float(case_count) if case_count > 0 else 0.0
        ),
        "event_count_mean": mean(event_counts) if event_counts else 0.0,
        "matched_event_count_mean": (
            mean(matched_event_counts) if matched_event_counts else 0.0
        ),
        "boosted_candidate_count_mean": mean(boosted_counts) if boosted_counts else 0.0,
        "boosted_unique_paths_mean": (
            mean(boosted_paths_counts) if boosted_paths_counts else 0.0
        ),
        "reasons": dict(sorted(reasons.items())),
    }


def build_feedback_loop_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "issue_report_case_count": 0,
            "issue_report_linked_case_count": 0,
            "issue_report_linked_plan_case_count": 0,
            "issue_report_resolved_case_count": 0,
            "issue_to_benchmark_case_conversion_rate": 0.0,
            "issue_report_linked_plan_rate": 0.0,
            "issue_report_resolution_rate": 0.0,
            "issue_report_time_to_fix_case_count": 0,
            "issue_report_time_to_fix_hours_mean": 0.0,
            "dev_issue_capture_case_count": 0,
            "dev_issue_captured_case_count": 0,
            "dev_issue_capture_rate": 0.0,
            "dev_feedback_resolution_case_count": 0,
            "dev_feedback_resolved_case_count": 0,
            "dev_feedback_resolution_rate": 0.0,
            "dev_feedback_issue_count": 0,
            "dev_feedback_linked_fix_issue_count": 0,
            "dev_feedback_resolved_issue_count": 0,
            "dev_issue_to_fix_rate": 0.0,
            "dev_feedback_issue_time_to_fix_case_count": 0,
            "dev_feedback_issue_time_to_fix_hours_mean": 0.0,
            "feedback_surfaces": {},
        }

    issue_report_case_count = 0
    issue_report_linked_case_count = 0
    issue_report_linked_plan_case_count = 0
    issue_report_resolved_case_count = 0
    issue_report_time_to_fix_hours: list[float] = []
    dev_issue_capture_case_count = 0
    dev_issue_captured_case_count = 0
    dev_feedback_resolution_case_count = 0
    dev_feedback_resolved_case_count = 0
    dev_feedback_issue_count = 0
    dev_feedback_linked_fix_issue_count = 0
    dev_feedback_resolved_issue_count = 0
    dev_feedback_issue_time_to_fix_hours: list[float] = []
    feedback_surfaces: dict[str, int] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        feedback_surface = str(item.get("feedback_surface") or "").strip()
        if feedback_surface:
            feedback_surfaces[feedback_surface] = (
                feedback_surfaces.get(feedback_surface, 0) + 1
            )

        lane = str(item.get("comparison_lane") or "").strip()
        if lane == "issue_report_feedback":
            issue_report_case_count += 1
            issue_report_issue_id = str(item.get("issue_report_issue_id") or "").strip()
            if issue_report_issue_id:
                issue_report_linked_case_count += 1
                if float(item.get("issue_report_has_plan_ref", 0.0) or 0.0) > 0.0:
                    issue_report_linked_plan_case_count += 1
            if str(item.get("issue_report_resolved_at") or "").strip():
                issue_report_resolved_case_count += 1
            time_to_fix_hours = float(item.get("issue_report_time_to_fix_hours", 0.0) or 0.0)
            if time_to_fix_hours > 0.0:
                issue_report_time_to_fix_hours.append(time_to_fix_hours)
            continue

        if lane == "dev_issue_capture":
            dev_issue_capture_case_count += 1
            if int(item.get("dev_feedback_issue_count", 0) or 0) > 0:
                dev_issue_captured_case_count += 1
            continue

        if lane == "dev_feedback_resolution":
            dev_feedback_resolution_case_count += 1
            task_success_hit = float(
                item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
            )
            if task_success_hit > 0.0:
                dev_feedback_resolved_case_count += 1
            dev_feedback_issue_count += int(item.get("dev_feedback_issue_count", 0) or 0)
            dev_feedback_linked_fix_issue_count += int(
                item.get("dev_feedback_linked_fix_issue_count", 0) or 0
            )
            dev_feedback_resolved_issue_count += int(
                item.get("dev_feedback_resolved_issue_count", 0) or 0
            )
            time_to_fix_hours = float(
                item.get("dev_feedback_issue_time_to_fix_hours", 0.0) or 0.0
            )
            if time_to_fix_hours > 0.0:
                dev_feedback_issue_time_to_fix_hours.append(time_to_fix_hours)

    return {
        "case_count": case_count,
        "issue_report_case_count": issue_report_case_count,
        "issue_report_linked_case_count": issue_report_linked_case_count,
        "issue_report_linked_plan_case_count": issue_report_linked_plan_case_count,
        "issue_report_resolved_case_count": issue_report_resolved_case_count,
        "issue_to_benchmark_case_conversion_rate": (
            float(issue_report_linked_case_count) / float(issue_report_case_count)
            if issue_report_case_count > 0
            else 0.0
        ),
        "issue_report_linked_plan_rate": (
            float(issue_report_linked_plan_case_count)
            / float(issue_report_linked_case_count)
            if issue_report_linked_case_count > 0
            else 0.0
        ),
        "issue_report_resolution_rate": (
            float(issue_report_resolved_case_count) / float(issue_report_case_count)
            if issue_report_case_count > 0
            else 0.0
        ),
        "issue_report_time_to_fix_case_count": len(issue_report_time_to_fix_hours),
        "issue_report_time_to_fix_hours_mean": (
            mean(issue_report_time_to_fix_hours)
            if issue_report_time_to_fix_hours
            else 0.0
        ),
        "dev_issue_capture_case_count": dev_issue_capture_case_count,
        "dev_issue_captured_case_count": dev_issue_captured_case_count,
        "dev_issue_capture_rate": (
            float(dev_issue_captured_case_count) / float(dev_issue_capture_case_count)
            if dev_issue_capture_case_count > 0
            else 0.0
        ),
        "dev_feedback_resolution_case_count": dev_feedback_resolution_case_count,
        "dev_feedback_resolved_case_count": dev_feedback_resolved_case_count,
        "dev_feedback_resolution_rate": (
            float(dev_feedback_resolved_case_count)
            / float(dev_feedback_resolution_case_count)
            if dev_feedback_resolution_case_count > 0
            else 0.0
        ),
        "dev_feedback_issue_count": dev_feedback_issue_count,
        "dev_feedback_linked_fix_issue_count": dev_feedback_linked_fix_issue_count,
        "dev_feedback_resolved_issue_count": dev_feedback_resolved_issue_count,
        "dev_issue_to_fix_rate": (
            float(dev_feedback_linked_fix_issue_count) / float(dev_feedback_issue_count)
            if dev_feedback_issue_count > 0
            else 0.0
        ),
        "dev_feedback_issue_time_to_fix_case_count": len(
            dev_feedback_issue_time_to_fix_hours
        ),
        "dev_feedback_issue_time_to_fix_hours_mean": (
            mean(dev_feedback_issue_time_to_fix_hours)
            if dev_feedback_issue_time_to_fix_hours
            else 0.0
        ),
        "feedback_surfaces": dict(sorted(feedback_surfaces.items())),
    }


def build_comparison_lane_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total_case_count = len(case_results)
    if total_case_count <= 0:
        return {
            "total_case_count": 0,
            "labeled_case_count": 0,
            "lane_count": 0,
            "lanes": [],
        }

    buckets: dict[str, dict[str, float]] = {}
    labeled_case_count = 0
    for item in case_results:
        if not isinstance(item, dict):
            continue
        lane = str(item.get("comparison_lane") or "").strip()
        if not lane:
            continue
        labeled_case_count += 1
        bucket = buckets.setdefault(
            lane,
            {
                "case_count": 0.0,
                "task_success_total": 0.0,
                "recall_total": 0.0,
                "chunk_guard_enabled_total": 0.0,
                "chunk_guard_report_only_total": 0.0,
                "chunk_guard_filtered_case_count": 0.0,
                "chunk_guard_filtered_count_total": 0.0,
                "chunk_guard_filter_ratio_total": 0.0,
                "chunk_guard_pairwise_conflict_total": 0.0,
                "chunk_guard_expectation_case_count": 0.0,
                "chunk_guard_expected_retained_hit_total": 0.0,
                "chunk_guard_report_only_improved_total": 0.0,
                "chunk_guard_expected_filtered_hit_rate_total": 0.0,
            },
        )
        filtered_count = float(item.get("chunk_guard_filtered_count", 0.0) or 0.0)
        expectation_applicable = float(
            item.get("chunk_guard_expectation_applicable", 0.0) or 0.0
        )
        bucket["case_count"] += 1.0
        bucket["task_success_total"] += float(
            item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
        )
        bucket["recall_total"] += float(item.get("recall_hit", 0.0) or 0.0)
        bucket["chunk_guard_enabled_total"] += float(
            item.get("chunk_guard_enabled", 0.0) or 0.0
        )
        bucket["chunk_guard_report_only_total"] += float(
            item.get("chunk_guard_report_only", 0.0) or 0.0
        )
        bucket["chunk_guard_filtered_case_count"] += 1.0 if filtered_count > 0.0 else 0.0
        bucket["chunk_guard_filtered_count_total"] += filtered_count
        bucket["chunk_guard_filter_ratio_total"] += float(
            item.get("chunk_guard_filter_ratio", 0.0) or 0.0
        )
        bucket["chunk_guard_pairwise_conflict_total"] += float(
            item.get("chunk_guard_pairwise_conflict_count", 0.0) or 0.0
        )
        bucket["chunk_guard_expectation_case_count"] += expectation_applicable
        if expectation_applicable > 0.0:
            bucket["chunk_guard_expected_retained_hit_total"] += float(
                item.get("chunk_guard_expected_retained_hit", 0.0) or 0.0
            )
        bucket["chunk_guard_report_only_improved_total"] += float(
            item.get("chunk_guard_report_only_improved", 0.0) or 0.0
        )
        if expectation_applicable > 0.0:
            bucket["chunk_guard_expected_filtered_hit_rate_total"] += float(
                item.get("chunk_guard_expected_filtered_hit_rate", 0.0) or 0.0
            )

    lanes: list[dict[str, Any]] = []
    for lane in sorted(buckets):
        bucket = buckets[lane]
        case_count = max(1.0, float(bucket["case_count"]))
        expectation_case_count = max(
            0.0, float(bucket["chunk_guard_expectation_case_count"])
        )
        lanes.append(
            {
                "comparison_lane": lane,
                "case_count": int(case_count),
                "task_success_rate": float(bucket["task_success_total"]) / case_count,
                "recall_at_k": float(bucket["recall_total"]) / case_count,
                "chunk_guard_enabled_ratio": (
                    float(bucket["chunk_guard_enabled_total"]) / case_count
                ),
                "chunk_guard_report_only_ratio": (
                    float(bucket["chunk_guard_report_only_total"]) / case_count
                ),
                "chunk_guard_filtered_case_rate": (
                    float(bucket["chunk_guard_filtered_case_count"]) / case_count
                ),
                "chunk_guard_filtered_count_mean": (
                    float(bucket["chunk_guard_filtered_count_total"]) / case_count
                ),
                "chunk_guard_filter_ratio_mean": (
                    float(bucket["chunk_guard_filter_ratio_total"]) / case_count
                ),
                "chunk_guard_expected_retained_hit_rate_mean": (
                    float(bucket["chunk_guard_expected_retained_hit_total"])
                    / expectation_case_count
                    if expectation_case_count > 0.0
                    else 0.0
                ),
                "chunk_guard_report_only_improved_rate": (
                    float(bucket["chunk_guard_report_only_improved_total"])
                    / expectation_case_count
                    if expectation_case_count > 0.0
                    else 0.0
                ),
                "chunk_guard_expected_filtered_hit_rate_mean": (
                    float(bucket["chunk_guard_expected_filtered_hit_rate_total"])
                    / expectation_case_count
                    if expectation_case_count > 0.0
                    else 0.0
                ),
                "chunk_guard_pairwise_conflict_count_mean": (
                    float(bucket["chunk_guard_pairwise_conflict_total"]) / case_count
                ),
            }
        )

    return {
        "total_case_count": total_case_count,
        "labeled_case_count": labeled_case_count,
        "lane_count": len(lanes),
        "lanes": lanes,
    }


def build_stage_latency_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stage in PIPELINE_STAGE_ORDER:
        field = f"{stage}_latency_ms"
        values = [float(item.get(field, 0.0) or 0.0) for item in case_results]
        if not values:
            summary[stage] = {"mean_ms": 0.0, "p95_ms": 0.0}
            continue
        summary[stage] = {
            "mean_ms": mean(values),
            "p95_ms": p95(values),
        }

    total_values = [float(item.get("latency_ms", 0.0) or 0.0) for item in case_results]
    summary["total"] = {
        "mean_ms": mean(total_values) if total_values else 0.0,
        "median_ms": float(median(total_values)) if total_values else 0.0,
        "p95_ms": p95(total_values),
    }
    return summary


def build_slo_budget_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "budget_limits_ms": {
                "parallel_time_budget_ms_mean": 0.0,
                "embedding_time_budget_ms_mean": 0.0,
                "chunk_semantic_time_budget_ms_mean": 0.0,
                "xref_time_budget_ms_mean": 0.0,
            },
            "downgrade_case_count": 0,
            "downgrade_case_rate": 0.0,
            "signals": {
                "parallel_docs_timeout_ratio": {"count": 0, "rate": 0.0},
                "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                "embedding_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                "embedding_adaptive_budget_ratio": {"count": 0, "rate": 0.0},
                "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                "chunk_semantic_time_budget_exceeded_ratio": {
                    "count": 0,
                    "rate": 0.0,
                },
                "chunk_semantic_fallback_ratio": {"count": 0, "rate": 0.0},
                "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
            },
        }

    budget_limits = {
        "parallel_time_budget_ms_mean": mean(
            float(item.get("parallel_time_budget_ms", 0.0) or 0.0)
            for item in case_results
        ),
        "embedding_time_budget_ms_mean": mean(
            float(item.get("embedding_time_budget_ms", 0.0) or 0.0)
            for item in case_results
        ),
        "chunk_semantic_time_budget_ms_mean": mean(
            float(item.get("chunk_semantic_time_budget_ms", 0.0) or 0.0)
            for item in case_results
        ),
        "xref_time_budget_ms_mean": mean(
            float(item.get("xref_time_budget_ms", 0.0) or 0.0) for item in case_results
        ),
    }
    signal_sources = {
        "parallel_docs_timeout_ratio": "parallel_docs_timed_out",
        "parallel_worktree_timeout_ratio": "parallel_worktree_timed_out",
        "embedding_time_budget_exceeded_ratio": "embedding_time_budget_exceeded",
        "embedding_adaptive_budget_ratio": "embedding_adaptive_budget_applied",
        "embedding_fallback_ratio": "embedding_fallback",
        "chunk_semantic_time_budget_exceeded_ratio": "chunk_semantic_time_budget_exceeded",
        "chunk_semantic_fallback_ratio": "chunk_semantic_fallback",
        "xref_budget_exhausted_ratio": "xref_budget_exhausted",
    }
    signals: dict[str, dict[str, float | int]] = {}
    for field, source_field in signal_sources.items():
        count = sum(
            1
            for item in case_results
            if float(item.get(source_field, 0.0) or 0.0) > 0.0
        )
        signals[field] = {
            "count": count,
            "rate": float(count) / float(case_count),
        }

    downgrade_case_count = sum(
        1
        for item in case_results
        if float(item.get("slo_downgrade_triggered", 0.0) or 0.0) > 0.0
    )
    return {
        "case_count": case_count,
        "budget_limits_ms": budget_limits,
        "downgrade_case_count": downgrade_case_count,
        "downgrade_case_rate": float(downgrade_case_count) / float(case_count),
        "signals": signals,
    }


__all__ = [
    "build_agent_loop_control_plane_summary",
    "build_chunk_stage_miss_summary",
    "build_comparison_lane_summary",
    "build_decision_observability_summary",
    "build_evidence_insufficiency_summary",
    "build_feedback_loop_summary",
    "build_feedback_observability_summary",
    "build_missing_context_risk_summary",
    "build_preference_observability_summary",
    "build_retrieval_context_observability_summary",
    "build_retrieval_default_strategy_summary",
    "build_slo_budget_summary",
    "build_stage_latency_summary",
    "build_wave1_context_governance_summary",
    "is_risk_upgrade_case",
    "summarize_missing_context_risk_case",
]
