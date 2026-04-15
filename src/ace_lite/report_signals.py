"""Shared helpers for report-only source-plan signals.

These helpers centralize two responsibilities used across report-only
payload builders and consumers:

- normalize small string/path payloads in a schema-compatible way
- resolve nested ``source_plan`` report signals with top-level fallback
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_REPORT_SIGNAL_KEYS = (
    "history_hits",
    "validation_findings",
    "session_end_report",
    "handoff_payload",
)

__all__ = [
    "DEFAULT_REPORT_SIGNAL_KEYS",
    "append_unique_signal_text",
    "coerce_payload",
    "normalize_signal_path",
    "normalize_signal_paths",
    "normalize_signal_text",
    "normalize_signal_texts",
    "resolve_report_signal",
    "resolve_report_signals",
    "resolve_source_plan_payload",
]


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def normalize_signal_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_signal_path(value: Any) -> str:
    return normalize_signal_text(value).replace("\\", "/").lstrip("./")


def append_unique_signal_text(
    items: list[str],
    seen: set[str],
    value: Any,
    *,
    normalizer: Any = normalize_signal_text,
) -> None:
    normalized = normalizer(value)
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    items.append(normalized)


def normalize_signal_texts(values: Sequence[Any], *, limit: int | None = None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        append_unique_signal_text(items, seen, value)
        if limit is not None and len(items) >= limit:
            break
    return items


def normalize_signal_paths(values: Sequence[Any], *, limit: int | None = None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        append_unique_signal_text(
            items,
            seen,
            value,
            normalizer=normalize_signal_path,
        )
        if limit is not None and len(items) >= limit:
            break
    return items


def coerce_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    return _dict(payload)


def resolve_source_plan_payload(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    return _dict(payload.get("source_plan", {}))


def resolve_report_signal(
    plan_payload: Mapping[str, Any] | Any,
    key: str,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _dict(sp.get(key, {})) or _dict(payload.get(key, {}))


def resolve_report_signals(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
    keys: Sequence[str] = DEFAULT_REPORT_SIGNAL_KEYS,
) -> dict[str, dict[str, Any]]:
    return {
        key: resolve_report_signal(plan_payload, key, source_plan=source_plan)
        for key in keys
    }
