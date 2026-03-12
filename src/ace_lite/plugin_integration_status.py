from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CircuitState = Literal["closed", "open", "half_open"]


@dataclass(frozen=True, slots=True)
class PluginIntegrationPolicy:
    timeout_seconds: float
    concurrency_limit: int
    failure_threshold: int
    recovery_timeout_seconds: float
    half_open_max_calls: int
    retries: int = 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "timeout_seconds": float(self.timeout_seconds),
            "concurrency_limit": int(self.concurrency_limit),
            "failure_threshold": int(self.failure_threshold),
            "recovery_timeout_seconds": float(self.recovery_timeout_seconds),
            "half_open_max_calls": int(self.half_open_max_calls),
            "retries": int(self.retries),
        }


@dataclass(frozen=True, slots=True)
class PluginIntegrationStatus:
    integration_id: str
    endpoint: str
    transport: str
    state: CircuitState
    policy: PluginIntegrationPolicy
    plugin_name: str | None = None
    inflight_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_at: float | None = None
    last_success_at: float | None = None
    last_latency_ms: float | None = None
    opened_at: float | None = None
    half_open_since: float | None = None
    last_transition_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "plugin_name": self.plugin_name,
            "endpoint": self.endpoint,
            "transport": self.transport,
            "state": self.state,
            "policy": self.policy.to_payload(),
            "inflight_calls": int(self.inflight_calls),
            "success_count": int(self.success_count),
            "failure_count": int(self.failure_count),
            "consecutive_failures": int(self.consecutive_failures),
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
            "last_success_at": self.last_success_at,
            "last_latency_ms": self.last_latency_ms,
            "opened_at": self.opened_at,
            "half_open_since": self.half_open_since,
            "last_transition_reason": self.last_transition_reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class PluginIntegrationAttempt:
    integration_id: str
    allowed: bool
    state: CircuitState
    reason: str | None
    timeout_seconds: float
    concurrency_limit: int
    inflight_calls: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "allowed": bool(self.allowed),
            "state": self.state,
            "reason": self.reason,
            "timeout_seconds": float(self.timeout_seconds),
            "concurrency_limit": int(self.concurrency_limit),
            "inflight_calls": int(self.inflight_calls),
        }


__all__ = [
    "CircuitState",
    "PluginIntegrationAttempt",
    "PluginIntegrationPolicy",
    "PluginIntegrationStatus",
]
