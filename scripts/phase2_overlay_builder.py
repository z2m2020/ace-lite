"""Build Phase 2 QuickFirst review overlay (ALH1-0205.T2).

Aggregates Phase 2 artifact outputs into a human-readable Markdown review
overlay for maintainers.

Usage:
    python scripts/phase2_overlay_builder.py \\
        --output-dir artifacts/checkpoints/phase2/latest

Reads from:
    - artifacts/observability/quick_to_plan/latest/quick_to_plan_utility_summary.json
    - artifacts/plan-quick-outcomes/latest/plan_quick_outcome_summary.json
    - artifacts/smoke/latest/smoke_summary.json
    - artifacts/doctor/latest/version_drift_report.json (if present)
    - benchmark/cases/paired_eval_cases.yaml (if results exist)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── CLI ──────────────────────────────────────────────────────────────────────


def _argparse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Phase 2 QuickFirst review overlay")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/checkpoints/phase2/latest"),
        help="Output directory for overlay files",
    )
    return p.parse_args()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_json(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


# ── Core ─────────────────────────────────────────────────────────────────────


SCHEMA_VERSION = "phase2_quickfirst_overlay_v1"


def build_overlay(output_dir: Path) -> dict:
    """Build Phase 2 QuickFirst review overlay.

    Reads available Phase 2 artifacts and produces:
    - phase2_quickfirst_overlay.json  (machine-readable)
    - phase2_quickfirst_overlay.md    (human-readable)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Locate Phase 2 artifacts
    utility_summary = _load_json(
        output_dir.parent.parent
        / "observability"
        / "quick_to_plan"
        / "latest"
        / "quick_to_plan_utility_summary.json"
    )
    outcome_summary = _load_json(
        output_dir.parent.parent
        / "plan-quick-outcomes"
        / "latest"
        / "plan_quick_outcome_summary.json"
    )
    smoke_summary = _load_json(output_dir.parent.parent / "smoke" / "latest" / "smoke_summary.json")
    drift_report = _load_json(
        output_dir.parent.parent / "doctor" / "latest" / "version_drift_report.json"
    )

    # Build overlay payload
    overlay: dict = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "phase": "phase2",
        "artifacts": {
            "quick_to_plan_utility_summary": _artifact_summary(utility_summary),
            "plan_quick_outcome_summary": _artifact_summary(outcome_summary),
            "smoke_summary": _artifact_summary(smoke_summary),
            "version_drift_report": _artifact_summary(drift_report),
        },
        "review": _build_review(utility_summary, outcome_summary, smoke_summary, drift_report),
    }

    # Write JSON
    json_path = output_dir / "phase2_quickfirst_overlay.json"
    json_path.write_text(json.dumps(overlay, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote: {json_path}")

    # Write Markdown
    md = _render_markdown(overlay)
    md_path = output_dir / "phase2_quickfirst_overlay.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {md_path}")

    return overlay


def _artifact_summary(artifact: dict | None) -> dict:
    if artifact is None:
        return {"available": False}
    return {
        "available": True,
        "schema_version": artifact.get("schema_version", "unknown"),
        "generated_at": artifact.get("generated_at"),
    }


def _build_review(
    utility_summary: dict | None,
    outcome_summary: dict | None,
    smoke_summary: dict | None,
    drift_report: dict | None,
) -> dict:
    """Build structured review signals from Phase 2 artifacts."""
    signals: dict = {
        "quick_to_plan_ratio": None,
        "upgrade_recommended_rate": None,
        "smoke_healthy": None,
        "has_install_drift": None,
        "has_stale_process": None,
    }

    if utility_summary:
        ratio = utility_summary.get("ratio")
        signals["quick_to_plan_ratio"] = ratio

    if outcome_summary:
        agg = outcome_summary.get("aggregate", {})
        total = outcome_summary.get("run_count", 0)
        if total > 0:
            rec_count = agg.get("upgrade_recommended_count", 0)
            signals["upgrade_recommended_rate"] = rec_count / total

    if smoke_summary:
        signals["smoke_healthy"] = smoke_summary.get("healthy")

    if drift_report:
        signals["has_install_drift"] = drift_report.get("has_install_drift")
        signals["has_stale_process"] = drift_report.get("has_stale_process")

    # Determine overall status
    all_green = (
        signals["smoke_healthy"] is True
        and signals["has_install_drift"] is False
        and signals["has_stale_process"] is False
    )

    return {
        "signals": signals,
        "all_operational_health_green": all_green,
        "ready_for_phase3": bool(
            signals["quick_to_plan_ratio"] is not None
            and signals["upgrade_recommended_rate"] is not None
        ),
    }


def _render_markdown(overlay: dict) -> str:
    review = overlay.get("review", {})
    signals = review.get("signals", {})
    artifacts = overlay.get("artifacts", {})

    lines = [
        "# Phase 2 QuickFirst Review Overlay",
        "",
        f"**Generated**: {overlay.get('generated_at', 'unknown')}",
        f"**Schema**:   {SCHEMA_VERSION}",
        f"**Git SHA**:  {overlay.get('git_sha', 'unknown')}",
        f"**Phase**:    Phase 2 (report-only)",
        "",
    ]

    # Artifact availability
    lines.append("## Artifact Availability")
    lines.append("")
    for name, info in artifacts.items():
        status = "✅ available" if info.get("available") else "❌ not found"
        lines.append(f"- **{name}**: {status}")
    lines.append("")

    # Signals
    lines.append("## Review Signals")
    lines.append("")

    ratio = signals.get("quick_to_plan_ratio")
    if ratio is not None:
        lines.append(
            f"- **quick_to_plan_ratio**: {ratio:.3f}  {'(full plan wins)' if ratio > 1 else '(quick wins)'}"
        )
    else:
        lines.append("- **quick_to_plan_ratio**: TBD")

    rate = signals.get("upgrade_recommended_rate")
    if rate is not None:
        lines.append(f"- **upgrade_recommended_rate**: {rate:.1%}")
    else:
        lines.append("- **upgrade_recommended_rate**: TBD")

    healthy = signals.get("smoke_healthy")
    lines.append(f"- **smoke_healthy**: {healthy if healthy is not None else 'TBD'}")

    drift = signals.get("has_install_drift")
    lines.append(f"- **has_install_drift**: {drift if drift is not None else 'TBD'}")

    stale = signals.get("has_stale_process")
    lines.append(f"- **has_stale_process**: {stale if stale is not None else 'TBD'}")
    lines.append("")

    # Status
    all_green = review.get("all_operational_health_green", False)
    ready = review.get("ready_for_phase3", False)

    lines.append("## Status")
    lines.append("")
    lines.append(f"- **Operational health green**: {'✅ yes' if all_green else '❌ no'}")
    lines.append(f"- **Ready for Phase 3**: {'✅ yes' if ready else '❌ no (insufficient data)'}")
    lines.append("")
    lines.append(
        "**Note**: Phase 2 artifacts are report-only. `upgrade_recommended` is not a release gate."
    )

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _argparse()
    build_overlay(args.output_dir)


if __name__ == "__main__":
    main()
