from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from ace_lite.orchestrator_runtime_observability_service import (
    RuntimeObservabilityService,
)
from ace_lite.pipeline.types import StageMetric


def _build_service(
    *,
    root: Path,
    export_enabled: bool = False,
    export_path: str = "context-map/traces/pipeline.jsonl",
    otlp_enabled: bool = False,
):
    recorded: list[object] = []

    class _Store:
        db_path = root / "user-runtime" / "runtime-stats.db"

        def record_invocation(self, stats: object) -> object:
            recorded.append(stats)
            return stats

    store = _Store()
    service = RuntimeObservabilityService(
        config=SimpleNamespace(
            trace=SimpleNamespace(
                export_enabled=export_enabled,
                export_path=export_path,
                otlp_enabled=otlp_enabled,
                otlp_endpoint="",
                otlp_timeout_seconds=1.0,
            )
        ),
        pipeline_order=("memory", "index", "source_plan", "validation"),
        resolve_repo_relative_path_fn=lambda *, root, configured_path: Path(root)
        / configured_path,
        durable_stats_store_factory=lambda: store,
        durable_stats_session_id="session-1",
    )
    return service, store, recorded


def test_export_stage_trace_writes_jsonl_from_service(tmp_path: Path) -> None:
    service, _, _ = _build_service(root=tmp_path, export_enabled=True)

    result = service.export_stage_trace(
        query="find auth entrypoint",
        repo="ace-lite",
        root=str(tmp_path),
        started_at=datetime(2026, 3, 27, 0, 0, 0, tzinfo=timezone.utc),
        total_ms=18.0,
        stage_metrics=[
            StageMetric(stage="memory", elapsed_ms=5.0, plugins=[], tags={}),
            StageMetric(stage="index", elapsed_ms=6.0, plugins=[], tags={}),
        ],
        plugin_policy_summary={"mode": "strict"},
    )

    assert result["enabled"] is True
    assert result["exported"] is True
    assert result["schema_version"] == "ace-lite-trace-v2"
    assert Path(str(result["path"])).exists()


def test_record_durable_stats_records_invocation_with_rollout_payload(tmp_path: Path) -> None:
    service, store, recorded = _build_service(root=tmp_path)

    result = service.record_durable_stats(
        query="record runtime stats",
        repo="ace-lite",
        root=str(tmp_path),
        started_at=datetime(2026, 3, 27, 0, 0, 0, tzinfo=timezone.utc),
        total_ms=9.5,
        stage_metrics=[
            StageMetric(stage="memory", elapsed_ms=3.0, plugins=[], tags={}),
            StageMetric(stage="index", elapsed_ms=4.0, plugins=[], tags={}),
        ],
        contract_error=None,
        replay_cache_info={"hit": True, "safe_hit": True, "stored": False},
        trace_export={"enabled": False, "exported": False},
        learning_router_rollout_decision={"reason": "adaptive_router_disabled"},
    )

    assert result["enabled"] is True
    assert result["recorded"] is True
    assert result["session_id"] == "session-1"
    assert result["db_path"] == str(store.db_path)
    assert result["learning_router_rollout_decision"]["reason"] == (
        "adaptive_router_disabled"
    )
    assert len(result["invocation_id"]) == 24
    assert len(recorded) == 1
    saved = recorded[0]
    assert saved.session_id == "session-1"
    assert saved.plan_replay_hit is True
    assert saved.trace_exported is False


def test_collect_durable_stats_reasons_marks_trace_export_failure() -> None:
    reasons = RuntimeObservabilityService.collect_durable_stats_reasons(
        stage_metrics=[],
        contract_error=None,
        replay_cache_info=None,
        trace_export={"enabled": True, "exported": False},
    )

    assert reasons == ["trace_export_failed"]
