from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.benchmark.report import METRIC_ORDER, build_results_summary


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _coerce_results_like(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept either results.json or summary.json and return a results-like dict."""
    if not isinstance(payload, dict):
        return {}
    if "metrics" not in payload:
        return {}
    if "cases" in payload or "regression" in payload:
        return payload
    # Looks like summary.json; wrap it so build_results_summary can be reused safely.
    return {"metrics": payload.get("metrics", {}), **payload}


@dataclass(frozen=True, slots=True)
class BenchmarkDiff:
    summary_a: dict[str, Any]
    summary_b: dict[str, Any]
    delta: dict[str, float]

    def to_payload(self) -> dict[str, Any]:
        return {
            "generated_at": self.summary_b.get("generated_at") or self.summary_a.get("generated_at"),
            "a": self.summary_a,
            "b": self.summary_b,
            "delta": dict(self.delta),
        }


def diff_benchmark_results(*, a: dict[str, Any], b: dict[str, Any]) -> BenchmarkDiff:
    a_results_like = _coerce_results_like(a)
    b_results_like = _coerce_results_like(b)

    summary_a = build_results_summary(a_results_like)
    summary_b = build_results_summary(b_results_like)

    metrics_a_raw = summary_a.get("metrics")
    metrics_b_raw = summary_b.get("metrics")
    metrics_a: dict[str, Any] = metrics_a_raw if isinstance(metrics_a_raw, dict) else {}
    metrics_b: dict[str, Any] = metrics_b_raw if isinstance(metrics_b_raw, dict) else {}

    delta: dict[str, float] = {}
    for key in METRIC_ORDER:
        delta[key] = float(metrics_b.get(key, 0.0) or 0.0) - float(metrics_a.get(key, 0.0) or 0.0)

    return BenchmarkDiff(summary_a=summary_a, summary_b=summary_b, delta=delta)


def _format_metric(name: str, value: Any, *, signed: bool = False) -> str:
    number = float(value or 0.0)
    if name in {
        "repomap_latency_p95_ms",
        "repomap_latency_median_ms",
        "latency_p95_ms",
        "latency_median_ms",
    }:
        return f"{number:+.2f}" if signed else f"{number:.2f}"
    return f"{number:+.4f}" if signed else f"{number:.4f}"


def build_diff_markdown(diff: BenchmarkDiff) -> str:
    a = diff.summary_a
    b = diff.summary_b
    metrics_a = a.get("metrics", {}) if isinstance(a.get("metrics"), dict) else {}
    metrics_b = b.get("metrics", {}) if isinstance(b.get("metrics"), dict) else {}

    lines: list[str] = []
    lines.append("# ACE-Lite Benchmark Diff")
    lines.append("")
    lines.append(f"- A: repo={a.get('repo','')} cases={a.get('case_count', 0)}")
    lines.append(f"- B: repo={b.get('repo','')} cases={b.get('case_count', 0)}")
    lines.append("")

    lines.append("## Metrics (A)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for metric in METRIC_ORDER:
        lines.append(f"| {metric} | {_format_metric(metric, metrics_a.get(metric, 0.0))} |")
    lines.append("")

    lines.append("## Metrics (B)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for metric in METRIC_ORDER:
        lines.append(f"| {metric} | {_format_metric(metric, metrics_b.get(metric, 0.0))} |")
    lines.append("")

    lines.append("## Delta (B - A)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for metric in METRIC_ORDER:
        lines.append(f"| {metric} | {_format_metric(metric, diff.delta.get(metric, 0.0), signed=True)} |")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_diff(
    *,
    a_path: str | Path,
    b_path: str | Path,
    output_dir: str | Path,
) -> dict[str, str]:
    a_payload = _load_json(a_path)
    b_payload = _load_json(b_path)
    diff = diff_benchmark_results(a=a_payload, b=b_payload)

    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / "diff.json"
    md_path = base / "diff.md"

    json_path.write_text(
        json.dumps(diff.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(build_diff_markdown(diff), encoding="utf-8")

    return {"diff_json": str(json_path), "diff_md": str(md_path)}


__all__ = [
    "BenchmarkDiff",
    "build_diff_markdown",
    "diff_benchmark_results",
    "write_diff",
]

