"""Finalization runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.orchestrator_runtime_support_types import (
    OrchestratorFinalizationDependencies,
    OrchestratorFinalizationRequest,
    OrchestratorFinalizationResult,
)


def execute_orchestrator_finalization(
    *,
    request: OrchestratorFinalizationRequest,
    dependencies: OrchestratorFinalizationDependencies,
    apply_contract_error_to_payload_fn: Callable[..., None],
    validate_context_plan_fn: Callable[[dict[str, Any]], None],
) -> OrchestratorFinalizationResult:
    payload = dependencies.build_plan_payload(
        query=request.query,
        repo=request.repo,
        root=request.root_path,
        conventions=request.conventions,
        ctx=request.ctx,
        stage_metrics=request.stage_metrics,
        plugins_loaded=request.plugins_loaded,
        total_ms=request.total_ms,
        contract_error=request.contract_error,
        replay_cache_info=request.replay_cache_info,
    )
    apply_contract_error_to_payload_fn(
        payload=payload,
        ctx=request.ctx,
        contract_error=request.contract_error,
    )
    validate_context_plan_fn(payload)

    trace_export = dependencies.export_stage_trace(
        query=request.query,
        repo=request.repo,
        root=request.root_path,
        started_at=request.started_at,
        total_ms=request.total_ms,
        stage_metrics=request.stage_metrics,
        plugin_policy_summary=payload["observability"].get("plugin_policy_summary", {}),
    )
    if trace_export.get("enabled"):
        payload["observability"]["trace_export"] = trace_export

    durable_stats = dependencies.record_durable_stats(
        query=request.query,
        repo=request.repo,
        root=request.root_path,
        started_at=request.started_at,
        total_ms=request.total_ms,
        stage_metrics=request.stage_metrics,
        contract_error=request.contract_error,
        replay_cache_info=request.replay_cache_info,
        trace_export=trace_export,
    )
    payload["observability"]["durable_stats"] = durable_stats
    dependencies.runtime_state.note_plan_root(request.root_path)
    dependencies.runtime_state.note_durable_stats(durable_stats)
    if dependencies.runtime_manager is not None:
        dependencies.runtime_manager.ensure_shutdown_hooks()

    return OrchestratorFinalizationResult(
        payload=payload,
        trace_export=trace_export,
        durable_stats=durable_stats,
    )
