from __future__ import annotations

from typing import Any, cast

from ace_lite.orchestrator_contracts_coercion import (
    get_bool,
    get_dict,
    get_float,
    get_int,
    get_list,
    get_optional_dict,
    get_optional_str,
    get_str,
)


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


__all__ = [
    "PlanRequestAdapter",
    "PlanResponseAdapter",
    "StageStateAdapter",
]
