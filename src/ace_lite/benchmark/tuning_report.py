from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark.diff import diff_benchmark_results
from ace_lite.benchmark.report import build_results_summary


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _coerce_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if "metrics" not in payload:
        return {}
    if "cases" in payload or "regression" in payload:
        return build_results_summary(payload)
    return payload


def _nested_overlay(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current = root
    for key in path[:-1]:
        child: dict[str, Any] = {}
        current[key] = child
        current = child
    current[path[-1]] = value
    return root


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        elif isinstance(value, dict):
            child: dict[str, Any] = {}
            _deep_merge(child, value)
            target[key] = child
        else:
            target[key] = value


def _float(metrics: dict[str, Any], key: str) -> float:
    return float(metrics.get(key, 0.0) or 0.0)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _build_recommendation(
    *,
    recommendation_id: str,
    rationale: str,
    confidence: str,
    overlay_entries: list[tuple[tuple[str, ...], Any]],
) -> dict[str, Any]:
    overlay: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    for path, value in overlay_entries:
        _deep_merge(overlay, _nested_overlay(path, value))
        items.append(
            {
                "path": ".".join(path),
                "value": value,
            }
        )
    return {
        "id": recommendation_id,
        "report_only": True,
        "confidence": confidence,
        "rationale": rationale,
        "items": items,
        "overlay": overlay,
    }


@dataclass(frozen=True, slots=True)
class BenchmarkTuningReport:
    summary: dict[str, Any]
    baseline_summary: dict[str, Any] | None
    delta: dict[str, float]
    recommendations: list[dict[str, Any]]
    operational_notes: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_only": True,
            "summary": self.summary,
            "baseline_summary": self.baseline_summary,
            "delta": dict(self.delta),
            "recommendations": [deepcopy(item) for item in self.recommendations],
            "recommendation_count": len(self.recommendations),
            "operational_notes": list(self.operational_notes),
        }


def build_benchmark_tuning_report(
    *,
    summary: dict[str, Any],
    baseline_summary: dict[str, Any] | None = None,
) -> BenchmarkTuningReport:
    normalized_summary = _coerce_summary(summary)
    normalized_baseline = _coerce_summary(baseline_summary or {}) if baseline_summary else None
    metrics = (
        dict(normalized_summary.get("metrics", {}))
        if isinstance(normalized_summary.get("metrics"), dict)
        else {}
    )
    tuning_context = (
        dict(normalized_summary.get("tuning_context_summary", {}))
        if isinstance(normalized_summary.get("tuning_context_summary"), dict)
        else {}
    )
    retrieval = (
        dict(tuning_context.get("retrieval", {}))
        if isinstance(tuning_context.get("retrieval"), dict)
        else {}
    )
    chunk = (
        dict(tuning_context.get("chunk", {}))
        if isinstance(tuning_context.get("chunk"), dict)
        else {}
    )
    scip = (
        dict(tuning_context.get("scip", {}))
        if isinstance(tuning_context.get("scip"), dict)
        else {}
    )
    delta: dict[str, float] = {}
    if normalized_baseline is not None:
        diff = diff_benchmark_results(a=normalized_baseline, b=normalized_summary)
        delta = dict(diff.delta)

    recommendations: list[dict[str, Any]] = []
    operational_notes: list[str] = []

    recall_at_k = _float(metrics, "recall_at_k")
    dependency_recall = _float(metrics, "dependency_recall")
    chunk_hit_at_k = _float(metrics, "chunk_hit_at_k")
    precision_at_k = _float(metrics, "precision_at_k")
    noise_rate = _float(metrics, "noise_rate")
    latency_p95_ms = _float(metrics, "latency_p95_ms")
    embedding_fallback_ratio = _float(metrics, "embedding_fallback_ratio")

    top_k_files = _int(retrieval.get("top_k_files"), 8)
    min_candidate_score = _int(retrieval.get("min_candidate_score"), 2)
    chunk_top_k = _int(chunk.get("top_k"), 8)
    scip_base_weight = float(scip.get("base_weight", 0.5) or 0.5)

    if (
        recall_at_k < 0.90
        or dependency_recall < 0.80
        or chunk_hit_at_k < 0.85
    ):
        recommendations.append(
            _build_recommendation(
                recommendation_id="recall_recovery",
                confidence="medium",
                rationale=(
                    "Current benchmark exposes recall or dependency coverage gaps; "
                    "increase retrieval and chunk budgets first as a report-only experiment."
                ),
                overlay_entries=[
                    (("plan", "retrieval", "top_k_files"), min(top_k_files + 2, 32)),
                    (("plan", "chunk", "top_k"), min(chunk_top_k + 2, 24)),
                ],
            )
        )

    if noise_rate > 0.45 and precision_at_k < 0.65:
        recommendations.append(
            _build_recommendation(
                recommendation_id="precision_noise_balance",
                confidence="medium",
                rationale=(
                    "Noise is high while precision is low; raise the candidate threshold "
                    "and slightly narrow file recall while keeping the experiment report-only."
                ),
                overlay_entries=[
                    (
                        ("plan", "retrieval", "min_candidate_score"),
                        min_candidate_score + 1,
                    ),
                    (
                        ("plan", "retrieval", "top_k_files"),
                        max(2, top_k_files - 1),
                    ),
                ],
            )
        )

    if (
        latency_p95_ms > 1200.0
        and recall_at_k >= 0.90
        and dependency_recall >= 0.80
    ):
        recommendations.append(
            _build_recommendation(
                recommendation_id="latency_recovery",
                confidence="low",
                rationale=(
                    "Latency is elevated but recall signals remain stable; try a small "
                    "reduction in context budgets and observe the trade-off."
                ),
                overlay_entries=[
                    (
                        ("plan", "retrieval", "top_k_files"),
                        max(2, top_k_files - 1),
                    ),
                    (
                        ("plan", "chunk", "top_k"),
                        max(4, chunk_top_k - 1),
                    ),
                ],
            )
        )

    if (
        bool(scip.get("enabled"))
        and _float(metrics, "graph_source_provider_loaded_ratio") > 0.50
        and dependency_recall < 0.80
    ):
        recommendations.append(
            _build_recommendation(
                recommendation_id="graph_signal_promotion",
                confidence="low",
                rationale=(
                    "Graph sources are sufficiently loaded but dependency recall is still low; "
                    "trial a small increase to `scip.base_weight` in a report-only pass."
                ),
                overlay_entries=[
                    (
                        ("plan", "scip", "base_weight"),
                        round(min(1.0, scip_base_weight + 0.1), 3),
                    )
                ],
            )
        )

    if embedding_fallback_ratio > 0.15:
        operational_notes.append(
            "embedding_fallback_ratio is elevated; inspect embedding provider and index health "
            "before increasing semantic weight."
        )

    if not recommendations:
        operational_notes.append(
            "Current summary does not trigger any conservative offline tuning rule; "
            "accumulate more benchmark comparisons before generating another candidate overlay."
        )

    return BenchmarkTuningReport(
        summary=normalized_summary,
        baseline_summary=normalized_baseline,
        delta=delta,
        recommendations=recommendations,
        operational_notes=operational_notes,
    )


