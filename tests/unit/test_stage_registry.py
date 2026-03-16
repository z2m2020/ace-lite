from __future__ import annotations

from ace_lite.pipeline.registry import (
    CORE_PIPELINE_ORDER,
    StageRegistry,
    get_stage_descriptor,
    iter_stage_descriptors,
)
from ace_lite.pipeline.types import StageContext, StageDescriptor


def _stage_ctx() -> StageContext:
    return StageContext(query="q", repo="repo", root="/tmp")


def test_core_stage_descriptors_match_pipeline_order_and_lookup() -> None:
    descriptors = iter_stage_descriptors()

    assert tuple(descriptor.name for descriptor in descriptors) == CORE_PIPELINE_ORDER
    assert tuple(descriptor.order for descriptor in descriptors) == tuple(
        range(len(CORE_PIPELINE_ORDER))
    )
    assert tuple(get_stage_descriptor(name) for name in CORE_PIPELINE_ORDER) == descriptors


def test_stage_registry_register_descriptor_preserves_order() -> None:
    registry = StageRegistry(descriptors=())
    first = StageDescriptor(
        name="later",
        order=4,
        handler=lambda ctx: {"stage": "later", "query": ctx.query},
    )
    second = StageDescriptor(
        name="earlier",
        order=1,
        handler=lambda ctx: {"stage": "earlier", "query": ctx.query},
    )

    registry.register_descriptor(first)
    registry.register_descriptor(second)

    assert tuple(descriptor.name for descriptor in registry.iter_descriptors()) == (
        "earlier",
        "later",
    )
    assert registry.run("earlier", _stage_ctx())["stage"] == "earlier"


def test_stage_registry_register_legacy_handler_reuses_core_descriptor() -> None:
    registry = StageRegistry()

    def handler(ctx: StageContext) -> dict[str, str]:
        return {"stage": "memory", "query": ctx.query}

    registry.register("memory", handler)

    descriptor = registry.get_descriptor("memory")
    assert descriptor is not None
    assert descriptor.name == "memory"
    assert descriptor.order == 0
    assert descriptor.contract_enforced is True
    assert registry.has_descriptor("memory") is True
    assert registry.has("memory") is True
    assert registry.run("memory", _stage_ctx()) == {"stage": "memory", "query": "q"}


def test_stage_registry_register_unknown_stage_appends_with_unenforced_contract() -> None:
    registry = StageRegistry(descriptors=())
    registry.register("custom_stage", lambda ctx: {"query": ctx.query})

    descriptor = registry.get_descriptor("custom_stage")
    assert descriptor is not None
    assert descriptor.order == 0
    assert descriptor.contract_enforced is False
    assert registry.has_descriptor("custom_stage") is True
    assert registry.has("custom_stage") is True
    assert registry.run("custom_stage", _stage_ctx()) == {"query": "q"}
