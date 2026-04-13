from __future__ import annotations

from typing import Any


def append_preference_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("preference_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Preference Observability Summary")
    lines.append("")
    lines.append(
        "- Observed cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("observed_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("observed_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Notes-hit cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("notes_hit_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("notes_hit_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Profile-selected cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("profile_selected_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("profile_selected_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Capture-triggered cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("capture_triggered_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("capture_triggered_case_rate", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| notes_hit_ratio_mean | {value:.4f} |".format(
            value=float(summary.get("notes_hit_ratio_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| profile_selected_count_mean | {value:.4f} |".format(
            value=float(summary.get("profile_selected_count_mean", 0.0) or 0.0)
        )
    )
    lines.append("")


def append_feedback_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("feedback_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    reasons_raw = summary.get("reasons")
    reasons: dict[str, Any] = reasons_raw if isinstance(reasons_raw, dict) else {}

    lines.append("## Feedback Observability Summary")
    lines.append("")
    lines.append(
        "- Enabled cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("enabled_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("enabled_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Matched cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("matched_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("matched_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Boosted cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("boosted_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("boosted_case_rate", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| event_count_mean | {value:.4f} |".format(
            value=float(summary.get("event_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| matched_event_count_mean | {value:.4f} |".format(
            value=float(summary.get("matched_event_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| boosted_candidate_count_mean | {value:.4f} |".format(
            value=float(summary.get("boosted_candidate_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| boosted_unique_paths_mean | {value:.4f} |".format(
            value=float(summary.get("boosted_unique_paths_mean", 0.0) or 0.0)
        )
    )
    lines.append("")
    lines.append("### Reasons")
    lines.append("")
    if not reasons:
        lines.append("- None")
        lines.append("")
        return
    lines.append("| Reason | Count |")
    lines.append("| --- | ---: |")
    for name, count in sorted(
        reasons.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
    ):
        lines.append(f"| {name} | {int(count or 0)} |")
    lines.append("")


def append_ltm_explainability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("ltm_explainability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    case_count = int(summary.get("case_count", 0) or 0)
    lines.append("## Long-Term Explainability Summary")
    lines.append("")
    lines.append(
        "- Selected cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("selected_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("selected_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Attribution cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("attribution_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("attribution_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Graph-neighbor cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("graph_neighbor_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("graph_neighbor_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Plan-constraint cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("plan_constraint_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("plan_constraint_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Feedback-signal observed cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("feedback_signal_observed_case_count", 0) or 0),
            total=case_count,
            rate=float(
                summary.get("feedback_signal_observed_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Attribution-scope observed cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("attribution_scope_observed_case_count", 0) or 0),
            total=case_count,
            rate=float(
                summary.get("attribution_scope_observed_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| selected_count_mean | {value:.4f} |".format(
            value=float(summary.get("selected_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| attribution_count_mean | {value:.4f} |".format(
            value=float(summary.get("attribution_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| graph_neighbor_count_mean | {value:.4f} |".format(
            value=float(summary.get("graph_neighbor_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| plan_constraint_count_mean | {value:.4f} |".format(
            value=float(summary.get("plan_constraint_count_mean", 0.0) or 0.0)
        )
    )
    lines.append("")
    feedback_rows_raw = summary.get("feedback_signals")
    feedback_rows = feedback_rows_raw if isinstance(feedback_rows_raw, list) else []
    if feedback_rows:
        lines.append("| Feedback Signal | Cases | Case Rate | Total Count | Count Mean |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for item in feedback_rows:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| "
                f"{str(item.get('feedback_signal') or '').strip() or '(unknown)'}"
                f" | {int(item.get('case_count', 0) or 0)}"
                f" | {float(item.get('case_rate', 0.0) or 0.0):.4f}"
                f" | {int(item.get('total_count', 0) or 0)}"
                f" | {float(item.get('count_mean', 0.0) or 0.0):.4f} |"
            )
        lines.append("")
    attribution_rows_raw = summary.get("attribution_scopes")
    attribution_rows = (
        attribution_rows_raw if isinstance(attribution_rows_raw, list) else []
    )
    if attribution_rows:
        lines.append(
            "| Attribution Scope | Cases | Case Rate | Total Count | Count Mean |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for item in attribution_rows:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| "
                f"{str(item.get('attribution_scope') or '').strip() or '(unknown)'}"
                f" | {int(item.get('case_count', 0) or 0)}"
                f" | {float(item.get('case_rate', 0.0) or 0.0):.4f}"
                f" | {int(item.get('total_count', 0) or 0)}"
                f" | {float(item.get('count_mean', 0.0) or 0.0):.4f} |"
            )
        lines.append("")


def append_feedback_loop_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("feedback_loop_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    feedback_surfaces_raw = summary.get("feedback_surfaces")
    feedback_surfaces: dict[str, Any] = (
        feedback_surfaces_raw if isinstance(feedback_surfaces_raw, dict) else {}
    )

    lines.append("## Feedback Loop Summary")
    lines.append("")
    lines.append(
        "- Issue-report cases: {count}".format(
            count=int(summary.get("issue_report_case_count", 0) or 0)
        )
    )
    lines.append(
        "- Converted issue-report benchmark cases: {count} rate={rate:.4f}".format(
            count=int(summary.get("issue_report_linked_case_count", 0) or 0),
            rate=float(
                summary.get("issue_to_benchmark_case_conversion_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Linked-plan issue reports: {count} rate={rate:.4f}".format(
            count=int(summary.get("issue_report_linked_plan_case_count", 0) or 0),
            rate=float(summary.get("issue_report_linked_plan_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Resolved issue reports: {count} rate={rate:.4f} time_to_fix_mean={hours:.2f}h".format(
            count=int(summary.get("issue_report_resolved_case_count", 0) or 0),
            rate=float(summary.get("issue_report_resolution_rate", 0.0) or 0.0),
            hours=float(summary.get("issue_report_time_to_fix_hours_mean", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Dev-issue capture cases: {count} captured={captured} rate={rate:.4f}".format(
            count=int(summary.get("dev_issue_capture_case_count", 0) or 0),
            captured=int(summary.get("dev_issue_captured_case_count", 0) or 0),
            rate=float(summary.get("dev_issue_capture_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Dev-feedback resolution cases: {count} resolved={resolved} rate={rate:.4f}".format(
            count=int(summary.get("dev_feedback_resolution_case_count", 0) or 0),
            resolved=int(summary.get("dev_feedback_resolved_case_count", 0) or 0),
            rate=float(summary.get("dev_feedback_resolution_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Dev-feedback issue linkage: issues={issue_count} linked_fixes={linked} resolved_issues={resolved} issue_to_fix_rate={rate:.4f} time_to_fix_mean={hours:.2f}h".format(
            issue_count=int(summary.get("dev_feedback_issue_count", 0) or 0),
            linked=int(summary.get("dev_feedback_linked_fix_issue_count", 0) or 0),
            resolved=int(summary.get("dev_feedback_resolved_issue_count", 0) or 0),
            rate=float(summary.get("dev_issue_to_fix_rate", 0.0) or 0.0),
            hours=float(
                summary.get("dev_feedback_issue_time_to_fix_hours_mean", 0.0) or 0.0
            ),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| issue_to_benchmark_case_conversion_rate | {value:.4f} |".format(
            value=float(
                summary.get("issue_to_benchmark_case_conversion_rate", 0.0) or 0.0
            )
        )
    )
    lines.append(
        "| issue_report_linked_plan_rate | {value:.4f} |".format(
            value=float(summary.get("issue_report_linked_plan_rate", 0.0) or 0.0)
        )
    )
    lines.append(
        "| issue_report_time_to_fix_hours_mean | {value:.2f} |".format(
            value=float(summary.get("issue_report_time_to_fix_hours_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| dev_issue_capture_rate | {value:.4f} |".format(
            value=float(summary.get("dev_issue_capture_rate", 0.0) or 0.0)
        )
    )
    lines.append(
        "| dev_feedback_resolution_rate | {value:.4f} |".format(
            value=float(summary.get("dev_feedback_resolution_rate", 0.0) or 0.0)
        )
    )
    lines.append(
        "| dev_issue_to_fix_rate | {value:.4f} |".format(
            value=float(summary.get("dev_issue_to_fix_rate", 0.0) or 0.0)
        )
    )
    lines.append("")
    lines.append("### Feedback Surfaces")
    lines.append("")
    if not feedback_surfaces:
        lines.append("- None")
        lines.append("")
        return

    lines.append("| Surface | Count |")
    lines.append("| --- | ---: |")
    for name, count in sorted(
        feedback_surfaces.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
    ):
        lines.append(f"| {name} | {int(count or 0)} |")
    lines.append("")


def append_adaptive_router_observability_summary(
    lines: list[str],
    results: dict[str, Any],
) -> None:
    summary_raw = results.get("adaptive_router_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    enabled_case_count = int(summary.get("enabled_case_count", 0) or 0)
    shadow_coverage_case_count = int(summary.get("shadow_coverage_case_count", 0) or 0)
    comparable_case_count = int(summary.get("comparable_case_count", 0) or 0)
    agreement_case_count = int(summary.get("agreement_case_count", 0) or 0)
    disagreement_case_count = int(summary.get("disagreement_case_count", 0) or 0)

    lines.append("## Adaptive Router Observability")
    lines.append("")
    lines.append(
        "- Enabled cases: {count}/{total} ({rate:.4f})".format(
            count=enabled_case_count,
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("enabled_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Shadow coverage: {count}/{enabled} ({rate:.4f})".format(
            count=shadow_coverage_case_count,
            enabled=enabled_case_count,
            rate=float(summary.get("shadow_coverage_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Comparable cases: {count}/{enabled} ({rate:.4f})".format(
            count=comparable_case_count,
            enabled=enabled_case_count,
            rate=float(summary.get("comparable_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Agreement: {count}/{comparable} ({rate:.4f})".format(
            count=agreement_case_count,
            comparable=comparable_case_count,
            rate=float(summary.get("agreement_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Disagreement: {count}/{comparable} ({rate:.4f})".format(
            count=disagreement_case_count,
            comparable=comparable_case_count,
            rate=float(summary.get("disagreement_rate", 0.0) or 0.0),
        )
    )
    shadow_source_counts_raw = summary.get("shadow_source_counts")
    shadow_source_counts: dict[str, Any] = (
        shadow_source_counts_raw if isinstance(shadow_source_counts_raw, dict) else {}
    )
    if shadow_source_counts:
        formatted = ", ".join(
            f"{name}={int(count or 0)}"
            for name, count in sorted(
                shadow_source_counts.items(),
                key=lambda item: (-int(item[1] or 0), str(item[0])),
            )
        )
        lines.append(f"- Shadow sources: {formatted}")
    lines.append("")

    executed_arms = summary.get("executed_arms", [])
    if isinstance(executed_arms, list) and executed_arms:
        lines.append("### Executed Arms")
        lines.append("")
        for item in executed_arms:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {arm_id}: cases={case_count} rate={case_rate:.4f} task_success={task_success:.4f} mrr={mrr:.4f} fallback_cases={fallback_cases} downgrade_cases={downgrade_cases} latency_p95_ms={latency_p95:.4f} index_latency_p95_ms={index_latency_p95:.4f}".format(
                    arm_id=str(item.get("arm_id", "") or "(unknown)"),
                    case_count=int(item.get("case_count", 0) or 0),
                    case_rate=float(item.get("case_rate", 0.0) or 0.0),
                    task_success=float(item.get("task_success_rate", 0.0) or 0.0),
                    mrr=float(item.get("mrr", 0.0) or 0.0),
                    fallback_cases=int(item.get("fallback_case_count", 0) or 0),
                    downgrade_cases=int(item.get("downgrade_case_count", 0) or 0),
                    latency_p95=float(item.get("latency_p95_ms", 0.0) or 0.0),
                    index_latency_p95=float(
                        item.get("index_latency_p95_ms", 0.0) or 0.0
                    ),
                )
            )
        lines.append("")

    shadow_arms = summary.get("shadow_arms", [])
    if isinstance(shadow_arms, list) and shadow_arms:
        lines.append("### Shadow Arms")
        lines.append("")
        for item in shadow_arms:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {arm_id}: cases={case_count} rate={case_rate:.4f} task_success={task_success:.4f} mrr={mrr:.4f} fallback_cases={fallback_cases} downgrade_cases={downgrade_cases} latency_p95_ms={latency_p95:.4f} index_latency_p95_ms={index_latency_p95:.4f}".format(
                    arm_id=str(item.get("arm_id", "") or "(unknown)"),
                    case_count=int(item.get("case_count", 0) or 0),
                    case_rate=float(item.get("case_rate", 0.0) or 0.0),
                    task_success=float(item.get("task_success_rate", 0.0) or 0.0),
                    mrr=float(item.get("mrr", 0.0) or 0.0),
                    fallback_cases=int(item.get("fallback_case_count", 0) or 0),
                    downgrade_cases=int(item.get("downgrade_case_count", 0) or 0),
                    latency_p95=float(item.get("latency_p95_ms", 0.0) or 0.0),
                    index_latency_p95=float(
                        item.get("index_latency_p95_ms", 0.0) or 0.0
                    ),
                )
            )
        lines.append("")


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
    "append_decision_observability_summary",
    "append_feedback_loop_summary",
    "append_feedback_observability_summary",
    "append_ltm_explainability_summary",
    "append_preference_observability_summary",
    "append_retrieval_control_plane_gate_summary",
    "append_reward_log_summary",
    "format_decision_event",
]
