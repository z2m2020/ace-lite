from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Any

from ace_lite.plugin_integration_status import (
    PluginIntegrationAttempt,
    PluginIntegrationPolicy,
    PluginIntegrationStatus,
)


@dataclass(slots=True)
class _EndpointRecord:
    integration_id: str
    endpoint: str
    transport: str
    plugin_name: str | None
    policy: PluginIntegrationPolicy
    metadata: dict[str, Any] = field(default_factory=dict)
    state: str = "closed"
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

    def to_status(self) -> PluginIntegrationStatus:
        return PluginIntegrationStatus(
            integration_id=self.integration_id,
            plugin_name=self.plugin_name,
            endpoint=self.endpoint,
            transport=self.transport,
            state=self.state,  # type: ignore[arg-type]
            policy=self.policy,
            inflight_calls=self.inflight_calls,
            success_count=self.success_count,
            failure_count=self.failure_count,
            consecutive_failures=self.consecutive_failures,
            last_error=self.last_error,
            last_error_at=self.last_error_at,
            last_success_at=self.last_success_at,
            last_latency_ms=self.last_latency_ms,
            opened_at=self.opened_at,
            half_open_since=self.half_open_since,
            last_transition_reason=self.last_transition_reason,
            metadata=dict(self.metadata),
        )


