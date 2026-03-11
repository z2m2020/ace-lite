from __future__ import annotations

from pathlib import Path

from ace_lite.runtime.hot_reload import ConfigWatcher


class _FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += float(seconds)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_config_watcher_emits_debounced_change(tmp_path: Path) -> None:
    path = tmp_path / ".ace-lite.yml"
    _write(path, "plan:\n  top_k_files: 8\n")

    clock = _FakeClock()
    watcher = ConfigWatcher(path=path, debounce_ms=200, monotonic_fn=clock.now)

    assert watcher.poll() is None

    _write(path, "plan:\n  top_k_files: 12\n")
    assert watcher.poll() is None
    clock.advance(0.1)
    assert watcher.poll() is None
    clock.advance(0.2)
    change = watcher.poll()
    assert change is not None
    assert change.exists is True
    assert change.generation == 1
    assert change.size_bytes > 0
    assert change.sha256


def test_config_watcher_detects_file_appearance(tmp_path: Path) -> None:
    path = tmp_path / ".ace-lite.yml"
    clock = _FakeClock()
    watcher = ConfigWatcher(path=path, debounce_ms=0, monotonic_fn=clock.now)

    assert watcher.poll() is None
    _write(path, "runtime:\n  scheduler:\n    enabled: true\n")
    change = watcher.poll()
    assert change is not None
    assert change.exists is True
    assert change.generation == 1
