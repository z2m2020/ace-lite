from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_metrics import (
    format_metric as _format_metric,
)
from ace_lite.benchmark.report_observability_memory import (
    append_feedback_loop_summary as _append_feedback_loop_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_feedback_observability_summary as _append_feedback_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_ltm_explainability_summary as _append_ltm_explainability_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_preference_observability_summary as _append_preference_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_adaptive_router_observability_summary as _append_adaptive_router_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_context_refine_summary as _append_context_refine_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_retrieval_context_observability_summary as _append_retrieval_context_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_retrieval_default_strategy_summary as _append_retrieval_default_strategy_summary_impl,
)
from ace_lite.benchmark.report_summary import get_nested_mapping, get_summary_mapping


def append_preference_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_preference_observability_summary_impl(lines, results)


def append_feedback_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_feedback_observability_summary_impl(lines, results)


def append_evidence_insufficiency_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary = get_summary_mapping(results=results, key="evidence_insufficiency_summary")
    if not summary:
        return

    reasons = get_nested_mapping(payload=summary, key="reasons")
    signals = get_nested_mapping(payload=summary, key="signals")
    applicable_case_count = int(summary.get("applicable_case_count", 0) or 0)

    lines.append("## Evidence Insufficiency Summary")
    lines.append("")
    lines.append(f"- Applicable failing positive cases: {applicable_case_count}")
    lines.append(
        "- Excluded negative-control cases: {count}".format(
            count=int(summary.get("excluded_negative_control_case_count", 0) or 0)
        )
    )
    lines.append(
        "- Evidence-insufficient cases: {count} ({rate})".format(
            count=int(summary.get("evidence_insufficient_count", 0) or 0),
            rate=_format_metric(
                "evidence_insufficient_rate",
                summary.get("evidence_insufficient_rate", 0.0),
            ),
        )
    )
    lines.append("")
    lines.append("### Reasons")
    lines.append("")
    if not reasons:
        lines.append("- None")
        lines.append("")
    else:
        lines.append("| Reason | Count | Rate |")
        lines.append("| --- | ---: | ---: |")
        for name, count in sorted(
            reasons.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
        ):
            rate = (
                float(count or 0) / float(applicable_case_count)
                if applicable_case_count > 0
                else 0.0
            )
            lines.append(
                f"| {name} | {int(count or 0)} | {_format_metric('evidence_insufficient_rate', rate)} |"
            )
        lines.append("")

    lines.append("### Signals")
    lines.append("")
    if not signals:
        lines.append("- None")
        lines.append("")
        return
    lines.append("| Signal | Count |")
    lines.append("| --- | ---: |")
    for name, count in sorted(
        signals.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
    ):
        lines.append(f"| {name} | {int(count or 0)} |")
    lines.append("")


