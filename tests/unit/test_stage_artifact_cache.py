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


def test_stage_artifact_cache_hot_tier_enforces_max_entries(tmp_path: Path) -> None:
    cache = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=2,
        hot_max_tokens=100,
    )

    cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fp-a",
        payload={"value": "a"},
        token_weight=10,
    )
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="bbbbbbbbbbbbbbbb",
        query_hash="1111222233334444",
        fingerprint="fp-b",
        payload={"value": "b"},
        token_weight=10,
    )
    cache.get_artifact(stage_name="source_plan", cache_key="aaaaaaaaaaaaaaaa")
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="cccccccccccccccc",
        query_hash="1111222233334444",
        fingerprint="fp-c",
        payload={"value": "c"},
        token_weight=10,
    )

    snapshot = cache.hot_tier_snapshot()

    assert snapshot["entry_count"] == 2
    assert snapshot["token_total"] == 20
    assert [item["cache_key"] for item in snapshot["entries"]] == [
        "aaaaaaaaaaaaaaaa",
        "cccccccccccccccc",
    ]


def test_stage_artifact_cache_hot_tier_enforces_max_tokens(tmp_path: Path) -> None:
    cache = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=8,
        hot_max_tokens=7,
    )

    cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fp-a",
        payload={"value": "a"},
        token_weight=4,
    )
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="bbbbbbbbbbbbbbbb",
        query_hash="1111222233334444",
        fingerprint="fp-b",
        payload={"value": "b"},
        token_weight=4,
    )
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="cccccccccccccccc",
        query_hash="1111222233334444",
        fingerprint="fp-c",
        payload={"value": "c"},
        token_weight=3,
    )

    snapshot = cache.hot_tier_snapshot()

    assert snapshot["entry_count"] == 2
    assert snapshot["token_total"] == 7
    assert [item["cache_key"] for item in snapshot["entries"]] == [
        "bbbbbbbbbbbbbbbb",
        "cccccccccccccccc",
    ]


def test_stage_artifact_cache_estimates_token_weight_when_missing(tmp_path: Path) -> None:
    cache = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=4,
        hot_max_tokens=100,
    )

    entry = cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fp-a",
        payload={"source_plan": {"steps": [{"id": 1, "stage": "index"}]}},
    )
    snapshot = cache.hot_tier_snapshot()

    assert entry.token_weight > 0
    assert snapshot["entry_count"] == 1
    assert snapshot["token_total"] == entry.token_weight


def test_stage_artifact_cache_hot_tier_isolates_payload_from_caller_mutation(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=4,
        hot_max_tokens=100,
    )
    payload = {
        "source_plan": {
            "steps": [{"id": 1, "stage": "index"}],
            "meta": {"owner": "seed"},
        }
    }

    cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fp-a",
        payload=payload,
        token_weight=4,
    )

    payload["source_plan"]["steps"][0]["id"] = 99
    payload["source_plan"]["meta"]["owner"] = "mutated"

    loaded = cache.get_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
    )

    assert loaded is not None
    assert loaded.payload["source_plan"]["steps"][0]["id"] == 1
    assert loaded.payload["source_plan"]["meta"]["owner"] == "seed"


def test_stage_artifact_cache_hot_tier_returns_nested_isolated_payload(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=4,
        hot_max_tokens=100,
    )
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fp-a",
        payload={"source_plan": {"steps": [{"id": 1, "stage": "index"}]}},
        token_weight=4,
    )

    first = cache.get_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
    )
    assert first is not None
    first.payload["source_plan"]["steps"][0]["id"] = 88

    second = cache.get_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
    )

    assert second is not None
    assert second.payload["source_plan"]["steps"][0]["id"] == 1
