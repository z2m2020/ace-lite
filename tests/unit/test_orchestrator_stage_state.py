from __future__ import annotations

from ace_lite.orchestrator_stage_state import apply_post_stage_state_updates


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
