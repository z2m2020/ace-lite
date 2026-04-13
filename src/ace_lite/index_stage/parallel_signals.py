"""Docs/worktree signal collection helpers for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import Any

CollectDocsFn = Callable[..., dict[str, Any]]
CollectWorktreeFn = Callable[..., dict[str, Any]]
DisabledDocsPayloadFn = Callable[..., dict[str, Any]]
DisabledWorktreePriorFn = Callable[..., dict[str, Any]]
GetExecutorFn = Callable[[], ThreadPoolExecutor]
ResolveFutureFn = Callable[..., tuple[Any, bool, str]]


@dataclass(slots=True)
class ParallelSignalsResult:
    docs_payload: dict[str, Any]
    worktree_prior: dict[str, Any]
    parallel_payload: dict[str, Any]
    docs_elapsed_ms: float
    worktree_elapsed_ms: float


def collect_parallel_signals(
    *,
    root: str,
    query: str,
    terms: list[str],
    files_map: dict[str, Any],
    top_k_files: int,
    docs_policy_enabled: bool,
    worktree_prior_enabled: bool,
    cochange_enabled: bool,
    docs_intent_weight: float,
    parallel_requested: bool,
    parallel_time_budget_ms: int,
    collect_docs: CollectDocsFn,
    collect_worktree: CollectWorktreeFn,
    disabled_docs_payload: DisabledDocsPayloadFn,
    disabled_worktree_prior: DisabledWorktreePriorFn,
    get_executor: GetExecutorFn,
    resolve_future: ResolveFutureFn,
) -> ParallelSignalsResult:
    """Collect docs/worktree signals with optional parallel timeout handling."""

    parallel_payload: dict[str, Any] = {
        "requested": bool(parallel_requested),
        "enabled": False,
        "time_budget_ms": int(parallel_time_budget_ms),
        "docs": {
            "started": False,
            "timed_out": False,
            "error": "",
            "elapsed_ms": 0.0,
        },
        "worktree": {
            "started": False,
            "timed_out": False,
            "error": "",
            "elapsed_ms": 0.0,
        },
    }

    def _run_docs_task() -> dict[str, Any]:
        started = perf_counter()
        try:
            payload = collect_docs(
                root=root,
                query=query,
                terms=terms,
                enabled=docs_policy_enabled,
                intent_weight=float(docs_intent_weight),
                max_sections=max(4, int(top_k_files)),
            )
            return {
                "ok": True,
                "payload": payload,
                "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                "error": "",
            }
        except Exception as exc:
            elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
            return {
                "ok": False,
                "payload": disabled_docs_payload(
                    reason=f"error:{exc.__class__.__name__}",
                    elapsed_ms=elapsed_ms,
                ),
                "elapsed_ms": elapsed_ms,
                "error": exc.__class__.__name__,
            }

    def _run_worktree_task() -> dict[str, Any]:
        started = perf_counter()
        try:
            if not bool(cochange_enabled):
                payload = disabled_worktree_prior(reason="cochange_disabled")
            else:
                payload = collect_worktree(
                    root=root,
                    files_map=files_map,
                    max_seed_paths=max(4, int(top_k_files) * 2),
                )
            return {
                "ok": True,
                "payload": payload,
                "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                "error": "",
            }
        except Exception as exc:
            elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
            return {
                "ok": False,
                "payload": disabled_worktree_prior(
                    reason=f"error:{exc.__class__.__name__}",
                ),
                "elapsed_ms": elapsed_ms,
                "error": exc.__class__.__name__,
            }

    docs_future: Future[Any] | None = None
    worktree_future: Future[Any] | None = None
    parallel_enabled_effective = False
    if bool(parallel_requested) and (bool(docs_policy_enabled) or bool(worktree_prior_enabled)):
        executor = get_executor()
        if docs_policy_enabled:
            docs_future = executor.submit(_run_docs_task)
            parallel_payload["docs"]["started"] = True
            parallel_enabled_effective = True
        if worktree_prior_enabled:
            worktree_future = executor.submit(_run_worktree_task)
            parallel_payload["worktree"]["started"] = True
            parallel_enabled_effective = True

    parallel_payload["enabled"] = bool(parallel_enabled_effective)
    if parallel_enabled_effective:
        deadline = None
        if int(parallel_time_budget_ms) > 0:
            deadline = perf_counter() + (float(parallel_time_budget_ms) / 1000.0)

        def _remaining_timeout_seconds() -> float | None:
            if deadline is None:
                return None
            return max(0.0, float(deadline - perf_counter()))

        if docs_future is None:
            docs_payload = disabled_docs_payload(reason="policy_disabled", elapsed_ms=0.0)
            docs_elapsed_ms = 0.0
        else:
            docs_fallback = disabled_docs_payload(reason="timeout", elapsed_ms=0.0)
            docs_result_raw, docs_timed_out, docs_error = resolve_future(
                future=docs_future,
                timeout_seconds=_remaining_timeout_seconds(),
                fallback={
                    "ok": False,
                    "payload": docs_fallback,
                    "elapsed_ms": 0.0,
                    "error": "missing",
                },
            )
            docs_result = (
                docs_result_raw
                if isinstance(docs_result_raw, dict)
                else {"payload": docs_fallback, "elapsed_ms": 0.0, "error": "invalid"}
            )
            docs_payload_value = docs_result.get("payload", docs_fallback)
            docs_payload = (
                docs_payload_value if isinstance(docs_payload_value, dict) else docs_fallback
            )
            docs_elapsed_value = docs_result.get("elapsed_ms", 0.0)
            docs_elapsed_ms = (
                float(docs_elapsed_value)
                if isinstance(docs_elapsed_value, (int, float, str))
                else 0.0
            )
            parallel_payload["docs"]["timed_out"] = bool(docs_timed_out)
            parallel_payload["docs"]["error"] = str(
                docs_error or docs_result.get("error", "") or ""
            )
            parallel_payload["docs"]["elapsed_ms"] = round(docs_elapsed_ms, 3)

        if worktree_future is None:
            worktree_prior = disabled_worktree_prior(reason="cochange_disabled")
            worktree_elapsed_ms = 0.0
        else:
            worktree_fallback = disabled_worktree_prior(reason="timeout")
            worktree_result_raw, worktree_timed_out, worktree_error = resolve_future(
                future=worktree_future,
                timeout_seconds=_remaining_timeout_seconds(),
                fallback={
                    "ok": False,
                    "payload": worktree_fallback,
                    "elapsed_ms": 0.0,
                    "error": "missing",
                },
            )
            worktree_result = (
                worktree_result_raw
                if isinstance(worktree_result_raw, dict)
                else {"payload": worktree_fallback, "elapsed_ms": 0.0, "error": "invalid"}
            )
            worktree_payload_value = worktree_result.get("payload", worktree_fallback)
            worktree_prior = (
                worktree_payload_value
                if isinstance(worktree_payload_value, dict)
                else worktree_fallback
            )
            worktree_elapsed_value = worktree_result.get("elapsed_ms", 0.0)
            worktree_elapsed_ms = (
                float(worktree_elapsed_value)
                if isinstance(worktree_elapsed_value, (int, float, str))
                else 0.0
            )
            parallel_payload["worktree"]["timed_out"] = bool(worktree_timed_out)
            parallel_payload["worktree"]["error"] = str(
                worktree_error or worktree_result.get("error", "") or ""
            )
            parallel_payload["worktree"]["elapsed_ms"] = round(worktree_elapsed_ms, 3)
    else:
        started = perf_counter()
        docs_payload = collect_docs(
            root=root,
            query=query,
            terms=terms,
            enabled=docs_policy_enabled,
            intent_weight=float(docs_intent_weight),
            max_sections=max(4, int(top_k_files)),
        )
        docs_elapsed_ms = round((perf_counter() - started) * 1000.0, 3)

        started = perf_counter()
        if worktree_prior_enabled:
            worktree_prior = collect_worktree(
                root=root,
                files_map=files_map,
                max_seed_paths=max(4, int(top_k_files) * 2),
            )
        else:
            worktree_prior = disabled_worktree_prior(reason="cochange_disabled")
        worktree_elapsed_ms = round((perf_counter() - started) * 1000.0, 3)

    return ParallelSignalsResult(
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        parallel_payload=parallel_payload,
        docs_elapsed_ms=float(docs_elapsed_ms),
        worktree_elapsed_ms=float(worktree_elapsed_ms),
    )


__all__ = ["ParallelSignalsResult", "collect_parallel_signals"]
