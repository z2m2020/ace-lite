from __future__ import annotations

import json
import pathlib
from pathlib import Path
from time import time

import ace_lite.repomap.cache as repomap_cache
from ace_lite.repomap.cache import (
    load_cached_repomap_precompute_checked,
    store_cached_repomap_precompute,
)


def test_repomap_cache_payload_is_memoized_in_process(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "precompute_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": repomap_cache._PRECOMPUTE_SCHEMA_VERSION,
                "entries": [
                    {
                        "key": "k1",
                        "updated_at_epoch": round(float(time()), 3),
                        "meta": {},
                        "payload": {"value": 1},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    first = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=3600,
        required_meta=None,
    )
    assert first == {"value": 1}

    def _read_text_disabled(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read_text disabled")

    monkeypatch.setattr(pathlib.Path, "read_text", _read_text_disabled)

    second = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=3600,
        required_meta=None,
    )
    assert second == {"value": 1}

    cache_path.write_text(cache_path.read_bytes().decode("utf-8") + "\n", encoding="utf-8")
    invalidated = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=3600,
        required_meta=None,
    )
    assert invalidated is None


def test_repomap_cache_store_updates_memory_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "precompute_cache.json"
    cache_path.write_text(
        json.dumps(
            {"schema_version": repomap_cache._PRECOMPUTE_SCHEMA_VERSION, "entries": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    store_cached_repomap_precompute(
        cache_path=cache_path,
        key="k2",
        payload={"hello": "world"},
        meta={"policy_version": "v1"},
    )

    def _read_text_disabled(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read_text disabled")

    monkeypatch.setattr(pathlib.Path, "read_text", _read_text_disabled)

    loaded = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k2",
        max_age_seconds=3600,
        required_meta=None,
    )
    assert loaded == {"hello": "world"}
