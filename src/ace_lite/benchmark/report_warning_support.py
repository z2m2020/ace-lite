from __future__ import annotations

from typing import Any


def normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def join_string_list(raw: Any, *, empty: str = "(none)") -> str:
    rows = normalize_string_list(raw)
    return ", ".join(rows) if rows else empty


__all__ = ["join_string_list", "normalize_string_list"]
