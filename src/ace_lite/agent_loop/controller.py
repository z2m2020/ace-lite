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
from ace_lite.validation.result import (
    score_validation_branch_result_v1,
    select_best_validation_branch_candidate_v1,
)
from ace_lite.agent_loop.contracts import build_agent_loop_branch_batch_v1

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
    validation_branch_score: dict[str, Any]
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
            "validation_branch_score": dict(self.validation_branch_score),
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
    branch_batch: dict[str, Any]
    branch_selection: dict[str, Any]
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
            "branch_batch": dict(self.branch_batch),
            "branch_selection": dict(self.branch_selection),
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
            branch_batch={},
            branch_selection={},
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
        focus_paths: list[str] = []
        seen_paths: set[str] = set()
        messages: list[str] = []
        metadata: dict[str, Any] = {"source": "validation"}
        normalized_diagnostics = diagnostics if isinstance(diagnostics, list) else []
        for item in normalized_diagnostics:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip().replace("\\", "/")
            if path and path not in seen_paths and len(focus_paths) < self.max_focus_paths:
                seen_paths.add(path)
                focus_paths.append(path)
            message = str(item.get("message") or "").strip()
            if message and message not in messages and len(messages) < 2:
                messages.append(message)
        if normalized_diagnostics:
            metadata["diagnostic_count"] = len(normalized_diagnostics)
            reason = "validation_diagnostics"
            focus_prefix = "Focus on validation diagnostics for "
        else:
            probe_payload = (
                validation_stage.get("probes", {})
                if isinstance(validation_stage.get("probes"), dict)
                else (
                    validation_stage.get("result", {}).get("probes", {})
                    if isinstance(validation_stage.get("result"), dict)
                    else {}
                )
            )
            probe_results = (
                probe_payload.get("results", [])
                if isinstance(probe_payload, dict) and isinstance(probe_payload.get("results"), list)
                else []
            )
            failed_probe_names: list[str] = []
            probe_issue_count = 0
            for probe in probe_results:
                if not isinstance(probe, dict):
                    continue
                status = str(probe.get("status") or "").strip().lower()
                issue_count = int(probe.get("issue_count", 0) or 0)
                if status not in {"failed", "degraded"} and issue_count <= 0:
                    continue
                name = str(probe.get("name") or "").strip()
                if name and name not in failed_probe_names:
                    failed_probe_names.append(name)
                probe_issue_count += max(0, issue_count)
                issues = probe.get("issues", [])
                if not isinstance(issues, list):
                    continue
                for item in issues:
                    if not isinstance(item, dict):
                        continue
                    path = str(item.get("path") or "").strip().replace("\\", "/")
                    if path and path not in seen_paths and len(focus_paths) < self.max_focus_paths:
                        seen_paths.add(path)
                        focus_paths.append(path)
                    message = str(item.get("message") or "").strip()
                    if message and message not in messages and len(messages) < 2:
                        messages.append(message)
            if not failed_probe_names and not focus_paths and not messages:
                return None
            metadata["probe_issue_count"] = probe_issue_count
            metadata["probe_names"] = failed_probe_names
            metadata["probe_status"] = str(probe_payload.get("status") or "").strip().lower()
            reason = "validation_probes"
            focus_prefix = "Focus on validation probe failures for "

        if not focus_paths and not messages:
            return None

        hint_parts: list[str] = []
        if focus_paths:
            hint_parts.append(focus_prefix + ", ".join(focus_paths))
        if messages:
            hint_parts.append(messages[0][: self.query_hint_max_chars])
        return build_agent_loop_action_v1(
            action_type="request_more_context",
            reason=reason,
            query_hint=". ".join(
                part for part in hint_parts if part
            )[: self.query_hint_max_chars],
            focus_paths=focus_paths,
            metadata=metadata,
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
        previous_validation_stage: dict[str, Any] | None = None,
        validation_stage: dict[str, Any],
    ) -> None:
        normalized = self._normalize_action(action) or {}
        source_plan_steps = source_plan_stage.get("steps", [])
        previous_validation_result = (
            previous_validation_stage.get("result", {})
            if isinstance(previous_validation_stage, dict)
            and isinstance(previous_validation_stage.get("result"), dict)
            else {}
        )
        validation_result = (
            validation_stage.get("result", {})
            if isinstance(validation_stage.get("result"), dict)
            else {}
        )
        validation_summary = (
            validation_result.get("summary", {})
            if isinstance(validation_result.get("summary"), dict)
            else {}
        )
        validation_branch_score = (
            score_validation_branch_result_v1(
                before=previous_validation_result,
                after=validation_result,
            )
            if previous_validation_result and validation_result
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
                validation_branch_score=validation_branch_score,
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
        branch_candidates = [
            {
                "branch_id": f"iteration-{item.index}",
                "validation_branch_score": dict(item.validation_branch_score),
                "patch_scope_lines": 0,
                "artifact_refs": [],
            }
            for item in self._iterations
            if isinstance(item.validation_branch_score, dict) and item.validation_branch_score
        ]
        branch_batch = (
            build_agent_loop_branch_batch_v1(
                candidates=branch_candidates,
                metadata={
                    "source": "agent_loop_iterations",
                    "candidate_origin": "report_only",
                },
            ).as_dict()
            if branch_candidates
            else {}
        )
        branch_selection = (
            select_best_validation_branch_candidate_v1(candidates=branch_candidates)
            if branch_candidates
            else {}
        )
        return AgentLoopSummaryV1(
            enabled=self.enabled,
            attempted=self.iteration_count > 0,
            iteration_count=self.iteration_count,
            max_iterations=self.max_iterations,
            stop_reason=normalized_stop_reason,
            actions_requested=self._actions_requested,
            actions_executed=self.iteration_count,
            iterations=tuple(self._iterations),
            branch_batch=branch_batch,
            branch_selection=branch_selection,
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
