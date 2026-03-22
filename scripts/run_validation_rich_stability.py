from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
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
    gate_failures: list[dict[str, Any]]
    metrics: dict[str, float]
    retrieval_control_plane_gate_summary: dict[str, Any]


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


def _normalize_retrieval_control_plane_gate_summary(
    *, summary: dict[str, Any]
) -> dict[str, Any]:
    gate_raw = summary.get("retrieval_control_plane_gate_summary")
    gate = gate_raw if isinstance(gate_raw, dict) else {}
    normalized: dict[str, Any] = {}
    for key, value in gate.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, bool):
            normalized[key] = bool(value)
        elif isinstance(value, (int, float)):
            normalized[key] = float(value)
        elif isinstance(value, list):
            normalized[key] = [str(item) for item in value if str(item).strip()]
        else:
            normalized[key] = value
    return normalized


def _evaluate_summary(
    *,
    summary: dict[str, Any],
    thresholds: dict[str, float],
) -> tuple[bool, list[dict[str, Any]], dict[str, float]]:
    metrics_raw = summary.get("metrics")
    metrics_input = metrics_raw if isinstance(metrics_raw, dict) else {}
    metrics = {
        name: _safe_float(metrics_input.get(name), 0.0)
        for name in METRIC_NAMES
    }

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
        return False, failures, metrics

    if int(summary.get("case_count", 0) or 0) <= 0:
        failures.append(
            {
                "metric": "case_count",
                "actual": 0,
                "operator": ">=",
                "expected": 1,
            }
        )

    if bool(summary.get("regressed", False)):
        failures.append(
            {
                "metric": "regressed",
                "actual": True,
                "operator": "==",
                "expected": False,
            }
        )

    threshold_rows = (
        ("task_success_rate", ">=", "min_task_success_rate"),
        ("precision_at_k", ">=", "min_precision_at_k"),
        ("noise_rate", "<=", "max_noise_rate"),
        ("latency_p95_ms", "<=", "max_latency_p95_ms"),
        ("validation_test_count", ">=", "min_validation_test_count"),
        ("evidence_insufficient_rate", "<=", "max_evidence_insufficient_rate"),
        ("missing_validation_rate", "<=", "max_missing_validation_rate"),
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

    return len(failures) == 0, failures, metrics


def _run_validation_rich_iteration(
    *,
    run_id: int,
    root: Path,
    output_dir: Path,
    repo: str,
    thresholds: dict[str, float],
    shell_bin: str,
) -> IterationResult:
    run_output = output_dir / f"run-{run_id:02d}"
    run_output.mkdir(parents=True, exist_ok=True)

    command = [
        shell_bin,
        "-File",
        str(root / "scripts" / "run_benchmark.ps1"),
        "-Lane",
        "validation_rich",
        "-Repo",
        str(repo),
        "-OutputDir",
        str(run_output),
    ]
    started = perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(root),
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = round(perf_counter() - started, 3)

    logs_dir = run_output / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stability.stdout.log").write_text(
        str(completed.stdout or ""), encoding="utf-8"
    )
    (logs_dir / "stability.stderr.log").write_text(
        str(completed.stderr or ""), encoding="utf-8"
    )

    summary_path = run_output / "summary.json"
    summary = _load_json(summary_path)
    benchmark_passed, gate_failures, metrics = _evaluate_summary(
        summary=summary,
        thresholds=thresholds,
    )
    return IterationResult(
        run_id=run_id,
        command=command,
        returncode=int(completed.returncode),
        elapsed_seconds=elapsed,
        report_path=str(summary_path),
        summary_loaded=bool(summary),
        benchmark_passed=benchmark_passed and int(completed.returncode) == 0,
        regressed=bool(summary.get("regressed", False)) if summary else False,
        gate_failures=gate_failures,
        metrics=metrics,
        retrieval_control_plane_gate_summary=_normalize_retrieval_control_plane_gate_summary(
            summary=summary
        ),
    )


