from __future__ import annotations

from datetime import datetime, timezone

from ace_lite import orchestrator_runtime_support as support
from ace_lite.orchestrator_runtime_support_types import (
    POST_SOURCE_PLAN_LIFECYCLE,
    PRE_SOURCE_PLAN_LIFECYCLE,
    SOURCE_PLAN_LIFECYCLE,
    OrchestratorFinalizationRequest,
    OrchestratorLifecycleRequest,
    OrchestratorPreparationRequest,
    get_lifecycle_descriptor,
    iter_lifecycle_descriptors,
)
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext


def test_runtime_support_reexports_lifecycle_types_and_constants() -> None:
    assert support.PRE_SOURCE_PLAN_LIFECYCLE is PRE_SOURCE_PLAN_LIFECYCLE
    assert support.SOURCE_PLAN_LIFECYCLE is SOURCE_PLAN_LIFECYCLE
    assert support.POST_SOURCE_PLAN_LIFECYCLE is POST_SOURCE_PLAN_LIFECYCLE
    assert support.iter_lifecycle_descriptors is iter_lifecycle_descriptors
    assert support.get_lifecycle_descriptor is get_lifecycle_descriptor


def test_lifecycle_types_module_keeps_stable_descriptor_order() -> None:
    assert tuple(item.name for item in iter_lifecycle_descriptors()) == (
        "pre_source_plan",
        "source_plan",
        "post_source_plan",
    )


def test_runtime_support_request_types_capture_stable_fields() -> None:
    ctx = StageContext(query="q", repo="repo", root="/tmp", state={})
    lifecycle = OrchestratorLifecycleRequest(
        query="q",
        repo="repo",
        root_path="/tmp",
        temporal_input={"time_range": None},
        plugins_loaded=["demo"],
        ctx=ctx,
        registry=StageRegistry(),
        hook_bus=HookBus(),
    )
    preparation = OrchestratorPreparationRequest(
        query="q",
        repo="repo",
        root="/tmp",
        time_range="30d",
        filters={"lane": "test"},
    )
    finalization = OrchestratorFinalizationRequest(
        query="q",
        repo="repo",
        root_path="/tmp",
        conventions={},
        ctx=ctx,
        stage_metrics=[],
        plugins_loaded=["demo"],
        started_at=datetime(2026, 4, 16, tzinfo=timezone.utc),
        total_ms=12.5,
        contract_error=None,
        replay_cache_info={"enabled": False},
    )

    assert lifecycle.root_path == "/tmp"
    assert lifecycle.plugins_loaded == ["demo"]
    assert preparation.filters == {"lane": "test"}
    assert finalization.replay_cache_info == {"enabled": False}
