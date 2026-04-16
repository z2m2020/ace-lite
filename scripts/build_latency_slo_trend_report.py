from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark.report_script_support import (
    collect_recent_git_diff_paths_with_runner,
    load_report_json,
    resolve_report_path,
)
from ace_lite.benchmark.report_script_support import (
    safe_float as _safe_float,
)

STAGE_NAMES = ("memory", "index", "repomap", "augment", "skills", "source_plan", "total")


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


def _iter_report_paths(*, history_root: Path, latest_report: Path | None, limit: int) -> list[Path]:
    paths: list[Path] = []
    if history_root.exists() and history_root.is_dir():
        for path in history_root.rglob("latency_slo_summary.json"):
            paths.append(path.resolve())
    if isinstance(latest_report, Path) and latest_report.exists() and latest_report.is_file():
        latest_resolved = latest_report.resolve()
        if latest_resolved not in paths:
            paths.append(latest_resolved)

    paths.sort(key=lambda item: (item.stat().st_mtime, str(item)))
    if limit > 0 and len(paths) > limit:
        paths = paths[-limit:]
    return paths


def _extract_stage_p95_map(summary: dict[str, Any]) -> dict[str, float]:
    extracted: dict[str, float] = {}
    for stage in STAGE_NAMES:
        stage_raw = summary.get(stage)
        stage_metrics = stage_raw if isinstance(stage_raw, dict) else {}
        extracted[stage] = _safe_float(stage_metrics.get("p95_ms"), 0.0)
    return extracted


def _extract_bucket_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows_raw = payload.get("workload_buckets")
    rows = rows_raw if isinstance(rows_raw, list) else []
    extracted: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        stage_summary_raw = item.get("stage_latency_summary")
        stage_summary = stage_summary_raw if isinstance(stage_summary_raw, dict) else {}
        slo_budget_summary_raw = item.get("slo_budget_summary")
        slo_budget_summary = (
            slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
        )
        extracted.append(
            {
                "workload_bucket": str(item.get("workload_bucket", "") or ""),
                "repo_count": int(item.get("repo_count", 0) or 0),
                "repo_names": [
                    str(value) for value in item.get("repo_names", []) if str(value).strip()
                ]
                if isinstance(item.get("repo_names"), list)
                else [],
                "file_count_mean": _safe_float(item.get("file_count_mean"), 0.0),
                "stage_p95_ms": _extract_stage_p95_map(stage_summary),
                "downgrade_case_rate": _safe_float(
                    slo_budget_summary.get("downgrade_case_rate"), 0.0
                ),
            }
        )
    return extracted


