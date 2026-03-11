from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.friction import SEVERITY_ORDER, aggregate_events, load_events


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _severity_value(value: str) -> int:
    return int(SEVERITY_ORDER.get(str(value or "").strip().lower(), 0))


def _apply_filters(
    *,
    events: list[dict[str, Any]],
    min_severity: str,
    status: str,
) -> list[dict[str, Any]]:
    min_value = _severity_value(min_severity)
    status_filter = str(status or "all").strip().lower() or "all"
    out: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        event_severity = str(item.get("severity") or "").strip().lower()
        event_status = str(item.get("status") or "").strip().lower() or "open"
        if _severity_value(event_severity) < min_value:
            continue
        if status_filter != "all" and event_status != status_filter:
            continue
        out.append(item)
    return out


def _build_markdown(summary: dict[str, Any]) -> str:
    aggregate = summary.get("aggregate")
    metrics = aggregate if isinstance(aggregate, dict) else {}
    lines = [
        "# ACE-Lite Friction Report",
        "",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Events path: {summary.get('events_path', '')}",
        f"- Total loaded events: {int(summary.get('loaded_event_count', 0) or 0)}",
        f"- Total filtered events: {int(summary.get('filtered_event_count', 0) or 0)}",
        "- Filters: min_severity={min_severity}, status={status}".format(
            min_severity=str(summary.get("min_severity") or "low"),
            status=str(summary.get("status") or "all"),
        ),
        "",
        "## Summary",
        "",
        f"- Open events: {int(metrics.get('open_count', 0) or 0)}",
        "- Mean time cost (min): {value:.4f}".format(
            value=float(metrics.get("mean_time_cost_min", 0.0) or 0.0)
        ),
        "- P95 time cost (min): {value:.4f}".format(
            value=float(metrics.get("p95_time_cost_min", 0.0) or 0.0)
        ),
        "",
        "## Top Root Causes",
        "",
        "| Root Cause | Count |",
        "| --- | ---: |",
    ]
    for item in metrics.get("top_root_causes", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {name} | {count} |".format(
                name=str(item.get("root_cause") or "(unknown)"),
                count=int(item.get("count", 0) or 0),
            )
        )
    lines.extend(
        [
            "",
            "## Top Stages",
            "",
            "| Stage | Count |",
            "| --- | ---: |",
        ]
    )
    for item in metrics.get("top_stages", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {name} | {count} |".format(
                name=str(item.get("stage") or "(unknown)"),
                count=int(item.get("count", 0) or 0),
            )
        )
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_report(
    *,
    events_path: Path,
    output_dir: Path,
    min_severity: str,
    status: str,
    top_n: int,
    fail_on_open_count: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    loaded_events = load_events(path=events_path)
    filtered_events = _apply_filters(
        events=loaded_events,
        min_severity=min_severity,
        status=status,
    )
    aggregate = aggregate_events(events=filtered_events, top_n=max(1, int(top_n)))
    open_count = int(aggregate.get("open_count", 0) or 0)
    passed = fail_on_open_count < 0 or open_count <= int(fail_on_open_count)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events_path": str(events_path),
        "min_severity": str(min_severity or "low").strip().lower() or "low",
        "status": str(status or "all").strip().lower() or "all",
        "loaded_event_count": len(loaded_events),
        "filtered_event_count": len(filtered_events),
        "top_n": max(1, int(top_n)),
        "fail_on_open_count": int(fail_on_open_count),
        "aggregate": aggregate,
        "passed": passed,
    }
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build friction aggregation artifacts from JSONL event log."
    )
    parser.add_argument(
        "--events-path",
        default="artifacts/friction/events.jsonl",
        help="Friction JSONL path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/friction/latest",
        help="Output directory for summary/report.",
    )
    parser.add_argument(
        "--min-severity",
        default="low",
        choices=["low", "medium", "high", "critical"],
        help="Minimum severity filter.",
    )
    parser.add_argument(
        "--status",
        default="all",
        choices=["all", "open", "resolved", "suppressed"],
        help="Status filter.",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Top list size.")
    parser.add_argument(
        "--fail-on-open-count",
        type=int,
        default=-1,
        help="Fail when filtered open count is greater than this threshold; negative disables.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    events_path = _resolve_path(root=project_root, value=str(args.events_path))
    output_dir = _resolve_path(root=project_root, value=str(args.output_dir))

    summary = build_report(
        events_path=events_path,
        output_dir=output_dir,
        min_severity=str(args.min_severity),
        status=str(args.status),
        top_n=max(1, int(args.top_n)),
        fail_on_open_count=int(args.fail_on_open_count),
    )

    print(f"[friction] summary: {output_dir / 'summary.json'}")
    print(f"[friction] report:  {output_dir / 'report.md'}")
    print(
        "[friction] passed={passed} open_count={open_count}".format(
            passed=bool(summary.get("passed", False)),
            open_count=int(summary.get("aggregate", {}).get("open_count", 0) or 0),
        )
    )
    return 0 if bool(summary.get("passed", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
