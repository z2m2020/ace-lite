from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ace_lite.pipeline.hooks import HookBus
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
from ace_lite.profile_store import ProfileStore


def _typed_dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value)


def _typed_optional_dict(value: Any) -> dict[str, Any] | None:
    return cast(dict[str, Any] | None, value)


def _typed_path(value: Any) -> Path:
    return cast(Path, value)


def _typed_str(value: Any) -> str:
    return cast(str, value)


def _typed_int(value: Any) -> int:
    return cast(int, value)


def _typed_list_str(value: Any) -> list[str]:
    return cast(list[str], value)


def _typed_plugin_load_result(value: Any) -> tuple[HookBus, list[str]]:
    return cast(tuple[HookBus, list[str]], value)


def _typed_namespace_result(value: Any) -> tuple[str | None, str, str]:
    return cast(tuple[str | None, str, str], value)


def _typed_replay_load_result(
    value: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return cast(tuple[dict[str, Any] | None, dict[str, Any]], value)


def _typed_profile_store(value: Any) -> ProfileStore:
    return cast(ProfileStore, value)


def _typed_optional_preference_capture_store(
    value: Any,
) -> DurablePreferenceCaptureStore | None:
    return cast(DurablePreferenceCaptureStore | None, value)


__all__ = [
    "_typed_dict",
    "_typed_int",
    "_typed_list_str",
    "_typed_namespace_result",
    "_typed_optional_dict",
    "_typed_optional_preference_capture_store",
    "_typed_path",
    "_typed_plugin_load_result",
    "_typed_profile_store",
    "_typed_replay_load_result",
    "_typed_str",
]
