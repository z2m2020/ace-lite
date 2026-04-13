from __future__ import annotations

from io import StringIO

from ace_lite.cli_app.progress import (
    ProgressContext,
    clear_progress,
    echo_done,
    echo_error,
    echo_progress,
    progress_iter,
)


def test_echo_helpers_emit_ascii_status_prefixes() -> None:
    stream = StringIO()

    echo_progress("Loading memory...", stream=stream)
    echo_done("Plan built", stream=stream)
    echo_error("Plan failed", stream=stream)

    text = stream.getvalue()
    assert "-> Loading memory..." in text
    assert "[ok] Plan built" in text
    assert "[error] Plan failed" in text


def test_progress_context_reports_success_with_ascii_output() -> None:
    stream = StringIO()

    with ProgressContext("Building plan", stream=stream) as ctx:
        ctx.stage("Loading memory")

    text = stream.getvalue()
    assert "Building plan" in text
    assert "-> Loading memory..." in text
    assert "[ok] Building plan" in text


def test_progress_context_reports_failure_with_ascii_output() -> None:
    stream = StringIO()

    try:
        with ProgressContext("Building plan", stream=stream) as ctx:
            ctx.stage("Generating source plan")
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    text = stream.getvalue()
    assert "-> Generating source plan..." in text
    assert "[error] Building plan" in text


def test_progress_iter_emits_progress_and_completion() -> None:
    stream = StringIO()

    items = list(progress_iter(["a", "b"], "Indexing {i}/{total}", stream=stream))

    assert items == ["a", "b"]
    text = stream.getvalue()
    assert "-> Indexing 1/2" in text
    assert "-> Indexing 2/2" in text
    assert "[ok] 2 items processed" in text


def test_clear_progress_writes_carriage_return_padding() -> None:
    stream = StringIO()

    clear_progress(stream=stream)

    assert stream.getvalue().startswith("\r")
