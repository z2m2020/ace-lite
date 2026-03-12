from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.validation.result import build_validation_result_v1
from ace_lite.validation.sandbox import (
    apply_patch_artifact_in_sandbox,
    bootstrap_patch_sandbox,
    cleanup_patch_sandbox,
)


def _build_issue_entries(
    *,
    diagnostics: list[dict[str, Any]],
    code: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        issues.append(
            {
                "code": code,
                "message": str(item.get("message") or "").strip() or code,
                "path": str(item.get("path") or "").strip(),
                "severity": str(item.get("severity") or "error").strip() or "error",
                "line": int(item.get("line", 0) or 0),
                "column": int(item.get("column", 0) or 0),
            }
        )
    return issues


def _resolve_validation_candidates(
    *,
    source_plan_stage: dict[str, Any],
    index_stage: dict[str, Any],
) -> list[dict[str, Any]]:
    source_candidates = source_plan_stage.get("candidate_files", [])
    if isinstance(source_candidates, list) and source_candidates:
        return [item for item in source_candidates if isinstance(item, dict)]
    index_candidates = index_stage.get("candidate_files", [])
    if isinstance(index_candidates, list):
        return [item for item in index_candidates if isinstance(item, dict)]
    return []


def run_validation_stage(
    *,
    root: str,
    query: str,
    source_plan_stage: dict[str, Any],
    index_stage: dict[str, Any],
    enabled: bool,
    include_xref: bool,
    top_n: int,
    xref_top_n: int,
    sandbox_timeout_seconds: float,
    broker: LspDiagnosticsBroker | None,
    patch_artifact: dict[str, Any] | None = None,
    policy_name: str = "general",
    policy_version: str = "v1",
) -> dict[str, Any]:
    selected_patch_artifact = (
        dict(patch_artifact)
        if isinstance(patch_artifact, dict)
        else (
            dict(source_plan_stage.get("patch_artifact"))
            if isinstance(source_plan_stage.get("patch_artifact"), dict)
            else {}
        )
    )
    validation_tests = (
        source_plan_stage.get("validation_tests", [])
        if isinstance(source_plan_stage.get("validation_tests"), list)
        else []
    )
    payload = {
        "enabled": bool(enabled),
        "reason": "disabled" if not enabled else "not_reached",
        "sandbox": {
            "enabled": bool(enabled),
            "sandbox_root": "",
            "patch_applied": False,
            "cleanup_ok": False,
            "restore_ok": False,
            "apply_result": {},
        },
        "diagnostics": [],
        "diagnostic_count": 0,
        "xref_enabled": bool(include_xref),
        "xref": {
            "count": 0,
            "results": [],
            "errors": [],
            "budget_exhausted": False,
            "elapsed_ms": 0.0,
            "time_budget_ms": max(1, int(sandbox_timeout_seconds * 1000)),
        },
        "result": build_validation_result_v1(
            selected_tests=[str(item) for item in validation_tests if isinstance(item, str)],
            sandboxed=False,
            runner="disabled",
            replay_key="",
            status="skipped",
        ).as_dict(),
        "patch_artifact_present": bool(selected_patch_artifact),
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
    }
    if not enabled:
        return payload
    if broker is None:
        payload["reason"] = "broker_unavailable"
        return payload
    if not selected_patch_artifact:
        payload["reason"] = "patch_artifact_missing"
        return payload

    session = bootstrap_patch_sandbox(
        repo_root=root,
        patch_artifact=selected_patch_artifact,
    )
    apply_result = apply_patch_artifact_in_sandbox(
        session=session,
        timeout_seconds=sandbox_timeout_seconds,
    )
    payload["sandbox"]["enabled"] = True
    payload["sandbox"]["sandbox_root"] = str(session.sandbox_root)
    payload["sandbox"]["apply_result"] = dict(apply_result)
    payload["sandbox"]["patch_applied"] = bool(apply_result.get("ok", False))

    try:
        if not apply_result.get("ok", False):
            payload["reason"] = "patch_apply_failed"
            payload["result"] = build_validation_result_v1(
                selected_tests=[str(item) for item in validation_tests if isinstance(item, str)],
                sandboxed=True,
                runner="temp-tree",
                degraded_reasons=[str(apply_result.get("reason") or "apply_failed")],
                artifacts=[str(Path(session.patch_path))],
                replay_key="",
                status="failed",
            ).as_dict()
            return payload

        candidates = _resolve_validation_candidates(
            source_plan_stage=source_plan_stage,
            index_stage=index_stage,
        )
        diagnostics_payload = broker.collect(
            root=session.sandbox_root,
            candidate_files=candidates,
            top_n=top_n,
        )
        xref_payload = (
            broker.collect_xref(
                root=session.sandbox_root,
                query=query,
                candidate_files=candidates,
                top_n=xref_top_n,
                time_budget_ms=max(1, int(sandbox_timeout_seconds * 1000)),
            )
            if include_xref
            else {
                "count": 0,
                "results": [],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 0.0,
                "time_budget_ms": max(1, int(sandbox_timeout_seconds * 1000)),
            }
        )
        diagnostics = (
            diagnostics_payload.get("diagnostics", [])
            if isinstance(diagnostics_payload.get("diagnostics"), list)
            else []
        )
        issues = _build_issue_entries(
            diagnostics=[item for item in diagnostics if isinstance(item, dict)],
            code="lsp.diagnostic",
        )
        payload["reason"] = "ok"
        payload["diagnostics"] = diagnostics
        payload["diagnostic_count"] = len(diagnostics)
        payload["xref"] = xref_payload
        payload["result"] = build_validation_result_v1(
            syntax_issues=issues,
            selected_tests=[str(item) for item in validation_tests if isinstance(item, str)],
            sandboxed=True,
            runner="temp-tree",
            artifacts=[str(Path(session.patch_path))],
            replay_key="",
            status="passed" if not issues else "failed",
        ).as_dict()
        return payload
    finally:
        cleanup_result = cleanup_patch_sandbox(session)
        payload["sandbox"]["cleanup_ok"] = bool(cleanup_result.get("ok", False))


__all__ = ["run_validation_stage"]
