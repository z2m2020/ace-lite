from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ace_lite.benchmark.report_cases import append_case_sections
from ace_lite.benchmark.report_metrics import (
    ALL_METRIC_ORDER,
    METRIC_ORDER,
    SLO_BUDGET_LIMIT_ORDER,
    SLO_SIGNAL_ORDER,
    STAGE_LATENCY_ORDER,
    format_metric as _format_metric,
    format_optional_metric as _format_optional_metric,
    normalize_metrics as _normalize_metrics,
)
from ace_lite.benchmark.report_summary import copy_optional_summary_sections


def _append_metrics_table(
    lines: list[str], title: str, metrics: dict[str, Any], *, signed: bool = False
) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for metric in METRIC_ORDER:
        lines.append(
            f"| {metric} | {_format_metric(metric, metrics.get(metric, 0.0), signed=signed)} |"
        )
    lines.append("")


def _append_plugin_policy_summary(lines: list[str], summary: dict[str, Any]) -> None:
    totals_raw = summary.get("totals")
    totals: dict[str, Any] = totals_raw if isinstance(totals_raw, dict) else {}

    per_case_raw = summary.get("per_case_mean")
    per_case: dict[str, Any] = per_case_raw if isinstance(per_case_raw, dict) else {}

    mode_distribution_raw = summary.get("mode_distribution")
    mode_distribution: dict[str, Any] = (
        mode_distribution_raw if isinstance(mode_distribution_raw, dict) else {}
    )

    allowlist_raw = summary.get("allowlist")
    allowlist: list[Any] = allowlist_raw if isinstance(allowlist_raw, list) else []

    by_stage_raw = summary.get("by_stage")
    by_stage: list[Any] = by_stage_raw if isinstance(by_stage_raw, list) else []

    by_stage_per_case_raw = summary.get("by_stage_per_case_mean")
    by_stage_per_case_mean: list[Any] = (
        by_stage_per_case_raw if isinstance(by_stage_per_case_raw, list) else []
    )

    lines.append("## Plugin Policy Summary")
    lines.append("")
    lines.append(f"- Mode: {summary.get('mode', '') or '(none)'}")
    if allowlist:
        lines.append(f"- Allowlist: {', '.join(str(item) for item in allowlist)}")
    else:
        lines.append("- Allowlist: (none)")
    if mode_distribution:
        formatted = ", ".join(
            f"{mode!s}={int(count)}"
            for mode, count in sorted(mode_distribution.items())
        )
        lines.append(f"- Mode distribution: {formatted}")
    lines.append("")

    lines.append("### Totals")
    lines.append("")
    lines.append("| Counter | Value |")
    lines.append("| --- | ---: |")
    for key in ("applied", "conflicts", "blocked", "warn", "remote_applied"):
        lines.append(f"| {key} | {int(totals.get(key, 0) or 0)} |")
    lines.append("")

    lines.append("### Per-case Mean")
    lines.append("")
    lines.append("| Counter | Value |")
    lines.append("| --- | ---: |")
    for key in ("applied", "conflicts", "blocked", "warn", "remote_applied"):
        lines.append(f"| {key} | {float(per_case.get(key, 0.0) or 0.0):.4f} |")
    lines.append("")

    if by_stage:
        lines.append("### By-stage Totals")
        lines.append("")
        lines.append(
            "| Stage | applied | conflicts | blocked | warn | remote_applied |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for item in by_stage:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "").strip() or "(unknown)"
            lines.append(
                "| "
                f"{stage} | {int(item.get('applied', 0) or 0)}"
                f" | {int(item.get('conflicts', 0) or 0)}"
                f" | {int(item.get('blocked', 0) or 0)}"
                f" | {int(item.get('warn', 0) or 0)}"
                f" | {int(item.get('remote_applied', 0) or 0)} |"
            )
        lines.append("")

    if by_stage_per_case_mean:
        lines.append("### By-stage Per-case Mean")
        lines.append("")
        lines.append(
            "| Stage | applied | conflicts | blocked | warn | remote_applied |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for item in by_stage_per_case_mean:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "").strip() or "(unknown)"
            lines.append(
                "| "
                f"{stage} | {float(item.get('applied', 0.0) or 0.0):.4f}"
                f" | {float(item.get('conflicts', 0.0) or 0.0):.4f}"
                f" | {float(item.get('blocked', 0.0) or 0.0):.4f}"
                f" | {float(item.get('warn', 0.0) or 0.0):.4f}"
                f" | {float(item.get('remote_applied', 0.0) or 0.0):.4f} |"
            )
        lines.append("")


def _append_task_success_summary(lines: list[str], summary: dict[str, Any]) -> None:
    lines.append("## Task Success Summary")
    lines.append("")


def _append_comparison_lane_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("comparison_lane_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    lanes_raw = summary.get("lanes")
    lanes: list[Any] = lanes_raw if isinstance(lanes_raw, list) else []
    if not lanes:
        return

    lines.append("## Comparison Lanes")
    lines.append("")
    lines.append(
        "- Labeled cases: {labeled} / {total}".format(
            labeled=int(summary.get("labeled_case_count", 0) or 0),
            total=int(summary.get("total_case_count", 0) or 0),
        )
    )
    lines.append("")
    lines.append(
        "| Lane | Cases | Task Success | Recall@K | Report-only | Filtered Cases | Filtered Count Mean | Filter Ratio Mean | Retained Hit | Improved | Conflict Mean |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for item in lanes:
        if not isinstance(item, dict):
            continue
        lane = str(item.get("comparison_lane") or "").strip() or "(none)"
        lines.append(
            "| "
            f"{lane} | {int(item.get('case_count', 0) or 0)}"
            f" | {float(item.get('task_success_rate', 0.0) or 0.0):.4f}"
            f" | {float(item.get('recall_at_k', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_report_only_ratio', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_filtered_case_rate', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_filtered_count_mean', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_filter_ratio_mean', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_expected_retained_hit_rate_mean', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_report_only_improved_rate', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_pairwise_conflict_count_mean', 0.0) or 0.0):.4f} |"
        )
    lines.append("")


def _append_runtime_stats_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("runtime_stats_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    latest_raw = summary.get("latest_match")
    latest: dict[str, Any] = latest_raw if isinstance(latest_raw, dict) else {}
    scopes_raw = summary.get("summary")
    scopes: dict[str, Any] = scopes_raw if isinstance(scopes_raw, dict) else {}
    preference_snapshot_raw = summary.get("preference_snapshot")
    preference_snapshot: dict[str, Any] = (
        preference_snapshot_raw
        if isinstance(preference_snapshot_raw, dict)
        else {}
    )

    lines.append("## Runtime Stats Summary")
    lines.append("")
    lines.append(f"- DB path: {summary.get('db_path', '')}")
    if latest:
        lines.append(f"- Latest session: {latest.get('session_id', '')}")
        lines.append(f"- Latest repo: {latest.get('repo_key', '')}")
        profile = str(latest.get("profile_key") or "").strip()
        lines.append(f"- Latest profile: {profile or '(none)'}")
        lines.append(f"- Latest finished_at: {latest.get('finished_at', '')}")
    else:
        lines.append("- Latest match: (none)")
    lines.append("")
    lines.append("| Scope | Invocations | Success | Degraded | Failed | Avg Latency ms |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for scope_name in ("session", "all_time", "repo", "profile", "repo_profile"):
        item_raw = scopes.get(scope_name)
        item: dict[str, Any] = item_raw if isinstance(item_raw, dict) else {}
        if not item:
            continue
        counters = item.get("counters", {}) if isinstance(item.get("counters"), dict) else {}
        latency = item.get("latency", {}) if isinstance(item.get("latency"), dict) else {}
        lines.append(
            "| "
            f"{scope_name} | {int(counters.get('invocation_count', 0) or 0)}"
            f" | {int(counters.get('success_count', 0) or 0)}"
            f" | {int(counters.get('degraded_count', 0) or 0)}"
            f" | {int(counters.get('failure_count', 0) or 0)}"
            f" | {float(latency.get('latency_ms_avg', 0.0) or 0.0):.2f} |"
        )
    lines.append("")
    if preference_snapshot:
        lines.append("### Preference Snapshot")
        lines.append("")
        preference_summary_raw = preference_snapshot.get(
            "preference_observability_summary"
        )
        preference_summary: dict[str, Any] = (
            preference_summary_raw
            if isinstance(preference_summary_raw, dict)
            else {}
        )
        if preference_summary:
            lines.append(
                "- Preference observed cases: {count}/{total} ({rate:.4f})".format(
                    count=int(preference_summary.get("observed_case_count", 0) or 0),
                    total=int(preference_summary.get("case_count", 0) or 0),
                    rate=float(preference_summary.get("observed_case_rate", 0.0) or 0.0),
                )
            )
            lines.append(
                "- Preference notes-hit mean: {value:.4f}".format(
                    value=float(
                        preference_summary.get("notes_hit_ratio_mean", 0.0) or 0.0
                    )
                )
            )
            lines.append(
                "- Preference profile-selected mean: {value:.4f}".format(
                    value=float(
                        preference_summary.get("profile_selected_count_mean", 0.0)
                        or 0.0
                    )
                )
            )
        feedback_summary_raw = preference_snapshot.get("feedback_observability_summary")
        feedback_summary: dict[str, Any] = (
            feedback_summary_raw if isinstance(feedback_summary_raw, dict) else {}
        )
        if feedback_summary:
            lines.append(
                "- Feedback boosted cases: {count}/{total} ({rate:.4f})".format(
                    count=int(feedback_summary.get("boosted_case_count", 0) or 0),
                    total=int(feedback_summary.get("case_count", 0) or 0),
                    rate=float(feedback_summary.get("boosted_case_rate", 0.0) or 0.0),
                )
            )
            lines.append(
                "- Feedback matched-event mean: {value:.4f}".format(
                    value=float(
                        feedback_summary.get("matched_event_count_mean", 0.0) or 0.0
                    )
                )
            )
            lines.append(
                "- Feedback boosted-candidate mean: {value:.4f}".format(
                    value=float(
                        feedback_summary.get("boosted_candidate_count_mean", 0.0)
                        or 0.0
                    )
                )
            )
        durable_summary_raw = preference_snapshot.get(
            "durable_preference_capture_summary"
        )
        durable_summary: dict[str, Any] = (
            durable_summary_raw if isinstance(durable_summary_raw, dict) else {}
        )
        if durable_summary:
            lines.append(
                "- Durable preference store: {path}".format(
                    path=str(durable_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable preference user_id: {durable_user}")
            lines.append(
                "- Durable preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_summary.get("distinct_target_path_count", 0) or 0
                    ),
                    weight=float(durable_summary.get("total_weight", 0.0) or 0.0),
                )
            )
            latest_created_at = str(durable_summary.get("latest_created_at") or "").strip()
            if latest_created_at:
                lines.append(
                    "- Durable preference latest_created_at: {value}".format(
                        value=latest_created_at
                )
            )
            lines.append("")
        durable_scoped_summary_raw = preference_snapshot.get(
            "durable_preference_capture_scoped_summary"
        )
        durable_scoped_summary: dict[str, Any] = (
            durable_scoped_summary_raw
            if isinstance(durable_scoped_summary_raw, dict)
            else {}
        )
        if durable_scoped_summary:
            lines.append(
                "- Durable preference scoped store: {path}".format(
                    path=str(durable_scoped_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_scoped_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable preference scoped user_id: {durable_user}")
            durable_profile = str(durable_scoped_summary.get("profile_key") or "").strip()
            if durable_profile:
                lines.append(
                    f"- Durable preference scoped profile_key: {durable_profile}"
                )
            lines.append(
                "- Durable preference scoped events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_scoped_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_scoped_summary.get("distinct_target_path_count", 0)
                        or 0
                    ),
                    weight=float(
                        durable_scoped_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_scoped_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    "- Durable preference scoped latest_created_at: {value}".format(
                        value=latest_created_at
                    )
                )
            lines.append("")
        durable_retrieval_summary_raw = preference_snapshot.get(
            "durable_retrieval_preference_summary"
        )
        durable_retrieval_summary: dict[str, Any] = (
            durable_retrieval_summary_raw
            if isinstance(durable_retrieval_summary_raw, dict)
            else {}
        )
        if durable_retrieval_summary:
            lines.append(
                "- Durable retrieval-preference store: {path}".format(
                    path=str(durable_retrieval_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_retrieval_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable retrieval-preference user_id: {durable_user}")
            lines.append(
                "- Durable retrieval-preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_retrieval_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_retrieval_summary.get("distinct_target_path_count", 0)
                        or 0
                    ),
                    weight=float(
                        durable_retrieval_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_retrieval_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    "- Durable retrieval-preference latest_created_at: {value}".format(
                        value=latest_created_at
                    )
                )
            lines.append("")
        durable_packing_summary_raw = preference_snapshot.get(
            "durable_packing_preference_summary"
        )
        durable_packing_summary: dict[str, Any] = (
            durable_packing_summary_raw
            if isinstance(durable_packing_summary_raw, dict)
            else {}
        )
        if durable_packing_summary:
            lines.append(
                "- Durable packing-preference store: {path}".format(
                    path=str(durable_packing_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_packing_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable packing-preference user_id: {durable_user}")
            lines.append(
                "- Durable packing-preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_packing_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_packing_summary.get("distinct_target_path_count", 0)
                        or 0
                    ),
                    weight=float(
                        durable_packing_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_packing_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    "- Durable packing-preference latest_created_at: {value}".format(
                        value=latest_created_at
                    )
                )
            lines.append("")
        durable_validation_summary_raw = preference_snapshot.get(
            "durable_validation_preference_summary"
        )
        durable_validation_summary: dict[str, Any] = (
            durable_validation_summary_raw
            if isinstance(durable_validation_summary_raw, dict)
            else {}
        )
        if durable_validation_summary:
            lines.append(
                "- Durable validation-preference store: {path}".format(
                    path=str(durable_validation_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_validation_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable validation-preference user_id: {durable_user}")
            lines.append(
                "- Durable validation-preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_validation_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_validation_summary.get(
                            "distinct_target_path_count", 0
                        )
                        or 0
                    ),
                    weight=float(
                        durable_validation_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_validation_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    "- Durable validation-preference latest_created_at: {value}".format(
                        value=latest_created_at
                    )
                )
            lines.append("")
        lines.append("")


def _append_evidence_insufficiency_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("evidence_insufficiency_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    reasons_raw = summary.get("reasons")
    reasons: dict[str, Any] = reasons_raw if isinstance(reasons_raw, dict) else {}
    signals_raw = summary.get("signals")
    signals: dict[str, Any] = signals_raw if isinstance(signals_raw, dict) else {}
    applicable_case_count = int(summary.get("applicable_case_count", 0) or 0)

    lines.append("## Evidence Insufficiency Summary")
    lines.append("")

    lines.append(
        "- Applicable failing positive cases: {applicable}".format(
            applicable=applicable_case_count
        )
    )
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
    else:
        lines.append("| Signal | Count |")
        lines.append("| --- | ---: |")
        for name, count in sorted(
            signals.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
        ):
            lines.append(f"| {name} | {int(count or 0)} |")
        lines.append("")


def _append_retrieval_context_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("retrieval_context_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Retrieval Context Observability Summary")
    lines.append("")
    lines.append(
        "- Available cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Pool-available cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("pool_available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("pool_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Parent-symbol cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("parent_symbol_available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("parent_symbol_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Reference-hint cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("reference_hint_available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("reference_hint_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| coverage_ratio_mean | {value:.4f} |".format(
            value=float(summary.get("coverage_ratio_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| parent_symbol_chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("parent_symbol_chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| parent_symbol_coverage_ratio_mean | {value:.4f} |".format(
            value=float(
                summary.get("parent_symbol_coverage_ratio_mean", 0.0) or 0.0
            )
        )
    )
    lines.append(
        "| reference_hint_chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("reference_hint_chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| reference_hint_coverage_ratio_mean | {value:.4f} |".format(
            value=float(
                summary.get("reference_hint_coverage_ratio_mean", 0.0) or 0.0
            )
        )
    )
    lines.append(
        "| pool_chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("pool_chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| pool_coverage_ratio_mean | {value:.4f} |".format(
            value=float(summary.get("pool_coverage_ratio_mean", 0.0) or 0.0)
        )
    )
    lines.append("")


def _append_preference_observability_summary(
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


def _append_feedback_observability_summary(
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


def _append_feedback_loop_summary(lines: list[str], results: dict[str, Any]) -> None:
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
        "- Dev-feedback resolution cases: {count} resolved={resolved} rate={rate:.4f}".format(
            count=int(summary.get("dev_feedback_resolution_case_count", 0) or 0),
            resolved=int(summary.get("dev_feedback_resolved_case_count", 0) or 0),
            rate=float(summary.get("dev_feedback_resolution_rate", 0.0) or 0.0),
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
        "| dev_feedback_resolution_rate | {value:.4f} |".format(
            value=float(summary.get("dev_feedback_resolution_rate", 0.0) or 0.0)
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


def _append_adaptive_router_observability_summary(
    lines: list[str],
    results: dict[str, Any],
) -> None:
    summary_raw = results.get("adaptive_router_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    enabled_case_count = int(summary.get("enabled_case_count", 0) or 0)
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


def _append_reward_log_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("reward_log_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Reward Log Summary")
    lines.append("")
    lines.append(f"- Status: {str(summary.get('status') or 'disabled')}")
    lines.append(f"- Enabled: {bool(summary.get('enabled', False))}")
    lines.append(f"- Active: {bool(summary.get('active', False))}")
    lines.append(f"- Path: {str(summary.get('path') or '(none)')}")
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


def _append_decision_observability_summary(
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


def _append_chunk_stage_miss_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("chunk_stage_miss_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    labels_raw = summary.get("labels")
    labels: dict[str, Any] = labels_raw if isinstance(labels_raw, dict) else {}
    oracle_case_count = int(summary.get("oracle_case_count", 0) or 0)

    lines.append("## Chunk Stage Miss Summary")
    lines.append("")
    lines.append(f"- Oracle-tagged cases: {oracle_case_count}")
    lines.append(
        "- Classified stage-miss cases: {count} ({rate})".format(
            count=int(summary.get("classified_case_count", 0) or 0),
            rate=f"{float(summary.get('classified_case_rate', 0.0) or 0.0):.4f}",
        )
    )
    lines.append("")
    lines.append("### Labels")
    lines.append("")
    if not labels:
        lines.append("- None")
        lines.append("")
        return

    lines.append("| Label | Count | Rate |")
    lines.append("| --- | ---: | ---: |")
    for name, count in sorted(
        labels.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
    ):
        rate = (
            float(count or 0) / float(oracle_case_count) if oracle_case_count > 0 else 0.0
        )
        lines.append(f"| {name} | {int(count or 0)} | {rate:.4f} |")
    lines.append("")


def _format_decision_event(event: dict[str, Any]) -> str:
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


def _append_stage_latency_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("stage_latency_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    baseline_metrics_raw = results.get("baseline_metrics")
    baseline_metrics = (
        _normalize_metrics(baseline_metrics_raw)
        if isinstance(baseline_metrics_raw, dict)
        else {}
    )
    delta_raw = results.get("delta")
    delta = _normalize_metrics(delta_raw) if isinstance(delta_raw, dict) else {}

    lines.append("## Stage Latency Summary")
    lines.append("")
    lines.append("| Stage | Mean (ms) | P95 (ms) | Baseline P95 | Delta P95 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")

    for stage, metric_name in STAGE_LATENCY_ORDER:
        stage_summary_raw = summary.get(stage)
        stage_summary = (
            stage_summary_raw if isinstance(stage_summary_raw, dict) else {}
        )
        lines.append(
            "| {stage} | {mean} | {p95} | {baseline} | {delta} |".format(
                stage=stage,
                mean=_format_metric("latency_p95_ms", stage_summary.get("mean_ms", 0.0)),
                p95=_format_metric("latency_p95_ms", stage_summary.get("p95_ms", 0.0)),
                baseline=_format_optional_metric(
                    metric_name, baseline_metrics.get(metric_name)
                ),
                delta=_format_optional_metric(metric_name, delta.get(metric_name), signed=True),
            )
        )

    total_raw = summary.get("total")
    total = total_raw if isinstance(total_raw, dict) else {}
    lines.append(
        "| total | {mean} | {p95} | {baseline} | {delta} |".format(
            mean=_format_metric("latency_p95_ms", total.get("mean_ms", 0.0)),
            p95=_format_metric("latency_p95_ms", total.get("p95_ms", 0.0)),
            baseline=_format_optional_metric(
                "latency_p95_ms", baseline_metrics.get("latency_p95_ms")
            ),
            delta=_format_optional_metric(
                "latency_p95_ms", delta.get("latency_p95_ms"), signed=True
            ),
        )
    )
    lines.append("")


def _append_slo_budget_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("slo_budget_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    metrics = _normalize_metrics(results.get("metrics"))
    baseline_metrics_raw = results.get("baseline_metrics")
    baseline_metrics = (
        _normalize_metrics(baseline_metrics_raw)
        if isinstance(baseline_metrics_raw, dict)
        else {}
    )
    delta_raw = results.get("delta")
    delta = _normalize_metrics(delta_raw) if isinstance(delta_raw, dict) else {}

    lines.append("## SLO Budget Summary")
    lines.append("")
    lines.append(
        "- Downgrade cases: {count}/{case_count} ({rate})".format(
            count=int(summary.get("downgrade_case_count", 0) or 0),
            case_count=int(summary.get("case_count", 0) or 0),
            rate=_format_metric(
                "slo_downgrade_case_rate",
                summary.get("downgrade_case_rate", 0.0),
            ),
        )
    )
    if baseline_metrics:
        lines.append(
            "- Downgrade delta vs baseline: {delta}".format(
                delta=_format_optional_metric(
                    "slo_downgrade_case_rate",
                    delta.get("slo_downgrade_case_rate"),
                    signed=True,
                )
            )
        )
    lines.append("")

    budget_limits_raw = summary.get("budget_limits_ms")
    budget_limits = (
        budget_limits_raw if isinstance(budget_limits_raw, dict) else {}
    )
    lines.append("### Budget Limits")
    lines.append("")
    lines.append("| Budget | Mean (ms) | Baseline | Delta |")
    lines.append("| --- | ---: | ---: | ---: |")
    for metric_name in SLO_BUDGET_LIMIT_ORDER:
        lines.append(
            "| {name} | {current} | {baseline} | {delta} |".format(
                name=metric_name,
                current=_format_metric(metric_name, budget_limits.get(metric_name, 0.0)),
                baseline=_format_optional_metric(
                    metric_name, baseline_metrics.get(metric_name)
                ),
                delta=_format_optional_metric(metric_name, delta.get(metric_name), signed=True),
            )
        )
    lines.append("")

    signals_raw = summary.get("signals")
    signals = signals_raw if isinstance(signals_raw, dict) else {}
    lines.append("### Downgrade Signals")
    lines.append("")
    lines.append("| Signal | Count | Current Rate | Baseline | Delta |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for metric_name in SLO_SIGNAL_ORDER:
        signal_raw = signals.get(metric_name)
        signal = signal_raw if isinstance(signal_raw, dict) else {}
        count = int(signal.get("count", 0) or 0)
        current_rate = (
            metrics.get(metric_name, signal.get("rate", 0.0))
            if metric_name != "slo_downgrade_case_rate"
            else summary.get("downgrade_case_rate", 0.0)
        )
        lines.append(
            "| {name} | {count} | {current} | {baseline} | {delta} |".format(
                name=metric_name,
                count=count if metric_name != "slo_downgrade_case_rate" else int(
                    summary.get("downgrade_case_count", 0) or 0
                ),
                current=_format_metric(metric_name, current_rate),
                baseline=_format_optional_metric(
                    metric_name, baseline_metrics.get(metric_name)
                ),
                delta=_format_optional_metric(metric_name, delta.get(metric_name), signed=True),
            )
        )
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | ---: |")
    for key in (
        "case_count",
        "positive_case_count",
        "negative_control_case_count",
        "task_success_rate",
        "positive_task_success_rate",
        "negative_control_task_success_rate",
        "retrieval_task_gap_count",
        "retrieval_task_gap_rate",
    ):
        value = summary.get(key, 0.0)
        if key.endswith("_count"):
            lines.append(f"| {key} | {int(value or 0)} |")
        else:
            lines.append(f"| {key} | {float(value or 0.0):.4f} |")
    lines.append("")


def _append_retrieval_task_gap_cases(lines: list[str], cases: list[Any]) -> None:
    gap_cases: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        recall_hit = float(item.get("recall_hit", 0.0) or 0.0)
        task_success_hit = float(item.get("task_success_hit", 0.0) or 0.0)
        if recall_hit <= 0.0 or task_success_hit > 0.0:
            continue
        gap_cases.append(item)

    lines.append("## Retrieval-to-Task Gaps")
    lines.append("")
    if not gap_cases:
        lines.append("- None")
        lines.append("")
        return

    for case in gap_cases:
        lines.append(f"### {case.get('case_id', 'unknown')}")
        lines.append(f"- Query: {case.get('query', '')}")
        lines.append(f"- task_success_mode: {case.get('task_success_mode', 'positive')}")
        lines.append(f"- first_hit_rank: {case.get('first_hit_rank', '(none)')}")
        lines.append(f"- precision_at_k: {float(case.get('precision_at_k', 0.0)):.4f}")
        lines.append(f"- validation_test_count: {int(case.get('validation_test_count', 0) or 0)}")
        failed_checks = case.get("task_success_failed_checks", [])
        if isinstance(failed_checks, list) and failed_checks:
            lines.append(
                "- task_success_failed_checks: "
                + ", ".join(str(item) for item in failed_checks if str(item).strip())
            )
        reason = str(case.get("evidence_insufficiency_reason") or "").strip()
        if reason:
            lines.append(f"- evidence_insufficiency_reason: {reason}")
        signals = case.get("evidence_insufficiency_signals", [])
        if isinstance(signals, list) and signals:
            lines.append(
                "- evidence_insufficiency_signals: "
                + ", ".join(str(item) for item in signals if str(item).strip())
            )
        decision_trace = case.get("decision_trace", [])
        if isinstance(decision_trace, list):
            for event in decision_trace:
                if isinstance(event, dict):
                    lines.append(f"- decision_event: {_format_decision_event(event)}")
        lines.append("")


def build_results_summary(results: dict[str, Any]) -> dict[str, Any]:
    metrics = _normalize_metrics(results.get("metrics"))

    regression_raw = results.get("regression")
    regression: dict[str, Any] = (
        regression_raw if isinstance(regression_raw, dict) else {}
    )

    failed_checks_raw = regression.get("failed_checks")
    failed_checks = (
        [str(item) for item in failed_checks_raw]
        if isinstance(failed_checks_raw, list)
        else []
    )

    metric_snapshot: dict[str, float] = {
        key: float(metrics.get(key, 0.0) or 0.0)
        for key in ALL_METRIC_ORDER
    }

    summary: dict[str, Any] = {
        "generated_at": results.get("generated_at"),
        "repo": results.get("repo", ""),
        "root": results.get("root", ""),
        "case_count": int(results.get("case_count", 0) or 0),
        "warmup_runs": int(results.get("warmup_runs", 0) or 0),
        "threshold_profile": results.get("threshold_profile"),
        "regressed": bool(regression.get("regressed", False)),
        "failed_checks": failed_checks,
        "metrics": metric_snapshot,
    }
    summary.update(copy_optional_summary_sections(results=results))

    return summary


def build_report_markdown(results: dict[str, Any]) -> str:
    metrics = _normalize_metrics(results.get("metrics"))
    cases = results.get("cases", [])
    policy_profiles_raw = results.get("policy_profile_distribution")
    policy_profiles: dict[str, Any] = (
        policy_profiles_raw if isinstance(policy_profiles_raw, dict) else {}
    )

    lines: list[str] = []
    lines.append("# ACE-Lite Benchmark Report")
    lines.append("")
    lines.append(f"- Generated: {results.get('generated_at', '')}")
    lines.append(f"- Repo: {results.get('repo', '')}")
    lines.append(f"- Case count: {results.get('case_count', 0)}")
    warmup_runs = int(results.get("warmup_runs", 0) or 0)
    if warmup_runs > 0:
        lines.append(f"- Warmup runs: {warmup_runs}")
    include_plan_payload = bool(results.get("include_plan_payload", True))
    if not include_plan_payload:
        lines.append("- Include plans: false")
    include_case_details = bool(results.get("include_case_details", True))
    if not include_case_details:
        lines.append("- Include case details: false")
    if results.get("threshold_profile"):
        lines.append(f"- Threshold profile: {results.get('threshold_profile')}")
    lines.append("")

    _append_metrics_table(lines, "Metrics", metrics)

    if policy_profiles:
        lines.append("## Policy Profile Distribution")
        lines.append("")
        for name, count in sorted(
            policy_profiles.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
        ):
            label = str(name).strip() or "(unknown)"
            lines.append(f"- {label}: {int(count or 0)}")
        lines.append("")

    _append_adaptive_router_observability_summary(lines, results)
    _append_reward_log_summary(lines, results)
    _append_runtime_stats_summary(lines, results)

    baseline_metrics_raw = results.get("baseline_metrics")
    baseline_metrics = (
        _normalize_metrics(baseline_metrics_raw)
        if isinstance(baseline_metrics_raw, dict)
        else None
    )
    if isinstance(baseline_metrics, dict):
        _append_metrics_table(lines, "Baseline", baseline_metrics)

    delta_raw = results.get("delta")
    delta = _normalize_metrics(delta_raw) if isinstance(delta_raw, dict) else None
    if isinstance(delta, dict):
        _append_metrics_table(lines, "Delta vs Baseline", delta, signed=True)

    task_success_summary = results.get("task_success_summary")
    if isinstance(task_success_summary, dict):
        _append_task_success_summary(lines, task_success_summary)

    _append_comparison_lane_summary(lines, results)
    _append_evidence_insufficiency_summary(lines, results)
    _append_feedback_loop_summary(lines, results)
    _append_feedback_observability_summary(lines, results)
    _append_preference_observability_summary(lines, results)
    _append_retrieval_context_observability_summary(lines, results)
    _append_chunk_stage_miss_summary(lines, results)
    _append_decision_observability_summary(lines, results)
    _append_stage_latency_summary(lines, results)
    _append_slo_budget_summary(lines, results)

    _append_retrieval_task_gap_cases(lines, cases if isinstance(cases, list) else [])

    plugin_policy_summary = results.get("plugin_policy_summary")
    if isinstance(plugin_policy_summary, dict):
        _append_plugin_policy_summary(lines, plugin_policy_summary)

    regression_thresholds = results.get("regression_thresholds")
    if isinstance(regression_thresholds, dict):
        lines.append("## Regression Thresholds")
        lines.append("")
        lines.append("| Threshold | Value |")
        lines.append("| --- | ---: |")
        for key, value in regression_thresholds.items():
            lines.append(f"| {key} | {float(value):.4f} |")
        lines.append("")

    regression = results.get("regression")
    if isinstance(regression, dict):
        failed_checks = regression.get("failed_checks", [])
        failed_thresholds = regression.get("failed_thresholds", [])
        lines.append("## Regression")
        lines.append("")
        lines.append(f"- regressed: {bool(regression.get('regressed', False))}")
        lines.append(
            f"- failed_checks: {', '.join(str(item) for item in failed_checks) if failed_checks else '(none)'}"
        )
        if isinstance(failed_thresholds, list) and failed_thresholds:
            lines.append("- failed_thresholds:")
            for item in failed_thresholds:
                if not isinstance(item, dict):
                    continue
                metric = str(item.get("metric", ""))
                operator = str(item.get("operator", ""))
                current = float(item.get("current", 0.0))
                threshold = float(item.get("threshold", 0.0))
                lines.append(f"  - {metric}: {current:.4f} {operator} {threshold:.4f}")
        lines.append("")

    lines.append("## Cases")
    lines.append("")

    append_case_sections(
        lines,
        cases=cases if isinstance(cases, list) else [],
        format_decision_event=_format_decision_event,
    )

    return "\n".join(lines).strip() + "\n"


def write_results(results: dict[str, Any], *, output_dir: str | Path) -> dict[str, str]:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)

    results_path = base / "results.json"
    report_path = base / "report.md"
    summary_path = base / "summary.json"

    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(build_report_markdown(results), encoding="utf-8")
    summary_path.write_text(
        json.dumps(build_results_summary(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "results_json": str(results_path),
        "report_md": str(report_path),
        "summary_json": str(summary_path),
    }


def write_report_from_json(
    *, input_path: str | Path, output_path: str | Path | None = None
) -> str:
    source = Path(input_path)
    results = json.loads(source.read_text(encoding="utf-8"))

    target = Path(output_path) if output_path else source.with_name("report.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_report_markdown(results), encoding="utf-8")
    return str(target)


__all__ = [
    "build_report_markdown",
    "build_results_summary",
    "write_report_from_json",
    "write_results",
]
