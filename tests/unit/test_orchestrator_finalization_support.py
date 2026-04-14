from __future__ import annotations

from types import SimpleNamespace

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support import (
    build_orchestrator_finalization_dependencies,
    run_orchestrator_finalization,
)
from ace_lite.pipeline.types import StageContext, StageMetric


def test_run_orchestrator_finalization_applies_contract_error_trace_and_runtime_hooks(
    monkeypatch,
) -> None:
    calls: list[str] = []
    durable_stats = {"enabled": True, "recorded": True}
    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support.validate_context_plan",
        lambda payload: calls.append(f"validate:{payload['schema_version']}"),
    )

    class _RuntimeState:
        def note_plan_root(self, root: str) -> None:
            calls.append(f"note_plan_root:{root}")

        def note_durable_stats(self, payload: dict[str, object]) -> None:
            calls.append(f"note_durable_stats:{payload['recorded']}")

    class _RuntimeManager:
        def ensure_shutdown_hooks(self) -> None:
            calls.append("ensure_shutdown_hooks")

    orchestrator = SimpleNamespace(
        _last_learning_router_rollout_decision={"mode": "canary"},
        _runtime_state=_RuntimeState(),
        _runtime_manager=_RuntimeManager(),
        _runtime_observability_service=SimpleNamespace(
            export_stage_trace=lambda **kwargs: calls.append("trace")
            or {"enabled": True, "path": "trace.jsonl"},
            record_durable_stats=lambda **kwargs: calls.append("durable")
            or durable_stats,
        ),
        _build_plan_payload=lambda **kwargs: {
            "schema_version": "context_plan_v1",
            "pipeline_order": [
                "memory",
                "index",
                "repomap",
                "augment",
                "skills",
                "source_plan",
                "validation",
            ],
            "observability": {
                "stage_metrics": [
                    {"stage": "memory", "elapsed_ms": 1.0, "plugins": [], "tags": {}}
                ],
                "plugin_policy_summary": {"allowed": 1},
            },
        },
    )
    ctx = StageContext(query="q", repo="repo", root="/tmp")
    ctx.state["_contract_errors"] = [{"stage": "index", "error_code": "missing"}]
    contract_error = StageContractError(
        stage="index",
        error_code="missing_required_key",
        reason="missing_key",
        message="missing key",
        context={"key": "targets"},
    )

    result = run_orchestrator_finalization(
        orchestrator=orchestrator,
        query="q",
        repo="repo",
        root_path="/tmp",
        conventions={},
        ctx=ctx,
        stage_metrics=[StageMetric(stage="memory", elapsed_ms=1.0, plugins=[], tags={})],
        plugins_loaded=[],
        started_at="2026-03-16T00:00:00Z",
        total_ms=5.0,
        contract_error=contract_error,
        replay_cache_info={"cache_hit": False},
    )

    assert result.payload["observability"]["error"]["stage"] == "index"
    assert result.payload["observability"]["contract_errors"] == [
        {"stage": "index", "error_code": "missing"}
    ]
    assert result.payload["observability"]["trace_export"] == {
        "enabled": True,
        "path": "trace.jsonl",
    }
    assert result.payload["observability"]["durable_stats"] == durable_stats
    assert result.trace_export == {"enabled": True, "path": "trace.jsonl"}
    assert result.durable_stats == durable_stats
    assert calls == [
        "validate:context_plan_v1",
        "trace",
        "durable",
        "note_plan_root:/tmp",
        "note_durable_stats:True",
        "ensure_shutdown_hooks",
    ]


def test_build_orchestrator_finalization_dependencies_captures_rollout_context() -> None:
    observed: list[dict[str, object]] = []
    runtime_service = SimpleNamespace(
        export_stage_trace=lambda **kwargs: {"enabled": False, "query": kwargs["query"]},
        record_durable_stats=lambda **kwargs: observed.append(kwargs) or {"recorded": True},
    )
    orchestrator = SimpleNamespace(
        _build_plan_payload=lambda **kwargs: {"schema_version": "context_plan_v1", **kwargs},
        _runtime_observability_service=runtime_service,
        _runtime_state=SimpleNamespace(),
        _runtime_manager=None,
        _last_learning_router_rollout_decision={"mode": "shadow"},
    )

    deps = build_orchestrator_finalization_dependencies(orchestrator=orchestrator)
    payload = deps.build_plan_payload(
        query="q",
        repo="repo",
        root="/tmp",
        conventions={},
        ctx=StageContext(query="q", repo="repo", root="/tmp"),
        stage_metrics=[],
        plugins_loaded=[],
        total_ms=1.0,
        contract_error=None,
        replay_cache_info={},
    )
    stats = deps.record_durable_stats(
        query="q",
        repo="repo",
        root="/tmp",
        started_at="2026-04-14T00:00:00Z",
        total_ms=1.0,
        stage_metrics=[],
        contract_error=None,
        replay_cache_info={},
        trace_export={"enabled": False},
    )

    assert payload["schema_version"] == "context_plan_v1"
    assert stats == {"recorded": True}
    assert observed == [
        {
            "query": "q",
            "repo": "repo",
            "root": "/tmp",
            "started_at": "2026-04-14T00:00:00Z",
            "total_ms": 1.0,
            "stage_metrics": [],
            "contract_error": None,
            "replay_cache_info": {},
            "trace_export": {"enabled": False},
            "learning_router_rollout_decision": {"mode": "shadow"},
        }
    ]
