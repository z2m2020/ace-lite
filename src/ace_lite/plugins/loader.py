from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from ace_lite.plugin_integration_manager import PluginIntegrationManager
from ace_lite.pipeline.hooks import HookBus
from ace_lite.plugins.runtime_mcp import make_mcp_hooks


@dataclass(slots=True)
class PluginConfig:
    name: str
    version: str
    runtime: str
    trusted: bool
    priority: int
    entrypoint: str | None
    mcp_endpoint: str | None
    mcp_timeout_seconds: float | None
    mcp_retries: int
    mcp_auth_env: str | None


class PluginLoader:
    def __init__(
        self,
        *,
        default_untrusted_runtime: str = "mcp",
        allow_untrusted_remote_mcp_endpoint: bool = False,
        integration_manager: PluginIntegrationManager | None = None,
    ) -> None:
        self._default_untrusted_runtime = default_untrusted_runtime
        self._allow_untrusted_remote_mcp_endpoint = bool(
            allow_untrusted_remote_mcp_endpoint
        )
        self._integration_manager = integration_manager

    def load_hooks(self, *, repo_root: str | Path) -> tuple[HookBus, list[str]]:
        root = Path(repo_root)
        plugins_dir = root / "plugins"
        hook_bus = HookBus()

        if not plugins_dir.exists() or not plugins_dir.is_dir():
            return hook_bus, []

        configs: list[tuple[PluginConfig, Path]] = []
        for manifest in sorted(plugins_dir.glob("*/plugin.yaml")):
            cfg = self._read_manifest(manifest)
            if cfg is None:
                continue
            configs.append((cfg, manifest.parent))

        configs.sort(key=lambda item: (-item[0].priority, item[0].name))

        loaded_names: list[str] = []
        for cfg, plugin_dir in configs:
            runtime = cfg.runtime
            mcp_endpoint = cfg.mcp_endpoint
            if not cfg.trusted and runtime == "in_process":
                runtime = self._default_untrusted_runtime
            if (
                runtime == "mcp"
                and not cfg.trusted
                and not self._allow_untrusted_remote_mcp_endpoint
            ):
                mcp_endpoint = self._resolve_untrusted_mcp_endpoint(
                    configured_endpoint=cfg.mcp_endpoint
                )

            if runtime == "mcp":
                headers: dict[str, str] | None = None
                auth_env = str(cfg.mcp_auth_env or "").strip()
                if auth_env:
                    token = str(os.getenv(auth_env, "")).strip()
                    if token:
                        headers = {"Authorization": token}

                before_hook, after_hook = make_mcp_hooks(
                    cfg.name,
                    endpoint=mcp_endpoint,
                    timeout_seconds=(
                        float(cfg.mcp_timeout_seconds)
                        if cfg.mcp_timeout_seconds is not None
                        else 0.3
                    ),
                    retries=cfg.mcp_retries,
                    headers=headers,
                    integration_manager=self._integration_manager,
                )
                hook_bus.register_before(cfg.name, before_hook)
                hook_bus.register_after(cfg.name, after_hook)
                loaded_names.append(cfg.name)
                continue

            if runtime == "in_process":
                if not cfg.entrypoint:
                    continue
                module = self._load_module(plugin_dir / cfg.entrypoint, cfg.name)
                if module is None:
                    continue
                before = getattr(module, "before_stage", None)
                after = getattr(module, "after_stage", None)
                if callable(before):
                    hook_bus.register_before(cfg.name, before)
                if callable(after):
                    hook_bus.register_after(cfg.name, after)
                loaded_names.append(cfg.name)

        return hook_bus, loaded_names

    def _read_manifest(self, manifest_path: Path) -> PluginConfig | None:
        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(raw, dict):
            return None

        name = str(raw.get("name") or manifest_path.parent.name)
        version = str(raw.get("version") or "0.0.0")
        runtime = str(raw.get("runtime") or "in_process").strip().lower()
        trusted = bool(raw.get("trusted", False))
        priority_raw = raw.get("priority", 0)
        try:
            priority = int(priority_raw)
        except (TypeError, ValueError):
            priority = 0
        entrypoint = raw.get("entrypoint")
        mcp_endpoint = raw.get("mcp_endpoint")
        mcp_timeout_seconds = raw.get("mcp_timeout_seconds", raw.get("timeout_seconds"))
        mcp_retries = raw.get("mcp_retries", raw.get("retries", 0))
        mcp_auth_env = raw.get("mcp_auth_env", raw.get("auth_env"))

        normalized_timeout: float | None = None
        try:
            if mcp_timeout_seconds is not None:
                normalized_timeout = float(mcp_timeout_seconds)
        except (TypeError, ValueError):
            normalized_timeout = None
        if normalized_timeout is not None and normalized_timeout <= 0.0:
            normalized_timeout = None

        normalized_retries = 0
        try:
            normalized_retries = int(str(mcp_retries))
        except (TypeError, ValueError):
            normalized_retries = 0
        normalized_retries = max(0, normalized_retries)

        normalized_auth_env = str(mcp_auth_env).strip() if mcp_auth_env else None
        if normalized_auth_env == "":
            normalized_auth_env = None

        return PluginConfig(
            name=name,
            version=version,
            runtime=runtime,
            trusted=trusted,
            priority=priority,
            entrypoint=str(entrypoint) if entrypoint else None,
            mcp_endpoint=str(mcp_endpoint) if mcp_endpoint else None,
            mcp_timeout_seconds=normalized_timeout,
            mcp_retries=normalized_retries,
            mcp_auth_env=normalized_auth_env,
        )

    @staticmethod
    def _load_module(path: Path, plugin_name: str) -> Any | None:
        if not path.exists() or not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(
            f"ace_plugin_{plugin_name}", str(path)
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _resolve_untrusted_mcp_endpoint(
        *, configured_endpoint: str | None
    ) -> str | None:
        endpoint = str(configured_endpoint or "").strip()
        if not endpoint:
            return None

        parsed = urlparse(endpoint)
        if parsed.scheme == "mock":
            return endpoint
        return None


__all__ = ["PluginConfig", "PluginLoader"]
