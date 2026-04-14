from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.stage_artifact_cache import StageArtifactCache
from ace_lite.stage_artifact_cache_store import (
    STAGE_ARTIFACT_CACHE_ENTRIES_TABLE,
    StageArtifactCacheEntry,
    build_stage_artifact_cache_migration_bootstrap,
    normalize_stage_artifact_cache_entry,
)

_SQLITE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validated_sqlite_identifier(name: str) -> str:
    normalized = str(name or "").strip()
    if not _SQLITE_IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"invalid_sqlite_identifier:{normalized or '<empty>'}")
    return normalized


_STAGE_ARTIFACT_CACHE_ENTRIES_TABLE = _validated_sqlite_identifier(
    STAGE_ARTIFACT_CACHE_ENTRIES_TABLE
)


def verify_stage_artifact_cache(
    *,
    repo_root: str | Path,
    db_path: str | Path | None = None,
    configured_db_path: str | Path | None = None,
    payload_root: str | Path | None = None,
    temp_root: str | Path | None = None,
) -> dict[str, Any]:
    cache = StageArtifactCache(
        repo_root=repo_root,
        db_path=db_path,
        configured_db_path=configured_db_path,
        payload_root=payload_root,
        temp_root=temp_root,
    )
    entries = _load_entries(cache=cache)
    now = datetime.now(timezone.utc)

    missing_payload_rows: list[dict[str, Any]] = []
    invalid_payload_rows: list[dict[str, Any]] = []
    checksum_mismatch_rows: list[dict[str, Any]] = []
    expired_rows: list[dict[str, Any]] = []
    orphaned_metadata_rows: list[dict[str, Any]] = []
    referenced_payloads: set[str] = set()

    for entry in entries:
        issue = _entry_issue(entry)
        payload_relpath = str(entry.payload_relpath or "").strip()
        if payload_relpath:
            referenced_payloads.add(payload_relpath)
        payload_path = _resolve_payload_path(cache=cache, payload_relpath=payload_relpath)

        if entry.orphaned:
            orphaned_metadata_rows.append(issue)
        if _is_expired(entry.expires_at, now=now):
            expired_rows.append(issue)
        if not payload_relpath:
            missing_payload_rows.append({**issue, "reason": "missing_payload_relpath"})
            continue
        if not payload_path.is_file():
            missing_payload_rows.append({**issue, "reason": "missing_payload"})
            continue

        payload_bytes = payload_path.read_bytes()
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        if entry.payload_sha256 and payload_sha256 != entry.payload_sha256:
            checksum_mismatch_rows.append(
                {
                    **issue,
                    "reason": "payload_sha256_mismatch",
                    "actual_payload_sha256": payload_sha256,
                }
            )

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalid_payload_rows.append({**issue, "reason": "invalid_payload"})
            continue
        if not isinstance(payload, dict):
            invalid_payload_rows.append({**issue, "reason": "payload_not_object"})

    orphan_payload_files = _find_orphan_payload_files(
        cache=cache,
        referenced_payloads=referenced_payloads,
    )
    temp_payload_files = _scan_temp_payload_files(cache=cache)

    severe_issue_count = (
        len(missing_payload_rows)
        + len(invalid_payload_rows)
        + len(checksum_mismatch_rows)
    )
    warning_issue_count = (
        len(expired_rows) + len(orphan_payload_files) + len(orphaned_metadata_rows)
    )

    return {
        "ok": severe_issue_count == 0,
        "db_path": str(cache.store.db_path),
        "payload_root": str(cache.payload_root),
        "temp_root": str(cache.temp_root),
        "entry_count": len(entries),
        "payload_file_count": _count_payload_files(cache=cache),
        "temp_payload_file_count": len(temp_payload_files),
        "severe_issue_count": severe_issue_count,
        "warning_issue_count": warning_issue_count,
        "missing_payload_rows": missing_payload_rows,
        "invalid_payload_rows": invalid_payload_rows,
        "checksum_mismatch_rows": checksum_mismatch_rows,
        "expired_rows": expired_rows,
        "orphan_payload_files": orphan_payload_files,
        "orphaned_metadata_rows": orphaned_metadata_rows,
        "temp_payload_files": temp_payload_files,
        "scanned_at": now.isoformat(),
    }


