from __future__ import annotations

import sys
from pathlib import Path

from ace_lite import subprocess_utils


def test_run_capture_output_success_and_env_override(tmp_path: Path) -> None:
    code = (
        "import os,sys;"
        "print(os.environ.get('ACE_LITE_TEST_ENV','missing'));"
        "print('err-line', file=sys.stderr)"
    )

    rc, stdout, stderr, timed_out = subprocess_utils.run_capture_output(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        timeout_seconds=2.0,
        env_overrides={"ACE_LITE_TEST_ENV": "ok"},
    )

    assert rc == 0
    assert timed_out is False
    assert "ok" in stdout
    assert "err-line" in stderr


def test_run_capture_output_handles_missing_executable(tmp_path: Path) -> None:
    rc, stdout, stderr, timed_out = subprocess_utils.run_capture_output(
        ["__ace_lite_missing_binary__"],
        cwd=tmp_path,
        timeout_seconds=1.0,
    )

    assert rc == 1
    assert stdout == ""
    assert timed_out is False
    assert stderr


def test_run_capture_output_timeout_returns_timed_out(tmp_path: Path) -> None:
    rc, stdout, stderr, timed_out = subprocess_utils.run_capture_output(
        [sys.executable, "-c", "import time; time.sleep(2.0)"],
        cwd=tmp_path,
        timeout_seconds=0.1,
    )

    assert timed_out is True
    assert isinstance(rc, int)
    assert isinstance(stdout, str)
    assert isinstance(stderr, str)


def test_terminate_process_tree_windows_uses_taskkill(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class Proc:
        pid = 42

        def kill(self) -> None:
            observed["killed"] = True

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return None

    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.subprocess, "run", fake_run)

    subprocess_utils._terminate_process_tree(Proc())  # type: ignore[arg-type]

    assert observed["args"] == ["taskkill", "/F", "/T", "/PID", "42"]
    assert "killed" not in observed


def test_terminate_process_tree_non_windows_falls_back_to_proc_kill(monkeypatch) -> None:
    observed = {"kill_calls": 0}

    class Proc:
        pid = 99

        def kill(self) -> None:
            observed["kill_calls"] += 1

    def fake_killpg(pid: int, sig: int) -> None:
        raise RuntimeError("no process group")

    monkeypatch.setattr(subprocess_utils.sys, "platform", "linux")
    monkeypatch.setattr(subprocess_utils.os, "killpg", fake_killpg, raising=False)

    subprocess_utils._terminate_process_tree(Proc())  # type: ignore[arg-type]

    assert observed["kill_calls"] == 1


def test_run_capture_output_sets_windows_creationflags(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeProc:
        returncode = 0

        def communicate(self, timeout: float):
            observed["timeout"] = timeout
            return "ok", ""

    def fake_popen(args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(
        subprocess_utils.subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        512,
        raising=False,
    )
    monkeypatch.setattr(subprocess_utils.subprocess, "Popen", fake_popen)

    rc, stdout, stderr, timed_out = subprocess_utils.run_capture_output(
        [sys.executable, "-c", "print('ok')"],
        cwd=None,
        timeout_seconds=1.0,
    )

    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["creationflags"] == 512
    assert rc == 0
    assert stdout == "ok"
    assert stderr == ""
    assert timed_out is False


def test_run_capture_output_sets_non_windows_start_new_session(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeProc:
        returncode = 0

        def communicate(self, timeout: float):
            observed["timeout"] = timeout
            return "out", "err"

    def fake_popen(args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(subprocess_utils.sys, "platform", "linux")
    monkeypatch.setattr(subprocess_utils.subprocess, "Popen", fake_popen)

    rc, stdout, stderr, timed_out = subprocess_utils.run_capture_output(
        [sys.executable, "-c", "print('x')"],
        cwd=None,
        timeout_seconds=1.0,
    )

    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["start_new_session"] is True
    assert rc == 0
    assert stdout == "out"
    assert stderr == "err"
    assert timed_out is False


def test_terminate_process_tree_swallow_exceptions(monkeypatch) -> None:
    class Proc:
        pid = 123

        def kill(self) -> None:
            raise RuntimeError("kill failed")

    def fake_run(args, **kwargs):
        raise OSError("taskkill missing")

    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.subprocess, "run", fake_run)

    # No exception should leak out.
    subprocess_utils._terminate_process_tree(Proc())  # type: ignore[arg-type]
