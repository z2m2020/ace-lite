from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MEMORY_SEARCH_DISCLAIMER = (
    "以下结果是历史线索, 不代表当前仓库事实, 请回到文件与提交记录进行核证。"
)
RECENCY_ALERT_TERMS: tuple[str, ...] = (
    "latest",
    "update",
    "sync",
    "recent",
    "newest",
    "最近",
    "最新",
    "同步",
    "更新",
)
STALE_THRESHOLD_DAYS = 30.0


def _normalize_iso8601(value: Any) -> datetime | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_row_timestamp(row: dict[str, Any]) -> datetime | None:
    for field in ("captured_at", "created_at", "updated_at"):
        parsed = _normalize_iso8601(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _iso_or_empty(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def build_memory_search_guardrails(
    *,
    query: str,
    items: list[dict[str, Any]],
    namespace: str | None = None,
    namespace_note_count: int | None = None,
) -> dict[str, Any]:
    lowered_query = str(query or "").lower()
    matched_terms = sorted({term for term in RECENCY_ALERT_TERMS if term in lowered_query})
    recency_requested = bool(matched_terms)
    now = datetime.now(timezone.utc)

    timestamps = [ts for ts in (_extract_row_timestamp(row) for row in items) if ts is not None]
    newest_item_at = max(timestamps) if timestamps else None
    oldest_item_at = min(timestamps) if timestamps else None
    stale_item_count = sum(
        1
        for ts in timestamps
        if (now - ts).total_seconds() / 86400.0 > STALE_THRESHOLD_DAYS
    )

    staleness_warning: dict[str, Any] | None = None
    if stale_item_count > 0:
        staleness_warning = {
            "triggered": True,
            "stale_item_count": int(stale_item_count),
            "threshold_days": int(STALE_THRESHOLD_DAYS),
            "newest_item_at": _iso_or_empty(newest_item_at),
            "oldest_item_at": _iso_or_empty(oldest_item_at),
            "message": "部分记忆条目时间较旧, 请优先以当前文件和提交记录为准。",
        }

    recency_alert: dict[str, Any] | None = None
    if recency_requested:
        if stale_item_count > 0:
            message = "query 包含最新/同步语义, 且命中结果包含旧条目, 请先核对最新仓库事实。"
        elif not items:
            message = "query 包含最新/同步语义, 但未命中记忆条目, 请直接检查仓库当前文件和提交。"
        else:
            message = "query 包含最新/同步语义, 请将记忆结果视为线索并进行事实核证。"
        recency_alert = {
            "triggered": True,
            "matched_terms": matched_terms,
            "threshold_days": int(STALE_THRESHOLD_DAYS),
            "stale_item_count": int(stale_item_count),
            "newest_item_at": _iso_or_empty(newest_item_at),
            "oldest_item_at": _iso_or_empty(oldest_item_at),
            "message": message,
        }

    cold_start = bool(
        str(namespace or "").strip()
        and int(namespace_note_count or 0) <= 0
        and not items
    )

    return {
        "disclaimer": MEMORY_SEARCH_DISCLAIMER,
        "staleness_warning": staleness_warning,
        "recency_alert": recency_alert,
        "cold_start": cold_start,
        "recommended_next_step": "ace_plan_quick" if cold_start else None,
    }


__all__ = ["build_memory_search_guardrails"]
