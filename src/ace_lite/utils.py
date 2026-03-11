from __future__ import annotations

from typing import Any


def normalize_str(value: Any, *, default: str = "") -> str:
    normalized = str(value if value is not None else default).strip()
    return normalized or default


def normalize_lower_str(value: Any, *, default: str = "") -> str:
    normalized = str(value if value is not None else default).strip().lower()
    return normalized or default


def normalize_choice(value: Any, choices: tuple[str, ...], *, default: str) -> str:
    normalized = normalize_lower_str(value, default=default)
    return normalized if normalized in choices else default


def normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def to_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def to_lower_list(value: Any) -> list[str]:
    return [item.lower().strip() for item in to_string_list(value) if str(item).strip()]


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "normalize_choice",
    "normalize_lower_str",
    "normalize_optional_str",
    "normalize_str",
    "to_float",
    "to_int",
    "to_lower_list",
    "to_string_list",
]