def build_tuning_markdown(report: BenchmarkTuningReport) -> str:
    payload = report.to_payload()
    summary = report.summary
    metrics = (
        dict(summary.get("metrics", {}))
        if isinstance(summary.get("metrics"), dict)
        else {}
    )
    lines: list[str] = []
    lines.append("# ACE-Lite Benchmark Tuning Report")
    lines.append("")
    lines.append("- Report-only: true")
    lines.append(f"- Repo: {summary.get('repo', '')}")
    lines.append(f"- Case count: {summary.get('case_count', 0)}")
    lines.append(
        f"- Threshold profile: {summary.get('threshold_profile') or '(none)'}"
    )
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    lines.append(
        "- recall_at_k={recall:.4f}, dependency_recall={dep:.4f}, chunk_hit_at_k={chunk:.4f}, precision_at_k={precision:.4f}, noise_rate={noise:.4f}, latency_p95_ms={latency:.2f}".format(
            recall=_float(metrics, "recall_at_k"),
            dep=_float(metrics, "dependency_recall"),
            chunk=_float(metrics, "chunk_hit_at_k"),
            precision=_float(metrics, "precision_at_k"),
            noise=_float(metrics, "noise_rate"),
            latency=_float(metrics, "latency_p95_ms"),
        )
    )
    if report.delta:
        lines.append(
            "- delta(recall_at_k)={recall:+.4f}, delta(precision_at_k)={precision:+.4f}, delta(noise_rate)={noise:+.4f}, delta(latency_p95_ms)={latency:+.2f}".format(
                recall=float(report.delta.get("recall_at_k", 0.0) or 0.0),
                precision=float(report.delta.get("precision_at_k", 0.0) or 0.0),
                noise=float(report.delta.get("noise_rate", 0.0) or 0.0),
                latency=float(report.delta.get("latency_p95_ms", 0.0) or 0.0),
            )
        )
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    if report.recommendations:
        for item in report.recommendations:
            lines.append(
                "- {rid} [{confidence}]: {rationale}".format(
                    rid=item["id"],
                    confidence=item["confidence"],
                    rationale=item["rationale"],
                )
            )
            for entry in item.get("items", []):
                if not isinstance(entry, dict):
                    continue
                lines.append(
                    "  - {path} = {value}".format(
                        path=entry.get("path", ""),
                        value=json.dumps(entry.get("value"), ensure_ascii=False),
                    )
                )
    else:
        lines.append("- No overlay recommendation generated.")
    lines.append("")

    if payload["operational_notes"]:
        lines.append("## Notes")
        lines.append("")
        for note in payload["operational_notes"]:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_tuning_report(
    *,
    input_path: str | Path,
    output_dir: str | Path,
    baseline_path: str | Path | None = None,
) -> dict[str, str]:
    report = build_benchmark_tuning_report(
        summary=_load_json(input_path),
        baseline_summary=_load_json(baseline_path) if baseline_path is not None else None,
    )
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / "tuning_report.json"
    md_path = base / "tuning_report.md"
    json_path.write_text(
        json.dumps(report.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(build_tuning_markdown(report), encoding="utf-8")
    return {
        "tuning_report_json": str(json_path),
        "tuning_report_md": str(md_path),
    }


__all__ = [
    "BenchmarkTuningReport",
    "build_benchmark_tuning_report",
    "build_tuning_markdown",
    "write_tuning_report",
]
