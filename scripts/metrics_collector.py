from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark_ops import (
    read_benchmark_deep_symbol_summary,
    read_benchmark_native_scip_summary,
    read_benchmark_retrieval_control_plane_gate_summary,
    read_benchmark_retrieval_frontier_gate_summary,
    read_benchmark_source_plan_failure_signal_summary,
    read_benchmark_source_plan_validation_feedback_summary,
    read_benchmark_validation_probe_summary,
)

METRICS_TO_TRACK = {
    "precision_at_k": {"target": 0.65, "trend": "up"},
    "noise_rate": {"target": 0.35, "trend": "down"},
    "latency_p95_ms": {"target": 350.0, "trend": "down"},
    "chunk_hit_at_k": {"target": 0.90, "trend": "up"},
    "memory_recall_rate": {
        "target": 0.70,
        "trend": "up",
        "requires_signal": "memory",
    },
    "profile_utilization": {
        "target": 0.50,
        "trend": "up",
        "requires_signal": "memory",
    },
}

VALIDATION_RICH_METRICS_TO_TRACK = {
    "task_success_rate": {"trend": "up"},
    "precision_at_k": {"trend": "up"},
    "noise_rate": {"trend": "down"},
    "latency_p95_ms": {"trend": "down"},
    "validation_test_count": {"trend": "up"},
    "missing_validation_rate": {"trend": "down"},
    "evidence_insufficient_rate": {"trend": "down"},
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _collect_matrix_source_status(*, summary_path: Path) -> dict[str, Any]:
    payload = _load_json(summary_path)
    repos_raw = payload.get("repos")
    repos = [item for item in repos_raw if isinstance(item, dict)] if isinstance(repos_raw, list) else []
    return {
        "path": str(summary_path),
        "exists": summary_path.exists() and summary_path.is_file(),
        "loaded": bool(repos),
        "repo_count": len(repos),
    }


def _collect_validation_rich_source_status(*, summary_path: Path) -> dict[str, Any]:
    payload = _load_json(summary_path)
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    return {
        "path": str(summary_path),
        "exists": summary_path.exists() and summary_path.is_file(),
        "loaded": bool(metrics),
        "metric_count": len(metrics),
    }


def collect_metrics(*, summary_path: Path) -> dict[str, float]:
    payload = _load_json(summary_path)
    repos_raw = payload.get("repos")
    repos = repos_raw if isinstance(repos_raw, list) else []

    precision_values: list[float] = []
    noise_values: list[float] = []
    latency_values: list[float] = []
    chunk_hit_values: list[float] = []
    notes_hit_values: list[float] = []
    profile_selected_values: list[float] = []
    memory_signal_repos = 0

    for item in repos:
        if not isinstance(item, dict):
            continue
        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

        precision_values.append(max(0.0, _safe_float(metrics.get("precision_at_k"), 0.0)))
        noise_values.append(max(0.0, _safe_float(metrics.get("noise_rate"), 0.0)))
        latency_values.append(max(0.0, _safe_float(metrics.get("latency_p95_ms"), 0.0)))
        chunk_hit_values.append(max(0.0, _safe_float(metrics.get("chunk_hit_at_k"), 0.0)))
        notes_hit_values.append(max(0.0, _safe_float(metrics.get("notes_hit_ratio"), 0.0)))
        profile_selected = max(0.0, _safe_float(metrics.get("profile_selected_mean"), 0.0))
        capture_trigger = max(0.0, _safe_float(metrics.get("capture_trigger_ratio"), 0.0))
        profile_selected_values.append(profile_selected)
        if (
            notes_hit_values[-1] > 0.0
            or profile_selected > 0.0
            or capture_trigger > 0.0
        ):
            memory_signal_repos += 1

    return {
        "precision_at_k": _mean(precision_values),
        "noise_rate": _mean(noise_values),
        "latency_p95_ms": _mean(latency_values),
        "chunk_hit_at_k": _mean(chunk_hit_values),
        "memory_recall_rate": _mean(notes_hit_values),
        "profile_utilization": _mean(profile_selected_values),
        "_repo_count": float(len(repos)),
        "_memory_signal_coverage": (
            float(memory_signal_repos) / float(len(repos)) if repos else 0.0
        ),
    }


def collect_validation_rich_metrics(*, summary_path: Path) -> dict[str, float]:
    payload = _load_json(summary_path)
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    return {
        "task_success_rate": max(
            0.0, _safe_float(metrics.get("task_success_rate"), 0.0)
        ),
        "precision_at_k": max(0.0, _safe_float(metrics.get("precision_at_k"), 0.0)),
        "noise_rate": max(0.0, _safe_float(metrics.get("noise_rate"), 0.0)),
        "latency_p95_ms": max(0.0, _safe_float(metrics.get("latency_p95_ms"), 0.0)),
        "validation_test_count": max(
            0.0, _safe_float(metrics.get("validation_test_count"), 0.0)
        ),
        "missing_validation_rate": max(
            0.0, _safe_float(metrics.get("missing_validation_rate"), 0.0)
        ),
        "evidence_insufficient_rate": max(
            0.0, _safe_float(metrics.get("evidence_insufficient_rate"), 0.0)
        ),
    }


def collect_validation_rich_gate_summary(*, summary_path: Path) -> dict[str, Any]:
    return read_benchmark_retrieval_control_plane_gate_summary(summary_path)


def collect_validation_rich_frontier_gate_summary(*, summary_path: Path) -> dict[str, Any]:
    return read_benchmark_retrieval_frontier_gate_summary(summary_path)


def collect_validation_rich_deep_symbol_summary(*, summary_path: Path) -> dict[str, float]:
    return read_benchmark_deep_symbol_summary(summary_path)


def collect_validation_rich_native_scip_summary(*, summary_path: Path) -> dict[str, float]:
    return read_benchmark_native_scip_summary(summary_path)


def collect_validation_rich_validation_probe_summary(
    *, summary_path: Path
) -> dict[str, float]:
    return read_benchmark_validation_probe_summary(summary_path)


def collect_validation_rich_source_plan_validation_feedback_summary(
    *, summary_path: Path
) -> dict[str, float]:
    return read_benchmark_source_plan_validation_feedback_summary(summary_path)


def collect_validation_rich_source_plan_failure_signal_summary(
    *, summary_path: Path
) -> dict[str, float]:
    return read_benchmark_source_plan_failure_signal_summary(summary_path)


def _is_metric_active(
    *,
    metric: str,
    current: dict[str, float],
    previous: dict[str, float],
    enforce_memory_metrics: bool,
) -> bool:
    config = METRICS_TO_TRACK.get(metric, {})
    signal = str(config.get("requires_signal") or "").strip().lower()
    if signal != "memory":
        return True
    if enforce_memory_metrics:
        return True
    current_coverage = _safe_float(current.get("_memory_signal_coverage"), 0.0)
    previous_coverage = _safe_float(previous.get("_memory_signal_coverage"), 0.0)
    return max(current_coverage, previous_coverage) > 0.0


def check_regressions(
    *,
    current: dict[str, float],
    previous: dict[str, float],
    tolerance_ratio: float = 0.05,
    enforce_memory_metrics: bool = False,
    metrics_to_track: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    ratio = max(0.0, float(tolerance_ratio))
    tracked_metrics = metrics_to_track or METRICS_TO_TRACK
    for metric, config in tracked_metrics.items():
        if metric not in current or metric not in previous:
            continue
        if not _is_metric_active(
            metric=metric,
            current=current,
            previous=previous,
            enforce_memory_metrics=enforce_memory_metrics,
        ):
            continue
        curr = _safe_float(current.get(metric), 0.0)
        prev = _safe_float(previous.get(metric), 0.0)
        trend = str(config.get("trend") or "").strip().lower()
        if trend == "up":
            floor = prev * (1.0 - ratio)
            if curr < floor:
                regressions.append(
                    {
                        "metric": metric,
                        "trend": "up",
                        "previous": prev,
                        "current": curr,
                        "threshold": floor,
                    }
                )
        elif trend == "down":
            ceiling = prev * (1.0 + ratio)
            if curr > ceiling:
                regressions.append(
                    {
                        "metric": metric,
                        "trend": "down",
                        "previous": prev,
                        "current": curr,
                        "threshold": ceiling,
                    }
                )
    return regressions


def check_targets(*, metrics: dict[str, float]) -> list[dict[str, Any]]:
    return _check_targets(metrics=metrics, enforce_memory_metrics=False)


def _check_targets(
    *,
    metrics: dict[str, float],
    enforce_memory_metrics: bool,
    metrics_to_track: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    tracked_metrics = metrics_to_track or METRICS_TO_TRACK
    for metric, config in tracked_metrics.items():
        if metric not in metrics:
            continue
        if not _is_metric_active(
            metric=metric,
            current=metrics,
            previous=metrics,
            enforce_memory_metrics=enforce_memory_metrics,
        ):
            continue
        trend = str(config.get("trend") or "").strip().lower()
        target = _safe_float(config.get("target"), 0.0)
        actual = _safe_float(metrics.get(metric), 0.0)
        if trend == "up" and actual < target:
            failures.append(
                {
                    "metric": metric,
                    "operator": ">=",
                    "target": target,
                    "actual": actual,
                }
            )
        if trend == "down" and actual > target:
            failures.append(
                {
                    "metric": metric,
                    "operator": "<=",
                    "target": target,
                    "actual": actual,
                }
            )
    return failures


def _resolve_summary_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect benchmark trends and regression warnings.")
    parser.add_argument(
        "--current",
        default="artifacts/benchmark/matrix/latest/matrix_summary.json",
        help="Current benchmark matrix summary path.",
    )
    parser.add_argument(
        "--previous",
        default="",
        help="Previous benchmark matrix summary path (optional).",
    )
    parser.add_argument(
        "--validation-rich-current",
        default="",
        help="Optional current validation-rich benchmark summary path.",
    )
    parser.add_argument(
        "--validation-rich-previous",
        default="",
        help="Optional previous validation-rich benchmark summary path.",
    )
    parser.add_argument(
        "--tolerance-ratio",
        type=float,
        default=0.05,
        help="Allowed drift ratio for regression checks.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSON path.",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero when regression or target failure exists.",
    )
    parser.add_argument(
        "--enforce-memory-metrics",
        action="store_true",
        help="Enforce memory/profile targets even when memory signal coverage is zero.",
    )
    args = parser.parse_args(sys.argv[1:])

    project_root = Path(__file__).resolve().parents[1]
    current_path = _resolve_summary_path(root=project_root, value=str(args.current))
    previous_path = (
        _resolve_summary_path(root=project_root, value=str(args.previous))
        if str(args.previous).strip()
        else None
    )
    validation_rich_current_path = (
        _resolve_summary_path(root=project_root, value=str(args.validation_rich_current))
        if str(args.validation_rich_current).strip()
        else None
    )
    validation_rich_previous_path = (
        _resolve_summary_path(root=project_root, value=str(args.validation_rich_previous))
        if str(args.validation_rich_previous).strip()
        else None
    )

    current_metrics = collect_metrics(summary_path=current_path)
    previous_metrics = (
        collect_metrics(summary_path=previous_path) if isinstance(previous_path, Path) else {}
    )
    matrix_source = _collect_matrix_source_status(summary_path=current_path)
    validation_rich_current_metrics = (
        collect_validation_rich_metrics(summary_path=validation_rich_current_path)
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_gate_summary = (
        collect_validation_rich_gate_summary(summary_path=validation_rich_current_path)
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_frontier_gate_summary = (
        collect_validation_rich_frontier_gate_summary(
            summary_path=validation_rich_current_path
        )
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_deep_symbol_summary = (
        collect_validation_rich_deep_symbol_summary(
            summary_path=validation_rich_current_path
        )
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_native_scip_summary = (
        collect_validation_rich_native_scip_summary(
            summary_path=validation_rich_current_path
        )
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_validation_probe_summary = (
        collect_validation_rich_validation_probe_summary(
            summary_path=validation_rich_current_path
        )
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_source_plan_validation_feedback_summary = (
        collect_validation_rich_source_plan_validation_feedback_summary(
            summary_path=validation_rich_current_path
        )
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_source_plan_failure_signal_summary = (
        collect_validation_rich_source_plan_failure_signal_summary(
            summary_path=validation_rich_current_path
        )
        if isinstance(validation_rich_current_path, Path)
        else {}
    )
    validation_rich_previous_metrics = (
        collect_validation_rich_metrics(summary_path=validation_rich_previous_path)
        if isinstance(validation_rich_previous_path, Path)
        else {}
    )
    validation_rich_previous_validation_probe_summary = (
        collect_validation_rich_validation_probe_summary(
            summary_path=validation_rich_previous_path
        )
        if isinstance(validation_rich_previous_path, Path)
        else {}
    )
    validation_rich_previous_source_plan_validation_feedback_summary = (
        collect_validation_rich_source_plan_validation_feedback_summary(
            summary_path=validation_rich_previous_path
        )
        if isinstance(validation_rich_previous_path, Path)
        else {}
    )
    validation_rich_previous_source_plan_failure_signal_summary = (
        collect_validation_rich_source_plan_failure_signal_summary(
            summary_path=validation_rich_previous_path
        )
        if isinstance(validation_rich_previous_path, Path)
        else {}
    )
    validation_rich_source = (
        _collect_validation_rich_source_status(summary_path=validation_rich_current_path)
        if isinstance(validation_rich_current_path, Path)
        else {"path": "", "exists": False, "loaded": False, "metric_count": 0}
    )
    regressions = (
        check_regressions(
            current=current_metrics,
            previous=previous_metrics,
            tolerance_ratio=max(0.0, float(args.tolerance_ratio)),
            enforce_memory_metrics=bool(args.enforce_memory_metrics),
        )
        if bool(matrix_source.get("loaded", False))
        else []
    )
    target_failures = (
        _check_targets(
            metrics=current_metrics,
            enforce_memory_metrics=bool(args.enforce_memory_metrics),
        )
        if bool(matrix_source.get("loaded", False))
        else []
    )
    validation_rich_regressions = (
        check_regressions(
            current=validation_rich_current_metrics,
            previous=validation_rich_previous_metrics,
            tolerance_ratio=max(0.0, float(args.tolerance_ratio)),
            enforce_memory_metrics=False,
            metrics_to_track=VALIDATION_RICH_METRICS_TO_TRACK,
        )
        if bool(validation_rich_source.get("loaded", False))
        else []
    )
    matrix_lane = {
        "enabled": bool(matrix_source.get("exists", False)),
        "loaded": bool(matrix_source.get("loaded", False)),
        "repo_count": int(matrix_source.get("repo_count", 0) or 0),
        "passed": (
            len(regressions) == 0 and len(target_failures) == 0
            if bool(matrix_source.get("loaded", False))
            else True
        ),
    }
    validation_rich_lane = {
        "enabled": bool(validation_rich_source.get("exists", False)),
        "loaded": bool(validation_rich_source.get("loaded", False)),
        "metric_count": int(validation_rich_source.get("metric_count", 0) or 0),
        "passed": (
            len(validation_rich_regressions) == 0
            if bool(validation_rich_source.get("loaded", False))
            else True
        ),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_path": str(current_path),
        "previous_path": str(previous_path) if isinstance(previous_path, Path) else "",
        "validation_rich_current_path": (
            str(validation_rich_current_path)
            if isinstance(validation_rich_current_path, Path)
            else ""
        ),
        "validation_rich_previous_path": (
            str(validation_rich_previous_path)
            if isinstance(validation_rich_previous_path, Path)
            else ""
        ),
        "current_metrics": current_metrics,
        "previous_metrics": previous_metrics,
        "matrix_lane": matrix_lane,
        "validation_rich_current_metrics": validation_rich_current_metrics,
        "validation_rich_previous_metrics": validation_rich_previous_metrics,
        "validation_rich_gate_summary": validation_rich_gate_summary,
        "validation_rich_frontier_gate_summary": validation_rich_frontier_gate_summary,
        "validation_rich_deep_symbol_summary": validation_rich_deep_symbol_summary,
        "validation_rich_native_scip_summary": validation_rich_native_scip_summary,
        "validation_rich_validation_probe_summary": (
            validation_rich_validation_probe_summary
        ),
        "validation_rich_source_plan_validation_feedback_summary": (
            validation_rich_source_plan_validation_feedback_summary
        ),
        "validation_rich_source_plan_failure_signal_summary": (
            validation_rich_source_plan_failure_signal_summary
        ),
        "validation_rich_previous_validation_probe_summary": (
            validation_rich_previous_validation_probe_summary
        ),
        "validation_rich_previous_source_plan_validation_feedback_summary": (
            validation_rich_previous_source_plan_validation_feedback_summary
        ),
        "validation_rich_previous_source_plan_failure_signal_summary": (
            validation_rich_previous_source_plan_failure_signal_summary
        ),
        "validation_rich_lane": validation_rich_lane,
        "regressions": regressions,
        "validation_rich_regressions": validation_rich_regressions,
        "target_failures": target_failures,
        "passed": (
            bool(matrix_lane.get("passed", True))
            and bool(validation_rich_lane.get("passed", True))
        ),
    }

    output_path = str(args.output).strip()
    if output_path:
        resolved = _resolve_summary_path(root=project_root, value=output_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[metrics] report: {resolved}")
    else:
        print(json.dumps(payload, ensure_ascii=False))

    if args.fail_on_regression and not payload["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
