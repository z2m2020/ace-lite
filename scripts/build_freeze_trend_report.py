from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark.pq_overlay import resolve_freeze_pq_003_overlay
from ace_lite.benchmark.report_script_support import (
    collect_recent_git_diff_paths_with_runner,
    load_report_json,
    resolve_report_path,
)
from ace_lite.benchmark.report_script_support import (
    safe_float as _safe_float,
)


def _iter_report_paths(*, history_root: Path, latest_report: Path | None, limit: int) -> list[Path]:
    paths: list[Path] = []
    if history_root.exists() and history_root.is_dir():
        for path in history_root.rglob("freeze_regression.json"):
            paths.append(path.resolve())
    if isinstance(latest_report, Path) and latest_report.exists() and latest_report.is_file():
        latest_resolved = latest_report.resolve()
        if latest_resolved not in paths:
            paths.append(latest_resolved)

    # Stable ordering by mtime then path to keep deterministic output.
    paths.sort(key=lambda item: (item.stat().st_mtime, str(item)))
    if limit > 0 and len(paths) > limit:
        paths = paths[-limit:]
    return paths


def _extract_failure_signatures(payload: dict[str, Any]) -> list[str]:
    signatures: list[str] = []
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
        failures_raw = gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if not failures and bool(gate.get("passed", True)):
            continue
        if not failures:
            signatures.append(f"{gate_name}:gate_failed")
            continue
        for item in failures:
            row = item if isinstance(item, dict) else {"metric": str(item)}
            metric = str(row.get("metric") or "unknown")
            signatures.append(f"{gate_name}:{metric}")
    validation_rich_raw = payload.get("validation_rich_benchmark")
    validation_rich = validation_rich_raw if isinstance(validation_rich_raw, dict) else {}
    validation_gate_raw = validation_rich.get("retrieval_control_plane_gate_summary")
    validation_gate = validation_gate_raw if isinstance(validation_gate_raw, dict) else {}
    validation_frontier_gate_raw = validation_rich.get("retrieval_frontier_gate_summary")
    validation_frontier_gate = (
        validation_frontier_gate_raw if isinstance(validation_frontier_gate_raw, dict) else {}
    )
    if validation_gate and not bool(validation_gate.get("gate_passed", False)):
        failed_checks_raw = validation_gate.get("failed_checks")
        failed_checks = failed_checks_raw if isinstance(failed_checks_raw, list) else []
        if failed_checks:
            for item in failed_checks:
                metric = str(item).strip()
                if metric:
                    signatures.append(f"validation_rich_q2_gate:{metric}")
        else:
            signatures.append("validation_rich_q2_gate:gate_failed")
    if validation_frontier_gate and not bool(validation_frontier_gate.get("gate_passed", False)):
        frontier_failed_checks_raw = validation_frontier_gate.get("failed_checks")
        frontier_failed_checks = (
            frontier_failed_checks_raw if isinstance(frontier_failed_checks_raw, list) else []
        )
        if frontier_failed_checks:
            for item in frontier_failed_checks:
                metric = str(item).strip()
                if metric:
                    signatures.append(f"validation_rich_q3_gate:{metric}")
        else:
            signatures.append("validation_rich_q3_gate:gate_failed")
    return signatures


