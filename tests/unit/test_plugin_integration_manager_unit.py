from __future__ import annotations

from ace_lite.plugin_integration_manager import PluginIntegrationManager


def test_register_endpoint_exposes_closed_state_and_policy() -> None:
    manager = PluginIntegrationManager(
        default_timeout_seconds=0.4,
        default_concurrency_limit=2,
    )

    status = manager.register_endpoint(
        "plugin:demo",
        endpoint="http://localhost:9000/mcp",
        transport="http_jsonrpc",
        plugin_name="demo",
        retries=1,
        metadata={"source": "plugin_manifest"},
    )

    assert status.state == "closed"
    assert status.policy.timeout_seconds == 0.4
    assert status.policy.concurrency_limit == 2
    assert status.policy.failure_threshold == 3
    assert status.policy.recovery_timeout_seconds == 30.0
    assert status.policy.half_open_max_calls == 1
    assert status.policy.retries == 1
    assert status.metadata == {"source": "plugin_manifest"}


def test_manager_opens_after_failure_threshold_then_recovers_to_half_open() -> None:
    manager = PluginIntegrationManager(default_failure_threshold=2)
    manager.register_endpoint(
        "plugin:demo",
        endpoint="http://localhost:9000/mcp",
        transport="http_jsonrpc",
        timeout_seconds=0.3,
        recovery_timeout_seconds=5.0,
    )

    first = manager.start_call("plugin:demo", now=0.0)
    assert first.allowed is True
    manager.finish_call("plugin:demo", success=False, error="boom-1", now=0.1)

    second = manager.start_call("plugin:demo", now=1.0)
    assert second.allowed is True
    opened = manager.finish_call("plugin:demo", success=False, error="boom-2", now=1.1)

    assert opened.state == "open"
    assert opened.consecutive_failures == 2
    assert opened.last_transition_reason == "failure_threshold"

    blocked = manager.start_call("plugin:demo", now=2.0)
    assert blocked.allowed is False
    assert blocked.state == "open"
    assert blocked.reason == "circuit_open"

    half_open = manager.get_status("plugin:demo", now=6.2)
    assert half_open.state == "half_open"
    assert half_open.last_transition_reason == "recovery_timeout_elapsed"

    probe = manager.start_call("plugin:demo", now=6.3)
    assert probe.allowed is True
    assert probe.state == "half_open"

    closed = manager.finish_call("plugin:demo", success=True, latency_ms=12.5, now=6.4)
    assert closed.state == "closed"
    assert closed.consecutive_failures == 0
    assert closed.last_transition_reason == "success"
    assert closed.last_latency_ms == 12.5


def test_half_open_failure_reopens_circuit() -> None:
    manager = PluginIntegrationManager(default_failure_threshold=1)
    manager.register_endpoint(
        "plugin:demo",
        endpoint="http://localhost:9000/mcp",
        transport="http_jsonrpc",
        recovery_timeout_seconds=2.0,
    )

    manager.start_call("plugin:demo", now=0.0)
    opened = manager.finish_call("plugin:demo", success=False, error="boom", now=0.1)
    assert opened.state == "open"

    manager.start_call("plugin:demo", now=2.2)
    reopened = manager.finish_call(
        "plugin:demo",
        success=False,
        error="probe failed",
        now=2.3,
    )
    assert reopened.state == "open"
    assert reopened.last_transition_reason == "half_open_failure"


def test_manager_enforces_concurrency_limit() -> None:
    manager = PluginIntegrationManager()
    manager.register_endpoint(
        "plugin:demo",
        endpoint="http://localhost:9000/mcp",
        transport="http_jsonrpc",
        concurrency_limit=2,
    )

    first = manager.start_call("plugin:demo", now=0.0)
    second = manager.start_call("plugin:demo", now=0.1)
    third = manager.start_call("plugin:demo", now=0.2)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.reason == "concurrency_limit"

    status = manager.finish_call("plugin:demo", success=True, now=0.3)
    assert status.inflight_calls == 1
