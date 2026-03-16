from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support import (
    OrchestratorSourcePlanReplayResult,
    finalize_source_plan_replay,
    prepare_source_plan_replay,
    run_source_plan_stage_with_replay,
)
from ace_lite.pipeline.types import StageContext, StageMetric


def test_prepare_source_plan_replay_resolves_cache_inputs_and_hit_payload() -> None:
    result = prepare_source_plan_replay(
        orchestrator=SimpleNamespace(
            _config=SimpleNamespace(
                plan_replay_cache=SimpleNamespace(enabled=True),
            ),
            _conventions_hashes={"rules.md": "abc"},
            _default_plan_replay_cache_info=lambda *, root: {"root": root, "cache_hit": False},
            _build_plan_replay_key=lambda **kwargs: "replay-key",
            _resolve_plan_replay_cache_path=lambda *, root: Path("/tmp/replay.json"),
            _load_replayed_source_plan=lambda **kwargs: (
                {"steps": [], "policy_name": "source_plan"},
                {"cache_hit": True, "lookup_ms": 2.5},
            ),
        ),
        query="q",
        repo="repo",
        root_path="/tmp/repo",
        temporal_input={"time_range": "last_30_days"},
        plugins_loaded=["plugin-a"],
        ctx=StageContext(
            query="q",
            repo="repo",
            root="/tmp/repo",
            state={"memory": {}, "index": {}, "repomap": {}, "augment": {}, "skills": {}},
        ),
    )

    assert result.cache_enabled is True
    assert result.replay_cache_key == "replay-key"
    assert result.replay_cache_path == Path("/tmp/replay.json")
    assert result.cached_source_plan == {"steps": [], "policy_name": "source_plan"}
    assert result.replay_cache_info == {"cache_hit": True, "lookup_ms": 2.5}


def test_finalize_source_plan_replay_stores_on_success_and_marks_contract_error() -> None:
    stored = finalize_source_plan_replay(
        orchestrator=SimpleNamespace(
            _store_source_plan_replay=lambda **kwargs: {
                **kwargs["replay_cache_info"],
                "stored": True,
                "replay_cache_key": kwargs["replay_cache_key"],
            }
        ),
        query="q",
        repo="repo",
        source_plan_stage={"steps": []},
        contract_error=None,
        replay_result=OrchestratorSourcePlanReplayResult(
            replay_cache_info={"cache_hit": False},
            replay_cache_path="/tmp/replay.json",
            replay_cache_key="key-1",
            cached_source_plan=None,
            cache_enabled=True,
        ),
    )
    failed = finalize_source_plan_replay(
        orchestrator=SimpleNamespace(),
        query="q",
        repo="repo",
        source_plan_stage={"steps": []},
        contract_error=StageContractError(
            stage="source_plan",
            error_code="missing_key",
            reason="missing_key",
            message="missing",
            context={},
        ),
        replay_result=OrchestratorSourcePlanReplayResult(
            replay_cache_info={"cache_hit": False},
            replay_cache_path="/tmp/replay.json",
            replay_cache_key="key-1",
            cached_source_plan=None,
            cache_enabled=True,
        ),
    )

    assert stored["stored"] is True
    assert stored["replay_cache_key"] == "key-1"
    assert failed["reason"] == "stage_contract_error"


def test_run_source_plan_stage_with_replay_uses_cache_hit_without_executing_stage(monkeypatch) -> None:
    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.prepare_source_plan_replay",
        lambda **kwargs: OrchestratorSourcePlanReplayResult(
            replay_cache_info={"cache_hit": True, "lookup_ms": 1.5, "stale_hit_safe": True},
            replay_cache_path="/tmp/replay.json",
            replay_cache_key="key-1",
            cached_source_plan={"steps": [], "policy_name": "source_plan"},
            cache_enabled=True,
        ),
    )

    stage_metrics: list[StageMetric] = []
    ctx = StageContext(query="q", repo="repo", root="/tmp", state={})
    contract_error, replay_cache_info = run_source_plan_stage_with_replay(
        orchestrator=SimpleNamespace(
            _config=SimpleNamespace(
                plan_replay_cache=SimpleNamespace(enabled=True),
            )
        ),
        query="q",
        repo="repo",
        root_path="/tmp",
        temporal_input={},
        plugins_loaded=[],
        ctx=ctx,
        registry=SimpleNamespace(),
        hook_bus=SimpleNamespace(),
        stage_metrics=stage_metrics,
        contract_error=None,
    )

    assert contract_error is None
    assert ctx.state["source_plan"] == {"steps": [], "policy_name": "source_plan"}
    assert replay_cache_info["cache_hit"] is True
    assert len(stage_metrics) == 1
    assert stage_metrics[0].stage == "source_plan"
