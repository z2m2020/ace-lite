from __future__ import annotations

from ace_lite.orchestrator_plugin_support import load_orchestrator_plugins
from ace_lite.pipeline.hooks import HookBus


def test_load_orchestrator_plugins_returns_empty_bus_when_disabled() -> None:
    class _Loader:
        def load_hooks(self, *, repo_root: str):
            raise AssertionError("load_hooks should not be called")

    hook_bus, loaded = load_orchestrator_plugins(
        plugins_enabled=False,
        plugin_loader=_Loader(),
        root="/repo",
    )

    assert isinstance(hook_bus, HookBus)
    assert loaded == []


def test_load_orchestrator_plugins_delegates_when_enabled() -> None:
    expected_bus = HookBus()

    class _Loader:
        def load_hooks(self, *, repo_root: str):
            assert repo_root == "/repo"
            return expected_bus, ["demo-plugin"]

    hook_bus, loaded = load_orchestrator_plugins(
        plugins_enabled=True,
        plugin_loader=_Loader(),
        root="/repo",
    )

    assert hook_bus is expected_bus
    assert loaded == ["demo-plugin"]
