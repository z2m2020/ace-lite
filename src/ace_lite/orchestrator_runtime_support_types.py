from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleDescriptor:
    name: str
    stage_names: tuple[str, ...]
    uses_plan_replay: bool = False
    runs_agent_loop: bool = False


@dataclass(slots=True)
class OrchestratorLifecycleResult:
    stage_metrics: list[StageMetric]
    contract_error: StageContractError | None
    replay_cache_info: dict[str, Any]


@dataclass(slots=True)
class OrchestratorFinalizationResult:
    payload: dict[str, Any]
    trace_export: dict[str, Any]
    durable_stats: dict[str, Any]


@dataclass(slots=True)
class OrchestratorPreparationResult:
    root_path: str
    conventions: dict[str, Any]
    hook_bus: HookBus
    plugins_loaded: list[str]
    registry: StageRegistry
    temporal_input: dict[str, Any]
    ctx: StageContext


@dataclass(slots=True)
class OrchestratorAgentLoopResult:
    contract_error: StageContractError | None
    summary: dict[str, Any]
    final_query: str


@dataclass(slots=True)
class OrchestratorSourcePlanReplayResult:
    replay_cache_info: dict[str, Any]
    replay_cache_path: Path | str | None
    replay_cache_key: str | None
    cached_source_plan: dict[str, Any] | None
    cache_enabled: bool


PRE_SOURCE_PLAN_LIFECYCLE = OrchestratorLifecycleDescriptor(
    name="pre_source_plan",
    stage_names=("memory", "index", "repomap", "augment", "skills"),
)
SOURCE_PLAN_LIFECYCLE = OrchestratorLifecycleDescriptor(
    name="source_plan",
    stage_names=("source_plan",),
    uses_plan_replay=True,
)
POST_SOURCE_PLAN_LIFECYCLE = OrchestratorLifecycleDescriptor(
    name="post_source_plan",
    stage_names=("validation",),
    runs_agent_loop=True,
)
ORCHESTRATOR_LIFECYCLE = (
    PRE_SOURCE_PLAN_LIFECYCLE,
    SOURCE_PLAN_LIFECYCLE,
    POST_SOURCE_PLAN_LIFECYCLE,
)
_ORCHESTRATOR_LIFECYCLE_MAP = {
    descriptor.name: descriptor for descriptor in ORCHESTRATOR_LIFECYCLE
}


def iter_lifecycle_descriptors() -> tuple[OrchestratorLifecycleDescriptor, ...]:
    return ORCHESTRATOR_LIFECYCLE


def get_lifecycle_descriptor(name: str) -> OrchestratorLifecycleDescriptor | None:
    normalized = str(name or "").strip().lower()
    return _ORCHESTRATOR_LIFECYCLE_MAP.get(normalized)


__all__ = [
    "ORCHESTRATOR_LIFECYCLE",
    "POST_SOURCE_PLAN_LIFECYCLE",
    "PRE_SOURCE_PLAN_LIFECYCLE",
    "SOURCE_PLAN_LIFECYCLE",
    "OrchestratorAgentLoopResult",
    "OrchestratorFinalizationResult",
    "OrchestratorLifecycleDescriptor",
    "OrchestratorLifecycleResult",
    "OrchestratorPreparationResult",
    "OrchestratorSourcePlanReplayResult",
    "get_lifecycle_descriptor",
    "iter_lifecycle_descriptors",
]
