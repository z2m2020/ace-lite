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
from typing import Any, TypedDict, TypeVar, cast

T = TypeVar("T")


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
# Type-Safe Accessors
# =============================================================================


def get_optional(data: Mapping[str, Any], key: str, default: T | None = None) -> Any:
    """Get an optional value from a dict with a default.

    This is a safe accessor that won't raise KeyError.
    """
    return data.get(key, default)


def get_required(data: dict[str, Any], key: str, context: str = "") -> Any:
    """Get a required value from a dict.

    Raises:
        KeyError: If the key is not found

    Args:
        data: The dict to access
        key: The key to look up
        context: Additional context for error messages
    """
    if key not in data:
        raise KeyError(
            f"Required key '{key}' not found in payload"
            + (f" ({context})" if context else "")
        )
    return data[key]


def get_typed(
    data: Mapping[str, Any],
    key: str,
    expected_type: type[Any] | tuple[type[Any], ...],
    default: T,
) -> T:
    """Get a value with type checking.

    Args:
        data: The dict to access
        key: The key to look up
        expected_type: The expected type of the value
        default: Default value if key not found or type mismatch

    Returns:
        The value if it matches the expected type, otherwise the default
    """
    value = data.get(key, default)
    if isinstance(value, expected_type):
        return cast(T, value)
    return default


def get_str(data: dict[str, Any], key: str, default: str = "") -> str:
    """Get a string value with default."""
    return get_typed(data, key, str, default)


