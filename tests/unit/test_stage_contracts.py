from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.contracts import validate_stage_output
from ace_lite.pipeline.registry import CORE_PIPELINE_ORDER, StageRegistry, get_stage_descriptor


def _build_sample_repo(tmp_path: Path) -> Path:
    root = tmp_path
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app" / "core.py").write_text(
        textwrap.dedent(
            """
            def process_data(input: str) -> str:
                return input.upper()
            """
        ).strip()
        + "\\n",
        encoding="utf-8",
    )
    return root


def _build_orchestrator(index_cache_path: Path) -> AceOrchestrator:
    return AceOrchestrator(
        config=OrchestratorConfig(
            index={
                "languages": ["python"],
                "cache_path": str(index_cache_path),
            },
            repomap={"enabled": False},
            lsp={"enabled": False},
            cochange={"enabled": False},
            plugins={"enabled": False},
        )
    )


def test_validate_stage_output_ignores_unknown_stage() -> None:
    validate_stage_output("unknown", {"ok": True})


def test_core_pipeline_order_matches_known_stage_descriptors() -> None:
    assert CORE_PIPELINE_ORDER == (
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
        "source_plan",
        "validation",
    )
    assert get_stage_descriptor("source_plan") is not None
    assert get_stage_descriptor("unknown") is None


def test_stage_registry_exposes_descriptor_lookup() -> None:
    registry = StageRegistry()

    assert registry.has_descriptor("memory") is True
    assert registry.has_descriptor("unknown") is False


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


@pytest.mark.parametrize(
    ("stage_name", "payload", "expected_reason"),
    [
        (
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
            },
            "source_plan.writeback_template",
        ),
        (
            "validation",
            {
                "enabled": False,
                "reason": "disabled",
                "sandbox": {},
                "diagnostics": [],
                "diagnostic_count": 0,
                "xref_enabled": False,
                "xref": {},
                "patch_artifact_present": False,
                "policy_name": "general",
                "policy_version": "v1",
            },
            "validation.result",
        ),
    ],
)
def test_validate_stage_output_missing_contract_keys_for_source_plan_and_validation(
    stage_name: str,
    payload: dict[str, object],
    expected_reason: str,
) -> None:
    with pytest.raises(StageContractError) as exc_info:
        validate_stage_output(stage_name, payload)

    exc = exc_info.value
    assert exc.error_code == "stage_contract.missing_key"
    assert exc.reason == expected_reason


@pytest.mark.parametrize(
    ("stage_name", "payload", "expected_reason"),
    [
        (
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
                "writeback_template": [],
            },
            "source_plan.writeback_template",
        ),
        (
            "validation",
            {
                "enabled": False,
                "reason": "disabled",
                "sandbox": {},
                "diagnostics": [],
                "diagnostic_count": 0,
                "xref_enabled": False,
                "xref": {},
                "result": [],
                "patch_artifact_present": False,
                "policy_name": "general",
                "policy_version": "v1",
            },
            "validation.result",
        ),
    ],
)
def test_validate_stage_output_rejects_invalid_contract_container_types(
    stage_name: str,
    payload: dict[str, object],
    expected_reason: str,
) -> None:
    with pytest.raises(StageContractError) as exc_info:
        validate_stage_output(stage_name, payload)

    exc = exc_info.value
    assert exc.error_code == "stage_contract.invalid_type"
    assert exc.reason == expected_reason


def test_validate_stage_output_rejects_invalid_source_plan_patch_artifacts_type() -> None:
    with pytest.raises(StageContractError) as exc_info:
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
                "patch_artifacts": {},
            },
        )

    exc = exc_info.value
    assert exc.error_code == "stage_contract.invalid_type"
    assert exc.reason == "source_plan.patch_artifacts"


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


def test_validate_stage_output_accepts_live_orchestrator_stage_payloads(
    tmp_path: Path,
) -> None:
    root = _build_sample_repo(tmp_path)
    orchestrator = _build_orchestrator(root / "context-map" / "index.json")

    payload = orchestrator.plan(
        query="fix bug in process_data",
        repo="test-repo",
        root=str(root),
    )

    for stage_name in AceOrchestrator.PIPELINE_ORDER:
        validate_stage_output(stage_name, payload[stage_name])
