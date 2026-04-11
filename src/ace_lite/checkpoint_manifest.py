"""Checkpoint manifest helpers for dated baseline metadata.

This module keeps checkpoint manifests lightweight and report-friendly. A
manifest can describe the artifact set that should exist for a checkpoint even
when some artifacts are still missing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ace_lite.checkpoint_manifest_schema import (
    CHECKPOINT_MANIFEST_ARTIFACT_REQUIRED_KEYS,
    CHECKPOINT_MANIFEST_ARTIFACT_STATUS_VALUES,
    CHECKPOINT_MANIFEST_REQUIRED_KEYS,
    CHECKPOINT_MANIFEST_SCHEMA_VERSION,
)

__all__ = [
    "SCHEMA_VERSION",
    "build_checkpoint_manifest_payload",
    "dump_checkpoint_manifest_payload",
    "dumps_checkpoint_manifest_payload",
    "load_checkpoint_manifest_payload",
    "loads_checkpoint_manifest_payload",
    "validate_checkpoint_manifest_payload",
]

SCHEMA_VERSION = CHECKPOINT_MANIFEST_SCHEMA_VERSION


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _bool(value: Any) -> bool:
    return bool(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_artifact_entry(entry: Mapping[str, Any] | Any) -> dict[str, Any]:
    artifact = _dict(entry)
    path = _str(artifact.get("path")).strip()
    present = _bool(artifact.get("present"))
    status = "present" if present else "missing"

    return {
        "path": path,
        "present": present,
        "schema_version": _str(artifact.get("schema_version")),
        "notes": _str(artifact.get("notes")),
        "status": status,
    }


def _build_warnings(included_artifacts: Sequence[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for artifact in included_artifacts:
        if artifact.get("status") != "missing":
            continue
        path = _str(artifact.get("path")).strip() or "(unknown-path)"
        warnings.append(f"artifact_missing:{path}")
    return warnings


def build_checkpoint_manifest_payload(
    *,
    generated_at: str | None = None,
    git_sha: str = "",
    phase: str = "baseline_checkpoint",
    included_artifacts: Sequence[Mapping[str, Any] | Any] | None = None,
) -> dict[str, Any]:
    normalized_artifacts = [_normalize_artifact_entry(item) for item in (included_artifacts or [])]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _str(generated_at) or _utc_now(),
        "git_sha": _str(git_sha),
        "phase": _str(phase) or "baseline_checkpoint",
        "included_artifacts": normalized_artifacts,
        "warnings": _build_warnings(normalized_artifacts),
    }


def validate_checkpoint_manifest_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    normalized = _dict(payload)
    if not normalized:
        raise ValueError("checkpoint_manifest payload must be a dictionary")

    for key in CHECKPOINT_MANIFEST_REQUIRED_KEYS:
        if key not in normalized:
            raise ValueError(f"{key} is required")

    if _str(normalized.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if (
        not isinstance(normalized.get("generated_at"), str)
        or not _str(normalized.get("generated_at")).strip()
    ):
        raise ValueError("generated_at must be a non-empty string")
    if not isinstance(normalized.get("git_sha"), str):
        raise ValueError("git_sha must be a string")
    if not isinstance(normalized.get("phase"), str) or not _str(normalized.get("phase")).strip():
        raise ValueError("phase must be a non-empty string")

    artifacts = normalized.get("included_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("included_artifacts must be a list")
    if not isinstance(normalized.get("warnings"), list):
        raise ValueError("warnings must be a list")

    normalized_artifacts = [_normalize_artifact_entry(item) for item in artifacts]
    for index, artifact in enumerate(normalized_artifacts):
        for key in CHECKPOINT_MANIFEST_ARTIFACT_REQUIRED_KEYS:
            if key not in artifact:
                raise ValueError(f"included_artifacts[{index}].{key} is required")
        if not artifact["path"]:
            raise ValueError(f"included_artifacts[{index}].path must be a non-empty string")
        if not isinstance(artifact["present"], bool):
            raise ValueError(f"included_artifacts[{index}].present must be a bool")
        if artifact["status"] not in CHECKPOINT_MANIFEST_ARTIFACT_STATUS_VALUES:
            raise ValueError(
                f"included_artifacts[{index}].status must be one of: "
                + ", ".join(CHECKPOINT_MANIFEST_ARTIFACT_STATUS_VALUES)
            )

    expected_warnings = _build_warnings(normalized_artifacts)
    actual_warnings = [_str(item) for item in _list(normalized.get("warnings"))]
    if actual_warnings != expected_warnings:
        raise ValueError("warnings must match missing included_artifacts")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _str(normalized.get("generated_at")),
        "git_sha": _str(normalized.get("git_sha")),
        "phase": _str(normalized.get("phase")),
        "included_artifacts": normalized_artifacts,
        "warnings": expected_warnings,
    }


def dump_checkpoint_manifest_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    return validate_checkpoint_manifest_payload(payload)


def load_checkpoint_manifest_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    return validate_checkpoint_manifest_payload(payload)


def dumps_checkpoint_manifest_payload(payload: Mapping[str, Any] | Any) -> str:
    return json.dumps(load_checkpoint_manifest_payload(payload), indent=2, sort_keys=True)


def loads_checkpoint_manifest_payload(value: str) -> dict[str, Any]:
    return load_checkpoint_manifest_payload(json.loads(value))
