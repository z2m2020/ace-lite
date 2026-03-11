from __future__ import annotations

import re
from pathlib import PurePath
from pathlib import PurePosixPath
from pathlib import PureWindowsPath


DEFAULT_USER_RUNTIME_DB_PATH = "~/.ace-lite/runtime_state.db"
DEFAULT_REPO_RUNTIME_CACHE_DB_PATH = "context-map/runtime-cache/cache.db"

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _is_windows_style(value: str | PurePath | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(
        _WINDOWS_DRIVE_RE.match(text)
        or text.startswith("\\\\")
        or "\\" in text
    )


def _path_cls(*values: str | PurePath | None) -> type[PurePath]:
    for value in values:
        if _is_windows_style(value):
            return PureWindowsPath
    return PurePosixPath


def _coerce_path(
    value: str | PurePath,
    *,
    cls: type[PurePath],
) -> PurePath:
    if isinstance(value, cls):
        return value
    return cls(str(value).strip())


def resolve_user_runtime_db_path(
    *,
    home_path: str | PurePath | None = None,
    configured_path: str | PurePath | None = None,
) -> PurePath:
    cls = _path_cls(home_path, configured_path)
    raw_candidate = str(configured_path or DEFAULT_USER_RUNTIME_DB_PATH).strip()
    if home_path is not None and raw_candidate.startswith("~/"):
        raw_candidate = raw_candidate[2:]
    elif home_path is not None and raw_candidate.startswith("~\\"):
        raw_candidate = raw_candidate[2:]
    candidate = _coerce_path(raw_candidate, cls=cls)
    if candidate.is_absolute():
        return candidate

    if home_path is None:
        return candidate
    return _coerce_path(home_path, cls=cls) / candidate


def resolve_repo_runtime_cache_db_path(
    *,
    root_path: str | PurePath,
    configured_path: str | PurePath | None = None,
) -> PurePath:
    cls = _path_cls(root_path, configured_path)
    candidate = _coerce_path(
        configured_path or DEFAULT_REPO_RUNTIME_CACHE_DB_PATH,
        cls=cls,
    )
    if candidate.is_absolute():
        return candidate
    return _coerce_path(root_path, cls=cls) / candidate


__all__ = [
    "DEFAULT_REPO_RUNTIME_CACHE_DB_PATH",
    "DEFAULT_USER_RUNTIME_DB_PATH",
    "resolve_repo_runtime_cache_db_path",
    "resolve_user_runtime_db_path",
]
