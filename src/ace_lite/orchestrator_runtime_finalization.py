"""Finalization runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_types import OrchestratorFinalizationResult
from ace_lite.pipeline.types import StageContext, StageMetric


def execute_orchestrator_finalization(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root_path: str,
    conventions: dict[str, Any],
    ctx: StageContext,
    stage_metrics: list[StageMetric],
    plugins_loaded: list[str],
    started_at: Any,
    total_ms: float,
    contract_error: StageContractError | None,
    replay_cache_info: dict[str, Any],
    apply_contract_error_to_payload_fn: Callable[..., None],
    validate_context_plan_fn: Callable[[dict[str, Any]], None],
) -> OrchestratorFinalizationResult:
    payload = orchestrator._build_plan_payload(
        query=query,
        repo=repo,
        root=root_path,
        conventions=conventions,
        ctx=ctx,
        stage_metrics=stage_metrics,
        plugins_loaded=plugins_loaded,
        total_ms=total_ms,
        contract_error=contract_error,
        replay_cache_info=replay_cache_info,
    )
    apply_contract_error_to_payload_fn(
        payload=payload,
        ctx=ctx,
        contract_error=contract_error,
    )
    validate_context_plan_fn(payload)

    trace_export = orchestrator._export_stage_trace(
        query=query,
        repo=repo,
        root=root_path,
        started_at=started_at,
        total_ms=total_ms,
        stage_metrics=stage_metrics,
        plugin_policy_summary=payload["observability"].get("plugin_policy_summary", {}),
    )
    if trace_export.get("enabled"):
        payload["observability"]["trace_export"] = trace_export

    durable_stats = orchestrator._record_durable_stats(
        query=query,
        repo=repo,
        root=root_path,
        started_at=started_at,
        total_ms=total_ms,
        stage_metrics=stage_metrics,
        contract_error=contract_error,
        replay_cache_info=replay_cache_info,
        trace_export=trace_export,
    )
    payload["observability"]["durable_stats"] = durable_stats
    orchestrator._runtime_state.note_plan_root(root_path)
    orchestrator._runtime_state.note_durable_stats(durable_stats)
    if orchestrator._runtime_manager is not None:
        orchestrator._runtime_manager.ensure_shutdown_hooks()

    return OrchestratorFinalizationResult(
        payload=payload,
        trace_export=trace_export,
        durable_stats=durable_stats,
    )
