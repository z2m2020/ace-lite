"""Config hot-reload polling primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import monotonic


@dataclass(frozen=True, slots=True)
class ConfigChange:
    path: str
    exists: bool
    mtime_ns: int
    size_bytes: int
    sha256: str
    generation: int


@dataclass(frozen=True, slots=True)
class _Fingerprint:
    exists: bool
    mtime_ns: int
    size_bytes: int
    sha256: str


class ConfigWatcher:
    """Polling watcher with debounce and content fingerprinting.

    The watcher is dependency-free and deterministic (pluggable monotonic clock),
    making it suitable for both local runtime and tests.
    """

    def __init__(
        self,
        *,
        path: str | Path,
        debounce_ms: int = 300,
        monotonic_fn: Callable[[], float] | None = None,
    ) -> None:
        self._path = Path(path).expanduser().resolve()
        self._debounce_seconds = max(0.0, float(debounce_ms) / 1000.0)
        self._monotonic = monotonic_fn or monotonic
        self._started = False
        self._generation = 0
        self._last_emitted: _Fingerprint | None = None
        self._pending: tuple[_Fingerprint, float] | None = None

    @property
    def path(self) -> Path:
        return self._path

    def start(self) -> None:
        """Initialize baseline fingerprint."""
        self._last_emitted = self._read_fingerprint()
        self._pending = None
        self._started = True

    def poll(self) -> ConfigChange | None:
        """Check for debounced config changes."""
        if not self._started:
            self.start()
            return None

        now = float(self._monotonic())
        current = self._read_fingerprint()
        if self._last_emitted is not None and current == self._last_emitted:
            self._pending = None
            return None

        pending = self._pending
        if pending is None or pending[0] != current:
            self._pending = (current, now)
            if self._debounce_seconds <= 0.0:
                return self._emit(current)
            return None

        first_seen_at = float(pending[1])
        if now - first_seen_at < self._debounce_seconds:
            return None
        return self._emit(current)

    def _emit(self, fingerprint: _Fingerprint) -> ConfigChange:
        self._generation += 1
        self._last_emitted = fingerprint
        self._pending = None
        return ConfigChange(
            path=str(self._path),
            exists=bool(fingerprint.exists),
            mtime_ns=int(fingerprint.mtime_ns),
            size_bytes=int(fingerprint.size_bytes),
            sha256=str(fingerprint.sha256),
            generation=int(self._generation),
        )

    def _read_fingerprint(self) -> _Fingerprint:
        path = self._path
        try:
            stat = path.stat()
        except OSError:
            return _Fingerprint(exists=False, mtime_ns=0, size_bytes=0, sha256="")

        if not path.is_file():
            return _Fingerprint(
                exists=False,
                mtime_ns=int(getattr(stat, "st_mtime_ns", 0)),
                size_bytes=0,
                sha256="",
            )

        try:
            data = path.read_bytes()
        except OSError:
            data = b""

        digest = sha256(data).hexdigest()
        return _Fingerprint(
            exists=True,
            mtime_ns=int(getattr(stat, "st_mtime_ns", 0)),
            size_bytes=int(getattr(stat, "st_size", len(data))),
            sha256=digest,
        )
