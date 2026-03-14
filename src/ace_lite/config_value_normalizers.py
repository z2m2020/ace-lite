from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ace_lite.utils import normalize_lower_str


def validate_choice_value(
    value: str | None,
    *,
    field_name: str,
    choices: Sequence[str],
) -> str | None:
    if value is None:
        return value
    normalized = str(value).strip().lower()
    if normalized not in choices:
        choice_text = ", ".join(choices)
        raise ValueError(
            f"Unsupported {field_name}: {normalized}. Expected one of: {choice_text}"
        )
    return normalized


def normalize_choice_value(
    value: Any,
    *,
    choices: Sequence[str],
    default: str,
) -> str:
    normalized_default = str(default).strip().lower() or str(default)
    normalized = (
        normalize_lower_str(value, default=normalized_default) or normalized_default
    )
    if normalized not in choices:
        return normalized_default
    return normalized


def normalize_optional_choice_value(
    value: Any,
    *,
    choices: Sequence[str],
) -> str | None:
    normalized = normalize_lower_str(value, default="")
    if not normalized:
        return None
    if normalized not in choices:
        return None
    return normalized


__all__ = [
    "normalize_choice_value",
    "normalize_optional_choice_value",
    "validate_choice_value",
]