def append_missing_context_risk_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary = get_summary_mapping(results=results, key="missing_context_risk_summary")
    if not summary:
        return

    levels = get_nested_mapping(payload=summary, key="levels")
    signals = get_nested_mapping(payload=summary, key="signals")
    applicable_case_count = int(summary.get("applicable_case_count", 0) or 0)

    lines.append("## Missing-Context Risk Summary")
    lines.append("")
    lines.append(f"- Applicable positive cases: {applicable_case_count}")
    lines.append(
        "- Excluded negative-control cases: {count}".format(
            count=int(summary.get("excluded_negative_control_case_count", 0) or 0)
        )
    )
    lines.append(
        "- Elevated cases: {count} ({rate:.4f})".format(
            count=int(summary.get("elevated_case_count", 0) or 0),
            rate=float(summary.get("elevated_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- High-risk cases: {count} ({rate:.4f})".format(
            count=int(summary.get("high_risk_case_count", 0) or 0),
            rate=float(summary.get("high_risk_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Risk score mean / p95: {mean:.4f} / {p95:.4f}".format(
            mean=float(summary.get("risk_score_mean", 0.0) or 0.0),
            p95=float(summary.get("risk_score_p95", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Risk-driven upgrades: {count}/{elevated} ({rate:.4f})".format(
            count=int(summary.get("risk_upgrade_case_count", 0) or 0),
            elevated=int(summary.get("elevated_case_count", 0) or 0),
            rate=float(summary.get("risk_upgrade_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Risk-upgrade precision mean / baseline / gain: {upgrade:.4f} / {baseline:.4f} / {gain:.4f}".format(
            upgrade=float(summary.get("risk_upgrade_precision_mean", 0.0) or 0.0),
            baseline=float(summary.get("risk_baseline_precision_mean", 0.0) or 0.0),
            gain=float(summary.get("risk_upgrade_precision_gain", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("### Levels")
    lines.append("")
    if not levels:
        lines.append("- None")
        lines.append("")
    else:
        lines.append("| Level | Count | Rate |")
        lines.append("| --- | ---: | ---: |")
        for name, count in sorted(
            levels.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
        ):
            rate = (
                float(count or 0) / float(applicable_case_count)
                if applicable_case_count > 0
                else 0.0
            )
            lines.append(f"| {name} | {int(count or 0)} | {rate:.4f} |")
        lines.append("")

    lines.append("### Signals")
    lines.append("")
    if not signals:
        lines.append("- None")
        lines.append("")
        return
    lines.append("| Signal | Count |")
    lines.append("| --- | ---: |")
    for name, count in sorted(
        signals.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
    ):
        lines.append(f"| {name} | {int(count or 0)} |")
    lines.append("")


def append_ltm_explainability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_ltm_explainability_summary_impl(lines, results)


def append_feedback_loop_summary(lines: list[str], results: dict[str, Any]) -> None:
    return _append_feedback_loop_summary_impl(lines, results)


def append_retrieval_context_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_retrieval_context_observability_summary_impl(lines, results)


def append_retrieval_default_strategy_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_retrieval_default_strategy_summary_impl(lines, results)


def append_adaptive_router_observability_summary(
    lines: list[str],
    results: dict[str, Any],
) -> None:
    return _append_adaptive_router_observability_summary_impl(lines, results)


def append_reward_log_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("reward_log_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Reward Log Summary")
    lines.append("")
    lines.append(f"- Status: {summary.get('status') or 'disabled'!s}")
    lines.append(f"- Enabled: {bool(summary.get('enabled', False))}")
    lines.append(f"- Active: {bool(summary.get('active', False))}")
    lines.append(f"- Path: {summary.get('path') or '(none)'!s}")
    lines.append(
        "- Eligible cases: {count}".format(
            count=max(0, int(summary.get("eligible_case_count", 0) or 0))
        )
    )
    lines.append(
        "- Submitted events: {count}".format(
            count=max(0, int(summary.get("submitted_count", 0) or 0))
        )
    )
    lines.append(
        "- Written events: {count}".format(
            count=max(0, int(summary.get("written_count", 0) or 0))
        )
    )
    lines.append(
        "- Pending events: {count}".format(
            count=max(0, int(summary.get("pending_count", 0) or 0))
        )
    )
    lines.append(
        "- Error count: {count}".format(
            count=max(0, int(summary.get("error_count", 0) or 0))
        )
    )
    last_error = str(summary.get("last_error") or "").strip()
    if last_error:
        lines.append(f"- Last error: {last_error}")
    lines.append("")


def append_wave1_context_governance_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary = get_summary_mapping(results=results, key="wave1_context_governance_summary")
    if not summary:
        return

    case_count = int(summary.get("case_count", 0) or 0)
    lines.append("## Wave 1 Context Governance Summary")
    lines.append("")
    lines.append(
        "- Plan-available cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("plan_available_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("plan_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- History-hits cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("history_hits_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("history_hits_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Candidate-review cases: {count}/{total} ({rate:.4f}); watch={watch_count} ({watch_rate:.4f})".format(
            count=int(summary.get("candidate_review_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("candidate_review_case_rate", 0.0) or 0.0),
            watch_count=int(summary.get("candidate_review_watch_case_count", 0) or 0),
            watch_rate=float(
                summary.get("candidate_review_watch_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Validation-findings cases: {count}/{total} ({rate:.4f}); blocker={blocker_count} ({blocker_rate:.4f})".format(
            count=int(summary.get("validation_findings_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("validation_findings_case_rate", 0.0) or 0.0),
            blocker_count=int(summary.get("validation_blocker_case_count", 0) or 0),
            blocker_rate=float(
                summary.get("validation_blocker_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Session-end-report cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("session_end_report_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("session_end_report_case_rate", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| history_hit_count_mean | {value:.4f} |".format(
            value=float(summary.get("history_hit_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| validation_warn_count_mean | {value:.4f} |".format(
            value=float(summary.get("validation_warn_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| validation_blocker_count_mean | {value:.4f} |".format(
            value=float(summary.get("validation_blocker_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| session_next_action_count_mean | {value:.4f} |".format(
            value=float(summary.get("session_next_action_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| session_risk_count_mean | {value:.4f} |".format(
            value=float(summary.get("session_risk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append("")


def append_context_refine_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_context_refine_summary_impl(lines, results)


def append_retrieval_control_plane_gate_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("retrieval_control_plane_gate_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    failed_checks_raw = summary.get("failed_checks", [])
    failed_checks = (
        [str(item) for item in failed_checks_raw if str(item).strip()]
        if isinstance(failed_checks_raw, list)
        else []
    )

    lines.append("## Retrieval Control Plane Gate Summary")
    lines.append("")
    lines.append(
        f"- Gate passed: {'yes' if bool(summary.get('gate_passed', False)) else 'no'}"
    )
    lines.append(
        "- Regression evaluated: {value}".format(
            value="yes" if bool(summary.get("regression_evaluated", False)) else "no"
        )
    )
    lines.append(
        "- Benchmark regression detected: {value}".format(
            value="yes"
            if bool(summary.get("benchmark_regression_detected", False))
            else "no"
        )
    )
    benchmark_regression_passed = (
        bool(summary.get("benchmark_regression_passed", False))
        if "benchmark_regression_passed" in summary
        else not bool(summary.get("benchmark_regression_detected", False))
    )
    lines.append(
        "- Benchmark regression gate: {value}".format(
            value="pass" if benchmark_regression_passed else "fail"
        )
    )
    lines.append(
        "- Adaptive router shadow coverage: {value:.4f} (threshold >= {threshold:.4f}, {status})".format(
            value=float(summary.get("adaptive_router_shadow_coverage", 0.0) or 0.0),
            threshold=float(
                summary.get("adaptive_router_shadow_coverage_threshold", 0.0) or 0.0
            ),
            status="pass"
            if bool(summary.get("adaptive_router_shadow_coverage_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Risk-upgrade precision gain: {value:.4f} (threshold >= {threshold:.4f}, {status})".format(
            value=float(summary.get("risk_upgrade_precision_gain", 0.0) or 0.0),
            threshold=float(
                summary.get("risk_upgrade_precision_gain_threshold", 0.0) or 0.0
            ),
            status="pass"
            if bool(summary.get("risk_upgrade_precision_gain_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Latency p95 ms: {value:.2f} (threshold <= {threshold:.2f}, {status})".format(
            value=float(summary.get("latency_p95_ms", 0.0) or 0.0),
            threshold=float(summary.get("latency_p95_ms_threshold", 0.0) or 0.0),
            status="pass"
            if bool(summary.get("latency_p95_ms_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Failed checks: {value}".format(
            value=", ".join(failed_checks) if failed_checks else "(none)"
        )
    )
    lines.append("")


def append_decision_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("decision_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Decision Observability Summary")
    lines.append("")
    lines.append(
        "- Cases with decision events: {count}/{case_count} ({rate})".format(
            count=int(summary.get("case_with_decisions_count", 0) or 0),
            case_count=int(summary.get("case_count", 0) or 0),
            rate=f"{float(summary.get('case_with_decisions_rate', 0.0) or 0.0):.4f}",
        )
    )
    lines.append(
        "- Decision events: {count}".format(
            count=int(summary.get("decision_event_count", 0) or 0)
        )
    )
    lines.append("")

    for title, key in (
        ("Actions", "actions"),
        ("Targets", "targets"),
        ("Reasons", "reasons"),
        ("Outcomes", "outcomes"),
    ):
        counts_raw = summary.get(key)
        counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
        lines.append(f"### {title}")
        lines.append("")
        if not counts:
            lines.append("- None")
            lines.append("")
            continue
        label = title[:-1] if title.endswith("s") else title
        lines.append(f"| {label} | Count |")
        lines.append("| --- | ---: |")
        for name, count in sorted(
            counts.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
        ):
            lines.append(f"| {name} | {int(count or 0)} |")
        lines.append("")


def append_workload_taxonomy_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary = get_summary_mapping(results=results, key="workload_taxonomy_summary")
    if not summary:
        return

    rows_raw = summary.get("taxonomies")
    rows = rows_raw if isinstance(rows_raw, list) else []
    lines.append("## Workload Taxonomy Summary")
    lines.append("")
    lines.append(
        "- Dominant taxonomy: {value}".format(
            value=str(summary.get("dominant_workload_taxonomy") or "").strip()
            or "(none)"
        )
    )
    lines.append(
        "- Observed taxonomies: {count}".format(
            count=int(summary.get("taxonomy_count", 0) or 0)
        )
    )
    lines.append("")
    if not rows:
        lines.append("- None")
        lines.append("")
        return
    lines.append("| Taxonomy | Count | Rate |")
    lines.append("| --- | ---: | ---: |")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {name} | {count} | {rate:.4f} |".format(
                name=str(row.get("workload_taxonomy") or "").strip() or "unknown",
                count=int(row.get("count", 0) or 0),
                rate=float(row.get("rate", 0.0) or 0.0),
            )
        )
    lines.append("")


def format_decision_event(event: dict[str, Any]) -> str:
    stage = str(event.get("stage") or "").strip()
    action = str(event.get("action") or "").strip()
    target = str(event.get("target") or "").strip()
    reason = str(event.get("reason") or "").strip()
    outcome = str(event.get("outcome") or "").strip()
    parts = [part for part in (stage, action, target) if part]
    if reason:
        parts.append(f"reason={reason}")
    if outcome:
        parts.append(f"outcome={outcome}")
    return " | ".join(parts)


__all__ = [
    "append_adaptive_router_observability_summary",
    "append_context_refine_summary",
    "append_decision_observability_summary",
    "append_evidence_insufficiency_summary",
    "append_feedback_loop_summary",
    "append_feedback_observability_summary",
    "append_ltm_explainability_summary",
    "append_missing_context_risk_summary",
    "append_preference_observability_summary",
    "append_retrieval_context_observability_summary",
    "append_retrieval_control_plane_gate_summary",
    "append_retrieval_default_strategy_summary",
    "append_reward_log_summary",
    "append_wave1_context_governance_summary",
    "append_workload_taxonomy_summary",
    "format_decision_event",
]
