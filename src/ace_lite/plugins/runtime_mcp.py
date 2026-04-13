from __future__ import annotations

import json
from collections.abc import Callable
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request

from ace_lite.http_utils import safe_urlopen
from ace_lite.pipeline.types import StageEvent
from ace_lite.plugin_integration_manager import PluginIntegrationManager
from ace_lite.plugin_integration_status import PluginIntegrationStatus

DEFAULT_MOCK_ENDPOINT = "mock://mcp"


def make_mcp_hooks(
    plugin_name: str,
    *,
    endpoint: str | None = None,
    timeout_seconds: float = 0.3,
    retries: int = 0,
    headers: dict[str, str] | None = None,
    integration_manager: PluginIntegrationManager | None = None,
) -> tuple[Callable[[StageEvent], bool], Callable[[StageEvent], dict[str, Any]]]:
    """Create MCP-style hooks for an untrusted plugin.

    This runtime is intentionally defensive:
    - Never raises exceptions (pipeline must not break).
    - Captures success/failure in an observability slot.

    The remote protocol is best-effort:
    - For HTTP(S) endpoints, we attempt a JSON-RPC 2.0 `tools/call` request
      against the provided URL.
    - If the remote returns `slots` / slot contributions, they are passed
      through.

    When no endpoint is provided, a `mock://` endpoint is used and no
    network calls are performed.
    """

    endpoint = (endpoint or DEFAULT_MOCK_ENDPOINT).strip() or DEFAULT_MOCK_ENDPOINT
    timeout_seconds = max(0.05, float(timeout_seconds))
    retries = max(0, int(retries))
    integration_id = _build_integration_id(plugin_name=plugin_name, endpoint=endpoint)

    if integration_manager is not None:
        parsed = urlparse(endpoint)
        if parsed.scheme in {"http", "https"}:
            integration_manager.register_endpoint(
                integration_id,
                endpoint=endpoint,
                transport="http_jsonrpc",
                plugin_name=plugin_name,
                timeout_seconds=timeout_seconds,
                retries=retries,
                metadata={"source": "runtime_mcp"},
            )

    before_outcomes: dict[str, dict[str, Any]] = {}

    def before_stage(event: StageEvent) -> bool:
        before_outcomes[event.stage] = _call_mcp_hook(
            endpoint=endpoint,
            plugin_name=plugin_name,
            event=event,
            timeout_seconds=timeout_seconds,
            retries=retries,
            headers=headers,
            integration_manager=integration_manager,
            integration_id=integration_id,
        )
        return True

    def after_stage(event: StageEvent) -> dict[str, Any]:
        after_outcome = _call_mcp_hook(
            endpoint=endpoint,
            plugin_name=plugin_name,
            event=event,
            timeout_seconds=timeout_seconds,
            retries=retries,
            headers=headers,
            integration_manager=integration_manager,
            integration_id=integration_id,
        )
        before_outcome = before_outcomes.get(event.stage)

        value: dict[str, Any] = {
            "name": plugin_name,
            "endpoint": endpoint,
            "integration_id": integration_id,
            "stage": event.stage,
            "when": event.when,
            "timeout_seconds": float(timeout_seconds),
            "retries": int(retries),
            "status": after_outcome.get("status"),
            "latency_ms": after_outcome.get("latency_ms"),
            "error": after_outcome.get("error"),
            "attempts": after_outcome.get("attempts"),
            "transport": after_outcome.get("transport"),
            "integration_state": after_outcome.get("integration_state"),
            "decision_reason": after_outcome.get("decision_reason"),
        }

        if before_outcome is not None:
            value.update(
                {
                    "before_status": before_outcome.get("status"),
                    "before_latency_ms": before_outcome.get("latency_ms"),
                    "before_error": before_outcome.get("error"),
                    "before_attempts": before_outcome.get("attempts"),
                    "before_integration_state": before_outcome.get("integration_state"),
                    "before_decision_reason": before_outcome.get("decision_reason"),
                }
            )

        remote_slots = _extract_slot_contributions(after_outcome.get("response"))

        return {
            "slots": [
                {
                    "slot": "observability.mcp_plugins",
                    "mode": "append",
                    "value": value,
                },
                *remote_slots,
            ]
        }

    return before_stage, after_stage


