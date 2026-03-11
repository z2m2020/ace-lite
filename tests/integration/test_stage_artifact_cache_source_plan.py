from __future__ import annotations

import json
import multiprocessing
import sqlite3
import traceback
from pathlib import Path
from queue import Empty
from typing import Any

from ace_lite.plan_replay_cache import load_cached_plan
from ace_lite.plan_replay_cache import store_cached_plan
from ace_lite.runtime_db import connect_runtime_db
from ace_lite.stage_artifact_cache import StageArtifactCache


def _writer_worker(
    *,
    repo_root: str,
    worker_id: int,
    iterations: int,
    queue: Any,
) -> None:
    try:
        cache = StageArtifactCache(repo_root=repo_root)
        for iteration in range(iterations):
            cache.put_artifact(
                stage_name="source_plan",
                cache_key=f"{worker_id:02x}{iteration:014x}",
                query_hash=f"{iteration:016x}",
                fingerprint=f"fingerprint-{worker_id}-{iteration}",
                payload={
                    "source_plan": {
                        "steps": [{"id": iteration, "stage": "source_plan"}],
                    }
                },
                write_token=f"writer-{worker_id}",
            )
        queue.put({"role": "writer", "worker_id": worker_id, "ok": True})
    except Exception:
        queue.put(
            {
                "role": "writer",
                "worker_id": worker_id,
                "ok": False,
                "traceback": traceback.format_exc(),
            }
        )


def _reader_worker(
    *,
    repo_root: str,
    iterations: int,
    queue: Any,
) -> None:
    try:
        cache = StageArtifactCache(repo_root=repo_root)
        for _ in range(iterations):
            hit = cache.get_artifact(
                stage_name="source_plan",
                cache_key="stable0000000000",
            )
            assert hit is not None
            assert hit.payload == {
                "source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}
            }
        queue.put({"role": "reader", "ok": True})
    except Exception:
        queue.put({"role": "reader", "ok": False, "traceback": traceback.format_exc()})


def test_source_plan_replay_cache_preserves_legacy_parity_and_stage_artifact_round_trip(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "context-map" / "plan-replay" / "cache.json"
    payload = {"source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}}

    assert store_cached_plan(
        cache_path=cache_path,
        key="abcdef0123456789",
        payload=payload,
        meta={"query": "draft auth plan", "repo": "ace-lite-engine", "stage": "source_plan"},
    )

    marker = json.loads(cache_path.read_text(encoding="utf-8"))
    assert marker["backend"] == "stage_artifact_cache"
    assert load_cached_plan(cache_path=cache_path, key="abcdef0123456789") == payload

    legacy_payload = {
        "schema_version": "plan-replay-cache-v1",
        "entries": [
            {
                "key": "legacy-key",
                "updated_at_epoch": 1.0,
                "meta": {"query": "draft auth plan"},
                "payload": payload,
            }
        ],
    }
    cache_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    assert load_cached_plan(cache_path=cache_path, key="legacy-key") == payload


def test_stage_artifact_cache_cleans_orphan_temp_payloads(tmp_path: Path) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    orphan = cache.temp_root / "source_plan" / "ab" / "abcdef.worker.json.tmp"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text('{"orphan": true}\n', encoding="utf-8")

    deleted = cache.cleanup_temp_payloads()

    assert deleted == 1
    assert orphan.exists() is False


def test_stage_artifact_cache_concurrent_readers_see_stable_payload_during_churn(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="stable0000000000",
        query_hash="1111222233334444",
        fingerprint="stable-fingerprint",
        payload={"source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}},
        write_token="seed",
    )

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_writer_worker,
            kwargs={
                "repo_root": str(tmp_path),
                "worker_id": worker_id,
                "iterations": 8,
                "queue": queue,
            },
        )
        for worker_id in range(1, 3)
    ]
    processes.extend(
        [
            ctx.Process(
                target=_reader_worker,
                kwargs={
                    "repo_root": str(tmp_path),
                    "iterations": 10,
                    "queue": queue,
                },
            )
            for _ in range(2)
        ]
    )

    for process in processes:
        process.start()

    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
            raise AssertionError(f"worker {process.pid} timed out")
        assert process.exitcode == 0

    results: list[dict[str, Any]] = []
    while len(results) < len(processes):
        try:
            results.append(queue.get_nowait())
        except Empty:
            break

    assert len(results) == len(processes)
    assert [item for item in results if not bool(item.get("ok"))] == []

    hit = cache.get_artifact(stage_name="source_plan", cache_key="stable0000000000")
    assert hit is not None
    assert hit.payload == {"source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}}

    conn = connect_runtime_db(db_path=cache.store.db_path, row_factory=sqlite3.Row)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        assert str(integrity[0]) == "ok"
    finally:
        conn.close()
