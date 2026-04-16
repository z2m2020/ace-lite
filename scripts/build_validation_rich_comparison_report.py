from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark.report_script_support import (
    build_validation_rich_support_bundle,
    load_report_json,
    resolve_report_path,
)
from ace_lite.benchmark.report_script_support import (
    safe_float as _safe_float,
)
from ace_lite.benchmark.report_warning_support import join_string_list, normalize_string_list

METRIC_NAMES = (
    "task_success_rate",
    "precision_at_k",
    "noise_rate",
    "latency_p95_ms",
    "validation_test_count",
    "evidence_insufficient_rate",
    "missing_validation_rate",
)


def _extract_summary(*, label: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    metrics_raw = payload.get("metrics")
    metrics_input = metrics_raw if isinstance(metrics_raw, dict) else {}
    failed_checks = normalize_string_list(payload.get("failed_checks"))
    return {
        "label": label,
        "path": str(path),
        "loaded": bool(payload),
        "generated_at": str(payload.get("generated_at", "") or ""),
        "repo": str(payload.get("repo", "") or ""),
        "case_count": int(payload.get("case_count", 0) or 0),
        "regressed": bool(payload.get("regressed", False)),
        "failed_checks": failed_checks,
        "metrics": {name: _safe_float(metrics_input.get(name), 0.0) for name in METRIC_NAMES},
        **build_validation_rich_support_bundle(path),
    }


def _build_delta(*, left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, float]]:
    left_metrics_raw = left.get("metrics")
    left_metrics = left_metrics_raw if isinstance(left_metrics_raw, dict) else {}
    right_metrics_raw = right.get("metrics")
    right_metrics = right_metrics_raw if isinstance(right_metrics_raw, dict) else {}
    return {
        metric_name: {
            "left": _safe_float(left_metrics.get(metric_name), 0.0),
            "right": _safe_float(right_metrics.get(metric_name), 0.0),
            "delta": _safe_float(right_metrics.get(metric_name), 0.0)
            - _safe_float(left_metrics.get(metric_name), 0.0),
        }
        for metric_name in METRIC_NAMES
    }


