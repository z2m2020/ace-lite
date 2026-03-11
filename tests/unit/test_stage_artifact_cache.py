from __future__ import annotations

from pathlib import Path

from ace_lite.stage_artifact_cache import StageArtifactCache
from ace_lite.stage_artifact_cache_store import STAGE_ARTIFACT_CACHE_WRITE_ORDER


def test_stage_artifact_cache_put_and_get_round_trip(tmp_path: Path) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)

    entry = cache.put_artifact(
        stage_name="source_plan",
        cache_key="abcdef0123456789",
        query_hash="1111222233334444",
        fingerprint="fingerprint-1",
        settings_fingerprint="settings-1",
        payload={"source_plan": {"steps": [{"id": 1, "stage": "index"}]}},
        token_weight=42,
        ttl_seconds=3600,
        soft_ttl_seconds=600,
        content_version="v1",
        policy_name="source_plan",
        trust_class="exact",
        write_token="worker-1",
    )

    payload_path = cache.payload_root / Path(*Path(entry.payload_relpath).parts)
    assert payload_path.exists()
    assert entry.token_weight == 42
    assert entry.ttl_seconds == 3600

    loaded = cache.get_artifact(stage_name="source_plan", cache_key="abcdef0123456789")

    assert loaded is not None
    assert loaded.entry.payload_sha256 == entry.payload_sha256
    assert loaded.entry.settings_fingerprint == "settings-1"
    assert loaded.payload == {"source_plan": {"steps": [{"id": 1, "stage": "index"}]}}


def test_stage_artifact_cache_put_respects_write_order(tmp_path: Path) -> None:
    steps: list[str] = []
    cache = StageArtifactCache(repo_root=tmp_path, write_step_recorder=steps.append)

    cache.put_artifact(
        stage_name="source_plan",
        cache_key="abcdef0123456789",
        query_hash="1111222233334444",
        fingerprint="fingerprint-1",
        payload={"ok": True},
    )

    assert steps == list(STAGE_ARTIFACT_CACHE_WRITE_ORDER)


def test_stage_artifact_cache_keeps_existing_payload_immutable(tmp_path: Path) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    first = cache.put_artifact(
        stage_name="source_plan",
        cache_key="abcdef0123456789",
        query_hash="1111222233334444",
        fingerprint="fingerprint-1",
        payload={"version": 1},
        write_token="worker-1",
    )

    second = cache.put_artifact(
        stage_name="source_plan",
        cache_key="abcdef0123456789",
        query_hash="1111222233334444",
        fingerprint="fingerprint-2",
        payload={"version": 2},
        write_token="worker-2",
    )
    loaded = cache.get_artifact(stage_name="source_plan", cache_key="abcdef0123456789")

    assert second.payload_sha256 == first.payload_sha256
    assert loaded is not None
    assert loaded.payload == {"version": 1}
