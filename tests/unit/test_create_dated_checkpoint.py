from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "create_dated_checkpoint.py"


def _run_script(*extra_args: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    python_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = python_path if not existing else python_path + os.pathsep + existing
    cmd = [sys.executable, str(SCRIPT_PATH), *extra_args]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode, result.stdout, result.stderr


def test_create_dated_checkpoint_creates_manifest(tmp_path: Path) -> None:
    rc, stdout, stderr = _run_script(
        "--date",
        "2026-04-11",
        "--phase",
        "0",
        "--output-root",
        str(tmp_path / "checkpoints"),
        "--artifact-ledger",
        "nonexistent/problem_ledger.json",
    )
    assert rc == 0
    manifest_path = tmp_path / "checkpoints" / "phase0" / "2026-04-11" / "checkpoint_manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "checkpoint_manifest_v1"
    assert payload["phase"] == "phase0"
    assert "included_artifacts" in payload
    assert "warnings" in payload


def test_create_dated_checkpoint_missing_artifact_emits_warning(tmp_path: Path) -> None:
    rc, stdout, stderr = _run_script(
        "--date",
        "2026-04-11",
        "--phase",
        "0",
        "--output-root",
        str(tmp_path / "checkpoints"),
        "--artifact-ledger",
        "nonexistent/problem_ledger.json",
    )
    assert rc == 0
    manifest_path = tmp_path / "checkpoints" / "phase0" / "2026-04-11" / "checkpoint_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert any("missing" in w for w in payload.get("warnings", []))


def test_create_dated_checkpoint_cli_help_succeeds() -> None:
    rc, stdout, stderr = _run_script("--help")
    assert rc == 0


def test_create_dated_checkpoint_cli_creates_file(tmp_path: Path) -> None:
    rc, stdout, stderr = _run_script(
        "--date",
        "2026-04-11",
        "--phase",
        "0",
        "--output-root",
        str(tmp_path / "checkpoints"),
    )
    assert rc == 0
    assert "manifest:" in stdout