def get_int(data: dict[str, Any], key: str, default: int = 0) -> int:
    """Get an integer value with default."""
    value = data.get(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def get_float(data: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Get a float value with default."""
    value = data.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def get_bool(data: dict[str, Any], key: str, default: bool = False) -> bool:
    """Get a boolean value with default."""
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return default


def get_optional_str(
    data: Mapping[str, Any],
    key: str,
    default: str | None = None,
) -> str | None:
    """Get an optional string value."""
    value = data.get(key, default)
    if isinstance(value, str):
        return value
    return default


def get_optional_dict(
    data: Mapping[str, Any],
    key: str,
) -> dict[str, Any] | None:
    """Get an optional mapping value."""
    value = data.get(key)
    if isinstance(value, Mapping):
        return {str(child_key): child_value for child_key, child_value in value.items()}
    return None


def get_list(
    data: Mapping[str, Any],
    key: str,
    default: list[Any] | None = None,
) -> list[Any]:
    """Get a list value with default."""
    if default is None:
        default = []
    return get_typed(data, key, list, default)


def get_dict(
    data: Mapping[str, Any],
    key: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get a dict value with default."""
    if default is None:
        default = {}
    value = data.get(key, default)
    if isinstance(value, Mapping):
        return {str(child_key): child_value for child_key, child_value in value.items()}
    return default


def coerce_mapping(data: Any) -> dict[str, Any]:
    """Project arbitrary input into a plain dict mapping."""
    if isinstance(data, Mapping):
        return {str(key): value for key, value in data.items()}
    return {}


def coerce_mapping_list(data: Any) -> list[dict[str, Any]]:
    """Project arbitrary input into a list of plain dict mappings."""
    if not isinstance(data, list):
        return []
    return [coerce_mapping(item) for item in data if isinstance(item, Mapping)]


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
        raise ValidationError(
            f"Expected dict for PlanResponsePayload, got {type(data).__name__}"
        )
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
        "completed_at": kwargs.get("completed_at", time.time() if status in ("completed", "failed") else None),
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
# Contract Adapters
# =============================================================================


class PlanRequestAdapter:
    """Adapter for PlanRequestPayload with type-safe accessors."""

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    @property
    def query(self) -> str:
        """Get the query string."""
        return get_str(self._payload, "query", "")

    @property
    def root(self) -> str:
        """Get the root path."""
        return get_str(self._payload, "root", ".")

    @property
    def repo(self) -> str:
        """Get the repository identifier."""
        return get_str(self._payload, "repo", "")

    @property
    def time_range(self) -> str | None:
        """Get the requested time range."""
        return get_optional_str(self._payload, "time_range")

    @property
    def start_date(self) -> str | None:
        """Get the requested start date."""
        return get_optional_str(self._payload, "start_date")

    @property
    def end_date(self) -> str | None:
        """Get the requested end date."""
        return get_optional_str(self._payload, "end_date")

    @property
    def top_k(self) -> int:
        """Get the top K value."""
        return get_int(self._payload, "top_k", 8)

    @property
    def budget_tokens(self) -> int:
        """Get the budget tokens value."""
        return get_int(self._payload, "budget_tokens", 800)

    @property
    def language(self) -> str | None:
        """Get the language filter."""
        return get_optional_str(self._payload, "language")

    @property
    def skip_stages(self) -> list[str]:
        """Get the stages to skip."""
        return cast(list[str], get_list(self._payload, "skip_stages"))

    @property
    def force_stages(self) -> list[str]:
        """Get the stages to force."""
        return cast(list[str], get_list(self._payload, "force_stages"))

    @property
    def ranking_profile(self) -> str:
        """Get the ranking profile."""
        return get_str(self._payload, "ranking_profile", "heuristic")

    @property
    def context(self) -> dict[str, Any]:
        """Get the context dict."""
        return get_dict(self._payload, "context", {})

    @property
    def filters(self) -> dict[str, Any]:
        """Get the filter mapping."""
        return get_dict(self._payload, "filters", {})


class PlanResponseAdapter:
    """Adapter for PlanResponsePayload with type-safe accessors."""

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    @property
    def schema_version(self) -> str:
        """Get the schema version."""
        return get_str(self._payload, "schema_version", "unknown")

    @property
    def query(self) -> str:
        """Get the original query."""
        return get_str(self._payload, "query", "")

    @property
    def plan(self) -> str:
        """Get the generated plan."""
        return get_str(self._payload, "plan", "")

    @property
    def confidence(self) -> float:
        """Get the confidence score."""
        return get_float(self._payload, "confidence", 0.0)

    @property
    def repo(self) -> str:
        """Get the repository identifier."""
        return get_str(self._payload, "repo", "")

    @property
    def root(self) -> str:
        """Get the resolved root path."""
        return get_str(self._payload, "root", "")

    @property
    def stage_metrics(self) -> list[dict[str, Any]]:
        """Get the stage metrics."""
        return cast(list[dict[str, Any]], get_list(self._payload, "stage_metrics"))

    @property
    def candidates(self) -> list[dict[str, Any]]:
        """Get the candidates."""
        return cast(list[dict[str, Any]], get_list(self._payload, "candidates"))

    @property
    def validation(self) -> dict[str, Any]:
        """Get the validation payload."""
        return get_dict(self._payload, "validation", {})

    @property
    def observability(self) -> dict[str, Any]:
        """Get the observability payload."""
        return get_dict(self._payload, "observability", {})

    @property
    def learning_router_rollout_decision(self) -> dict[str, Any]:
        """Get the learning-router rollout decision payload."""
        return get_dict(self.observability, "learning_router_rollout_decision", {})

    def get_candidate_paths(self) -> list[str]:
        """Get just the candidate paths."""
        return [c.get("path", "") for c in self.candidates if c.get("path")]

    def get_candidate_scores(self) -> list[float]:
        """Get just the candidate scores."""
        return [c.get("score", 0.0) for c in self.candidates]


class StageStateAdapter:
    """Adapter for StageStatePayload with type-safe accessors."""

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    @property
    def stage_name(self) -> str:
        """Get the stage name."""
        return get_str(self._payload, "stage_name", "unknown")

    @property
    def enabled(self) -> bool:
        """Check if the stage is enabled."""
        return get_bool(self._payload, "enabled", True)

    @property
    def status(self) -> str:
        """Get the current status."""
        return get_str(self._payload, "status", "pending")

    @property
    def is_running(self) -> bool:
        """Check if the stage is running."""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if the stage is completed."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if the stage has failed."""
        return self.status == "failed"

    @property
    def elapsed_time(self) -> float | None:
        """Get the elapsed time in seconds."""
        started = self._payload.get("started_at")
        completed = self._payload.get("completed_at")
        if (
            isinstance(started, (int, float))
            and not isinstance(started, bool)
            and isinstance(completed, (int, float))
            and not isinstance(completed, bool)
        ):
            return float(completed) - float(started)
        return None

    @property
    def result(self) -> dict[str, Any] | None:
        """Get the stage result."""
        return get_optional_dict(self._payload, "result")

    @property
    def error(self) -> str | None:
        """Get the error message."""
        return get_optional_str(self._payload, "error")


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
