from __future__ import annotations

from ace_lite.orchestrator_skills_support import (
    build_orchestrator_skills_runtime,
)


def test_build_orchestrator_skills_runtime_uses_precomputed_route_when_enabled() -> None:
    runtime = build_orchestrator_skills_runtime(
        ctx_state={
            "index": {"module_hint": "billing.service"},
            "_skills_route": {"selected": ["skill-a"]},
        },
        precomputed_routing_enabled=True,
    )

    assert runtime.index_stage == {"module_hint": "billing.service"}
    assert runtime.module_hint == "billing.service"
    assert runtime.routed_payload == {"selected": ["skill-a"]}


def test_build_orchestrator_skills_runtime_drops_invalid_route_when_disabled() -> None:
    runtime = build_orchestrator_skills_runtime(
        ctx_state={
            "index": [],
            "_skills_route": {"selected": ["skill-a"]},
        },
        precomputed_routing_enabled=False,
    )

    assert runtime.index_stage == {}
    assert runtime.module_hint == ""
    assert runtime.routed_payload is None