def _call_mcp_hook(
    *,
    endpoint: str,
    plugin_name: str,
    event: StageEvent,
    timeout_seconds: float,
    retries: int,
    headers: dict[str, str] | None,
    integration_manager: PluginIntegrationManager | None,
    integration_id: str | None,
) -> dict[str, Any]:
    parsed = urlparse(endpoint)
    if parsed.scheme == "mock":
        return {
            "status": "skipped",
            "latency_ms": 0.0,
            "error": None,
            "attempts": 0,
            "transport": "mock",
            "integration_state": None,
            "decision_reason": None,
            "response": None,
        }

    if parsed.scheme not in {"http", "https"}:
        return {
            "status": "skipped",
            "latency_ms": 0.0,
            "error": f"unsupported_endpoint:{parsed.scheme or 'none'}",
            "attempts": 0,
            "transport": "unknown",
            "integration_state": None,
            "decision_reason": None,
            "response": None,
        }

    if integration_manager is not None and integration_id:
        decision = integration_manager.start_call(integration_id)
        if not decision.allowed:
            status = integration_manager.get_status(integration_id)
            return {
                "status": "degraded",
                "latency_ms": 0.0,
                "error": decision.reason,
                "attempts": 0,
                "transport": "http_jsonrpc",
                "integration_state": status.state,
                "decision_reason": decision.reason,
                "response": None,
            }
    else:
        decision = None

    arguments = {
        "plugin": plugin_name,
        "stage": event.stage,
        "when": event.when,
        "context": {
            "query": event.context.query,
            "repo": event.context.repo,
            "root": event.context.root,
        },
        "payload": event.payload,
    }

    request_payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": "ace-lite",
        "method": "tools/call",
        "params": {
            "name": "ace_lite_stage_hook",
            "arguments": arguments,
        },
    }

    last_error: str | None = None
    attempts = 0

    for attempt in range(retries + 1):
        attempts = attempt + 1
        started = perf_counter()
        try:
            response_payload = _post_json(
                url=endpoint,
                payload=request_payload,
                timeout_seconds=timeout_seconds,
                headers=headers,
            )
            latency_ms = (perf_counter() - started) * 1000.0
            success_status: PluginIntegrationStatus | None = None
            if integration_manager is not None and integration_id:
                success_status = integration_manager.finish_call(
                    integration_id,
                    success=True,
                    latency_ms=latency_ms,
                )
            return {
                "status": "ok",
                "latency_ms": round(latency_ms, 3),
                "error": None,
                "attempts": attempts,
                "transport": "http_jsonrpc",
                "integration_state": (
                    success_status.state if success_status is not None else None
                ),
                "decision_reason": None if decision is None else decision.reason,
                "response": response_payload,
            }
        except (
            HTTPError,
            URLError,
            OSError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            latency_ms = (perf_counter() - started) * 1000.0
            last_error = f"{exc.__class__.__name__}:{exc}"
            if attempt >= retries:
                failure_status: PluginIntegrationStatus | None = None
                if integration_manager is not None and integration_id:
                    failure_status = integration_manager.finish_call(
                        integration_id,
                        success=False,
                        error=last_error,
                        latency_ms=latency_ms,
                    )
                return {
                    "status": "error",
                    "latency_ms": round(latency_ms, 3),
                    "error": last_error,
                    "attempts": attempts,
                    "transport": "http_jsonrpc",
                    "integration_state": (
                        failure_status.state if failure_status is not None else None
                    ),
                    "decision_reason": None if decision is None else decision.reason,
                    "response": None,
                }

    return {
        "status": "error",
        "latency_ms": 0.0,
        "error": last_error or "unknown",
        "attempts": attempts,
        "transport": "http_jsonrpc",
        "integration_state": None,
        "decision_reason": None if decision is None else decision.reason,
        "response": None,
    }


def _post_json(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if headers:
        for key, value in headers.items():
            name = str(key or "").strip()
            resolved = str(value or "").strip()
            if name and resolved:
                request_headers[name] = resolved
    request = Request(
        url=url,
        data=body,
        headers=request_headers,
        method="POST",
    )

    with safe_urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8", errors="replace")

    if not raw.strip():
        return {}
    return json.loads(raw)


def _extract_slot_contributions(payload: Any) -> list[dict[str, Any]]:
    resolved = _unwrap_jsonrpc(payload)

    if resolved is None or resolved is False:
        return []

    if isinstance(resolved, dict):
        if "slot" in resolved and "value" in resolved:
            return [_with_remote_source(resolved)]

        slots = resolved.get("slots")
        if isinstance(slots, list):
            return [
                _with_remote_source(item)
                for item in slots
                if isinstance(item, dict) and str(item.get("slot", "")).strip()
            ]
        if isinstance(slots, dict):
            return [
                {
                    "slot": str(slot),
                    "mode": "set",
                    "value": value,
                    "source": "mcp_remote",
                }
                for slot, value in slots.items()
                if str(slot).strip()
            ]

    if isinstance(resolved, list):
        return [
            _with_remote_source(item)
            for item in resolved
            if isinstance(item, dict) and str(item.get("slot", "")).strip()
        ]

    return []


def _unwrap_jsonrpc(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    if "result" in payload:
        return payload.get("result")

    return payload


def _with_remote_source(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized["source"] = "mcp_remote"
    return normalized


def _build_integration_id(*, plugin_name: str, endpoint: str) -> str:
    normalized_name = str(plugin_name or "").strip() or "unknown"
    normalized_endpoint = str(endpoint or "").strip() or DEFAULT_MOCK_ENDPOINT
    return f"plugin_mcp:{normalized_name}:{normalized_endpoint}"


__all__ = ["make_mcp_hooks"]
