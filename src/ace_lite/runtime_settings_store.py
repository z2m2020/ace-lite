from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any


RUNTIME_SETTINGS_SCHEMA_VERSION = 1
DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH = "~/.ace-lite/runtime-settings/current.json"
DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH = "~/.ace-lite/runtime-settings/last-known-good.json"


def _normalize_for_fingerprint(value: Any) -> Any:
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(str(item) for item in value.keys()):
            normalized[key] = _normalize_for_fingerprint(value[key])
        return normalized
    if isinstance(value, tuple):
        return [_normalize_for_fingerprint(item) for item in value]
    if isinstance(value, list):
        return [_normalize_for_fingerprint(item) for item in value]
    if isinstance(value, set):
        normalized_items = [_normalize_for_fingerprint(item) for item in value]
        return sorted(
            normalized_items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return value


def build_runtime_settings_fingerprint(snapshot: Mapping[str, Any]) -> str:
    normalized = _normalize_for_fingerprint(dict(snapshot))
    text = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def build_runtime_settings_record(
    *,
    snapshot: Mapping[str, Any],
    provenance: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
    schema_version: int = RUNTIME_SETTINGS_SCHEMA_VERSION,
) -> dict[str, Any]:
    normalized_snapshot = dict(snapshot)
    normalized_provenance = dict(provenance)
    normalized_metadata = dict(metadata or {})
    return {
        "schema_version": int(schema_version),
        "snapshot": normalized_snapshot,
        "provenance": normalized_provenance,
        "fingerprint": build_runtime_settings_fingerprint(normalized_snapshot),
        "metadata": normalized_metadata,
    }


def resolve_user_runtime_settings_path(
    *,
    home_path: str | Path | None = None,
    configured_path: str | Path | None = None,
) -> Path:
    base = Path(home_path).expanduser() if home_path is not None else Path.home()
    raw = str(configured_path or DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH).strip()
    if raw.startswith("~/") or raw.startswith("~\\"):
        raw = raw[2:]
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base / candidate).resolve()


def resolve_user_runtime_settings_last_known_good_path(
    *,
    home_path: str | Path | None = None,
    configured_path: str | Path | None = None,
) -> Path:
    base = Path(home_path).expanduser() if home_path is not None else Path.home()
    raw = str(configured_path or DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH).strip()
    if raw.startswith("~/") or raw.startswith("~\\"):
        raw = raw[2:]
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base / candidate).resolve()


def validate_runtime_settings_record(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    snapshot = payload.get("snapshot")
    provenance = payload.get("provenance")
    metadata = payload.get("metadata", {})
    fingerprint = str(payload.get("fingerprint") or "").strip()
    schema_version = payload.get("schema_version")
    if not isinstance(snapshot, Mapping) or not isinstance(provenance, Mapping):
        return None
    if not isinstance(metadata, Mapping):
        metadata = {}
    try:
        normalized_schema_version = int(schema_version)
    except Exception:
        return None
    expected_fingerprint = build_runtime_settings_fingerprint(snapshot)
    if fingerprint != expected_fingerprint:
        return None
    return {
        "schema_version": normalized_schema_version,
        "snapshot": dict(snapshot),
        "provenance": dict(provenance),
        "fingerprint": fingerprint,
        "metadata": dict(metadata),
    }


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _ensure_parent_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def write_runtime_settings_record(*, path: str | Path, payload: Mapping[str, Any]) -> Path:
    target = Path(path).resolve()
    _atomic_write_json(target, payload)
    return target


def load_runtime_settings_record(path: str | Path) -> dict[str, Any] | None:
    target = Path(path).resolve()
    if not target.exists() or not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def load_valid_runtime_settings_record(path: str | Path) -> dict[str, Any] | None:
    payload = load_runtime_settings_record(path)
    if payload is None:
        return None
    return validate_runtime_settings_record(payload)


def load_runtime_settings_with_fallback(
    *,
    current_path: str | Path,
    last_known_good_path: str | Path,
) -> tuple[dict[str, Any] | None, str | None]:
    current = load_valid_runtime_settings_record(current_path)
    if current is not None:
        return current, "current"
    last_known_good = load_valid_runtime_settings_record(last_known_good_path)
    if last_known_good is not None:
        return last_known_good, "last_known_good"
    return None, None


def persist_runtime_settings_record(
    *,
    current_path: str | Path,
    payload: Mapping[str, Any],
    last_known_good_path: str | Path | None = None,
    update_last_known_good: bool = False,
) -> Path:
    validated = validate_runtime_settings_record(payload)
    if validated is None:
        raise ValueError("Invalid runtime settings record")
    target = write_runtime_settings_record(path=current_path, payload=validated)
    if update_last_known_good and last_known_good_path is not None:
        write_runtime_settings_record(path=last_known_good_path, payload=validated)
    return target


__all__ = [
    "RUNTIME_SETTINGS_SCHEMA_VERSION",
    "DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH",
    "DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH",
    "build_runtime_settings_fingerprint",
    "build_runtime_settings_record",
    "load_runtime_settings_with_fallback",
    "load_runtime_settings_record",
    "load_valid_runtime_settings_record",
    "persist_runtime_settings_record",
    "resolve_user_runtime_settings_last_known_good_path",
    "resolve_user_runtime_settings_path",
    "validate_runtime_settings_record",
    "write_runtime_settings_record",
]
