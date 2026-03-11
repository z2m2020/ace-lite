from __future__ import annotations

import re

_TOKEN_SPLIT_RE = re.compile(r"[^a-zA-Z0-9_]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+")


def code_tokens(
    text: str,
    *,
    min_len: int = 2,
    max_tokens: int = 64,
) -> list[str]:
    """Return a stable, code-aware list of lowercase tokens.

    Examples:
    - "getUserById" -> ["getuserbyid", "get", "user", "by", "id"]
    - "get_user_by_id" -> ["get_user_by_id", "get", "user", "by", "id"]
    - "internal/app/api" -> ["internal", "app", "api"]
    """
    normalized = str(text or "").strip()
    if not normalized:
        return []

    threshold = max(1, int(min_len))
    limit = max(1, int(max_tokens))

    parts = [part for part in _TOKEN_SPLIT_RE.split(normalized) if part]
    tokens: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        candidate = str(value or "").strip().lower()
        if not candidate or len(candidate) < threshold:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        tokens.append(candidate)

    for part in parts:
        add(part)
        for frag in _CAMEL_RE.findall(part):
            add(frag)
        if len(tokens) >= limit:
            break

    return tokens[:limit]


def code_token_set(
    text: str,
    *,
    min_len: int = 2,
    max_tokens: int = 64,
) -> set[str]:
    return set(code_tokens(text, min_len=min_len, max_tokens=max_tokens))


__all__ = ["code_tokens", "code_token_set"]