def evaluate_stability(
    *,
    iterations: list[IterationResult],
    max_failure_rate: float,
) -> dict[str, Any]:
    run_count = len(iterations)
    passed_count = sum(1 for item in iterations if item.benchmark_passed)
    failed_count = max(0, run_count - passed_count)
    pass_rate = float(passed_count) / float(run_count) if run_count > 0 else 0.0
    failure_rate = 1.0 - pass_rate if run_count > 0 else 1.0
    classification = _classify_passes(
        passed_count=passed_count,
        run_count=run_count,
    )

    failed_runs: list[dict[str, Any]] = []
    for item in iterations:
        if item.benchmark_passed:
            continue
        failed_runs.append(
            {
                "run_id": int(item.run_id),
                "returncode": int(item.returncode),
                "report_path": str(item.report_path),
                "regressed": bool(item.regressed),
                "gate_failures": item.gate_failures,
            }
        )

    metric_ranges: list[dict[str, Any]] = []
    for metric_name in METRIC_NAMES:
        samples = [
            _safe_float(item.metrics.get(metric_name), 0.0)
            for item in iterations
        ]
        if not samples:
            continue
        metric_ranges.append(
            {
                "metric": metric_name,
                "min": min(samples),
                "max": max(samples),
                "spread": max(samples) - min(samples),
                "latest": samples[-1],
                "median": float(statistics.median(samples)),
            }
        )

    q2_gate_failed_count = sum(
        1
        for item in iterations
        if item.retrieval_control_plane_gate_summary
        and not bool(
            item.retrieval_control_plane_gate_summary.get("gate_passed", False)
        )
    )
    latest_q2_gate_summary = (
        dict(iterations[-1].retrieval_control_plane_gate_summary)
        if iterations and iterations[-1].retrieval_control_plane_gate_summary
        else {}
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_count": run_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_rate": pass_rate,
        "failure_rate": failure_rate,
        "classification": classification,
        "max_failure_rate": max_failure_rate,
        "passed": failure_rate <= max(0.0, float(max_failure_rate)),
        "q2_gate_failed_count": q2_gate_failed_count,
        "latest_retrieval_control_plane_gate_summary": latest_q2_gate_summary,
        "failed_runs": failed_runs,
        "metric_ranges": metric_ranges,
        "iterations": [
            {
                "run_id": int(item.run_id),
                "returncode": int(item.returncode),
                "elapsed_seconds": float(item.elapsed_seconds),
                "report_path": str(item.report_path),
                "summary_loaded": bool(item.summary_loaded),
                "benchmark_passed": bool(item.benchmark_passed),
                "regressed": bool(item.regressed),
                "gate_failures": item.gate_failures,
                "metrics": {
                    name: _safe_float(item.metrics.get(name), 0.0)
                    for name in METRIC_NAMES
                },
                "retrieval_control_plane_gate_summary": dict(
                    item.retrieval_control_plane_gate_summary
                ),
            }
            for item in iterations
        ],
    }


