from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

T = TypeVar("T")


def get_optional(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Get an optional value from a dict with a default.

    This is a safe accessor that won't raise KeyError.
    """
    return data.get(key, default)


def get_required(data: dict[str, Any], key: str, context: str = "") -> Any:
    """Get a required value from a dict."""
    if key not in data:
        raise KeyError(
            f"Required key '{key}' not found in payload" + (f" ({context})" if context else "")
        )
    return data[key]


def get_typed(
    data: Mapping[str, Any],
    key: str,
    expected_type: type[Any] | tuple[type[Any], ...],
    default: T,
) -> T:
    """Get a value with type checking."""
    value = data.get(key, default)
    if isinstance(value, expected_type):
        return cast(T, value)
    return default


def get_str(data: dict[str, Any], key: str, default: str = "") -> str:
    """Get a string value with default."""
    return get_typed(data, key, str, default)


def get_int(data: dict[str, Any], key: str, default: int = 0) -> int:
    """Get an integer value with default."""
    value = data.get(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def get_float(data: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Get a float value with default."""
    value = data.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def get_bool(data: dict[str, Any], key: str, default: bool = False) -> bool:
    """Get a boolean value with default."""
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return default


def get_optional_str(
    data: Mapping[str, Any],
    key: str,
    default: str | None = None,
) -> str | None:
    """Get an optional string value."""
    value = data.get(key, default)
    if isinstance(value, str):
        return value
    return default


def get_optional_dict(
    data: Mapping[str, Any],
    key: str,
) -> dict[str, Any] | None:
    """Get an optional mapping value."""
    value = data.get(key)
    if isinstance(value, Mapping):
        return {str(child_key): child_value for child_key, child_value in value.items()}
    return None


def get_list(
    data: Mapping[str, Any],
    key: str,
    default: list[Any] | None = None,
) -> list[Any]:
    """Get a list value with default."""
    if default is None:
        default = []
    return get_typed(data, key, list, default)


def get_dict(
    data: Mapping[str, Any],
    key: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get a dict value with default."""
    if default is None:
        default = {}
    value = data.get(key, default)
    if isinstance(value, Mapping):
        return {str(child_key): child_value for child_key, child_value in value.items()}
    return default


def coerce_mapping(data: Any) -> dict[str, Any]:
    """Project arbitrary input into a plain dict mapping."""
    if isinstance(data, Mapping):
        return {str(key): value for key, value in data.items()}
    return {}


def coerce_mapping_list(data: Any) -> list[dict[str, Any]]:
    """Project arbitrary input into a list of plain dict mappings."""
    if not isinstance(data, list):
        return []
    return [coerce_mapping(item) for item in data if isinstance(item, Mapping)]


__all__ = [
    "coerce_mapping",
    "coerce_mapping_list",
    "get_bool",
    "get_dict",
    "get_float",
    "get_int",
    "get_list",
    "get_optional",
    "get_optional_dict",
    "get_optional_str",
    "get_required",
    "get_str",
    "get_typed",
]
