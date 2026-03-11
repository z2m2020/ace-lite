from __future__ import annotations

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


def test_memory_stage_postprocess_disabled_is_noop() -> None:
    provider = DummyMemoryProvider(
        [
            {"handle": "a", "preview": "x" * 2000, "score": 1.0, "metadata": {}},
            {"handle": "b", "preview": "short", "score": 1.0, "metadata": {}},
        ]
    )
    payload = run_memory(
        memory_provider=provider,
        query="some long query that should retrieve",
        temporal_enabled=False,
        timeline_enabled=False,
        postprocess_enabled=False,
    )
    assert payload["postprocess"]["enabled"] is False
    assert [h["handle"] for h in payload["hits_preview"]] == ["a", "b"]


def test_memory_stage_postprocess_noise_filter_drops() -> None:
    provider = DummyMemoryProvider(
        [
            {"handle": "a", "preview": "As an AI language model, I can't do that.", "score": 1.0, "metadata": {}},
            {"handle": "b", "preview": "We decided to use repo tags", "score": 1.0, "metadata": {}},
        ]
    )
    payload = run_memory(
        memory_provider=provider,
        query="some long query that should retrieve",
        temporal_enabled=False,
        timeline_enabled=False,
        postprocess_enabled=True,
        postprocess_noise_filter_enabled=True,
        postprocess_length_norm_anchor_chars=0,
        postprocess_diversity_enabled=False,
    )
    assert payload["postprocess"]["enabled"] is True
    assert payload["postprocess"]["noise_filter"]["dropped"] == 1
    assert [h["handle"] for h in payload["hits_preview"]] == ["b"]

