"""Build quick-to-plan incremental utility ratio summary (ALH1-0201.T2).

Reads paired-eval run results (quick plan vs full plan) and produces:
    - quick_to_plan_utility_ratio summary (JSON + MD)
    - Dated output under artifacts/benchmark/paired-eval/{run_id}/

Usage:
    python scripts/quick_to_plan_utility_summary.py \\
        --paired-eval-dir artifacts/benchmark/paired-eval/latest \\
        --output-dir artifacts/benchmark/paired-eval/latest

Report-only: does not block on missing inputs; missing fields are "unknown".
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── CLI ──────────────────────────────────────────────────────────────────────


def _argparse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="quick-to-plan utility ratio summary")
    p.add_argument(
        "--paired-eval-dir",
        type=Path,
        required=True,
        help="Directory containing paired-eval run subdirs (quick/, full/)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for summary JSON + MD",
    )
    p.add_argument(
        "--runtime-stats-path",
        type=Path,
        default=None,
        help="Optional runtime stats JSON (for elapsed_ms). If absent, incremental_cost_ms is unknown.",
    )
    return p.parse_args()


# ── Schema version ────────────────────────────────────────────────────────────

SCHEMA_VERSION = "quick_to_plan_utility_summary_v1"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _get_task_success(metrics: dict) -> float | None:
    """Extract task_success from a benchmark metrics dict.

    Tries task_success_hit first (per-case), then falls back to
    utility_hit. Returns None if neither is present.
    """
    if not isinstance(metrics, dict):
        return None
    val = metrics.get("task_success_hit") or metrics.get("utility_hit")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _get_elapsed_ms(payload: dict) -> float | None:
    """Extract total elapsed_ms from a plan-run payload."""
    if not isinstance(payload, dict):
        return None
    val = payload.get("elapsed_ms") or payload.get("total_ms")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_div(a: float | None, b: float | None) -> float | None:
    """Return a/b or None if either is missing or b is zero."""
    if a is None or b is None or b == 0:
        return None
    return a / b


# ── Core ─────────────────────────────────────────────────────────────────────


def build_quick_to_plan_utility_summary(
    *,
    quick_results: dict,
    full_results: dict,
    case_id: str,
) -> dict:
    """Compute utility metrics for one paired eval case.

    Parameters:
        quick_results: parsed JSON from quick-plan benchmark results.json
        full_results:  parsed JSON from full-plan  benchmark results.json
        case_id:      case identifier

    Returns:
        dict with schema_version, case_id, utility metrics, warnings
    """
    warnings: list[str] = []

    # ── task success ────────────────────────────────────────────────────────
    quick_metrics = _get_safe_metrics(quick_results)
    full_metrics = _get_safe_metrics(full_results)

    quick_task_success = _get_task_success(quick_metrics)
    full_task_success = _get_task_success(full_metrics)

    if quick_task_success is None:
        warnings.append(f"{case_id}: quick plan task_success unknown")
    if full_task_success is None:
        warnings.append(f"{case_id}: full plan task_success unknown")

    # ── incremental utility ──────────────────────────────────────────────────
    if quick_task_success is not None and full_task_success is not None:
        incremental_utility = full_task_success - quick_task_success
    else:
        incremental_utility = None

    # ── elapsed_ms ──────────────────────────────────────────────────────────
    quick_elapsed = _get_plan_elapsed_ms(quick_results)
    full_elapsed = _get_plan_elapsed_ms(full_results)

    if quick_elapsed is None:
        warnings.append(f"{case_id}: quick plan elapsed_ms unknown")
    if full_elapsed is None:
        warnings.append(f"{case_id}: full plan elapsed_ms unknown")

    if quick_elapsed is not None and full_elapsed is not None:
        incremental_cost_ms = full_elapsed - quick_elapsed
    else:
        incremental_cost_ms = None

    # ── utility ratio ──────────────────────────────────────────────────────
    utility_ratio = _safe_div(incremental_utility, incremental_cost_ms)

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "quick_plan": {
            "task_success": quick_task_success,
            "elapsed_ms": quick_elapsed,
        },
        "full_plan": {
            "task_success": full_task_success,
            "elapsed_ms": full_elapsed,
        },
        "incremental_utility": incremental_utility,
        "incremental_cost_ms": incremental_cost_ms,
        "utility_ratio": utility_ratio,
        "warnings": warnings,
    }


def _get_safe_metrics(results: dict) -> dict:
    """Return the metrics sub-dict from a benchmark results payload."""
    if not isinstance(results, dict):
        return {}
    # Support top-level metrics key
    if "metrics" in results:
        m = results["metrics"]
        return m if isinstance(m, dict) else {}
    # Fallback: treat the whole payload as metrics
    return {k: v for k, v in results.items() if k != "cases"}


def _get_plan_elapsed_ms(payload: dict) -> float | None:
    """Extract elapsed_ms from a plan-run payload.

    Checks multiple common locations:
        - payload.elapsed_ms / payload.total_ms
        - payload.observability.elapsed_ms
        - payload.stages[].elapsed_ms (summed)
    """
    if not isinstance(payload, dict):
        return None

    # Direct
    direct = _get_elapsed_ms(payload)
    if direct is not None:
        return direct

    # Nested observability
    obs = payload.get("observability") or {}
    if isinstance(obs, dict):
        nested = _get_elapsed_ms(obs)
        if nested is not None:
            return nested

    # Stages list — sum stage elapsed_ms
    stages = payload.get("stages")
    if isinstance(stages, list):
        total = 0.0
        found = False
        for stage in stages:
            if isinstance(stage, dict):
                v = _get_elapsed_ms(stage)
                if v is not None:
                    total += v
                    found = True
        if found:
            return total

    return None


def build_summary_from_dir(
    paired_eval_dir: Path,
) -> tuple[dict, list[str]]:
    """Walk paired_eval_dir and build per-case utility summaries.

    Expected layout:
        paired_eval_dir/
            quick/results.json     # quick plan aggregate results
            full/results.json      # full plan aggregate results
            {case_id}/
                quick/results.json
                full/results.json

    Returns (summary_payload, warnings).
    """
    warnings: list[str] = []
    pair_results: list[dict] = []

    quick_results_path = paired_eval_dir / "quick" / "results.json"
    full_results_path = paired_eval_dir / "full" / "results.json"

    if quick_results_path.exists() and full_results_path.exists():
        # Top-level quick/full pair
        quick_data = _load_json(quick_results_path)
        full_data = _load_json(full_results_path)
        case_id = paired_eval_dir.name or "run"
        pair = build_quick_to_plan_utility_summary(
            quick_results=quick_data,
            full_results=full_data,
            case_id=case_id,
        )
        pair_results.append(pair)
        warnings.extend(pair["warnings"])
    else:
        # Per-case subdirs
        for case_dir in sorted(paired_eval_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            q = case_dir / "quick" / "results.json"
            f = case_dir / "full" / "results.json"
            if not (q.exists() and f.exists()):
                warnings.append(f"{case_dir.name}: missing quick or full results, skipping")
                continue
            quick_data = _load_json(q)
            full_data = _load_json(f)
            pair = build_quick_to_plan_utility_summary(
                quick_results=quick_data,
                full_results=full_data,
                case_id=case_dir.name,
            )
            pair_results.append(pair)
            warnings.extend(pair["warnings"])

    # Aggregate summary
    utility_ratios = [p["utility_ratio"] for p in pair_results if p["utility_ratio"] is not None]
    incremental_utils = [
        p["incremental_utility"] for p in pair_results if p["incremental_utility"] is not None
    ]

    summary: dict = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paired_eval_dir": str(paired_eval_dir),
        "pair_count": len(pair_results),
        "pairs": pair_results,
        "aggregate": {
            "mean_utility_ratio": sum(utility_ratios) / len(utility_ratios)
            if utility_ratios
            else None,
            "mean_incremental_utility": sum(incremental_utils) / len(incremental_utils)
            if incremental_utils
            else None,
            "pairs_with_ratio": len(utility_ratios),
            "pairs_unknown": len(pair_results) - len(utility_ratios),
        },
        "warnings": warnings,
    }

    return summary, warnings


# ── Markdown renderer ─────────────────────────────────────────────────────────


def render_summary_markdown(summary: dict) -> str:
    lines = [
        "# Quick-to-Plan Incremental Utility Summary",
        "",
        f"**Generated**: {summary.get('generated_at', 'unknown')}",
        f"**Schema**:   {SCHEMA_VERSION}",
        f"**Source**:   {summary.get('paired_eval_dir', 'unknown')}",
        "",
        f"**Pairs evaluated**: {summary.get('pair_count', 0)}",
        f"**Pairs with utility_ratio**: {summary['aggregate']['pairs_with_ratio']}",
        f"**Pairs unknown**:            {summary['aggregate']['pairs_unknown']}",
        "",
    ]
    agg = summary.get("aggregate", {})
    mur = agg.get("mean_utility_ratio")
    miu = agg.get("mean_incremental_utility")
    if mur is not None:
        lines.append(f"**Mean utility_ratio**:   {mur:.4f} (task_successΔ / msΔ)")
    else:
        lines.append("**Mean utility_ratio**:   unknown")
    if miu is not None:
        lines.append(f"**Mean incremental_utility**: {miu:.4f} (task_successΔ)")
    else:
        lines.append("**Mean incremental_utility**: unknown")

    lines.append("")
    lines.append("## Per-Case Results")
    lines.append("")
    lines.append(
        "| case_id | quick_task_success | full_task_success | "
        "incremental_utility | incremental_cost_ms | utility_ratio | warnings |"
    )
    lines.append("|---|---|---|---|---|---|---|")

    for p in summary.get("pairs", []):
        qts = (
            f"{p['quick_plan']['task_success']:.3f}"
            if p["quick_plan"]["task_success"] is not None
            else "unknown"
        )
        fts = (
            f"{p['full_plan']['task_success']:.3f}"
            if p["full_plan"]["task_success"] is not None
            else "unknown"
        )
        iu = (
            f"{p['incremental_utility']:.4f}" if p["incremental_utility"] is not None else "unknown"
        )
        ic = (
            f"{p['incremental_cost_ms']:.1f}" if p["incremental_cost_ms"] is not None else "unknown"
        )
        ur = f"{p['utility_ratio']:.6f}" if p["utility_ratio"] is not None else "unknown"
        wrn = "; ".join(p.get("warnings") or []) or "—"
        lines.append(f"| {p['case_id']} | {qts} | {fts} | {iu} | {ic} | {ur} | {wrn} |")

    if summary.get("warnings"):
        lines.append("")
        lines.append("## Top-level Warnings")
        for w in summary["warnings"]:
            lines.append(f"- {w}")

    lines.append("")
    lines.append(
        "**Note**: This is a report-only artifact (PQ-002). utility_ratio does not block release."
    )
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _argparse()

    if not args.paired_eval_dir.exists():
        sys.exit(f"Error: paired-eval-dir not found: {args.paired_eval_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary, warnings = build_summary_from_dir(args.paired_eval_dir)

    # Write JSON
    json_path = args.output_dir / "quick_to_plan_utility_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote: {json_path}")

    # Write Markdown
    md = render_summary_markdown(summary)
    md_path = args.output_dir / "quick_to_plan_utility_summary.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {md_path}")

    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
