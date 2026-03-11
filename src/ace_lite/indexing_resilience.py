from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.indexer import discover_source_files, finalize_index_payload
from ace_lite.parsers.treesitter_engine import TreeSitterEngine

RESUME_STATE_SCHEMA_VERSION = 1


def _classify_tier(*, path: str, language: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/").lstrip("./")
    if normalized.startswith("node_modules/"):
        return "dependency"
    if str(language or "").strip().lower() == "solidity" and normalized.startswith("lib/"):
        return "dependency"
    return "first_party"


@dataclass(frozen=True, slots=True)
class IndexingResilienceConfig:
    batch_size: int = 200
    timeout_per_file_seconds: float | None = None
    resume: bool = False
    resume_state_path: Path = Path("context-map/index.resume.json")
    retry_timeouts: bool = False
    retry_timeout_multiplier: float = 2.0
    subprocess_batch: bool = False
    subprocess_batch_timeout_seconds: float | None = None


def build_index_with_resilience(
    root_dir: str | Path,
    *,
    languages: Iterable[str] | None = None,
    include_globs: Iterable[str] | None = None,
    exclude_dirs: Iterable[str] | None = None,
    config: IndexingResilienceConfig | None = None,
) -> dict[str, Any]:
    """Build a repo index with checkpoint/resume and deterministic resilience stats.

    This entrypoint is intended for the ``ace-lite index`` / ``ace_index`` use
    case when large repositories may require resuming after interruption.
    """

    resolved = config or IndexingResilienceConfig()
    root_path, enabled_languages, file_paths = discover_source_files(
        root_dir,
        include_globs=include_globs,
        exclude_dirs=exclude_dirs,
        languages=languages,
    )
    relative_paths = [path.relative_to(root_path).as_posix() for path in file_paths]

    state_path = _resolve_repo_relative_path(root=root_path, path=resolved.resume_state_path)
    journal_path = _default_journal_path(state_path)

    started_at = datetime.now(timezone.utc).isoformat()
    started_perf = perf_counter()

    file_list_sha256 = _hash_file_list(relative_paths)
    timeout_seconds = _normalize_optional_timeout(resolved.timeout_per_file_seconds)
    batch_size = _normalize_batch_size(resolved.batch_size, total=len(relative_paths))

    state = _load_or_init_state(
        root_path=root_path,
        enabled_languages=enabled_languages,
        state_path=state_path,
        journal_path=journal_path,
        file_list_sha256=file_list_sha256,
        total_files=len(relative_paths),
        resume=bool(resolved.resume),
        batch_size=batch_size,
        timeout_per_file_seconds=timeout_seconds,
        retry_timeouts=bool(resolved.retry_timeouts),
        retry_timeout_multiplier=float(resolved.retry_timeout_multiplier),
        subprocess_batch=bool(resolved.subprocess_batch),
        subprocess_batch_timeout_seconds=resolved.subprocess_batch_timeout_seconds,
    )

    next_index = int(state.get("next_index") or 0)
    next_index = max(0, min(next_index, len(relative_paths)))

    timed_out_files = set(_coerce_string_list(state.get("timed_out_files")))
    failed_files = list(_coerce_failed_files(state.get("failed_files")))

    initial_stats = dict(state.get("stats") or {})
    stats = {
        "total_files": len(relative_paths),
        "processed_files": int(initial_stats.get("processed_files") or 0),
        "parsed_files": int(initial_stats.get("parsed_files") or 0),
        "timed_out_files": int(initial_stats.get("timed_out_files") or 0),
        "failed_files": int(initial_stats.get("failed_files") or 0),
        "retried_files": int(initial_stats.get("retried_files") or 0),
        "retry_succeeded_files": int(initial_stats.get("retry_succeeded_files") or 0),
    }

    if next_index < len(relative_paths):
        _ensure_parent_dir(state_path)
        _ensure_parent_dir(journal_path)

        if not state.get("resume_active"):
            journal_path.write_text("", encoding="utf-8")

        while next_index < len(relative_paths):
            batch = relative_paths[next_index : next_index + batch_size]
            if not batch:
                break

            events: list[dict[str, Any]]
            if resolved.subprocess_batch:
                events = _process_batch_subprocess(
                    root_path=root_path,
                    enabled_languages=enabled_languages,
                    batch=batch,
                    timeout_per_file_seconds=timeout_seconds,
                    batch_timeout_seconds=_resolve_batch_timeout(
                        resolved.subprocess_batch_timeout_seconds,
                        per_file_timeout=timeout_seconds,
                        batch_count=len(batch),
                    ),
                )
            else:
                events = _process_batch_in_process(
                    root_path=root_path,
                    enabled_languages=enabled_languages,
                    batch=batch,
                    timeout_per_file_seconds=timeout_seconds,
                )

            _append_journal_events(journal_path=journal_path, events=events)

            for event in events:
                event_type = str(event.get("type") or "")
                if event_type == "file":
                    stats["processed_files"] += 1
                    stats["parsed_files"] += 1
                elif event_type == "timeout":
                    stats["processed_files"] += 1
                    stats["timed_out_files"] += 1
                    timed_out_files.add(str(event.get("path") or ""))
                elif event_type == "error":
                    stats["processed_files"] += 1
                    stats["failed_files"] += 1
                    failed_files.append(
                        {
                            "path": str(event.get("path") or ""),
                            "error": str(event.get("error") or ""),
                        }
                    )
                else:
                    stats["processed_files"] += 1

            next_index += len(batch)
            state["next_index"] = next_index
            state["stats"] = dict(stats)
            state["timed_out_files"] = sorted(path for path in timed_out_files if path)
            state["failed_files"] = failed_files
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            _atomic_write_json(state_path, state)

    retry_timeout_seconds = _resolve_retry_timeout(
        timeout_seconds=timeout_seconds,
        enabled=bool(resolved.retry_timeouts),
        multiplier=float(resolved.retry_timeout_multiplier),
    )

    if resolved.retry_timeouts and timed_out_files and retry_timeout_seconds is not None:
        retry_paths = sorted(path for path in timed_out_files if path)
        retry_batch_size = min(batch_size, len(retry_paths)) if retry_paths else batch_size
        retry_index = 0
        while retry_index < len(retry_paths):
            batch = retry_paths[retry_index : retry_index + retry_batch_size]
            if not batch:
                break

            events = _process_batch_in_process(
                root_path=root_path,
                enabled_languages=enabled_languages,
                batch=batch,
                timeout_per_file_seconds=retry_timeout_seconds,
                attempt=1,
            )
            _append_journal_events(journal_path=journal_path, events=events)

            for event in events:
                stats["retried_files"] += 1
                event_type = str(event.get("type") or "")
                path = str(event.get("path") or "")
                if event_type == "file":
                    stats["retry_succeeded_files"] += 1
                    stats["parsed_files"] += 1
                    stats["timed_out_files"] = max(0, int(stats["timed_out_files"]) - 1)
                    timed_out_files.discard(path)
                elif event_type == "timeout":
                    timed_out_files.add(path)
                elif event_type == "error":
                    timed_out_files.discard(path)
                    stats["timed_out_files"] = max(0, int(stats["timed_out_files"]) - 1)
                    stats["failed_files"] += 1
                    failed_files.append(
                        {"path": path, "error": str(event.get("error") or "")}
                    )

            retry_index += len(batch)

            state["stats"] = dict(stats)
            state["timed_out_files"] = sorted(path for path in timed_out_files if path)
            state["failed_files"] = failed_files
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            _atomic_write_json(state_path, state)

    engine = TreeSitterEngine(enabled_languages)
    files = _load_files_from_journal(journal_path=journal_path)
    payload = finalize_index_payload(
        {
            "root_dir": str(root_path),
            "files": files,
            "parser": {"engine": "tree-sitter", "version": engine.parser_version},
            "configured_languages": list(enabled_languages),
        }
    )

    finished_at = datetime.now(timezone.utc).isoformat()
    total_ms = (perf_counter() - started_perf) * 1000.0
    payload["indexing_resilience"] = {
        "enabled": True,
        "schema_version": RESUME_STATE_SCHEMA_VERSION,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_ms": total_ms,
        "batch_size": batch_size,
        "timeout_per_file_seconds": timeout_seconds,
        "retry_timeouts": bool(resolved.retry_timeouts),
        "retry_timeout_multiplier": float(resolved.retry_timeout_multiplier),
        "retry_timeout_seconds": retry_timeout_seconds,
        "subprocess_batch": bool(resolved.subprocess_batch),
        "subprocess_batch_timeout_seconds": _normalize_optional_timeout(
            resolved.subprocess_batch_timeout_seconds
        ),
        "resume": bool(resolved.resume),
        "resume_state_path": str(state_path),
        "journal_path": str(journal_path),
        "file_list_sha256": file_list_sha256,
        "stats": dict(stats),
        "timed_out_files": sorted(path for path in timed_out_files if path),
        "failed_files": failed_files,
        "incomplete": bool(timed_out_files or failed_files),
    }
    return payload


def _resolve_repo_relative_path(*, root: Path, path: str | Path) -> Path:
    resolved = Path(path).expanduser()
    if resolved.is_absolute():
        return resolved
    return (root / resolved).resolve()


def _default_journal_path(state_path: Path) -> Path:
    name = state_path.name
    stem = name[: -len(".json")] if name.endswith(".json") else state_path.stem
    return state_path.with_name(f"{stem}.journal.jsonl")


def _normalize_batch_size(value: int, *, total: int) -> int:
    size = int(value)
    if size <= 0:
        return max(1, int(total))
    return max(1, size)


def _normalize_optional_timeout(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _hash_file_list(paths: list[str]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8", "ignore"))
        digest.update(b"\n")
    return digest.hexdigest()


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp_path, path)


def _load_or_init_state(
    *,
    root_path: Path,
    enabled_languages: tuple[str, ...],
    state_path: Path,
    journal_path: Path,
    file_list_sha256: str,
    total_files: int,
    resume: bool,
    batch_size: int,
    timeout_per_file_seconds: float | None,
    retry_timeouts: bool,
    retry_timeout_multiplier: float,
    subprocess_batch: bool,
    subprocess_batch_timeout_seconds: float | None,
) -> dict[str, Any]:
    if resume and state_path.exists():
        state_candidate = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state_candidate, dict):
            raise ValueError("resume state must be a JSON object")
        state: dict[str, Any] = state_candidate
        _validate_state(
            state=state,
            root_path=root_path,
            enabled_languages=enabled_languages,
            file_list_sha256=file_list_sha256,
            total_files=total_files,
        )
        state["resume_active"] = True
        state["settings"] = _settings_payload(
            batch_size=batch_size,
            timeout_per_file_seconds=timeout_per_file_seconds,
            retry_timeouts=retry_timeouts,
            retry_timeout_multiplier=retry_timeout_multiplier,
            subprocess_batch=subprocess_batch,
            subprocess_batch_timeout_seconds=subprocess_batch_timeout_seconds,
        )
        state.setdefault("journal_path", str(journal_path))
        return state

    state = {
        "schema_version": RESUME_STATE_SCHEMA_VERSION,
        "root_dir": str(root_path),
        "languages": list(enabled_languages),
        "file_list_sha256": file_list_sha256,
        "total_files": int(total_files),
        "next_index": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "journal_path": str(journal_path),
        "resume_active": False,
        "settings": _settings_payload(
            batch_size=batch_size,
            timeout_per_file_seconds=timeout_per_file_seconds,
            retry_timeouts=retry_timeouts,
            retry_timeout_multiplier=retry_timeout_multiplier,
            subprocess_batch=subprocess_batch,
            subprocess_batch_timeout_seconds=subprocess_batch_timeout_seconds,
        ),
        "stats": {
            "total_files": int(total_files),
            "processed_files": 0,
            "parsed_files": 0,
            "timed_out_files": 0,
            "failed_files": 0,
            "retried_files": 0,
            "retry_succeeded_files": 0,
        },
        "timed_out_files": [],
        "failed_files": [],
    }
    _atomic_write_json(state_path, state)
    return state


def _settings_payload(
    *,
    batch_size: int,
    timeout_per_file_seconds: float | None,
    retry_timeouts: bool,
    retry_timeout_multiplier: float,
    subprocess_batch: bool,
    subprocess_batch_timeout_seconds: float | None,
) -> dict[str, Any]:
    return {
        "batch_size": int(batch_size),
        "timeout_per_file_seconds": timeout_per_file_seconds,
        "retry_timeouts": bool(retry_timeouts),
        "retry_timeout_multiplier": float(retry_timeout_multiplier),
        "subprocess_batch": bool(subprocess_batch),
        "subprocess_batch_timeout_seconds": subprocess_batch_timeout_seconds,
    }


def _validate_state(
    *,
    state: dict[str, Any],
    root_path: Path,
    enabled_languages: tuple[str, ...],
    file_list_sha256: str,
    total_files: int,
) -> None:
    schema = int(state.get("schema_version") or 0)
    if schema != RESUME_STATE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported resume state schema_version: {schema} (expected {RESUME_STATE_SCHEMA_VERSION})"
        )

    expected_root = str(root_path)
    if str(state.get("root_dir") or "") != expected_root:
        raise ValueError(
            f"Resume state root_dir mismatch: {state.get('root_dir')} (expected {expected_root})"
        )

    expected_languages = list(enabled_languages)
    if list(state.get("languages") or []) != expected_languages:
        raise ValueError(
            f"Resume state languages mismatch: {state.get('languages')} (expected {expected_languages})"
        )

    if str(state.get("file_list_sha256") or "") != str(file_list_sha256):
        raise ValueError("Resume state file list hash mismatch (repo changed)")

    if int(state.get("total_files") or 0) != int(total_files):
        raise ValueError("Resume state total_files mismatch (repo changed)")


