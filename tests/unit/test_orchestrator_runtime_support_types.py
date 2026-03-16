from __future__ import annotations

from ace_lite import orchestrator_runtime_support as support
from ace_lite.orchestrator_runtime_support_types import (
    POST_SOURCE_PLAN_LIFECYCLE,
    PRE_SOURCE_PLAN_LIFECYCLE,
    SOURCE_PLAN_LIFECYCLE,
    get_lifecycle_descriptor,
    iter_lifecycle_descriptors,
)


def test_runtime_support_reexports_lifecycle_types_and_constants() -> None:
    assert support.PRE_SOURCE_PLAN_LIFECYCLE is PRE_SOURCE_PLAN_LIFECYCLE
    assert support.SOURCE_PLAN_LIFECYCLE is SOURCE_PLAN_LIFECYCLE
    assert support.POST_SOURCE_PLAN_LIFECYCLE is POST_SOURCE_PLAN_LIFECYCLE
    assert support.iter_lifecycle_descriptors is iter_lifecycle_descriptors
    assert support.get_lifecycle_descriptor is get_lifecycle_descriptor


def test_lifecycle_types_module_keeps_stable_descriptor_order() -> None:
    assert tuple(item.name for item in iter_lifecycle_descriptors()) == (
        "pre_source_plan",
        "source_plan",
        "post_source_plan",
    )
