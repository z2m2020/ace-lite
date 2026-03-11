from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    ratio = max(0.0, float(tolerance_ratio))
    for metric, config in METRICS_TO_TRACK.items():
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
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for metric, config in METRICS_TO_TRACK.items():
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

    current_metrics = collect_metrics(summary_path=current_path)
    previous_metrics = (
        collect_metrics(summary_path=previous_path) if isinstance(previous_path, Path) else {}
    )
    regressions = check_regressions(
        current=current_metrics,
        previous=previous_metrics,
        tolerance_ratio=max(0.0, float(args.tolerance_ratio)),
        enforce_memory_metrics=bool(args.enforce_memory_metrics),
    )
    target_failures = _check_targets(
        metrics=current_metrics,
        enforce_memory_metrics=bool(args.enforce_memory_metrics),
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_path": str(current_path),
        "previous_path": str(previous_path) if isinstance(previous_path, Path) else "",
        "current_metrics": current_metrics,
        "previous_metrics": previous_metrics,
        "regressions": regressions,
        "target_failures": target_failures,
        "passed": len(regressions) == 0 and len(target_failures) == 0,
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
