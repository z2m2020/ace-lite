from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_summary import get_nested_mapping, get_summary_mapping


def append_preference_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary = get_summary_mapping(results=results, key="preference_observability_summary")
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
    summary = get_summary_mapping(results=results, key="feedback_observability_summary")
    if not summary:
        return

    reasons = get_nested_mapping(payload=summary, key="reasons")

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
    summary = get_summary_mapping(results=results, key="ltm_explainability_summary")
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
    summary = get_summary_mapping(results=results, key="feedback_loop_summary")
    if not summary:
        return

    feedback_surfaces = get_nested_mapping(payload=summary, key="feedback_surfaces")

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


__all__ = [
    "append_feedback_loop_summary",
    "append_feedback_observability_summary",
    "append_ltm_explainability_summary",
    "append_preference_observability_summary",
]