def _append_journal_events(*, journal_path: Path, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    with journal_path.open("a", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def _process_batch_in_process(
    *,
    root_path: Path,
    enabled_languages: tuple[str, ...],
    batch: list[str],
    timeout_per_file_seconds: float | None,
    attempt: int = 0,
) -> list[dict[str, Any]]:
    engine = TreeSitterEngine(enabled_languages)
    events: list[dict[str, Any]] = []
    for relative in batch:
        absolute = root_path / Path(relative)
        started = perf_counter()
        try:
            entry = engine.parse_file(absolute, root_path)
        except Exception as exc:
            events.append(
                {
                    "type": "error",
                    "path": relative,
                    "attempt": attempt,
                    "error": str(exc),
                    "elapsed_ms": (perf_counter() - started) * 1000.0,
                }
            )
            continue

        elapsed_ms = (perf_counter() - started) * 1000.0
        if timeout_per_file_seconds is not None and elapsed_ms > timeout_per_file_seconds * 1000.0:
            events.append(
                {
                    "type": "timeout",
                    "path": relative,
                    "attempt": attempt,
                    "elapsed_ms": elapsed_ms,
                }
            )
            continue

        if entry is None:
            events.append(
                {
                    "type": "error",
                    "path": relative,
                    "attempt": attempt,
                    "error": "parse_skipped",
                    "elapsed_ms": elapsed_ms,
                }
            )
            continue

        entry["tier"] = _classify_tier(
            path=str(entry.get("path", relative) or relative),
            language=str(entry.get("language") or ""),
        )
        events.append(
            {
                "type": "file",
                "path": entry.get("path", relative),
                "attempt": attempt,
                "elapsed_ms": elapsed_ms,
                "entry": entry,
            }
        )
    return events


def _process_batch_subprocess(
    *,
    root_path: Path,
    enabled_languages: tuple[str, ...],
    batch: list[str],
    timeout_per_file_seconds: float | None,
    batch_timeout_seconds: float | None,
) -> list[dict[str, Any]]:
    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    queue: Any = ctx.Queue(maxsize=1)
    proc = ctx.Process(
        target=_subprocess_worker,
        kwargs={
            "queue": queue,
            "root_dir": str(root_path),
            "languages": list(enabled_languages),
            "batch": list(batch),
            "timeout_per_file_seconds": timeout_per_file_seconds,
        },
    )
    proc.start()

    proc.join(timeout=batch_timeout_seconds)
    if proc.is_alive():
        try:
            proc.terminate()
        finally:
            proc.join(timeout=1.0)
        elapsed_ms = (
            float(batch_timeout_seconds or 0.0) * 1000.0
            if batch_timeout_seconds is not None
            else 0.0
        )
        return [
            {
                "type": "timeout",
                "path": path,
                "attempt": 0,
                "elapsed_ms": elapsed_ms,
                "reason": "batch_timeout",
            }
            for path in batch
        ]

    if getattr(proc, "exitcode", 0) not in (0, None):
        return [
            {
                "type": "error",
                "path": path,
                "attempt": 0,
                "elapsed_ms": 0.0,
                "error": f"batch_exitcode:{proc.exitcode}",
            }
            for path in batch
        ]

    try:
        payload = queue.get_nowait()
    except Exception:
        payload = None

    if not isinstance(payload, dict):
        return [
            {
                "type": "error",
                "path": path,
                "attempt": 0,
                "elapsed_ms": 0.0,
                "error": "batch_no_payload",
            }
            for path in batch
        ]

    events = payload.get("events")
    if not isinstance(events, list):
        return [
            {
                "type": "error",
                "path": path,
                "attempt": 0,
                "elapsed_ms": 0.0,
                "error": "batch_invalid_payload",
            }
            for path in batch
        ]

    normalized: list[dict[str, Any]] = []
    for event in events:
        if isinstance(event, dict):
            normalized.append(event)
    return normalized


def _subprocess_worker(
    *,
    queue: Any,
    root_dir: str,
    languages: list[str],
    batch: list[str],
    timeout_per_file_seconds: float | None,
) -> None:
    try:
        root_path = Path(root_dir)
        events = _process_batch_in_process(
            root_path=root_path,
            enabled_languages=tuple(languages),
            batch=batch,
            timeout_per_file_seconds=timeout_per_file_seconds,
        )
        queue.put({"events": events})
    except Exception as exc:
        queue.put({"events": [{"type": "error", "path": "", "error": str(exc)}]})


def _resolve_batch_timeout(
    explicit_timeout: float | None,
    *,
    per_file_timeout: float | None,
    batch_count: int,
) -> float | None:
    normalized = _normalize_optional_timeout(explicit_timeout)
    if normalized is not None:
        return normalized
    if per_file_timeout is None:
        return None
    return max(2.0, float(per_file_timeout) * max(1, int(batch_count)) * 3.0)


def _resolve_retry_timeout(
    *,
    timeout_seconds: float | None,
    enabled: bool,
    multiplier: float,
) -> float | None:
    if not enabled or timeout_seconds is None:
        return None
    return max(0.001, float(timeout_seconds) * max(1.0, float(multiplier)))


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _coerce_failed_files(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            path = str(item.get("path") or "")
            error = str(item.get("error") or "")
            if path or error:
                normalized.append({"path": path, "error": error})
    return normalized


def _load_files_from_journal(*, journal_path: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    if not journal_path.exists():
        return files

    with journal_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = str(line or "").strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if str(event.get("type") or "") != "file":
                continue
            entry = event.get("entry")
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                continue
            files[path] = entry
    return files


__all__ = ["IndexingResilienceConfig", "build_index_with_resilience"]
