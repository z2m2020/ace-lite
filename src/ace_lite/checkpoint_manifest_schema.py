from __future__ import annotations

from typing import Any

CHECKPOINT_MANIFEST_SCHEMA_NAME = "checkpoint_manifest"
CHECKPOINT_MANIFEST_SCHEMA_VERSION = "checkpoint_manifest_v1"
CHECKPOINT_MANIFEST_SCHEMA_LABEL = "ace-lite-checkpoint-manifest-v1"

CHECKPOINT_MANIFEST_REQUIRED_KEYS = (
    "schema_version",
    "generated_at",
    "git_sha",
    "phase",
    "included_artifacts",
    "warnings",
)

CHECKPOINT_MANIFEST_ARTIFACT_REQUIRED_KEYS = (
    "path",
    "present",
    "schema_version",
    "notes",
    "status",
)

CHECKPOINT_MANIFEST_ARTIFACT_STATUS_VALUES = (
    "present",
    "missing",
)


def build_checkpoint_manifest_schema_document() -> dict[str, Any]:
    return {
        "schema_name": CHECKPOINT_MANIFEST_SCHEMA_NAME,
        "schema_version": CHECKPOINT_MANIFEST_SCHEMA_VERSION,
        "schema_label": CHECKPOINT_MANIFEST_SCHEMA_LABEL,
        "required_keys": list(CHECKPOINT_MANIFEST_REQUIRED_KEYS),
        "artifact_required_keys": list(CHECKPOINT_MANIFEST_ARTIFACT_REQUIRED_KEYS),
        "artifact_status_values": list(CHECKPOINT_MANIFEST_ARTIFACT_STATUS_VALUES),
    }


__all__ = [
    "CHECKPOINT_MANIFEST_ARTIFACT_REQUIRED_KEYS",
    "CHECKPOINT_MANIFEST_ARTIFACT_STATUS_VALUES",
    "CHECKPOINT_MANIFEST_REQUIRED_KEYS",
    "CHECKPOINT_MANIFEST_SCHEMA_LABEL",
    "CHECKPOINT_MANIFEST_SCHEMA_NAME",
    "CHECKPOINT_MANIFEST_SCHEMA_VERSION",
    "build_checkpoint_manifest_schema_document",
]
