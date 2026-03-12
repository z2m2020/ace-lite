from __future__ import annotations

import textwrap
from pathlib import Path
from urllib.error import URLError

from ace_lite.plugin_integration_manager import PluginIntegrationManager
from ace_lite.pipeline.types import StageContext, StageEvent
from ace_lite.plugins import runtime_mcp
from ace_lite.plugins.loader import PluginLoader


def test_plugin_loader_loads_trusted_inprocess_plugin(
    tmp_path: Path, tmp_plugin_dir: Path
) -> None:
    plugin_dir = tmp_plugin_dir / "demo"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: demo
            version: 1.0.0
            runtime: in_process
            trusted: true
            priority: 10
            entrypoint: main.py
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_text(
        textwrap.dedent(
            """
            from ace_lite.pipeline.types import StageEvent

            def before_stage(event: StageEvent) -> bool:
                return event.stage == "memory"

            def after_stage(event: StageEvent) -> dict[str, object]:
                return {"plugin": {"name": "demo", "stage": event.stage}}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    loader = PluginLoader(default_untrusted_runtime="mcp")
    hook_bus, loaded = loader.load_hooks(repo_root=tmp_path)

    assert loaded == ["demo"]

    event = StageEvent(
        stage="memory",
        when="after",
        context=StageContext(query="q", repo="r", root=str(tmp_path), state={}),
        payload={},
    )
    assert hook_bus.dispatch_before(event) == ["demo"]
    contributions, after_fired = hook_bus.dispatch_after(event)
    assert after_fired == ["demo"]
    assert {item["slot"] for item in contributions} == {"plugin.name", "plugin.stage"}


def test_plugin_loader_downgrades_untrusted_inprocess_to_mcp(
    tmp_path: Path, tmp_plugin_dir: Path
) -> None:
    plugin_dir = tmp_plugin_dir / "unsafe"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: unsafe
            version: 1.0.0
            runtime: in_process
            trusted: false
            priority: 1
            entrypoint: main.py
            mcp_endpoint: http://localhost:9000/mcp
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_text(
        "def before_stage(event):\n    return False\n", encoding="utf-8"
    )

    loader = PluginLoader(default_untrusted_runtime="mcp")
    hook_bus, loaded = loader.load_hooks(repo_root=tmp_path)

    assert loaded == ["unsafe"]

    event = StageEvent(
        stage="index",
        when="after",
        context=StageContext(query="q", repo="r", root=str(tmp_path), state={}),
        payload={},
    )
    contributions, _ = hook_bus.dispatch_after(event)
    assert contributions[0]["slot"] == "observability.mcp_plugins"
    assert contributions[0]["mode"] == "append"
    assert contributions[0]["value"]["name"] == "unsafe"
    assert contributions[0]["value"]["endpoint"] == "mock://mcp"


def test_plugin_loader_allows_untrusted_remote_mcp_endpoint_when_opted_in(
    tmp_path: Path, tmp_plugin_dir: Path
) -> None:
    plugin_dir = tmp_plugin_dir / "unsafe-remote"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: unsafe-remote
            version: 1.0.0
            runtime: in_process
            trusted: false
            priority: 1
            entrypoint: main.py
            mcp_endpoint: http://localhost:9000/mcp
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_text(
        "def before_stage(event):\n    return False\n", encoding="utf-8"
    )

    loader = PluginLoader(
        default_untrusted_runtime="mcp",
        allow_untrusted_remote_mcp_endpoint=True,
    )
    hook_bus, loaded = loader.load_hooks(repo_root=tmp_path)

    assert loaded == ["unsafe-remote"]

    event = StageEvent(
        stage="index",
        when="after",
        context=StageContext(query="q", repo="r", root=str(tmp_path), state={}),
        payload={},
    )
    contributions, _ = hook_bus.dispatch_after(event)
    assert contributions[0]["slot"] == "observability.mcp_plugins"
    assert contributions[0]["value"]["endpoint"] == "http://localhost:9000/mcp"


def test_plugin_loader_invalid_priority_falls_back_to_zero(
    tmp_path: Path, tmp_plugin_dir: Path
) -> None:
    plugin_dir = tmp_plugin_dir / "priority-fallback"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: priority-fallback
            version: 1.0.0
            runtime: in_process
            trusted: true
            priority: high
            entrypoint: main.py
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_text(
        textwrap.dedent(
            """
            from ace_lite.pipeline.types import StageEvent

            def before_stage(event: StageEvent) -> bool:
                return event.stage == "memory"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    loader = PluginLoader(default_untrusted_runtime="mcp")
    hook_bus, loaded = loader.load_hooks(repo_root=tmp_path)

    assert loaded == ["priority-fallback"]

    event = StageEvent(
        stage="memory",
        when="before",
        context=StageContext(query="q", repo="r", root=str(tmp_path), state={}),
        payload={},
    )
    assert hook_bus.dispatch_before(event) == ["priority-fallback"]


def test_plugin_loader_threads_mcp_timeout_retries_and_auth_env(
    tmp_path: Path, tmp_plugin_dir: Path, monkeypatch
) -> None:
    plugin_dir = tmp_plugin_dir / "mcp-config"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: mcp-config
            version: 1.0.0
            runtime: mcp
            trusted: true
            priority: 1
            mcp_endpoint: http://localhost:9000/mcp
            mcp_timeout_seconds: 0.7
            mcp_retries: 2
            mcp_auth_env: DEMO_MCP_AUTH
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("DEMO_MCP_AUTH", "Bearer secret-token")

    captured: dict[str, object] = {}

    def fake_make_mcp_hooks(
        plugin_name: str,
        *,
        endpoint: str | None = None,
        timeout_seconds: float = 0.3,
        retries: int = 0,
        headers: dict[str, str] | None = None,
        integration_manager: PluginIntegrationManager | None = None,
    ):
        captured["name"] = plugin_name
        captured["endpoint"] = endpoint
        captured["timeout_seconds"] = timeout_seconds
        captured["retries"] = retries
        captured["headers"] = headers
        captured["integration_manager"] = integration_manager

        def before_stage(_event: StageEvent) -> bool:
            return True

        def after_stage(_event: StageEvent) -> dict[str, object]:
            return {}

        return before_stage, after_stage

    monkeypatch.setattr("ace_lite.plugins.loader.make_mcp_hooks", fake_make_mcp_hooks)

    loader = PluginLoader(default_untrusted_runtime="mcp")
    _hook_bus, loaded = loader.load_hooks(repo_root=tmp_path)

    assert loaded == ["mcp-config"]
    assert captured["endpoint"] == "http://localhost:9000/mcp"
    assert float(captured["timeout_seconds"]) == 0.7
    assert int(captured["retries"]) == 2
    assert captured["headers"] == {"Authorization": "Bearer secret-token"}
    assert captured["integration_manager"] is None


def test_plugin_loader_threads_integration_manager_into_mcp_hooks(
    tmp_path: Path, tmp_plugin_dir: Path, monkeypatch
) -> None:
    plugin_dir = tmp_plugin_dir / "mcp-with-manager"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: mcp-with-manager
            version: 1.0.0
            runtime: mcp
            trusted: true
            priority: 1
            mcp_endpoint: http://localhost:9000/mcp
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, object] = {}
    manager = PluginIntegrationManager()

    def fake_make_mcp_hooks(
        plugin_name: str,
        *,
        endpoint: str | None = None,
        timeout_seconds: float = 0.3,
        retries: int = 0,
        headers: dict[str, str] | None = None,
        integration_manager: PluginIntegrationManager | None = None,
    ):
        captured["plugin_name"] = plugin_name
        captured["endpoint"] = endpoint
        captured["integration_manager"] = integration_manager

        def before_stage(_event: StageEvent) -> bool:
            return True

        def after_stage(_event: StageEvent) -> dict[str, object]:
            return {}

        return before_stage, after_stage

    monkeypatch.setattr("ace_lite.plugins.loader.make_mcp_hooks", fake_make_mcp_hooks)

    loader = PluginLoader(
        default_untrusted_runtime="mcp",
        integration_manager=manager,
    )
    _hook_bus, loaded = loader.load_hooks(repo_root=tmp_path)

    assert loaded == ["mcp-with-manager"]
    assert captured["plugin_name"] == "mcp-with-manager"
    assert captured["endpoint"] == "http://localhost:9000/mcp"
    assert captured["integration_manager"] is manager


def test_runtime_mcp_extract_slot_contributions_sets_remote_source() -> None:
    payload = {
        "result": {
            "slots": {
                "source_plan.writeback_template.decision": "from-remote",
            }
        }
    }

    contributions = runtime_mcp._extract_slot_contributions(payload)

    assert len(contributions) == 1
    assert contributions[0]["slot"] == "source_plan.writeback_template.decision"
    assert contributions[0]["source"] == "mcp_remote"


def test_runtime_mcp_post_json_includes_extra_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout=0.0):
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(runtime_mcp, "safe_urlopen", fake_urlopen)

    runtime_mcp._post_json(
        url="http://localhost:9000/mcp",
        payload={"jsonrpc": "2.0", "id": "t", "method": "ping", "params": {}},
        timeout_seconds=0.1,
        headers={"Authorization": "Bearer secret-token"},
    )

    headers = {str(k).lower(): str(v) for k, v in dict(captured["headers"]).items()}
    assert headers.get("authorization") == "Bearer secret-token"


