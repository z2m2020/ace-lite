from __future__ import annotations

from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.types import StageContext, StageEvent


def _event() -> StageEvent:
    ctx = StageContext(query="q", repo="r", root="/tmp", state={})
    return StageEvent(stage="source_plan", when="after", context=ctx, payload={})


def test_hook_bus_dispatch_before_and_after() -> None:
    bus = HookBus()

    bus.register_before("p1", lambda event: event.stage == "source_plan")
    bus.register_before("p2", lambda event: False)
    bus.register_after("p1", lambda event: {"a": 1})
    bus.register_after("p2", lambda event: None)

    event = _event()
    fired_before = bus.dispatch_before(event)
    contributions, fired_after = bus.dispatch_after(event)

    assert fired_before == ["p1"]
    assert fired_after == ["p1"]
    assert contributions == [
        {
            "plugin": "p1",
            "slot": "a",
            "value": 1,
            "mode": "set",
        }
    ]


def test_hook_bus_after_patch_deep_merge() -> None:
    bus = HookBus()

    bus.register_after("p1", lambda event: {"writeback_template": {"decision": "A"}})
    bus.register_after("p2", lambda event: {"writeback_template": {"caveat": "B"}})

    contributions, fired = bus.dispatch_after(_event())

    assert fired == ["p1", "p2"]
    assert {item["slot"] for item in contributions} == {
        "writeback_template.decision",
        "writeback_template.caveat",
    }


def test_hook_bus_preserves_source_field_in_slot_contribution() -> None:
    bus = HookBus()

    bus.register_after(
        "remote-plugin",
        lambda event: {
            "slot": "observability.mcp_plugins",
            "mode": "append",
            "value": {"name": "remote-plugin"},
            "source": "mcp_remote",
        },
    )

    contributions, fired = bus.dispatch_after(_event())

    assert fired == ["remote-plugin"]
    assert len(contributions) == 1
    assert contributions[0]["slot"] == "observability.mcp_plugins"
    assert contributions[0]["source"] == "mcp_remote"
