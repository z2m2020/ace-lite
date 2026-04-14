from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_shared import (
    apply_contract_error_to_payload,
    get_stage_state,
    resolve_agent_loop_rerun_stages,
    run_stage_sequence,
)
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


class RunStageSequenceFn(Protocol):
    def __call__(
        self,
        *,
        orchestrator: Any,
        repo: str,
        ctx: StageContext,
        registry: StageRegistry,
        hook_bus: HookBus,
        stage_metrics: list[StageMetric],
        stage_names: tuple[str, ...],
    ) -> StageContractError | None: ...


class GetStageStateFn(Protocol):
    def __call__(self, *, ctx: StageContext, stage_name: str) -> dict[str, Any]: ...


class ApplyContractErrorToPayloadFn(Protocol):
    def __call__(
        self,
        *,
        payload: dict[str, Any],
        ctx: StageContext,
        contract_error: StageContractError | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class OrchestratorRuntimeStageGroups:
    pre_stage_names: tuple[str, ...]
    source_plan_stage_names: tuple[str, ...]
    post_stage_names: tuple[str, ...]

    def resolve_agent_loop_rerun_stages(self, *, action_type: str) -> list[str]:
        return resolve_agent_loop_rerun_stages(
            action_type=action_type,
            pre_stage_names=self.pre_stage_names,
            source_plan_stage_names=self.source_plan_stage_names,
            post_stage_names=self.post_stage_names,
        )


@dataclass(frozen=True, slots=True)
class OrchestratorRuntimeSupportCompat:
    run_stage_sequence: RunStageSequenceFn
    get_stage_state: GetStageStateFn
    apply_contract_error_to_payload: ApplyContractErrorToPayloadFn
    stage_groups: OrchestratorRuntimeStageGroups

    def resolve_agent_loop_rerun_stages(self, *, action_type: str) -> list[str]:
        return self.stage_groups.resolve_agent_loop_rerun_stages(action_type=action_type)


def build_orchestrator_runtime_stage_groups(
    *,
    pre_stage_names: tuple[str, ...],
    source_plan_stage_names: tuple[str, ...],
    post_stage_names: tuple[str, ...],
) -> OrchestratorRuntimeStageGroups:
    return OrchestratorRuntimeStageGroups(
        pre_stage_names=pre_stage_names,
        source_plan_stage_names=source_plan_stage_names,
        post_stage_names=post_stage_names,
    )


def build_orchestrator_runtime_support_compat(
    *,
    pre_stage_names: tuple[str, ...],
    source_plan_stage_names: tuple[str, ...],
    post_stage_names: tuple[str, ...],
) -> OrchestratorRuntimeSupportCompat:
    return OrchestratorRuntimeSupportCompat(
        run_stage_sequence=run_stage_sequence,
        get_stage_state=get_stage_state,
        apply_contract_error_to_payload=apply_contract_error_to_payload,
        stage_groups=build_orchestrator_runtime_stage_groups(
            pre_stage_names=pre_stage_names,
            source_plan_stage_names=source_plan_stage_names,
            post_stage_names=post_stage_names,
        ),
    )


__all__ = [
    "ApplyContractErrorToPayloadFn",
    "GetStageStateFn",
    "OrchestratorRuntimeStageGroups",
    "OrchestratorRuntimeSupportCompat",
    "RunStageSequenceFn",
    "build_orchestrator_runtime_stage_groups",
    "build_orchestrator_runtime_support_compat",
]
