"""Console-safe output helpers for CLI commands."""

from __future__ import annotations

import json
from typing import Any

import click


def echo_json(payload: Any, *, indent: int | None = None) -> None:
    """Echo JSON to stdout while avoiding Windows console encoding crashes.

    Primary path preserves unicode characters (`ensure_ascii=False`). If the
    current stdout encoding cannot represent some characters (common on Windows
    consoles using legacy code pages like GBK), fall back to ASCII-escaped JSON.
    """

    try:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=indent))
    except UnicodeEncodeError:
        click.echo(json.dumps(payload, ensure_ascii=True, indent=indent))


__all__ = ["echo_json"]

