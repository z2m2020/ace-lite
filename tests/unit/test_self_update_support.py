from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app import self_update_support


def test_build_self_update_plan_uses_repo_update_script_for_editable_mode(
    tmp_path: Path,
) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "update.py").write_text("print('ok')\n", encoding="utf-8")

    payload = self_update_support.build_self_update_plan(
        root=str(tmp_path),
        python_executable="python-custom",
        skip_git_pull=True,
        get_version_info_fn=lambda **kwargs: {
            "dist_name": kwargs["dist_name"],
            "version": "0.3.82",
            "source": "pyproject",
            "pyproject_version": "0.3.82",
            "installed_version": "0.3.82",
            "drifted": False,
            "reason_code": "ok",
        },
        get_update_status_fn=lambda **kwargs: {
            "dist_name": kwargs["dist_name"],
            "install_mode": "editable",
            "source_root": str(tmp_path),
            "recommended_update_command": "python scripts/update.py --root .",
            "update_available": False,
        },
    )

    assert payload["execution_mode"] == "source_update_script"
    assert payload["commands"][0]["argv"] == [
        "python-custom",
        str((tmp_path / "scripts" / "update.py").resolve()),
        "--root",
        str(tmp_path.resolve()),
        "--skip-git-pull",
    ]


def test_run_self_update_executes_pip_upgrade_and_verify_for_installed_package() -> None:
    seen: list[tuple[list[str], str]] = []

    payload = self_update_support.run_self_update(
        root=".",
        python_executable="python-custom",
        get_version_info_fn=lambda **kwargs: {
            "dist_name": kwargs["dist_name"],
            "version": "0.3.82",
            "source": "installed_metadata",
            "pyproject_version": None,
            "installed_version": "0.3.82",
            "drifted": False,
            "reason_code": "ok",
        },
        get_update_status_fn=lambda **kwargs: {
            "dist_name": kwargs["dist_name"],
            "install_mode": "installed_package",
            "source_root": "",
            "recommended_update_command": "python -m pip install -U ace-lite-engine",
            "update_available": True,
        },
        run_command_fn=lambda argv, *, cwd: seen.append((list(argv), str(cwd or ""))) or {
            "argv": list(argv),
            "display": " ".join(argv),
            "cwd": str(cwd or ""),
            "exit_code": 0,
            "ok": True,
            "stdout": "",
            "stderr": "",
        },
        should_defer_update_fn=lambda: False,
    )

    assert payload["ok"] is True
    assert payload["executed"] is True
    assert seen == [
        (["python-custom", "-m", "pip", "install", "-U", "ace-lite-engine"], ""),
        (
            [
                "python-custom",
                "-c",
                "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
            ],
            "",
        ),
    ]


def test_run_self_update_defers_windows_console_script_update() -> None:
    payload = self_update_support.run_self_update(
        root=".",
        python_executable="python-custom",
        get_version_info_fn=lambda **kwargs: {
            "dist_name": kwargs["dist_name"],
            "version": "0.3.85",
            "source": "pyproject",
            "pyproject_version": "0.3.85",
            "installed_version": "0.3.82",
            "drifted": True,
            "reason_code": "install_drift",
        },
        get_update_status_fn=lambda **kwargs: {
            "dist_name": kwargs["dist_name"],
            "install_mode": "editable",
            "source_root": "F:/repo",
            "recommended_update_command": "python scripts/update.py --root F:/repo",
            "update_available": True,
        },
        should_defer_update_fn=lambda: True,
        launch_detached_update_fn=lambda **kwargs: {
            "ok": True,
            "background_pid": 43210,
            "log_path": "F:/tmp/ace-lite-self-update.log",
        },
    )

    assert payload["ok"] is True
    assert payload["executed"] is False
    assert payload["deferred"] is True
    assert payload["launched"] is True
    assert payload["background_pid"] == 43210
    assert payload["log_path"] == "F:/tmp/ace-lite-self-update.log"
