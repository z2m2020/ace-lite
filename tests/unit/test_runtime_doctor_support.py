from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app import runtime_doctor_support
from ace_lite.cli_app.runtime_command_support import (
    build_runtime_cache_doctor_payload,
    build_runtime_cache_vacuum_payload,
    build_runtime_doctor_payload,
    build_runtime_git_doctor_payload,
    build_runtime_version_sync_payload,
)


def test_runtime_doctor_support_facade_reexports_doctor_helpers() -> None:
    assert build_runtime_cache_doctor_payload is runtime_doctor_support.build_runtime_cache_doctor_payload
    assert build_runtime_cache_vacuum_payload is runtime_doctor_support.build_runtime_cache_vacuum_payload
    assert build_runtime_doctor_payload is runtime_doctor_support.build_runtime_doctor_payload
    assert build_runtime_git_doctor_payload is runtime_doctor_support.build_runtime_git_doctor_payload
    assert build_runtime_version_sync_payload is runtime_doctor_support.build_runtime_version_sync_payload


def test_build_runtime_git_doctor_payload_accepts_non_git_repo(tmp_path: Path) -> None:
    payload = runtime_doctor_support.build_runtime_git_doctor_payload(
        root=str(tmp_path),
        timeout_seconds=1.0,
    )

    assert payload["ok"] is True
    assert payload["enabled"] is False
    assert payload["reason"] == "not_git_repo"


def test_build_runtime_git_doctor_payload_classifies_git_launch_failure(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    payload = runtime_doctor_support.build_runtime_git_doctor_payload(
        root=str(tmp_path),
        timeout_seconds=1.0,
        find_git_root_fn=lambda root: Path(root),
        collect_git_head_snapshot_fn=lambda **kwargs: {
            "enabled": True,
            "reason": "error",
            "error": "error launching git:",
            "head_commit": "",
            "head_ref": "",
        },
        collect_git_worktree_summary_fn=lambda **kwargs: {
            "enabled": True,
            "reason": "error",
            "error": "error launching git:",
            "changed_count": 0,
            "entries": [],
        },
    )

    assert payload["ok"] is False
    assert payload["issue_type"] == "git_unavailable"
    assert payload["git_available"] is False
    assert payload["recommendations"]


def test_build_runtime_version_sync_payload_detects_install_drift() -> None:
    payload = runtime_doctor_support.build_runtime_version_sync_payload(
        get_version_info_fn=lambda **kwargs: {
            "dist_name": "ace-lite-engine",
            "version": "0.3.46",
            "source": "pyproject",
            "pyproject_version": "0.3.46",
            "installed_version": "0.3.44",
            "drifted": True,
        }
    )

    assert payload["ok"] is False
    assert payload["reason"] == "install_drift"
    assert payload["recommendations"]
