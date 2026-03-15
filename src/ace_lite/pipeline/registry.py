from __future__ import annotations

from typing import Any

from ace_lite.pipeline.types import StageCallable, StageContext, StageDescriptor

CORE_STAGE_DESCRIPTORS = (
    StageDescriptor("memory"),
    StageDescriptor("index"),
    StageDescriptor("repomap"),
    StageDescriptor("augment"),
    StageDescriptor("skills"),
    StageDescriptor("source_plan"),
    StageDescriptor("validation"),
)

CORE_PIPELINE_ORDER = tuple(descriptor.name for descriptor in CORE_STAGE_DESCRIPTORS)


def iter_stage_descriptors() -> tuple[StageDescriptor, ...]:
    return CORE_STAGE_DESCRIPTORS


def get_stage_descriptor(stage: str) -> StageDescriptor | None:
    normalized = str(stage or "").strip().lower()
    for descriptor in CORE_STAGE_DESCRIPTORS:
        if descriptor.name == normalized:
            return descriptor
    return None


class StageRegistry:
    def __init__(self) -> None:
        self._stages: dict[str, StageCallable] = {}

    def register(self, stage: str, handler: StageCallable) -> None:
        self._stages[stage] = handler

    def has(self, stage: str) -> bool:
        return stage in self._stages

    def has_descriptor(self, stage: str) -> bool:
        return get_stage_descriptor(stage) is not None

    def run(self, stage: str, ctx: StageContext) -> dict[str, Any]:
        if stage not in self._stages:
            raise KeyError(f"unregistered stage: {stage}")
        return self._stages[stage](ctx)


__all__ = [
    "CORE_PIPELINE_ORDER",
    "CORE_STAGE_DESCRIPTORS",
    "StageRegistry",
    "get_stage_descriptor",
    "iter_stage_descriptors",
]
