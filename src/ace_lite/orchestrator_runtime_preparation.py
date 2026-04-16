"""Preparation runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ace_lite.orchestrator_runtime_support_types import (
    OrchestratorPreparationRequest,
    OrchestratorPreparationResult,
)
from ace_lite.pipeline.types import StageContext


def execute_orchestrator_preparation(
    *,
    orchestrator: Any,
    request: OrchestratorPreparationRequest,
    load_conventions_fn: Callable[..., dict[str, Any]],
) -> OrchestratorPreparationResult:
    root_path = str(Path(request.root).resolve())
    conventions = load_conventions_fn(
        root_dir=root_path,
        files=orchestrator._conventions_files,
        previous_hashes=orchestrator._conventions_hashes,
    )
    orchestrator._runtime_state.update_conventions_hashes(conventions.get("file_hashes", {}))
    hook_bus, plugins_loaded = orchestrator._load_plugins(root=root_path)
    registry = orchestrator._build_registry()
    temporal_input = {
        "time_range": str(request.time_range or "").strip() or None,
        "start_date": str(request.start_date or "").strip() or None,
        "end_date": str(request.end_date or "").strip() or None,
    }
    ctx = StageContext(
        query=request.query,
        repo=request.repo,
        root=root_path,
        state={
            "conventions": conventions,
            "temporal": temporal_input,
            "benchmark_filters": (
                dict(request.filters) if isinstance(request.filters, dict) else {}
            ),
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
