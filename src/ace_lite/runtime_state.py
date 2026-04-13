from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.memory import MemoryProvider
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.plugin_runtime import PluginRuntime
from ace_lite.plugin_integration_manager import PluginIntegrationManager
from ace_lite.plugins.loader import PluginLoader
from ace_lite.signal_extractor import SignalExtractor


@dataclass(slots=True)
class RuntimeServiceBundle:
    memory_provider: MemoryProvider
    plugin_loader: PluginLoader
    plugin_runtime: PluginRuntime
    plugin_integration_manager: PluginIntegrationManager
    lsp_broker: LspDiagnosticsBroker | None
    signal_extractor: SignalExtractor
    skill_manifest: Any
    durable_stats_store_factory: Callable[[], Any]


@dataclass(slots=True)
class RuntimeState:
    config: OrchestratorConfig
    services: RuntimeServiceBundle
    durable_stats_session_id: str
    conventions_files: list[str] | None = None
    conventions_hashes: dict[str, str] = field(default_factory=dict)
    last_root: str | None = None
    last_durable_stats_payload: dict[str, Any] | None = None

    def update_conventions_hashes(self, file_hashes: dict[str, Any] | None) -> None:
        normalized = {
            str(path): str(sha)
            for path, sha in (file_hashes or {}).items()
        }
        self.conventions_hashes.clear()
        self.conventions_hashes.update(normalized)

    def note_plan_root(self, root: str | None) -> None:
        text = str(root or "").strip()
        self.last_root = text or None

    def note_durable_stats(self, payload: dict[str, Any] | None) -> None:
        self.last_durable_stats_payload = dict(payload or {}) if payload else None


__all__ = ["RuntimeServiceBundle", "RuntimeState"]
