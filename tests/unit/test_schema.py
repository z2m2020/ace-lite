from __future__ import annotations

import copy
from typing import Any

import pytest

from ace_lite.pipeline.contracts import validate_stage_output
from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.types import StageContext
from ace_lite.schema import (
    SCHEMA_VERSION,
    validate_context_plan,
    validate_validation_result_payload,
)
from ace_lite.validation.result import build_validation_result_v1


def _valid_payload() -> dict[str, Any]:
    validation_result = build_validation_result_v1(
        replay_key="validation-run-001",
        selected_tests=[],
        available_probes=["compile", "import", "tests"],
        sandboxed=False,
        runner="disabled",
        status="skipped",
    ).as_dict()
    payload = {
        "schema_version": "3.3",
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
            "validation",
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
        "validation": {
            "enabled": False,
            "reason": "disabled",
            "sandbox": {
                "enabled": False,
                "sandbox_root": "",
                "patch_applied": False,
                "cleanup_ok": False,
                "restore_ok": False,
                "apply_result": {},
            },
            "diagnostics": [],
            "diagnostic_count": 0,
            "xref_enabled": False,
            "xref": {
                "count": 0,
                "results": [],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 0.0,
                "time_budget_ms": 0,
            },
            "probes": dict(validation_result.get("probes", {})),
            "result": validation_result,
            "patch_artifact_present": False,
            "policy_name": "general",
            "policy_version": "v1",
        },
        "observability": {"stage_metrics": []},
    }
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def _build_source_plan_payload_with_internal_sidecars() -> dict[str, Any]:
    ctx = StageContext(query="trace schema roundtrip boundary", repo="r", root="/tmp/repo")
    ctx.state = {
        "memory": {},
        "index": {
            "candidate_files": [{"path": "src/app.py"}],
            "candidate_chunks": [
                {
                    "path": "src/app.py",
                    "qualified_name": "Auth.validate",
                    "kind": "method",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 9.5,
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
                    "_retrieval_context": "module=src.app\nsymbol=Auth.validate",
                    "_contextual_chunking_sidecar": {
                        "schema_version": "contextual_chunking_sidecar_v1",
                        "symbol_path": "src.app:Auth.validate",
                        "module_hint": "src.app",
                        "import_hints": ["typing.Any"],
                    },
                    "_robust_signature_lite": {
                        "available": True,
                        "compatibility_domain": "src/app.py::method",
                    },
                    "_topological_shield": {"enabled": True, "attenuation": 0.2},
                }
            ],
            "chunk_metrics": {"chunk_budget_used": 48.0},
        },
        "repomap": {"focused_files": ["src/app.py"]},
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {"suspicious_chunks": [], "suggested_tests": []},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }
    return run_source_plan(
        ctx=ctx,
        pipeline_order=[
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
        ],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="skeleton_light",
        policy_version="v1",
    )


def test_schema_version_is_3_3() -> None:
    assert SCHEMA_VERSION == "3.3"


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


def test_validate_context_plan_accepts_source_plan_roundtrip_without_internal_sidecar_leaks() -> None:
    payload = _valid_payload()
    source_plan = _build_source_plan_payload_with_internal_sidecars()

    validate_stage_output("source_plan", source_plan)

    payload["source_plan"] = copy.deepcopy(source_plan)
    validate_context_plan(payload)

    assert len(source_plan["candidate_chunks"]) == 1
    candidate = source_plan["candidate_chunks"][0]
    chunk_ref = source_plan["chunk_steps"][0]["chunk_ref"]
    source_plan_step = next(
        item for item in source_plan["steps"] if item.get("stage") == "source_plan"
    )
    assert source_plan["card_summary"] == {
        "schema_version": "y7503-card-v1",
        "evidence_card_count": 1,
        "file_card_count": 1,
        "chunk_card_count": 1,
        "validation_card_present": False,
    }
    assert source_plan["evidence_cards"][0]["topic"] == "retrieval_grounding"
    assert source_plan["file_cards"][0]["card_id"] == "file:src/app.py"
    assert source_plan["chunk_cards"][0]["card_id"] == "src/app.py:Auth.validate:10-20"

    for forbidden_key in (
        "_retrieval_context",
        "_contextual_chunking_sidecar",
        "_robust_signature_lite",
        "_topological_shield",
    ):
        assert forbidden_key not in candidate
        assert forbidden_key not in chunk_ref
        assert forbidden_key not in source_plan_step["candidate_chunks"][0]


def test_validate_context_plan_rejects_invalid_source_plan_card_summary() -> None:
    payload = _valid_payload()
    payload["source_plan"]["card_summary"] = {
        "schema_version": "y7503-card-v1",
        "evidence_card_count": "bad",
        "file_card_count": 1,
        "chunk_card_count": 1,
        "validation_card_present": False,
    }

    with pytest.raises(
        ValueError,
        match=r"source_plan\.card_summary\.evidence_card_count must be numeric",
    ):
        validate_context_plan(payload)


def test_validate_context_plan_rejects_invalid_validation_stage_payload() -> None:
    payload = _valid_payload()
    payload["validation"]["result"]["summary"]["status"] = "mystery"

    with pytest.raises(
        ValueError,
        match=r"validation\.result\.summary\.status",
    ):
        validate_context_plan(payload)


def test_validate_validation_result_payload_rejects_invalid_summary_status() -> None:
    payload = build_validation_result_v1(replay_key="validation-run-001").as_dict()
    payload["summary"]["status"] = "mystery"

    with pytest.raises(
        ValueError,
        match=r"validation_result\.summary\.status",
    ):
        validate_validation_result_payload(payload, prefix="validation_result")