def vacuum_stage_artifact_cache(
    *,
    repo_root: str | Path,
    db_path: str | Path | None = None,
    configured_db_path: str | Path | None = None,
    payload_root: str | Path | None = None,
    temp_root: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    cache = StageArtifactCache(
        repo_root=repo_root,
        db_path=db_path,
        configured_db_path=configured_db_path,
        payload_root=payload_root,
        temp_root=temp_root,
    )
    report = verify_stage_artifact_cache(
        repo_root=repo_root,
        db_path=db_path,
        configured_db_path=configured_db_path,
        payload_root=payload_root,
        temp_root=temp_root,
    )
    expired_rows = list(report.get("expired_rows", []))
    orphan_payload_files = list(report.get("orphan_payload_files", []))

    deleted_expired_rows = 0
    deleted_expired_payload_files = 0
    deleted_orphan_payload_files = 0
    errors: list[dict[str, str]] = []

    if apply:
        if expired_rows:
            conn = connect_runtime_db(
                db_path=cache.store.db_path,
                row_factory=sqlite3.Row,
                migration_bootstrap=build_stage_artifact_cache_migration_bootstrap(),
            )
            try:
                conn.execute("BEGIN IMMEDIATE")
                for item in expired_rows:
                    payload_relpath = str(item.get("payload_relpath") or "").strip()
                    if payload_relpath:
                        payload_path = _resolve_payload_path(
                            cache=cache,
                            payload_relpath=payload_relpath,
                        )
                        try:
                            if payload_path.is_file():
                                payload_path.unlink()
                                deleted_expired_payload_files += 1
                        except OSError as exc:
                            errors.append(
                                {
                                    "kind": "expired_payload_delete",
                                    "path": str(payload_path),
                                    "error": str(exc),
                                }
                            )
                    conn.execute(
                        f"DELETE FROM {_STAGE_ARTIFACT_CACHE_ENTRIES_TABLE} WHERE stage_name = ? AND cache_key = ?",  # nosec B608
                        (
                            str(item.get("stage_name") or "").strip(),
                            str(item.get("cache_key") or "").strip(),
                        ),
                    )
                    deleted_expired_rows += 1
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()

        for item in orphan_payload_files:
            payload_relpath = str(item.get("payload_relpath") or "").strip()
            if not payload_relpath:
                continue
            payload_path = _resolve_payload_path(cache=cache, payload_relpath=payload_relpath)
            try:
                if payload_path.is_file():
                    payload_path.unlink()
                    deleted_orphan_payload_files += 1
            except OSError as exc:
                errors.append(
                    {
                        "kind": "orphan_payload_delete",
                        "path": str(payload_path),
                        "error": str(exc),
                    }
                )

        _prune_empty_dirs(root=cache.payload_root)

    return {
        "ok": len(errors) == 0,
        "dry_run": not apply,
        "db_path": str(cache.store.db_path),
        "payload_root": str(cache.payload_root),
        "temp_root": str(cache.temp_root),
        "expired_row_candidates": len(expired_rows),
        "orphan_payload_candidates": len(orphan_payload_files),
        "deleted_expired_rows": deleted_expired_rows,
        "deleted_expired_payload_files": deleted_expired_payload_files,
        "deleted_orphan_payload_files": deleted_orphan_payload_files,
        "errors": errors,
        "report": report,
    }


def run_bounded_stage_artifact_cache_gc(
    *,
    repo_root: str | Path,
    db_path: str | Path | None = None,
    configured_db_path: str | Path | None = None,
    payload_root: str | Path | None = None,
    temp_root: str | Path | None = None,
    budget_ms: float = 50.0,
    max_delete: int = 16,
) -> dict[str, Any]:
    cache = StageArtifactCache(
        repo_root=repo_root,
        db_path=db_path,
        configured_db_path=configured_db_path,
        payload_root=payload_root,
        temp_root=temp_root,
    )
    started = perf_counter()
    resolved_budget_ms = max(1.0, float(budget_ms))
    delete_budget = max(0, int(max_delete))
    deleted_total = 0
    deleted_temp_payloads = 0
    deleted_expired_rows = 0
    deleted_expired_payload_files = 0
    deleted_orphan_payload_files = 0
    exhausted_budget = False

    for path in sorted(cache.temp_root.rglob("*"), reverse=True) if cache.temp_root.exists() else []:
        if path.is_dir():
            continue
        if _budget_exhausted(started=started, budget_ms=resolved_budget_ms):
            exhausted_budget = True
            break
        if deleted_total >= delete_budget:
            break
        path.unlink(missing_ok=True)
        deleted_total += 1
        deleted_temp_payloads += 1

    if not exhausted_budget and deleted_total < delete_budget:
        conn = connect_runtime_db(
            db_path=cache.store.db_path,
            row_factory=sqlite3.Row,
            migration_bootstrap=build_stage_artifact_cache_migration_bootstrap(),
        )
        try:
            entries = _load_entries(cache=cache)
            expired_entries = [
                entry
                for entry in entries
                if _is_expired(entry.expires_at, now=datetime.now(timezone.utc))
            ]
            conn.execute("BEGIN IMMEDIATE")
            for entry in expired_entries:
                if _budget_exhausted(started=started, budget_ms=resolved_budget_ms):
                    exhausted_budget = True
                    break
                if deleted_total >= delete_budget:
                    break
                payload_relpath = str(entry.payload_relpath or "").strip()
                if payload_relpath:
                    payload_path = _resolve_payload_path(
                        cache=cache,
                        payload_relpath=payload_relpath,
                    )
                    if payload_path.is_file():
                        payload_path.unlink(missing_ok=True)
                        deleted_expired_payload_files += 1
                conn.execute(
                    f"DELETE FROM {_STAGE_ARTIFACT_CACHE_ENTRIES_TABLE} WHERE stage_name = ? AND cache_key = ?",  # nosec B608
                    (entry.stage_name, entry.cache_key),
                )
                deleted_total += 1
                deleted_expired_rows += 1
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    if not exhausted_budget and deleted_total < delete_budget:
        referenced_payloads = {
            str(entry.payload_relpath or "").strip()
            for entry in _load_entries(cache=cache)
            if str(entry.payload_relpath or "").strip()
        }
        for path in sorted(cache.payload_root.rglob("*.json")) if cache.payload_root.exists() else []:
            if not path.is_file():
                continue
            if _budget_exhausted(started=started, budget_ms=resolved_budget_ms):
                exhausted_budget = True
                break
            if deleted_total >= delete_budget:
                break
            relpath = path.relative_to(cache.payload_root).as_posix()
            if relpath in referenced_payloads:
                continue
            path.unlink(missing_ok=True)
            deleted_total += 1
            deleted_orphan_payload_files += 1

    _prune_empty_dirs(root=cache.payload_root)
    _prune_empty_dirs(root=cache.temp_root)
    elapsed_ms = max(0.0, (perf_counter() - started) * 1000.0)
    if _budget_exhausted(started=started, budget_ms=resolved_budget_ms):
        exhausted_budget = True

    return {
        "ok": True,
        "mode": "bounded_opportunistic",
        "budget_ms": resolved_budget_ms,
        "elapsed_ms": round(elapsed_ms, 3),
        "max_delete": delete_budget,
        "deleted_total": deleted_total,
        "deleted_temp_payloads": deleted_temp_payloads,
        "deleted_expired_rows": deleted_expired_rows,
        "deleted_expired_payload_files": deleted_expired_payload_files,
        "deleted_orphan_payload_files": deleted_orphan_payload_files,
        "exhausted_budget": exhausted_budget,
    }


def _load_entries(*, cache: StageArtifactCache) -> list[StageArtifactCacheEntry]:
    conn = connect_runtime_db(
        db_path=cache.store.db_path,
        row_factory=sqlite3.Row,
        migration_bootstrap=build_stage_artifact_cache_migration_bootstrap(),
    )
    try:
        rows = conn.execute(
            f"SELECT * FROM {_STAGE_ARTIFACT_CACHE_ENTRIES_TABLE} ORDER BY stage_name, cache_key"  # nosec B608
        ).fetchall()
    finally:
        conn.close()
    return [normalize_stage_artifact_cache_entry(dict(row)) for row in rows]


def _entry_issue(entry: StageArtifactCacheEntry) -> dict[str, Any]:
    return {
        "stage_name": entry.stage_name,
        "cache_key": entry.cache_key,
        "payload_relpath": entry.payload_relpath,
        "payload_bytes": int(entry.payload_bytes),
        "payload_sha256": entry.payload_sha256,
        "expires_at": entry.expires_at,
        "orphaned": bool(entry.orphaned),
        "orphan_reason": entry.orphan_reason,
    }


def _resolve_payload_path(*, cache: StageArtifactCache, payload_relpath: str) -> Path:
    pure = PurePosixPath(str(payload_relpath or "").strip())
    return cache.payload_root / Path(*pure.parts) if pure.parts else cache.payload_root


def _is_expired(expires_at: str, *, now: datetime) -> bool:
    text = str(expires_at or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= now


def _find_orphan_payload_files(
    *,
    cache: StageArtifactCache,
    referenced_payloads: set[str],
) -> list[dict[str, Any]]:
    if not cache.payload_root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(cache.payload_root.rglob("*.json")):
        if not path.is_file():
            continue
        relpath = path.relative_to(cache.payload_root).as_posix()
        if relpath in referenced_payloads:
            continue
        rows.append(
            {
                "payload_relpath": relpath,
                "payload_bytes": int(path.stat().st_size),
                "reason": "unreferenced_payload",
            }
        )
    return rows


def _scan_temp_payload_files(*, cache: StageArtifactCache) -> list[dict[str, Any]]:
    if not cache.temp_root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(cache.temp_root.rglob("*")):
        if not path.is_file():
            continue
        rows.append(
            {
                "temp_relpath": path.relative_to(cache.temp_root).as_posix(),
                "payload_bytes": int(path.stat().st_size),
            }
        )
    return rows


def _count_payload_files(*, cache: StageArtifactCache) -> int:
    if not cache.payload_root.exists():
        return 0
    return sum(1 for path in cache.payload_root.rglob("*.json") if path.is_file())


def _prune_empty_dirs(*, root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if not path.is_dir():
            continue
        try:
            path.rmdir()
        except OSError:
            continue


def _budget_exhausted(*, started: float, budget_ms: float) -> bool:
    return (perf_counter() - started) * 1000.0 >= max(1.0, float(budget_ms))


__all__ = [
    "run_bounded_stage_artifact_cache_gc",
    "vacuum_stage_artifact_cache",
    "verify_stage_artifact_cache",
]
