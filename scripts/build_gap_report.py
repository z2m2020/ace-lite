from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "retrieval_task_gap_report_v1"
GATE_MODE = "report_only"
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalized_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)


def _git_sha(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except Exception:
        return "unknown"
    sha = str(completed.stdout or "").strip()
    return sha if completed.returncode == 0 and sha else "unknown"


def _discover_checkpoint_paths(*, repo_root: Path, date: str) -> tuple[str, str, str, list[str]]:
    warnings: list[str] = []
    checkpoints_root = repo_root / "artifacts" / "checkpoints"
    if not checkpoints_root.exists() or not checkpoints_root.is_dir():
        warnings.append("checkpoint_manifest_unavailable: artifacts/checkpoints not found")
        return "unknown", "", "", warnings

    matches = sorted(checkpoints_root.glob(f"phase*/{date}/checkpoint_manifest.json"), key=str)
    if not matches:
        warnings.append(f"checkpoint_manifest_missing: no dated checkpoint for {date}")
        return "unknown", "", "", warnings

    if len(matches) > 1:
        warnings.append(
            "multiple_checkpoint_manifests_found: using "
            + str(matches[-1].relative_to(repo_root)).replace("\\", "/")
        )

    current = matches[-1]
    try:
        phase = current.relative_to(checkpoints_root).parts[0]
    except Exception:
        phase = "unknown"

    prior_checkpoint = ""
    phase_root = checkpoints_root / phase
    prior_matches = sorted(
        [
            path
            for path in phase_root.glob("*/checkpoint_manifest.json")
            if path != current and path.parent.name < date
        ],
        key=lambda item: item.parent.name,
    )
    if prior_matches:
        prior_checkpoint = str(prior_matches[-1].relative_to(repo_root)).replace("\\", "/")
    else:
        warnings.append(
            f"prior_checkpoint_manifest_missing: no earlier checkpoint found for {phase}"
        )

    checkpoint_id = str(current.relative_to(repo_root)).replace("\\", "/")
    return phase, checkpoint_id, prior_checkpoint, warnings


def _find_input_paths(*, repo_root: Path, date: str) -> dict[str, Path]:
    return {
        "context_report": repo_root
        / "artifacts"
        / "context-reports"
        / date
        / "context_report.json",
        "retrieval_graph_view": repo_root
        / "artifacts"
        / "retrieval-graphs"
        / date
        / "retrieval_graph_view.json",
    }


def _confidence_counts(
    *, context_report: dict[str, Any], retrieval_graph: dict[str, Any]
) -> tuple[int, int, int, int]:
    context_breakdown = context_report.get("confidence_breakdown")
    if isinstance(context_breakdown, dict) and context_breakdown:
        return (
            _safe_int(context_breakdown.get("extracted_count")),
            _safe_int(context_breakdown.get("inferred_count")),
            _safe_int(context_breakdown.get("ambiguous_count")),
            _safe_int(context_breakdown.get("unknown_count")),
        )

    nodes = retrieval_graph.get("nodes")
    if not isinstance(nodes, list):
        return 0, 0, 0, 0

    extracted = inferred = ambiguous = unknown = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        confidence = str(node.get("evidence_confidence") or "").strip().upper()
        if not confidence:
            continue
        if confidence == "EXTRACTED":
            extracted += 1
        elif confidence == "INFERRED":
            inferred += 1
        elif confidence == "AMBIGUOUS":
            ambiguous += 1
        elif confidence == "UNKNOWN":
            unknown += 1
    return extracted, inferred, ambiguous, unknown


def _collect_uncertain_chunks(retrieval_graph: dict[str, Any]) -> tuple[list[str], list[str]]:
    ambiguous_ids: list[str] = []
    unknown_ids: list[str] = []
    nodes = retrieval_graph.get("nodes")
    if not isinstance(nodes, list):
        return ambiguous_ids, unknown_ids

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            continue
        confidence = str(node.get("evidence_confidence") or "").strip().upper()
        if confidence == "AMBIGUOUS":
            ambiguous_ids.append(node_id)
        elif confidence == "UNKNOWN":
            unknown_ids.append(node_id)
    return ambiguous_ids, unknown_ids


def _detect_noise_rate(
    *, retrieval_graph: dict[str, Any], ambiguous_count: int, unknown_count: int
) -> float:
    nodes = retrieval_graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        total = ambiguous_count + unknown_count
        return _normalized_ratio(float(total), float(total)) if total > 0 else 0.0

    file_paths: set[str] = set()
    test_paths = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        path = str(node.get("path") or "").replace("\\", "/")
        if not path:
            continue
        file_paths.add(path)
        if path.startswith("tests/") or "/tests/" in path or path.endswith("_test.py"):
            test_paths += 1

    unsupported_ratio = _normalized_ratio(float(ambiguous_count + unknown_count), float(len(nodes)))
    test_ratio = _normalized_ratio(float(test_paths), float(max(1, len(file_paths))))
    return round(max(unsupported_ratio, test_ratio), 4)


def _overall_severity(
    *, grounded_ratio: float, unknown_ratio: float, truncation_applied: bool, has_support: bool
) -> str:
    if not has_support:
        return "critical"
    if grounded_ratio < 0.5 or unknown_ratio > 0.15:
        return "high"
    if 0.5 <= grounded_ratio <= 0.7 or truncation_applied:
        return "medium"
    return "low"


def _gap_severity_breakdown(gaps: list[dict[str, Any]]) -> dict[str, int]:
    breakdown = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for gap in gaps:
        severity = str(gap.get("severity") or "low").strip().lower()
        if severity in breakdown:
            breakdown[severity] += 1
    return breakdown


def _build_gap_entries(
    *,
    context_report: dict[str, Any],
    retrieval_graph: dict[str, Any],
    warnings: list[str],
    grounded_ratio: float,
    unknown_ratio: float,
    noise_rate: float,
    truncation_applied: bool,
    node_limit_applied: bool,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    ambiguous_ids, unknown_ids = _collect_uncertain_chunks(retrieval_graph)

    if not context_report and not retrieval_graph:
        gaps.append(
            {
                "gap_id": "GAP-001",
                "description": "Task support artifacts are missing; retrieval-to-task alignment could not be assessed directly.",
                "severity": "critical",
                "affected_chunks": [],
                "root_cause": "unknown_evidence",
                "remediation_suggestion": "Generate the dated context report and retrieval graph view before the next checkpoint review.",
            }
        )
        return gaps

    next_id = 1

    if not context_report:
        gaps.append(
            {
                "gap_id": f"GAP-{next_id:03d}",
                "description": "ContextReport input is missing, so task alignment depends only on retrieval graph evidence.",
                "severity": "medium",
                "affected_chunks": [],
                "root_cause": "unknown_evidence",
                "remediation_suggestion": "Publish artifacts/context-reports/<date>/context_report.json alongside the retrieval graph output.",
            }
        )
        next_id += 1

    if not retrieval_graph:
        gaps.append(
            {
                "gap_id": f"GAP-{next_id:03d}",
                "description": "Retrieval graph view input is missing, so chunk-level support and truncation signals are incomplete.",
                "severity": "high",
                "affected_chunks": [],
                "root_cause": "unknown_evidence",
                "remediation_suggestion": "Publish artifacts/retrieval-graphs/<date>/retrieval_graph_view.json for the same review date.",
            }
        )
        next_id += 1

    uncertain = ambiguous_ids + unknown_ids
    if uncertain:
        severity = "high" if unknown_ratio > 0.15 else "medium"
        gaps.append(
            {
                "gap_id": f"GAP-{next_id:03d}",
                "description": "Some retrieved chunks remain ambiguous or unknown, leaving parts of the task weakly grounded.",
                "severity": severity,
                "affected_chunks": uncertain,
                "root_cause": "unknown_evidence",
                "remediation_suggestion": "Expand retrieval budget or seed paths so ambiguous chunks are replaced by directly grounded evidence.",
            }
        )
        next_id += 1

    if retrieval_graph and grounded_ratio < 0.5:
        gaps.append(
            {
                "gap_id": f"GAP-{next_id:03d}",
                "description": "Most retrieved support is indirect or unsupported relative to the planned task.",
                "severity": "high",
                "affected_chunks": uncertain,
                "root_cause": "inferred_only",
                "remediation_suggestion": "Tighten query intent or retrieval heuristics to favor direct candidate chunks for the checkpoint task.",
            }
        )
        next_id += 1

    if truncation_applied or node_limit_applied:
        gaps.append(
            {
                "gap_id": f"GAP-{next_id:03d}",
                "description": "Retrieval results were truncated, so some potentially relevant nodes may be missing from the task review.",
                "severity": "medium",
                "affected_chunks": [],
                "root_cause": "budget_truncation",
                "remediation_suggestion": "Increase the retrieval node budget or record the truncation rationale in the next checkpoint.",
            }
        )
        next_id += 1

    if noise_rate > 0.15:
        gaps.append(
            {
                "gap_id": f"GAP-{next_id:03d}",
                "description": "Retrieved context includes a meaningful amount of low-signal or potentially off-task material.",
                "severity": "medium" if noise_rate <= 0.3 else "high",
                "affected_chunks": uncertain,
                "root_cause": "noise",
                "remediation_suggestion": "Reduce noisy seed paths and prefer artifact-specific candidates that match the planned task surface.",
            }
        )

    return gaps


def _render_status(value: bool) -> str:
    return "✅" if value else "⚠️"


def _render_markdown(payload: dict[str, Any]) -> str:
    summary_raw = payload.get("gap_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    retrieval_signals_raw = payload.get("retrieval_signals")
    retrieval_signals: dict[str, Any] = (
        retrieval_signals_raw if isinstance(retrieval_signals_raw, dict) else {}
    )
    gaps_raw = payload.get("gaps")
    gaps: list[Any] = gaps_raw if isinstance(gaps_raw, list) else []
    warnings_raw = payload.get("warnings")
    warnings: list[Any] = warnings_raw if isinstance(warnings_raw, list) else []

    overall_severity = str(summary.get("overall_severity") or "low").upper()
    grounded_ratio = _safe_float(retrieval_signals.get("grounded_ratio"), 0.0)
    unknown_ratio = _safe_float(retrieval_signals.get("unknown_ratio"), 0.0)
    noise_rate = _safe_float(retrieval_signals.get("noise_rate"), 0.0)
    truncation_applied = bool(retrieval_signals.get("truncation_applied", False))

    executive = (
        f"This report found {int(summary.get('gaps_identified', 0) or 0)} retrieval-to-task gap(s) "
        f"with overall severity **{overall_severity}**. "
        f"Grounded support is {grounded_ratio:.2f}, unknown evidence is {unknown_ratio:.2f}, "
        f"and retrieval {'was' if truncation_applied else 'was not'} truncated."
    )

    lines = [
        "# Retrieval-to-Task Gap Report",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Git SHA: {payload.get('git_sha', '')}",
        f"- Phase: {payload.get('phase', '')}",
        f"- Gate mode: {payload.get('gate_mode', GATE_MODE)}",
        f"- Checkpoint: `{payload.get('checkpoint_id', '')}`",
        f"- Prior checkpoint: `{payload.get('prior_checkpoint_id', '')}`",
        "",
        "## Executive Summary",
        "",
        f"> {executive}",
        "",
        "## Top Findings",
        "",
        "| Severity | Gap ID | Description | Affected chunks | Root cause | Remediation |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]

    if gaps:
        ordered_gaps = sorted(
            [gap for gap in gaps if isinstance(gap, dict)],
            key=lambda item: (
                -SEVERITY_ORDER.get(str(item.get("severity") or "low").strip().lower(), 0),
                str(item.get("gap_id") or ""),
            ),
        )
        for gap in ordered_gaps[:5]:
            affected_raw = gap.get("affected_chunks")
            affected: list[Any] = affected_raw if isinstance(affected_raw, list) else []
            lines.append(
                "| {severity} | {gap_id} | {description} | {affected} | {root_cause} | {remediation} |".format(
                    severity=str(gap.get("severity") or "").upper(),
                    gap_id=str(gap.get("gap_id") or ""),
                    description=str(gap.get("description") or "").replace("|", "\\|"),
                    affected=len(affected),
                    root_cause=str(gap.get("root_cause") or "").replace("|", "\\|"),
                    remediation=str(gap.get("remediation_suggestion") or "").replace("|", "\\|"),
                )
            )
    else:
        lines.append(
            "| LOW | GAP-000 | No actionable gaps identified from available inputs. | 0 | n/a | Continue monitoring in report-only mode. |"
        )

    lines.extend(
        [
            "",
            "## Retrieval Signal Summary",
            "",
            "| Signal | Value | Threshold | Status |",
            "| --- | ---: | --- | --- |",
            f"| grounded_ratio | {grounded_ratio:.4f} | > 0.7 | {_render_status(grounded_ratio > 0.7)} |",
            f"| unknown_ratio | {unknown_ratio:.4f} | < 0.1 | {_render_status(unknown_ratio < 0.1)} |",
            f"| noise_rate | {noise_rate:.4f} | < 0.15 | {_render_status(noise_rate < 0.15)} |",
            f"| truncation_applied | {str(truncation_applied).lower()} | false | {_render_status(not truncation_applied)} |",
        ]
    )

    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.append("")
    return "\n".join(lines)


def build_gap_report(*, date: str, output_root: Path, repo_root: Path) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    git_sha = _git_sha(repo_root)
    warnings: list[str] = []

    input_paths = _find_input_paths(repo_root=repo_root, date=date)
    context_path = input_paths["context_report"]
    retrieval_path = input_paths["retrieval_graph_view"]
    context_report = _load_json(context_path)
    retrieval_graph = _load_json(retrieval_path)

    if not context_report:
        warnings.append(
            f"context_report_missing_or_invalid: {context_path.relative_to(repo_root).as_posix()}"
        )
    elif str(context_report.get("schema_version") or "") != "context_report_v1":
        warnings.append(
            "context_report_schema_unexpected: expected context_report_v1, got "
            f"{context_report.get('schema_version')!r}"
        )

    if not retrieval_graph:
        warnings.append(
            f"retrieval_graph_view_missing_or_invalid: {retrieval_path.relative_to(repo_root).as_posix()}"
        )
    elif str(retrieval_graph.get("schema_version") or "") != "retrieval_graph_view_v1":
        warnings.append(
            "retrieval_graph_view_schema_unexpected: expected retrieval_graph_view_v1, got "
            f"{retrieval_graph.get('schema_version')!r}"
        )

    phase, checkpoint_id, prior_checkpoint_id, checkpoint_warnings = _discover_checkpoint_paths(
        repo_root=repo_root,
        date=date,
    )
    warnings.extend(checkpoint_warnings)

    extracted_count, inferred_count, ambiguous_count, unknown_count = _confidence_counts(
        context_report=context_report,
        retrieval_graph=retrieval_graph,
    )
    total_retrieved_nodes = _safe_int(
        retrieval_graph.get("summary", {}).get("node_count")
        if isinstance(retrieval_graph.get("summary"), dict)
        else 0,
        extracted_count + inferred_count + ambiguous_count + unknown_count,
    )
    if total_retrieved_nodes <= 0:
        total_retrieved_nodes = extracted_count + inferred_count + ambiguous_count + unknown_count

    grounded_ratio = _normalized_ratio(
        float(extracted_count + inferred_count),
        float(max(1, total_retrieved_nodes)),
    )
    unknown_ratio = _normalized_ratio(float(unknown_count), float(max(1, total_retrieved_nodes)))
    retrieval_warnings_raw = retrieval_graph.get("warnings")
    retrieval_warnings: list[Any] = (
        retrieval_warnings_raw if isinstance(retrieval_warnings_raw, list) else []
    )
    truncation_applied = any("truncat" in str(item).lower() for item in retrieval_warnings)
    retrieval_summary_raw = retrieval_graph.get("summary")
    retrieval_summary: dict[str, Any] = (
        retrieval_summary_raw if isinstance(retrieval_summary_raw, dict) else {}
    )
    node_limit_applied = bool(retrieval_summary.get("node_limit_applied", False))
    noise_rate = _detect_noise_rate(
        retrieval_graph=retrieval_graph,
        ambiguous_count=ambiguous_count,
        unknown_count=unknown_count,
    )

    gaps = _build_gap_entries(
        context_report=context_report,
        retrieval_graph=retrieval_graph,
        warnings=warnings,
        grounded_ratio=grounded_ratio,
        unknown_ratio=unknown_ratio,
        noise_rate=noise_rate,
        truncation_applied=truncation_applied,
        node_limit_applied=node_limit_applied,
    )
    severity_breakdown = _gap_severity_breakdown(gaps)
    overall_severity = _overall_severity(
        grounded_ratio=grounded_ratio,
        unknown_ratio=unknown_ratio,
        truncation_applied=(truncation_applied or node_limit_applied),
        has_support=bool(context_report or retrieval_graph),
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "git_sha": git_sha,
        "phase": phase,
        "checkpoint_id": checkpoint_id,
        "prior_checkpoint_id": prior_checkpoint_id,
        "gap_summary": {
            "total_retrieved_nodes": total_retrieved_nodes,
            "direct_matches": extracted_count,
            "indirect_matches": inferred_count,
            "gaps_identified": len(gaps),
            "overall_severity": overall_severity,
            "severity_breakdown": severity_breakdown,
        },
        "gaps": gaps,
        "retrieval_signals": {
            "grounded_ratio": grounded_ratio,
            "unknown_ratio": unknown_ratio,
            "noise_rate": noise_rate,
            "truncation_applied": bool(truncation_applied),
            "node_limit_applied": bool(node_limit_applied),
        },
        "warnings": warnings,
        "gate_mode": GATE_MODE,
    }

    dated_root = output_root / date
    dated_root.mkdir(parents=True, exist_ok=True)
    json_path = dated_root / "gap_report.json"
    md_path = dated_root / "gap_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return {"payload": payload, "json_path": str(json_path), "md_path": str(md_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a dated retrieval-to-task gap report.")
    parser.add_argument("--date", required=True, help="Review date in YYYY-MM-DD format.")
    parser.add_argument(
        "--output-root",
        default="artifacts/gap-reports",
        help="Output root for gap reports (default: artifacts/gap-reports).",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    repo_root = Path(__file__).resolve().parents[1]
    output_root = _resolve_path(root=repo_root, value=str(args.output_root))

    try:
        result = build_gap_report(
            date=str(args.date).strip(), output_root=output_root, repo_root=repo_root
        )
    except Exception as exc:
        print(f"[gap-report] error: {exc}", file=sys.stderr)
        return 1

    print(f"[gap-report] json: {result['json_path']}")
    print(f"[gap-report] md:   {result['md_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
