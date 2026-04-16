"""Orchestrator Type Contracts for ACE-Lite

This module provides typed interfaces and contracts for the orchestrator
to reduce dict fallback patterns and improve type safety.

PRD-91 QO-2101/QO-2102: Orchestrator Typed Contracts

Key improvements:
1. TypedDict definitions for all payload structures
2. Type-safe accessor functions
3. Validation with helpful error messages
4. Backward compatibility with existing dict-based code
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from ace_lite.orchestrator_contracts_adapters import (
    PlanRequestAdapter,
    PlanResponseAdapter,
    StageStateAdapter,
)
from ace_lite.orchestrator_contracts_coercion import (
    coerce_mapping,
    coerce_mapping_list,
    get_bool,
    get_dict,
    get_float,
    get_int,
    get_list,
    get_optional,
    get_optional_dict,
    get_optional_str,
    get_required,
    get_str,
    get_typed,
)

# =============================================================================
# Core Payload TypedDicts
# =============================================================================


class PlanRequestPayload(TypedDict, total=False):
    """Payload structure for plan requests."""

    query: str
    repo: str
    root: str
    time_range: str | None
    start_date: str | None
    end_date: str | None
    top_k: int
    ranking_profile: str
    budget_tokens: int
    language: str | None
    skip_stages: list[str]
    force_stages: list[str]
    context: dict[str, Any]
    filters: dict[str, Any]


class PlanResponsePayload(TypedDict, total=False):
    """Payload structure for plan responses."""

    schema_version: str
    query: str
    repo: str
    root: str
    plan: str
    confidence: float
    pipeline_order: list[str]
    conventions: dict[str, Any]
    memory: dict[str, Any]
    index: dict[str, Any]
    repomap: dict[str, Any]
    augment: dict[str, Any]
    skills: dict[str, Any]
    history_channel: dict[str, Any]
    context_refine: dict[str, Any]
    source_plan: dict[str, Any]
    validation: dict[str, Any]
    observability: dict[str, Any]
    stage_metrics: list[dict[str, Any]]
    candidates: list[dict[str, Any]]


class StageStatePayload(TypedDict, total=False):
    """Payload structure for stage states."""

    stage_name: str
    enabled: bool
    status: str  # pending, running, completed, failed
    started_at: float | None
    completed_at: float | None
    metrics: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None


class RetrievalContextPayload(TypedDict, total=False):
    """Payload structure for retrieval context."""

    query: str
    candidates: list[dict[str, Any]]
    rankings: list[str]
    selected: list[str]
    rejected: list[str]
    total_tokens: int


class MemoryConfigPayload(TypedDict, total=False):
    """Payload structure for memory configuration."""

    namespace: str | None
    root: str | None
    notes_path: str | None
    db_path: str | None
    profile_path: str | None


class RetrievalConfigPayload(TypedDict, total=False):
    """Payload structure for retrieval configuration."""

    top_k: int
    budget_tokens: int
    language: str | None
    ranking_profile: str
    signal_weights: dict[str, float]


class OrchestratorStateProjection(TypedDict):
    """Canonical orchestrator stage/state projection."""

    memory: dict[str, Any]
    index: dict[str, Any]
    repomap: dict[str, Any]
    augment: dict[str, Any]
    skills: dict[str, Any]
    history_channel: dict[str, Any]
    context_refine: dict[str, Any]
    source_plan: dict[str, Any]
    validation: dict[str, Any]
    plugin_action_log: list[dict[str, Any]]
    plugin_conflicts: list[dict[str, Any]]
    plugin_policy_stage: dict[str, Any]
    contract_errors: list[dict[str, Any]]
    agent_loop: dict[str, Any]
    long_term_capture: list[dict[str, Any]]


# =============================================================================
# Validation Functions
# =============================================================================


class ValidationError(Exception):
    """Raised when payload validation fails."""

    def __init__(self, message: str, key: str | None = None):
        super().__init__(message)
        self.key = key


def validate_payload(
    data: dict[str, Any],
    required_keys: list[str],
    payload_name: str = "payload",
) -> None:
    """Validate that a payload has all required keys.

    Args:
        data: The payload to validate
        required_keys: List of required key names
        payload_name: Name of the payload for error messages

    Raises:
        ValidationError: If a required key is missing
    """
    for key in required_keys:
        if key not in data:
            raise ValidationError(
                f"Missing required key '{key}' in {payload_name}",
                key=key,
            )


def validate_plan_request(data: dict[str, Any]) -> PlanRequestPayload:
    """Validate a plan request payload.

    Args:
        data: The payload to validate

    Returns:
        The validated payload

    Raises:
        ValidationError: If validation fails
    """
    validate_payload(data, ["query"], "PlanRequestPayload")
    return data  # type: ignore


def validate_plan_response(data: dict[str, Any]) -> PlanResponsePayload:
    """Validate a plan response payload.

    Args:
        data: The payload to validate

    Returns:
        The validated payload

    Raises:
        ValidationError: If validation fails
    """
    # Response may have various structures, just check it's a dict
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict for PlanResponsePayload, got {type(data).__name__}")
    return data  # type: ignore


# =============================================================================
# Builder Functions
# =============================================================================


def build_stage_state(
    stage_name: str,
    status: str,
    **kwargs: Any,
) -> StageStatePayload:
    """Build a stage state payload.

    Args:
        stage_name: Name of the stage
        status: Current status (pending, running, completed, failed)
        **kwargs: Additional fields to include

    Returns:
        A new stage state payload
    """
    import time

    payload: StageStatePayload = {
        "stage_name": stage_name,
        "enabled": kwargs.get("enabled", True),
        "status": status,
        "started_at": kwargs.get("started_at", time.time() if status == "running" else None),
        "completed_at": kwargs.get(
            "completed_at", time.time() if status in ("completed", "failed") else None
        ),
        "metrics": kwargs.get("metrics", {}),
        "result": kwargs.get("result"),
        "error": kwargs.get("error"),
    }
    return payload


def build_plan_request_payload(
    *,
    query: str,
    repo: str,
    root: str,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: Mapping[str, Any] | None = None,
) -> PlanRequestPayload:
    """Build a canonical plan request payload."""
    payload: PlanRequestPayload = {
        "query": str(query),
        "repo": str(repo),
        "root": str(root),
    }
    if time_range is not None:
        payload["time_range"] = str(time_range)
    if start_date is not None:
        payload["start_date"] = str(start_date)
    if end_date is not None:
        payload["end_date"] = str(end_date)
    if isinstance(filters, Mapping):
        payload["filters"] = coerce_mapping(filters)
    return payload


def project_orchestrator_state(
    state: Mapping[str, Any],
    *,
    default_validation_payload: Mapping[str, Any],
) -> OrchestratorStateProjection:
    """Project raw ``ctx.state`` into a stable typed view."""
    validation = coerce_mapping(state.get("validation"))
    if not validation:
        validation = coerce_mapping(default_validation_payload)
    return {
        "memory": coerce_mapping(state.get("memory")),
        "index": coerce_mapping(state.get("index")),
        "repomap": coerce_mapping(state.get("repomap")),
        "augment": coerce_mapping(state.get("augment")),
        "skills": coerce_mapping(state.get("skills")),
        "history_channel": coerce_mapping(state.get("history_channel")),
        "context_refine": coerce_mapping(state.get("context_refine")),
        "source_plan": coerce_mapping(state.get("source_plan")),
        "validation": validation,
        "plugin_action_log": coerce_mapping_list(state.get("_plugin_action_log")),
        "plugin_conflicts": coerce_mapping_list(state.get("_plugin_conflicts")),
        "plugin_policy_stage": coerce_mapping(state.get("_plugin_policy_stage")),
        "contract_errors": coerce_mapping_list(state.get("_contract_errors")),
        "agent_loop": coerce_mapping(state.get("_agent_loop")),
        "long_term_capture": coerce_mapping_list(state.get("_long_term_capture")),
    }


def build_retrieval_candidate(
    path: str,
    score: float,
    rank: int,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a retrieval candidate entry.

    Args:
        path: File path of the candidate
        score: Relevance score
        rank: Rank position
        **kwargs: Additional fields

    Returns:
        A new candidate dict
    """
    return {
        "path": path,
        "score": float(score),
        "rank": int(rank),
        "source": kwargs.get("source", "retrieval"),
        "language": kwargs.get("language"),
        "lines": kwargs.get("lines"),
        "preview": kwargs.get("preview"),
    }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MemoryConfigPayload",
    "OrchestratorStateProjection",
    "PlanRequestAdapter",
    "PlanRequestPayload",
    "PlanResponseAdapter",
    "PlanResponsePayload",
    "RetrievalConfigPayload",
    "RetrievalContextPayload",
    "StageStateAdapter",
    "StageStatePayload",
    "ValidationError",
    "build_plan_request_payload",
    "build_retrieval_candidate",
    "build_stage_state",
    "coerce_mapping",
    "coerce_mapping_list",
    "get_bool",
    "get_dict",
    "get_float",
    "get_int",
    "get_list",
    "get_optional",
    "get_optional_dict",
    "get_optional_str",
    "get_required",
    "get_str",
    "get_typed",
    "project_orchestrator_state",
    "validate_payload",
    "validate_plan_request",
    "validate_plan_response",
]
