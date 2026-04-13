from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from ace_lite.runtime_paths import (
    DEFAULT_REPO_RUNTIME_CACHE_DB_PATH,
    DEFAULT_USER_PREFERENCE_CAPTURE_DB_PATH,
    DEFAULT_USER_RUNTIME_DB_PATH,
    resolve_repo_runtime_cache_db_path,
    resolve_user_preference_capture_db_path,
    resolve_user_runtime_db_path,
)


def test_resolve_user_runtime_db_path_posix_home() -> None:
    resolved = resolve_user_runtime_db_path(
        home_path="/home/dev",
    )

    assert resolved == PurePosixPath("/home/dev/.ace-lite/runtime_state.db")
    assert str(resolved).endswith(
        str(PurePosixPath(".ace-lite/runtime_state.db"))
    )


def test_resolve_user_runtime_db_path_windows_home() -> None:
    resolved = resolve_user_runtime_db_path(
        home_path=r"C:\Users\dev",
    )

    assert resolved == PureWindowsPath(r"C:\Users\dev\.ace-lite\runtime_state.db")


def test_resolve_user_preference_capture_db_path_posix_home() -> None:
    resolved = resolve_user_preference_capture_db_path(
        home_path="/home/dev",
    )

    assert resolved == PurePosixPath("/home/dev/.ace-lite/preference_capture.db")
    assert str(resolved).endswith(
        str(PurePosixPath(DEFAULT_USER_PREFERENCE_CAPTURE_DB_PATH[2:]))
    )


def test_resolve_user_preference_capture_db_path_windows_home() -> None:
    resolved = resolve_user_preference_capture_db_path(
        home_path=r"C:\Users\dev",
    )

    assert resolved == PureWindowsPath(r"C:\Users\dev\.ace-lite\preference_capture.db")


def test_resolve_repo_runtime_cache_db_path_posix_root() -> None:
    resolved = resolve_repo_runtime_cache_db_path(
        root_path="/repo/demo",
    )

    assert resolved == PurePosixPath("/repo/demo/context-map/runtime-cache/cache.db")
    assert str(resolved).endswith(str(PurePosixPath(DEFAULT_REPO_RUNTIME_CACHE_DB_PATH)))


def test_resolve_repo_runtime_cache_db_path_windows_root() -> None:
    resolved = resolve_repo_runtime_cache_db_path(
        root_path=r"F:\repo\demo",
    )

    assert resolved == PureWindowsPath(r"F:\repo\demo\context-map\runtime-cache\cache.db")


def test_resolve_repo_runtime_cache_db_path_preserves_absolute_override() -> None:
    resolved = resolve_repo_runtime_cache_db_path(
        root_path="/repo/demo",
        configured_path="/var/tmp/runtime-cache.db",
    )

    assert resolved == PurePosixPath("/var/tmp/runtime-cache.db")
