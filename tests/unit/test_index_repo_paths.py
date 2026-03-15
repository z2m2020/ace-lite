from __future__ import annotations

from pathlib import Path

from ace_lite.index_stage.repo_paths import normalize_repo_path, resolve_repo_relative_path


def test_resolve_repo_relative_path_uses_repo_root_for_relative_path() -> None:
    resolved = resolve_repo_relative_path(
        root="F:/repo",
        configured_path="context-map/router/model.json",
    )

    assert resolved == Path("F:/repo/context-map/router/model.json")


def test_resolve_repo_relative_path_falls_back_to_default_index_path() -> None:
    resolved = resolve_repo_relative_path(root="F:/repo", configured_path="")

    assert resolved == Path("F:/repo/context-map/index.json")


def test_normalize_repo_path_preserves_leading_slash_by_default() -> None:
    assert normalize_repo_path("./src\\app.py") == "src/app.py"
    assert normalize_repo_path("/src/app.py") == "/src/app.py"


def test_normalize_repo_path_can_strip_leading_slash() -> None:
    assert (
        normalize_repo_path("/src/app.py", strip_leading_slash=True)
        == "src/app.py"
    )
