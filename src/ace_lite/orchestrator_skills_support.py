from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class OrchestratorSkillsRuntime:
    index_stage: dict[str, Any]
    routed_payload: dict[str, Any] | None

    @property
    def module_hint(self) -> str:
        return str(self.index_stage.get("module_hint", "") or "")


def build_orchestrator_skills_runtime(
    *,
    ctx_state: dict[str, Any],
    precomputed_routing_enabled: bool,
) -> OrchestratorSkillsRuntime:
    index_stage = (
        ctx_state.get("index", {})
        if isinstance(ctx_state.get("index"), dict)
        else {}
    )
    routed_payload = ctx_state.get("_skills_route")
    if not precomputed_routing_enabled or not isinstance(routed_payload, dict):
        routed_payload = None
    return OrchestratorSkillsRuntime(
        index_stage=index_stage,
        routed_payload=routed_payload,
    )


__all__ = [
    "OrchestratorSkillsRuntime",
    "build_orchestrator_skills_runtime",
]
