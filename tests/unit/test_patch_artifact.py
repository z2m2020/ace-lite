from __future__ import annotations

from ace_lite.validation.patch_artifact import (
    PATCH_ARTIFACT_SCHEMA_VERSION,
    build_patch_artifact_contract_v1,
    validate_patch_artifact_contract_v1,
)


def test_build_patch_artifact_contract_supports_add_update_delete_and_rollback() -> None:
    contract = build_patch_artifact_contract_v1(
        operations=[
            {"op": "add", "path": "src/new_file.py", "after_sha256": "a1", "hunk_count": 1},
            {
                "op": "update",
                "path": "src/existing.py",
                "before_sha256": "b1",
                "after_sha256": "b2",
                "hunk_count": 2,
            },
            {"op": "delete", "path": "src/old_file.py", "before_sha256": "c1"},
        ],
        rollback_anchors=[
            {"path": "src/new_file.py", "strategy": "delete_added_file", "anchor": "post-apply"},
            {"path": "src/existing.py", "strategy": "git_restore", "anchor": "HEAD"},
            {"path": "src/old_file.py", "strategy": "git_restore", "anchor": "HEAD"},
        ],
        patch_text="diff --git a/src/existing.py b/src/existing.py",
        apply_target_root="/tmp/sandbox",
        metadata={"source": "unit-test"},
    ).as_dict()

    assert contract["schema_version"] == PATCH_ARTIFACT_SCHEMA_VERSION
    assert contract["target_file_manifest"] == [
        "src/new_file.py",
        "src/existing.py",
        "src/old_file.py",
    ]
    assert contract["stats"] == {
        "operation_count": 3,
        "add_count": 1,
        "update_count": 1,
        "delete_count": 1,
        "rollback_anchor_count": 3,
    }


def test_validate_patch_artifact_contract_rejects_invalid_operation() -> None:
    payload = {
        "schema_version": PATCH_ARTIFACT_SCHEMA_VERSION,
        "patch_format": "unified_diff",
        "apply_target_root": "/tmp/sandbox",
        "target_file_manifest": ["src/app.py"],
        "operations": [{"op": "rename", "path": "src/app.py"}],
        "rollback_anchors": [{"path": "src/app.py", "strategy": "git_restore", "anchor": "HEAD"}],
        "patch_text": "",
        "stats": {},
        "metadata": {},
    }

    result = validate_patch_artifact_contract_v1(
        contract=payload,
        strict=True,
        fail_closed=True,
    )

    assert result["ok"] is False
    assert "patch_artifact_operation_op_invalid" in result["violations"]
