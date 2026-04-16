"""Build plan_quick upgrade outcome summary (ALH1-0202.T2).

Reads plan_quick run artifacts and produces a dated outcome summary
that aggregates `outcome_label` and `upgrade_outcome_hint` fields.

Usage:
    python scripts/plan_quick_outcome_summary.py \\
        --input-dir artifacts/plan-quick/latest \\
        --output-dir artifacts/plan-quick-outcomes/latest

Report-only: does not block on missing inputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── CLI ──────────────────────────────────────────────────────────────────────


def _argparse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="plan_quick upgrade outcome summary")
    p.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing plan_quick run artifacts (JSON files)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for summary JSON + MD",
    )
    return p.parse_args()


# ── Schema version ────────────────────────────────────────────────────────────

SCHEMA_VERSION = "plan_quick_outcome_summary_v1"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ── Core ─────────────────────────────────────────────────────────────────────

OUTCOME_LABELS = (
    "plan_quick_success",
    "plan_quick_timeout_fallback",
    "plan_quick_error",
)


def extract_outcome_record(payload: dict) -> dict:
    """Extract outcome fields from a plan_quick payload.

    Returns a flat record with outcome_label and upgrade_outcome_hint.
    """
    outcome_label = str(payload.get("outcome_label", "") or "")
    if outcome_label not in OUTCOME_LABELS:
        outcome_label = ""

    hint_raw = payload.get("upgrade_outcome_hint") or {}
    hint: dict = {
        "expected_incremental_value": None,
        "expected_cost_ms_band": None,
        "upgrade_recommended": None,
    }
    if isinstance(hint_raw, dict):
        hint = {
            "expected_incremental_value": hint_raw.get("expected_incremental_value"),
            "expected_cost_ms_band": hint_raw.get("expected_cost_ms_band"),
            "upgrade_recommended": hint_raw.get("upgrade_recommended"),
        }

    return {
        "outcome_label": outcome_label,
        "upgrade_recommended": hint.get("upgrade_recommended"),
        "expected_incremental_value": hint.get("expected_incremental_value"),
        "expected_cost_ms_band": hint.get("expected_cost_ms_band"),
    }


def build_summary_from_dir(input_dir: Path) -> tuple[dict, list[str]]:
    """Walk input_dir and aggregate plan_quick outcome records.

    Expected layout:
        input_dir/
            run_YYYY-MM-DD_HH-MM-SS.json   (one plan_quick result per file)
            ...

    Returns (summary_payload, warnings).
    """
    warnings: list[str] = []
    records: list[dict] = []

    if not input_dir.exists():
        warnings.append(f"input-dir not found: {input_dir}")
        empty_summary = _build_empty_summary(input_dir, warnings)
        return empty_summary, warnings

    for json_file in sorted(input_dir.iterdir()):
        if json_file.suffix != ".json":
            continue
        payload = _load_json(json_file)
        if not payload:
            warnings.append(f"empty/invalid JSON skipped: {json_file.name}")
            continue

        record = extract_outcome_record(payload)
        record["source_file"] = json_file.name

        # If outcome_label is unknown, record a warning
        if not record["outcome_label"]:
            warnings.append(f"{json_file.name}: outcome_label missing/unknown")
            record["outcome_label"] = "unknown"

        records.append(record)

    return _build_summary_payload(input_dir, records, warnings), warnings


def _build_empty_summary(input_dir: Path, warnings: list[str]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "run_count": 0,
        "outcome_counts": {},
        "records": [],
        "aggregate": {
            "upgrade_recommended_count": 0,
            "upgrade_not_recommended_count": 0,
            "unknown_count": 0,
            "value_breakdown": {},
        },
        "warnings": warnings,
    }


def _build_summary_payload(input_dir: Path, records: list[dict], warnings: list[str]) -> dict:
    outcome_counter: Counter = Counter(r["outcome_label"] for r in records)
    value_counter: Counter = Counter(
        str(r.get("expected_incremental_value") or "unknown") for r in records
    )

    upgrade_recommended = sum(1 for r in records if r.get("upgrade_recommended") is True)
    upgrade_not_recommended = sum(1 for r in records if r.get("upgrade_recommended") is False)

    summary: dict = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "run_count": len(records),
        "outcome_counts": dict(outcome_counter),
        "records": records,
        "aggregate": {
            "upgrade_recommended_count": upgrade_recommended,
            "upgrade_not_recommended_count": upgrade_not_recommended,
            "unknown_count": len(records) - upgrade_recommended - upgrade_not_recommended,
            "value_breakdown": dict(value_counter),
        },
        "warnings": warnings,
    }
    return summary


# ── Markdown renderer ─────────────────────────────────────────────────────────


def render_summary_markdown(summary: dict) -> str:
    lines = [
        "# Plan_Quick Upgrade Outcome Summary",
        "",
        f"**Generated**: {summary.get('generated_at', 'unknown')}",
        f"**Schema**:   {SCHEMA_VERSION}",
        f"**Input**:    {summary.get('input_dir', 'unknown')}",
        "",
        f"**Total runs**: {summary.get('run_count', 0)}",
        "",
    ]

    agg = summary.get("aggregate", {})
    lines.append("## Upgrade Guidance Counts")
    lines.append("")
    lines.append(f"- **upgrade_recommended=true**:  {agg.get('upgrade_recommended_count', 0)}")
    lines.append(f"- **upgrade_recommended=false**: {agg.get('upgrade_not_recommended_count', 0)}")
    lines.append(f"- **unknown**:                  {agg.get('unknown_count', 0)}")
    lines.append("")

    outcome_counts = summary.get("outcome_counts", {})
    if outcome_counts:
        lines.append("## Outcome Label Counts")
        lines.append("")
        for label, count in sorted(outcome_counts.items()):
            lines.append(f"- **{label}**: {count}")
        lines.append("")

    value_breakdown = agg.get("value_breakdown", {})
    if value_breakdown:
        lines.append("## Incremental Value Breakdown")
        lines.append("")
        for val, count in sorted(value_breakdown.items()):
            lines.append(f"- **{val}**: {count}")
        lines.append("")

    if summary.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for w in summary["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines.append(
        "**Note**: This is a report-only artifact. upgrade_recommended does not block release."
    )
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _argparse()

    if not args.input_dir.exists():
        sys.exit(f"Error: input-dir not found: {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary, warnings = build_summary_from_dir(args.input_dir)

    # Write JSON
    json_path = args.output_dir / "plan_quick_outcome_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote: {json_path}")

    # Write Markdown
    md = render_summary_markdown(summary)
    md_path = args.output_dir / "plan_quick_outcome_summary.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {md_path}")

    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings[:10]:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
