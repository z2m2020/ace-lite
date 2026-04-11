from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "write_run_manifest.py"


def _run_writer(tmp_path: Path, *extra_args: str) -> tuple[int, Path]:
    manifest_path = tmp_path / "run_manifest.jsonl"
    env = os.environ.copy()
    python_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = python_path if not existing else python_path + os.pathsep + existing
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--manifest-path",
        str(manifest_path),
        *extra_args,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode, manifest_path


def test_write_run_manifest_appends_valid_jsonl_row(tmp_path: Path) -> None:
    rc, manifest_path = _run_writer(
        tmp_path,
        "--unit-id",
        "ALH1-0004.T2",
        "--phase",
        "phase0",
        "--priority",
        "high",
        "--owner-role",
        "governance",
        "--status",
        "done",
        "--depends-on",
        "ALH1-0004.T1",
        "--path-set",
        "src/ace_lite/run_manifest.py",
        "--forbidden-paths",
        "src/ace_lite/mcp_server",
        "--goal",
        "Write run manifest entries.",
        "--deliverable",
        "A JSONL row per task.",
        "--input-contracts",
        "task spec",
        "--output-contracts",
        "validated run_manifest_v1 row",
        "--metrics-touched",
        "execution_traceability",
        "--verification-commands",
        "pytest -q tests/unit/test_run_manifest_writer.py",
        "--artifacts-emitted",
        "context-map/run_manifest.jsonl",
        "--rollback-steps",
        "Remove the appended JSONL row.",
        "--done-definition",
        "Entry validates against run_manifest_v1.",
        "--failure-signals",
        "status is invalid",
    )
    assert rc == 0
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["unit_id"] == "ALH1-0004.T2"
    assert payload["status"] == "done"
    assert payload["schema_version"] == "run_manifest_v1"


def test_write_run_manifest_rejects_invalid_status(tmp_path: Path) -> None:
    rc, _ = _run_writer(
        tmp_path,
        "--unit-id",
        "ALH1-0004.T2",
        "--phase",
        "phase0",
        "--priority",
        "high",
        "--owner-role",
        "governance",
        "--status",
        "invalid_status",
        "--goal",
        "Test.",
        "--deliverable",
        "Test.",
    )
    assert rc == 1


def test_write_run_manifest_multiple_entries(tmp_path: Path) -> None:
    rc1, manifest_path = _run_writer(
        tmp_path,
        "--unit-id",
        "ALH1-0004.T1",
        "--phase",
        "phase0",
        "--priority",
        "high",
        "--owner-role",
        "governance",
        "--status",
        "done",
        "--goal",
        "First.",
        "--deliverable",
        "First.",
    )
    rc2, _ = _run_writer(
        tmp_path,
        "--unit-id",
        "ALH1-0004.T2",
        "--phase",
        "phase0",
        "--priority",
        "high",
        "--owner-role",
        "governance",
        "--status",
        "done",
        "--goal",
        "Second.",
        "--deliverable",
        "Second.",
    )
    assert rc1 == 0
    assert rc2 == 0
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert [p["unit_id"] for p in payloads] == ["ALH1-0004.T1", "ALH1-0004.T2"]
