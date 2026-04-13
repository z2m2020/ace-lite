from __future__ import annotations

import json
from pathlib import Path

import ace_lite.index_stage.cache as index_stage_cache
from ace_lite.index_stage.cache import store_cached_index_candidates


def test_store_cached_index_candidates_returns_false_on_oserror(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {"schema_version": index_stage_cache._SCHEMA_VERSION, "entries": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    class BrokenManager:
        def put_artifact(self, **kwargs):  # type: ignore[no-untyped-def]
            raise OSError("disk full")

    monkeypatch.setattr(
        index_stage_cache,
        "_build_stage_artifact_cache",
        lambda **kwargs: BrokenManager(),
    )

    stored = store_cached_index_candidates(
        cache_path=cache_path,
        key="k1",
        payload={"value": 1},
        meta={"query": "router"},
    )

    assert stored is False


def test_index_stage_cache_invalid_updated_at_epoch_is_expired() -> None:
    assert (
        index_stage_cache._is_entry_expired(
            entry={"updated_at_epoch": "not-a-number"},
            now_epoch=100.0,
            max_age_seconds=10,
        )
        is True
    )
