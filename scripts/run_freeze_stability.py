from __future__ import annotations

import argparse
import json
import shlex
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


@dataclass
class IterationResult:
    run_id: int
    command: list[str]
    returncode: int
    elapsed_seconds: float
    report_path: str
    freeze_passed: bool
    tabiv3_retry_attempts: int
    gate_failures: list[dict[str, Any]]
    feature_slice_results: dict[str, bool]


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


def _collect_gate_failures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for gate_name in (
        "tabiv3_gate",
        "concept_gate",
        "external_concept_gate",
        "embedding_gate",
        "plugin_policy_gate",
        "e2e_success_gate",
        "runtime_gate",
    ):
        gate_raw = payload.get(gate_name)
        gate = gate_raw if isinstance(gate_raw, dict) else {}
        if not bool(gate.get("enabled", False)):
            continue
        gate_failures_raw = gate.get("failures")
        gate_failures = gate_failures_raw if isinstance(gate_failures_raw, list) else []
        if not gate_failures and bool(gate.get("passed", True)):
            continue
        if gate_failures:
            for item in gate_failures:
                row = item if isinstance(item, dict) else {"detail": str(item)}
                failures.append(
                    {
                        "gate": gate_name,
                        "metric": str(row.get("metric") or ""),
                        "repo": str(row.get("repo") or ""),
                        "operator": str(row.get("operator") or ""),
                        "actual": row.get("actual"),
                        "expected": row.get("expected"),
                    }
                )
            continue
        failures.append({"gate": gate_name, "metric": "passed", "actual": 0, "expected": 1})
    return failures


