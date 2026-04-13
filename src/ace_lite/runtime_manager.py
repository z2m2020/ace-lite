from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.memory import MemoryProvider, NullMemoryProvider
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.plugin_runtime import (
    PluginRuntime,
    PluginRuntimeConfig,
    normalize_remote_slot_allowlist,
    normalize_remote_slot_policy_mode,
)
from ace_lite.plugin_integration_manager import PluginIntegrationManager
from ace_lite.plugins.loader import PluginLoader
from ace_lite.runtime_state import RuntimeServiceBundle, RuntimeState
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.signal_extractor import SignalExtractor
from ace_lite.skills import build_skill_manifest
from ace_lite.stage_artifact_cache import StageArtifactCache
from ace_lite.stage_artifact_cache_gc import run_bounded_stage_artifact_cache_gc

logger = logging.getLogger(__name__)

ShutdownHook = Callable[[RuntimeState], Any]


class RuntimeManager:
    def __init__(
        self,
        *,
        config: OrchestratorConfig | None = None,
        memory_provider: MemoryProvider | None = None,
        plugin_loader: PluginLoader | None = None,
        plugin_runtime: PluginRuntime | None = None,
        plugin_integration_manager: PluginIntegrationManager | None = None,
        lsp_broker: LspDiagnosticsBroker | None = None,
        signal_extractor: SignalExtractor | None = None,
        skill_manifest: Any = None,
        durable_stats_store_factory: Callable[[], Any] | None = None,
        durable_stats_session_id: str | None = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._memory_provider = memory_provider
        self._plugin_loader = plugin_loader
        self._plugin_runtime = plugin_runtime
        self._plugin_integration_manager = plugin_integration_manager
        self._lsp_broker = lsp_broker
        self._signal_extractor = signal_extractor
        self._skill_manifest = skill_manifest
        self._durable_stats_store_factory = durable_stats_store_factory
        self._durable_stats_session_id = (
            str(durable_stats_session_id).strip()
            if durable_stats_session_id is not None
            else f"session-{uuid4().hex[:12]}"
        )
        self._state: RuntimeState | None = None
        self._shutdown_hooks: list[ShutdownHook] = []
        self._shutdown_summary: dict[str, Any] | None = None
        self._lifecycle_hooks_registered = False

    @property
    def state(self) -> RuntimeState | None:
        return self._state

    def startup(self) -> RuntimeState:
        if self._state is not None:
            return self._state

        config = self._config
        conventions_files = (
            list(config.index.conventions_files)
            if config.index.conventions_files
            else None
        )

        memory_provider = self._memory_provider or NullMemoryProvider()
        plugin_integration_manager = (
            self._plugin_integration_manager or PluginIntegrationManager()
        )
        plugin_loader = self._plugin_loader or PluginLoader(
            default_untrusted_runtime="mcp",
            integration_manager=plugin_integration_manager,
        )
        plugin_runtime = self._plugin_runtime or PluginRuntime(
            config=PluginRuntimeConfig(
                remote_slot_allowlist=normalize_remote_slot_allowlist(
                    config.plugins.remote_slot_allowlist
                ),
                remote_slot_policy_mode=normalize_remote_slot_policy_mode(
                    config.plugins.remote_slot_policy_mode
                ),
            )
        )
        lsp_broker = self._lsp_broker
        if lsp_broker is None and (config.lsp.commands or config.lsp.xref_commands):
            lsp_broker = LspDiagnosticsBroker(
                commands=config.lsp.commands,
                xref_commands=config.lsp.xref_commands,
            )
        signal_extractor = self._signal_extractor or SignalExtractor(
            keywords=config.memory.capture.keywords,
            min_query_length=config.memory.capture.min_query_length,
        )
        skill_manifest = self._skill_manifest
        if skill_manifest is None:
            if config.skills.manifest is not None:
                skill_manifest = config.skills.manifest
            else:
                skill_root = Path(config.skills.dir or "skills")
                skill_manifest = build_skill_manifest(skill_root)
        durable_stats_store_factory = (
            self._durable_stats_store_factory or DurableStatsStore
        )

        self._state = RuntimeState(
            config=config,
            services=RuntimeServiceBundle(
                memory_provider=memory_provider,
                plugin_loader=plugin_loader,
                plugin_runtime=plugin_runtime,
                plugin_integration_manager=plugin_integration_manager,
                lsp_broker=lsp_broker,
                signal_extractor=signal_extractor,
                skill_manifest=skill_manifest,
                durable_stats_store_factory=durable_stats_store_factory,
            ),
            durable_stats_session_id=self._durable_stats_session_id,
            conventions_files=conventions_files,
        )
        self._shutdown_summary = None
        return self._state

    def register_shutdown_hook(self, hook: ShutdownHook) -> None:
        self._shutdown_hooks.append(hook)

    def ensure_shutdown_hooks(self) -> None:
        if self._lifecycle_hooks_registered:
            return
        self.register_shutdown_hook(self._flush_runtime_stats_hook)
        self.register_shutdown_hook(self._cleanup_stage_artifact_temps_hook)
        self._lifecycle_hooks_registered = True

    def shutdown(self) -> dict[str, Any]:
        if self._shutdown_summary is not None:
            return dict(self._shutdown_summary)

        state = self._state
        if state is None:
            self._shutdown_summary = {
                "started": False,
                "shutdown": False,
                "executed_count": 0,
                "errors": [],
                "results": [],
            }
            return dict(self._shutdown_summary)

        errors: list[dict[str, str]] = []
        results: list[dict[str, Any]] = []
        for hook in reversed(self._shutdown_hooks):
            hook_name = getattr(hook, "__name__", hook.__class__.__name__)
            try:
                results.append(
                    {
                        "hook": hook_name,
                        "ok": True,
                        "result": hook(state),
                    }
                )
            except Exception as exc:
                logger.warning(
                    "runtime_manager.shutdown.error",
                    extra={
                        "hook": hook_name,
                        "error": str(exc),
                    },
                )
                payload = {"hook": hook_name, "error": str(exc)}
                errors.append(payload)
                results.append({**payload, "ok": False})

        self._shutdown_summary = {
            "started": True,
            "shutdown": True,
            "executed_count": len(self._shutdown_hooks),
            "errors": errors,
            "results": results,
        }
        return dict(self._shutdown_summary)

    @staticmethod
    def _cleanup_stage_artifact_temps_hook(state: RuntimeState) -> dict[str, Any]:
        if not state.last_root:
            return {"ok": True, "skipped": True, "reason": "no_repo_root"}
        result = run_bounded_stage_artifact_cache_gc(
            repo_root=state.last_root,
            budget_ms=50.0,
            max_delete=16,
        )
        return {
            "ok": True,
            "skipped": False,
            "repo_root": state.last_root,
            **result,
        }

    @staticmethod
    def _flush_runtime_stats_hook(state: RuntimeState) -> dict[str, Any]:
        payload = state.last_durable_stats_payload or {}
        session_id = str(payload.get("session_id") or state.durable_stats_session_id).strip()
        store = state.services.durable_stats_store_factory()
        result = {
            "ok": True,
            "session_id": session_id,
            "db_path": str(getattr(store, "db_path", "")),
            "recorded": bool(payload.get("recorded", False)),
        }
        if not hasattr(store, "read_scope") or not session_id:
            result["skipped"] = True
            return result
        scope = store.read_scope(scope_kind="session", scope_key=session_id)
        if scope is None:
            result["skipped"] = True
            return result
        scope_payload = scope.to_payload()
        result.update(
            {
                "skipped": False,
                "invocation_count": int(
                    scope_payload.get("counters", {}).get("invocation_count", 0) or 0
                ),
                "status_counts": {
                    "success_count": int(
                        scope_payload.get("counters", {}).get("success_count", 0) or 0
                    ),
                    "degraded_count": int(
                        scope_payload.get("counters", {}).get("degraded_count", 0) or 0
                    ),
                    "failure_count": int(
                        scope_payload.get("counters", {}).get("failure_count", 0) or 0
                    ),
                },
            }
        )
        return result


__all__ = ["RuntimeManager", "ShutdownHook"]