def _extract_row(*, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    tabiv3_summary_raw = payload.get("tabiv3_matrix_summary")
    tabiv3_summary = tabiv3_summary_raw if isinstance(tabiv3_summary_raw, dict) else {}
    tabiv3_means_raw = tabiv3_summary.get("latency_metrics_mean")
    tabiv3_means = tabiv3_means_raw if isinstance(tabiv3_means_raw, dict) else {}

    concept_gate_raw = payload.get("concept_gate")
    concept_gate = concept_gate_raw if isinstance(concept_gate_raw, dict) else {}
    concept_metrics_raw = concept_gate.get("metrics")
    concept_metrics = concept_metrics_raw if isinstance(concept_metrics_raw, dict) else {}

    external_gate_raw = payload.get("external_concept_gate")
    external_gate = external_gate_raw if isinstance(external_gate_raw, dict) else {}
    external_metrics_raw = external_gate.get("metrics")
    external_metrics = external_metrics_raw if isinstance(external_metrics_raw, dict) else {}

    embedding_gate_raw = payload.get("embedding_gate")
    embedding_gate = embedding_gate_raw if isinstance(embedding_gate_raw, dict) else {}
    embedding_means_raw = embedding_gate.get("means")
    embedding_means = embedding_means_raw if isinstance(embedding_means_raw, dict) else {}
    validation_rich_raw = payload.get("validation_rich_benchmark")
    validation_rich = validation_rich_raw if isinstance(validation_rich_raw, dict) else {}
    validation_gate_raw = validation_rich.get("retrieval_control_plane_gate_summary")
    validation_gate = validation_gate_raw if isinstance(validation_gate_raw, dict) else {}
    validation_frontier_gate_raw = validation_rich.get("retrieval_frontier_gate_summary")
    validation_frontier_gate = (
        validation_frontier_gate_raw if isinstance(validation_frontier_gate_raw, dict) else {}
    )
    validation_deep_symbol_raw = validation_rich.get("deep_symbol_summary")
    validation_deep_symbol = (
        validation_deep_symbol_raw if isinstance(validation_deep_symbol_raw, dict) else {}
    )
    validation_native_scip_raw = validation_rich.get("native_scip_summary")
    validation_native_scip = (
        validation_native_scip_raw if isinstance(validation_native_scip_raw, dict) else {}
    )
    validation_probe_raw = validation_rich.get("validation_probe_summary")
    validation_probe = validation_probe_raw if isinstance(validation_probe_raw, dict) else {}
    validation_source_plan_feedback_raw = validation_rich.get(
        "source_plan_validation_feedback_summary"
    )
    validation_source_plan_feedback = (
        validation_source_plan_feedback_raw
        if isinstance(validation_source_plan_feedback_raw, dict)
        else {}
    )
    validation_source_plan_failure_raw = validation_rich.get("source_plan_failure_signal_summary")
    validation_source_plan_failure = (
        validation_source_plan_failure_raw
        if isinstance(validation_source_plan_failure_raw, dict)
        else {}
    )

    return {
        "generated_at": str(payload.get("generated_at", "") or ""),
        "path": str(path),
        "passed": bool(payload.get("passed", False)),
        "tabiv3_latency_p95_ms": _safe_float(tabiv3_means.get("latency_p95_ms"), 0.0),
        "tabiv3_repomap_latency_p95_ms": _safe_float(
            tabiv3_means.get("repomap_latency_p95_ms"), 0.0
        ),
        "concept_precision_at_k": _safe_float(concept_metrics.get("precision_at_k"), 0.0),
        "concept_noise_rate": _safe_float(concept_metrics.get("noise_rate"), 0.0),
        "external_precision_at_k": _safe_float(external_metrics.get("precision_at_k"), 0.0),
        "external_noise_rate": _safe_float(external_metrics.get("noise_rate"), 0.0),
        "embedding_enabled_ratio": _safe_float(embedding_means.get("embedding_enabled_ratio"), 0.0),
        "validation_rich_q2_gate_passed": bool(validation_gate.get("gate_passed", False)),
        "validation_rich_q2_shadow_coverage": _safe_float(
            validation_gate.get("adaptive_router_shadow_coverage"), 0.0
        ),
        "validation_rich_q2_risk_upgrade_gain": _safe_float(
            validation_gate.get("risk_upgrade_precision_gain"), 0.0
        ),
        "validation_rich_q2_latency_p95_ms": _safe_float(
            validation_gate.get("latency_p95_ms"), 0.0
        ),
        "validation_rich_q3_gate_passed": bool(validation_frontier_gate.get("gate_passed", False)),
        "validation_rich_q3_deep_symbol_case_recall": _safe_float(
            validation_frontier_gate.get("deep_symbol_case_recall"), 0.0
        ),
        "validation_rich_q3_native_scip_loaded_rate": _safe_float(
            validation_frontier_gate.get("native_scip_loaded_rate"), 0.0
        ),
        "validation_rich_q3_precision_at_k": _safe_float(
            validation_frontier_gate.get("precision_at_k"), 0.0
        ),
        "validation_rich_q3_noise_rate": _safe_float(
            validation_frontier_gate.get("noise_rate"), 0.0
        ),
        "validation_rich_q3_deep_symbol_case_count": _safe_float(
            validation_deep_symbol.get("case_count"), 0.0
        ),
        "validation_rich_q3_native_scip_document_count_mean": _safe_float(
            validation_native_scip.get("document_count_mean"), 0.0
        ),
        "validation_rich_q4_probe_enabled_ratio": _safe_float(
            validation_probe.get("probe_enabled_ratio"), 0.0
        ),
        "validation_rich_q4_probe_failure_rate": _safe_float(
            validation_probe.get("probe_failure_rate"), 0.0
        ),
        "validation_rich_q4_feedback_present_ratio": _safe_float(
            validation_source_plan_feedback.get("present_ratio"), 0.0
        ),
        "validation_rich_q4_feedback_failure_rate": _safe_float(
            validation_source_plan_feedback.get("failure_rate"), 0.0
        ),
        "validation_rich_q4_feedback_executed_test_count_mean": _safe_float(
            validation_source_plan_feedback.get("executed_test_count_mean"), 0.0
        ),
        "validation_rich_q1_failure_present_ratio": _safe_float(
            validation_source_plan_failure.get("present_ratio"), 0.0
        ),
        "validation_rich_q1_failure_failure_rate": _safe_float(
            validation_source_plan_failure.get("failure_rate"), 0.0
        ),
        "validation_rich_q1_failure_replay_cache_origin_ratio": _safe_float(
            validation_source_plan_failure.get("replay_cache_origin_ratio"), 0.0
        ),
        "validation_probe_summary": dict(validation_probe),
        "source_plan_validation_feedback_summary": dict(validation_source_plan_feedback),
        "source_plan_failure_signal_summary": dict(validation_source_plan_failure),
        "failure_signatures": _extract_failure_signatures(payload),
    }


def _build_delta(*, latest: dict[str, Any], previous: dict[str, Any]) -> dict[str, float]:
    keys = (
        "tabiv3_latency_p95_ms",
        "tabiv3_repomap_latency_p95_ms",
        "concept_precision_at_k",
        "concept_noise_rate",
        "external_precision_at_k",
        "external_noise_rate",
        "embedding_enabled_ratio",
        "validation_rich_q2_shadow_coverage",
        "validation_rich_q2_risk_upgrade_gain",
        "validation_rich_q2_latency_p95_ms",
        "validation_rich_q3_deep_symbol_case_recall",
        "validation_rich_q3_native_scip_loaded_rate",
        "validation_rich_q3_precision_at_k",
        "validation_rich_q3_noise_rate",
        "validation_rich_q3_deep_symbol_case_count",
        "validation_rich_q3_native_scip_document_count_mean",
        "validation_rich_q4_probe_enabled_ratio",
        "validation_rich_q4_probe_failure_rate",
        "validation_rich_q4_feedback_present_ratio",
        "validation_rich_q4_feedback_failure_rate",
        "validation_rich_q4_feedback_executed_test_count_mean",
        "validation_rich_q1_failure_present_ratio",
        "validation_rich_q1_failure_failure_rate",
        "validation_rich_q1_failure_replay_cache_origin_ratio",
    )
    delta: dict[str, float] = {}
    for key in keys:
        delta[key] = _safe_float(latest.get(key), 0.0) - _safe_float(previous.get(key), 0.0)
    return delta


def _render_markdown(*, payload: dict[str, Any]) -> str:
    rows_raw = payload.get("history")
    rows = rows_raw if isinstance(rows_raw, list) else []
    latest_raw = payload.get("latest")
    latest = latest_raw if isinstance(latest_raw, dict) else {}
    previous_raw = payload.get("previous")
    previous = previous_raw if isinstance(previous_raw, dict) else {}

    lines: list[str] = [
        "# Freeze Trend Report",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- History count: {int(payload.get('history_count', 0) or 0)}",
        f"- Failure signatures scanned: {int(payload.get('failure_signature_count', 0) or 0)}",
        "",
    ]

    if latest:
        lines.append("## Latest")
        lines.append("")
        lines.append(f"- Path: `{latest.get('path', '')}`")
        lines.append(f"- Passed: {bool(latest.get('passed', False))}")
        lines.append(
            "- Metrics: tabiv3_p95={tabi:.2f}, tabiv3_repomap_p95={repomap:.2f}, concept_precision={c_prec:.4f}, concept_noise={c_noise:.4f}, external_precision={e_prec:.4f}, external_noise={e_noise:.4f}, embedding_enabled_ratio={emb:.4f}".format(
                tabi=_safe_float(latest.get("tabiv3_latency_p95_ms"), 0.0),
                repomap=_safe_float(latest.get("tabiv3_repomap_latency_p95_ms"), 0.0),
                c_prec=_safe_float(latest.get("concept_precision_at_k"), 0.0),
                c_noise=_safe_float(latest.get("concept_noise_rate"), 0.0),
                e_prec=_safe_float(latest.get("external_precision_at_k"), 0.0),
                e_noise=_safe_float(latest.get("external_noise_rate"), 0.0),
                emb=_safe_float(latest.get("embedding_enabled_ratio"), 0.0),
            )
        )
        lines.append(
            "- Validation-rich Q2 gate: passed={passed}, shadow_coverage={shadow:.4f}, risk_upgrade_gain={gain:.4f}, latency_p95_ms={latency:.2f}".format(
                passed=bool(latest.get("validation_rich_q2_gate_passed", False)),
                shadow=_safe_float(latest.get("validation_rich_q2_shadow_coverage"), 0.0),
                gain=_safe_float(latest.get("validation_rich_q2_risk_upgrade_gain"), 0.0),
                latency=_safe_float(latest.get("validation_rich_q2_latency_p95_ms"), 0.0),
            )
        )
        lines.append(
            "- Validation-rich Q3 gate: passed={passed}, deep_symbol_case_recall={recall:.4f}, native_scip_loaded_rate={native_scip:.4f}, precision_at_k={precision:.4f}, noise_rate={noise:.4f}".format(
                passed=bool(latest.get("validation_rich_q3_gate_passed", False)),
                recall=_safe_float(latest.get("validation_rich_q3_deep_symbol_case_recall"), 0.0),
                native_scip=_safe_float(
                    latest.get("validation_rich_q3_native_scip_loaded_rate"), 0.0
                ),
                precision=_safe_float(latest.get("validation_rich_q3_precision_at_k"), 0.0),
                noise=_safe_float(latest.get("validation_rich_q3_noise_rate"), 0.0),
            )
        )
        lines.append(
            "- Validation-rich Q3 evidence: deep_symbol_case_count={case_count:.4f}, native_scip_document_count_mean={document:.4f}".format(
                case_count=_safe_float(
                    latest.get("validation_rich_q3_deep_symbol_case_count"), 0.0
                ),
                document=_safe_float(
                    latest.get("validation_rich_q3_native_scip_document_count_mean"),
                    0.0,
                ),
            )
        )
        lines.append(
            "- Validation-rich Q4 validation probe: probe_enabled_ratio={enabled:.4f}, probe_failure_rate={failure:.4f}".format(
                enabled=_safe_float(latest.get("validation_rich_q4_probe_enabled_ratio"), 0.0),
                failure=_safe_float(latest.get("validation_rich_q4_probe_failure_rate"), 0.0),
            )
        )
        lines.append(
            "- Validation-rich Q4 source-plan feedback: present_ratio={present:.4f}, failure_rate={failure:.4f}, executed_test_count_mean={executed:.4f}".format(
                present=_safe_float(latest.get("validation_rich_q4_feedback_present_ratio"), 0.0),
                failure=_safe_float(latest.get("validation_rich_q4_feedback_failure_rate"), 0.0),
                executed=_safe_float(
                    latest.get("validation_rich_q4_feedback_executed_test_count_mean"),
                    0.0,
                ),
            )
        )
        lines.append(
            "- Validation-rich Q1 failure signal: present_ratio={present:.4f}, failure_rate={failure:.4f}, replay_cache_origin_ratio={replay:.4f}".format(
                present=_safe_float(latest.get("validation_rich_q1_failure_present_ratio"), 0.0),
                failure=_safe_float(latest.get("validation_rich_q1_failure_failure_rate"), 0.0),
                replay=_safe_float(
                    latest.get("validation_rich_q1_failure_replay_cache_origin_ratio"),
                    0.0,
                ),
            )
        )
        lines.append("")

    if previous:
        delta_raw = payload.get("delta")
        delta = delta_raw if isinstance(delta_raw, dict) else {}
        lines.append("## Delta")
        lines.append("")
        lines.append(f"- Previous path: `{previous.get('path', '')}`")
        lines.append(
            "- Delta: tabiv3_p95={tabi:+.2f}, tabiv3_repomap_p95={repomap:+.2f}, concept_precision={c_prec:+.4f}, concept_noise={c_noise:+.4f}, external_precision={e_prec:+.4f}, external_noise={e_noise:+.4f}, embedding_enabled_ratio={emb:+.4f}, validation_q2_shadow={shadow:+.4f}, validation_q2_gain={gain:+.4f}, validation_q2_latency={latency:+.2f}, validation_q3_recall={q3_recall:+.4f}, validation_q3_native_scip={q3_scip:+.4f}, validation_q3_precision={q3_precision:+.4f}, validation_q3_noise={q3_noise:+.4f}, validation_q3_case_count={q3_case_count:+.4f}, validation_q3_document_count={q3_document:+.4f}".format(
                tabi=_safe_float(delta.get("tabiv3_latency_p95_ms"), 0.0),
                repomap=_safe_float(delta.get("tabiv3_repomap_latency_p95_ms"), 0.0),
                c_prec=_safe_float(delta.get("concept_precision_at_k"), 0.0),
                c_noise=_safe_float(delta.get("concept_noise_rate"), 0.0),
                e_prec=_safe_float(delta.get("external_precision_at_k"), 0.0),
                e_noise=_safe_float(delta.get("external_noise_rate"), 0.0),
                emb=_safe_float(delta.get("embedding_enabled_ratio"), 0.0),
                shadow=_safe_float(delta.get("validation_rich_q2_shadow_coverage"), 0.0),
                gain=_safe_float(delta.get("validation_rich_q2_risk_upgrade_gain"), 0.0),
                latency=_safe_float(delta.get("validation_rich_q2_latency_p95_ms"), 0.0),
                q3_recall=_safe_float(delta.get("validation_rich_q3_deep_symbol_case_recall"), 0.0),
                q3_scip=_safe_float(delta.get("validation_rich_q3_native_scip_loaded_rate"), 0.0),
                q3_precision=_safe_float(delta.get("validation_rich_q3_precision_at_k"), 0.0),
                q3_noise=_safe_float(delta.get("validation_rich_q3_noise_rate"), 0.0),
                q3_case_count=_safe_float(
                    delta.get("validation_rich_q3_deep_symbol_case_count"), 0.0
                ),
                q3_document=_safe_float(
                    delta.get("validation_rich_q3_native_scip_document_count_mean"),
                    0.0,
                ),
            )
        )
        lines.append(
            "- Validation-rich Q4 delta: probe_enabled={probe_enabled:+.4f}, probe_failure={probe_failure:+.4f}, feedback_present={feedback_present:+.4f}, feedback_failure={feedback_failure:+.4f}, feedback_executed_tests={feedback_executed:+.4f}".format(
                probe_enabled=_safe_float(delta.get("validation_rich_q4_probe_enabled_ratio"), 0.0),
                probe_failure=_safe_float(delta.get("validation_rich_q4_probe_failure_rate"), 0.0),
                feedback_present=_safe_float(
                    delta.get("validation_rich_q4_feedback_present_ratio"), 0.0
                ),
                feedback_failure=_safe_float(
                    delta.get("validation_rich_q4_feedback_failure_rate"), 0.0
                ),
                feedback_executed=_safe_float(
                    delta.get("validation_rich_q4_feedback_executed_test_count_mean"),
                    0.0,
                ),
            )
        )
        lines.append(
            "- Validation-rich Q1 delta: failure_present={present:+.4f}, failure_rate={failure:+.4f}, replay_cache_origin={replay:+.4f}".format(
                present=_safe_float(delta.get("validation_rich_q1_failure_present_ratio"), 0.0),
                failure=_safe_float(delta.get("validation_rich_q1_failure_failure_rate"), 0.0),
                replay=_safe_float(
                    delta.get("validation_rich_q1_failure_replay_cache_origin_ratio"),
                    0.0,
                ),
            )
        )
        lines.append("")

    lines.append("## Failure Top3")
    lines.append("")
    top_failures_raw = payload.get("failure_top3")
    top_failures = top_failures_raw if isinstance(top_failures_raw, list) else []
    if top_failures:
        for item in top_failures:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {signature}: {count}".format(
                    signature=str(item.get("signature", "")),
                    count=int(item.get("count", 0) or 0),
                )
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Suspect Files")
    lines.append("")
    suspect_files_raw = payload.get("suspect_files")
    suspect_files = suspect_files_raw if isinstance(suspect_files_raw, list) else []
    if suspect_files:
        for item in suspect_files:
            lines.append(f"- `{item!s}`")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## History")
    lines.append("")
    lines.append(
        "| Generated | Passed | Tabiv3 p95 | Repomap p95 | Concept P | Concept N | External P | External N | Embedding Ratio | Validation Q2 Gate | Validation Q3 Gate |"
    )
    lines.append("| --- | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | :---: |")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {generated} | {passed} | {tabi:.2f} | {repomap:.2f} | {cp:.4f} | {cn:.4f} | {ep:.4f} | {en:.4f} | {emb:.4f} | {vq2} | {vq3} |".format(
                generated=str(row.get("generated_at", "")),
                passed="✅" if bool(row.get("passed", False)) else "❌",
                tabi=_safe_float(row.get("tabiv3_latency_p95_ms"), 0.0),
                repomap=_safe_float(row.get("tabiv3_repomap_latency_p95_ms"), 0.0),
                cp=_safe_float(row.get("concept_precision_at_k"), 0.0),
                cn=_safe_float(row.get("concept_noise_rate"), 0.0),
                ep=_safe_float(row.get("external_precision_at_k"), 0.0),
                en=_safe_float(row.get("external_noise_rate"), 0.0),
                emb=_safe_float(row.get("embedding_enabled_ratio"), 0.0),
                vq2="✅" if bool(row.get("validation_rich_q2_gate_passed", False)) else "❌",
                vq3="✅" if bool(row.get("validation_rich_q3_gate_passed", False)) else "❌",
            )
        )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build trend report from freeze regression history."
    )
    parser.add_argument(
        "--history-root",
        default="artifacts/release-freeze/history",
        help="Directory that contains historical freeze_regression.json files.",
    )
    parser.add_argument(
        "--latest-report",
        default="artifacts/release-freeze/latest/freeze_regression.json",
        help="Latest freeze report path.",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=30,
        help="Max number of reports retained in trend history.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/release-freeze/trend/latest",
        help="Output directory for trend report artifacts.",
    )
    args = parser.parse_args(sys.argv[1:])

    root = Path(__file__).resolve().parents[1]
    history_root = resolve_report_path(root=root, value=str(args.history_root))
    latest_report = resolve_report_path(root=root, value=str(args.latest_report))
    output_dir = resolve_report_path(root=root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    report_paths = _iter_report_paths(
        history_root=history_root,
        latest_report=latest_report,
        limit=max(1, int(args.history_limit)),
    )

    rows: list[dict[str, Any]] = []
    failure_counter: Counter[str] = Counter()
    latest_pq_003_overlay: dict[str, Any] = {}
    for path in report_paths:
        payload = load_report_json(path)
        if not payload:
            continue
        row = _extract_row(path=path, payload=payload)
        rows.append(row)
        failure_counter.update([str(item) for item in row.get("failure_signatures", [])])
        overlay = resolve_freeze_pq_003_overlay(payload)
        if isinstance(overlay, dict) and overlay:
            latest_pq_003_overlay = dict(overlay)

    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    delta = _build_delta(latest=latest, previous=previous) if latest and previous else {}

    top3 = [
        {"signature": str(signature), "count": int(count)}
        for signature, count in failure_counter.most_common(3)
    ]
    suspect_files = collect_recent_git_diff_paths_with_runner(
        root=root,
        subprocess_module=subprocess,
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history_count": len(rows),
        "failure_signature_count": int(sum(failure_counter.values())),
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "failure_top3": top3,
        "suspect_files": suspect_files,
        "history": rows,
    }
    if latest_pq_003_overlay:
        payload["pq_003_overlay"] = latest_pq_003_overlay

    report_json = output_dir / "freeze_trend_report.json"
    report_md = output_dir / "freeze_trend_report.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_render_markdown(payload=payload), encoding="utf-8")

    print(f"[trend] report json: {report_json}")
    print(f"[trend] report md:   {report_md}")
    print(
        "[trend] history_count={count} latest_passed={latest_passed} top_failures={top}".format(
            count=len(rows),
            latest_passed=bool(latest.get("passed", False)) if isinstance(latest, dict) else False,
            top=",".join(item["signature"] for item in top3) if top3 else "-",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
