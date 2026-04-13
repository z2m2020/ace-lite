"""Shared helper utilities for layered CLI config resolution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import click
from click.core import ParameterSource

from ace_lite.cli_app.params import _resolve_retrieval_preset
from ace_lite.config import config_get, load_layered_config
from ace_lite.config_models import validate_cli_config
from ace_lite.config_pack import load_config_pack
from ace_lite.runtime_profiles import get_runtime_profile


def _parameter_is_default(ctx: click.Context, param_name: str) -> bool:
    source = ctx.get_parameter_source(param_name)
    return source in {None, ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP}


def _resolve_from_layers(
    *,
    ctx: click.Context,
    param_name: str,
    current: Any,
    config: dict[str, Any],
    paths: list[tuple[str, ...]],
    preset: dict[str, Any] | None = None,
    preset_key: str | None = None,
    transform: Callable[[Any], Any] | None = None,
) -> Any:
    if not _parameter_is_default(ctx, param_name):
        return current

    if preset is not None and preset_key is not None:
        value = preset.get(preset_key)
        if value is not None:
            return transform(value) if transform is not None else value

    for path in paths:
        value = config_get(config, *path, default=None)
        if value is None:
            continue
        return transform(value) if transform is not None else value

    return current


def _resolve_from_config(
    *,
    ctx: click.Context,
    param_name: str,
    current: Any,
    config: dict[str, Any],
    paths: list[tuple[str, ...]],
    transform: Callable[[Any], Any] | None = None,
) -> Any:
    if not _parameter_is_default(ctx, param_name):
        return current

    for path in paths:
        value = config_get(config, *path, default=None)
        if value is None:
            continue
        return transform(value) if transform is not None else value

    return current


def _load_command_config(root: str) -> dict[str, Any]:
    raw = load_layered_config(root_dir=root, cwd=Path.cwd())
    meta = raw.get("_meta")
    payload = dict(raw)
    payload.pop("_meta", None)

    try:
        validated = validate_cli_config(payload)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if meta is not None:
        validated["_meta"] = meta
    return validated


def _deep_merge_overlay(
    base: dict[str, Any],
    overlay: Mapping[str, Any],
) -> None:
    for raw_key, value in overlay.items():
        key = str(raw_key)
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge_overlay(current, value)
            continue
        if isinstance(value, Mapping):
            nested: dict[str, Any] = {}
            _deep_merge_overlay(nested, value)
            base[key] = nested
            continue
        base[key] = value


def _apply_plan_namespace_overlays(
    *,
    config: dict[str, Any],
    namespace: str,
    runtime_profile: str | None,
    retrieval_preset: str,
    config_pack: str | None,
) -> str | None:
    runtime_profile_payload: dict[str, Any] = {}
    resolved_profile_name = None
    if runtime_profile:
        resolved_profile = get_runtime_profile(runtime_profile)
        if resolved_profile is not None:
            runtime_profile_payload = resolved_profile.plan_overrides()
            resolved_profile_name = resolved_profile.name
    preset_payload = _resolve_retrieval_preset(retrieval_preset)
    pack_result = load_config_pack(path=config_pack)

    if not runtime_profile_payload and preset_payload is None and not pack_result.enabled:
        return resolved_profile_name

    scoped_config = config.get(namespace)
    if not isinstance(scoped_config, dict):
        scoped_config = {}
        config[namespace] = scoped_config

    if runtime_profile_payload:
        _deep_merge_overlay(scoped_config, runtime_profile_payload)
        scoped_config["runtime_profile"] = resolved_profile_name
    if preset_payload is not None:
        _deep_merge_overlay(scoped_config, preset_payload)
    if pack_result.enabled:
        _deep_merge_overlay(scoped_config, pack_result.overrides)

    return resolved_profile_name
