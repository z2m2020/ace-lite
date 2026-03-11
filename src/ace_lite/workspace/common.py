from __future__ import annotations

import re
from typing import Any

_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def ensure_non_empty_str(*, value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{context} cannot be empty")
    return normalized


def tokenize(value: Any) -> tuple[str, ...]:
    tokens = {match.group(0) for match in _TOKEN_PATTERN.finditer(str(value or "").lower())}
    return tuple(sorted(tokens))


__all__ = ["ensure_non_empty_str", "tokenize"]
