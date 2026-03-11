from __future__ import annotations

from datetime import datetime, timezone

from ace_lite.memory.postprocess import PostprocessConfig, postprocess_hits_preview


def test_postprocess_noise_filter_drops_boilerplate() -> None:
    hits = [
        {"handle": "a", "preview": "As an AI language model, I can't do that.", "score": 1.0, "metadata": {}},
        {"handle": "b", "preview": "We decided to use repo:auto tags.", "score": 1.0, "metadata": {}},
    ]
    out, telemetry = postprocess_hits_preview(
        hits,
        config=PostprocessConfig(enabled=True, noise_filter_enabled=True, length_norm_anchor_chars=0),
    )
    assert [h["handle"] for h in out] == ["b"]
    assert telemetry["noise_filter"]["dropped"] == 1


def test_postprocess_length_norm_penalizes_long_hits() -> None:
    hits = [
        {"handle": "short", "preview": "short note", "score": 1.0, "metadata": {}},
        {"handle": "long", "preview": ("x" * 2000), "score": 1.0, "metadata": {}},
    ]
    out, telemetry = postprocess_hits_preview(
        hits,
        config=PostprocessConfig(enabled=True, noise_filter_enabled=False, length_norm_anchor_chars=200, diversity_enabled=False),
    )
    assert telemetry["length_norm"]["enabled_effective"] is True
    assert out[0]["handle"] == "short"
    assert float(out[0]["score"]) > float(out[1]["score"])


def test_postprocess_time_decay_penalizes_old_hits() -> None:
    now = datetime(2026, 2, 25, 0, 0, 0, tzinfo=timezone.utc)
    hits = [
        {"handle": "new", "preview": "new note", "score": 1.0, "metadata": {"captured_at": "2026-02-24T00:00:00+00:00"}},
        {"handle": "old", "preview": "old note", "score": 1.0, "metadata": {"captured_at": "2025-02-01T00:00:00+00:00"}},
    ]
    out, telemetry = postprocess_hits_preview(
        hits,
        config=PostprocessConfig(enabled=True, noise_filter_enabled=False, length_norm_anchor_chars=0, time_decay_half_life_days=60, diversity_enabled=False),
        now=now,
    )
    assert telemetry["time_decay"]["enabled_effective"] is True
    assert out[0]["handle"] == "new"
    assert float(out[0]["score"]) > float(out[1]["score"])


def test_postprocess_diversity_drops_near_duplicates() -> None:
    hits = [
        {"handle": "a", "preview": "we decided to use repo tags", "score": 1.0, "metadata": {}},
        {"handle": "b", "preview": "we decided to use repo tags!", "score": 0.99, "metadata": {}},
        {"handle": "c", "preview": "unrelated memory about embeddings", "score": 0.5, "metadata": {}},
    ]
    out, telemetry = postprocess_hits_preview(
        hits,
        config=PostprocessConfig(enabled=True, noise_filter_enabled=False, length_norm_anchor_chars=0, diversity_enabled=True, diversity_similarity_threshold=0.9),
    )
    assert telemetry["diversity"]["dropped"] == 1
    assert [h["handle"] for h in out] == ["a", "c"]

