from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.config_runtime_projection import build_orchestrator_runtime_projection
from ace_lite.orchestrator_config import OrchestratorConfig


def _warning(*, code: str, path: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "path": path,
        "severity": "warning",
        "message": message,
    }


def validate_orchestrator_config(
    payload: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    if not isinstance(payload, Mapping):
        return []

    try:
        config = build_orchestrator_runtime_projection(payload)
    except Exception as exc:  # pragma: no cover - fail-open governance helper
        return [
            _warning(
                code="CFG-VALIDATION-ERROR",
                path="plan",
                message=(
                    "config consistency validation failed open; "
                    f"{exc.__class__.__name__}: {exc}"
                ),
            )
        ]

    defaults = OrchestratorConfig()
    warnings: list[dict[str, str]] = []
    warnings.extend(_validate_plugins_config(config=config, defaults=defaults))
    warnings.extend(_validate_trace_config(config=config))
    warnings.extend(_validate_memory_profile_config(config=config, defaults=defaults))
    warnings.extend(_validate_long_term_memory_config(config=config))
    return warnings


def _validate_plugins_config(
    *,
    config: OrchestratorConfig,
    defaults: OrchestratorConfig,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if config.plugins.enabled:
        return warnings

    allowlist = tuple(config.plugins.remote_slot_allowlist or ())
    if allowlist:
        warnings.append(
            _warning(
                code="CFG-PLUGINS-001",
                path="plan.plugins.remote_slot_allowlist",
                message=(
                    "plugins.enabled=false so remote_slot_allowlist is inactive until "
                    "plugins are enabled again"
                ),
            )
        )

    if (
        str(config.plugins.remote_slot_policy_mode)
        != str(defaults.plugins.remote_slot_policy_mode)
    ):
        warnings.append(
            _warning(
                code="CFG-PLUGINS-002",
                path="plan.plugins.remote_slot_policy_mode",
                message=(
                    "plugins.enabled=false so remote_slot_policy_mode does not affect "
                    "the current runtime"
                ),
            )
        )
    return warnings


def _validate_trace_config(*, config: OrchestratorConfig) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if config.trace.export_enabled:
        return warnings

    if config.trace.otlp_enabled:
        warnings.append(
            _warning(
                code="CFG-TRACE-001",
                path="plan.trace.otlp_enabled",
                message=(
                    "trace.export_enabled=false so OTLP export stays disabled even "
                    "though otlp_enabled=true"
                ),
            )
        )

    if str(config.trace.otlp_endpoint).strip():
        warnings.append(
            _warning(
                code="CFG-TRACE-002",
                path="plan.trace.otlp_endpoint",
                message=(
                    "trace.export_enabled=false so the configured OTLP endpoint is not "
                    "used by the current runtime"
                ),
            )
        )
    return warnings


def _validate_memory_profile_config(
    *,
    config: OrchestratorConfig,
    defaults: OrchestratorConfig,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if config.memory.profile.enabled:
        return warnings

    profile = config.memory.profile
    default_profile = defaults.memory.profile
    inactive_overrides: list[str] = []
    if int(profile.top_n) != int(default_profile.top_n):
        inactive_overrides.append("top_n")
    if int(profile.token_budget) != int(default_profile.token_budget):
        inactive_overrides.append("token_budget")
    if str(profile.path) != str(default_profile.path):
        inactive_overrides.append("path")
    if int(profile.ttl_days) != int(default_profile.ttl_days):
        inactive_overrides.append("ttl_days")
    if int(profile.max_age_days) != int(default_profile.max_age_days):
        inactive_overrides.append("max_age_days")

    if inactive_overrides:
        warnings.append(
            _warning(
                code="CFG-MEMORY-001",
                path="plan.memory.profile",
                message=(
                    "memory.profile.enabled=false so profile-specific overrides are "
                    f"inactive: {', '.join(inactive_overrides)}"
                ),
            )
        )
    return warnings


def _validate_long_term_memory_config(
    *,
    config: OrchestratorConfig,
) -> list[dict[str, str]]:
    if config.memory.long_term.enabled or not config.memory.long_term.write_enabled:
        return []
    return [
        _warning(
            code="CFG-MEMORY-002",
            path="plan.memory.long_term.write_enabled",
            message=(
                "memory.long_term.write_enabled=true has no effect while "
                "memory.long_term.enabled=false"
            ),
        )
    ]


__all__ = ["validate_orchestrator_config"]