def test_runtime_mcp_repeated_failure_degrades_via_integration_manager(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_urlopen(*_args, **_kwargs):
        calls.append("attempt")
        raise URLError("down")

    monkeypatch.setattr(runtime_mcp, "safe_urlopen", fake_urlopen)

    manager = PluginIntegrationManager(default_failure_threshold=1)
    before_hook, after_hook = runtime_mcp.make_mcp_hooks(
        "remote-plugin",
        endpoint="http://localhost:9000/mcp",
        integration_manager=manager,
    )
    event = StageEvent(
        stage="augment",
        when="after",
        context=StageContext(query="q", repo="r", root=".", state={}),
        payload={},
    )

    assert before_hook(event) is True
    result = after_hook(event)

    plugin_row = result["slots"][0]["value"]
    assert plugin_row["before_status"] == "error"
    assert plugin_row["before_integration_state"] == "open"
    assert plugin_row["status"] == "degraded"
    assert plugin_row["integration_state"] == "open"
    assert plugin_row["decision_reason"] == "circuit_open"
    assert len(calls) == 1


def test_plan_post_processor_plugin_patches_source_plan(
    tmp_path: Path, tmp_plugin_dir: Path, null_orchestrator
) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    plugin_dir = tmp_plugin_dir / "plan_post_processor"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (tmp_path / "src" / "main.py").write_text(
        "def run():\n    return 1\n", encoding="utf-8"
    )

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            """
            name: plan-post-processor
            version: 1.0.0
            runtime: in_process
            trusted: true
            priority: 100
            entrypoint: main.py
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_text(
        textwrap.dedent(
            """
            from ace_lite.pipeline.types import StageEvent

            def before_stage(event: StageEvent) -> bool:
                return event.stage == "source_plan"

            def after_stage(event: StageEvent) -> dict[str, object]:
                if event.stage != "source_plan":
                    return {}
                return {
                    "writeback_template": {
                        "decision": "Document final decision clearly.",
                        "caveat": "Include rollback note if applicable.",
                    }
                }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    payload = null_orchestrator.plan(
        query="implement run", repo="demo", root=str(tmp_path)
    )

    template = payload["source_plan"]["writeback_template"]
    assert template["decision"] == "Document final decision clearly."
    assert template["caveat"] == "Include rollback note if applicable."
    assert "plan-post-processor" in payload["observability"]["plugins_loaded"]

    policy_summary = payload["observability"]["plugin_policy_summary"]
    assert policy_summary["mode"] == "strict"
    assert policy_summary["allowlist"] == ["observability.mcp_plugins"]
    assert policy_summary["totals"] == {
        "applied": 2,
        "conflicts": 0,
        "blocked": 0,
        "warn": 0,
        "remote_applied": 0,
    }
    source_plan_row = next(
        item for item in policy_summary["by_stage"] if item["stage"] == "source_plan"
    )
    assert source_plan_row == {
        "stage": "source_plan",
        "applied": 2,
        "conflicts": 0,
        "blocked": 0,
        "warn": 0,
        "remote_applied": 0,
    }