class PluginIntegrationManager:
    def __init__(
        self,
        *,
        default_timeout_seconds: float = 0.3,
        default_concurrency_limit: int = 1,
        default_failure_threshold: int = 3,
        default_recovery_timeout_seconds: float = 30.0,
        default_half_open_max_calls: int = 1,
    ) -> None:
        self._default_timeout_seconds = max(0.05, float(default_timeout_seconds))
        self._default_concurrency_limit = max(1, int(default_concurrency_limit))
        self._default_failure_threshold = max(1, int(default_failure_threshold))
        self._default_recovery_timeout_seconds = max(
            0.05, float(default_recovery_timeout_seconds)
        )
        self._default_half_open_max_calls = max(1, int(default_half_open_max_calls))
        self._lock = Lock()
        self._registry: dict[str, _EndpointRecord] = {}

    def register_endpoint(
        self,
        integration_id: str,
        *,
        endpoint: str,
        transport: str,
        plugin_name: str | None = None,
        timeout_seconds: float | None = None,
        concurrency_limit: int | None = None,
        failure_threshold: int | None = None,
        recovery_timeout_seconds: float | None = None,
        half_open_max_calls: int | None = None,
        retries: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> PluginIntegrationStatus:
        key = self._normalize_integration_id(integration_id)
        resolved_endpoint = str(endpoint or "").strip()
        if not resolved_endpoint:
            raise ValueError("endpoint cannot be empty")
        resolved_transport = str(transport or "").strip().lower() or "unknown"
        policy = PluginIntegrationPolicy(
            timeout_seconds=max(
                0.05,
                float(
                    self._default_timeout_seconds
                    if timeout_seconds is None
                    else timeout_seconds
                ),
            ),
            concurrency_limit=max(
                1,
                int(
                    self._default_concurrency_limit
                    if concurrency_limit is None
                    else concurrency_limit
                ),
            ),
            failure_threshold=max(
                1,
                int(
                    self._default_failure_threshold
                    if failure_threshold is None
                    else failure_threshold
                ),
            ),
            recovery_timeout_seconds=max(
                0.05,
                float(
                    self._default_recovery_timeout_seconds
                    if recovery_timeout_seconds is None
                    else recovery_timeout_seconds
                ),
            ),
            half_open_max_calls=max(
                1,
                int(
                    self._default_half_open_max_calls
                    if half_open_max_calls is None
                    else half_open_max_calls
                ),
            ),
            retries=max(0, int(retries)),
        )

        with self._lock:
            existing = self._registry.get(key)
            if existing is None:
                existing = _EndpointRecord(
                    integration_id=key,
                    plugin_name=str(plugin_name).strip() or None if plugin_name else None,
                    endpoint=resolved_endpoint,
                    transport=resolved_transport,
                    policy=policy,
                    metadata=dict(metadata or {}),
                )
                self._registry[key] = existing
            else:
                existing.plugin_name = (
                    str(plugin_name).strip() or None if plugin_name else existing.plugin_name
                )
                existing.endpoint = resolved_endpoint
                existing.transport = resolved_transport
                existing.policy = policy
                if metadata is not None:
                    existing.metadata = dict(metadata)
            self._refresh_state_locked(existing, now=monotonic())
            return existing.to_status()

    def start_call(
        self, integration_id: str, *, now: float | None = None
    ) -> PluginIntegrationAttempt:
        current = self._now(now)
        with self._lock:
            record = self._get_record_locked(integration_id)
            self._refresh_state_locked(record, now=current)
            if record.state == "open":
                return PluginIntegrationAttempt(
                    integration_id=record.integration_id,
                    allowed=False,
                    state="open",
                    reason="circuit_open",
                    timeout_seconds=record.policy.timeout_seconds,
                    concurrency_limit=record.policy.concurrency_limit,
                    inflight_calls=record.inflight_calls,
                )
            if record.state == "half_open":
                if record.inflight_calls >= record.policy.half_open_max_calls:
                    return PluginIntegrationAttempt(
                        integration_id=record.integration_id,
                        allowed=False,
                        state="half_open",
                        reason="half_open_probe_inflight",
                        timeout_seconds=record.policy.timeout_seconds,
                        concurrency_limit=record.policy.concurrency_limit,
                        inflight_calls=record.inflight_calls,
                    )
                record.inflight_calls += 1
                return PluginIntegrationAttempt(
                    integration_id=record.integration_id,
                    allowed=True,
                    state="half_open",
                    reason=None,
                    timeout_seconds=record.policy.timeout_seconds,
                    concurrency_limit=record.policy.concurrency_limit,
                    inflight_calls=record.inflight_calls,
                )
            if record.inflight_calls >= record.policy.concurrency_limit:
                return PluginIntegrationAttempt(
                    integration_id=record.integration_id,
                    allowed=False,
                    state="closed",
                    reason="concurrency_limit",
                    timeout_seconds=record.policy.timeout_seconds,
                    concurrency_limit=record.policy.concurrency_limit,
                    inflight_calls=record.inflight_calls,
                )
            record.inflight_calls += 1
            return PluginIntegrationAttempt(
                integration_id=record.integration_id,
                allowed=True,
                state="closed",
                reason=None,
                timeout_seconds=record.policy.timeout_seconds,
                concurrency_limit=record.policy.concurrency_limit,
                inflight_calls=record.inflight_calls,
            )

    def finish_call(
        self,
        integration_id: str,
        *,
        success: bool,
        error: str | None = None,
        latency_ms: float | None = None,
        now: float | None = None,
    ) -> PluginIntegrationStatus:
        current = self._now(now)
        with self._lock:
            record = self._get_record_locked(integration_id)
            if record.inflight_calls > 0:
                record.inflight_calls -= 1
            if latency_ms is not None:
                record.last_latency_ms = max(0.0, float(latency_ms))
            if success:
                record.success_count += 1
                record.consecutive_failures = 0
                record.last_error = None
                record.last_success_at = current
                if record.state in {"open", "half_open"}:
                    record.state = "closed"
                    record.opened_at = None
                    record.half_open_since = None
                    record.last_transition_reason = "success"
                return record.to_status()

            record.failure_count += 1
            record.last_error = str(error or "unknown")
            record.last_error_at = current

            if record.state == "half_open":
                record.consecutive_failures = max(1, record.consecutive_failures + 1)
                record.state = "open"
                record.opened_at = current
                record.half_open_since = None
                record.last_transition_reason = "half_open_failure"
                return record.to_status()

            record.consecutive_failures += 1
            if record.consecutive_failures >= record.policy.failure_threshold:
                record.state = "open"
                record.opened_at = current
                record.half_open_since = None
                record.last_transition_reason = "failure_threshold"
            return record.to_status()

    def get_status(
        self, integration_id: str, *, now: float | None = None
    ) -> PluginIntegrationStatus:
        current = self._now(now)
        with self._lock:
            record = self._get_record_locked(integration_id)
            self._refresh_state_locked(record, now=current)
            return record.to_status()

    def list_statuses(self, *, now: float | None = None) -> list[PluginIntegrationStatus]:
        current = self._now(now)
        with self._lock:
            rows: list[PluginIntegrationStatus] = []
            for key in sorted(self._registry):
                record = self._registry[key]
                self._refresh_state_locked(record, now=current)
                rows.append(record.to_status())
            return rows

    def to_payload(self, *, now: float | None = None) -> dict[str, Any]:
        return {
            "integrations": [item.to_payload() for item in self.list_statuses(now=now)],
        }

    @staticmethod
    def _normalize_integration_id(value: str) -> str:
        key = str(value or "").strip()
        if not key:
            raise ValueError("integration_id cannot be empty")
        return key

    @staticmethod
    def _now(value: float | None) -> float:
        return float(monotonic() if value is None else value)

    def _get_record_locked(self, integration_id: str) -> _EndpointRecord:
        key = self._normalize_integration_id(integration_id)
        if key not in self._registry:
            raise KeyError(f"unknown integration_id: {key}")
        return self._registry[key]

    def _refresh_state_locked(self, record: _EndpointRecord, *, now: float) -> None:
        if record.state != "open" or record.opened_at is None:
            return
        elapsed = now - record.opened_at
        if elapsed < record.policy.recovery_timeout_seconds:
            return
        record.state = "half_open"
        if record.half_open_since is None:
            record.half_open_since = now
        record.last_transition_reason = "recovery_timeout_elapsed"


__all__ = ["PluginIntegrationManager"]
