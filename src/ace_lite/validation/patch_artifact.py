from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PATCH_ARTIFACT_SCHEMA_VERSION = "patch_artifact_v1"
PATCH_ARTIFACT_ALLOWED_OPERATIONS = ("add", "update", "delete")


def _normalize_relpath(*, value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError(f"{context} cannot be empty")
    return normalized


def _normalize_optional_str(*, value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalize_operation(*, payload: dict[str, Any], index: int) -> dict[str, Any]:
    op = str(payload.get("op") or payload.get("kind") or "").strip().lower()
    if op not in PATCH_ARTIFACT_ALLOWED_OPERATIONS:
        raise ValueError(
            "operations"
            f"[{index}].op must be one of {', '.join(PATCH_ARTIFACT_ALLOWED_OPERATIONS)}"
        )

    path = _normalize_relpath(
        value=payload.get("path") or payload.get("target_path"),
        context=f"operations[{index}].path",
    )
    normalized = {
        "op": op,
        "path": path,
        "language": _normalize_optional_str(value=payload.get("language")),
        "before_sha256": _normalize_optional_str(value=payload.get("before_sha256")),
        "after_sha256": _normalize_optional_str(value=payload.get("after_sha256")),
        "content_sha256": _normalize_optional_str(value=payload.get("content_sha256")),
        "hunk_count": max(0, int(payload.get("hunk_count", 0) or 0)),
    }
    return normalized


def _normalize_rollback_anchor(*, payload: dict[str, Any], index: int) -> dict[str, Any]:
    path = _normalize_relpath(
        value=payload.get("path"),
        context=f"rollback_anchors[{index}].path",
    )
    strategy = str(payload.get("strategy") or "").strip() or "git_restore"
    anchor = str(payload.get("anchor") or "").strip() or "HEAD"
    return {
        "path": path,
        "strategy": strategy,
        "anchor": anchor,
        "required": bool(payload.get("required", True)),
    }


@dataclass(frozen=True, slots=True)
class PatchArtifactContractV1:
    patch_format: str
    apply_target_root: str
    target_file_manifest: tuple[str, ...]
    operations: tuple[dict[str, Any], ...]
    rollback_anchors: tuple[dict[str, Any], ...]
    patch_text: str
    stats: dict[str, int]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PATCH_ARTIFACT_SCHEMA_VERSION,
            "patch_format": self.patch_format,
            "apply_target_root": self.apply_target_root,
            "target_file_manifest": list(self.target_file_manifest),
            "operations": [dict(item) for item in self.operations],
            "rollback_anchors": [dict(item) for item in self.rollback_anchors],
            "patch_text": self.patch_text,
            "stats": dict(self.stats),
            "metadata": dict(self.metadata),
        }


def build_patch_artifact_contract_v1(
    *,
    operations: list[dict[str, Any]],
    rollback_anchors: list[dict[str, Any]],
    patch_text: str = "",
    patch_format: str = "unified_diff",
    apply_target_root: str = "",
    metadata: dict[str, Any] | None = None,
) -> PatchArtifactContractV1:
    if not isinstance(operations, list) or not operations:
        raise ValueError("operations must be a non-empty list")
    if not isinstance(rollback_anchors, list) or not rollback_anchors:
        raise ValueError("rollback_anchors must be a non-empty list")

    normalized_operations = tuple(
        _normalize_operation(payload=item, index=index)
        for index, item in enumerate(operations)
        if isinstance(item, dict)
    )
    if not normalized_operations:
        raise ValueError("operations must include at least one mapping entry")

    normalized_anchors = tuple(
        _normalize_rollback_anchor(payload=item, index=index)
        for index, item in enumerate(rollback_anchors)
        if isinstance(item, dict)
    )
    if not normalized_anchors:
        raise ValueError("rollback_anchors must include at least one mapping entry")

    manifest: list[str] = []
    seen: set[str] = set()
    for item in [*normalized_operations, *normalized_anchors]:
        path = str(item.get("path") or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        manifest.append(path)

    stats = {
        "operation_count": len(normalized_operations),
        "add_count": sum(1 for item in normalized_operations if item["op"] == "add"),
        "update_count": sum(1 for item in normalized_operations if item["op"] == "update"),
        "delete_count": sum(1 for item in normalized_operations if item["op"] == "delete"),
        "rollback_anchor_count": len(normalized_anchors),
    }
    return PatchArtifactContractV1(
        patch_format=str(patch_format or "unified_diff").strip() or "unified_diff",
        apply_target_root=str(apply_target_root or "").strip(),
        target_file_manifest=tuple(manifest),
        operations=normalized_operations,
        rollback_anchors=normalized_anchors,
        patch_text=str(patch_text or ""),
        stats=stats,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def validate_patch_artifact_contract_v1(
    *,
    contract: PatchArtifactContractV1 | dict[str, Any],
    strict: bool = True,
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload = contract.as_dict() if isinstance(contract, PatchArtifactContractV1) else contract
    if not isinstance(payload, dict):
        raise ValueError("contract must be PatchArtifactContractV1 or a mapping payload")

    violation_details: list[dict[str, Any]] = []

    def _add_violation(
        *,
        code: str,
        field: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        violation_details.append(
            {
                "code": code,
                "severity": "error",
                "field": field,
                "message": message,
                "context": dict(context) if isinstance(context, dict) else {},
            }
        )

    if payload.get("schema_version") != PATCH_ARTIFACT_SCHEMA_VERSION:
        _add_violation(
            code="patch_artifact_schema_version_invalid",
            field="schema_version",
            message="schema_version must match patch artifact v1",
        )

    patch_format = payload.get("patch_format")
    if not isinstance(patch_format, str) or not patch_format.strip():
        _add_violation(
            code="patch_artifact_patch_format_invalid",
            field="patch_format",
            message="patch_format must be a non-empty string",
        )

    target_file_manifest = payload.get("target_file_manifest")
    if not isinstance(target_file_manifest, list):
        _add_violation(
            code="patch_artifact_target_file_manifest_invalid",
            field="target_file_manifest",
            message="target_file_manifest must be a list",
        )
        target_file_manifest = []
    manifest_paths = {
        str(item).strip().replace("\\", "/")
        for item in target_file_manifest
        if isinstance(item, str) and str(item).strip()
    }
    if strict and not manifest_paths:
        _add_violation(
            code="patch_artifact_target_file_manifest_empty",
            field="target_file_manifest",
            message="target_file_manifest must be non-empty in strict mode",
        )

    operations = payload.get("operations")
    if not isinstance(operations, list):
        _add_violation(
            code="patch_artifact_operations_invalid",
            field="operations",
            message="operations must be a list",
        )
        operations = []
    if strict and not operations:
        _add_violation(
            code="patch_artifact_operations_empty",
            field="operations",
            message="operations must be non-empty in strict mode",
        )

    for index, item in enumerate(operations):
        if not isinstance(item, dict):
            _add_violation(
                code="patch_artifact_operation_entry_invalid",
                field="operations",
                message="operations entries must be mappings",
                context={"index": index},
            )
            continue
        op = str(item.get("op") or "").strip().lower()
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if op not in PATCH_ARTIFACT_ALLOWED_OPERATIONS:
            _add_violation(
                code="patch_artifact_operation_op_invalid",
                field="operations",
                message="operation op must be add, update, or delete",
                context={"index": index, "op": op},
            )
        if not path:
            _add_violation(
                code="patch_artifact_operation_path_invalid",
                field="operations",
                message="operation path must be non-empty",
                context={"index": index},
            )
        elif manifest_paths and path not in manifest_paths:
            _add_violation(
                code="patch_artifact_operation_path_missing_from_manifest",
                field="operations",
                message="operation path must appear in target_file_manifest",
                context={"index": index, "path": path},
            )

    rollback_anchors = payload.get("rollback_anchors")
    if not isinstance(rollback_anchors, list):
        _add_violation(
            code="patch_artifact_rollback_anchors_invalid",
            field="rollback_anchors",
            message="rollback_anchors must be a list",
        )
        rollback_anchors = []
    if strict and not rollback_anchors:
        _add_violation(
            code="patch_artifact_rollback_anchors_empty",
            field="rollback_anchors",
            message="rollback_anchors must be non-empty in strict mode",
        )

    for index, item in enumerate(rollback_anchors):
        if not isinstance(item, dict):
            _add_violation(
                code="patch_artifact_rollback_anchor_entry_invalid",
                field="rollback_anchors",
                message="rollback_anchors entries must be mappings",
                context={"index": index},
            )
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if not path:
            _add_violation(
                code="patch_artifact_rollback_anchor_path_invalid",
                field="rollback_anchors",
                message="rollback anchor path must be non-empty",
                context={"index": index},
            )
        elif manifest_paths and path not in manifest_paths:
            _add_violation(
                code="patch_artifact_rollback_anchor_path_missing_from_manifest",
                field="rollback_anchors",
                message="rollback anchor path must appear in target_file_manifest",
                context={"index": index, "path": path},
            )

    violations = list(dict.fromkeys(detail["code"] for detail in violation_details))
    return {
        "ok": not violations,
        "strict": bool(strict),
        "fail_closed": bool(fail_closed),
        "violations": violations,
        "violation_details": [dict(item) for item in violation_details],
    }


__all__ = [
    "PATCH_ARTIFACT_ALLOWED_OPERATIONS",
    "PATCH_ARTIFACT_SCHEMA_VERSION",
    "PatchArtifactContractV1",
    "build_patch_artifact_contract_v1",
    "validate_patch_artifact_contract_v1",
]
