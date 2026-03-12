from __future__ import annotations

import json
import time
from urllib.error import URLError

from ace_lite.plugin_integration_manager import PluginIntegrationManager
from ace_lite.pipeline.types import StageContext, StageEvent
from ace_lite.plugins import runtime_mcp


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _build_event() -> StageEvent:
    return StageEvent(
        stage="augment",
        when="after",
        context=StageContext(query="q", repo="demo", root=".", state={}),
        payload={"candidate_files": ["src/app.py"]},
    )


def test_runtime_mcp_timeout_opens_then_half_open_recovers_to_closed(monkeypatch) -> None:
    outcomes: list[object] = [
        TimeoutError("simulated timeout"),
        {"result": {"slots": []}},
        {"result": {"slots": []}},
    ]
    network_calls: list[str] = []

    def fake_urlopen(*_args, **_kwargs):
        network_calls.append("call")
        current = outcomes.pop(0)
        if isinstance(current, BaseException):
            raise current
        return _FakeResponse(current)

    monkeypatch.setattr(runtime_mcp, "safe_urlopen", fake_urlopen)

    manager = PluginIntegrationManager(
        default_failure_threshold=1,
        default_recovery_timeout_seconds=0.05,
    )
    before_hook, after_hook = runtime_mcp.make_mcp_hooks(
        "chaos-plugin",
        endpoint="http://localhost:9000/mcp",
        integration_manager=manager,
    )
    event = _build_event()

    assert before_hook(event) is True
    degraded = after_hook(event)
    degraded_row = degraded["slots"][0]["value"]
    assert degraded_row["before_status"] == "error"
    assert degraded_row["status"] == "degraded"
    assert degraded_row["decision_reason"] == "circuit_open"

    opened = manager.list_statuses()[0]
    assert opened.state == "open"

    time.sleep(0.08)
    half_open = manager.get_status(opened.integration_id)
    assert half_open.state == "half_open"

    assert before_hook(event) is True
    recovered = after_hook(event)
    recovered_row = recovered["slots"][0]["value"]
    assert recovered_row["status"] == "ok"

    closed = manager.get_status(opened.integration_id)
    assert closed.state == "closed"
    assert len(network_calls) == 3


def test_runtime_mcp_partial_recovery_failure_reopens_before_eventual_close(
    monkeypatch,
) -> None:
    outcomes: list[object] = [
        URLError("initial outage"),
        TimeoutError("half-open probe timeout"),
        {"result": {"slots": []}},
        {"result": {"slots": []}},
    ]
    network_calls: list[str] = []

    def fake_urlopen(*_args, **_kwargs):
        network_calls.append("call")
        current = outcomes.pop(0)
        if isinstance(current, BaseException):
            raise current
        return _FakeResponse(current)

    monkeypatch.setattr(runtime_mcp, "safe_urlopen", fake_urlopen)

    manager = PluginIntegrationManager(
        default_failure_threshold=1,
        default_recovery_timeout_seconds=0.05,
    )
    before_hook, after_hook = runtime_mcp.make_mcp_hooks(
        "chaos-plugin",
        endpoint="http://localhost:9000/mcp",
        integration_manager=manager,
    )
    event = _build_event()

    assert before_hook(event) is True
    first_degraded = after_hook(event)
    assert first_degraded["slots"][0]["value"]["status"] == "degraded"

    integration_id = manager.list_statuses()[0].integration_id
    assert manager.get_status(integration_id).state == "open"

    time.sleep(0.08)
    assert manager.get_status(integration_id).state == "half_open"

    assert before_hook(event) is True
    second_degraded = after_hook(event)
    second_row = second_degraded["slots"][0]["value"]
    assert second_row["before_status"] == "error"
    assert second_row["before_integration_state"] == "open"
    assert second_row["status"] == "degraded"
    assert second_row["decision_reason"] == "circuit_open"
    assert manager.get_status(integration_id).state == "open"

    time.sleep(0.08)
    assert manager.get_status(integration_id).state == "half_open"

    assert before_hook(event) is True
    final_result = after_hook(event)
    assert final_result["slots"][0]["value"]["status"] == "ok"
    assert manager.get_status(integration_id).state == "closed"
    assert len(network_calls) == 4
