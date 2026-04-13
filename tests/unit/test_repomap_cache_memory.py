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


def test_repomap_cache_store_isolated_from_input_mutation(tmp_path: Path) -> None:
    cache_path = tmp_path / "precompute_cache.json"
    cache_path.write_text(
        json.dumps(
            {"schema_version": repomap_cache._PRECOMPUTE_SCHEMA_VERSION, "entries": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    payload = {"nested": {"value": 1}}

    store_cached_repomap_precompute(
        cache_path=cache_path,
        key="k3",
        payload=payload,
        meta={"policy_version": "v1"},
    )
    payload["nested"]["value"] = 99

    loaded = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k3",
        max_age_seconds=3600,
        required_meta=None,
    )

    assert loaded == {"nested": {"value": 1}}


def test_repomap_cache_load_isolated_from_loaded_payload_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_path = tmp_path / "precompute_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": repomap_cache._PRECOMPUTE_SCHEMA_VERSION,
                "entries": [
                    {
                        "key": "k4",
                        "updated_at_epoch": round(float(time()), 3),
                        "meta": {},
                        "payload": {"nested": {"value": 1}},
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
        key="k4",
        max_age_seconds=3600,
        required_meta=None,
    )
    assert first == {"nested": {"value": 1}}
    first["nested"]["value"] = 99

    def _read_text_disabled(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read_text disabled")

    monkeypatch.setattr(pathlib.Path, "read_text", _read_text_disabled)

    second = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k4",
        max_age_seconds=3600,
        required_meta=None,
    )

    assert second == {"nested": {"value": 1}}


def test_repomap_cache_store_falls_back_on_oserror(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "precompute_cache.json"
    cache_path.write_text(
        json.dumps(
            {"schema_version": repomap_cache._PRECOMPUTE_SCHEMA_VERSION, "entries": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    class BrokenManager:
        def put_artifact(self, **kwargs):  # type: ignore[no-untyped-def]
            raise OSError("disk full")

    monkeypatch.setattr(
        repomap_cache,
        "_build_stage_artifact_cache",
        lambda **kwargs: BrokenManager(),
    )

    stored = store_cached_repomap_precompute(
        cache_path=cache_path,
        key="k5",
        payload={"value": 5},
        meta={"policy_version": "v1"},
    )

    assert stored is True

    loaded = load_cached_repomap_precompute_checked(
        cache_path=cache_path,
        key="k5",
        max_age_seconds=3600,
        required_meta=None,
    )
    assert loaded == {"value": 5}


def test_repomap_cache_invalid_updated_at_epoch_is_expired() -> None:
    assert (
        repomap_cache._is_entry_expired(
            entry={"updated_at_epoch": "not-a-number"},
            now_epoch=100.0,
            max_age_seconds=10,
        )
        is True
    )