def _render_markdown(*, payload: dict[str, Any], thresholds: dict[str, float]) -> str:
    iterations_raw = payload.get("iterations")
    iterations = iterations_raw if isinstance(iterations_raw, list) else []
    metric_ranges_raw = payload.get("metric_ranges")
    metric_ranges = metric_ranges_raw if isinstance(metric_ranges_raw, list) else []
    latest_q2_gate_raw = payload.get("latest_retrieval_control_plane_gate_summary")
    latest_q2_gate = (
        latest_q2_gate_raw if isinstance(latest_q2_gate_raw, dict) else {}
    )

    lines = [
        "# Validation-Rich Stability Summary",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Run count: {int(payload.get('run_count', 0) or 0)}",
        f"- Passed count: {int(payload.get('passed_count', 0) or 0)}",
        f"- Failure rate: {_safe_float(payload.get('failure_rate'), 1.0):.4f}",
        f"- Classification: {str(payload.get('classification', 'no_data') or 'no_data')}",
        f"- Passed: {bool(payload.get('passed', False))}",
        f"- Q2 gate failed count: {int(payload.get('q2_gate_failed_count', 0) or 0)}",
        "",
        "## Thresholds",
        "",
        f"- task_success_rate >= {_safe_float(thresholds.get('min_task_success_rate'), -1.0):.4f}",
        f"- precision_at_k >= {_safe_float(thresholds.get('min_precision_at_k'), -1.0):.4f}",
        f"- noise_rate <= {_safe_float(thresholds.get('max_noise_rate'), -1.0):.4f}",
        f"- latency_p95_ms <= {_safe_float(thresholds.get('max_latency_p95_ms'), -1.0):.2f}",
        f"- validation_test_count >= {_safe_float(thresholds.get('min_validation_test_count'), -1.0):.4f}",
        f"- evidence_insufficient_rate <= {_safe_float(thresholds.get('max_evidence_insufficient_rate'), -1.0):.4f}",
        f"- missing_validation_rate <= {_safe_float(thresholds.get('max_missing_validation_rate'), -1.0):.4f}",
        "",
    ]

    if latest_q2_gate:
        lines.extend(
            [
                "## Latest Q2 Retrieval Control Plane Gate",
                "",
                f"- Gate passed: {bool(latest_q2_gate.get('gate_passed', False))}",
                "- Regression evaluated: {evaluated}".format(
                    evaluated=bool(latest_q2_gate.get("regression_evaluated", False))
                ),
                "- Regression detected: {detected}".format(
                    detected=bool(
                        latest_q2_gate.get("benchmark_regression_detected", False)
                    )
                ),
                "- Shadow coverage: {shadow:.4f}".format(
                    shadow=_safe_float(
                        latest_q2_gate.get("adaptive_router_shadow_coverage"), 0.0
                    )
                ),
                "- Risk upgrade gain: {gain:.4f}".format(
                    gain=_safe_float(
                        latest_q2_gate.get("risk_upgrade_precision_gain"), 0.0
                    )
                ),
                "- Latency P95 ms: {latency:.2f}".format(
                    latency=_safe_float(latest_q2_gate.get("latency_p95_ms"), 0.0)
                ),
                "",
            ]
        )

    lines.extend(["## Metric Ranges", ""])

    if metric_ranges:
        lines.append("| Metric | Min | Max | Spread | Median | Latest |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for row in metric_ranges:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| {metric} | {min:.4f} | {max:.4f} | {spread:.4f} | {median:.4f} | {latest:.4f} |".format(
                    metric=str(row.get("metric", "")),
                    min=_safe_float(row.get("min"), 0.0),
                    max=_safe_float(row.get("max"), 0.0),
                    spread=_safe_float(row.get("spread"), 0.0),
                    median=_safe_float(row.get("median"), 0.0),
                    latest=_safe_float(row.get("latest"), 0.0),
                )
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.extend(
        [
            "## Iterations",
            "",
            "| Run | Passed | Regressed | Task Success | Precision | Noise | Latency p95 | Validation Tests | Evidence Insufficient | Missing Validation |",
            "| --- | :---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in iterations:
        if not isinstance(row, dict):
            continue
        metrics_raw = row.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        lines.append(
            "| {run_id} | {passed} | {regressed} | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} | {validation_count:.4f} | {evidence:.4f} | {missing:.4f} |".format(
                run_id=int(row.get("run_id", 0) or 0),
                passed="✅" if bool(row.get("benchmark_passed", False)) else "❌",
                regressed="✅" if bool(row.get("regressed", False)) else "❌",
                task_success=_safe_float(metrics.get("task_success_rate"), 0.0),
                precision=_safe_float(metrics.get("precision_at_k"), 0.0),
                noise=_safe_float(metrics.get("noise_rate"), 0.0),
                latency=_safe_float(metrics.get("latency_p95_ms"), 0.0),
                validation_count=_safe_float(metrics.get("validation_test_count"), 0.0),
                evidence=_safe_float(metrics.get("evidence_insufficient_rate"), 0.0),
                missing=_safe_float(metrics.get("missing_validation_rate"), 0.0),
            )
        )
        gate_raw = row.get("retrieval_control_plane_gate_summary")
        gate = gate_raw if isinstance(gate_raw, dict) else {}
        if gate:
            lines.append(
                "  q2_gate: passed={passed}, shadow_coverage={shadow:.4f}, risk_upgrade_gain={gain:.4f}, latency_p95_ms={latency:.2f}".format(
                    passed=bool(gate.get("gate_passed", False)),
                    shadow=_safe_float(
                        gate.get("adaptive_router_shadow_coverage"), 0.0
                    ),
                    gain=_safe_float(gate.get("risk_upgrade_precision_gain"), 0.0),
                    latency=_safe_float(gate.get("latency_p95_ms"), 0.0),
                )
            )

    failed_runs_raw = payload.get("failed_runs")
    failed_runs = failed_runs_raw if isinstance(failed_runs_raw, list) else []
    lines.extend(["", "## Failed Runs", ""])
    if failed_runs:
        for row in failed_runs:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- run {run_id}: returncode={returncode}, regressed={regressed}, report=`{report_path}`".format(
                    run_id=int(row.get("run_id", 0) or 0),
                    returncode=int(row.get("returncode", 0) or 0),
                    regressed=bool(row.get("regressed", False)),
                    report_path=str(row.get("report_path", "")),
                )
            )
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run repeated validation-rich benchmark checks and evaluate stability."
    )
    parser.add_argument("--runs", type=int, default=2, help="Number of repeated runs.")
    parser.add_argument(
        "--repo",
        default="ace-lite-engine",
        help="Repo name passed to run_benchmark.ps1.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmark/validation_rich/stability/latest",
        help="Output directory for per-run reports and stability summary.",
    )
    parser.add_argument(
        "--shell-bin",
        default="powershell",
        help="Shell binary used to execute run_benchmark.ps1.",
    )
    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.0,
        help="Maximum tolerated failure rate across repeated runs.",
    )
    parser.add_argument("--min-task-success-rate", type=float, default=0.90)
    parser.add_argument("--min-precision-at-k", type=float, default=0.40)
    parser.add_argument("--max-noise-rate", type=float, default=0.60)
    parser.add_argument("--max-latency-p95-ms", type=float, default=700.0)
    parser.add_argument("--min-validation-test-count", type=float, default=5.0)
    parser.add_argument("--max-evidence-insufficient-rate", type=float, default=0.0)
    parser.add_argument("--max-missing-validation-rate", type=float, default=0.0)
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit non-zero when the stability summary exceeds the configured budget.",
    )
    args = parser.parse_args(sys.argv[1:])

    root = Path(__file__).resolve().parents[1]
    output_dir = _resolve_path(root=root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    thresholds = {
        "min_task_success_rate": float(args.min_task_success_rate),
        "min_precision_at_k": float(args.min_precision_at_k),
        "max_noise_rate": float(args.max_noise_rate),
        "max_latency_p95_ms": float(args.max_latency_p95_ms),
        "min_validation_test_count": float(args.min_validation_test_count),
        "max_evidence_insufficient_rate": float(args.max_evidence_insufficient_rate),
        "max_missing_validation_rate": float(args.max_missing_validation_rate),
    }

    iterations: list[IterationResult] = []
    run_count = max(1, int(args.runs))
    for run_id in range(1, run_count + 1):
        print(f"[validation-rich-stability] running iteration {run_id}/{run_count}...")
        result = _run_validation_rich_iteration(
            run_id=run_id,
            root=root,
            output_dir=output_dir,
            repo=str(args.repo),
            thresholds=thresholds,
            shell_bin=str(args.shell_bin),
        )
        iterations.append(result)
        print(
            "[validation-rich-stability] run={run_id:02d} passed={passed} regressed={regressed} returncode={returncode} elapsed={elapsed:.3f}s".format(
                run_id=run_id,
                passed=bool(result.benchmark_passed),
                regressed=bool(result.regressed),
                returncode=int(result.returncode),
                elapsed=float(result.elapsed_seconds),
            )
        )

    summary = evaluate_stability(
        iterations=iterations,
        max_failure_rate=float(args.max_failure_rate),
    )
    summary["thresholds"] = thresholds

    summary_json = output_dir / "stability_summary.json"
    summary_md = output_dir / "stability_summary.md"
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_md.write_text(
        _render_markdown(payload=summary, thresholds=thresholds),
        encoding="utf-8",
    )

    print(f"[validation-rich-stability] summary json: {summary_json}")
    print(f"[validation-rich-stability] summary md:   {summary_md}")
    print(
        "[validation-rich-stability] pass_rate={pass_rate:.4f} failure_rate={failure_rate:.4f} passed={passed}".format(
            pass_rate=_safe_float(summary.get("pass_rate"), 0.0),
            failure_rate=_safe_float(summary.get("failure_rate"), 1.0),
            passed=bool(summary.get("passed", False)),
        )
    )

    if bool(args.fail_on_gate) and not bool(summary.get("passed", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
