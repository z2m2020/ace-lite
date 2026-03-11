from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ace_lite.pipeline.stages.memory import run_memory


class DummyMemoryProvider:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.last_channel_used = "dummy"
        self.strategy = "semantic"
        self.fallback_reason = None
        self.last_cache_stats = {"enabled": False}
        self.last_hybrid_stats = {}
        self.last_notes_stats = {}
        self.last_container_tag_fallback = None

    def search_compact(
        self, query: str, *, limit: int | None = None, container_tag: str | None = None
    ) -> list[dict[str, Any]]:
        return list(self._rows)

    def fetch(self, handles: list[str]) -> list[dict[str, Any]]:
        return []


def test_memory_stage_filters_hits_by_time_range() -> None:
    now = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    provider = DummyMemoryProvider(
        [
            {
                "handle": "a",
                "preview": "recent note",
                "score": 1.0,
                "metadata": {"created_at": "2026-02-14T23:00:00+00:00"},
            },
            {
                "handle": "b",
                "preview": "old note",
                "score": 1.0,
                "metadata": {"created_at": "2026-02-13T00:00:00+00:00"},
            },
            {
                "handle": "c",
                "preview": "unknown note",
                "score": 1.0,
                "metadata": {},
            },
        ]
    )

    payload = run_memory(
        memory_provider=provider,
        query="q",
        time_range="24h",
        temporal_enabled=True,
        timezone_mode="utc",
        now=now,
    )

    assert payload["count"] == 2
    assert [hit["handle"] for hit in payload["hits_preview"]] == ["a", "c"]
    temporal = payload["temporal"]
    assert temporal["requested"] is True
    assert temporal["reason"] == "ok"
    assert temporal["filtered_out_count"] == 1
    assert temporal["unknown_timestamp_count"] == 1


def test_memory_stage_applies_recency_boost_and_reranks() -> None:
    now = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    provider = DummyMemoryProvider(
        [
            {
                "handle": "old",
                "preview": "validate token legacy_validator",
                "score": 1.0,
                "metadata": {"captured_at": "2026-01-01T00:00:00+00:00"},
            },
            {
                "handle": "new",
                "preview": "validate modern_validator token",
                "score": 1.0,
                "metadata": {"captured_at": "2026-02-14T00:00:00+00:00"},
            },
        ]
    )

    payload = run_memory(
        memory_provider=provider,
        query="validate token",
        temporal_enabled=True,
        recency_boost_enabled=True,
        recency_boost_max=0.2,
        timezone_mode="utc",
        now=now,
    )

    hits = payload["hits_preview"]
    assert [hit["handle"] for hit in hits] == ["new", "old"]
    assert float(hits[0]["score"]) > float(hits[1]["score"])
    assert hits[0]["score_breakdown"]["recency_boost"] == 0.2
    assert hits[1]["score_breakdown"]["recency_boost"] == 0.0
    recency = payload["temporal"]["recency_boost"]
    assert recency["enabled_effective"] is True
    assert recency["applied_count"] == 1


def test_memory_stage_ignores_temporal_inputs_when_disabled() -> None:
    now = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    provider = DummyMemoryProvider(
        [
            {
                "handle": "a",
                "preview": "note",
                "score": 1.0,
                "metadata": {"created_at": "2026-01-01T00:00:00+00:00"},
            }
        ]
    )

    payload = run_memory(
        memory_provider=provider,
        query="q",
        time_range="24h",
        temporal_enabled=False,
        timezone_mode="utc",
        now=now,
    )

    assert payload["count"] == 1
    temporal = payload["temporal"]
    assert temporal["requested"] is True
    assert temporal["reason"] == "disabled_by_config"
    assert temporal["filtered_out_count"] == 0


def test_memory_stage_gate_skips_provider_calls() -> None:
    class ExplodingProvider(DummyMemoryProvider):
        def search_compact(self, query, *, limit=None, container_tag=None):  # type: ignore[override]
            raise AssertionError("provider should not be called when gated")

    provider = ExplodingProvider(
        [
            {
                "handle": "a",
                "preview": "should never be read",
                "score": 1.0,
                "metadata": {},
            }
        ]
    )

    payload = run_memory(
        memory_provider=provider,
        query="hello",
        gate_enabled=True,
        gate_mode="auto",
        temporal_enabled=False,
        timeline_enabled=False,
    )

    assert payload["count"] == 0
    assert payload["gate"]["skipped"] is True
