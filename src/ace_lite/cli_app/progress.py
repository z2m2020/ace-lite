"""Progress feedback module for CLI commands.

Provides simple progress indicators for long-running operations.

PRD-91: Plan/Index进度显示
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator


class SpinnerProgress:
    """Simple spinner progress indicator for CLI.

    Usage:
        with SpinnerProgress("Working..."):
            do_long_operation()
    """

    SPINNER_CHARS = ("-", "\\", "|", "/")
    DEFAULT_DELAY = 0.1

    def __init__(self, message: str = "Working...", delay: float = DEFAULT_DELAY, stream=None):
        """Initialize spinner.

        Args:
            message: Message to display alongside spinner
            delay: Delay between spinner updates (seconds)
            stream: Output stream (default: stderr)
        """
        self.message = message
        self.delay = delay
        self.stream = stream or sys.stderr
        self._running = False
        self._index = 0

    def __enter__(self):
        """Start the spinner."""
        self._running = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the spinner."""
        self._running = False
        # Clear the line
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
    """Context manager for staged progress tracking.

    Usage:
        with ProgressContext("Building plan") as ctx:
            ctx.stage("Loading memory...")
            load_memory()
            ctx.stage("Building index...")
            build_index()
            ctx.stage("Generating plan...")
            generate_plan()
    """

    def __init__(self, title: str, verbose: bool = True, stream=None):
        """Initialize progress context.

        Args:
            title: Overall task title
            verbose: Whether to show progress output
            stream: Output stream (default: stderr)
        """
        self.title = title
        self.verbose = verbose
        self.stream = stream or sys.stderr
        self.current_stage: str | None = None
        self._start_time: float | None = None

    def __enter__(self):
        """Start progress tracking."""
        self._start_time = time.time()
        if self.verbose:
            self.stream.write(f"\n{self.title}\n")
            self.stream.flush()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finish progress tracking."""
        if self.verbose:
            elapsed = time.time() - (self._start_time or 0)
            if exc_type is None:
                self.stream.write(f"\r✓ {self.title} (completed in {elapsed:.1f}s)\n")
            else:
                self.stream.write(f"\r✗ {self.title} (failed after {elapsed:.1f}s)\n")
            self.stream.flush()
        return False

    def stage(self, message: str) -> None:
        """Mark entering a new stage.

        Args:
            message: Stage description
        """
        self.current_stage = message
        if self.verbose:
            self.stream.write(f"\r  → {message}...")
            self.stream.flush()


def echo_progress(message: str, stream=None) -> None:
    """Simple progress echo to stderr.

    Args:
        message: Progress message
        stream: Output stream (default: stderr)
    """
    target = stream or sys.stderr
    target.write(f"\r  → {message}")
    target.flush()


def clear_progress(stream=None) -> None:
    """Clear the current progress line.

    Args:
        stream: Output stream (default: stderr)
    """
    target = stream or sys.stderr
    target.write("\r" + " " * 80 + "\r")
    target.flush()


def echo_done(message: str | None = None, stream=None) -> None:
    """Echo a completion message.

    Args:
        message: Optional completion message
        stream: Output stream (default: stderr)
    """
    target = stream or sys.stderr
    msg = message or "Done"
    target.write(f"\r✓ {msg}\n")
    target.flush()


def echo_error(message: str, stream=None) -> None:
    """Echo an error message.

    Args:
        message: Error message
        stream: Output stream (default: stderr)
    """
    target = stream or sys.stderr
    target.write(f"\r✗ {message}\n")
    target.flush()


def progress_iter(items: list, message: str = "Processing", stream=None) -> Generator:
    """Yield items with progress indication.

    Args:
        items: Items to iterate over
        message: Progress message template (use {i} and {total})
        stream: Output stream (default: stderr)

    Yields:
        Items from the input list

    Usage:
        for item in progress_iter(files, "Indexing {i}/{total}"):
            process(item)
    """
    total = len(items)
    target = stream or sys.stderr

    for i, item in enumerate(items, 1):
        target.write(f"\r  → {message.format(i=i, total=total)}")
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
