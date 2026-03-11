from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

try:  # pragma: no cover - sqlite3 may be unavailable in minimal runtimes
    import sqlite3
except Exception:  # pragma: no cover
    sqlite3 = None  # type: ignore[assignment]


MIRROR_SCHEMA_VERSION = "ace-lite-sqlite-mirror-v1"
DEFAULT_DB_RELATIVE_PATH = Path("context-map/index.db")


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000.0, 3)


def _sha256_pairs(pairs: list[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for key, value in pairs:
        digest.update(str(key).encode("utf-8", errors="ignore"))
        digest.update(b"\x00")
        digest.update(str(value).encode("utf-8", errors="ignore"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def compute_hash_fingerprint(file_hashes: dict[str, str]) -> str:
    """Compute a stable fingerprint from per-path sha256 hashes."""
    pairs = [(str(path), str(file_hashes.get(path, ""))) for path in sorted(file_hashes)]
    return _sha256_pairs(pairs)


def resolve_mirror_db_path(*, root: str | Path, configured_path: str | Path | None = None) -> Path:
    """Resolve the mirror database path under the repo root."""
    root_path = Path(root)
    path = Path(configured_path) if configured_path is not None else DEFAULT_DB_RELATIVE_PATH
    if path.is_absolute():
        return path
    return root_path / path


def _connect(db_path: Path) -> Any:
    if sqlite3 is None:
        raise RuntimeError("sqlite3_unavailable")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_meta_table(conn: Any) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS mirror_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def _get_meta(conn: Any, key: str) -> str:
    cursor = conn.execute("SELECT value FROM mirror_meta WHERE key = ?", (str(key),))
    row = cursor.fetchone()
    return str(row["value"]) if row else ""


def _set_meta(conn: Any, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO mirror_meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(key), str(value)),
    )


def _table_exists(conn: Any, name: str) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (str(name),),
    )
    return cursor.fetchone() is not None


def supports_fts5() -> bool:
    """Return True if sqlite3 supports FTS5 virtual tables."""
    if sqlite3 is None:
        return False

    try:
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE VIRTUAL TABLE fts5_probe USING fts5(content)")
            conn.execute("DROP TABLE fts5_probe")
        finally:
            conn.close()
        return True
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class DocsMirrorResult:
    enabled: bool
    reason: str
    path: str
    cache_hit: bool
    rebuilt: bool
    fts5_available: bool
    docs_fingerprint: str
    section_count: int
    elapsed_ms: float
    warning: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "reason": str(self.reason),
            "path": str(self.path),
            "cache_hit": bool(self.cache_hit),
            "rebuilt": bool(self.rebuilt),
            "fts5_available": bool(self.fts5_available),
            "docs_fingerprint": str(self.docs_fingerprint),
            "section_count": int(self.section_count),
            "elapsed_ms": float(self.elapsed_ms),
            "warning": str(self.warning or ""),
        }


def ensure_docs_fts_mirror(
    *,
    db_path: Path,
    docs_fingerprint: str,
    sections: list[dict[str, Any]],
) -> DocsMirrorResult:
    """Ensure docs sections are mirrored into a persistent FTS5 index.

    This is a best-effort optimization. Failures must be safe and should not
    prevent docs scoring from falling back to in-memory or python BM25 paths.
    """
    started = perf_counter()
    section_count = len(sections) if isinstance(sections, list) else 0
    normalized_fingerprint = str(docs_fingerprint or "").strip()

    if sqlite3 is None:
        return DocsMirrorResult(
            enabled=False,
            reason="sqlite3_unavailable",
            path=str(db_path),
            cache_hit=False,
            rebuilt=False,
            fts5_available=False,
            docs_fingerprint=normalized_fingerprint,
            section_count=section_count,
            elapsed_ms=_elapsed_ms(started),
            warning="sqlite3_unavailable",
        )

    fts5_available = supports_fts5()
    if not fts5_available:
        return DocsMirrorResult(
            enabled=False,
            reason="fts5_unavailable",
            path=str(db_path),
            cache_hit=False,
            rebuilt=False,
            fts5_available=False,
            docs_fingerprint=normalized_fingerprint,
            section_count=section_count,
            elapsed_ms=_elapsed_ms(started),
            warning=None,
        )

    try:
        conn = _connect(db_path)
    except Exception as exc:
        return DocsMirrorResult(
            enabled=False,
            reason="open_failed",
            path=str(db_path),
            cache_hit=False,
            rebuilt=False,
            fts5_available=True,
            docs_fingerprint=normalized_fingerprint,
            section_count=section_count,
            elapsed_ms=_elapsed_ms(started),
            warning=str(exc)[:240],
        )

    try:
        _ensure_meta_table(conn)
        schema = _get_meta(conn, "schema_version")
        cached_fingerprint = _get_meta(conn, "docs_fingerprint")
        cached_count_raw = _get_meta(conn, "docs_section_count")
        try:
            cached_count = int(cached_count_raw)
        except Exception:
            cached_count = -1

        cache_hit = (
            schema == MIRROR_SCHEMA_VERSION
            and cached_fingerprint == normalized_fingerprint
            and cached_count == section_count
            and _table_exists(conn, "docs_fts")
        )
        if cache_hit:
            return DocsMirrorResult(
                enabled=True,
                reason="cache_hit",
                path=str(db_path),
                cache_hit=True,
                rebuilt=False,
                fts5_available=True,
                docs_fingerprint=normalized_fingerprint,
                section_count=section_count,
                elapsed_ms=_elapsed_ms(started),
                warning=None,
            )

        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS docs_fts")
        conn.execute(
            "CREATE VIRTUAL TABLE docs_fts USING fts5("
            "path, heading, heading_path, body, "
            "line_start UNINDEXED, line_end UNINDEXED)"
        )

        rows: list[tuple[int, str, str, str, str, int, int]] = []
        for index, item in enumerate(sections, start=1):
            if not isinstance(item, dict):
                continue
            rows.append(
                (
                    int(index),
                    str(item.get("path") or ""),
                    str(item.get("heading") or ""),
                    str(item.get("heading_path") or ""),
                    str(item.get("body") or ""),
                    int(item.get("line_start", 0) or 0),
                    int(item.get("line_end", 0) or 0),
                )
            )

        if rows:
            conn.executemany(
                (
                    "INSERT INTO docs_fts(rowid, path, heading, heading_path, body, line_start, line_end) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)"
                ),
                rows,
            )

        _set_meta(conn, "schema_version", MIRROR_SCHEMA_VERSION)
        _set_meta(conn, "docs_fingerprint", normalized_fingerprint)
        _set_meta(conn, "docs_section_count", str(section_count))
        conn.execute("COMMIT")

        return DocsMirrorResult(
            enabled=True,
            reason="rebuilt",
            path=str(db_path),
            cache_hit=False,
            rebuilt=True,
            fts5_available=True,
            docs_fingerprint=normalized_fingerprint,
            section_count=section_count,
            elapsed_ms=_elapsed_ms(started),
            warning=None,
        )
    except Exception as exc:
        with suppress(Exception):
            conn.execute("ROLLBACK")
        return DocsMirrorResult(
            enabled=False,
            reason="error",
            path=str(db_path),
            cache_hit=False,
            rebuilt=False,
            fts5_available=True,
            docs_fingerprint=normalized_fingerprint,
            section_count=section_count,
            elapsed_ms=_elapsed_ms(started),
            warning=str(exc)[:240],
        )
    finally:
        with suppress(Exception):
            conn.close()


def query_docs_fts(
    *,
    db_path: Path,
    query_expr: str,
    limit: int,
) -> list[tuple[int, float]]:
    """Query mirrored FTS5 table and return (rowid, raw_bm25_score)."""
    if sqlite3 is None:
        return []

    normalized_query = str(query_expr or "").strip()
    if not normalized_query:
        return []
    max_rows = max(1, int(limit))

    try:
        conn = _connect(db_path)
    except Exception:
        return []
    try:
        if not _table_exists(conn, "docs_fts"):
            return []
        cursor = conn.execute(
            (
                "SELECT rowid, bm25(docs_fts, 0.8, 1.6, 1.2, 1.0) AS bm25_score "
                "FROM docs_fts WHERE docs_fts MATCH ? "
                "ORDER BY bm25_score ASC, rowid ASC LIMIT ?"
            ),
            (normalized_query, max_rows),
        )
        rows: list[tuple[int, float]] = []
        for row in cursor.fetchall():
            try:
                rowid = int(row["rowid"] or 0)
            except Exception:
                rowid = 0
            if rowid <= 0:
                continue
            try:
                raw = float(row["bm25_score"] or 0.0)
            except Exception:
                raw = 0.0
            rows.append((rowid, raw))
        return rows
    except Exception:
        return []
    finally:
        with suppress(Exception):
            conn.close()


@dataclass(frozen=True, slots=True)
class EmbeddingsMirrorResult:
    enabled: bool
    reason: str
    path: str
    provider: str
    model: str
    dimension: int
    fingerprint: str
    upserted: int
    deleted: int
    elapsed_ms: float
    warning: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "reason": str(self.reason),
            "path": str(self.path),
            "provider": str(self.provider),
            "model": str(self.model),
            "dimension": int(self.dimension),
            "fingerprint": str(self.fingerprint),
            "upserted": int(self.upserted),
            "deleted": int(self.deleted),
            "elapsed_ms": float(self.elapsed_ms),
            "warning": str(self.warning or ""),
        }


