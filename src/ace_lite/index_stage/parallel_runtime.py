"""Parallel signal runtime helpers for the index stage."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Lock
from typing import Any

_INDEX_PARALLEL_EXECUTOR: ThreadPoolExecutor | None = None
_INDEX_PARALLEL_EXECUTOR_LOCK = Lock()


def build_disabled_docs_payload(*, reason: str, elapsed_ms: float) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "backend": "disabled",
        "backend_fallback_reason": "",
        "cache_hit": False,
        "cache_layer": "none",
        "cache_store_written": False,
        "cache_path": "",
        "docs_fingerprint": "",
        "section_pool_size": 0,
        "section_count": 0,
        "query_token_count": 0,
        "evidence": [],
        "hints": {
            "paths": [],
            "modules": [],
            "symbols": [],
            "path_scores": [],
            "module_scores": [],
            "symbol_scores": [],
        },
        "elapsed_ms": round(float(elapsed_ms), 3),
    }


def build_disabled_worktree_prior(*, reason: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "changed_count": 0,
        "changed_paths": [],
        "seed_paths": [],
        "reverse_added_count": 0,
        "state_hash": "",
        "raw": {
            "enabled": False,
            "reason": str(reason),
            "changed_count": 0,
            "entries": [],
            "truncated": False,
            "error": "",
        },
    }


def resolve_parallel_future(
    *,
    future: Future[Any] | None,
    timeout_seconds: float | None,
    fallback: Any,
) -> tuple[Any, bool, str]:
    if future is None:
        return fallback, False, ""

    try:
        if timeout_seconds is None:
            return future.result(), False, ""
        return future.result(timeout=float(timeout_seconds)), False, ""
    except FuturesTimeoutError:
        future.cancel()
        return fallback, True, "timeout"
    except Exception as exc:  # pragma: no cover - defensive
        return fallback, False, exc.__class__.__name__


def get_index_parallel_executor() -> ThreadPoolExecutor:
    global _INDEX_PARALLEL_EXECUTOR
    with _INDEX_PARALLEL_EXECUTOR_LOCK:
        if _INDEX_PARALLEL_EXECUTOR is None:
            _INDEX_PARALLEL_EXECUTOR = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="ace-lite-index-parallel",
            )
        return _INDEX_PARALLEL_EXECUTOR


__all__ = [
    "build_disabled_docs_payload",
    "build_disabled_worktree_prior",
    "get_index_parallel_executor",
    "resolve_parallel_future",
]
