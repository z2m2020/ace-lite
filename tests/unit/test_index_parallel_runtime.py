from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from ace_lite.index_stage.parallel_runtime import (
    build_disabled_docs_payload,
    build_disabled_worktree_prior,
    get_index_parallel_executor,
    resolve_parallel_future,
)


def test_build_disabled_docs_payload_preserves_default_shape() -> None:
    payload = build_disabled_docs_payload(reason="timeout", elapsed_ms=1.23456)

    assert payload["enabled"] is False
    assert payload["reason"] == "timeout"
    assert payload["backend"] == "disabled"
    assert payload["elapsed_ms"] == 1.235
    assert payload["hints"]["paths"] == []


def test_build_disabled_worktree_prior_preserves_default_shape() -> None:
    payload = build_disabled_worktree_prior(reason="policy_disabled")

    assert payload["enabled"] is False
    assert payload["reason"] == "policy_disabled"
    assert payload["changed_count"] == 0
    assert payload["raw"]["truncated"] is False


def test_resolve_parallel_future_returns_result_without_timeout() -> None:
    future: Future[str] = Future()
    future.set_result("ok")

    value, timed_out, error = resolve_parallel_future(
        future=future,
        timeout_seconds=0.1,
        fallback="fallback",
    )

    assert value == "ok"
    assert timed_out is False
    assert error == ""


def test_resolve_parallel_future_returns_timeout_fallback() -> None:
    future: Future[str] = Future()

    value, timed_out, error = resolve_parallel_future(
        future=future,
        timeout_seconds=0.0,
        fallback={"reason": "timeout"},
    )

    assert value == {"reason": "timeout"}
    assert timed_out is True
    assert error == "timeout"
    assert future.cancelled() is True


def test_get_index_parallel_executor_reuses_singleton() -> None:
    first = get_index_parallel_executor()
    second = get_index_parallel_executor()

    assert isinstance(first, ThreadPoolExecutor)
    assert first is second