def _render_markdown(*, payload: dict[str, Any]) -> str:
    baseline_raw = payload.get("baseline")
    baseline = baseline_raw if isinstance(baseline_raw, dict) else {}
    current_raw = payload.get("current")
    current = current_raw if isinstance(current_raw, dict) else {}
    tuned_raw = payload.get("tuned")
    tuned = tuned_raw if isinstance(tuned_raw, dict) else {}
    comparisons_raw = payload.get("comparisons")
    comparisons = comparisons_raw if isinstance(comparisons_raw, dict) else {}

    lines = [
        "# Validation-Rich Comparison Report",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Report only: {bool(payload.get('report_only', True))}",
        "",
        "## Inputs",
        "",
        "| Label | Loaded | Regressed | Case Count | Failed Checks |",
        "| --- | :---: | :---: | ---: | --- |",
    ]
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {label} | {loaded} | {regressed} | {case_count} | {failed_checks} |".format(
                label=str(row.get("label", "")),
                loaded="✅" if bool(row.get("loaded", False)) else "❌",
                regressed="✅" if bool(row.get("regressed", False)) else "❌",
                case_count=int(row.get("case_count", 0) or 0),
                failed_checks=join_string_list(row.get("failed_checks", [])),
            )
        )

    lines.extend(["", "## Metrics", ""])
    lines.append("| Metric | Baseline | Current | Tuned |")
    lines.append("| --- | ---: | ---: | ---: |")
    baseline_metrics_raw = baseline.get("metrics")
    baseline_metrics = baseline_metrics_raw if isinstance(baseline_metrics_raw, dict) else {}
    current_metrics_raw = current.get("metrics")
    current_metrics = current_metrics_raw if isinstance(current_metrics_raw, dict) else {}
    tuned_metrics_raw = tuned.get("metrics")
    tuned_metrics = tuned_metrics_raw if isinstance(tuned_metrics_raw, dict) else {}
    for metric_name in METRIC_NAMES:
        lines.append(
            f"| {metric_name} | {_safe_float(baseline_metrics.get(metric_name), 0.0):.4f} | {_safe_float(current_metrics.get(metric_name), 0.0):.4f} | {_safe_float(tuned_metrics.get(metric_name), 0.0):.4f} |"
        )

    for name in ("baseline_vs_current", "current_vs_tuned", "baseline_vs_tuned"):
        delta_raw = comparisons.get(name)
        delta = delta_raw if isinstance(delta_raw, dict) else {}
        lines.extend(["", f"## {name}", ""])
        lines.append("| Metric | Left | Right | Delta |")
        lines.append("| --- | ---: | ---: | ---: |")
        for metric_name in METRIC_NAMES:
            row_raw = delta.get(metric_name)
            row = row_raw if isinstance(row_raw, dict) else {}
            lines.append(
                "| {metric} | {left:.4f} | {right:.4f} | {delta:+.4f} |".format(
                    metric=metric_name,
                    left=_safe_float(row.get("left"), 0.0),
                    right=_safe_float(row.get("right"), 0.0),
                    delta=_safe_float(row.get("delta"), 0.0),
                )
            )

    lines.extend(["", "## Q2 Retrieval Control Plane Gate", ""])
    lines.append(
        "| Label | Gate Passed | Regression Evaluated | Regression Detected | Shadow Coverage | Risk Upgrade Gain | Latency P95 ms | Failed Checks |"
    )
    lines.append("| --- | :---: | :---: | :---: | ---: | ---: | ---: | --- |")
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        gate_raw = row.get("retrieval_control_plane_gate_summary")
        gate = gate_raw if isinstance(gate_raw, dict) else {}
        failed_checks = join_string_list(gate.get("failed_checks", []))
        lines.append(
            "| {label} | {gate_passed} | {regression_evaluated} | {regression_detected} | {shadow:.4f} | {gain:.4f} | {latency:.2f} | {failed_checks} |".format(
                label=str(row.get("label", "")),
                gate_passed="yes" if bool(gate.get("gate_passed", False)) else "no",
                regression_evaluated=(
                    "yes" if bool(gate.get("regression_evaluated", False)) else "no"
                ),
                regression_detected=(
                    "yes" if bool(gate.get("benchmark_regression_detected", False)) else "no"
                ),
                shadow=_safe_float(gate.get("adaptive_router_shadow_coverage", 0.0), 0.0),
                gain=_safe_float(gate.get("risk_upgrade_precision_gain", 0.0), 0.0),
                latency=_safe_float(gate.get("latency_p95_ms", 0.0), 0.0),
                failed_checks=failed_checks,
            )
        )

    lines.extend(["", "## Q3 Retrieval Frontier Gate", ""])
    lines.append(
        "| Label | Gate Passed | Deep Symbol Recall | Native SCIP Loaded | Precision at k | Noise Rate | Failed Checks |"
    )
    lines.append("| --- | :---: | ---: | ---: | ---: | ---: | --- |")
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        frontier_gate_raw = row.get("retrieval_frontier_gate_summary")
        frontier_gate = frontier_gate_raw if isinstance(frontier_gate_raw, dict) else {}
        frontier_failed_checks = join_string_list(frontier_gate.get("failed_checks", []))
        lines.append(
            "| {label} | {gate_passed} | {recall:.4f} | {native_scip:.4f} | {precision:.4f} | {noise:.4f} | {failed_checks} |".format(
                label=str(row.get("label", "")),
                gate_passed=("yes" if bool(frontier_gate.get("gate_passed", False)) else "no"),
                recall=_safe_float(frontier_gate.get("deep_symbol_case_recall", 0.0), 0.0),
                native_scip=_safe_float(frontier_gate.get("native_scip_loaded_rate", 0.0), 0.0),
                precision=_safe_float(frontier_gate.get("precision_at_k", 0.0), 0.0),
                noise=_safe_float(frontier_gate.get("noise_rate", 0.0), 0.0),
                failed_checks=frontier_failed_checks,
            )
        )

    lines.extend(["", "## Q3 Frontier Evidence", ""])
    lines.append(
        "| Label | Deep Symbol Cases | Deep Symbol Recall | Native SCIP Loaded | Document Mean | Definition Mean | Reference Mean | Symbol Definition Mean |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        deep_symbol_raw = row.get("deep_symbol_summary")
        deep_symbol = deep_symbol_raw if isinstance(deep_symbol_raw, dict) else {}
        native_scip_raw = row.get("native_scip_summary")
        native_scip = native_scip_raw if isinstance(native_scip_raw, dict) else {}
        lines.append(
            "| {label} | {case_count:.4f} | {recall:.4f} | {loaded:.4f} | {document:.4f} | {definition:.4f} | {reference:.4f} | {symbol:.4f} |".format(
                label=str(row.get("label", "")),
                case_count=_safe_float(deep_symbol.get("case_count", 0.0), 0.0),
                recall=_safe_float(deep_symbol.get("recall", 0.0), 0.0),
                loaded=_safe_float(native_scip.get("loaded_rate", 0.0), 0.0),
                document=_safe_float(native_scip.get("document_count_mean", 0.0), 0.0),
                definition=_safe_float(
                    native_scip.get("definition_occurrence_count_mean", 0.0), 0.0
                ),
                reference=_safe_float(native_scip.get("reference_occurrence_count_mean", 0.0), 0.0),
                symbol=_safe_float(native_scip.get("symbol_definition_count_mean", 0.0), 0.0),
            )
        )

    lines.extend(["", "## Q4 Validation Probe Summary", ""])
    lines.append(
        "| Label | Validation Test Count | Probe Enabled Ratio | Probe Executed Count Mean | Probe Failure Rate |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        validation_probe_raw = row.get("validation_probe_summary")
        validation_probe = validation_probe_raw if isinstance(validation_probe_raw, dict) else {}
        lines.append(
            "| {label} | {validation_test_count:.4f} | {probe_enabled_ratio:.4f} | {probe_executed_count_mean:.4f} | {probe_failure_rate:.4f} |".format(
                label=str(row.get("label", "")),
                validation_test_count=_safe_float(
                    validation_probe.get("validation_test_count", 0.0), 0.0
                ),
                probe_enabled_ratio=_safe_float(
                    validation_probe.get("probe_enabled_ratio", 0.0), 0.0
                ),
                probe_executed_count_mean=_safe_float(
                    validation_probe.get("probe_executed_count_mean", 0.0), 0.0
                ),
                probe_failure_rate=_safe_float(
                    validation_probe.get("probe_failure_rate", 0.0), 0.0
                ),
            )
        )

    lines.extend(["", "## Q4 Source Plan Validation Feedback Summary", ""])
    lines.append(
        "| Label | Present Ratio | Failure Rate | Issue Count Mean | Probe Issue Count Mean | Probe Executed Count Mean | Selected Test Count Mean | Executed Test Count Mean |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        source_plan_feedback_raw = row.get("source_plan_validation_feedback_summary")
        source_plan_feedback = (
            source_plan_feedback_raw if isinstance(source_plan_feedback_raw, dict) else {}
        )
        lines.append(
            "| {label} | {present_ratio:.4f} | {failure_rate:.4f} | {issue_count_mean:.4f} | {probe_issue_count_mean:.4f} | {probe_executed_count_mean:.4f} | {selected_test_count_mean:.4f} | {executed_test_count_mean:.4f} |".format(
                label=str(row.get("label", "")),
                present_ratio=_safe_float(source_plan_feedback.get("present_ratio", 0.0), 0.0),
                failure_rate=_safe_float(source_plan_feedback.get("failure_rate", 0.0), 0.0),
                issue_count_mean=_safe_float(
                    source_plan_feedback.get("issue_count_mean", 0.0), 0.0
                ),
                probe_issue_count_mean=_safe_float(
                    source_plan_feedback.get("probe_issue_count_mean", 0.0), 0.0
                ),
                probe_executed_count_mean=_safe_float(
                    source_plan_feedback.get("probe_executed_count_mean", 0.0), 0.0
                ),
                selected_test_count_mean=_safe_float(
                    source_plan_feedback.get("selected_test_count_mean", 0.0), 0.0
                ),
                executed_test_count_mean=_safe_float(
                    source_plan_feedback.get("executed_test_count_mean", 0.0), 0.0
                ),
            )
        )

    lines.extend(["", "## Q1 Source Plan Failure Signal Summary", ""])
    lines.append(
        "| Label | Present Ratio | Failure Rate | Issue Count Mean | Probe Issue Count Mean | Probe Executed Count Mean | Replay Cache Origin Ratio | Observability Origin Ratio | Source Plan Origin Ratio | Validate Step Origin Ratio |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in (baseline, current, tuned):
        if not isinstance(row, dict):
            continue
        source_plan_failure_raw = row.get("source_plan_failure_signal_summary")
        source_plan_failure = (
            source_plan_failure_raw if isinstance(source_plan_failure_raw, dict) else {}
        )
        lines.append(
            "| {label} | {present_ratio:.4f} | {failure_rate:.4f} | {issue_count_mean:.4f} | {probe_issue_count_mean:.4f} | {probe_executed_count_mean:.4f} | {replay_cache_origin_ratio:.4f} | {observability_origin_ratio:.4f} | {source_plan_origin_ratio:.4f} | {validate_step_origin_ratio:.4f} |".format(
                label=str(row.get("label", "")),
                present_ratio=_safe_float(source_plan_failure.get("present_ratio", 0.0), 0.0),
                failure_rate=_safe_float(source_plan_failure.get("failure_rate", 0.0), 0.0),
                issue_count_mean=_safe_float(source_plan_failure.get("issue_count_mean", 0.0), 0.0),
                probe_issue_count_mean=_safe_float(
                    source_plan_failure.get("probe_issue_count_mean", 0.0), 0.0
                ),
                probe_executed_count_mean=_safe_float(
                    source_plan_failure.get("probe_executed_count_mean", 0.0), 0.0
                ),
                replay_cache_origin_ratio=_safe_float(
                    source_plan_failure.get("replay_cache_origin_ratio", 0.0), 0.0
                ),
                observability_origin_ratio=_safe_float(
                    source_plan_failure.get("observability_origin_ratio", 0.0), 0.0
                ),
                source_plan_origin_ratio=_safe_float(
                    source_plan_failure.get("source_plan_origin_ratio", 0.0), 0.0
                ),
                validate_step_origin_ratio=_safe_float(
                    source_plan_failure.get("validate_step_origin_ratio", 0.0), 0.0
                ),
            )
        )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare baseline/current/tuned validation-rich summaries."
    )
    parser.add_argument("--baseline", required=True, help="Baseline summary.json path.")
    parser.add_argument("--current", required=True, help="Current summary.json path.")
    parser.add_argument("--tuned", required=True, help="Tuned summary.json path.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmark/validation_rich/comparison/latest",
        help="Directory to write comparison outputs.",
    )
    args = parser.parse_args(sys.argv[1:])

    root = Path(__file__).resolve().parents[1]
    baseline_path = resolve_report_path(root=root, value=str(args.baseline))
    current_path = resolve_report_path(root=root, value=str(args.current))
    tuned_path = resolve_report_path(root=root, value=str(args.tuned))
    output_dir = resolve_report_path(root=root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline = _extract_summary(
        label="baseline",
        path=baseline_path,
        payload=load_report_json(baseline_path),
    )
    current = _extract_summary(
        label="current",
        path=current_path,
        payload=load_report_json(current_path),
    )
    tuned = _extract_summary(
        label="tuned",
        path=tuned_path,
        payload=load_report_json(tuned_path),
    )

    if not baseline["loaded"] or not current["loaded"] or not tuned["loaded"]:
        print("[validation-rich-compare] missing required summary input", file=sys.stderr)
        return 2

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_only": True,
        "baseline": baseline,
        "current": current,
        "tuned": tuned,
        "comparisons": {
            "baseline_vs_current": _build_delta(left=baseline, right=current),
            "current_vs_tuned": _build_delta(left=current, right=tuned),
            "baseline_vs_tuned": _build_delta(left=baseline, right=tuned),
        },
    }

    json_path = output_dir / "validation_rich_comparison_report.json"
    md_path = output_dir / "validation_rich_comparison_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload=payload), encoding="utf-8")

    print(f"[validation-rich-compare] report json: {json_path}")
    print(f"[validation-rich-compare] report md:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
