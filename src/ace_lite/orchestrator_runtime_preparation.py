"""Preparation runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ace_lite.orchestrator_runtime_support_types import OrchestratorPreparationResult
from ace_lite.pipeline.types import StageContext


def execute_orchestrator_preparation(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root: str,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: dict[str, Any] | None = None,
    load_conventions_fn: Callable[..., dict[str, Any]],
) -> OrchestratorPreparationResult:
    root_path = str(Path(root).resolve())
    conventions = load_conventions_fn(
        root_dir=root_path,
        files=orchestrator._conventions_files,
        previous_hashes=orchestrator._conventions_hashes,
    )
    orchestrator._runtime_state.update_conventions_hashes(
        conventions.get("file_hashes", {})
    )
    hook_bus, plugins_loaded = orchestrator._load_plugins(root=root_path)
    registry = orchestrator._build_registry()
    temporal_input = {
        "time_range": str(time_range or "").strip() or None,
        "start_date": str(start_date or "").strip() or None,
        "end_date": str(end_date or "").strip() or None,
    }
    ctx = StageContext(
        query=query,
        repo=repo,
        root=root_path,
        state={
            "conventions": conventions,
            "temporal": temporal_input,
            "benchmark_filters": dict(filters) if isinstance(filters, dict) else {},
        },
    )
    return OrchestratorPreparationResult(
        root_path=root_path,
        conventions=conventions,
        hook_bus=hook_bus,
        plugins_loaded=plugins_loaded,
        registry=registry,
        temporal_input=temporal_input,
        ctx=ctx,
    )
