from __future__ import annotations

from pathlib import Path

from ace_lite.stage_artifact_cache import StageArtifactCache


def test_stage_artifact_cache_hot_tier_soak_keeps_bounds_during_churn(
    tmp_path: Path,
) -> None:
    stable_key = "abcdef0000000000"
    cache = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=3,
        hot_max_tokens=9,
    )

    cache.put_artifact(
        stage_name="source_plan",
        cache_key=stable_key,
        query_hash="1111222233334444",
        fingerprint="stable-fingerprint",
        payload={"source_plan": {"steps": [{"id": 0, "stage": "source_plan"}]}},
        token_weight=3,
        write_token="seed",
    )

    for iteration in range(48):
        hit = cache.get_artifact(
            stage_name="source_plan",
            cache_key=stable_key,
        )
        assert hit is not None
        assert hit.payload["source_plan"]["steps"][0]["id"] == 0

        rotating_key = f"{iteration:016x}"
        cache.put_artifact(
            stage_name="source_plan",
            cache_key=rotating_key,
            query_hash=f"{iteration:016x}",
            fingerprint=f"rotating-{iteration}",
            payload={
                "source_plan": {
                    "steps": [{"id": iteration + 1, "stage": "source_plan"}]
                }
            },
            token_weight=3,
            write_token=f"writer-{iteration}",
        )

        snapshot = cache.hot_tier_snapshot()
        keys = [item["cache_key"] for item in snapshot["entries"]]

        assert snapshot["entry_count"] <= 3
        assert snapshot["token_total"] <= 9
        assert len(keys) == len(set(keys))
        assert stable_key in keys

    final_snapshot = cache.hot_tier_snapshot()
    final_keys = [item["cache_key"] for item in final_snapshot["entries"]]

    assert final_snapshot["entry_count"] == 3
    assert final_snapshot["token_total"] == 9
    assert set(final_keys) == {
        stable_key,
        f"{46:016x}",
        f"{47:016x}",
    }


def test_stage_artifact_cache_hot_tier_same_key_warm_hits_do_not_accumulate(
    tmp_path: Path,
) -> None:
    stable_key = "abcdef0000000000"
    writer = StageArtifactCache(
        repo_root=tmp_path,
        hot_max_entries=2,
        hot_max_tokens=10,
    )
    writer.put_artifact(
        stage_name="source_plan",
        cache_key=stable_key,
        query_hash="1111222233334444",
        fingerprint="stable-fingerprint",
        payload={"source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}},
        token_weight=4,
        write_token="seed",
    )

    for _ in range(40):
        reader = StageArtifactCache(
            repo_root=tmp_path,
            hot_max_entries=2,
            hot_max_tokens=10,
        )
        hit = reader.get_artifact(
            stage_name="source_plan",
            cache_key=stable_key,
        )
        assert hit is not None
        hit.payload["source_plan"]["steps"][0]["id"] = 77
        assert hit.payload == {
            "source_plan": {"steps": [{"id": 77, "stage": "source_plan"}]}
        }

    snapshot = writer.hot_tier_snapshot()

    assert snapshot["entry_count"] == 1
    assert snapshot["token_total"] == 4
    assert snapshot["entries"] == [
        {
            "stage_name": "source_plan",
            "cache_key": stable_key,
            "token_weight": 4,
        }
    ]

    final_hit = writer.get_artifact(
        stage_name="source_plan",
        cache_key=stable_key,
    )
    assert final_hit is not None
    assert final_hit.payload == {
        "source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}
    }
