from __future__ import annotations

from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


def run_stage_sequence(
    *,
    orchestrator: Any,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    stage_metrics: list[StageMetric],
    stage_names: tuple[str, ...],
) -> StageContractError | None:
    for stage_name in stage_names:
        contract_error = orchestrator._execute_stage(
            stage_name=stage_name,
            repo=repo,
            ctx=ctx,
            registry=registry,
            hook_bus=hook_bus,
            stage_metrics=stage_metrics,
        )
        if contract_error is not None:
            return contract_error
    return None


def get_stage_state(*, ctx: StageContext, stage_name: str) -> dict[str, Any]:
    value = ctx.state.get(stage_name, {})
    return value if isinstance(value, dict) else {}


def apply_contract_error_to_payload(
    *,
    payload: dict[str, Any],
    ctx: StageContext,
    contract_error: StageContractError | None,
) -> None:
    if contract_error is None:
        return
    payload["observability"]["error"] = {
        "type": "stage_contract_error",
        "stage": contract_error.stage or "",
        "error_code": contract_error.error_code,
        "reason": contract_error.reason,
        "message": contract_error.message,
        "context": contract_error.context,
    }
    payload["observability"]["contract_errors"] = ctx.state.get("_contract_errors", [])


def resolve_agent_loop_rerun_stages(
    *,
    action_type: str,
    pre_stage_names: tuple[str, ...],
    source_plan_stage_names: tuple[str, ...],
    post_stage_names: tuple[str, ...],
) -> list[str]:
    if action_type == "request_source_plan_retry":
        return [
            *source_plan_stage_names,
            *post_stage_names,
        ]
    if action_type == "request_validation_retry":
        return list(post_stage_names)
    return [
        *pre_stage_names[1:],
        *source_plan_stage_names,
        *post_stage_names,
    ]


__all__ = [
    "apply_contract_error_to_payload",
    "get_stage_state",
    "resolve_agent_loop_rerun_stages",
    "run_stage_sequence",
]