def _extract_row(*, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    stage_latency_summary_raw = payload.get("stage_latency_summary")
    stage_latency_summary = (
        stage_latency_summary_raw if isinstance(stage_latency_summary_raw, dict) else {}
    )
    slo_budget_summary_raw = payload.get("slo_budget_summary")
    slo_budget_summary = slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
    signals_raw = slo_budget_summary.get("signals")
    signals = signals_raw if isinstance(signals_raw, dict) else {}
    adaptive_signal_raw = signals.get("embedding_adaptive_budget_ratio")
    adaptive_signal = adaptive_signal_raw if isinstance(adaptive_signal_raw, dict) else {}

    return {
        "generated_at": str(payload.get("generated_at", "") or ""),
        "path": str(path),
        "repo_count": int(payload.get("repo_count", 0) or 0),
        "has_stage_latency_summary": bool(stage_latency_summary),
        "has_slo_budget_summary": bool(slo_budget_summary),
        "stage_p95_ms": _extract_stage_p95_map(stage_latency_summary),
        "downgrade_case_rate": _safe_float(slo_budget_summary.get("downgrade_case_rate"), 0.0),
        "embedding_adaptive_budget_ratio": _safe_float(adaptive_signal.get("rate"), 0.0),
        "workload_buckets": _extract_bucket_rows(payload),
    }


def _build_delta(*, latest: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    latest_stage_raw = latest.get("stage_p95_ms")
    latest_stage = latest_stage_raw if isinstance(latest_stage_raw, dict) else {}
    previous_stage_raw = previous.get("stage_p95_ms")
    previous_stage = previous_stage_raw if isinstance(previous_stage_raw, dict) else {}

    return {
        "stage_p95_ms": {
            stage: _safe_float(latest_stage.get(stage), 0.0)
            - _safe_float(previous_stage.get(stage), 0.0)
            for stage in STAGE_NAMES
        },
        "downgrade_case_rate": _safe_float(latest.get("downgrade_case_rate"), 0.0)
        - _safe_float(previous.get("downgrade_case_rate"), 0.0),
        "embedding_adaptive_budget_ratio": _safe_float(
            latest.get("embedding_adaptive_budget_ratio"), 0.0
        )
        - _safe_float(previous.get("embedding_adaptive_budget_ratio"), 0.0),
    }


def _build_bucket_deltas(
    *, latest: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    latest_rows_raw = latest.get("workload_buckets")
    latest_rows = latest_rows_raw if isinstance(latest_rows_raw, list) else []
    previous_rows_raw = previous.get("workload_buckets")
    previous_rows = previous_rows_raw if isinstance(previous_rows_raw, list) else []

    latest_map = {
        str(item.get("workload_bucket", "") or ""): item
        for item in latest_rows
        if isinstance(item, dict)
    }
    previous_map = {
        str(item.get("workload_bucket", "") or ""): item
        for item in previous_rows
        if isinstance(item, dict)
    }

    rows: list[dict[str, Any]] = []
    for bucket_name in sorted(set(latest_map) | set(previous_map)):
        latest_bucket = latest_map.get(bucket_name, {})
        previous_bucket = previous_map.get(bucket_name, {})
        latest_stage_raw = latest_bucket.get("stage_p95_ms")
        latest_stage = latest_stage_raw if isinstance(latest_stage_raw, dict) else {}
        previous_stage_raw = previous_bucket.get("stage_p95_ms")
        previous_stage = previous_stage_raw if isinstance(previous_stage_raw, dict) else {}
        rows.append(
            {
                "workload_bucket": bucket_name,
                "latest_repo_count": int(latest_bucket.get("repo_count", 0) or 0),
                "previous_repo_count": int(previous_bucket.get("repo_count", 0) or 0),
                "latest_file_count_mean": _safe_float(latest_bucket.get("file_count_mean"), 0.0),
                "previous_file_count_mean": _safe_float(
                    previous_bucket.get("file_count_mean"), 0.0
                ),
                "stage_p95_delta_ms": {
                    stage: _safe_float(latest_stage.get(stage), 0.0)
                    - _safe_float(previous_stage.get(stage), 0.0)
                    for stage in STAGE_NAMES
                },
                "downgrade_case_rate_delta": _safe_float(
                    latest_bucket.get("downgrade_case_rate"), 0.0
                )
                - _safe_float(previous_bucket.get("downgrade_case_rate"), 0.0),
            }
        )
    return rows


def _render_markdown(*, payload: dict[str, Any]) -> str:
    rows_raw = payload.get("history")
    rows = rows_raw if isinstance(rows_raw, list) else []
    latest_raw = payload.get("latest")
    latest = latest_raw if isinstance(latest_raw, dict) else {}
    previous_raw = payload.get("previous")
    previous = previous_raw if isinstance(previous_raw, dict) else {}
    delta_raw = payload.get("delta")
    delta = delta_raw if isinstance(delta_raw, dict) else {}
    stage_delta_raw = delta.get("stage_p95_ms")
    stage_delta = stage_delta_raw if isinstance(stage_delta_raw, dict) else {}

    lines: list[str] = [
        "# Latency And SLO Trend Report",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Report only: {bool(payload.get('report_only', True))}",
        f"- History count: {int(payload.get('history_count', 0) or 0)}",
        "",
    ]

    if latest:
        latest_stage_raw = latest.get("stage_p95_ms")
        latest_stage = latest_stage_raw if isinstance(latest_stage_raw, dict) else {}
        lines.extend(
            [
                "## Latest",
                "",
                f"- Path: `{latest.get('path', '')}`",
                f"- Repo count: {int(latest.get('repo_count', 0) or 0)}",
                "- Coverage: stage_latency_summary={stage}, slo_budget_summary={slo}".format(
                    stage="yes" if bool(latest.get("has_stage_latency_summary", False)) else "no",
                    slo="yes" if bool(latest.get("has_slo_budget_summary", False)) else "no",
                ),
                "- Metrics: total_p95={total:.2f}, index_p95={index:.2f}, repomap_p95={repomap:.2f}, downgrade_case_rate={downgrade:.4f}, embedding_adaptive_budget_ratio={adaptive:.4f}".format(
                    total=_safe_float(latest_stage.get("total"), 0.0),
                    index=_safe_float(latest_stage.get("index"), 0.0),
                    repomap=_safe_float(latest_stage.get("repomap"), 0.0),
                    downgrade=_safe_float(latest.get("downgrade_case_rate"), 0.0),
                    adaptive=_safe_float(latest.get("embedding_adaptive_budget_ratio"), 0.0),
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
                "- Previous coverage: stage_latency_summary={stage}, slo_budget_summary={slo}".format(
                    stage="yes" if bool(previous.get("has_stage_latency_summary", False)) else "no",
                    slo="yes" if bool(previous.get("has_slo_budget_summary", False)) else "no",
                ),
            ]
        )
        if not bool(previous.get("has_stage_latency_summary", False)) or not bool(
            previous.get("has_slo_budget_summary", False)
        ):
            lines.append(
                "- Delta note: previous baseline is missing stage or SLO coverage, so zero-filled fallback remains report-only context."
            )
        lines.extend(
            [
                "| Metric | Delta |",
                "| --- | ---: |",
            ]
        )
        for stage in STAGE_NAMES:
            lines.append(
                "| {metric} | {delta:+.2f} |".format(
                    metric=f"{stage}_p95_ms",
                    delta=_safe_float(stage_delta.get(stage), 0.0),
                )
            )
        lines.append(
            "| downgrade_case_rate | {delta:+.4f} |".format(
                delta=_safe_float(delta.get("downgrade_case_rate"), 0.0)
            )
        )
        lines.append(
            "| embedding_adaptive_budget_ratio | {delta:+.4f} |".format(
                delta=_safe_float(delta.get("embedding_adaptive_budget_ratio"), 0.0)
            )
        )
        lines.append("")

    lines.extend(
        [
            "## Bucket Deltas",
            "",
            "| Bucket | Latest Repo Count | Previous Repo Count | Total Delta (ms) | Index Delta (ms) | Repomap Delta (ms) | Downgrade Delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    bucket_deltas_raw = payload.get("bucket_deltas")
    bucket_deltas = bucket_deltas_raw if isinstance(bucket_deltas_raw, list) else []
    if bucket_deltas:
        for item in bucket_deltas:
            if not isinstance(item, dict):
                continue
            stage_deltas_raw = item.get("stage_p95_delta_ms")
            stage_deltas = stage_deltas_raw if isinstance(stage_deltas_raw, dict) else {}
            lines.append(
                "| {bucket} | {latest_repo_count} | {previous_repo_count} | {total:+.2f} | {index:+.2f} | {repomap:+.2f} | {downgrade:+.4f} |".format(
                    bucket=str(item.get("workload_bucket", "") or ""),
                    latest_repo_count=int(item.get("latest_repo_count", 0) or 0),
                    previous_repo_count=int(item.get("previous_repo_count", 0) or 0),
                    total=_safe_float(stage_deltas.get("total"), 0.0),
                    index=_safe_float(stage_deltas.get("index"), 0.0),
                    repomap=_safe_float(stage_deltas.get("repomap"), 0.0),
                    downgrade=_safe_float(item.get("downgrade_case_rate_delta"), 0.0),
                )
            )
    else:
        lines.append("| None | 0 | 0 | +0.00 | +0.00 | +0.00 | +0.0000 |")
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
        "| Generated | Repo Count | Total P95 | Index P95 | Repomap P95 | Downgrade Rate | Adaptive Budget |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_raw = row.get("stage_p95_ms")
        stage = stage_raw if isinstance(stage_raw, dict) else {}
        lines.append(
            "| {generated} | {repo_count} | {total:.2f} | {index:.2f} | {repomap:.2f} | {downgrade:.4f} | {adaptive:.4f} |".format(
                generated=str(row.get("generated_at", "")),
                repo_count=int(row.get("repo_count", 0) or 0),
                total=_safe_float(stage.get("total"), 0.0),
                index=_safe_float(stage.get("index"), 0.0),
                repomap=_safe_float(stage.get("repomap"), 0.0),
                downgrade=_safe_float(row.get("downgrade_case_rate"), 0.0),
                adaptive=_safe_float(row.get("embedding_adaptive_budget_ratio"), 0.0),
            )
        )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a report-only latency/SLO trend summary from benchmark artifacts."
    )
    parser.add_argument(
        "--history-root",
        default="artifacts/benchmark/matrix",
        help="Directory containing dated latency_slo_summary.json artifacts.",
    )
    parser.add_argument(
        "--latest-report",
        default="",
        help="Optional path to a latest latency_slo_summary.json artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmark/matrix/latency_slo_trend/latest",
        help="Directory to write latency_slo_trend_report outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of history artifacts to include.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    history_root = resolve_report_path(root=project_root, value=str(args.history_root))
    latest_report = (
        resolve_report_path(root=project_root, value=str(args.latest_report))
        if str(args.latest_report).strip()
        else None
    )
    output_dir = resolve_report_path(root=project_root, value=str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    report_paths = _iter_report_paths(
        history_root=history_root,
        latest_report=latest_report,
        limit=max(1, int(args.limit)),
    )
    if not report_paths:
        print("[latency-slo-trend] no latency_slo_summary.json artifacts found", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    for path in report_paths:
        payload = load_report_json(path)
        if not payload:
            continue
        rows.append(_extract_row(path=path, payload=payload))

    if not rows:
        print(
            "[latency-slo-trend] failed to load any latency_slo_summary.json artifacts",
            file=sys.stderr,
        )
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
    bucket_deltas = _build_bucket_deltas(latest=latest, previous=previous) if previous else []
    suspect_files = collect_recent_git_diff_paths_with_runner(
        root=project_root,
        subprocess_module=subprocess,
    )

    report_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_only": True,
        "history_count": len(rows),
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "bucket_deltas": bucket_deltas,
        "suspect_files": suspect_files,
        "history": rows,
    }

    json_path = output_dir / "latency_slo_trend_report.json"
    md_path = output_dir / "latency_slo_trend_report.md"
    json_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(payload=report_payload), encoding="utf-8")

    print(f"[latency-slo-trend] report json: {json_path}")
    print(f"[latency-slo-trend] report md:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
