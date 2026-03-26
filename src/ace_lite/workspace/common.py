from __future__ import annotations

import re
from typing import Any

_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
_CAMEL_BOUNDARY_PATTERN = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def ensure_non_empty_str(*, value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{context} cannot be empty")
    return normalized


def tokenize(value: Any) -> tuple[str, ...]:
    raw_text = _CAMEL_BOUNDARY_PATTERN.sub(" ", str(value or ""))
    tokens: set[str] = set()
    for match in _TOKEN_PATTERN.finditer(raw_text.lower()):
        token = match.group(0)
        if not token:
            continue
        tokens.add(token)
        if "_" in token:
            for part in token.split("_"):
                part = part.strip()
                if part:
                    tokens.add(part)
    return tuple(sorted(tokens))


__all__ = ["ensure_non_empty_str", "tokenize"]
