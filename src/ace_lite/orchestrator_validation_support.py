from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class OrchestratorValidationRuntime:
    source_plan_stage: dict[str, Any]
    index_stage: dict[str, Any]
    policy: dict[str, Any]
    patch_artifact: dict[str, Any] | None


def build_orchestrator_validation_runtime(
    *, ctx_state: dict[str, Any]
) -> OrchestratorValidationRuntime:
    source_plan_stage = (
        ctx_state.get("source_plan", {})
        if isinstance(ctx_state.get("source_plan"), dict)
        else {}
    )
    index_stage = (
        ctx_state.get("index", {})
        if isinstance(ctx_state.get("index"), dict)
        else {}
    )
    policy = (
        ctx_state.get("__policy", {})
        if isinstance(ctx_state.get("__policy"), dict)
        else {}
    )
    patch_artifact = ctx_state.get("_validation_patch_artifact")
    if not isinstance(patch_artifact, dict):
        patch_artifact = None
    return OrchestratorValidationRuntime(
        source_plan_stage=source_plan_stage,
        index_stage=index_stage,
        policy=policy,
        patch_artifact=patch_artifact,
    )


__all__ = [
    "OrchestratorValidationRuntime",
    "build_orchestrator_validation_runtime",
]
