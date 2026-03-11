from __future__ import annotations

import logging
import subprocess
import time
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)

_CacheKey = tuple[str, str, str, str, int, int, tuple[str, ...], str]


class LspDiagnosticsBroker:
    def __init__(
        self,
        *,
        commands: dict[str, list[str]] | None = None,
        xref_commands: dict[str, list[str]] | None = None,
        timeout_seconds: float = 2.0,
        cache_ttl_seconds: float = 30.0,
        cache_max_entries: int = 256,
    ) -> None:
        self._commands = commands or {}
        self._xref_commands = xref_commands or {}
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self._cache_max_entries = max(16, int(cache_max_entries))
        self._cache: OrderedDict[_CacheKey, tuple[float, dict[str, Any]]] = OrderedDict()
        self._cache_lock = RLock()

    def collect(
        self,
        *,
        root: str | Path,
        candidate_files: list[dict[str, Any]],
        top_n: int,
    ) -> dict[str, Any]:
        diagnostics: list[dict[str, Any]] = []
        errors: list[str] = []
        cache_hits = 0
        cache_misses = 0

        for candidate in candidate_files[: max(0, top_n)]:
            if not isinstance(candidate, dict):
                continue
            language = str(candidate.get("language", "")).strip().lower()
            relative_path = str(candidate.get("path", "")).strip()
            if not language or not relative_path:
                continue
            command = self._commands.get(language)
            if not command:
                continue

            file_path = Path(root) / relative_path
            if not file_path.exists():
                continue

            cache_key = self._build_cache_key(
                mode="diagnostic",
                root=root,
                language=language,
                relative_path=relative_path,
                file_path=file_path,
                command=command,
                query="",
            )
            cached = self._cache_get(cache_key) if cache_key is not None else None
            if cached is not None:
                cache_hits += 1
                returncode = int(cached.get("returncode", 1) or 1)
                stdout = str(cached.get("stdout") or "")
                stderr = str(cached.get("stderr") or "")
            else:
                cache_misses += 1
                try:
                    proc = subprocess.run(
                        [*command, str(file_path)],
                        cwd=str(root),
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=self._timeout_seconds,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    errors.append(f"{language}:{relative_path}:{exc}")
                    logger.warning(
                        "lsp.collect.error",
                        extra={
                            "language": language,
                            "path": relative_path,
                            "error": str(exc),
                        },
                    )
                    continue

                returncode = int(proc.returncode)
                stdout = str(proc.stdout or "")
                stderr = str(proc.stderr or "")
                if cache_key is not None:
                    self._cache_set(
                        cache_key,
                        {
                            "returncode": returncode,
                            "stdout": stdout,
                            "stderr": stderr,
                        },
                    )

            if returncode == 0:
                continue

            message = stderr.strip() or stdout.strip() or "diagnostic"
            diagnostics.append(
                {
                    "path": relative_path,
                    "language": language,
                    "severity": "error",
                    "message": message,
                }
            )

        return {
            "count": len(diagnostics),
            "diagnostics": diagnostics,
            "errors": errors,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        }

    def collect_xref(
        self,
        *,
        root: str | Path,
        query: str,
        candidate_files: list[dict[str, Any]],
        top_n: int,
        time_budget_ms: int,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        started = perf_counter()
        budget_ms = max(1, int(time_budget_ms))
        budget_exhausted = False
        cache_hits = 0
        cache_misses = 0

        for candidate in candidate_files[: max(0, top_n)]:
            elapsed_ms = (perf_counter() - started) * 1000.0
            if elapsed_ms >= budget_ms:
                budget_exhausted = True
                break

            if not isinstance(candidate, dict):
                continue
            language = str(candidate.get("language", "")).strip().lower()
            relative_path = str(candidate.get("path", "")).strip()
            if not language or not relative_path:
                continue

            command = self._xref_commands.get(language) or self._commands.get(language)
            if not command:
                continue

            file_path = Path(root) / relative_path
            if not file_path.exists():
                continue

            cmd = self._build_xref_command(
                command=command, file_path=str(file_path), query=query
            )
            if not cmd:
                continue

            cache_key = self._build_cache_key(
                mode="xref",
                root=root,
                language=language,
                relative_path=relative_path,
                file_path=file_path,
                command=cmd,
                query=query,
            )
            cached = self._cache_get(cache_key) if cache_key is not None else None
            if cached is not None:
                cache_hits += 1
                returncode = int(cached.get("returncode", 1) or 1)
                stdout = str(cached.get("stdout") or "")
                stderr = str(cached.get("stderr") or "")
            else:
                cache_misses += 1
                try:
                    proc = subprocess.run(
                        cmd,
                        cwd=str(root),
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=self._timeout_seconds,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    errors.append(f"xref:{language}:{relative_path}:{exc}")
                    logger.warning(
                        "lsp.xref.error",
                        extra={
                            "language": language,
                            "path": relative_path,
                            "error": str(exc),
                        },
                    )
                    continue

                returncode = int(proc.returncode)
                stdout = str(proc.stdout or "")
                stderr = str(proc.stderr or "")
                if cache_key is not None:
                    self._cache_set(
                        cache_key,
                        {
                            "returncode": returncode,
                            "stdout": stdout,
                            "stderr": stderr,
                        },
                    )

            if returncode not in {0, 1}:
                errors.append(f"xref:{language}:{relative_path}:returncode={returncode}")
                logger.warning(
                    "lsp.xref.returncode",
                    extra={
                        "language": language,
                        "path": relative_path,
                        "returncode": returncode,
                    },
                )
                continue

            message = stdout.strip() or stderr.strip()
            if not message:
                continue
            results.append(
                {
                    "path": relative_path,
                    "language": language,
                    "query": query,
                    "message": message[:1500],
                }
            )

        elapsed_ms = (perf_counter() - started) * 1000.0
        return {
            "count": len(results),
            "results": results,
            "errors": errors,
            "budget_exhausted": budget_exhausted,
            "elapsed_ms": round(elapsed_ms, 3),
            "time_budget_ms": budget_ms,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        }

    def _build_cache_key(
        self,
        *,
        mode: str,
        root: str | Path,
        language: str,
        relative_path: str,
        file_path: Path,
        command: list[str],
        query: str,
    ) -> _CacheKey | None:
        if self._cache_ttl_seconds <= 0.0:
            return None
        try:
            stat_result = file_path.stat()
        except OSError:
            return None
        return (
            str(mode or "").strip().lower(),
            str(Path(root).resolve()),
            str(language or "").strip().lower(),
            str(relative_path or "").strip(),
            int(stat_result.st_mtime_ns),
            int(stat_result.st_size),
            tuple(str(item) for item in command),
            str(query or "").strip(),
        )

    def _cache_get(self, key: _CacheKey) -> dict[str, Any] | None:
        if self._cache_ttl_seconds <= 0.0:
            return None
        now = time.time()
        with self._cache_lock:
            row = self._cache.get(key)
            if row is None:
                return None
            expires_at, payload = row
            if expires_at <= now:
                self._cache.pop(key, None)
                return None
            self._cache.move_to_end(key)
            return dict(payload)

    def _cache_set(self, key: _CacheKey, payload: dict[str, Any]) -> None:
        if self._cache_ttl_seconds <= 0.0:
            return
        expires_at = time.time() + self._cache_ttl_seconds
        with self._cache_lock:
            self._cache[key] = (expires_at, dict(payload))
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_max_entries:
                self._cache.popitem(last=False)

    @staticmethod
    def _build_xref_command(*, command: list[str], file_path: str, query: str) -> list[str]:
        if not command:
            return []

        rendered: list[str] = []
        has_file_placeholder = False
        has_query_placeholder = False
        for token in command:
            value = str(token)
            if "{file}" in value:
                has_file_placeholder = True
                value = value.replace("{file}", file_path)
            if "{query}" in value:
                has_query_placeholder = True
                value = value.replace("{query}", query)
            rendered.append(value)

        if not has_file_placeholder:
            rendered.append(file_path)
        if not has_query_placeholder and query.strip():
            rendered.append(query.strip())
        return rendered


__all__ = ["LspDiagnosticsBroker"]
