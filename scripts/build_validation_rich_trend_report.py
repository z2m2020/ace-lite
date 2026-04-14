from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
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

METRIC_NAMES = (
    "task_success_rate",
    "precision_at_k",
    "noise_rate",
    "validation_test_count",
    "latency_p95_ms",
    "evidence_insufficient_rate",
    "missing_validation_rate",
)

_DATED_CHECKPOINT_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:$|[-_].+)")


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


def _parse_generated_at(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_direct_dated_summary(*, history_root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(history_root.resolve())
    except Exception:
        return False
    parts = relative.parts
    if len(parts) != 2:
        return False
    parent, filename = parts
    if str(filename) != "summary.json":
        return False
    parent_name = str(parent)
    if not _DATED_CHECKPOINT_PREFIX_RE.match(parent_name):
        return False
    try:
        datetime.strptime(parent_name[:10], "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _iter_summary_paths(*, history_root: Path, latest_report: Path | None, limit: int) -> list[Path]:
    paths: list[Path] = []
    if history_root.exists() and history_root.is_dir():
        for path in history_root.rglob("summary.json"):
            resolved = path.resolve()
            if _is_direct_dated_summary(history_root=history_root, path=resolved):
                paths.append(resolved)
    if isinstance(latest_report, Path) and latest_report.exists() and latest_report.is_file():
        latest_resolved = latest_report.resolve()
        if latest_resolved not in paths:
            paths.append(latest_resolved)

    paths.sort(key=lambda item: (item.stat().st_mtime, str(item)))
    if limit > 0 and len(paths) > limit:
        paths = paths[-limit:]
    return paths


def _canonical_latest_report_path(*, history_root: Path) -> Path:
    return (history_root / "latest" / "summary.json").resolve()


def _resolve_latest_report(
    *,
    history_root: Path,
    latest_report: Path | None,
) -> tuple[Path | None, str]:
    if isinstance(latest_report, Path):
        return latest_report.resolve(), "explicit_override"
    canonical = _canonical_latest_report_path(history_root=history_root)
    if canonical.exists() and canonical.is_file():
        return canonical, "canonical_current"
    return None, "none"


def _extract_row(*, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    failed_checks_raw = payload.get("failed_checks")
    failed_checks = (
        [str(item) for item in failed_checks_raw if str(item).strip()]
        if isinstance(failed_checks_raw, list)
        else []
    )
    return {
        "generated_at": str(payload.get("generated_at", "") or ""),
        "path": str(path),
        "repo": str(payload.get("repo", "") or ""),
        "case_count": int(payload.get("case_count", 0) or 0),
        "regressed": bool(payload.get("regressed", False)),
        "failed_checks": failed_checks,
        "metrics": {
            metric_name: _safe_float(metrics.get(metric_name), 0.0)
            for metric_name in METRIC_NAMES
        },
        "retrieval_control_plane_gate_summary": (
            read_benchmark_retrieval_control_plane_gate_summary(path)
        ),
        "retrieval_frontier_gate_summary": (
            read_benchmark_retrieval_frontier_gate_summary(path)
        ),
        "deep_symbol_summary": read_benchmark_deep_symbol_summary(path),
        "native_scip_summary": read_benchmark_native_scip_summary(path),
        "validation_probe_summary": read_benchmark_validation_probe_summary(path),
        "source_plan_failure_signal_summary": (
            read_benchmark_source_plan_failure_signal_summary(path)
        ),
        "source_plan_validation_feedback_summary": (
            read_benchmark_source_plan_validation_feedback_summary(path)
        ),
    }


def _build_delta(*, latest: dict[str, Any], previous: dict[str, Any]) -> dict[str, dict[str, float]]:
    latest_metrics_raw = latest.get("metrics")
    latest_metrics = latest_metrics_raw if isinstance(latest_metrics_raw, dict) else {}
    previous_metrics_raw = previous.get("metrics")
    previous_metrics = previous_metrics_raw if isinstance(previous_metrics_raw, dict) else {}

    delta: dict[str, dict[str, float]] = {
        "case_count": {
            "current": float(latest.get("case_count", 0) or 0),
            "previous": float(previous.get("case_count", 0) or 0),
            "delta": float(latest.get("case_count", 0) or 0)
            - float(previous.get("case_count", 0) or 0),
        }
    }
    for metric_name in METRIC_NAMES:
        current = _safe_float(latest_metrics.get(metric_name), 0.0)
        prior = _safe_float(previous_metrics.get(metric_name), 0.0)
        delta[metric_name] = {
            "current": current,
            "previous": prior,
            "delta": current - prior,
        }
    return delta


def _collect_suspect_files(*, root: Path, limit: int = 20) -> list[str]:
    command = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
    completed = subprocess.run(
        command,
        cwd=str(root),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return []
    rows = [line.strip().replace("\\", "/") for line in str(completed.stdout or "").splitlines()]
    filtered = [line for line in rows if line]
    return filtered[: max(0, int(limit))]


def _render_markdown(*, payload: dict[str, Any]) -> str:
    rows_raw = payload.get("history")
    rows = rows_raw if isinstance(rows_raw, list) else []
    latest_raw = payload.get("latest")
    latest = latest_raw if isinstance(latest_raw, dict) else {}
    previous_raw = payload.get("previous")
    previous = previous_raw if isinstance(previous_raw, dict) else {}
    delta_raw = payload.get("delta")
    delta = delta_raw if isinstance(delta_raw, dict) else {}

    lines: list[str] = [
        "# Validation-Rich Trend Report",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Report only: {bool(payload.get('report_only', True))}",
        f"- History count: {int(payload.get('history_count', 0) or 0)}",
        f"- Latest report mode: {payload.get('latest_report_mode', '')}",
        f"- Latest report path: {payload.get('latest_report_path', '')}",
        "",
    ]

    if latest:
        latest_metrics_raw = latest.get("metrics")
        latest_metrics = latest_metrics_raw if isinstance(latest_metrics_raw, dict) else {}
        latest_gate_raw = latest.get("retrieval_control_plane_gate_summary")
        latest_gate = latest_gate_raw if isinstance(latest_gate_raw, dict) else {}
        latest_frontier_gate_raw = latest.get("retrieval_frontier_gate_summary")
        latest_frontier_gate = (
            latest_frontier_gate_raw
            if isinstance(latest_frontier_gate_raw, dict)
            else {}
        )
        latest_deep_symbol_raw = latest.get("deep_symbol_summary")
        latest_deep_symbol = (
            latest_deep_symbol_raw if isinstance(latest_deep_symbol_raw, dict) else {}
        )
        latest_native_scip_raw = latest.get("native_scip_summary")
        latest_native_scip = (
            latest_native_scip_raw if isinstance(latest_native_scip_raw, dict) else {}
        )
        latest_validation_probe_raw = latest.get("validation_probe_summary")
        latest_validation_probe = (
            latest_validation_probe_raw
            if isinstance(latest_validation_probe_raw, dict)
            else {}
        )
        latest_source_plan_feedback_raw = latest.get(
            "source_plan_validation_feedback_summary"
        )
        latest_source_plan_feedback = (
            latest_source_plan_feedback_raw
            if isinstance(latest_source_plan_feedback_raw, dict)
            else {}
        )
        latest_source_plan_failure_raw = latest.get(
            "source_plan_failure_signal_summary"
        )
        latest_source_plan_failure = (
            latest_source_plan_failure_raw
            if isinstance(latest_source_plan_failure_raw, dict)
            else {}
        )
        lines.extend(
            [
                "## Latest",
                "",
                f"- Path: `{latest.get('path', '')}`",
                f"- Repo: {latest.get('repo', '')}",
                f"- Case count: {int(latest.get('case_count', 0) or 0)}",
                f"- Regressed: {bool(latest.get('regressed', False))}",
                "- Metrics: task_success={task_success:.4f}, precision={precision:.4f}, noise={noise:.4f}, validation_test_count={validation_count:.4f}, latency_p95_ms={latency:.2f}, evidence_insufficient={evidence:.4f}, missing_validation={missing:.4f}".format(
                    task_success=_safe_float(latest_metrics.get("task_success_rate"), 0.0),
                    precision=_safe_float(latest_metrics.get("precision_at_k"), 0.0),
                    noise=_safe_float(latest_metrics.get("noise_rate"), 0.0),
                    validation_count=_safe_float(latest_metrics.get("validation_test_count"), 0.0),
                    latency=_safe_float(latest_metrics.get("latency_p95_ms"), 0.0),
                    evidence=_safe_float(latest_metrics.get("evidence_insufficient_rate"), 0.0),
                    missing=_safe_float(latest_metrics.get("missing_validation_rate"), 0.0),
                ),
                "",
            ]
        )
        if latest_gate:
            failed_checks_raw = latest_gate.get("failed_checks", [])
            failed_checks = (
                ", ".join(str(item) for item in failed_checks_raw if str(item).strip())
                if isinstance(failed_checks_raw, list)
                else ""
            )
            lines.extend(
                [
                    "## Latest Q2 Retrieval Control Plane Gate",
                    "",
                    f"- Gate passed: {bool(latest_gate.get('gate_passed', False))}",
                    "- Regression evaluated: {evaluated}".format(
                        evaluated=bool(latest_gate.get("regression_evaluated", False))
                    ),
                    "- Regression detected: {detected}".format(
                        detected=bool(
                            latest_gate.get("benchmark_regression_detected", False)
                        )
                    ),
                    "- Shadow coverage: {shadow:.4f}".format(
                        shadow=_safe_float(
                            latest_gate.get("adaptive_router_shadow_coverage", 0.0),
                            0.0,
                        )
                    ),
                    "- Risk upgrade gain: {gain:.4f}".format(
                        gain=_safe_float(
                            latest_gate.get("risk_upgrade_precision_gain", 0.0), 0.0
                        )
                    ),
                    "- Latency P95 ms: {latency:.2f}".format(
                        latency=_safe_float(latest_gate.get("latency_p95_ms", 0.0), 0.0)
                    ),
                    f"- Failed checks: {failed_checks or '(none)'}",
                    "",
                ]
            )
        if latest_frontier_gate:
            frontier_failed_checks_raw = latest_frontier_gate.get("failed_checks", [])
            frontier_failed_checks = (
                ", ".join(
                    str(item) for item in frontier_failed_checks_raw if str(item).strip()
                )
                if isinstance(frontier_failed_checks_raw, list)
                else ""
            )
            lines.extend(
                [
                    "## Latest Q3 Retrieval Frontier Gate",
                    "",
                    f"- Gate passed: {bool(latest_frontier_gate.get('gate_passed', False))}",
                    "- Deep symbol case recall: {recall:.4f}".format(
                        recall=_safe_float(
                            latest_frontier_gate.get("deep_symbol_case_recall", 0.0),
                            0.0,
                        )
                    ),
                    "- Native SCIP loaded rate: {rate:.4f}".format(
                        rate=_safe_float(
                            latest_frontier_gate.get("native_scip_loaded_rate", 0.0),
                            0.0,
                        )
                    ),
                    "- Precision at k: {precision:.4f}".format(
                        precision=_safe_float(
                            latest_frontier_gate.get("precision_at_k", 0.0), 0.0
                        )
                    ),
                    "- Noise rate: {noise:.4f}".format(
                        noise=_safe_float(
                            latest_frontier_gate.get("noise_rate", 0.0), 0.0
                        )
                    ),
                    f"- Failed checks: {frontier_failed_checks or '(none)'}",
                    "",
                ]
            )
        if latest_deep_symbol or latest_native_scip:
            lines.extend(
                [
                    "## Latest Q3 Frontier Evidence",
                    "",
                    "- Deep symbol case count: {count:.4f}; recall: {recall:.4f}".format(
                        count=_safe_float(latest_deep_symbol.get("case_count", 0.0), 0.0),
                        recall=_safe_float(latest_deep_symbol.get("recall", 0.0), 0.0),
                    ),
                    "- Native SCIP loaded rate: {loaded:.4f}; document_count_mean={document:.4f}; definition_occurrence_count_mean={definition:.4f}; reference_occurrence_count_mean={reference:.4f}; symbol_definition_count_mean={symbol:.4f}".format(
                        loaded=_safe_float(latest_native_scip.get("loaded_rate", 0.0), 0.0),
                        document=_safe_float(
                            latest_native_scip.get("document_count_mean", 0.0), 0.0
                        ),
                        definition=_safe_float(
                            latest_native_scip.get(
                                "definition_occurrence_count_mean", 0.0
                            ),
                            0.0,
                        ),
                        reference=_safe_float(
                            latest_native_scip.get(
                                "reference_occurrence_count_mean", 0.0
                            ),
                            0.0,
                        ),
                        symbol=_safe_float(
                            latest_native_scip.get(
                                "symbol_definition_count_mean", 0.0
                            ),
                            0.0,
                        ),
                    ),
                    "",
                ]
            )
        if latest_validation_probe:
            lines.extend(
                [
                    "## Latest Q4 Validation Probe Summary",
                    "",
                    "- Validation test count: {count:.4f}".format(
                        count=_safe_float(
                            latest_validation_probe.get("validation_test_count", 0.0),
                            0.0,
                        )
                    ),
                    "- Probe enabled ratio: {ratio:.4f}".format(
                        ratio=_safe_float(
                            latest_validation_probe.get("probe_enabled_ratio", 0.0),
                            0.0,
                        )
                    ),
                    "- Probe executed count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_validation_probe.get(
                                "probe_executed_count_mean", 0.0
                            ),
                            0.0,
                        )
                    ),
                    "- Probe failure rate: {rate:.4f}".format(
                        rate=_safe_float(
                            latest_validation_probe.get("probe_failure_rate", 0.0),
                            0.0,
                        )
                    ),
                    "",
                ]
            )
        if latest_source_plan_feedback:
            lines.extend(
                [
                    "## Latest Q4 Source Plan Validation Feedback Summary",
                    "",
                    "- Present ratio: {ratio:.4f}".format(
                        ratio=_safe_float(
                            latest_source_plan_feedback.get("present_ratio", 0.0), 0.0
                        )
                    ),
                    "- Failure rate: {rate:.4f}".format(
                        rate=_safe_float(
                            latest_source_plan_feedback.get("failure_rate", 0.0), 0.0
                        )
                    ),
                    "- Issue count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_source_plan_feedback.get("issue_count_mean", 0.0),
                            0.0,
                        )
                    ),
                    "- Probe issue count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_source_plan_feedback.get(
                                "probe_issue_count_mean", 0.0
                            ),
                            0.0,
                        )
                    ),
                    "- Probe executed count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_source_plan_feedback.get(
                                "probe_executed_count_mean", 0.0
                            ),
                            0.0,
                        )
                    ),
                    "- Selected test count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_source_plan_feedback.get(
                                "selected_test_count_mean", 0.0
                            ),
                            0.0,
                        )
                    ),
                    "- Executed test count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_source_plan_feedback.get(
                                "executed_test_count_mean", 0.0
                            ),
                            0.0,
                        )
                    ),
                    "",
                ]
            )
        if latest_source_plan_failure:
            lines.extend(
                [
                    "## Latest Q1 Source Plan Failure Signal Summary",
                    "",
                    "- Present ratio: {ratio:.4f}".format(
                        ratio=_safe_float(
                            latest_source_plan_failure.get("present_ratio", 0.0), 0.0
                        )
                    ),
                    "- Failure rate: {rate:.4f}".format(
                        rate=_safe_float(
                            latest_source_plan_failure.get("failure_rate", 0.0), 0.0
                        )
                    ),
                    "- Issue count mean: {count:.4f}".format(
                        count=_safe_float(
                            latest_source_plan_failure.get("issue_count_mean", 0.0),
                            0.0,
                        )
                    ),
                    "- Replay cache origin ratio: {replay:.4f}; observability origin ratio: {observability:.4f}; source_plan origin ratio: {source_plan:.4f}; validate_step origin ratio: {validate_step:.4f}".format(
                        replay=_safe_float(
                            latest_source_plan_failure.get(
                                "replay_cache_origin_ratio", 0.0
                            ),
                            0.0,
                        ),
                        observability=_safe_float(
                            latest_source_plan_failure.get(
                                "observability_origin_ratio", 0.0
                            ),
                            0.0,
                        ),
                        source_plan=_safe_float(
                            latest_source_plan_failure.get(
                                "source_plan_origin_ratio", 0.0
                            ),
                            0.0,
                        ),
                        validate_step=_safe_float(
                            latest_source_plan_failure.get(
                                "validate_step_origin_ratio", 0.0
                            ),
                            0.0,
                        ),
                    ),
                    "",
                ]
            )

    if previous:
        lines.extend(
            [
                "## Delta",
                "",
                f"- Previous path: `{previous.get('path', '')}`",
                "| Metric | Current | Previous | Delta |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for metric_name in ("case_count", *METRIC_NAMES):
            row_raw = delta.get(metric_name)
            row = row_raw if isinstance(row_raw, dict) else {}
            precision = 0 if metric_name == "case_count" else 4
            lines.append(
                "| {metric} | {current} | {previous} | {delta_value} |".format(
                    metric=metric_name,
                    current=(
                        f"{_safe_float(row.get('current'), 0.0):.0f}"
                        if precision == 0
                        else f"{_safe_float(row.get('current'), 0.0):.{precision}f}"
                    ),
                    previous=(
                        f"{_safe_float(row.get('previous'), 0.0):.0f}"
                        if precision == 0
                        else f"{_safe_float(row.get('previous'), 0.0):.{precision}f}"
                    ),
                    delta_value=(
                        f"{_safe_float(row.get('delta'), 0.0):+.0f}"
                        if precision == 0
                        else f"{_safe_float(row.get('delta'), 0.0):+.{precision}f}"
                    ),
                )
            )
        lines.append("")

    lines.extend(["## Failed Check Top3", ""])
    top_failures_raw = payload.get("failed_check_top3")
    top_failures = top_failures_raw if isinstance(top_failures_raw, list) else []
    if top_failures:
        for item in top_failures:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {check}: {count}".format(
                    check=str(item.get("check", "")),
                    count=int(item.get("count", 0) or 0),
                )
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.extend(["## Suspect Files", ""])
    suspect_files_raw = payload.get("suspect_files")
    suspect_files = suspect_files_raw if isinstance(suspect_files_raw, list) else []
    if suspect_files:
        for item in suspect_files:
            lines.append(f"- `{item!s}`")
    else:
        lines.append("- None")
    lines.append("")

    lines.extend(
        [
            "## History",
            "",
            "| Generated | Repo | Cases | Regressed | Task Success | Precision | Noise | Validation Tests | Missing Validation | Evidence Insufficient |",
            "| --- | --- | ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        if not isinstance(row, dict):
            continue
        metrics_raw = row.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        lines.append(
            "| {generated} | {repo} | {case_count} | {regressed} | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {validation_count:.4f} | {missing:.4f} | {evidence:.4f} |".format(
                generated=str(row.get("generated_at", "")),
                repo=str(row.get("repo", "") or ""),
                case_count=int(row.get("case_count", 0) or 0),
                regressed="yes" if bool(row.get("regressed", False)) else "no",
                task_success=_safe_float(metrics.get("task_success_rate"), 0.0),
                precision=_safe_float(metrics.get("precision_at_k"), 0.0),
                noise=_safe_float(metrics.get("noise_rate"), 0.0),
                validation_count=_safe_float(metrics.get("validation_test_count"), 0.0),
                missing=_safe_float(metrics.get("missing_validation_rate"), 0.0),
                evidence=_safe_float(metrics.get("evidence_insufficient_rate"), 0.0),
            )
        )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a report-only validation-rich trend summary from benchmark artifacts."
    )
    parser.add_argument(
        "--history-root",
        default="artifacts/benchmark/validation_rich",
        help="Directory containing dated validation-rich summary.json artifacts.",
    )
    parser.add_argument(
        "--latest-report",
        default="",
        help="Optional path to a latest validation-rich summary.json artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmark/validation_rich/trend/latest",
        help="Directory to write validation-rich trend report outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of history artifacts to include.",
    )
    args = parser.parse_args(sys.argv[1:])

    project_root = Path(__file__).resolve().parents[1]
    history_root = _resolve_path(root=project_root, value=str(args.history_root))
    latest_report_arg = (
        _resolve_path(root=project_root, value=str(args.latest_report))
        if str(args.latest_report).strip()
        else None
    )
    latest_report, latest_report_mode = _resolve_latest_report(
        history_root=history_root,
        latest_report=latest_report_arg,
    )
    output_dir = _resolve_path(root=project_root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    report_paths = _iter_summary_paths(
        history_root=history_root,
        latest_report=latest_report,
        limit=max(1, int(args.limit)),
    )
    if not report_paths:
        print("[validation-rich-trend] no summary.json artifacts found", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    failed_check_counter: Counter[str] = Counter()
    for path in report_paths:
        payload = _load_json(path)
        if not payload:
            continue
        row = _extract_row(path=path, payload=payload)
        rows.append(row)
        failed_check_counter.update([str(item) for item in row.get("failed_checks", [])])

    if not rows:
        print("[validation-rich-trend] failed to load any summary.json artifacts", file=sys.stderr)
        return 2

    rows.sort(
        key=lambda item: (
            _parse_generated_at(item.get("generated_at")),
            str(item.get("path", "")),
        )
    )

    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else {}
    delta = _build_delta(latest=latest, previous=previous) if previous else {}
    suspect_files = _collect_suspect_files(root=project_root)
    failed_check_top3 = [
        {"check": str(check), "count": int(count)}
        for check, count in failed_check_counter.most_common(3)
    ]

    report_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_only": True,
        "latest_report_mode": latest_report_mode,
        "latest_report_path": str(latest_report) if isinstance(latest_report, Path) else "",
        "canonical_latest_report_path": str(
            _canonical_latest_report_path(history_root=history_root)
        ),
        "history_count": len(rows),
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "failed_check_top3": failed_check_top3,
        "suspect_files": suspect_files,
        "history": rows,
    }

    json_path = output_dir / "validation_rich_trend_report.json"
    md_path = output_dir / "validation_rich_trend_report.md"
    json_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(payload=report_payload), encoding="utf-8")

    print(f"[validation-rich-trend] report json: {json_path}")
    print(f"[validation-rich-trend] report md:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
