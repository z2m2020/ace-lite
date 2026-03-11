from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ace_lite.friction import append_event, make_event


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _load_context(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("context JSON must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append a validated MCP friction event into JSONL log."
    )
    parser.add_argument(
        "--output",
        default="artifacts/friction/events.jsonl",
        help="Friction log output path (JSONL).",
    )
    parser.add_argument("--stage", required=True, help="Pipeline/operation stage.")
    parser.add_argument("--expected", required=True, help="Expected behavior.")
    parser.add_argument("--actual", required=True, help="Observed behavior.")
    parser.add_argument("--query", default="", help="Original request/query context.")
    parser.add_argument("--manual-fix", default="", help="Manual workaround/fix text.")
    parser.add_argument(
        "--severity",
        default="medium",
        choices=["low", "medium", "high", "critical"],
        help="Severity level.",
    )
    parser.add_argument(
        "--status",
        default="open",
        choices=["open", "resolved", "suppressed"],
        help="Lifecycle status.",
    )
    parser.add_argument("--source", default="manual", help="Event source identifier.")
    parser.add_argument("--root-cause", default="", help="Root cause bucket.")
    parser.add_argument(
        "--time-cost-min",
        type=float,
        default=0.0,
        help="Estimated lost time in minutes.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Tag value; can be repeated.",
    )
    parser.add_argument(
        "--context-json",
        default="",
        help="Optional JSON object for structured context.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    output_path = _resolve_path(root=project_root, value=str(args.output))
    context = _load_context(str(args.context_json))

    event = make_event(
        stage=str(args.stage),
        expected=str(args.expected),
        actual=str(args.actual),
        query=str(args.query),
        manual_fix=str(args.manual_fix),
        severity=str(args.severity),
        status=str(args.status),
        source=str(args.source),
        root_cause=str(args.root_cause),
        time_cost_min=float(args.time_cost_min),
        tags=args.tag,
        context=context,
    )
    append_event(path=output_path, event=event)

    print(f"[friction] appended: {output_path}")
    print(f"[friction] event_id: {event['event_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
