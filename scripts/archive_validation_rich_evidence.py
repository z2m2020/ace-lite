from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark.report_warning_support import join_string_list, normalize_string_list


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _copy_file(*, source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _copy_tree_if_exists(*, source: Path, destination: Path) -> list[str]:
    if not source.exists() or not source.is_dir():
        return []
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    copied: list[str] = []
    for path in destination.rglob("*"):
        if path.is_file():
            copied.append(str(path))
    return copied


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_retrieval_control_plane_gate_summary(*, payload: dict[str, Any]) -> dict[str, Any]:
    summary_raw = payload.get("retrieval_control_plane_gate_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    normalized: dict[str, Any] = {}
    for key, value in summary.items():
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


def _extract_retrieval_frontier_gate_summary(*, payload: dict[str, Any]) -> dict[str, Any]:
    summary_raw = payload.get("retrieval_frontier_gate_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    normalized: dict[str, Any] = {}
    for key, value in summary.items():
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


def _extract_numeric_summary(
    *,
    payload: dict[str, Any],
    key: str,
) -> dict[str, float]:
    summary_raw = payload.get(key)
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    normalized: dict[str, float] = {}
    for item_key, value in summary.items():
        if not isinstance(item_key, str):
            continue
        try:
            normalized[item_key] = float(value or 0.0)
        except Exception:
            continue
    return normalized


def _render_next_cycle_todo(*, payload: dict[str, Any]) -> str:
    archived_raw = payload.get("archived_files")
    archived_files = archived_raw if isinstance(archived_raw, list) else []
    decision_raw = payload.get("promotion_decision")
    decision = decision_raw if isinstance(decision_raw, dict) else {}
    reasons = normalize_string_list(decision.get("reasons"))
    gate_raw = payload.get("retrieval_control_plane_gate_summary")
    gate = gate_raw if isinstance(gate_raw, dict) else {}
    frontier_gate_raw = payload.get("retrieval_frontier_gate_summary")
    frontier_gate = frontier_gate_raw if isinstance(frontier_gate_raw, dict) else {}
    deep_symbol_raw = payload.get("deep_symbol_summary")
    deep_symbol = deep_symbol_raw if isinstance(deep_symbol_raw, dict) else {}
    native_scip_raw = payload.get("native_scip_summary")
    native_scip = native_scip_raw if isinstance(native_scip_raw, dict) else {}
    validation_probe_raw = payload.get("validation_probe_summary")
    validation_probe = validation_probe_raw if isinstance(validation_probe_raw, dict) else {}
    source_plan_feedback_raw = payload.get("source_plan_validation_feedback_summary")
    source_plan_feedback = (
        source_plan_feedback_raw if isinstance(source_plan_feedback_raw, dict) else {}
    )
    source_plan_failure_raw = payload.get("source_plan_failure_signal_summary")
    source_plan_failure = (
        source_plan_failure_raw if isinstance(source_plan_failure_raw, dict) else {}
    )

    lines = [
        "# Validation-Rich Next Cycle Todo",
        "",
        f"- Archive date: {payload.get('archive_date', '')}",
        f"- Promotion recommendation: {decision.get('recommendation', 'stay_report_only')}",
        "",
        "## Archived Files",
        "",
    ]
    if archived_files:
        for item in archived_files:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None")

    if gate:
        failed_checks = normalize_string_list(gate.get("failed_checks"))
        lines.extend(
            [
                "",
                "## Q2 Retrieval Control Plane Gate",
                "",
                f"- Gate passed: {bool(gate.get('gate_passed', False))}",
                "- Regression evaluated: {evaluated}".format(
                    evaluated=bool(gate.get("regression_evaluated", False))
                ),
                "- Regression detected: {detected}".format(
                    detected=bool(gate.get("benchmark_regression_detected", False))
                ),
                "- Shadow coverage: {shadow:.4f}".format(
                    shadow=float(gate.get("adaptive_router_shadow_coverage", 0.0) or 0.0)
                ),
                "- Risk upgrade gain: {gain:.4f}".format(
                    gain=float(gate.get("risk_upgrade_precision_gain", 0.0) or 0.0)
                ),
                "- Latency P95 ms: {latency:.2f}".format(
                    latency=float(gate.get("latency_p95_ms", 0.0) or 0.0)
                ),
                f"- Failed checks: {join_string_list(failed_checks)}",
            ]
        )

    if frontier_gate:
        frontier_failed_checks = normalize_string_list(frontier_gate.get("failed_checks"))
        lines.extend(
            [
                "",
                "## Q3 Retrieval Frontier Gate",
                "",
                f"- Gate passed: {bool(frontier_gate.get('gate_passed', False))}",
                "- Deep symbol case recall: {recall:.4f}".format(
                    recall=float(frontier_gate.get("deep_symbol_case_recall", 0.0) or 0.0)
                ),
                "- Native SCIP loaded rate: {rate:.4f}".format(
                    rate=float(frontier_gate.get("native_scip_loaded_rate", 0.0) or 0.0)
                ),
                "- Precision at k: {precision:.4f}".format(
                    precision=float(frontier_gate.get("precision_at_k", 0.0) or 0.0)
                ),
                "- Noise rate: {noise:.4f}".format(
                    noise=float(frontier_gate.get("noise_rate", 0.0) or 0.0)
                ),
                f"- Failed checks: {join_string_list(frontier_failed_checks)}",
            ]
        )

    if deep_symbol or native_scip:
        lines.extend(
            [
                "",
                "## Q3 Frontier Evidence",
                "",
                "- Deep symbol case count: {count:.4f}; recall: {recall:.4f}".format(
                    count=float(deep_symbol.get("case_count", 0.0) or 0.0),
                    recall=float(deep_symbol.get("recall", 0.0) or 0.0),
                ),
                "- Native SCIP loaded rate: {loaded:.4f}; document_count_mean={document:.4f}; definition_occurrence_count_mean={definition:.4f}; reference_occurrence_count_mean={reference:.4f}; symbol_definition_count_mean={symbol:.4f}".format(
                    loaded=float(native_scip.get("loaded_rate", 0.0) or 0.0),
                    document=float(native_scip.get("document_count_mean", 0.0) or 0.0),
                    definition=float(
                        native_scip.get("definition_occurrence_count_mean", 0.0) or 0.0
                    ),
                    reference=float(native_scip.get("reference_occurrence_count_mean", 0.0) or 0.0),
                    symbol=float(native_scip.get("symbol_definition_count_mean", 0.0) or 0.0),
                ),
            ]
        )

    if validation_probe:
        lines.extend(
            [
                "",
                "## Q4 Validation Probe Summary",
                "",
                "- Validation test count: {count:.4f}".format(
                    count=float(validation_probe.get("validation_test_count", 0.0) or 0.0)
                ),
                "- Probe enabled ratio: {ratio:.4f}".format(
                    ratio=float(validation_probe.get("probe_enabled_ratio", 0.0) or 0.0)
                ),
                "- Probe executed count mean: {count:.4f}".format(
                    count=float(validation_probe.get("probe_executed_count_mean", 0.0) or 0.0)
                ),
                "- Probe failure rate: {rate:.4f}".format(
                    rate=float(validation_probe.get("probe_failure_rate", 0.0) or 0.0)
                ),
            ]
        )

    if source_plan_feedback:
        lines.extend(
            [
                "",
                "## Q4 Source Plan Validation Feedback",
                "",
                "- Present ratio: {ratio:.4f}".format(
                    ratio=float(source_plan_feedback.get("present_ratio", 0.0) or 0.0)
                ),
                "- Failure rate: {rate:.4f}".format(
                    rate=float(source_plan_feedback.get("failure_rate", 0.0) or 0.0)
                ),
                "- Issue count mean: {count:.4f}".format(
                    count=float(source_plan_feedback.get("issue_count_mean", 0.0) or 0.0)
                ),
                "- Probe issue count mean: {count:.4f}".format(
                    count=float(source_plan_feedback.get("probe_issue_count_mean", 0.0) or 0.0)
                ),
                "- Probe executed count mean: {count:.4f}".format(
                    count=float(source_plan_feedback.get("probe_executed_count_mean", 0.0) or 0.0)
                ),
                "- Selected test count mean: {count:.4f}".format(
                    count=float(source_plan_feedback.get("selected_test_count_mean", 0.0) or 0.0)
                ),
                "- Executed test count mean: {count:.4f}".format(
                    count=float(source_plan_feedback.get("executed_test_count_mean", 0.0) or 0.0)
                ),
            ]
        )
    if source_plan_failure:
        lines.extend(
            [
                "",
                "## Q1 Source Plan Failure Signal Summary",
                "",
                "- Present ratio: {ratio:.4f}".format(
                    ratio=float(source_plan_failure.get("present_ratio", 0.0) or 0.0)
                ),
                "- Failure rate: {rate:.4f}".format(
                    rate=float(source_plan_failure.get("failure_rate", 0.0) or 0.0)
                ),
                "- Issue count mean: {count:.4f}".format(
                    count=float(source_plan_failure.get("issue_count_mean", 0.0) or 0.0)
                ),
                "- Replay cache origin ratio: {replay:.4f}; observability origin ratio: {observability:.4f}; source_plan origin ratio: {source_plan:.4f}; validate_step origin ratio: {validate_step:.4f}".format(
                    replay=float(source_plan_failure.get("replay_cache_origin_ratio", 0.0) or 0.0),
                    observability=float(
                        source_plan_failure.get("observability_origin_ratio", 0.0) or 0.0
                    ),
                    source_plan=float(
                        source_plan_failure.get("source_plan_origin_ratio", 0.0) or 0.0
                    ),
                    validate_step=float(
                        source_plan_failure.get("validate_step_origin_ratio", 0.0) or 0.0
                    ),
                ),
            ]
        )

    lines.extend(["", "## Follow-ups", ""])
    if reasons:
        for reason in reasons:
            lines.append(f"- Resolve: {reason}")
    elif gate and normalize_string_list(gate.get("failed_checks")):
        for item in normalize_string_list(gate.get("failed_checks", [])):
            lines.append(f"- Resolve Q2 gate: {item}")
    elif frontier_gate and normalize_string_list(frontier_gate.get("failed_checks")):
        for item in normalize_string_list(frontier_gate.get("failed_checks", [])):
            lines.append(f"- Resolve Q3 gate: {item}")
    else:
        lines.append("- Review whether `validation_rich_gate.mode` can move beyond `report_only`.")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive validation-rich evidence into a dated directory and seed the next cycle todo."
    )
    parser.add_argument("--date", required=True, help="Archive date in YYYY-MM-DD format.")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--trend-dir", default="")
    parser.add_argument("--stability-dir", default="")
    parser.add_argument("--comparison-dir", default="")
    parser.add_argument("--promotion-decision", default="")
    parser.add_argument("--output-root", default="artifacts/benchmark/validation_rich/archive")
    args = parser.parse_args(sys.argv[1:])

    root = Path(__file__).resolve().parents[1]
    archive_date = str(args.date).strip()
    if not archive_date:
        print("[validation-rich-archive] missing archive date", file=sys.stderr)
        return 2

    output_root = _resolve_path(root=root, value=str(args.output_root))
    dated_root = output_root / archive_date
    dated_root.mkdir(parents=True, exist_ok=True)

    archived_files: list[str] = []
    summary_path = _resolve_path(root=root, value=str(args.summary))
    summary_payload = _load_json(summary_path)
    for name, value in (
        ("summary.json", args.summary),
        ("results.json", args.results),
        ("report.md", args.report),
    ):
        source = (
            summary_path if name == "summary.json" else _resolve_path(root=root, value=str(value))
        )
        if not source.exists():
            print(f"[validation-rich-archive] missing required file: {source}", file=sys.stderr)
            return 2
        archived_files.append(_copy_file(source=source, destination=dated_root / name))

    for folder_name, value in (
        ("trend", args.trend_dir),
        ("stability", args.stability_dir),
        ("comparison", args.comparison_dir),
    ):
        if not str(value).strip():
            continue
        archived_files.extend(
            _copy_tree_if_exists(
                source=_resolve_path(root=root, value=str(value)),
                destination=dated_root / folder_name,
            )
        )

    promotion_decision = {}
    if str(args.promotion_decision).strip():
        decision_path = _resolve_path(root=root, value=str(args.promotion_decision))
        promotion_decision = _load_json(decision_path)
        if decision_path.exists():
            archived_files.append(
                _copy_file(
                    source=decision_path,
                    destination=dated_root / "promotion_decision.json",
                )
            )
            md_path = decision_path.with_suffix(".md")
            if md_path.exists():
                archived_files.append(
                    _copy_file(
                        source=md_path,
                        destination=dated_root / "promotion_decision.md",
                    )
                )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_date": archive_date,
        "dated_root": str(dated_root),
        "archived_files": archived_files,
        "promotion_decision": promotion_decision,
        "retrieval_control_plane_gate_summary": _extract_retrieval_control_plane_gate_summary(
            payload=summary_payload
        ),
        "retrieval_frontier_gate_summary": _extract_retrieval_frontier_gate_summary(
            payload=summary_payload
        ),
        "deep_symbol_summary": _extract_numeric_summary(
            payload=summary_payload,
            key="deep_symbol_summary",
        ),
        "native_scip_summary": _extract_numeric_summary(
            payload=summary_payload,
            key="native_scip_summary",
        ),
        "validation_probe_summary": _extract_numeric_summary(
            payload=summary_payload,
            key="validation_probe_summary",
        ),
        "source_plan_validation_feedback_summary": _extract_numeric_summary(
            payload=summary_payload,
            key="source_plan_validation_feedback_summary",
        ),
        "source_plan_failure_signal_summary": _extract_numeric_summary(
            payload=summary_payload,
            key="source_plan_failure_signal_summary",
        ),
    }
    manifest_path = dated_root / "archive_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    todo_path = dated_root / "next_cycle_todo.md"
    todo_path.write_text(_render_next_cycle_todo(payload=manifest), encoding="utf-8")

    print(f"[validation-rich-archive] dated root: {dated_root}")
    print(f"[validation-rich-archive] manifest:   {manifest_path}")
    print(f"[validation-rich-archive] next todo:  {todo_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
