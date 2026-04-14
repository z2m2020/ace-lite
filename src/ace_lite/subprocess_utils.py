from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


def _resolve_windows_executable(name: str) -> str | None:
    resolved = shutil.which(str(name or "").strip())
    if not resolved:
        return None
    return str(Path(resolved))


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    try:
        if sys.platform == "win32":
            taskkill_executable = _resolve_windows_executable("taskkill")
            if not taskkill_executable:
                proc.kill()
                return
            subprocess.run(
                [taskkill_executable, "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=2.0,
            )
            return

        try:
            import signal

            os.killpg(proc.pid, signal.SIGKILL)
            return
        except Exception:
            proc.kill()
            return
    except Exception:
        try:
            proc.kill()
        except Exception:
            return


def run_capture_output(
    args: Sequence[str],
    *,
    cwd: str | Path | None,
    timeout_seconds: float,
    env_overrides: Mapping[str, str] | None = None,
) -> tuple[int, str, str, bool]:
    """Run a subprocess and capture stdout/stderr with a hard timeout.

    This helper is designed to be robust in non-interactive environments where
    child processes (like git) may hang, spawn grandchildren, or block on stdin.

    Returns:
        (returncode, stdout, stderr, timed_out)
    """

    timeout = max(0.1, float(timeout_seconds))
    run_env = dict(os.environ)
    if env_overrides:
        for key, value in env_overrides.items():
            run_env[str(key)] = str(value)

    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                list(args),
                cwd=str(cwd) if cwd is not None else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=run_env,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        else:
            proc = subprocess.Popen(
                list(args),
                cwd=str(cwd) if cwd is not None else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=run_env,
                start_new_session=True,
            )
    except OSError as exc:
        return 1, "", str(exc), False

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return int(proc.returncode or 0), str(stdout or ""), str(stderr or ""), False
    except subprocess.TimeoutExpired:
        _terminate_process_tree(proc)
        stdout = ""
        stderr = ""
        try:
            stdout, stderr = proc.communicate(timeout=0.2)
        except Exception:
            stdout = ""
            stderr = ""
        return int(proc.returncode or 1), str(stdout or ""), str(stderr or ""), True
