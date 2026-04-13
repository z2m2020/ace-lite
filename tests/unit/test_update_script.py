from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():  # type: ignore[no-untyped-def]
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "update.py"
    spec = importlib.util.spec_from_file_location("update_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load update.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_update_runs_git_pull_then_install_then_version_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    (tmp_path / ".git").mkdir()
    commands: list[list[str]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        ["update.py", "--root", str(tmp_path), "--python-executable", "python-custom"],
    )
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, *, cwd: commands.append(list(command)),
    )

    assert module.main() == 0
    assert commands == [
        ["git", "pull"],
        ["python-custom", "-m", "pip", "install", "-e", ".[dev]"],
        [
            "python-custom",
            "-c",
            "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
        ],
    ]


def test_update_skips_git_pull_when_flag_is_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    (tmp_path / ".git").mkdir()
    commands: list[list[str]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        ["update.py", "--root", str(tmp_path), "--skip-git-pull"],
    )
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, *, cwd: commands.append(list(command)),
    )

    assert module.main() == 0
    assert commands == [
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        [
            sys.executable,
            "-c",
            "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
        ],
    ]


def test_update_skips_git_pull_when_repo_has_no_git_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    commands: list[list[str]] = []

    monkeypatch.setattr(sys, "argv", ["update.py", "--root", str(tmp_path)])
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, *, cwd: commands.append(list(command)),
    )

    assert module.main() == 0
    assert commands == [
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        [
            sys.executable,
            "-c",
            "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
        ],
    ]


def test_update_exits_with_actionable_message_when_git_pull_fails_to_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    (tmp_path / ".git").mkdir()

    monkeypatch.setattr(sys, "argv", ["update.py", "--root", str(tmp_path)])

    def _boom(command, *, cwd):  # type: ignore[no-untyped-def]
        if list(command) == ["git", "pull"]:
            raise OSError("git missing")

    monkeypatch.setattr(module, "_run", _boom)

    with pytest.raises(SystemExit, match="rerun with --skip-git-pull"):
        module.main()
