from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_MISSING = object()


@dataclass(frozen=True)
class _FieldSpec:
    output_path: tuple[str, ...]
    default: Any
    candidate_paths: tuple[tuple[str, ...], ...]


def _spec(output_path: tuple[str, ...], default: Any, *candidate_paths: tuple[str, ...]) -> _FieldSpec:
    return _FieldSpec(output_path=output_path, default=default, candidate_paths=tuple(candidate_paths))


def _deep_merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        normalized_key = str(key)
        if isinstance(value, Mapping) and isinstance(target.get(normalized_key), dict):
            _deep_merge(target[normalized_key], value)
        elif isinstance(value, Mapping):
            child: dict[str, Any] = {}
            _deep_merge(child, value)
            target[normalized_key] = child
        else:
            target[normalized_key] = value


def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    payload: dict[str, Any] = {}
    _deep_merge(payload, value)
    return payload


def _extract_path(payload: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _set_nested(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def _build_payload_and_provenance(
    *,
    specs: tuple[_FieldSpec, ...],
    layers: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for spec in specs:
        source = "default"
        value = spec.default
        for label, layer in layers:
            for candidate_path in spec.candidate_paths:
                candidate = _extract_path(layer, candidate_path)
                if candidate is _MISSING:
                    continue
                value = candidate
                source = label
                break
            if source != "default":
                break
        _set_nested(payload, spec.output_path, value)
        _set_nested(provenance, spec.output_path, source)
    return payload, provenance


__all__ = [
    "_MISSING",
    "_FieldSpec",
    "_build_payload_and_provenance",
    "_deep_merge",
    "_extract_path",
    "_normalize_mapping",
    "_set_nested",
    "_spec",
]
