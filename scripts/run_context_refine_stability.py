from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.benchmark_ops import read_benchmark_context_refine_summary

METRIC_NAMES = (
    "present_case_rate",
    "watch_case_rate",
    "thin_context_case_rate",
    "keep_count_mean",
    "need_more_read_count_mean",
)


@dataclass
class IterationResult:
    run_id: int
    command: list[str]
    returncode: int
    elapsed_seconds: float
    report_path: str
    summary_loaded: bool
    benchmark_passed: bool
    regressed: bool
    failures: list[dict[str, Any]]
    metrics: dict[str, float]
    context_refine_summary: dict[str, float] = field(default_factory=dict)


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


def _classify_passes(*, passed_count: int, run_count: int) -> str:
    if run_count <= 0:
        return "no_data"
    if passed_count <= 0:
        return "stable_fail"
    if passed_count >= run_count:
        return "stable_pass"
    if passed_count == 1:
        return "one_off_pass"
    return "mixed"


def _evaluate_summary(
    *,
    summary: dict[str, Any],
    thresholds: dict[str, float],
) -> tuple[bool, list[dict[str, Any]], dict[str, float], dict[str, float]]:
    context_refine_summary = read_benchmark_context_refine_summary(
        Path(str(summary.get("__path", "")))
    )
    metrics = {name: _safe_float(context_refine_summary.get(name), 0.0) for name in METRIC_NAMES}
    failures: list[dict[str, Any]] = []
    if not summary:
        failures.append(
            {
                "metric": "summary",
                "actual": "missing",
                "operator": "==",
                "expected": "present",
                "reason": "summary_missing",
            }
        )
        return False, failures, metrics, context_refine_summary

    threshold_rows = (
        ("present_case_rate", ">=", "min_present_case_rate"),
        ("watch_case_rate", "<=", "max_watch_case_rate"),
        ("thin_context_case_rate", "<=", "max_thin_context_case_rate"),
        ("keep_count_mean", ">=", "min_keep_count_mean"),
        ("need_more_read_count_mean", "<=", "max_need_more_read_count_mean"),
    )
    for metric_name, operator, threshold_name in threshold_rows:
        actual = _safe_float(metrics.get(metric_name), 0.0)
        expected = _safe_float(thresholds.get(threshold_name), -1.0)
        if expected < 0.0:
            continue
        if operator == ">=" and actual < expected:
            failures.append(
                {
                    "metric": metric_name,
                    "actual": actual,
                    "operator": operator,
                    "expected": expected,
                }
            )
        if operator == "<=" and actual > expected:
            failures.append(
                {
                    "metric": metric_name,
                    "actual": actual,
                    "operator": operator,
                    "expected": expected,
                }
            )

    return len(failures) == 0, failures, metrics, context_refine_summary


def evaluate_stability(
    *, iterations: list[IterationResult], max_failure_rate: float
) -> dict[str, Any]:
    run_count = len(iterations)
    passed_count = sum(1 for item in iterations if item.benchmark_passed)
    failed_runs = [item for item in iterations if not item.benchmark_passed]
    failure_rate = float(len(failed_runs)) / float(run_count) if run_count else 0.0
    metric_ranges = []
    for metric in METRIC_NAMES:
        values = [float(item.metrics.get(metric, 0.0)) for item in iterations]
        metric_ranges.append(
            {
                "metric": metric,
                "min": min(values) if values else 0.0,
                "max": max(values) if values else 0.0,
                "spread": (max(values) - min(values)) if values else 0.0,
            }
        )

    latest_summary = iterations[-1].context_refine_summary if iterations else {}
    return {
        "run_count": run_count,
        "passed_count": passed_count,
        "failed_count": len(failed_runs),
        "pass_rate": float(passed_count) / float(run_count) if run_count else 0.0,
        "failure_rate": failure_rate,
        "classification": _classify_passes(passed_count=passed_count, run_count=run_count),
        "passed": failure_rate <= float(max_failure_rate),
        "latest_context_refine_summary": latest_summary,
        "failed_runs": [{"run_id": item.run_id, "failures": item.failures} for item in failed_runs],
        "metric_ranges": metric_ranges,
    }


def _run_context_refine_iteration(
    *,
    run_id: int,
    command: list[str],
    cwd: Path,
    summary_path: Path,
    thresholds: dict[str, float],
) -> IterationResult:
    started = perf_counter()
    completed = subprocess.run(command, cwd=str(cwd), check=False, capture_output=True, text=True)
    elapsed_seconds = max(0.0, perf_counter() - started)
    summary = _load_json(summary_path)
    if summary:
        summary["__path"] = str(summary_path)
    benchmark_passed, failures, metrics, context_refine_summary = _evaluate_summary(
        summary=summary,
        thresholds=thresholds,
    )
    return IterationResult(
        run_id=run_id,
        command=command,
        returncode=int(completed.returncode),
        elapsed_seconds=elapsed_seconds,
        report_path=str(summary_path),
        summary_loaded=bool(summary),
        benchmark_passed=benchmark_passed,
        regressed=not benchmark_passed,
        failures=failures,
        metrics=metrics,
        context_refine_summary=context_refine_summary,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run context_refine benchmark stability lane")
    parser.add_argument("--root", default=".")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-failure-rate", type=float, default=0.25)
    parser.add_argument("--min-present-case-rate", type=float, default=0.5)
    parser.add_argument("--max-watch-case-rate", type=float, default=0.75)
    parser.add_argument("--max-thin-context-case-rate", type=float, default=0.5)
    parser.add_argument("--min-keep-count-mean", type=float, default=0.0)
    parser.add_argument("--max-need-more-read-count-mean", type=float, default=10.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    root = _resolve_path(root=Path.cwd(), value=str(args.root))
    summary_path = _resolve_path(root=root, value=str(args.summary))
    output_path = _resolve_path(root=root, value=str(args.output))
    thresholds = {
        "min_present_case_rate": float(args.min_present_case_rate),
        "max_watch_case_rate": float(args.max_watch_case_rate),
        "max_thin_context_case_rate": float(args.max_thin_context_case_rate),
        "min_keep_count_mean": float(args.min_keep_count_mean),
        "max_need_more_read_count_mean": float(args.max_need_more_read_count_mean),
    }
    command = [str(item) for item in args.command if str(item).strip()] or [
        sys.executable,
        "-c",
        "print('context_refine')",
    ]

    iterations = [
        _run_context_refine_iteration(
            run_id=run_id,
            command=command,
            cwd=root,
            summary_path=summary_path,
            thresholds=thresholds,
        )
        for run_id in range(1, max(1, int(args.runs)) + 1)
    ]
    payload = evaluate_stability(
        iterations=iterations, max_failure_rate=float(args.max_failure_rate)
    )
    payload["schema_version"] = "context_refine_stability_v1"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["runs"] = [item.__dict__ for item in iterations]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if bool(payload.get("passed", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
