"""Canonical payload core helpers for orchestrator factory payload builders."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def resolve_grouped_value(
    *,
    current: Any,
    default: Any,
    specs: tuple[tuple[dict[str, Any], tuple[tuple[str, ...], ...]], ...],
) -> Any:
    if current != default:
        return current
    for payload, paths in specs:
        if not payload:
            continue
        for path in paths:
            candidate: Any = payload
            missing = False
            for key in path:
                if not isinstance(candidate, Mapping) or key not in candidate:
                    missing = True
                    break
                candidate = candidate[key]
            if not missing:
                return candidate
    return current


@dataclass(frozen=True)
class CanonicalFieldSpec:
    output_path: tuple[str, ...]
    current: Any
    default: Any
    group_specs: tuple[tuple[dict[str, Any], tuple[tuple[str, ...], ...]], ...]


def set_nested_mapping_value(
    target: dict[str, Any],
    path: tuple[str, ...],
    value: Any,
) -> None:
    node = target
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = value


def build_canonical_payload(
    *,
    field_specs: tuple[CanonicalFieldSpec, ...],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for spec in field_specs:
        value = resolve_grouped_value(
            current=spec.current,
            default=spec.default,
            specs=spec.group_specs,
        )
        set_nested_mapping_value(payload, spec.output_path, value)
    return payload


__all__ = [
    "CanonicalFieldSpec",
    "build_canonical_payload",
    "resolve_grouped_value",
    "set_nested_mapping_value",
]
