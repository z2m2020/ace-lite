"""Build smoke_summary_v1 from a plan run artifact (ALH1-0204.T1).

Reads a plan JSON output (from ``ace-lite plan --output-json``) and produces
a ``smoke_summary_v1`` JSON artifact that captures the key smoke-test signals.

Usage:
    python scripts/smoke_summary.py \\
        --input artifacts/plan/latest/plan.json \\
        --output artifacts/smoke/latest/smoke_summary.json

Report-only: does not block on missing inputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── CLI ──────────────────────────────────────────────────────────────────────


def _argparse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build smoke_summary_v1 from plan artifact")
    p.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to plan JSON output (from ace-lite plan --output-json)",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for smoke_summary.json",
    )
    return p.parse_args()


# ── Schema version ────────────────────────────────────────────────────────────

SCHEMA_VERSION = "smoke_summary_v1"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"Error: input not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Core ─────────────────────────────────────────────────────────────────────


def extract_smoke_record(plan_payload: dict) -> dict:
    """Extract smoke-test signals from a plan payload.

    Returns a flat record with the key fields that indicate whether the
    plan run was healthy enough to be used as a smoke signal.
    """
    source_plan = plan_payload.get("source_plan") or {}

    # Timeout / fallback signal
    timed_out = bool(plan_payload.get("_plan_timeout_fallback"))

    # Elapsed time
    elapsed_ms = _resolve_elapsed_ms(plan_payload)

    # Candidate file count
    candidate_files = source_plan.get("candidate_files") or []
    file_count = len(candidate_files) if isinstance(candidate_files, list) else 0

    # Step count
    steps = source_plan.get("steps") or []
    step_count = len(steps) if isinstance(steps, list) else 0

    # Validation result
    validation = source_plan.get("validation") or {}
    has_validation = bool(validation)
    validation_passed = bool(validation.get("passed")) if isinstance(validation, dict) else False

    # Quick-plan signal
    is_quick = bool(plan_payload.get("quick_plan") or plan_payload.get("_plan_quick_hit"))

    # Error signal (if outcome_label is set by plan_quick)
    outcome_label = str(plan_payload.get("outcome_label") or "")

    return {
        "timed_out": timed_out,
        "is_quick": is_quick,
        "elapsed_ms": elapsed_ms,
        "file_count": file_count,
        "step_count": step_count,
        "has_validation": has_validation,
        "validation_passed": validation_passed,
        "outcome_label": outcome_label,
    }


def _resolve_elapsed_ms(payload: dict) -> float | None:
    """Resolve elapsed_ms from payload.

    Follows the same resolution order as benchmark elapsed_ms:
    1. Top-level elapsed_ms
    2. observability.elapsed_ms
    3. Sum of stage elapsed_ms values
    """
    if "elapsed_ms" in payload:
        return float(payload["elapsed_ms"])
    obs = payload.get("observability") or {}
    if isinstance(obs, dict) and "elapsed_ms" in obs:
        return float(obs["elapsed_ms"])
    stages = payload.get("stages") or []
    if isinstance(stages, list):
        total = sum(float(s.get("elapsed_ms", 0)) for s in stages if isinstance(s, dict))
        if total > 0:
            return total
    return None


def build_smoke_summary(plan_input: Path) -> dict:
    """Build a smoke_summary_v1 artifact from a plan JSON file.

    Returns a dict with schema_version, generated_at, and the smoke record.
    """
    payload = _load_json(plan_input)

    record = extract_smoke_record(payload)

    summary: dict = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_input": str(plan_input),
        "smoke": record,
        "healthy": _is_healthy(record),
    }
    return summary


def _is_healthy(record: dict) -> bool:
    """Determine if a smoke record represents a healthy run.

    A run is considered healthy when:
    - It did NOT time out
    - It produced at least one candidate file
    - It produced at least one step
    """
    if record["timed_out"]:
        return False
    if record["file_count"] == 0:
        return False
    if record["step_count"] == 0:
        return False
    return True


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _argparse()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    summary = build_smoke_summary(args.input)

    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