def write_embeddings_mirror(
    *,
    db_path: Path,
    provider: str,
    model: str,
    dimension: int,
    file_hashes: dict[str, str],
    vectors: dict[str, list[float]],
) -> EmbeddingsMirrorResult:
    """Write-through embedding vectors + hashes into the mirror DB.

    JSON remains the source-of-truth. The mirror is best-effort and must be
    safe to skip on any sqlite errors.
    """
    started = perf_counter()
    if sqlite3 is None:
        return EmbeddingsMirrorResult(
            enabled=False,
            reason="sqlite3_unavailable",
            path=str(db_path),
            provider=str(provider),
            model=str(model),
            dimension=int(dimension),
            fingerprint="",
            upserted=0,
            deleted=0,
            elapsed_ms=_elapsed_ms(started),
            warning="sqlite3_unavailable",
        )

    normalized_provider = str(provider or "").strip()
    normalized_model = str(model or "").strip()
    normalized_dimension = max(1, int(dimension))
    fingerprint = compute_hash_fingerprint(file_hashes)

    try:
        conn = _connect(db_path)
    except Exception as exc:
        return EmbeddingsMirrorResult(
            enabled=False,
            reason="open_failed",
            path=str(db_path),
            provider=normalized_provider,
            model=normalized_model,
            dimension=normalized_dimension,
            fingerprint=fingerprint,
            upserted=0,
            deleted=0,
            elapsed_ms=_elapsed_ms(started),
            warning=str(exc)[:240],
        )

    upserted = 0
    deleted = 0
    try:
        _ensure_meta_table(conn)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embedding_vectors("
            "provider TEXT NOT NULL, "
            "model TEXT NOT NULL, "
            "dimension INTEGER NOT NULL, "
            "path TEXT NOT NULL, "
            "sha256 TEXT NOT NULL, "
            "vector_json TEXT NOT NULL, "
            "batch_id TEXT NOT NULL, "
            "PRIMARY KEY (provider, model, dimension, path))"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS embedding_vectors_batch "
            "ON embedding_vectors(provider, model, dimension, batch_id)"
        )

        conn.execute("BEGIN")
        for path, sha in sorted(file_hashes.items()):
            vector = vectors.get(path)
            if vector is None:
                continue
            vector_json = json.dumps(vector, ensure_ascii=False, separators=(",", ":"))
            conn.execute(
                (
                    "INSERT INTO embedding_vectors(provider, model, dimension, path, sha256, vector_json, batch_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(provider, model, dimension, path) DO UPDATE SET "
                    "sha256=excluded.sha256, vector_json=excluded.vector_json, batch_id=excluded.batch_id"
                ),
                (
                    normalized_provider,
                    normalized_model,
                    normalized_dimension,
                    str(path),
                    str(sha),
                    vector_json,
                    fingerprint,
                ),
            )
            upserted += 1

        cursor = conn.execute(
            (
                "DELETE FROM embedding_vectors WHERE provider = ? AND model = ? AND dimension = ? "
                "AND batch_id != ?"
            ),
            (normalized_provider, normalized_model, normalized_dimension, fingerprint),
        )
        deleted = int(cursor.rowcount or 0)
        _set_meta(conn, "schema_version", MIRROR_SCHEMA_VERSION)
        conn.execute("COMMIT")
        return EmbeddingsMirrorResult(
            enabled=True,
            reason="ok",
            path=str(db_path),
            provider=normalized_provider,
            model=normalized_model,
            dimension=normalized_dimension,
            fingerprint=fingerprint,
            upserted=upserted,
            deleted=deleted,
            elapsed_ms=_elapsed_ms(started),
            warning=None,
        )
    except Exception as exc:
        with suppress(Exception):
            conn.execute("ROLLBACK")
        return EmbeddingsMirrorResult(
            enabled=False,
            reason="error",
            path=str(db_path),
            provider=normalized_provider,
            model=normalized_model,
            dimension=normalized_dimension,
            fingerprint=fingerprint,
            upserted=upserted,
            deleted=deleted,
            elapsed_ms=_elapsed_ms(started),
            warning=str(exc)[:240],
        )
    finally:
        with suppress(Exception):
            conn.close()


__all__ = [
    "DEFAULT_DB_RELATIVE_PATH",
    "MIRROR_SCHEMA_VERSION",
    "DocsMirrorResult",
    "EmbeddingsMirrorResult",
    "compute_hash_fingerprint",
    "ensure_docs_fts_mirror",
    "query_docs_fts",
    "resolve_mirror_db_path",
    "supports_fts5",
    "write_embeddings_mirror",
]
