from __future__ import annotations

from ace_lite.config import normalize_repo_identity, resolve_repo_identity


def test_resolve_repo_identity_prefers_git_root_name_when_worktree_name_is_requested(
    tmp_path,
) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_root = repo_root / "tabiapp-backend_worktree_aeon_v2"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)

    payload = resolve_repo_identity(
        root=worktree_root,
        repo="tabiapp-backend_worktree_aeon_v2",
    )

    assert payload == {
        "repo_id": "tabiapp-backend",
        "repo_label": "tabiapp-backend",
        "requested_repo": "tabiapp-backend_worktree_aeon_v2",
        "source": "git_root_name",
        "root_path": str(worktree_root.resolve()),
        "git_root": str(repo_root.resolve()),
        "git_root_name": "tabiapp-backend",
        "worktree_name": "tabiapp-backend_worktree_aeon_v2",
        "uses_git_root_name": True,
    }


def test_normalize_repo_identity_sanitizes_explicit_repo_labels() -> None:
    assert normalize_repo_identity("TabiApp Backend / Prod") == "tabiapp-backend-prod"
    assert normalize_repo_identity("  ") == "repo"


def test_resolve_repo_identity_detects_actual_git_worktree_file_layout(tmp_path) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_root = tmp_path / "tabiapp-backend_worktree_aeon_v2"
    common_git_dir = repo_root / ".git"
    worktree_git_dir = common_git_dir / "worktrees" / "tabiapp-backend_worktree_aeon_v2"
    worktree_git_dir.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    (worktree_root / ".git").write_text(
        f"gitdir: {worktree_git_dir}\n",
        encoding="utf-8",
    )

    payload = resolve_repo_identity(root=worktree_root)

    assert payload == {
        "repo_id": "tabiapp-backend",
        "repo_label": "tabiapp-backend",
        "requested_repo": None,
        "source": "git_root_name",
        "root_path": str(worktree_root.resolve()),
        "git_root": str(repo_root.resolve()),
        "git_root_name": "tabiapp-backend",
        "worktree_name": "tabiapp-backend_worktree_aeon_v2",
        "uses_git_root_name": True,
    }
