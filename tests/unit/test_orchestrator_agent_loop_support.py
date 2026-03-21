from __future__ import annotations

from types import SimpleNamespace

from ace_lite.orchestrator_runtime_support import (
    OrchestratorAgentLoopResult,
    run_post_source_plan_agent_loop,
    run_post_source_plan_runtime,
)
from ace_lite.pipeline.types import StageContext


def test_run_post_source_plan_runtime_delegates_agent_loop_summary_to_ctx(monkeypatch) -> None:
    ctx = StageContext(query="q", repo="repo", root="/tmp", state={})

    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support._run_stage_sequence",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.run_post_source_plan_agent_loop",
        lambda **kwargs: OrchestratorAgentLoopResult(
            contract_error=None,
            summary={"enabled": True, "stop_reason": "completed"},
            final_query="q refined",
        ),
    )

    contract_error = run_post_source_plan_runtime(
        orchestrator=SimpleNamespace(
            _config=SimpleNamespace(
                agent_loop=SimpleNamespace(
                    enabled=True,
                    max_iterations=1,
                    max_focus_paths=4,
                    query_hint_max_chars=160,
                )
            )
        ),
        query="q",
        repo="repo",
        ctx=ctx,
        registry=SimpleNamespace(),
        hook_bus=SimpleNamespace(),
        stage_metrics=[],
        contract_error=None,
    )

    assert contract_error is None
    assert ctx.state["_agent_loop"] == {"enabled": True, "stop_reason": "completed"}


def test_run_post_source_plan_agent_loop_returns_default_summary_when_no_action(monkeypatch) -> None:
    class FakeController:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def select_action(self, **kwargs):
            return None

        def default_summary(self, *, final_query: str) -> dict[str, object]:
            return {"enabled": True, "stop_reason": "idle", "final_query": final_query}

    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.BoundedLoopController",
        FakeController,
    )

    result = run_post_source_plan_agent_loop(
        orchestrator=SimpleNamespace(
            _config=SimpleNamespace(
                agent_loop=SimpleNamespace(
                    enabled=True,
                    max_iterations=1,
                    max_focus_paths=4,
                    query_hint_max_chars=160,
                )
            )
        ),
        query="draft auth plan",
        repo="repo",
        ctx=StageContext(
            query="draft auth plan",
            repo="repo",
            root="/tmp",
            state={"source_plan": {}, "validation": {}},
        ),
        registry=SimpleNamespace(),
        hook_bus=SimpleNamespace(),
        stage_metrics=[],
    )

    assert result.contract_error is None
    assert result.final_query == "draft auth plan"
    assert result.summary == {
        "enabled": True,
        "stop_reason": "idle",
        "final_query": "draft auth plan",
    }


def test_run_post_source_plan_agent_loop_appends_metric_for_max_iterations(monkeypatch) -> None:
    class FakeController:
        def __init__(self, **kwargs) -> None:
            self.enabled = True
            self.max_iterations = 1
            self._count = 0

        @property
        def iteration_count(self) -> int:
            return self._count

        def can_continue(self) -> bool:
            return self._count < 1

        def select_action(self, **kwargs):
            if self._count == 0:
                return {"action_type": "request_more_context"}
            return {"action_type": "request_more_context"}

        def build_incremental_query(self, *, base_query: str, action: dict[str, object]) -> str:
            return base_query

        def record_iteration(self, **kwargs) -> None:
            self._count += 1

        def finalize(self, *, stop_reason: str, last_action=None, final_query: str = "") -> dict[str, object]:
            return {
                "enabled": True,
                "stop_reason": stop_reason,
                "iteration_count": self._count,
                "actions_executed": self._count,
                "final_query": final_query,
            }

    stage_metrics = []
    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.BoundedLoopController",
        FakeController,
    )

    orchestrator = SimpleNamespace(
        _config=SimpleNamespace(
            agent_loop=SimpleNamespace(
                enabled=True,
                max_iterations=1,
                max_focus_paths=4,
                query_hint_max_chars=160,
            )
        ),
        _execute_stage=lambda **kwargs: None,
    )

    result = run_post_source_plan_agent_loop(
        orchestrator=orchestrator,
        query="draft auth plan",
        repo="repo",
        ctx=StageContext(
            query="draft auth plan",
            repo="repo",
            root="/tmp",
            state={"source_plan": {}, "validation": {}},
        ),
        registry=SimpleNamespace(),
        hook_bus=SimpleNamespace(),
        stage_metrics=stage_metrics,
    )

    assert result.contract_error is None
    assert result.summary["stop_reason"] == "max_iterations"
    assert len(stage_metrics) == 1
    assert stage_metrics[0].stage == "agent_loop"
    assert stage_metrics[0].tags["stop_reason"] == "max_iterations"
    assert stage_metrics[0].tags["iteration_count"] == 1
