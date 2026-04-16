from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


class FinalizationPlanPayloadBuilder(Protocol):
    def __call__(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        conventions: dict[str, Any],
        ctx: StageContext,
        stage_metrics: list[StageMetric],
        plugins_loaded: list[str],
        total_ms: float,
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any],
    ) -> dict[str, Any]: ...


class FinalizationTraceExporter(Protocol):
    def __call__(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
        total_ms: float,
        stage_metrics: list[StageMetric],
        plugin_policy_summary: dict[str, Any],
    ) -> dict[str, Any]: ...


class FinalizationDurableStatsRecorder(Protocol):
    def __call__(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
        total_ms: float,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
    ) -> dict[str, Any]: ...


class FinalizationRuntimeState(Protocol):
    def note_plan_root(self, root: str | None) -> None: ...

    def note_durable_stats(self, payload: dict[str, Any] | None) -> None: ...


class FinalizationRuntimeManager(Protocol):
    def ensure_shutdown_hooks(self) -> None: ...


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


@dataclass(frozen=True, slots=True)
class OrchestratorFinalizationDependencies:
    build_plan_payload: FinalizationPlanPayloadBuilder
    export_stage_trace: FinalizationTraceExporter
    record_durable_stats: FinalizationDurableStatsRecorder
    runtime_state: FinalizationRuntimeState
    runtime_manager: FinalizationRuntimeManager | None


@dataclass(slots=True)
class OrchestratorPreparationResult:
    root_path: str
    conventions: dict[str, Any]
    hook_bus: HookBus
    plugins_loaded: list[str]
    registry: StageRegistry
    temporal_input: dict[str, Any]
    ctx: StageContext


@dataclass(frozen=True, slots=True)
class OrchestratorPreparationRequest:
    query: str
    repo: str
    root: str
    time_range: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    filters: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleRequest:
    query: str
    repo: str
    root_path: str
    temporal_input: dict[str, Any]
    plugins_loaded: list[str]
    ctx: StageContext
    registry: StageRegistry
    hook_bus: HookBus


@dataclass(frozen=True, slots=True)
class OrchestratorFinalizationRequest:
    query: str
    repo: str
    root_path: str
    conventions: dict[str, Any]
    ctx: StageContext
    stage_metrics: list[StageMetric]
    plugins_loaded: list[str]
    started_at: datetime
    total_ms: float
    contract_error: StageContractError | None
    replay_cache_info: dict[str, Any]


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
    stage_names=(
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
        "history_channel",
        "context_refine",
    ),
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
_ORCHESTRATOR_LIFECYCLE_MAP = {descriptor.name: descriptor for descriptor in ORCHESTRATOR_LIFECYCLE}


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
    "FinalizationDurableStatsRecorder",
    "FinalizationPlanPayloadBuilder",
    "FinalizationRuntimeManager",
    "FinalizationRuntimeState",
    "FinalizationTraceExporter",
    "OrchestratorAgentLoopResult",
    "OrchestratorFinalizationDependencies",
    "OrchestratorFinalizationRequest",
    "OrchestratorFinalizationResult",
    "OrchestratorLifecycleDescriptor",
    "OrchestratorLifecycleRequest",
    "OrchestratorLifecycleResult",
    "OrchestratorPreparationRequest",
    "OrchestratorPreparationResult",
    "OrchestratorSourcePlanReplayResult",
    "get_lifecycle_descriptor",
    "iter_lifecycle_descriptors",
]
