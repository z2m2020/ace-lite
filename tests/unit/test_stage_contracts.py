from __future__ import annotations

import pytest

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.contracts import validate_stage_output


def test_validate_stage_output_ignores_unknown_stage() -> None:
    validate_stage_output("unknown", {"ok": True})


def test_validate_stage_output_accepts_minimal_valid_payloads() -> None:
    validate_stage_output(
        "memory",
        {
            "query": "q",
            "count": 0,
            "hits_preview": [],
            "channel_used": "none",
            "strategy": "semantic",
            "namespace": {},
            "timeline": {},
            "cache": {},
            "notes": {},
            "disclosure": {},
            "cost": {},
            "profile": {},
            "capture": {},
        },
    )

    validate_stage_output(
        "index",
        {
            "repo": "r",
            "root": "/tmp",
            "terms": [],
            "targets": [],
            "module_hint": "",
            "index_hash": "h",
            "file_count": 0,
            "cache": {},
            "candidate_files": [],
            "candidate_chunks": [],
            "chunk_metrics": {},
            "docs": {},
            "worktree_prior": {},
            "cochange": {},
            "embeddings": {},
            "policy_name": "general",
            "policy_version": "v1",
        },
    )

    validate_stage_output(
        "repomap",
        {
            "enabled": True,
            "focused_files": [],
            "seed_paths": [],
            "neighbor_paths": [],
            "dependency_recall": {},
            "markdown": "",
            "ranking_profile": "graph",
            "policy_name": "general",
            "policy_version": "v1",
            "neighbor_limit": 0,
            "neighbor_depth": 1,
            "budget_tokens": 0,
            "repomap_enabled_effective": True,
            "cache": {},
            "precompute": {},
        },
    )

    validate_stage_output(
        "augment",
        {
            "enabled": False,
            "count": 0,
            "diagnostics": [],
            "errors": [],
            "vcs_history": {},
            "vcs_worktree": {},
            "xref_enabled": False,
            "xref": {},
            "tests": {},
            "policy_name": "general",
            "policy_version": "v1",
        },
    )

    validate_stage_output(
        "skills",
        {
            "query_ctx": {},
            "available_count": 0,
            "selected": [],
        },
    )

    validate_stage_output(
        "source_plan",
        {
            "repo": "r",
            "root": "/tmp",
            "query": "q",
            "stages": [],
            "constraints": [],
            "diagnostics": [],
            "xref": {},
            "tests": {},
            "validation_tests": [],
            "candidate_chunks": [],
            "chunk_steps": [],
            "chunk_budget_used": 0,
            "chunk_budget_limit": 0,
            "chunk_disclosure": "refs",
            "policy_name": "general",
            "policy_version": "v1",
            "steps": [],
            "writeback_template": {},
        },
    )

    validate_stage_output(
        "validation",
        {
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
            "xref": {},
            "result": {
                "schema_version": "validation_result_v1",
                "syntax": {"ok": True, "issues": [], "issue_count": 0},
                "type": {"ok": True, "issues": [], "issue_count": 0},
                "tests": {
                    "ok": True,
                    "issues": [],
                    "issue_count": 0,
                    "selected": [],
                    "executed": [],
                },
                "environment": {
                    "ok": True,
                    "sandboxed": False,
                    "runner": "disabled",
                    "artifacts": [],
                    "degraded_reasons": [],
                },
                "summary": {
                    "ok": True,
                    "status": "skipped",
                    "issue_count": 0,
                    "replay_key": "",
                    "artifact_refs": [],
                    "comparison_key": "abc123",
                },
            },
            "patch_artifact_present": False,
            "policy_name": "general",
            "policy_version": "v1",
        },
    )


def test_validate_stage_output_missing_key_has_stable_code_and_reason() -> None:
    with pytest.raises(StageContractError) as exc_info:
        validate_stage_output("memory", {"count": 0})

    exc = exc_info.value
    assert exc.error_code == "stage_contract.missing_key"
    assert exc.reason == "memory.query"


def test_orchestrator_plan_includes_contract_error_payload(tmp_path, monkeypatch) -> None:
    orchestrator = AceOrchestrator(config=OrchestratorConfig())

    def fake_execute_stage(**kwargs):
        stage_name = str(kwargs.get("stage_name") or "")
        raise StageContractError(
            "boom",
            stage=stage_name,
            error_code="stage_contract.invalid_type",
            reason=f"{stage_name}.output",
            context={"type": "list"},
        )

    monkeypatch.setattr(orchestrator._plugin_runtime, "execute_stage", fake_execute_stage)

    payload = orchestrator.plan(query="q", repo="r", root=str(tmp_path))

    error = payload["observability"]["error"]
    assert error["type"] == "stage_contract_error"
    assert error["error_code"] == "stage_contract.invalid_type"
    assert error["reason"] == "memory.output"
