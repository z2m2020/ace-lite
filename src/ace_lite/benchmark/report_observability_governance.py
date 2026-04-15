from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_summary import get_summary_mapping


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
            status="pass" if bool(summary.get("latency_p95_ms_passed", False)) else "fail",
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


__all__ = [
    "append_decision_observability_summary",
    "append_retrieval_control_plane_gate_summary",
    "append_wave1_context_governance_summary",
    "append_workload_taxonomy_summary",
]
