"""Progress feedback module for CLI commands.

Provides simple progress indicators for long-running operations.

PRD-91: Plan/index progress display.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from typing import Any, Literal


class SpinnerProgress:
    """Simple spinner progress indicator for CLI.

    Usage:
        with SpinnerProgress("Working..."):
            do_long_operation()
    """

    SPINNER_CHARS = ("-", "\\", "|", "/")
    DEFAULT_DELAY = 0.1

    def __init__(
        self,
        message: str = "Working...",
        delay: float = DEFAULT_DELAY,
        stream: Any = None,
    ) -> None:
        """Initialize spinner.

        Args:
            message: Message to display alongside spinner.
            delay: Delay between spinner updates in seconds.
            stream: Output stream. Defaults to stderr.
        """
        self.message = message
        self.delay = delay
        self.stream = stream or sys.stderr
        self._running = False
        self._index = 0

    def __enter__(self) -> SpinnerProgress:
        """Start the spinner."""
        self._running = True
        return self

    def __exit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> Literal[False]:
        """Stop the spinner."""
        self._running = False
        self.stream.write("\r" + " " * (len(self.message) + 5) + "\r")
        self.stream.flush()
        return False

    def spin(self) -> None:
        """Update spinner one step."""
        if self._running:
            char = self.SPINNER_CHARS[self._index % len(self.SPINNER_CHARS)]
            self.stream.write(f"\r{char} {self.message}")
            self.stream.flush()
            self._index += 1
            time.sleep(self.delay)


class ProgressContext:
    """Context manager for staged progress tracking."""

    def __init__(self, title: str, verbose: bool = True, stream: Any = None) -> None:
        """Initialize progress context.

        Args:
            title: Overall task title.
            verbose: Whether to show progress output.
            stream: Output stream. Defaults to stderr.
        """
        self.title = title
        self.verbose = verbose
        self.stream = stream or sys.stderr
        self.current_stage: str | None = None
        self._start_time: float | None = None

    def __enter__(self) -> ProgressContext:
        """Start progress tracking."""
        self._start_time = time.time()
        if self.verbose:
            self.stream.write(f"\n{self.title}\n")
            self.stream.flush()
        return self

    def __exit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> Literal[False]:
        """Finish progress tracking."""
        if self.verbose:
            elapsed = time.time() - (self._start_time or 0)
            if exc_type is None:
                self.stream.write(f"\r[ok] {self.title} (completed in {elapsed:.1f}s)\n")
            else:
                self.stream.write(f"\r[error] {self.title} (failed after {elapsed:.1f}s)\n")
            self.stream.flush()
        return False

    def stage(self, message: str) -> None:
        """Mark entering a new stage."""
        self.current_stage = message
        if self.verbose:
            self.stream.write(f"\r  -> {message}...")
            self.stream.flush()


def echo_progress(message: str, stream: Any = None) -> None:
    """Write a progress update to stderr."""
    target = stream or sys.stderr
    target.write(f"\r  -> {message}")
    target.flush()


def clear_progress(stream: Any = None) -> None:
    """Clear the current progress line."""
    target = stream or sys.stderr
    target.write("\r" + " " * 80 + "\r")
    target.flush()


def echo_done(message: str | None = None, stream: Any = None) -> None:
    """Write a completion message."""
    target = stream or sys.stderr
    msg = message or "Done"
    target.write(f"\r[ok] {msg}\n")
    target.flush()


def echo_error(message: str, stream: Any = None) -> None:
    """Write an error message."""
    target = stream or sys.stderr
    target.write(f"\r[error] {message}\n")
    target.flush()


def progress_iter(
    items: list[Any],
    message: str = "Processing",
    stream: Any = None,
) -> Generator[Any, None, None]:
    """Yield items while emitting simple progress text."""
    total = len(items)
    target = stream or sys.stderr

    for i, item in enumerate(items, 1):
        target.write(f"\r  -> {message.format(i=i, total=total)}")
        target.flush()
        yield item

    clear_progress(target)
    echo_done(f"{total} items processed", target)


__all__ = [
    "ProgressContext",
    "SpinnerProgress",
    "clear_progress",
    "echo_done",
    "echo_error",
    "echo_progress",
    "progress_iter",
]
