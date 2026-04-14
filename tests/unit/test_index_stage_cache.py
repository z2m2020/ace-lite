from __future__ import annotations

import json
from pathlib import Path

import ace_lite.index_stage.cache as index_stage_cache
from ace_lite.index_stage.cache import (
    load_cached_index_candidates_checked,
    store_cached_index_candidates,
)


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


def test_load_cached_index_candidates_checked_returns_isolated_legacy_payload(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": index_stage_cache._SCHEMA_VERSION,
                "entries": [
                    {
                        "key": "k1",
                        "updated_at_epoch": 100.0,
                        "payload": {
                            "candidate_files": [{"path": "src/app.py", "score": 1.0}],
                            "metadata": {"timings_ms": {"cache": 1.0}},
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    first = load_cached_index_candidates_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=0,
        required_meta=None,
    )
    assert first is not None
    first["candidate_files"][0]["score"] = 9.0
    first["metadata"]["timings_ms"]["cache"] = 99.0

    second = load_cached_index_candidates_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=0,
        required_meta=None,
    )
    assert second is not None
    assert second["candidate_files"][0]["score"] == 1.0
    assert second["metadata"]["timings_ms"]["cache"] == 1.0


def test_store_cached_index_candidates_keeps_artifact_memory_payload_isolated(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.json"
    payload = {
        "candidate_files": [{"path": "src/app.py", "score": 1.0}],
        "metadata": {"timings_ms": {"cache": 1.0}},
    }

    stored = store_cached_index_candidates(
        cache_path=cache_path,
        key="k1",
        payload=payload,
        meta={"query": "router"},
    )

    assert stored is True

    first = load_cached_index_candidates_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=0,
        required_meta={"query": "router"},
    )
    assert first is not None
    first["candidate_files"][0]["score"] = 7.0
    first["metadata"]["timings_ms"]["cache"] = 77.0

    second = load_cached_index_candidates_checked(
        cache_path=cache_path,
        key="k1",
        max_age_seconds=0,
        required_meta={"query": "router"},
    )
    assert second is not None
    assert second["candidate_files"][0]["score"] == 1.0
    assert second["metadata"]["timings_ms"]["cache"] == 1.0


def test_load_cache_payload_reuses_manifest_memory_until_file_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": index_stage_cache._SCHEMA_VERSION,
                "entries": [{"key": "k1", "updated_at_epoch": 100.0}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest_memory = getattr(index_stage_cache, "_INDEX_CANDIDATE_CACHE_MEMORY", None)
    if isinstance(manifest_memory, dict):
        manifest_memory.clear()

    original_read_text = Path.read_text
    calls = {"count": 0}

    def _tracked_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.resolve() == cache_path.resolve():
            calls["count"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _tracked_read_text)

    first = index_stage_cache._load_cache_payload(
        cache_path=cache_path,
        schema_version=index_stage_cache._SCHEMA_VERSION,
    )
    second = index_stage_cache._load_cache_payload(
        cache_path=cache_path,
        schema_version=index_stage_cache._SCHEMA_VERSION,
    )

    assert first is not None
    assert second is not None
    assert calls["count"] == 1

    cache_path.write_text(
        json.dumps(
            {
                "schema_version": index_stage_cache._SCHEMA_VERSION,
                "entries": [{"key": "k2", "updated_at_epoch": 200.0}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    third = index_stage_cache._load_cache_payload(
        cache_path=cache_path,
        schema_version=index_stage_cache._SCHEMA_VERSION,
    )

    assert third is not None
    assert third["entries"][0]["key"] == "k2"
    assert calls["count"] == 2


def test_write_cache_payload_primes_manifest_memory_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_path = tmp_path / "cache.json"
    payload = {
        "schema_version": index_stage_cache._SCHEMA_VERSION,
        "entries": [{"key": "k1", "updated_at_epoch": 100.0}],
    }

    manifest_memory = getattr(index_stage_cache, "_INDEX_CANDIDATE_CACHE_MEMORY", None)
    if isinstance(manifest_memory, dict):
        manifest_memory.clear()

    index_stage_cache._write_cache_payload(cache_path=cache_path, payload=payload)

    original_read_text = Path.read_text
    calls = {"count": 0}

    def _tracked_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.resolve() == cache_path.resolve():
            calls["count"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _tracked_read_text)

    loaded = index_stage_cache._load_cache_payload(
        cache_path=cache_path,
        schema_version=index_stage_cache._SCHEMA_VERSION,
    )

    assert loaded is not None
    assert loaded["entries"][0]["key"] == "k1"
    assert calls["count"] == 0
