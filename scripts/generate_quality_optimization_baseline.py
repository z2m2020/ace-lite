#!/usr/bin/env python3
"""Generate the PRD-91 quality optimization baseline bundle.

This script composes the existing manifest and hotspot scan scripts into a
single Phase-0 baseline artifact for the PRD-91 execution plan.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "artifacts" / "quality-optimization" / "baseline"
)
CORE_METRICS: tuple[tuple[str, str], ...] = (
    ("M-ARCH-01", "dict_fallback_sites"),
    ("M-CACHE-01", "cache_deepcopy_count"),
    ("M-REL-01", "broad_exception_sites"),
)


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def _default_paths(
    *,
    root: Path,
    output_dir: Path,
    snapshot_date: date,
) -> dict[str, Path]:
    return {
        "manifest": output_dir / "benchmark_manifest.json",
        "hotspots": output_dir / "static_hotspots.json",
        "baseline": output_dir / "baseline_metrics.json",
        "dated_baseline": output_dir / f"baseline_metrics_{snapshot_date.isoformat()}.json",
        "output_dir": output_dir,
        "root": root,
    }


def _build_manifest_command(*, root: Path, manifest_path: Path) -> list[str]:
    return [
        sys.executable,
        str((root / "scripts" / "quality_benchmark_manifest.py").resolve()),
        "--output",
        str(manifest_path.resolve()),
    ]


def _build_hotspot_command(
    *,
    root: Path,
    hotspot_path: Path,
    include_tests: bool,
) -> list[str]:
    command = [
        sys.executable,
        str((root / "scripts" / "scan_quality_hotspots.py").resolve()),
        "--output",
        str(hotspot_path.resolve()),
    ]
    if not include_tests:
        command.append("--no-tests")
    return command


def _run_command(*, name: str, command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return CommandResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_baseline_summary(
    *,
    manifest_payload: dict[str, Any],
    hotspot_payload: dict[str, Any],
    root: Path,
    paths: dict[str, Path],
    snapshot_date: date,
) -> dict[str, Any]:
    scan_summary_raw = hotspot_payload.get("scan_summary")
    scan_summary = scan_summary_raw if isinstance(scan_summary_raw, dict) else {}
    metrics: dict[str, Any] = {}
    for metric_id, metric_name in CORE_METRICS:
        metric_summary_raw = scan_summary.get(metric_id)
        metric_summary = (
            metric_summary_raw if isinstance(metric_summary_raw, dict) else {}
        )
        metrics[metric_name] = {
            "metric_id": metric_id,
            "count": int(metric_summary.get("total_count", 0) or 0),
        }

    return {
        "schema_version": "quality_optimization_baseline_v1",
        "prd": "91_QUALITY_OPTIMIZATION_PRD_2026-04-12",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": snapshot_date.isoformat(),
        "root": str(root.resolve()),
        "phase": "Phase 0",
        "tasks": {
            "QO-0001": {
                "status": "completed",
                "artifact": str(paths["manifest"].resolve()),
                "summary": {
                    "metrics_count": len(manifest_payload.get("metrics", {})),
                    "streams_count": len(manifest_payload.get("streams", {})),
                    "phases_count": len(manifest_payload.get("phases", {})),
                },
            },
            "QO-0002": {
                "status": "completed",
                "artifact": str(paths["hotspots"].resolve()),
                "summary": {
                    "metric_ids": sorted(scan_summary.keys()),
                },
            },
            "QO-0003": {
                "status": "completed",
                "artifact": str(paths["baseline"].resolve()),
                "summary": metrics,
            },
        },
        "metrics": metrics,
        "source_artifacts": {
            "benchmark_manifest": str(paths["manifest"].resolve()),
            "static_hotspots": str(paths["hotspots"].resolve()),
        },
    }


def run_quality_optimization_baseline(
    *,
    root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    python_exe: str = sys.executable,
    include_tests: bool = True,
    snapshot_date: str | None = None,
) -> dict[str, Any]:
    _ = python_exe
    resolved_root = root.resolve()
    parsed_snapshot_date = (
        date.fromisoformat(snapshot_date)
        if snapshot_date
        else datetime.now(timezone.utc).date()
    )
    paths = _default_paths(
        root=resolved_root,
        output_dir=output_dir.resolve(),
        snapshot_date=parsed_snapshot_date,
    )
    paths["output_dir"].mkdir(parents=True, exist_ok=True)

    manifest_result = _run_command(
        name="quality_benchmark_manifest",
        command=_build_manifest_command(
            root=resolved_root,
            manifest_path=paths["manifest"],
        ),
        cwd=resolved_root,
    )
    if manifest_result.returncode != 0:
        raise RuntimeError(
            "quality_benchmark_manifest failed: "
            + (manifest_result.stderr.strip() or manifest_result.stdout.strip())
        )

    hotspot_result = _run_command(
        name="scan_quality_hotspots",
        command=_build_hotspot_command(
            root=resolved_root,
            hotspot_path=paths["hotspots"],
            include_tests=include_tests,
        ),
        cwd=resolved_root,
    )
    if hotspot_result.returncode != 0:
        raise RuntimeError(
            "scan_quality_hotspots failed: "
            + (hotspot_result.stderr.strip() or hotspot_result.stdout.strip())
        )

    manifest_payload = _load_json(paths["manifest"])
    hotspot_payload = _load_json(paths["hotspots"])
    baseline_payload = build_baseline_summary(
        manifest_payload=manifest_payload,
        hotspot_payload=hotspot_payload,
        root=resolved_root,
        paths=paths,
        snapshot_date=parsed_snapshot_date,
    )

    baseline_text = json.dumps(baseline_payload, ensure_ascii=False, indent=2)
    paths["baseline"].write_text(baseline_text, encoding="utf-8")
    paths["dated_baseline"].write_text(baseline_text, encoding="utf-8")

    return {
        "manifest_path": str(paths["manifest"]),
        "hotspots_path": str(paths["hotspots"]),
        "baseline_path": str(paths["baseline"]),
        "dated_baseline_path": str(paths["dated_baseline"]),
        "baseline": baseline_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the PRD-91 quality optimization baseline bundle."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository root to scan.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for generated baseline artifacts.",
    )
    parser.add_argument(
        "--snapshot-date",
        type=str,
        default=None,
        help="Optional snapshot date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Exclude tests from the hotspot scan.",
    )
    args = parser.parse_args()

    payload = run_quality_optimization_baseline(
        root=args.root,
        output_dir=args.output_dir,
        include_tests=not args.no_tests,
        snapshot_date=args.snapshot_date,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
