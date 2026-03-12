from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.agent_loop.contracts import (
    build_agent_loop_action_v1,
    validate_agent_loop_action_v1,
)
from ace_lite.orchestrator_replay import (
    build_agent_loop_iteration_replay_fingerprint,
)

AGENT_LOOP_SUMMARY_SCHEMA_VERSION = "agent_loop_summary_v1"
AGENT_LOOP_STOP_REASONS = (
    "disabled",
    "no_action",
    "completed",
    "max_iterations",
    "stage_contract_error",
)


@dataclass(frozen=True, slots=True)
class AgentLoopIterationRecord:
    index: int
    action: dict[str, Any]
    query: str
    rerun_stages: tuple[str, ...]
    source_plan_step_count: int
    validation_status: str
    diagnostic_count: int
    replay_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "action": dict(self.action),
            "query": self.query,
            "rerun_stages": list(self.rerun_stages),
            "source_plan_step_count": self.source_plan_step_count,
            "validation_status": self.validation_status,
            "diagnostic_count": self.diagnostic_count,
            "replay_fingerprint": self.replay_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class AgentLoopSummaryV1:
    enabled: bool
    attempted: bool
    iteration_count: int
    max_iterations: int
    stop_reason: str
    actions_requested: int
    actions_executed: int
    iterations: tuple[AgentLoopIterationRecord, ...]
    last_action: dict[str, Any]
    final_query: str
    replay_safe: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AGENT_LOOP_SUMMARY_SCHEMA_VERSION,
            "enabled": self.enabled,
            "attempted": self.attempted,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            "stop_reason": self.stop_reason,
            "actions_requested": self.actions_requested,
            "actions_executed": self.actions_executed,
            "iterations": [item.as_dict() for item in self.iterations],
            "last_action": dict(self.last_action),
            "final_query": self.final_query,
            "replay_safe": self.replay_safe,
        }


