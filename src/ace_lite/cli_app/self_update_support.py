from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ace_lite.version import get_update_status, get_version_info


def _format_command(parts: list[str]) -> str:
    rendered: list[str] = []
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        if any(char.isspace() for char in text) or '"' in text:
            escaped = text.replace('"', '\\"')
            rendered.append(f'"{escaped}"')
            continue
        rendered.append(text)
    return " ".join(rendered)


def _run_command(command: list[str], *, cwd: Path | None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "argv": list(command),
        "display": _format_command(command),
        "cwd": str(cwd) if cwd is not None else "",
        "exit_code": int(completed.returncode),
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _should_defer_self_update() -> bool:
    return sys.platform.startswith("win")


def _launch_detached_windows_update(
    *,
    python_executable: str,
    commands: list[dict[str, Any]],
    parent_pid: int | None = None,
) -> dict[str, Any]:
    resolved_parent_pid = int(parent_pid if parent_pid is not None else os.getpid())
    log_path = (
        Path(tempfile.gettempdir()).resolve()
        / f"ace-lite-self-update-{int(time.time())}-{resolved_parent_pid}.log"
    )
    payload = {
        "parent_pid": resolved_parent_pid,
        "commands": commands,
        "log_path": str(log_path),
    }
    child_code = (
        "import json, os, subprocess, sys, time\n"
        "payload = json.loads(sys.argv[1])\n"
        "parent_pid = int(payload.get('parent_pid', 0) or 0)\n"
        "commands = list(payload.get('commands', []))\n"
        "log_path = payload.get('log_path', '')\n"
        "def _parent_alive(pid):\n"
        "    if pid <= 0:\n"
        "        return False\n"
        "    try:\n"
        "        os.kill(pid, 0)\n"
        "    except OSError:\n"
        "        return False\n"
        "    return True\n"
        "for _ in range(600):\n"
        "    if not _parent_alive(parent_pid):\n"
        "        break\n"
        "    time.sleep(0.2)\n"
        "with open(log_path, 'w', encoding='utf-8') as log:\n"
        "    for item in commands:\n"
        "        argv = [str(part) for part in item.get('argv', []) if str(part).strip()]\n"
        "        cwd = str(item.get('cwd') or '').strip() or None\n"
        "        log.write('==> ' + ' '.join(argv) + '\\n')\n"
        "        log.flush()\n"
        "        completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)\n"
        "        if completed.stdout:\n"
        "            log.write(completed.stdout)\n"
        "        if completed.stderr:\n"
        "            log.write(completed.stderr)\n"
        "        log.flush()\n"
        "        if completed.returncode != 0:\n"
        "            sys.exit(completed.returncode)\n"
        "sys.exit(0)\n"
    )
    creationflags = 0
    for name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS", "CREATE_NO_WINDOW"):
        creationflags |= int(getattr(subprocess, name, 0))
    process = subprocess.Popen(
        [python_executable, "-c", child_code, json.dumps(payload)],
        cwd=None,
        creationflags=creationflags,
        close_fds=True,
    )
    return {
        "ok": True,
        "background_pid": int(process.pid),
        "log_path": str(log_path),
    }


def build_self_update_plan(
    *,
    root: str = ".",
    python_executable: str = sys.executable,
    dist_name: str = "ace-lite-engine",
    skip_git_pull: bool = False,
    get_version_info_fn: Any = get_version_info,
    get_update_status_fn: Any = get_update_status,
) -> dict[str, Any]:
    requested_root = Path(root).resolve()
    version_info = dict(get_version_info_fn(dist_name=dist_name))
    update_status = dict(
        get_update_status_fn(
            dist_name=dist_name,
            version_info=version_info,
        )
    )
    install_mode = str(update_status.get("install_mode") or "unknown").strip() or "unknown"
    source_root = str(update_status.get("source_root") or "").strip()
    working_root = Path(source_root).resolve() if source_root else requested_root

    commands: list[dict[str, Any]] = []
    execution_mode = "pip_upgrade"
    if install_mode in {"editable", "source_checkout"}:
        script_path = working_root / "scripts" / "update.py"
        if script_path.exists():
            argv = [python_executable, str(script_path), "--root", str(working_root)]
            if skip_git_pull:
                argv.append("--skip-git-pull")
            commands.append(
                {
                    "argv": argv,
                    "display": _format_command(argv),
                    "cwd": str(working_root),
                }
            )
            execution_mode = "source_update_script"
        else:
            install_argv = [python_executable, "-m", "pip", "install", "-e", ".[dev]"]
            verify_argv = [
                python_executable,
                "-c",
                "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
            ]
            commands.extend(
                [
                    {
                        "argv": install_argv,
                        "display": _format_command(install_argv),
                        "cwd": str(working_root),
                    },
                    {
                        "argv": verify_argv,
                        "display": _format_command(verify_argv),
                        "cwd": str(working_root),
                    },
                ]
            )
            execution_mode = "editable_reinstall"
    else:
        install_argv = [python_executable, "-m", "pip", "install", "-U", dist_name]
        verify_argv = [
            python_executable,
            "-c",
            "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
        ]
        commands.extend(
            [
                {
                    "argv": install_argv,
                    "display": _format_command(install_argv),
                    "cwd": "",
                },
                {
                    "argv": verify_argv,
                    "display": _format_command(verify_argv),
                    "cwd": "",
                },
            ]
        )

    return {
        "ok": True,
        "event": "self_update_plan",
        "dist_name": dist_name,
        "root": str(requested_root),
        "install_mode": install_mode,
        "execution_mode": execution_mode,
        "skip_git_pull": bool(skip_git_pull),
        "python_executable": str(python_executable),
        "version_info": version_info,
        "update_status": update_status,
        "commands": commands,
    }


def run_self_update(
    *,
    root: str = ".",
    python_executable: str = sys.executable,
    dist_name: str = "ace-lite-engine",
    skip_git_pull: bool = False,
    check: bool = False,
    get_version_info_fn: Any = get_version_info,
    get_update_status_fn: Any = get_update_status,
    run_command_fn: Any = _run_command,
    should_defer_update_fn: Any = _should_defer_self_update,
    launch_detached_update_fn: Any = _launch_detached_windows_update,
) -> dict[str, Any]:
    payload = build_self_update_plan(
        root=root,
        python_executable=python_executable,
        dist_name=dist_name,
        skip_git_pull=skip_git_pull,
        get_version_info_fn=get_version_info_fn,
        get_update_status_fn=get_update_status_fn,
    )
    payload["check_only"] = bool(check)
    payload["executed"] = False
    if check:
        payload["message"] = "Self-update plan only; no commands were executed."
        return payload

    if bool(should_defer_update_fn()):
        launch_result = launch_detached_update_fn(
            python_executable=python_executable,
            commands=[
                dict(item)
                for item in payload.get("commands", [])
                if isinstance(item, dict)
            ],
        )
        payload["deferred"] = True
        payload["launched"] = bool(launch_result.get("ok", False))
        payload["background_pid"] = int(launch_result.get("background_pid", 0) or 0)
        payload["log_path"] = str(launch_result.get("log_path") or "")
        payload["message"] = (
            "Self-update launched in the background so Windows can replace console scripts after this process exits."
        )
        payload["ok"] = bool(launch_result.get("ok", False))
        return payload

    command_results: list[dict[str, Any]] = []
    for command in payload.get("commands", []):
        if not isinstance(command, dict):
            continue
        cwd_value = str(command.get("cwd") or "").strip()
        cwd = Path(cwd_value).resolve() if cwd_value else None
        result = run_command_fn(list(command.get("argv", [])), cwd=cwd)
        command_results.append(dict(result))
        if not bool(result.get("ok")):
            payload["ok"] = False
            payload["failed_command"] = dict(result)
            break

    payload["executed"] = True
    payload["command_results"] = command_results
    if bool(payload.get("ok")):
        payload["message"] = "Self-update completed successfully."
    else:
        payload["message"] = "Self-update failed."
    return payload


__all__ = ["build_self_update_plan", "run_self_update"]
