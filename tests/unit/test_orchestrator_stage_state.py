from __future__ import annotations

from types import SimpleNamespace

from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_stage_state import apply_post_stage_state_updates
from ace_lite.pipeline.types import StageContext


def _build_orchestrator_for_stage_state(
    *,
    precomputed_routing_enabled: bool = False,
) -> AceOrchestrator:
    orchestrator = object.__new__(AceOrchestrator)
    orchestrator._config = SimpleNamespace(
        skills=SimpleNamespace(
            precomputed_routing_enabled=precomputed_routing_enabled,
        )
    )
    orchestrator._capture_long_term_stage_observation = lambda **_: {"capture": True}
    orchestrator._precompute_skills_route = lambda **_: {"selected": ["skill-a"]}
    return orchestrator


def test_apply_post_stage_state_updates_syncs_validation_and_capture() -> None:
    state: dict[str, object] = {}

    apply_post_stage_state_updates(
        stage_name="validation",
        ctx_state=state,
        stage_payload={
            "patch_artifact": {"path": "a.patch"},
            "patch_artifacts": [{"path": "a.patch"}, {"path": "b.patch"}],
        },
        precomputed_routing_enabled=False,
        precompute_skills_route_fn=lambda: {"unused": True},
        capture_payload={"stage": "validation"},
    )

    assert state["_validation_patch_artifact"] == {"path": "a.patch"}
    assert state["_validation_patch_artifacts"] == [
        {"path": "a.patch"},
        {"path": "b.patch"},
    ]
    assert state["_long_term_capture"] == [{"stage": "validation"}]


def test_apply_post_stage_state_updates_syncs_precomputed_skills_route() -> None:
    state: dict[str, object] = {}

    apply_post_stage_state_updates(
        stage_name="augment",
        ctx_state=state,
        stage_payload={"ok": True},
        precomputed_routing_enabled=True,
        precompute_skills_route_fn=lambda: {"selected": ["skill-a"]},
        capture_payload=None,
    )

    assert state["_skills_route"] == {"selected": ["skill-a"]}


def test_apply_post_stage_state_updates_clears_disabled_or_missing_state() -> None:
    state: dict[str, object] = {
        "_validation_patch_artifact": {"path": "old.patch"},
        "_validation_patch_artifacts": [{"path": "old.patch"}],
        "_skills_route": {"selected": ["old-skill"]},
    }

    apply_post_stage_state_updates(
        stage_name="validation",
        ctx_state=state,
        stage_payload={},
        precomputed_routing_enabled=False,
        precompute_skills_route_fn=lambda: {"selected": ["unused"]},
        capture_payload=None,
    )
    apply_post_stage_state_updates(
        stage_name="augment",
        ctx_state=state,
        stage_payload={},
        precomputed_routing_enabled=False,
        precompute_skills_route_fn=lambda: {"selected": ["unused"]},
        capture_payload=None,
    )

    assert "_validation_patch_artifact" not in state
    assert "_validation_patch_artifacts" not in state
    assert "_skills_route" not in state


def test_store_stage_state_updates_validation_and_capture_state() -> None:
    orchestrator = _build_orchestrator_for_stage_state()
    ctx = StageContext(query="q", repo="repo", root=".", state={})

    orchestrator._store_stage_state(
        stage_name="validation",
        ctx=ctx,
        stage_payload={
            "patch_artifact": {"path": "a.patch"},
            "patch_artifacts": [{"path": "a.patch"}],
        },
    )

    assert ctx.state["validation"] == {
        "patch_artifact": {"path": "a.patch"},
        "patch_artifacts": [{"path": "a.patch"}],
    }
    assert ctx.state["_validation_patch_artifact"] == {"path": "a.patch"}
    assert ctx.state["_validation_patch_artifacts"] == [{"path": "a.patch"}]
    assert ctx.state["_long_term_capture"] == [{"capture": True}]


def test_store_stage_state_precomputes_skills_route_when_enabled() -> None:
    orchestrator = _build_orchestrator_for_stage_state(
        precomputed_routing_enabled=True
    )
    ctx = StageContext(query="q", repo="repo", root=".", state={})

    orchestrator._store_stage_state(
        stage_name="augment",
        ctx=ctx,
        stage_payload={"ok": True},
    )

    assert ctx.state["augment"] == {"ok": True}
    assert ctx.state["_skills_route"] == {"selected": ["skill-a"]}


def test_get_stage_state_returns_copy_and_fail_opens_non_mapping() -> None:
    ctx = StageContext(
        query="q",
        repo="repo",
        root=".",
        state={"memory": {"hits": 2}, "augment": ["invalid"]},
    )

    memory_stage = AceOrchestrator._get_stage_state(ctx=ctx, stage_name="memory")
    invalid_stage = AceOrchestrator._get_stage_state(ctx=ctx, stage_name="augment")

    memory_stage["hits"] = 9

    assert ctx.state["memory"] == {"hits": 2}
    assert invalid_stage == {}
