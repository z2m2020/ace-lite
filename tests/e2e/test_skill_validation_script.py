from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_script(name: str):
    module_name = f"script_{name.replace('.', '_')}"
    module_path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_skill_validation_checkout_reuses_existing_checkout_when_git_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script("run_skill_validation.py")

    workspace = tmp_path / "repos"
    target = workspace / "blockscout-frontend"
    git_dir = target / ".git"
    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (refs_dir / "main").write_text("deadbeefcafebabe\n", encoding="utf-8")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = cwd
        if cmd[:4] == ["git", "-C", str(target), "fetch"]:
            return module.CommandResult(
                cmd=cmd,
                cwd=None,
                returncode=1,
                stdout="",
                stderr="error launching git:",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    checkout = module._ensure_checkout(
        workspace=workspace,
        repo_name="blockscout-frontend",
        repo_url="https://github.com/blockscout/frontend.git",
        repo_ref="main",
    )

    assert checkout["skipped"] is False
    assert checkout["checkout_reused_without_refresh"] is True
    assert checkout["resolved_commit"] == "deadbeefcafebabe"
    assert checkout["root"] == str(target.resolve())


def test_skill_validation_main_skips_when_git_unavailable_and_checkout_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script("run_skill_validation.py")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    output_path = tmp_path / "report.json"
    index_cache_path = tmp_path / "index.json"
    repo_dir = tmp_path / "repos"

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None):
        _ = cwd
        if cmd[:2] == ["git", "clone"]:
            return module.CommandResult(
                cmd=cmd,
                cwd=None,
                returncode=1,
                stdout="",
                stderr="error launching git:",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_skill_validation.py",
            "--repo-dir",
            str(repo_dir),
            "--skills-dir",
            str(skills_dir),
            "--index-cache-path",
            str(index_cache_path),
            "--output-path",
            str(output_path),
            "--fail-on-miss",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["skipped"] is True
    assert payload["skip_reason"] == "git_unavailable_missing_checkout"
    assert payload["total"] == 0
    assert payload["failed_apps"] == []
