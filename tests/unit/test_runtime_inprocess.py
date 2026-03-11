from __future__ import annotations

from ace_lite.pipeline.types import StageContext, StageEvent
from ace_lite.plugins import runtime_inprocess


def _event() -> StageEvent:
    return StageEvent(
        stage="source_plan",
        when="after",
        context=StageContext(query="q", repo="demo", root=".", state={}),
        payload={"ok": True},
    )


def test_before_stage_always_true() -> None:
    assert runtime_inprocess.before_stage(_event()) is True


def test_after_stage_returns_empty_patch() -> None:
    assert runtime_inprocess.after_stage(_event()) == {}


def test_runtime_inprocess_exports_hooks() -> None:
    assert set(runtime_inprocess.__all__) == {"before_stage", "after_stage"}
