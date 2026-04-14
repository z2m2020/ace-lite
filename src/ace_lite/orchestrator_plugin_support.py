from __future__ import annotations

from typing import Protocol

from ace_lite.pipeline.hooks import HookBus


class PluginHookLoader(Protocol):
    def load_hooks(self, *, repo_root: str) -> tuple[HookBus, list[str]]: ...


def load_orchestrator_plugins(
    *,
    plugins_enabled: bool,
    plugin_loader: PluginHookLoader,
    root: str,
) -> tuple[HookBus, list[str]]:
    if not plugins_enabled:
        return HookBus(), []
    return plugin_loader.load_hooks(repo_root=root)

__all__ = ["PluginHookLoader", "load_orchestrator_plugins"]
