"""Shared option group registry primitives for CLI option catalogs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import click

OptionDescriptor = tuple[tuple[str, ...], dict[str, Any]]


@dataclass(frozen=True)
class OptionGroupDescriptor:
    name: str
    option_descriptors: tuple[OptionDescriptor, ...]


def build_option_decorators(
    descriptors: tuple[OptionDescriptor, ...],
) -> tuple[Callable[[Callable[..., Any]], Callable[..., Any]], ...]:
    return tuple(
        click.option(*option_names, **option_kwargs)
        for option_names, option_kwargs in descriptors
    )


__all__ = [
    "OptionDescriptor",
    "OptionGroupDescriptor",
    "build_option_decorators",
]
