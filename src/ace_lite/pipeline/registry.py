from __future__ import annotations

from typing import Any

from ace_lite.pipeline.types import StageCallable, StageContext


class StageRegistry:
    def __init__(self) -> None:
        self._stages: dict[str, StageCallable] = {}

    def register(self, stage: str, handler: StageCallable) -> None:
        self._stages[stage] = handler

    def has(self, stage: str) -> bool:
        return stage in self._stages

    def run(self, stage: str, ctx: StageContext) -> dict[str, Any]:
        if stage not in self._stages:
            raise KeyError(f"unregistered stage: {stage}")
        return self._stages[stage](ctx)


__all__ = ["StageRegistry"]
