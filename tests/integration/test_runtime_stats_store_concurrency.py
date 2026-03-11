from __future__ import annotations

import multiprocessing
import traceback
from pathlib import Path
from queue import Empty
from typing import Any

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_stats import RuntimeInvocationStats, RuntimeStageLatency
from ace_lite.runtime_stats_store import DurableStatsStore


def _writer_worker(*, db_path: str, worker_id: int, iterations: int, queue: Any) -> None:
    try:
        store = DurableStatsStore(db_path=db_path)
        for iteration in range(iterations):
            store.record_invocation(
                RuntimeInvocationStats(
                    invocation_id=f"w{worker_id}-i{iteration}",
                    session_id=f"session-{worker_id}",
                    repo_key="repo-alpha",
                    profile_key="bugfix",
                    status="succeeded",
                    total_latency_ms=float(worker_id + iteration + 1),
                    stage_latencies=(
                        RuntimeStageLatency(stage_name="memory", elapsed_ms=1.0),
                        RuntimeStageLatency(
                            stage_name="total",
                            elapsed_ms=float(worker_id + iteration + 1),
                        ),
                    ),
                    plan_replay_hit=(iteration % 2 == 0),
                )
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


def _reader_worker(*, db_path: str, iterations: int, queue: Any) -> None:
    try:
        store = DurableStatsStore(db_path=db_path)
        for _ in range(iterations):
            snapshot = store.read_snapshot(
                session_id="session-1",
                repo_key="repo-alpha",
                profile_key="bugfix",
            )
            assert isinstance(snapshot.to_payload()["scopes"], list)
        queue.put({"role": "reader", "ok": True})
    except Exception:
        queue.put({"role": "reader", "ok": False, "traceback": traceback.format_exc()})


def test_runtime_stats_store_handles_concurrent_writers_and_readers(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime-stats.db"
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_writer_worker,
            kwargs={
                "db_path": str(db_path),
                "worker_id": worker_id,
                "iterations": 6,
                "queue": queue,
            },
        )
        for worker_id in range(1, 4)
    ]
    processes.append(
        ctx.Process(
            target=_reader_worker,
            kwargs={
                "db_path": str(db_path),
                "iterations": 6,
                "queue": queue,
            },
        )
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

    store = DurableStatsStore(db_path=db_path)
    scope = store.read_scope(scope_kind="repo_profile", scope_key="repo-alpha::bugfix")
    assert scope is not None
    payload = scope.to_payload()
    assert payload["counters"]["invocation_count"] == 18
    assert payload["counters"]["plan_replay_hit_count"] == 9

    conn = connect_runtime_db(db_path=db_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        assert str(integrity[0]) == "ok"
    finally:
        conn.close()
