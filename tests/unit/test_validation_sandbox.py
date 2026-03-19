from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.validation.sandbox import (
    apply_patch_artifact_in_sandbox,
    bootstrap_patch_sandbox,
    cleanup_patch_sandbox,
    restore_patch_sandbox,
)


def test_patch_sandbox_bootstrap_apply_restore_and_cleanup(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_path = repo_root / "src" / "app.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("print('old')\n", encoding="utf-8")

    patch_artifact = {
        "schema_version": "patch_artifact_v1",
        "patch_format": "unified_diff",
        "apply_target_root": "",
        "target_file_manifest": ["src/app.py"],
        "operations": [
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before",
                "after_sha256": "after",
                "hunk_count": 1,
            }
        ],
        "rollback_anchors": [
            {"path": "src/app.py", "strategy": "git_restore", "anchor": "HEAD"}
        ],
        "patch_text": "\n".join(
            [
                "diff --git a/src/app.py b/src/app.py",
                "--- a/src/app.py",
                "+++ b/src/app.py",
                "@@ -1 +1 @@",
                "-print('old')",
                "+print('new')",
                "",
            ]
        ),
        "stats": {
            "operation_count": 1,
            "add_count": 0,
            "update_count": 1,
            "delete_count": 0,
            "rollback_anchor_count": 1,
        },
        "metadata": {},
    }

    session = bootstrap_patch_sandbox(
        repo_root=repo_root,
        patch_artifact=patch_artifact,
        sandbox_parent=tmp_path,
    )
    apply_result = apply_patch_artifact_in_sandbox(session=session, timeout_seconds=5.0)

    assert apply_result["ok"] is True
    assert source_path.read_text(encoding="utf-8") == "print('old')\n"
    sandbox_path = Path(session.sandbox_root) / "src" / "app.py"
    assert sandbox_path.read_text(encoding="utf-8") == "print('new')\n"

    restore_result = restore_patch_sandbox(session)
    assert restore_result["ok"] is True
    assert sandbox_path.read_text(encoding="utf-8") == "print('old')\n"

    cleanup_result = cleanup_patch_sandbox(session)
    assert cleanup_result["ok"] is True
    assert not Path(session.sandbox_root).exists()


def test_apply_patch_artifact_in_sandbox_reports_empty_patch_text(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    patch_artifact = {
        "schema_version": "patch_artifact_v1",
        "patch_format": "unified_diff",
        "apply_target_root": "",
        "target_file_manifest": ["src/app.py"],
        "operations": [{"op": "add", "path": "src/app.py", "hunk_count": 1}],
        "rollback_anchors": [
            {"path": "src/app.py", "strategy": "delete_added_file", "anchor": "post-apply"}
        ],
        "patch_text": "",
        "stats": {
            "operation_count": 1,
            "add_count": 1,
            "update_count": 0,
            "delete_count": 0,
            "rollback_anchor_count": 1,
        },
        "metadata": {},
    }

    session = bootstrap_patch_sandbox(
        repo_root=repo_root,
        patch_artifact=patch_artifact,
        sandbox_parent=tmp_path,
    )

    result = apply_patch_artifact_in_sandbox(session=session)

    assert result["ok"] is False
    assert result["reason"] == "empty_patch_text"
    cleanup_patch_sandbox(session)


def test_apply_patch_artifact_in_sandbox_falls_back_when_git_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    source_path = repo_root / "src" / "app.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("print('old')\n", encoding="utf-8")

    patch_artifact = {
        "schema_version": "patch_artifact_v1",
        "patch_format": "unified_diff",
        "apply_target_root": "",
        "target_file_manifest": ["src/app.py"],
        "operations": [
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before",
                "after_sha256": "after",
                "hunk_count": 1,
            }
        ],
        "rollback_anchors": [
            {"path": "src/app.py", "strategy": "git_restore", "anchor": "HEAD"}
        ],
        "patch_text": "\n".join(
            [
                "diff --git a/src/app.py b/src/app.py",
                "--- a/src/app.py",
                "+++ b/src/app.py",
                "@@ -1 +1 @@",
                "-print('old')",
                "+print('new')",
                "",
            ]
        ),
        "stats": {
            "operation_count": 1,
            "add_count": 0,
            "update_count": 1,
            "delete_count": 0,
            "rollback_anchor_count": 1,
        },
        "metadata": {},
    }

    session = bootstrap_patch_sandbox(
        repo_root=repo_root,
        patch_artifact=patch_artifact,
        sandbox_parent=tmp_path,
    )

    monkeypatch.setattr(
        "ace_lite.validation.sandbox.run_capture_output",
        lambda *args, **kwargs: (1, "", "error launching git: \n\n", False),
    )

    result = apply_patch_artifact_in_sandbox(session=session, timeout_seconds=5.0)

    assert result["ok"] is True
    assert result["method"] == "python_fallback"
    sandbox_path = Path(session.sandbox_root) / "src" / "app.py"
    assert sandbox_path.read_text(encoding="utf-8") == "print('new')\n"

    cleanup_patch_sandbox(session)
