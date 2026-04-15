from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_metrics import (
    format_metric as _format_metric,
)
from ace_lite.benchmark.report_observability_governance import (
    append_decision_observability_summary as _append_decision_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_retrieval_control_plane_gate_summary as _append_retrieval_control_plane_gate_summary_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_wave1_context_governance_summary as _append_wave1_context_governance_summary_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_workload_taxonomy_summary as _append_workload_taxonomy_summary_impl,
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
    return _append_wave1_context_governance_summary_impl(lines, results)


def append_context_refine_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_context_refine_summary_impl(lines, results)


def append_retrieval_control_plane_gate_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_retrieval_control_plane_gate_summary_impl(lines, results)


def append_decision_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_decision_observability_summary_impl(lines, results)


def append_workload_taxonomy_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    return _append_workload_taxonomy_summary_impl(lines, results)


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
