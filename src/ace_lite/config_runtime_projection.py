from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from ace_lite.cli_app.params import parse_lsp_commands_from_config
from ace_lite.config_models import RuntimeConfig
from ace_lite.orchestrator_config import OrchestratorConfig


def _copy_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in payload.items():
        normalized_key = str(key)
        if isinstance(value, Mapping):
            copied[normalized_key] = _copy_mapping(value)
        elif isinstance(value, list):
            copied[normalized_key] = list(value)
        else:
            copied[normalized_key] = value
    return copied


def _split_csv(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
        return values or None
    if isinstance(value, (list, tuple)):
        values = [str(item).strip() for item in value if str(item).strip()]
        return values or None
    return None


def normalize_orchestrator_runtime_projection(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize boundary payloads before runtime projection."""
    normalized = _copy_mapping(payload or {})
    index_payload = normalized.get("index")
    if isinstance(index_payload, dict):
        languages = _split_csv(index_payload.get("languages"))
        if languages is not None:
            index_payload["languages"] = languages
        conventions = _split_csv(index_payload.get("conventions_files"))
        if conventions is not None:
            index_payload["conventions_files"] = conventions
    lsp_payload = normalized.get("lsp")
    if isinstance(lsp_payload, dict):
        for key in ("commands", "xref_commands"):
            value = lsp_payload.get(key)
            if value is not None:
                lsp_payload[key] = parse_lsp_commands_from_config(value)
    return normalized


def build_orchestrator_runtime_projection(
    payload: Mapping[str, Any] | None,
) -> OrchestratorConfig:
    """Project boundary configuration into the runtime orchestrator model."""
    normalized = normalize_orchestrator_runtime_projection(payload)
    return cast(OrchestratorConfig, OrchestratorConfig.model_validate(normalized))


def dump_orchestrator_runtime_projection(
    payload: Mapping[str, Any] | None,
    *,
    exclude_none: bool,
    by_alias: bool,
) -> dict[str, Any]:
    """Project and dump orchestrator runtime configuration."""
    return cast(
        dict[str, Any],
        build_orchestrator_runtime_projection(payload).model_dump(
            exclude_none=exclude_none,
            by_alias=by_alias,
        ),
    )


def dump_runtime_boundary_projection(
    payload: Mapping[str, Any] | None,
    *,
    exclude_none: bool,
    by_alias: bool,
) -> dict[str, Any]:
    """Validate and dump runtime-only boundary configuration."""
    normalized = _copy_mapping(payload or {})
    return cast(
        dict[str, Any],
        RuntimeConfig.model_validate(normalized).model_dump(
            exclude_none=exclude_none,
            by_alias=by_alias,
        ),
    )


__all__ = [
    "build_orchestrator_runtime_projection",
    "dump_orchestrator_runtime_projection",
    "dump_runtime_boundary_projection",
    "normalize_orchestrator_runtime_projection",
]
