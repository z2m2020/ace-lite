from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_shared import (
    apply_contract_error_to_payload,
    get_stage_state,
    resolve_agent_loop_rerun_stages,
    run_stage_sequence,
)
from ace_lite.pipeline.types import StageContext, StageMetric


RunStageSequence = Callable[..., StageContractError | None]
GetStageState = Callable[..., dict[str, Any]]
ApplyContractErrorToPayload = Callable[..., None]


@dataclass(frozen=True, slots=True)
class OrchestratorRuntimeSupportCompat:
    run_stage_sequence: RunStageSequence
    get_stage_state: GetStageState
    apply_contract_error_to_payload: ApplyContractErrorToPayload
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
        pre_stage_names=pre_stage_names,
        source_plan_stage_names=source_plan_stage_names,
        post_stage_names=post_stage_names,
    )


__all__ = [
    "OrchestratorRuntimeSupportCompat",
    "build_orchestrator_runtime_support_compat",
]
