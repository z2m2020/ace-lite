from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METRIC_NAMES = (
    "task_success_rate",
    "precision_at_k",
    "noise_rate",
    "latency_p95_ms",
    "validation_test_count",
    "evidence_insufficient_rate",
    "missing_validation_rate",
)


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _evaluate_thresholds(*, metrics: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    failures: list[str] = []
    checks = (
        ("task_success_rate", ">=", "min_task_success_rate"),
        ("precision_at_k", ">=", "min_precision_at_k"),
        ("noise_rate", "<=", "max_noise_rate"),
        ("latency_p95_ms", "<=", "max_latency_p95_ms"),
        ("validation_test_count", ">=", "min_validation_test_count"),
        ("evidence_insufficient_rate", "<=", "max_evidence_insufficient_rate"),
        ("missing_validation_rate", "<=", "max_missing_validation_rate"),
    )
    for metric_name, operator, threshold_name in checks:
        actual = _safe_float(metrics.get(metric_name), 0.0)
        expected = _safe_float(thresholds.get(threshold_name), -1.0)
        if expected < 0.0:
            continue
        if operator == ">=" and actual < expected:
            failures.append(f"{metric_name} below threshold")
        if operator == "<=" and actual > expected:
            failures.append(f"{metric_name} above threshold")
    return failures


def _extract_latest_metrics(trend_payload: dict[str, Any]) -> dict[str, float]:
    latest_raw = trend_payload.get("latest")
    latest = latest_raw if isinstance(latest_raw, dict) else {}
    metrics_raw = latest.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else latest
    return {
        metric_name: _safe_float(metrics.get(metric_name), 0.0)
        for metric_name in METRIC_NAMES
    }


def evaluate_promotion(
    *,
    trend_payload: dict[str, Any],
    stability_payload: dict[str, Any],
    comparison_payload: dict[str, Any] | None,
    thresholds: dict[str, float],
    min_history_count: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    gates: list[dict[str, Any]] = []

    history_count = int(trend_payload.get("history_count", 0) or 0)
    trend_latest_raw = trend_payload.get("latest")
    trend_latest = trend_latest_raw if isinstance(trend_latest_raw, dict) else {}
    trend_failed_checks_raw = trend_payload.get("failed_check_top3")
    trend_failed_checks = (
        trend_failed_checks_raw if isinstance(trend_failed_checks_raw, list) else []
    )
    latest_metrics = _extract_latest_metrics(trend_payload)
    threshold_failures = _evaluate_thresholds(metrics=latest_metrics, thresholds=thresholds)
    retrieval_control_plane_gate_raw = trend_latest.get(
        "retrieval_control_plane_gate_summary"
    )
    retrieval_control_plane_gate = (
        retrieval_control_plane_gate_raw
        if isinstance(retrieval_control_plane_gate_raw, dict)
        else {}
    )
    retrieval_frontier_gate_raw = trend_latest.get("retrieval_frontier_gate_summary")
    retrieval_frontier_gate = (
        retrieval_frontier_gate_raw
        if isinstance(retrieval_frontier_gate_raw, dict)
        else {}
    )
    deep_symbol_summary_raw = trend_latest.get("deep_symbol_summary")
    deep_symbol_summary = (
        deep_symbol_summary_raw if isinstance(deep_symbol_summary_raw, dict) else {}
    )
    native_scip_summary_raw = trend_latest.get("native_scip_summary")
    native_scip_summary = (
        native_scip_summary_raw if isinstance(native_scip_summary_raw, dict) else {}
    )
    validation_probe_summary_raw = trend_latest.get("validation_probe_summary")
    validation_probe_summary = (
        validation_probe_summary_raw
        if isinstance(validation_probe_summary_raw, dict)
        else {}
    )
    source_plan_feedback_summary_raw = trend_latest.get(
        "source_plan_validation_feedback_summary"
    )
    source_plan_feedback_summary = (
        source_plan_feedback_summary_raw
        if isinstance(source_plan_feedback_summary_raw, dict)
        else {}
    )
    source_plan_failure_summary_raw = trend_latest.get(
        "source_plan_failure_signal_summary"
    )
    source_plan_failure_summary = (
        source_plan_failure_summary_raw
        if isinstance(source_plan_failure_summary_raw, dict)
        else {}
    )

    trend_ok = history_count >= max(1, int(min_history_count))
    if not trend_ok:
        reasons.append(
            f"trend history_count {history_count} is below required {min_history_count}"
        )
    if bool(trend_latest.get("regressed", False)):
        reasons.append("latest validation-rich summary is marked regressed")
    if trend_failed_checks:
        warnings.append("trend report still shows failed_checks history")
    if threshold_failures:
        reasons.extend(threshold_failures)
    gates.append(
        {
            "name": "trend",
            "passed": trend_ok
            and not bool(trend_latest.get("regressed", False))
            and not threshold_failures,
            "history_count": history_count,
            "latest_regressed": bool(trend_latest.get("regressed", False)),
            "threshold_failures": threshold_failures,
            "historical_failed_checks": trend_failed_checks,
        }
    )

    retrieval_control_plane_ok = True
    retrieval_control_plane_summary: dict[str, Any] = {"present": False, "passed": True}
    if retrieval_control_plane_gate:
        retrieval_control_plane_ok = bool(
            retrieval_control_plane_gate.get("gate_passed", False)
        )
        if not retrieval_control_plane_ok:
            reasons.append("retrieval control plane gate is not passed")
        retrieval_control_plane_summary = {
            "present": True,
            "passed": retrieval_control_plane_ok,
            "regression_evaluated": bool(
                retrieval_control_plane_gate.get("regression_evaluated", False)
            ),
            "benchmark_regression_detected": bool(
                retrieval_control_plane_gate.get("benchmark_regression_detected", False)
            ),
            "failed_checks": [
                str(item)
                for item in retrieval_control_plane_gate.get("failed_checks", [])
                if str(item).strip()
            ]
            if isinstance(retrieval_control_plane_gate.get("failed_checks"), list)
            else [],
        }
    gates.append({"name": "retrieval_control_plane", **retrieval_control_plane_summary})

    retrieval_frontier_ok = True
    retrieval_frontier_summary: dict[str, Any] = {"present": False, "passed": True}
    if retrieval_frontier_gate:
        retrieval_frontier_ok = bool(retrieval_frontier_gate.get("gate_passed", False))
        if not retrieval_frontier_ok:
            reasons.append("retrieval frontier gate is not passed")
        retrieval_frontier_summary = {
            "present": True,
            "passed": retrieval_frontier_ok,
            "failed_checks": [
                str(item)
                for item in retrieval_frontier_gate.get("failed_checks", [])
                if str(item).strip()
            ]
            if isinstance(retrieval_frontier_gate.get("failed_checks"), list)
            else [],
            "deep_symbol_case_recall": _safe_float(
                retrieval_frontier_gate.get("deep_symbol_case_recall"), 0.0
            ),
            "native_scip_loaded_rate": _safe_float(
                retrieval_frontier_gate.get("native_scip_loaded_rate"), 0.0
            ),
            "deep_symbol_summary": {
                "case_count": _safe_float(deep_symbol_summary.get("case_count"), 0.0),
                "recall": _safe_float(deep_symbol_summary.get("recall"), 0.0),
            },
            "native_scip_summary": {
                "loaded_rate": _safe_float(native_scip_summary.get("loaded_rate"), 0.0),
                "document_count_mean": _safe_float(
                    native_scip_summary.get("document_count_mean"), 0.0
                ),
                "definition_occurrence_count_mean": _safe_float(
                    native_scip_summary.get("definition_occurrence_count_mean"), 0.0
                ),
                "reference_occurrence_count_mean": _safe_float(
                    native_scip_summary.get("reference_occurrence_count_mean"), 0.0
                ),
                "symbol_definition_count_mean": _safe_float(
                    native_scip_summary.get("symbol_definition_count_mean"), 0.0
                ),
            },
        }
    gates.append({"name": "retrieval_frontier", **retrieval_frontier_summary})
    gates.append(
        {
            "name": "validation_probe_summary",
            "present": bool(validation_probe_summary),
            "passed": True,
            "validation_test_count": _safe_float(
                validation_probe_summary.get("validation_test_count"), 0.0
            ),
            "probe_enabled_ratio": _safe_float(
                validation_probe_summary.get("probe_enabled_ratio"), 0.0
            ),
            "probe_executed_count_mean": _safe_float(
                validation_probe_summary.get("probe_executed_count_mean"), 0.0
            ),
            "probe_failure_rate": _safe_float(
                validation_probe_summary.get("probe_failure_rate"), 0.0
            ),
        }
    )
    gates.append(
        {
            "name": "source_plan_validation_feedback",
            "present": bool(source_plan_feedback_summary),
            "passed": True,
            "present_ratio": _safe_float(
                source_plan_feedback_summary.get("present_ratio"), 0.0
            ),
            "failure_rate": _safe_float(
                source_plan_feedback_summary.get("failure_rate"), 0.0
            ),
            "issue_count_mean": _safe_float(
                source_plan_feedback_summary.get("issue_count_mean"), 0.0
            ),
            "probe_issue_count_mean": _safe_float(
                source_plan_feedback_summary.get("probe_issue_count_mean"), 0.0
            ),
            "probe_executed_count_mean": _safe_float(
                source_plan_feedback_summary.get("probe_executed_count_mean"), 0.0
            ),
            "selected_test_count_mean": _safe_float(
                source_plan_feedback_summary.get("selected_test_count_mean"), 0.0
            ),
            "executed_test_count_mean": _safe_float(
                source_plan_feedback_summary.get("executed_test_count_mean"), 0.0
            ),
        }
    )
    gates.append(
        {
            "name": "source_plan_failure_signal",
            "present": bool(source_plan_failure_summary),
            "passed": True,
            "present_ratio": _safe_float(
                source_plan_failure_summary.get("present_ratio"), 0.0
            ),
            "failure_rate": _safe_float(
                source_plan_failure_summary.get("failure_rate"), 0.0
            ),
            "issue_count_mean": _safe_float(
                source_plan_failure_summary.get("issue_count_mean"), 0.0
            ),
            "probe_issue_count_mean": _safe_float(
                source_plan_failure_summary.get("probe_issue_count_mean"), 0.0
            ),
            "probe_executed_count_mean": _safe_float(
                source_plan_failure_summary.get("probe_executed_count_mean"), 0.0
            ),
            "selected_test_count_mean": _safe_float(
                source_plan_failure_summary.get("selected_test_count_mean"), 0.0
            ),
            "executed_test_count_mean": _safe_float(
                source_plan_failure_summary.get("executed_test_count_mean"), 0.0
            ),
            "replay_cache_origin_ratio": _safe_float(
                source_plan_failure_summary.get("replay_cache_origin_ratio"), 0.0
            ),
        }
    )

    classification = str(stability_payload.get("classification", "no_data") or "no_data")
    stability_ok = bool(stability_payload.get("passed", False)) and classification == "stable_pass"
    if not stability_ok:
        reasons.append(
            f"stability classification is {classification} with passed={bool(stability_payload.get('passed', False))}"
        )
    gates.append(
        {
            "name": "stability",
            "passed": stability_ok,
            "classification": classification,
            "failure_rate": _safe_float(stability_payload.get("failure_rate"), 1.0),
        }
    )

    comparison_ok = True
    comparison_summary: dict[str, Any] = {"present": False, "passed": True}
    if isinstance(comparison_payload, dict) and comparison_payload:
        comparison_summary["present"] = True
        current_raw = comparison_payload.get("current")
        current = current_raw if isinstance(current_raw, dict) else {}
        tuned_raw = comparison_payload.get("tuned")
        tuned = tuned_raw if isinstance(tuned_raw, dict) else {}
        current_metrics_raw = current.get("metrics")
        current_metrics = current_metrics_raw if isinstance(current_metrics_raw, dict) else {}
        tuned_metrics_raw = tuned.get("metrics")
        tuned_metrics = tuned_metrics_raw if isinstance(tuned_metrics_raw, dict) else {}
        regression_reasons: list[str] = []
        if _safe_float(tuned_metrics.get("noise_rate"), 0.0) > _safe_float(
            current_metrics.get("noise_rate"), 0.0
        ):
            regression_reasons.append("tuned noise_rate is worse than current")
        if _safe_float(
            tuned_metrics.get("missing_validation_rate"), 0.0
        ) > _safe_float(current_metrics.get("missing_validation_rate"), 0.0):
            regression_reasons.append("tuned missing_validation_rate is worse than current")
        if _safe_float(
            tuned_metrics.get("evidence_insufficient_rate"), 0.0
        ) > _safe_float(current_metrics.get("evidence_insufficient_rate"), 0.0):
            regression_reasons.append(
                "tuned evidence_insufficient_rate is worse than current"
            )
        if regression_reasons:
            comparison_ok = False
            reasons.extend(regression_reasons)
        comparison_summary.update(
            {
                "passed": comparison_ok,
                "regression_reasons": regression_reasons,
            }
        )
    gates.append({"name": "comparison", **comparison_summary})

    eligible = (
        trend_ok
        and retrieval_control_plane_ok
        and retrieval_frontier_ok
        and stability_ok
        and comparison_ok
        and not threshold_failures
        and not bool(trend_latest.get("regressed", False))
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommendation": "eligible_for_enforced" if eligible else "stay_report_only",
        "eligible": eligible,
        "reasons": reasons,
        "warnings": warnings,
        "gates": gates,
        "thresholds": thresholds,
        "latest_metrics": latest_metrics,
    }


def _render_markdown(*, payload: dict[str, Any]) -> str:
    reasons_raw = payload.get("reasons")
    reasons = reasons_raw if isinstance(reasons_raw, list) else []
    warnings_raw = payload.get("warnings")
    warnings = warnings_raw if isinstance(warnings_raw, list) else []
    gates_raw = payload.get("gates")
    gates = gates_raw if isinstance(gates_raw, list) else []
    latest_metrics_raw = payload.get("latest_metrics")
    latest_metrics = latest_metrics_raw if isinstance(latest_metrics_raw, dict) else {}

    lines = [
        "# Validation-Rich Gate Promotion Decision",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Recommendation: {payload.get('recommendation', 'stay_report_only')}",
        f"- Eligible: {bool(payload.get('eligible', False))}",
        "",
        "## Gates",
        "",
    ]
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        lines.append(
            "- {name}: passed={passed}".format(
                name=str(gate.get("name", "")),
                passed=bool(gate.get("passed", False)),
            )
        )
    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")
    lines.extend(["", "## Latest Metrics", "", "| Metric | Value |", "| --- | ---: |"])
    for metric_name in METRIC_NAMES:
        lines.append(
            f"| {metric_name} | "
            f"{_safe_float(latest_metrics.get(metric_name), 0.0):.4f} |"
        )
    lines.extend(["", "## Reasons", ""])
    if reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate whether validation_rich_gate can move beyond report_only."
    )
    parser.add_argument("--trend-report", required=True)
    parser.add_argument("--stability-report", required=True)
    parser.add_argument("--comparison-report", default="")
    parser.add_argument("--output", default="artifacts/benchmark/validation_rich/promotion/latest/promotion_decision.json")
    parser.add_argument("--min-history-count", type=int, default=2)
    parser.add_argument("--min-task-success-rate", type=float, default=0.90)
    parser.add_argument("--min-precision-at-k", type=float, default=0.40)
    parser.add_argument("--max-noise-rate", type=float, default=0.60)
    parser.add_argument("--max-latency-p95-ms", type=float, default=650.0)
    parser.add_argument("--min-validation-test-count", type=float, default=5.0)
    parser.add_argument("--max-evidence-insufficient-rate", type=float, default=0.0)
    parser.add_argument("--max-missing-validation-rate", type=float, default=0.0)
    args = parser.parse_args(sys.argv[1:])

    root = Path(__file__).resolve().parents[1]
    trend_path = _resolve_path(root=root, value=str(args.trend_report))
    stability_path = _resolve_path(root=root, value=str(args.stability_report))
    comparison_path = (
        _resolve_path(root=root, value=str(args.comparison_report))
        if str(args.comparison_report).strip()
        else None
    )
    output_path = _resolve_path(root=root, value=str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    trend_payload = _load_json(trend_path)
    stability_payload = _load_json(stability_path)
    comparison_payload = _load_json(comparison_path) if comparison_path is not None else {}
    if not trend_payload or not stability_payload:
        print("[validation-rich-promotion] missing required trend or stability report", file=sys.stderr)
        return 2

    thresholds = {
        "min_task_success_rate": float(args.min_task_success_rate),
        "min_precision_at_k": float(args.min_precision_at_k),
        "max_noise_rate": float(args.max_noise_rate),
        "max_latency_p95_ms": float(args.max_latency_p95_ms),
        "min_validation_test_count": float(args.min_validation_test_count),
        "max_evidence_insufficient_rate": float(args.max_evidence_insufficient_rate),
        "max_missing_validation_rate": float(args.max_missing_validation_rate),
    }
    decision = evaluate_promotion(
        trend_payload=trend_payload,
        stability_payload=stability_payload,
        comparison_payload=comparison_payload,
        thresholds=thresholds,
        min_history_count=int(args.min_history_count),
    )
    output_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    output_path.with_suffix(".md").write_text(_render_markdown(payload=decision), encoding="utf-8")
    print(f"[validation-rich-promotion] decision json: {output_path}")
    print(f"[validation-rich-promotion] decision md:   {output_path.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
