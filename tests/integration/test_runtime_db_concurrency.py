from __future__ import annotations

import json
import multiprocessing
import traceback
from pathlib import Path
from queue import Empty
from typing import Any

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.sqlite_mirror import MIRROR_SCHEMA_VERSION, write_embeddings_mirror


def _writer_payload(worker_id: int, iteration: int) -> tuple[dict[str, str], dict[str, list[float]]]:
    file_hashes = {
        f"src/worker_{worker_id}.py": f"hash-{worker_id}-{iteration}",
        f"src/shared.py": f"shared-{iteration}",
    }
    vectors = {
        f"src/worker_{worker_id}.py": [
            float(worker_id),
            float(iteration),
            float(worker_id + iteration),
        ],
        "src/shared.py": [
            float(iteration),
            float(worker_id),
            float(iteration + 1),
        ],
    }
    return file_hashes, vectors


def _writer_worker(
    *,
    db_path: str,
    worker_id: int,
    iterations: int,
    queue: Any,
) -> None:
    try:
        for iteration in range(max(1, int(iterations))):
            file_hashes, vectors = _writer_payload(worker_id, iteration)
            result = write_embeddings_mirror(
                db_path=Path(db_path),
                provider="hash",
                model="hash-v1",
                dimension=3,
                file_hashes=file_hashes,
                vectors=vectors,
            )
            if not result.enabled:
                raise RuntimeError(result.warning or result.reason)
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
    db_path: str,
    worker_id: int,
    iterations: int,
    queue: Any,
) -> None:
    try:
        for _ in range(max(1, int(iterations))):
            conn = connect_runtime_db(db_path=Path(db_path))
            try:
                row = conn.execute("SELECT COUNT(*) FROM embedding_vectors").fetchone()
                count = int(row[0] or 0)
                if count <= 0:
                    raise AssertionError("embedding_vectors unexpectedly empty")
                mirror_meta = conn.execute(
                    "SELECT value FROM mirror_meta WHERE key = 'schema_version'"
                ).fetchone()
                if mirror_meta is None:
                    raise AssertionError("mirror_meta schema_version missing")
            finally:
                conn.close()
        queue.put({"role": "reader", "worker_id": worker_id, "ok": True})
    except Exception:
        queue.put(
            {
                "role": "reader",
                "worker_id": worker_id,
                "ok": False,
                "traceback": traceback.format_exc(),
            }
        )


def test_runtime_db_handles_concurrent_embedding_writers_and_readers(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "context-map" / "runtime.db"
    seed_hashes, seed_vectors = _writer_payload(worker_id=0, iteration=0)
    seed = write_embeddings_mirror(
        db_path=db_path,
        provider="hash",
        model="hash-v1",
        dimension=3,
        file_hashes=seed_hashes,
        vectors=seed_vectors,
    )
    assert seed.enabled is True

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_writer_worker,
            kwargs={
                "db_path": str(db_path),
                "worker_id": worker_id,
                "iterations": 8,
                "queue": queue,
            },
        )
        for worker_id in range(1, 4)
    ]
    processes.extend(
        ctx.Process(
            target=_reader_worker,
            kwargs={
                "db_path": str(db_path),
                "worker_id": worker_id,
                "iterations": 8,
                "queue": queue,
            },
        )
        for worker_id in range(1, 3)
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
    failures = [item for item in results if not bool(item.get("ok"))]
    assert failures == []

    conn = connect_runtime_db(db_path=db_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        assert str(integrity[0]) == "ok"

        meta = conn.execute(
            "SELECT value FROM mirror_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert meta is not None
        assert str(meta[0]) == MIRROR_SCHEMA_VERSION

        rows = conn.execute(
            "SELECT path, vector_json FROM embedding_vectors ORDER BY path"
        ).fetchall()
        assert rows
        for row in rows:
            vector = json.loads(str(row[1]))
            assert isinstance(vector, list)
            assert vector
    finally:
        conn.close()
