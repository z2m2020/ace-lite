from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ace_lite.temporal_filter import resolve_temporal_filter


def test_resolve_temporal_filter_disabled_when_no_inputs() -> None:
    temporal = resolve_temporal_filter(
        time_range=None, start_date=None, end_date=None, timezone_mode="utc"
    )
    assert temporal.enabled is False
    assert temporal.reason == "disabled"
    assert temporal.start_ts is None
    assert temporal.end_ts is None


def test_resolve_temporal_filter_parses_time_range_relative_to_now() -> None:
    now = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    temporal = resolve_temporal_filter(
        time_range="7d",
        start_date=None,
        end_date=None,
        timezone_mode="utc",
        now=now,
    )
    assert temporal.enabled is True
    assert temporal.reason == "ok"
    assert temporal.start_ts == pytest.approx(
        datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    )
    assert temporal.end_ts == pytest.approx(now.timestamp())


def test_resolve_temporal_filter_parses_date_only_bounds() -> None:
    temporal = resolve_temporal_filter(
        time_range=None,
        start_date="2026-02-10",
        end_date="2026-02-12",
        timezone_mode="utc",
        now=datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc),
    )
    assert temporal.enabled is True
    assert temporal.reason == "ok"
    assert temporal.start_iso.startswith("2026-02-10T00:00:00")
    assert temporal.end_iso.startswith("2026-02-12T23:59:59.999999")


def test_resolve_temporal_filter_rejects_mixed_range_and_dates() -> None:
    with pytest.raises(ValueError, match="time_range cannot be combined"):
        resolve_temporal_filter(
            time_range="24h",
            start_date="2026-02-10",
            end_date=None,
            timezone_mode="utc",
        )


def test_resolve_temporal_filter_requires_offset_in_explicit_mode() -> None:
    with pytest.raises(ValueError, match="timezone offset required"):
        resolve_temporal_filter(
            time_range=None,
            start_date="2026-02-10T00:00:00",
            end_date=None,
            timezone_mode="explicit",
        )