class BoundedLoopController:
    def __init__(
        self,
        *,
        enabled: bool,
        max_iterations: int,
        max_focus_paths: int = 3,
        query_hint_max_chars: int = 240,
    ) -> None:
        self.enabled = bool(enabled)
        self.max_iterations = max(0, int(max_iterations))
        self.max_focus_paths = max(1, int(max_focus_paths))
        self.query_hint_max_chars = max(32, int(query_hint_max_chars))
        self._iterations: list[AgentLoopIterationRecord] = []
        self._actions_requested = 0

    @property
    def iteration_count(self) -> int:
        return len(self._iterations)

    def can_continue(self) -> bool:
        return self.enabled and self.iteration_count < self.max_iterations

    def default_summary(self, *, final_query: str = "") -> dict[str, Any]:
        stop_reason = "disabled" if not self.enabled else "no_action"
        return AgentLoopSummaryV1(
            enabled=self.enabled,
            attempted=False,
            iteration_count=0,
            max_iterations=self.max_iterations,
            stop_reason=stop_reason,
            actions_requested=0,
            actions_executed=0,
            iterations=(),
            last_action={},
            final_query=str(final_query or ""),
            replay_safe=True,
        ).as_dict()

    def _normalize_action(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        validation = validate_agent_loop_action_v1(contract=payload, strict=True)
        if not validation.get("ok", False):
            return None
        action = validation.get("action")
        return dict(action) if isinstance(action, dict) else None

    def _synthesize_validation_action(
        self,
        *,
        validation_stage: dict[str, Any],
    ) -> dict[str, Any] | None:
        diagnostics = validation_stage.get("diagnostics", [])
        if not isinstance(diagnostics, list) or not diagnostics:
            return None

        focus_paths: list[str] = []
        seen_paths: set[str] = set()
        messages: list[str] = []
        for item in diagnostics:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip().replace("\\", "/")
            if path and path not in seen_paths and len(focus_paths) < self.max_focus_paths:
                seen_paths.add(path)
                focus_paths.append(path)
            message = str(item.get("message") or "").strip()
            if message and message not in messages and len(messages) < 2:
                messages.append(message)
        if not focus_paths and not messages:
            return None

        hint_parts: list[str] = []
        if focus_paths:
            hint_parts.append(
                "Focus on validation diagnostics for " + ", ".join(focus_paths)
            )
        if messages:
            hint_parts.append(messages[0][: self.query_hint_max_chars])
        return build_agent_loop_action_v1(
            action_type="request_more_context",
            reason="validation_diagnostics",
            query_hint=". ".join(
                part for part in hint_parts if part
            )[: self.query_hint_max_chars],
            focus_paths=focus_paths,
            metadata={"source": "validation", "diagnostic_count": len(diagnostics)},
        ).as_dict()

    def select_action(
        self,
        *,
        source_plan_stage: dict[str, Any],
        validation_stage: dict[str, Any],
    ) -> dict[str, Any] | None:
        for candidate in (
            validation_stage.get("loop_action"),
            source_plan_stage.get("loop_action"),
        ):
            normalized = self._normalize_action(candidate)
            if normalized is not None:
                self._actions_requested += 1
                return normalized

        synthesized = self._synthesize_validation_action(
            validation_stage=validation_stage,
        )
        if synthesized is not None:
            self._actions_requested += 1
            return synthesized
        return None

    def build_incremental_query(
        self,
        *,
        base_query: str,
        action: dict[str, Any],
    ) -> str:
        normalized = self._normalize_action(action)
        if normalized is None:
            return str(base_query or "").strip()
        if normalized.get("action_type") == "request_validation_retry":
            return str(base_query or "").strip()

        parts = [str(base_query or "").strip()]
        query_hint = str(normalized.get("query_hint") or "").strip()
        if query_hint:
            parts.append(
                f"Focus refinement: {query_hint[: self.query_hint_max_chars]}"
            )
        focus_paths = normalized.get("focus_paths", [])
        if isinstance(focus_paths, list) and focus_paths:
            parts.append(
                "Target files: "
                + ", ".join(str(item) for item in focus_paths[: self.max_focus_paths])
            )
        return "\n".join(part for part in parts if part)

    def record_iteration(
        self,
        *,
        action: dict[str, Any],
        query: str,
        rerun_stages: list[str] | tuple[str, ...],
        source_plan_stage: dict[str, Any],
        validation_stage: dict[str, Any],
    ) -> None:
        normalized = self._normalize_action(action) or {}
        source_plan_steps = source_plan_stage.get("steps", [])
        validation_summary = (
            validation_stage.get("result", {}).get("summary", {})
            if isinstance(validation_stage.get("result"), dict)
            else {}
        )
        replay_fingerprint = build_agent_loop_iteration_replay_fingerprint(
            query=query,
            action_payload=normalized,
            rerun_stages=[str(item) for item in rerun_stages],
            source_plan_payload=source_plan_stage,
            validation_payload=validation_stage,
        )
        self._iterations.append(
            AgentLoopIterationRecord(
                index=len(self._iterations) + 1,
                action=normalized,
                query=str(query or ""),
                rerun_stages=tuple(str(item) for item in rerun_stages),
                source_plan_step_count=(
                    len(source_plan_steps) if isinstance(source_plan_steps, list) else 0
                ),
                validation_status=str(validation_summary.get("status") or ""),
                diagnostic_count=int(validation_stage.get("diagnostic_count", 0) or 0),
                replay_fingerprint=replay_fingerprint,
            )
        )

    def finalize(
        self,
        *,
        stop_reason: str,
        last_action: dict[str, Any] | None = None,
        final_query: str = "",
    ) -> dict[str, Any]:
        normalized_stop_reason = (
            str(stop_reason or "").strip().lower() or "completed"
        )
        if normalized_stop_reason not in AGENT_LOOP_STOP_REASONS:
            normalized_stop_reason = "completed"
        return AgentLoopSummaryV1(
            enabled=self.enabled,
            attempted=self.iteration_count > 0,
            iteration_count=self.iteration_count,
            max_iterations=self.max_iterations,
            stop_reason=normalized_stop_reason,
            actions_requested=self._actions_requested,
            actions_executed=self.iteration_count,
            iterations=tuple(self._iterations),
            last_action=dict(last_action) if isinstance(last_action, dict) else {},
            final_query=str(final_query or ""),
            replay_safe=True,
        ).as_dict()


__all__ = [
    "AGENT_LOOP_STOP_REASONS",
    "AGENT_LOOP_SUMMARY_SCHEMA_VERSION",
    "AgentLoopIterationRecord",
    "AgentLoopSummaryV1",
    "BoundedLoopController",
]
