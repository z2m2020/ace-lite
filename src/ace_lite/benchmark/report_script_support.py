from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ace_lite.benchmark_ops import (
    read_benchmark_deep_symbol_summary,
    read_benchmark_native_scip_summary,
    read_benchmark_retrieval_control_plane_gate_summary,
    read_benchmark_retrieval_frontier_gate_summary,
    read_benchmark_source_plan_failure_signal_summary,
    read_benchmark_source_plan_validation_feedback_summary,
    read_benchmark_validation_probe_summary,
)


def resolve_report_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def load_report_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def collect_recent_git_diff_paths(*, root: Path, limit: int = 20) -> list[str]:
    return collect_recent_git_diff_paths_with_runner(
        root=root,
        limit=limit,
        subprocess_module=subprocess,
    )


def collect_recent_git_diff_paths_with_runner(
    *,
    root: Path,
    limit: int = 20,
    subprocess_module: Any,
) -> list[str]:
    command = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
    completed = subprocess_module.run(
        command,
        cwd=str(root),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return []
    rows = [line.strip().replace("\\", "/") for line in str(completed.stdout or "").splitlines()]
    filtered = [line for line in rows if line]
    return filtered[: max(0, int(limit))]


def build_validation_rich_support_bundle(path: Path) -> dict[str, Any]:
    return {
        "retrieval_control_plane_gate_summary": read_benchmark_retrieval_control_plane_gate_summary(
            path
        ),
        "retrieval_frontier_gate_summary": read_benchmark_retrieval_frontier_gate_summary(path),
        "deep_symbol_summary": read_benchmark_deep_symbol_summary(path),
        "native_scip_summary": read_benchmark_native_scip_summary(path),
        "validation_probe_summary": read_benchmark_validation_probe_summary(path),
        "source_plan_failure_signal_summary": read_benchmark_source_plan_failure_signal_summary(
            path
        ),
        "source_plan_validation_feedback_summary": (
            read_benchmark_source_plan_validation_feedback_summary(path)
        ),
    }


__all__ = [
    "build_validation_rich_support_bundle",
    "collect_recent_git_diff_paths",
    "collect_recent_git_diff_paths_with_runner",
    "load_report_json",
    "resolve_report_path",
    "safe_float",
]
