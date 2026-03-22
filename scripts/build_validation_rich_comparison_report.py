from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark_ops import read_benchmark_retrieval_control_plane_gate_summary

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


def _extract_summary(*, label: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    metrics_raw = payload.get("metrics")
    metrics_input = metrics_raw if isinstance(metrics_raw, dict) else {}
    failed_checks_raw = payload.get("failed_checks")
    failed_checks = (
        [str(item) for item in failed_checks_raw if str(item).strip()]
        if isinstance(failed_checks_raw, list)
        else []
    )
    return {
        "label": label,
        "path": str(path),
        "loaded": bool(payload),
        "generated_at": str(payload.get("generated_at", "") or ""),
        "repo": str(payload.get("repo", "") or ""),
        "case_count": int(payload.get("case_count", 0) or 0),
        "regressed": bool(payload.get("regressed", False)),
        "failed_checks": failed_checks,
        "metrics": {
            name: _safe_float(metrics_input.get(name), 0.0)
            for name in METRIC_NAMES
        },
        "retrieval_control_plane_gate_summary": (
            read_benchmark_retrieval_control_plane_gate_summary(path)
        ),
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
                failed_checks=", ".join(str(item) for item in row.get("failed_checks", []))
                or "(none)",
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
            "| {metric} | {baseline:.4f} | {current:.4f} | {tuned:.4f} |".format(
                metric=metric_name,
                baseline=_safe_float(baseline_metrics.get(metric_name), 0.0),
                current=_safe_float(current_metrics.get(metric_name), 0.0),
                tuned=_safe_float(tuned_metrics.get(metric_name), 0.0),
            )
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
        failed_checks_raw = gate.get("failed_checks", [])
        failed_checks = (
            ", ".join(str(item) for item in failed_checks_raw if str(item).strip())
            if isinstance(failed_checks_raw, list)
            else ""
        )
        lines.append(
            "| {label} | {gate_passed} | {regression_evaluated} | {regression_detected} | {shadow:.4f} | {gain:.4f} | {latency:.2f} | {failed_checks} |".format(
                label=str(row.get("label", "")),
                gate_passed="yes" if bool(gate.get("gate_passed", False)) else "no",
                regression_evaluated=(
                    "yes" if bool(gate.get("regression_evaluated", False)) else "no"
                ),
                regression_detected=(
                    "yes"
                    if bool(gate.get("benchmark_regression_detected", False))
                    else "no"
                ),
                shadow=_safe_float(
                    gate.get("adaptive_router_shadow_coverage", 0.0), 0.0
                ),
                gain=_safe_float(gate.get("risk_upgrade_precision_gain", 0.0), 0.0),
                latency=_safe_float(gate.get("latency_p95_ms", 0.0), 0.0),
                failed_checks=failed_checks or "(none)",
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
    baseline_path = _resolve_path(root=root, value=str(args.baseline))
    current_path = _resolve_path(root=root, value=str(args.current))
    tuned_path = _resolve_path(root=root, value=str(args.tuned))
    output_dir = _resolve_path(root=root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline = _extract_summary(
        label="baseline",
        path=baseline_path,
        payload=_load_json(baseline_path),
    )
    current = _extract_summary(
        label="current",
        path=current_path,
        payload=_load_json(current_path),
    )
    tuned = _extract_summary(
        label="tuned",
        path=tuned_path,
        payload=_load_json(tuned_path),
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
