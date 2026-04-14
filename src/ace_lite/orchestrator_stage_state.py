from __future__ import annotations

from collections.abc import Callable
from typing import Any


def apply_post_stage_state_updates(
    *,
    stage_name: str,
    ctx_state: dict[str, Any],
    stage_payload: Any,
    precomputed_routing_enabled: bool,
    precompute_skills_route_fn: Callable[[], dict[str, Any]],
    capture_payload: dict[str, Any] | None,
) -> None:
    if stage_name == "validation":
        _sync_validation_patch_state(ctx_state=ctx_state, stage_payload=stage_payload)
    if stage_name == "augment":
        _sync_precomputed_skills_route(
            ctx_state=ctx_state,
            enabled=precomputed_routing_enabled,
            precompute_skills_route_fn=precompute_skills_route_fn,
        )
    if capture_payload is not None:
        ctx_state.setdefault("_long_term_capture", []).append(capture_payload)


def _sync_validation_patch_state(*, ctx_state: dict[str, Any], stage_payload: Any) -> None:
    selected_patch_artifact = (
        stage_payload.get("patch_artifact", {})
        if isinstance(stage_payload, dict)
        else {}
    )
    if isinstance(selected_patch_artifact, dict) and selected_patch_artifact:
        ctx_state["_validation_patch_artifact"] = dict(selected_patch_artifact)
    else:
        ctx_state.pop("_validation_patch_artifact", None)

    selected_patch_artifacts = (
        stage_payload.get("patch_artifacts", [])
        if isinstance(stage_payload, dict)
        else []
    )
    if isinstance(selected_patch_artifacts, list) and selected_patch_artifacts:
        ctx_state["_validation_patch_artifacts"] = [
            dict(item) for item in selected_patch_artifacts if isinstance(item, dict)
        ]
    else:
        ctx_state.pop("_validation_patch_artifacts", None)


def _sync_precomputed_skills_route(
    *,
    ctx_state: dict[str, Any],
    enabled: bool,
    precompute_skills_route_fn: Callable[[], dict[str, Any]],
) -> None:
    if enabled:
        ctx_state["_skills_route"] = precompute_skills_route_fn()
    else:
        ctx_state.pop("_skills_route", None)


__all__ = ["apply_post_stage_state_updates"]