def _collect_feature_slice_results(payload: dict[str, Any]) -> dict[str, bool]:
    summary_raw = payload.get("feature_slices_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    slices_raw = summary.get("slices")
    slices = slices_raw if isinstance(slices_raw, list) else []
    rows: dict[str, bool] = {}
    for item in slices:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        rows[name] = bool(item.get("passed", False))
    return rows


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


def _parse_csv_names(raw: str) -> list[str]:
    values = [
        item.strip()
        for item in str(raw or "").split(",")
        if item.strip()
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def _run_freeze_iteration(
    *,
    run_id: int,
    root: Path,
    output_dir: Path,
    matrix_config: Path,
    cli_bin: str,
    fail_on_thresholds: bool,
    skip_skill_validation: bool,
) -> IterationResult:
    run_output = output_dir / f"run-{run_id:02d}"
    run_output.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(root / "scripts" / "run_release_freeze_regression.py"),
        "--matrix-config",
        str(matrix_config),
        "--output-dir",
        str(run_output),
        "--cli-bin",
        str(cli_bin),
    ]
    if fail_on_thresholds:
        command.append("--fail-on-thresholds")
    if skip_skill_validation:
        command.append("--skip-skill-validation")

    started = perf_counter()
    completed = subprocess.run(command, cwd=str(root), check=False, capture_output=True, text=True)
    elapsed = round(perf_counter() - started, 3)

    logs_dir = run_output / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stability.stdout.log").write_text(str(completed.stdout or ""), encoding="utf-8")
    (logs_dir / "stability.stderr.log").write_text(str(completed.stderr or ""), encoding="utf-8")

    report_path = run_output / "freeze_regression.json"
    payload = _load_json(report_path)
    tabiv3_gate_raw = payload.get("tabiv3_gate")
    tabiv3_gate = tabiv3_gate_raw if isinstance(tabiv3_gate_raw, dict) else {}

    return IterationResult(
        run_id=run_id,
        command=command,
        returncode=int(completed.returncode),
        elapsed_seconds=elapsed,
        report_path=str(report_path),
        freeze_passed=bool(payload.get("passed", False)),
        tabiv3_retry_attempts=max(0, int(tabiv3_gate.get("retry_attempts_executed", 0) or 0)),
        gate_failures=_collect_gate_failures(payload),
        feature_slice_results=_collect_feature_slice_results(payload),
    )


def evaluate_stability(
    *,
    iterations: list[IterationResult],
    max_failure_rate: float,
    max_retry_median: float,
    tracked_feature_slices: list[str],
    min_feature_slice_pass_rate: float,
) -> dict[str, Any]:
    run_count = len(iterations)
    passed_count = sum(1 for item in iterations if item.freeze_passed)
    pass_rate = float(passed_count) / float(run_count) if run_count > 0 else 0.0
    failure_rate = 1.0 - pass_rate if run_count > 0 else 1.0

    retry_samples = [int(item.tabiv3_retry_attempts) for item in iterations]
    retry_median = (
        float(statistics.median(retry_samples))
        if retry_samples
        else 0.0
    )

    failed_runs: list[dict[str, Any]] = []
    for item in iterations:
        if item.freeze_passed:
            continue
        failed_runs.append(
            {
                "run_id": int(item.run_id),
                "returncode": int(item.returncode),
                "report_path": str(item.report_path),
                "gate_failures": item.gate_failures,
            }
        )

    passes_failure_budget = failure_rate <= max(0.0, float(max_failure_rate))
    passes_retry_budget = retry_median <= max(0.0, float(max_retry_median))

    feature_slice_names = sorted(
        {
            name
            for item in iterations
            for name in item.feature_slice_results.keys()
        }
    )
    tracked_slices = tracked_feature_slices or feature_slice_names
    feature_slice_stability: list[dict[str, Any]] = []
    tracked_feature_slice_failures: list[dict[str, Any]] = []
    for name in feature_slice_names:
        passed_runs = sum(
            1
            for item in iterations
            if bool(item.feature_slice_results.get(name, False))
        )
        pass_rate_for_slice = (
            float(passed_runs) / float(run_count)
            if run_count > 0
            else 0.0
        )
        classification = _classify_passes(
            passed_count=passed_runs,
            run_count=run_count,
        )
        feature_slice_stability.append(
            {
                "name": name,
                "run_count": run_count,
                "passed_count": passed_runs,
                "failed_count": max(0, run_count - passed_runs),
                "pass_rate": pass_rate_for_slice,
                "classification": classification,
                "stable": passed_runs == run_count and run_count > 0,
                "tracked": name in tracked_slices,
                "latest_passed": bool(iterations[-1].feature_slice_results.get(name, False))
                if iterations
                else False,
            }
        )
        if name in tracked_slices and pass_rate_for_slice < min_feature_slice_pass_rate:
            tracked_feature_slice_failures.append(
                {
                    "slice": name,
                    "pass_rate": pass_rate_for_slice,
                    "expected_min_pass_rate": min_feature_slice_pass_rate,
                    "classification": classification,
                }
            )

    return {
        "run_count": run_count,
        "passed_count": passed_count,
        "failed_count": max(0, run_count - passed_count),
        "pass_rate": pass_rate,
        "failure_rate": failure_rate,
        "tabiv3_retry_attempts": retry_samples,
        "tabiv3_retry_median": retry_median,
        "classification": _classify_passes(
            passed_count=passed_count,
            run_count=run_count,
        ),
        "max_failure_rate": max(0.0, float(max_failure_rate)),
        "max_retry_median": max(0.0, float(max_retry_median)),
        "tracked_feature_slices": tracked_slices,
        "min_feature_slice_pass_rate": max(
            0.0, float(min_feature_slice_pass_rate)
        ),
        "feature_slice_stability": feature_slice_stability,
        "tracked_feature_slice_failures": tracked_feature_slice_failures,
        "passed": bool(
            passes_failure_budget
            and passes_retry_budget
            and not tracked_feature_slice_failures
        ),
        "failed_runs": failed_runs,
    }


def _render_markdown(*, payload: dict[str, Any]) -> str:
    iterations_raw = payload.get("iterations")
    iterations = iterations_raw if isinstance(iterations_raw, list) else []
    tracked_feature_slices_raw = payload.get("tracked_feature_slices")
    tracked_feature_slices = (
        tracked_feature_slices_raw
        if isinstance(tracked_feature_slices_raw, list)
        else []
    )
    feature_slice_stability_raw = payload.get("feature_slice_stability")
    feature_slice_stability = (
        feature_slice_stability_raw
        if isinstance(feature_slice_stability_raw, list)
        else []
    )
    tracked_feature_slice_failures_raw = payload.get("tracked_feature_slice_failures")
    tracked_feature_slice_failures = (
        tracked_feature_slice_failures_raw
        if isinstance(tracked_feature_slice_failures_raw, list)
        else []
    )

    lines: list[str] = [
        "# Freeze Stability Report",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Passed: {bool(payload.get('passed', False))}",
        f"- Run count: {int(payload.get('run_count', 0) or 0)}",
        f"- Pass rate: {float(payload.get('pass_rate', 0.0) or 0.0):.4f}",
        f"- Failure rate: {float(payload.get('failure_rate', 0.0) or 0.0):.4f}",
        f"- Classification: {str(payload.get('classification') or 'no_data')}",
        f"- Tabiv3 retry median: {float(payload.get('tabiv3_retry_median', 0.0) or 0.0):.4f}",
        f"- Allowed failure rate: {float(payload.get('max_failure_rate', 0.0) or 0.0):.4f}",
        f"- Allowed retry median: {float(payload.get('max_retry_median', 0.0) or 0.0):.4f}",
        f"- Tracked feature slices: {', '.join(tracked_feature_slices) if tracked_feature_slices else '(all)'}",
        f"- Required tracked feature-slice pass rate: {float(payload.get('min_feature_slice_pass_rate', 0.0) or 0.0):.4f}",
        "",
        "## Iterations",
        "",
        "| Run | Passed | Return Code | Elapsed (s) | Retry Attempts |",
        "| --- | :---: | ---: | ---: | ---: |",
    ]

    for item in iterations:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {run} | {passed} | {code} | {elapsed:.3f} | {retry} |".format(
                run=int(item.get("run_id", 0) or 0),
                passed="PASS" if bool(item.get("freeze_passed", False)) else "FAIL",
                code=int(item.get("returncode", 0) or 0),
                elapsed=float(item.get("elapsed_seconds", 0.0) or 0.0),
                retry=int(item.get("tabiv3_retry_attempts", 0) or 0),
            )
        )

    lines.append("")
    lines.append("## Feature Slice Stability")
    lines.append("")
    lines.append("| Slice | Tracked | Passed Runs | Pass Rate | Classification | Latest Passed |")
    lines.append("| --- | :---: | ---: | ---: | --- | :---: |")
    for item in feature_slice_stability:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {name} | {tracked} | {passed}/{runs} | {rate:.4f} | {classification} | {latest} |".format(
                name=str(item.get("name") or ""),
                tracked="yes" if bool(item.get("tracked", False)) else "no",
                passed=int(item.get("passed_count", 0) or 0),
                runs=int(item.get("run_count", 0) or 0),
                rate=float(item.get("pass_rate", 0.0) or 0.0),
                classification=str(item.get("classification") or "no_data"),
                latest="PASS" if bool(item.get("latest_passed", False)) else "FAIL",
            )
        )

    lines.append("")
    lines.append("## Tracked Feature Slice Failures")
    lines.append("")
    if not tracked_feature_slice_failures:
        lines.append("- None")
    else:
        for row in tracked_feature_slice_failures:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- {slice}: pass_rate={rate:.4f}, expected>={expected:.4f}, classification={classification}".format(
                    slice=str(row.get("slice") or ""),
                    rate=float(row.get("pass_rate", 0.0) or 0.0),
                    expected=float(row.get("expected_min_pass_rate", 0.0) or 0.0),
                    classification=str(row.get("classification") or "no_data"),
                )
            )

    failed_runs_raw = payload.get("failed_runs")
    failed_runs = failed_runs_raw if isinstance(failed_runs_raw, list) else []
    lines.append("")
    lines.append("## Failed Runs")
    lines.append("")
    if not failed_runs:
        lines.append("- None")
        lines.append("")
        return "\n".join(lines).strip() + "\n"

    for item in failed_runs:
        if not isinstance(item, dict):
            continue
        lines.append(f"### run-{int(item.get('run_id', 0) or 0):02d}")
        lines.append(f"- returncode: {int(item.get('returncode', 0) or 0)}")
        lines.append(f"- report: `{item.get('report_path', '')!s}`")
        failures_raw = item.get("gate_failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if not failures:
            lines.append("- gate_failures: (none)")
            lines.append("")
            continue
        lines.append("- gate_failures:")
        for row in failures:
            if not isinstance(row, dict):
                continue
            lines.append(
                "  - gate={gate}, metric={metric}, repo={repo}, actual={actual}, expected={expected}, operator={op}".format(
                    gate=str(row.get("gate", "")),
                    metric=str(row.get("metric", "")),
                    repo=str(row.get("repo", "")),
                    actual=str(row.get("actual", "")),
                    expected=str(row.get("expected", "")),
                    op=str(row.get("operator", "")),
                )
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated freeze checks and evaluate stability budgets.")
    parser.add_argument(
        "--matrix-config",
        default="benchmark/matrix/repos.yaml",
        help="Matrix config path passed to freeze script.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/release-freeze/stability/latest",
        help="Output directory for per-run reports and stability summary.",
    )
    parser.add_argument("--cli-bin", default="ace-lite", help="CLI binary name/path.")
    parser.add_argument("--runs", type=int, default=20, help="Number of freeze iterations.")
    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.05,
        help="Maximum allowed freeze failure rate.",
    )
    parser.add_argument(
        "--max-retry-median",
        type=float,
        default=2.0,
        help="Maximum allowed tabiv3 retry-attempt median.",
    )
    parser.add_argument(
        "--tracked-feature-slices",
        default="dependency_recall,perturbation,repomap_perturbation",
        help="Comma-separated feature slices that must stay stable across repeated runs.",
    )
    parser.add_argument(
        "--min-feature-slice-pass-rate",
        type=float,
        default=1.0,
        help="Minimum pass rate required for each tracked feature slice.",
    )
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Pass --fail-on-thresholds to freeze runs.",
    )
    parser.add_argument(
        "--skip-skill-validation",
        action="store_true",
        help="Pass --skip-skill-validation to freeze runs.",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit non-zero if stability budget fails.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    matrix_config_path = _resolve_path(root=root, value=str(args.matrix_config))
    output_dir = _resolve_path(root=root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    run_count = max(1, int(args.runs))
    tracked_feature_slices = _parse_csv_names(str(args.tracked_feature_slices))
    iterations: list[IterationResult] = []

    for run_id in range(1, run_count + 1):
        print(f"[stability] running freeze iteration {run_id}/{run_count}...")
        result = _run_freeze_iteration(
            run_id=run_id,
            root=root,
            output_dir=output_dir,
            matrix_config=matrix_config_path,
            cli_bin=str(args.cli_bin),
            fail_on_thresholds=bool(args.fail_on_thresholds),
            skip_skill_validation=bool(args.skip_skill_validation),
        )
        iterations.append(result)
        print(
            f"[stability] run={run_id:02d} freeze_passed={result.freeze_passed} returncode={result.returncode} retry_attempts={result.tabiv3_retry_attempts} elapsed={result.elapsed_seconds:.3f}s"
        )

    summary = evaluate_stability(
        iterations=iterations,
        max_failure_rate=max(0.0, float(args.max_failure_rate)),
        max_retry_median=max(0.0, float(args.max_retry_median)),
        tracked_feature_slices=tracked_feature_slices,
        min_feature_slice_pass_rate=max(
            0.0, float(args.min_feature_slice_pass_rate)
        ),
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_config": str(matrix_config_path),
        "cli_bin": str(args.cli_bin),
        **summary,
        "iterations": [
            {
                "run_id": int(item.run_id),
                "command": list(item.command),
                "command_line": " ".join(shlex.quote(part) for part in item.command),
                "returncode": int(item.returncode),
                "elapsed_seconds": float(item.elapsed_seconds),
                "report_path": str(item.report_path),
                "freeze_passed": bool(item.freeze_passed),
                "tabiv3_retry_attempts": int(item.tabiv3_retry_attempts),
                "gate_failures": list(item.gate_failures),
                "feature_slice_results": dict(item.feature_slice_results),
            }
            for item in iterations
        ],
    }

    summary_json = output_dir / "stability_summary.json"
    summary_md = output_dir / "stability_summary.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(_render_markdown(payload=payload), encoding="utf-8")

    print(f"[stability] summary json: {summary_json}")
    print(f"[stability] summary md:   {summary_md}")
    print(
        "[stability] pass_rate={pass_rate:.4f} failure_rate={failure_rate:.4f} retry_median={retry_median:.4f} passed={passed}".format(
            pass_rate=float(payload.get("pass_rate", 0.0) or 0.0),
            failure_rate=float(payload.get("failure_rate", 0.0) or 0.0),
            retry_median=float(payload.get("tabiv3_retry_median", 0.0) or 0.0),
            passed=bool(payload.get("passed", False)),
        )
    )

    if bool(args.fail_on_gate) and not bool(payload.get("passed", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
