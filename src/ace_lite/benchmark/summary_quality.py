"""Non-router benchmark summary builders."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from ace_lite.benchmark.summary_common import PIPELINE_STAGE_ORDER, p95


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
    "build_chunk_stage_miss_summary",
    "build_comparison_lane_summary",
    "build_decision_observability_summary",
    "build_evidence_insufficiency_summary",
    "build_feedback_loop_summary",
    "build_feedback_observability_summary",
    "build_preference_observability_summary",
    "build_retrieval_context_observability_summary",
    "build_slo_budget_summary",
    "build_stage_latency_summary",
]
