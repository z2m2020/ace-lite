from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from ace_lite.pipeline.types import StageCallable, StageContext, StageDescriptor


def _normalize_stage_name(stage: str) -> str:
    return str(stage or "").strip().lower()


def _build_stage_descriptor(
    stage: str,
    *,
    order: int,
    contract_enforced: bool = True,
    handler: StageCallable | None = None,
) -> StageDescriptor:
    return StageDescriptor(
        name=_normalize_stage_name(stage),
        contract_enforced=contract_enforced,
        order=order,
        handler=handler,
    )


def _build_dynamic_stage_descriptor(stage: str, *, order: int) -> StageDescriptor:
    return _build_stage_descriptor(
        stage,
        order=order,
        contract_enforced=False,
    )


def _normalize_descriptor(descriptor: StageDescriptor) -> StageDescriptor:
    normalized = _normalize_stage_name(descriptor.name)
    if normalized == descriptor.name:
        return descriptor
    return replace(descriptor, name=normalized)

CORE_STAGE_DESCRIPTORS = (
    _build_stage_descriptor("memory", order=0),
    _build_stage_descriptor("index", order=1),
    _build_stage_descriptor("repomap", order=2),
    _build_stage_descriptor("augment", order=3),
    _build_stage_descriptor("skills", order=4),
    _build_stage_descriptor("history_channel", order=5),
    _build_stage_descriptor("context_refine", order=6),
    _build_stage_descriptor("source_plan", order=7),
    _build_stage_descriptor("validation", order=8),
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
            descriptor = _build_dynamic_stage_descriptor(
                normalized,
                order=self._next_order(),
            )
        self._stages[normalized] = descriptor.with_handler(handler)

    def register_descriptor(self, descriptor: StageDescriptor) -> None:
        normalized = _normalize_descriptor(descriptor)
        self._stages[normalized.name] = normalized

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
        return cast(dict[str, Any], descriptor.handler(ctx))

    def _next_order(self) -> int:
        if not self._stages:
            return 0
        return cast(int, max(descriptor.order for descriptor in self._stages.values()) + 1)


__all__ = [
    "CORE_PIPELINE_ORDER",
    "CORE_STAGE_DESCRIPTORS",
    "CORE_STAGE_DESCRIPTOR_MAP",
    "StageRegistry",
    "get_stage_descriptor",
    "iter_stage_descriptors",
]
