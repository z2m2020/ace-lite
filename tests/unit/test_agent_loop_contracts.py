from __future__ import annotations

import pytest

from ace_lite.agent_loop.contracts import (
    AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION,
    build_agent_loop_branch_batch_v1,
    build_agent_loop_action_v1,
    validate_agent_loop_branch_batch_v1,
    validate_agent_loop_action_v1,
)


def test_build_agent_loop_action_v1_normalizes_request_more_context() -> None:
    action = build_agent_loop_action_v1(
        action_type="request_more_context",
        reason="validation_diagnostics",
        query_hint="focus auth paths",
        focus_paths=["src\\auth.py", "src/auth.py", "src/session.py"],
        selected_tests=[
            "pytest -q tests/unit/test_auth.py",
            "pytest -q tests/unit/test_auth.py",
        ],
    ).as_dict()

    assert action["action_type"] == "request_more_context"
    assert action["focus_paths"] == ["src/auth.py", "src/session.py"]
    assert action["selected_tests"] == ["pytest -q tests/unit/test_auth.py"]


def test_validate_agent_loop_action_v1_rejects_missing_reason() -> None:
    result = validate_agent_loop_action_v1(
        contract={
            "schema_version": "agent_loop_action_v1",
            "action_type": "request_validation_retry",
            "reason": "",
            "query_hint": "",
            "focus_paths": [],
            "selected_tests": [],
            "metadata": {},
        }
    )

    assert result["ok"] is False
    assert "agent_loop_action_reason_invalid" in result["violations"]


def test_request_more_context_requires_query_hint_or_focus_paths() -> None:
    with pytest.raises(ValueError, match="requires query_hint or focus_paths"):
        build_agent_loop_action_v1(
            action_type="request_more_context",
            reason="need more detail",
        )


def test_build_agent_loop_branch_batch_v1_normalizes_candidates() -> None:
    batch = build_agent_loop_branch_batch_v1(
        candidates=[
            {
                "branch_id": "branch-a",
                "patch_scope_lines": 12,
                "artifact_refs": ["artifacts\\a.json", "artifacts/a.json"],
                "validation_branch_score": {"score": 10.0, "passed": True},
            }
        ],
        metadata={"source": "report_only"},
    ).as_dict()

    assert batch["schema_version"] == AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION
    assert batch["candidate_count"] == 1
    assert batch["candidates"][0]["artifact_refs"] == ["artifacts/a.json"]
    assert batch["metadata"]["source"] == "report_only"


def test_validate_agent_loop_branch_batch_v1_rejects_duplicate_branch_ids() -> None:
    result = validate_agent_loop_branch_batch_v1(
        contract={
            "schema_version": AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION,
            "candidate_count": 2,
            "candidates": [
                {
                    "branch_id": "branch-a",
                    "patch_scope_lines": 1,
                    "artifact_refs": [],
                    "validation_branch_score": {},
                },
                {
                    "branch_id": "branch-a",
                    "patch_scope_lines": 2,
                    "artifact_refs": [],
                    "validation_branch_score": {},
                },
            ],
            "metadata": {},
        }
    )

    assert result["ok"] is False
    assert "agent_loop_branch_batch_branch_id_duplicate" in result["violations"]
