from __future__ import annotations

from types import SimpleNamespace

from ace_lite.orchestrator_runtime_support import (
    PRE_SOURCE_PLAN_LIFECYCLE,
    run_pre_source_plan_stages,
)
from ace_lite.pipeline.types import StageContext, StageMetric


def test_run_pre_source_plan_stages_delegates_descriptor_stage_names(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _run_stage_sequence(**kwargs):
        recorded["stage_names"] = kwargs["stage_names"]
        recorded["repo"] = kwargs["repo"]
        kwargs["stage_metrics"].append(
            StageMetric(stage="memory", elapsed_ms=1.0, plugins=[], tags={})
        )
        return None

    monkeypatch.setattr(
        "ace_lite.orchestrator_runtime_support._run_stage_sequence",
        _run_stage_sequence,
    )

    stage_metrics, contract_error = run_pre_source_plan_stages(
        orchestrator=SimpleNamespace(),
        repo="repo",
        ctx=StageContext(query="q", repo="repo", root="/tmp"),
        registry=SimpleNamespace(),
        hook_bus=SimpleNamespace(),
    )

    assert contract_error is None
    assert recorded == {
        "stage_names": PRE_SOURCE_PLAN_LIFECYCLE.stage_names,
        "repo": "repo",
    }
    assert [metric.stage for metric in stage_metrics] == ["memory"]
