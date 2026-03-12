from __future__ import annotations

from typing import Any

import pytest

from ace_lite.schema import (
    SCHEMA_VERSION,
    validate_context_plan,
    validate_validation_result_payload,
)
from ace_lite.validation.result import build_validation_result_v1


def _valid_payload() -> dict[str, Any]:
    payload = {
        "schema_version": "3.0",
        "query": "q",
        "repo": "r",
        "root": "/tmp/repo",
        "pipeline_order": [
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
        ],
        "conventions": {},
        "memory": {},
        "index": {},
        "repomap": {},
        "augment": {},
        "skills": {},
        "source_plan": {
            "writeback_template": {
                "metadata": {
                    "repo": "r",
                    "branch": "",
                    "path": "",
                    "topic": "",
                    "module": "",
                    "updated_at": "",
                    "app": "codex",
                }
            }
        },
        "observability": {"stage_metrics": []},
    }
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def test_schema_version_is_3_2() -> None:
    assert SCHEMA_VERSION == "3.2"


def test_validate_context_plan_accepts_valid_payload() -> None:
    payload = _valid_payload()
    validate_context_plan(payload)


def test_validate_context_plan_rejects_missing_required_field() -> None:
    payload = _valid_payload()
    payload.pop("query")

    with pytest.raises(ValueError, match="missing required top-level field"):
        validate_context_plan(payload)


def test_validate_context_plan_rejects_wrong_schema_version() -> None:
    payload = _valid_payload()
    payload["schema_version"] = "1.0"

    with pytest.raises(ValueError, match="unexpected schema_version"):
        validate_context_plan(payload)


def test_validate_context_plan_rejects_missing_stage_metrics() -> None:
    payload = _valid_payload()
    payload["observability"] = {}

    with pytest.raises(ValueError, match=r"observability\.stage_metrics"):
        validate_context_plan(payload)


def test_validate_context_plan_accepts_plugin_policy_summary() -> None:
    payload = _valid_payload()
    payload["observability"]["plugin_policy_summary"] = {
        "mode": "strict",
        "allowlist": ["observability.mcp_plugins"],
        "totals": {
            "applied": 1,
            "conflicts": 0,
            "blocked": 0,
            "warn": 0,
            "remote_applied": 0,
        },
        "by_stage": [
            {
                "stage": "source_plan",
                "applied": 1,
                "conflicts": 0,
                "blocked": 0,
                "warn": 0,
                "remote_applied": 0,
            }
        ],
    }

    validate_context_plan(payload)


def test_validate_context_plan_rejects_invalid_plugin_policy_summary_totals() -> None:
    payload = _valid_payload()
    payload["observability"]["plugin_policy_summary"] = {
        "mode": "strict",
        "allowlist": ["observability.mcp_plugins"],
        "totals": {
            "applied": "bad",
            "conflicts": 0,
            "blocked": 0,
            "warn": 0,
            "remote_applied": 0,
        },
        "by_stage": [],
    }

    with pytest.raises(
        ValueError,
        match=r"observability\.plugin_policy_summary\.totals\.applied must be numeric",
    ):
        validate_context_plan(payload)


def test_validate_context_plan_accepts_chunk_references() -> None:
    payload = _valid_payload()
    payload["index"]["candidate_chunks"] = [
        {
            "path": "src/app.py",
            "qualified_name": "Auth.validate",
            "kind": "method",
            "lineno": 10,
            "end_lineno": 20,
            "disclosure": "skeleton_light",
            "skeleton": {
                "schema_version": "y2-freeze-v1",
                "mode": "skeleton_light",
                "language": "python",
                "module": "src.app",
                "symbol": {
                    "name": "validate",
                    "qualified_name": "Auth.validate",
                    "kind": "method",
                },
                "span": {
                    "start_line": 10,
                    "end_line": 20,
                    "line_count": 11,
                },
                "anchors": {
                    "path": "src/app.py",
                    "signature": "def validate(token: str) -> bool:",
                    "robust_signature_available": True,
                },
            },
        }
    ]
    payload["source_plan"]["candidate_chunks"] = list(payload["index"]["candidate_chunks"])
    payload["source_plan"]["chunk_steps"] = [
        {
            "action": "Inspect chunk before opening full file",
            "chunk_ref": payload["index"]["candidate_chunks"][0],
        }
    ]
    payload["source_plan"]["validation_tests"] = ["tests.test_auth::test_token"]

    validate_context_plan(payload)


def test_validate_context_plan_rejects_invalid_chunk_steps() -> None:
    payload = _valid_payload()
    payload["source_plan"]["chunk_steps"] = [
        {"action": 123, "chunk_ref": {"path": "src/app.py"}}
    ]

    with pytest.raises(ValueError, match=r"source_plan\.chunk_steps"):
        validate_context_plan(payload)


def test_validate_context_plan_rejects_invalid_validation_tests() -> None:
    payload = _valid_payload()
    payload["source_plan"]["validation_tests"] = [123]

    with pytest.raises(ValueError, match=r"source_plan\.validation_tests"):
        validate_context_plan(payload)


def test_validate_context_plan_accepts_optional_validation_result_payload() -> None:
    payload = _valid_payload()
    payload["source_plan"]["validation_result"] = build_validation_result_v1(
        replay_key="validation-run-001",
        selected_tests=["tests/test_auth.py::test_token"],
        executed_tests=["tests/test_auth.py::test_token"],
    ).as_dict()

    validate_context_plan(payload)


def test_validate_validation_result_payload_rejects_invalid_summary_status() -> None:
    payload = build_validation_result_v1(replay_key="validation-run-001").as_dict()
    payload["summary"]["status"] = "mystery"

    with pytest.raises(
        ValueError,
        match=r"validation_result\.summary\.status",
    ):
        validate_validation_result_payload(payload, prefix="validation_result")
