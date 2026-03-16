from __future__ import annotations

from dataclasses import replace
from typing import Any

from ace_lite.pipeline.types import StageCallable, StageContext, StageDescriptor

CORE_STAGE_DESCRIPTORS = (
    StageDescriptor("memory", order=0),
    StageDescriptor("index", order=1),
    StageDescriptor("repomap", order=2),
    StageDescriptor("augment", order=3),
    StageDescriptor("skills", order=4),
    StageDescriptor("source_plan", order=5),
    StageDescriptor("validation", order=6),
)
CORE_STAGE_DESCRIPTOR_MAP = {
    descriptor.name: descriptor for descriptor in CORE_STAGE_DESCRIPTORS
}

CORE_PIPELINE_ORDER = tuple(descriptor.name for descriptor in CORE_STAGE_DESCRIPTORS)


def iter_stage_descriptors() -> tuple[StageDescriptor, ...]:
    return CORE_STAGE_DESCRIPTORS


def get_stage_descriptor(stage: str) -> StageDescriptor | None:
    normalized = _normalize_stage_name(stage)
    return CORE_STAGE_DESCRIPTOR_MAP.get(normalized)


class StageRegistry:
    def __init__(self, descriptors: tuple[StageDescriptor, ...] | None = None) -> None:
        self._stages: dict[str, StageDescriptor] = {}
        source_descriptors = CORE_STAGE_DESCRIPTORS if descriptors is None else descriptors
        for descriptor in source_descriptors:
            self.register_descriptor(descriptor)

    def register(self, stage: str, handler: StageCallable) -> None:
        normalized = _normalize_stage_name(stage)
        descriptor = self.get_descriptor(normalized)
        if descriptor is None:
            descriptor = StageDescriptor(
                name=normalized,
                contract_enforced=False,
                order=self._next_order(),
            )
        self._stages[normalized] = descriptor.with_handler(handler)

    def register_descriptor(self, descriptor: StageDescriptor) -> None:
        normalized = _normalize_stage_name(descriptor.name)
        if normalized != descriptor.name:
            descriptor = replace(descriptor, name=normalized)
        self._stages[normalized] = descriptor

    def get_descriptor(self, stage: str) -> StageDescriptor | None:
        normalized = _normalize_stage_name(stage)
        return self._stages.get(normalized)

    def iter_descriptors(self) -> tuple[StageDescriptor, ...]:
        return tuple(
            sorted(
                self._stages.values(),
                key=lambda descriptor: (descriptor.order, descriptor.name),
            )
        )

    def has(self, stage: str) -> bool:
        descriptor = self.get_descriptor(stage)
        return descriptor is not None and descriptor.handler is not None

    def has_descriptor(self, stage: str) -> bool:
        return self.get_descriptor(stage) is not None

    def run(self, stage: str, ctx: StageContext) -> dict[str, Any]:
        descriptor = self.get_descriptor(stage)
        if descriptor is None or descriptor.handler is None:
            raise KeyError(f"unregistered stage: {stage}")
        return descriptor.handler(ctx)

    def _next_order(self) -> int:
        if not self._stages:
            return 0
        return max(descriptor.order for descriptor in self._stages.values()) + 1


def _normalize_stage_name(stage: str) -> str:
    return str(stage or "").strip().lower()


__all__ = [
    "CORE_PIPELINE_ORDER",
    "CORE_STAGE_DESCRIPTOR_MAP",
    "CORE_STAGE_DESCRIPTORS",
    "StageRegistry",
    "get_stage_descriptor",
    "iter_stage_descriptors",
]
