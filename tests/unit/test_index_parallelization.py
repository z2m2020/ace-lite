from __future__ import annotations

from concurrent.futures import Future

from ace_lite.pipeline.stages.index import _resolve_parallel_future


def test_resolve_parallel_future_returns_result_when_ready() -> None:
    future: Future[str] = Future()
    future.set_result("ok")

    value, timed_out, error = _resolve_parallel_future(
        future=future,
        timeout_seconds=0.0,
        fallback="fallback",
    )

    assert value == "ok"
    assert timed_out is False
    assert error == ""


def test_resolve_parallel_future_returns_fallback_on_timeout() -> None:
    future: Future[str] = Future()

    value, timed_out, error = _resolve_parallel_future(
        future=future,
        timeout_seconds=0.0,
        fallback="fallback",
    )

    assert value == "fallback"
    assert timed_out is True
    assert error == "timeout"
    assert future.cancelled() is True


def test_resolve_parallel_future_returns_fallback_on_error() -> None:
    future: Future[str] = Future()
    future.set_exception(RuntimeError("boom"))

    value, timed_out, error = _resolve_parallel_future(
        future=future,
        timeout_seconds=0.0,
        fallback="fallback",
    )

    assert value == "fallback"
    assert timed_out is False
    assert error == "RuntimeError"

