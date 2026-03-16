from __future__ import annotations

from types import SimpleNamespace

from ace_lite.orchestrator_runtime_support import (
    POST_SOURCE_PLAN_LIFECYCLE,
    PRE_SOURCE_PLAN_LIFECYCLE,
    SOURCE_PLAN_LIFECYCLE,
    get_lifecycle_descriptor,
    iter_lifecycle_descriptors,
    run_orchestrator_lifecycle,
)
from ace_lite.pipeline.types import StageContext, StageMetric


def test_orchestrator_lifecycle_descriptors_expose_stable_order_and_lookup() -> None:
    descriptors = iter_lifecycle_descriptors()

    assert tuple(descriptor.name for descriptor in descriptors) == (
        "pre_source_plan",
        "source_plan",
        "post_source_plan",
    )
    assert PRE_SOURCE_PLAN_LIFECYCLE.stage_names == (
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
    )
    assert SOURCE_PLAN_LIFECYCLE.uses_plan_replay is True
    assert POST_SOURCE_PLAN_LIFECYCLE.runs_agent_loop is True
    assert get_lifecycle_descriptor(" source_plan ") == SOURCE_PLAN_LIFECYCLE
    assert get_lifecycle_descriptor("unknown") is None


def test_run_orchestrator_lifecycle_dispatches_descriptors_in_order(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def _run_pre_source_plan_stages(**kwargs):
        descriptor = kwargs["descriptor"]
        calls.append(descriptor.name)
        assert descriptor == PRE_SOURCE_PLAN_LIFECYCLE
        return [StageMetric(stage="memory", elapsed_ms=1.0, plugins=[], tags={})], None

    def _run_source_plan_stage_with_replay(**kwargs):
        descriptor = kwargs["descriptor"]
        calls.append(descriptor.name)
        assert descriptor == SOURCE_PLAN_LIFECYCLE
        assert len(kwargs["stage_metrics"]) == 1
        return None, {"cache_hit": False, "reason": "miss"}

    def _run_post_source_plan_runtime(**kwargs):
        descriptor = kwargs["descriptor"]
        calls.append(descriptor.name)
        assert descriptor == POST_SOURCE_PLAN_LIFECYCLE
        return None

    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.run_pre_source_plan_stages",
        _run_pre_source_plan_stages,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.run_source_plan_stage_with_replay",
        _run_source_plan_stage_with_replay,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.run_post_source_plan_runtime",
        _run_post_source_plan_runtime,
    )

    result = run_orchestrator_lifecycle(
        orchestrator=SimpleNamespace(
            _default_plan_replay_cache_info=lambda *, root: {"root": root, "cache_hit": False}
        ),
        query="q",
        repo="repo",
        root_path="/tmp/repo",
        temporal_input={},
        plugins_loaded=[],
        ctx=StageContext(query="q", repo="repo", root="/tmp/repo"),
        registry=SimpleNamespace(),
        hook_bus=SimpleNamespace(),
    )

    assert calls == ["pre_source_plan", "source_plan", "post_source_plan"]
    assert result.contract_error is None
    assert len(result.stage_metrics) == 1
    assert result.replay_cache_info == {"cache_hit": False, "reason": "miss"}
