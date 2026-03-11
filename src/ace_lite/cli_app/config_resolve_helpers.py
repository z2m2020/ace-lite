"""Shared helper utilities for layered CLI config resolution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from click.core import ParameterSource

from ace_lite.config import config_get, load_layered_config
from ace_lite.config_models import validate_cli_config


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
