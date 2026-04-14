from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ace_lite.stage_artifact_cache import StageArtifactCache
from ace_lite.stage_artifact_cache_gc import (
    _validated_sqlite_identifier,
    run_bounded_stage_artifact_cache_gc,
    vacuum_stage_artifact_cache,
    verify_stage_artifact_cache,
)


def test_verify_stage_artifact_cache_detects_missing_orphan_and_expired_rows(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)

    stable = cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="stable-fingerprint",
        payload={"value": "stable"},
        ttl_seconds=3600,
        write_token="stable",
    )
    missing = cache.put_artifact(
        stage_name="source_plan",
        cache_key="bbbbbbbbbbbbbbbb",
        query_hash="1111222233334444",
        fingerprint="missing-fingerprint",
        payload={"value": "missing"},
        ttl_seconds=3600,
        write_token="missing",
    )
    expired = cache.put_artifact(
        stage_name="source_plan",
        cache_key="cccccccccccccccc",
        query_hash="1111222233334444",
        fingerprint="expired-fingerprint",
        payload={"value": "expired"},
        ttl_seconds=3600,
        write_token="expired",
    )

    stable_path = cache.payload_root / Path(*Path(stable.payload_relpath).parts)
    assert stable_path.exists()

    missing_path = cache.payload_root / Path(*Path(missing.payload_relpath).parts)
    missing_path.unlink()

    expired_row = replace(expired, expires_at="2000-01-01T00:00:00+00:00")
    cache.store.upsert_entry(expired_row)

    orphan_path = cache.payload_root / "source_plan" / "ff" / "ffffffffffffffff.json"
    orphan_path.parent.mkdir(parents=True, exist_ok=True)
    orphan_path.write_text('{"orphan": true}\n', encoding="utf-8")

    report = verify_stage_artifact_cache(repo_root=tmp_path)

    assert report["ok"] is False
    assert report["entry_count"] == 3
    assert report["payload_file_count"] == 3
    assert len(report["missing_payload_rows"]) == 1
    assert report["missing_payload_rows"][0]["cache_key"] == "bbbbbbbbbbbbbbbb"
    assert len(report["expired_rows"]) == 1
    assert report["expired_rows"][0]["cache_key"] == "cccccccccccccccc"
    assert len(report["orphan_payload_files"]) == 1
    assert report["orphan_payload_files"][0]["payload_relpath"] == (
        "source_plan/ff/ffffffffffffffff.json"
    )


def test_verify_stage_artifact_cache_flags_invalid_payload_and_temp_files(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    entry = cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fingerprint",
        payload={"value": "ok"},
        write_token="writer",
    )

    payload_path = cache.payload_root / Path(*Path(entry.payload_relpath).parts)
    payload_path.write_text("not json\n", encoding="utf-8")

    temp_path = cache.temp_root / "source_plan" / "aa" / "aaaaaaaaaaaaaaaa.writer.json.tmp"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text('{"temp": true}\n', encoding="utf-8")

    report = verify_stage_artifact_cache(repo_root=tmp_path)

    assert report["ok"] is False
    assert len(report["invalid_payload_rows"]) == 1
    assert report["invalid_payload_rows"][0]["cache_key"] == "aaaaaaaaaaaaaaaa"
    assert report["temp_payload_file_count"] == 1
    assert report["temp_payload_files"][0]["temp_relpath"] == (
        "source_plan/aa/aaaaaaaaaaaaaaaa.writer.json.tmp"
    )


def test_vacuum_stage_artifact_cache_apply_removes_expired_rows_and_orphans(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    expired = cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="expired",
        payload={"value": "expired"},
        ttl_seconds=3600,
        write_token="expired",
    )
    cache.store.upsert_entry(replace(expired, expires_at="2000-01-01T00:00:00+00:00"))

    orphan_path = cache.payload_root / "source_plan" / "ff" / "ffffffffffffffff.json"
    orphan_path.parent.mkdir(parents=True, exist_ok=True)
    orphan_path.write_text('{"orphan": true}\n', encoding="utf-8")

    dry_run = vacuum_stage_artifact_cache(repo_root=tmp_path, apply=False)
    assert dry_run["dry_run"] is True
    assert dry_run["expired_row_candidates"] == 1
    assert dry_run["orphan_payload_candidates"] == 1

    applied = vacuum_stage_artifact_cache(repo_root=tmp_path, apply=True)
    assert applied["ok"] is True
    assert applied["dry_run"] is False
    assert applied["deleted_expired_rows"] == 1
    assert applied["deleted_expired_payload_files"] == 1
    assert applied["deleted_orphan_payload_files"] == 1

    report = verify_stage_artifact_cache(repo_root=tmp_path)
    assert report["entry_count"] == 0
    assert report["orphan_payload_files"] == []


def test_run_bounded_stage_artifact_cache_gc_honors_inline_delete_budget(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    temp_a = cache.temp_root / "source_plan" / "aa" / "aaaaaaaaaaaaaaaa.writer.json.tmp"
    temp_b = cache.temp_root / "source_plan" / "bb" / "bbbbbbbbbbbbbbbb.writer.json.tmp"
    temp_a.parent.mkdir(parents=True, exist_ok=True)
    temp_b.parent.mkdir(parents=True, exist_ok=True)
    temp_a.write_text('{"temp": "a"}\n', encoding="utf-8")
    temp_b.write_text('{"temp": "b"}\n', encoding="utf-8")

    expired = cache.put_artifact(
        stage_name="source_plan",
        cache_key="cccccccccccccccc",
        query_hash="1111222233334444",
        fingerprint="expired",
        payload={"value": "expired"},
        ttl_seconds=3600,
        write_token="expired",
    )
    cache.store.upsert_entry(replace(expired, expires_at="2000-01-01T00:00:00+00:00"))

    result = run_bounded_stage_artifact_cache_gc(
        repo_root=tmp_path,
        budget_ms=1000.0,
        max_delete=2,
    )

    assert result["mode"] == "bounded_opportunistic"
    assert result["deleted_total"] == 2
    assert result["deleted_temp_payloads"] == 2
    assert cache.store.load_entry(stage_name="source_plan", cache_key="cccccccccccccccc") is not None


def test_validated_sqlite_identifier_rejects_invalid_stage_cache_table_name() -> None:
    with pytest.raises(ValueError, match="invalid_sqlite_identifier"):
        _validated_sqlite_identifier("stage-cache entries")
