from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AGENT_LOOP_ACTION_SCHEMA_VERSION = "agent_loop_action_v1"
AGENT_LOOP_ACTION_TYPES = ("request_more_context", "request_validation_retry")


def _normalize_text(value: Any, *, default: str = "") -> str:
    return str(value or default).strip()


def _normalize_text_list(*, value: Any, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{context}[{index}] must be a string")
        text = item.strip().replace("\\", "/")
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class AgentLoopActionV1:
    action_type: str
    reason: str
    query_hint: str
    focus_paths: tuple[str, ...]
    selected_tests: tuple[str, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AGENT_LOOP_ACTION_SCHEMA_VERSION,
            "action_type": self.action_type,
            "reason": self.reason,
            "query_hint": self.query_hint,
            "focus_paths": list(self.focus_paths),
            "selected_tests": list(self.selected_tests),
            "metadata": dict(self.metadata),
        }


def build_agent_loop_action_v1(
    *,
    action_type: str,
    reason: str,
    query_hint: str = "",
    focus_paths: list[str] | None = None,
    selected_tests: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentLoopActionV1:
    normalized_action_type = _normalize_text(action_type).lower()
    if normalized_action_type not in AGENT_LOOP_ACTION_TYPES:
        raise ValueError(
            f"action_type must be one of: {', '.join(AGENT_LOOP_ACTION_TYPES)}"
        )
    normalized_reason = _normalize_text(reason)
    if not normalized_reason:
        raise ValueError("reason cannot be empty")

    normalized_query_hint = _normalize_text(query_hint)
    normalized_focus_paths = _normalize_text_list(
        value=focus_paths,
        context="focus_paths",
    )
    normalized_selected_tests = _normalize_text_list(
        value=selected_tests,
        context="selected_tests",
    )
    if normalized_action_type == "request_more_context" and (
        not normalized_query_hint and not normalized_focus_paths
    ):
        raise ValueError(
            "request_more_context requires query_hint or focus_paths"
        )
    return AgentLoopActionV1(
        action_type=normalized_action_type,
        reason=normalized_reason,
        query_hint=normalized_query_hint,
        focus_paths=normalized_focus_paths,
        selected_tests=normalized_selected_tests,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def validate_agent_loop_action_v1(
    *,
    contract: AgentLoopActionV1 | dict[str, Any],
    strict: bool = True,
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload = contract.as_dict() if isinstance(contract, AgentLoopActionV1) else contract
    if not isinstance(payload, dict):
        raise ValueError("contract must be AgentLoopActionV1 or a mapping payload")

    violation_details: list[dict[str, Any]] = []

    def _add_violation(
        *,
        code: str,
        field: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        violation_details.append(
            {
                "code": code,
                "severity": "error",
                "field": field,
                "message": message,
                "context": dict(context) if isinstance(context, dict) else {},
            }
        )

    if payload.get("schema_version") != AGENT_LOOP_ACTION_SCHEMA_VERSION:
        _add_violation(
            code="agent_loop_action_schema_version_invalid",
            field="schema_version",
            message="schema_version must match agent_loop_action_v1",
        )

    action_type = _normalize_text(payload.get("action_type")).lower()
    if action_type not in AGENT_LOOP_ACTION_TYPES:
        _add_violation(
            code="agent_loop_action_type_invalid",
            field="action_type",
            message=f"action_type must be one of: {', '.join(AGENT_LOOP_ACTION_TYPES)}",
        )

    reason = _normalize_text(payload.get("reason"))
    if not reason:
        _add_violation(
            code="agent_loop_action_reason_invalid",
            field="reason",
            message="reason must be a non-empty string",
        )

    try:
        normalized_focus_paths = _normalize_text_list(
            value=payload.get("focus_paths"),
            context="focus_paths",
        )
    except ValueError as exc:
        normalized_focus_paths = ()
        _add_violation(
            code="agent_loop_action_focus_paths_invalid",
            field="focus_paths",
            message=str(exc),
        )

    try:
        normalized_selected_tests = _normalize_text_list(
            value=payload.get("selected_tests"),
            context="selected_tests",
        )
    except ValueError as exc:
        normalized_selected_tests = ()
        _add_violation(
            code="agent_loop_action_selected_tests_invalid",
            field="selected_tests",
            message=str(exc),
        )

    query_hint = _normalize_text(payload.get("query_hint"))
    if strict and action_type == "request_more_context" and (
        not query_hint and not normalized_focus_paths
    ):
        _add_violation(
            code="agent_loop_action_more_context_missing_signal",
            field="query_hint",
            message="request_more_context requires query_hint or focus_paths",
        )

    if not isinstance(payload.get("metadata", {}), dict):
        _add_violation(
            code="agent_loop_action_metadata_invalid",
            field="metadata",
            message="metadata must be a mapping when present",
        )

    ok = len(violation_details) == 0
    normalized_action = (
        build_agent_loop_action_v1(
            action_type=action_type,
            reason=reason,
            query_hint=query_hint,
            focus_paths=list(normalized_focus_paths),
            selected_tests=list(normalized_selected_tests),
            metadata=payload.get("metadata", {}),
        ).as_dict()
        if ok
        else None
    )
    violations = [item["code"] for item in violation_details]
    return {
        "ok": ok,
        "strict": bool(strict),
        "fail_closed": bool(fail_closed),
        "violations": violations,
        "violation_details": violation_details,
        "action": normalized_action,
    }


__all__ = [
    "AGENT_LOOP_ACTION_SCHEMA_VERSION",
    "AGENT_LOOP_ACTION_TYPES",
    "AgentLoopActionV1",
    "build_agent_loop_action_v1",
    "validate_agent_loop_action_v1",
]
