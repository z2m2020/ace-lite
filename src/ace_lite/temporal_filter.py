"""Temporal filter parsing utilities (UTC-normalized, deterministic).

The temporal filter is intended to be an optional query-time constraint used by
memory/retrieval stages. It must be explicit and observable (no silent tz drops).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

TimezoneMode = Literal["utc", "local", "explicit"]


_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DURATION_RE = re.compile(r"^(\d+)([hdw])$")
_NATURAL_RANGE_RE = re.compile(r"^(?:last|past)\s+(\d+)\s*(hours?|days?|weeks?)$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _local_tz() -> timezone:
    tzinfo = datetime.now().astimezone().tzinfo
    if tzinfo is None:
        return timezone.utc
    return tzinfo  # type: ignore[return-value]


def _resolve_tzinfo(*, timezone_mode: TimezoneMode) -> timezone:
    if timezone_mode == "utc":
        return timezone.utc
    if timezone_mode == "local":
        return _local_tz()
    raise ValueError("timezone_mode=explicit requires timezone offsets on datetime inputs")


def _parse_iso_datetime(
    value: str,
    *,
    timezone_mode: TimezoneMode,
    is_end: bool,
) -> tuple[datetime, str | None]:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty datetime")

    warning: str | None = None
    if _DATE_ONLY_RE.match(text):
        day = date.fromisoformat(text)
        if is_end:
            naive = datetime(day.year, day.month, day.day, 23, 59, 59, 999999)
        else:
            naive = datetime(day.year, day.month, day.day, 0, 0, 0, 0)

        if timezone_mode == "explicit":
            warning = "date_only_assumed_utc"
            tzinfo = timezone.utc
        else:
            tzinfo = _resolve_tzinfo(timezone_mode=timezone_mode)
        return naive.replace(tzinfo=tzinfo).astimezone(timezone.utc), warning

    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid datetime: {text}") from exc

    if dt.tzinfo is None:
        if timezone_mode == "explicit":
            raise ValueError("timezone offset required (timezone_mode=explicit)")
        dt = dt.replace(tzinfo=_resolve_tzinfo(timezone_mode=timezone_mode))

    return dt.astimezone(timezone.utc), warning


def _parse_time_range(value: str) -> timedelta:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("time_range cannot be empty")

    aliases = {
        "last_week": "7d",
        "past_week": "7d",
        "last_day": "24h",
        "past_day": "24h",
    }
    if text in aliases:
        text = aliases[text]

    m = _DURATION_RE.match(text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if amount <= 0:
            raise ValueError("time_range must be positive")
        if unit == "h":
            return timedelta(hours=amount)
        if unit == "d":
            return timedelta(days=amount)
        if unit == "w":
            return timedelta(weeks=amount)
        raise ValueError(f"unsupported time_range unit: {unit}")

    m = _NATURAL_RANGE_RE.match(text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if amount <= 0:
            raise ValueError("time_range must be positive")
        if unit.startswith("hour"):
            return timedelta(hours=amount)
        if unit.startswith("day"):
            return timedelta(days=amount)
        if unit.startswith("week"):
            return timedelta(weeks=amount)

    raise ValueError(f"unsupported time_range: {value}")


@dataclass(frozen=True, slots=True)
class TemporalFilter:
    enabled: bool
    start_ts: float | None
    end_ts: float | None
    start_iso: str | None
    end_iso: str | None
    timezone_mode: TimezoneMode
    input_time_range: str | None
    input_start_date: str | None
    input_end_date: str | None
    reason: str
    warning: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "reason": str(self.reason),
            "timezone_mode": str(self.timezone_mode),
            "warning": self.warning,
            "input": {
                "time_range": self.input_time_range,
                "start_date": self.input_start_date,
                "end_date": self.input_end_date,
            },
            "resolved": {
                "start_iso": self.start_iso,
                "end_iso": self.end_iso,
                "start_ts": self.start_ts,
                "end_ts": self.end_ts,
            },
        }


def resolve_temporal_filter(
    *,
    time_range: str | None,
    start_date: str | None,
    end_date: str | None,
    timezone_mode: str = "utc",
    now: datetime | None = None,
) -> TemporalFilter:
    normalized_time_range = _normalize_text(time_range)
    normalized_start = _normalize_text(start_date)
    normalized_end = _normalize_text(end_date)

    if not normalized_time_range and not normalized_start and not normalized_end:
        return TemporalFilter(
            enabled=False,
            start_ts=None,
            end_ts=None,
            start_iso=None,
            end_iso=None,
            timezone_mode="utc",
            input_time_range=None,
            input_start_date=None,
            input_end_date=None,
            reason="disabled",
        )

    mode = str(timezone_mode or "utc").strip().lower() or "utc"
    if mode not in {"utc", "local", "explicit"}:
        raise ValueError(f"unsupported timezone_mode: {mode}")

    tz_mode: TimezoneMode = mode  # type: ignore[assignment]
    warning: str | None = None

    if normalized_time_range and (normalized_start or normalized_end):
        raise ValueError("time_range cannot be combined with start_date/end_date")

    effective_now = now.astimezone(timezone.utc) if now is not None else _utc_now()

    start_dt: datetime | None = None
    end_dt: datetime | None = None

    if normalized_time_range:
        delta = _parse_time_range(normalized_time_range)
        end_dt = effective_now
        start_dt = effective_now - delta
    else:
        if normalized_start:
            start_dt, warning = _parse_iso_datetime(
                normalized_start, timezone_mode=tz_mode, is_end=False
            )
        if normalized_end:
            end_dt_candidate, end_warning = _parse_iso_datetime(
                normalized_end, timezone_mode=tz_mode, is_end=True
            )
            end_dt = end_dt_candidate
            if warning is None:
                warning = end_warning
            elif end_warning and warning != end_warning:
                warning = f"{warning};{end_warning}"

    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        raise ValueError("start_date must be <= end_date")

    start_ts = start_dt.timestamp() if start_dt is not None else None
    end_ts = end_dt.timestamp() if end_dt is not None else None
    start_iso = start_dt.isoformat() if start_dt is not None else None
    end_iso = end_dt.isoformat() if end_dt is not None else None

    return TemporalFilter(
        enabled=True,
        start_ts=start_ts,
        end_ts=end_ts,
        start_iso=start_iso,
        end_iso=end_iso,
        timezone_mode=tz_mode,
        input_time_range=normalized_time_range,
        input_start_date=normalized_start,
        input_end_date=normalized_end,
        reason="ok",
        warning=warning,
    )


__all__ = ["TemporalFilter", "TimezoneMode", "resolve_temporal_filter"]
