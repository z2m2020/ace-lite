from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any

from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.subprocess_utils import run_capture_output
from ace_lite.validation.result import build_validation_result_v1
from ace_lite.validation.sandbox import (
    apply_patch_artifact_in_sandbox,
    bootstrap_patch_sandbox,
    cleanup_patch_sandbox,
)

AVAILABLE_VALIDATION_PROBES = ("compile", "import", "tests")


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


def _select_compile_probe_paths(
    *,
    sandbox_root: str | Path,
    candidates: list[dict[str, Any]],
) -> list[str]:
    root_path = Path(sandbox_root)
    selected: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        rel_path = str(item.get("path") or "").strip().replace("\\", "/")
        language = str(item.get("language") or "").strip().lower()
        if not rel_path:
            continue
        if language not in {"python", "py"} and not rel_path.endswith(".py"):
            continue
        normalized = rel_path.replace("\\", "/")
        if normalized in seen:
            continue
        target_path = root_path / Path(*Path(normalized).parts)
        if not target_path.is_file():
            continue
        seen.add(normalized)
        selected.append(normalized)
    return selected


def _run_compile_probe(
    *,
    sandbox_root: str | Path,
    candidates: list[dict[str, Any]],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    selected_paths = _select_compile_probe_paths(
        sandbox_root=sandbox_root,
        candidates=candidates,
    )
    if not selected_paths:
        return []
    returncode, stdout, stderr, timed_out = run_capture_output(
        [sys.executable, "-m", "py_compile", *selected_paths],
        cwd=sandbox_root,
        timeout_seconds=max(0.1, float(timeout_seconds)),
    )
    issue_message = str(stderr or "").strip() or str(stdout or "").strip()
    issues: list[dict[str, Any]] = []
    if timed_out or int(returncode) != 0:
        issues.append(
            {
                "code": "probe.compile.timeout" if timed_out else "probe.compile.failed",
                "message": issue_message or "compile probe failed",
                "path": selected_paths[0],
                "severity": "error",
                "line": 0,
                "column": 0,
            }
        )
    return [
        {
            "name": "compile",
            "status": "failed" if issues else "passed",
            "selected": True,
            "executed": True,
            "issues": issues,
            "artifacts": [],
            "degraded_reasons": [],
            "timed_out": bool(timed_out),
        }
    ]


def _build_pytest_probe_command(
    *,
    sandbox_root: str | Path,
    command: str,
) -> list[str] | None:
    text = str(command or "").strip()
    if not text:
        return None
    try:
        tokens = shlex.split(text, posix=(sys.platform != "win32"))
    except ValueError:
        return None
    if not tokens:
        return None
    first = str(tokens[0]).strip().lower()
    args = list(tokens[1:])
    if first == "pytest":
        normalized = [sys.executable, "-m", "pytest", *args]
        pytest_args = args
    elif (
        first in {"python", "python.exe"}
        and len(args) >= 2
        and str(args[0]).strip() == "-m"
        and str(args[1]).strip() == "pytest"
    ):
        normalized = [sys.executable, *args]
        pytest_args = args[2:]
    else:
        return None

    root_path = Path(sandbox_root)
    value_flags = {"-k", "-m", "--maxfail", "--tb", "-c", "--rootdir"}
    skip_next = False
    for token in pytest_args:
        if skip_next:
            skip_next = False
            continue
        if token in value_flags:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        candidate_path = str(token).split("::", 1)[0].strip()
        if not candidate_path:
            continue
        if (root_path / Path(*Path(candidate_path).parts)).exists():
            return normalized
    return None


def _run_tests_probe(
    *,
    sandbox_root: str | Path,
    validation_tests: list[str],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    for item in validation_tests:
        command = _build_pytest_probe_command(
            sandbox_root=sandbox_root,
            command=item,
        )
        if command is None:
            continue
        returncode, stdout, stderr, timed_out = run_capture_output(
            command,
            cwd=sandbox_root,
            timeout_seconds=max(0.1, float(timeout_seconds)),
        )
        issue_message = str(stderr or "").strip() or str(stdout or "").strip()
        issues: list[dict[str, Any]] = []
        if timed_out or int(returncode) != 0:
            issues.append(
                {
                    "code": "probe.tests.timeout" if timed_out else "probe.tests.failed",
                    "message": issue_message or "tests probe failed",
                    "path": "",
                    "severity": "error",
                    "line": 0,
                    "column": 0,
                }
            )
        return [
            {
                "name": "tests",
                "status": "failed" if issues else "passed",
                "selected": True,
                "executed": True,
                "issues": issues,
                "artifacts": [],
                "degraded_reasons": [],
                "timed_out": bool(timed_out),
            }
        ]
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
    initial_result = build_validation_result_v1(
        selected_tests=[str(item) for item in validation_tests if isinstance(item, str)],
        available_probes=list(AVAILABLE_VALIDATION_PROBES),
        sandboxed=False,
        runner="disabled",
        replay_key="",
        status="skipped",
    ).as_dict()
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
        "probes": dict(initial_result.get("probes", {})),
        "result": initial_result,
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
                available_probes=list(AVAILABLE_VALIDATION_PROBES),
                sandboxed=True,
                runner="temp-tree",
                degraded_reasons=[str(apply_result.get("reason") or "apply_failed")],
                artifacts=[str(Path(session.patch_path))],
                replay_key="",
                status="failed",
            ).as_dict()
            payload["probes"] = dict(payload["result"].get("probes", {}))
            return payload

        candidates = _resolve_validation_candidates(
            source_plan_stage=source_plan_stage,
            index_stage=index_stage,
        )
        probe_results = _run_compile_probe(
            sandbox_root=session.sandbox_root,
            candidates=candidates,
            timeout_seconds=sandbox_timeout_seconds,
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
        test_probe_results = _run_tests_probe(
            sandbox_root=session.sandbox_root,
            validation_tests=[str(item) for item in validation_tests if isinstance(item, str)],
            timeout_seconds=sandbox_timeout_seconds,
        )
        probe_results.extend(test_probe_results)
        issues = _build_issue_entries(
            diagnostics=[item for item in diagnostics if isinstance(item, dict)],
            code="lsp.diagnostic",
        )
        probe_failed = any(
            int(item.get("issue_count", 0) or 0) > 0
            or str(item.get("status") or "").strip().lower() in {"failed", "degraded"}
            for item in probe_results
            if isinstance(item, dict)
        )
        payload["reason"] = "ok"
        payload["diagnostics"] = diagnostics
        payload["diagnostic_count"] = len(diagnostics)
        payload["xref"] = xref_payload
        payload["result"] = build_validation_result_v1(
            syntax_issues=issues,
            selected_tests=[str(item) for item in validation_tests if isinstance(item, str)],
            executed_tests=[str(item) for item in validation_tests if isinstance(item, str)][:1]
            if test_probe_results
            else [],
            probes=probe_results,
            available_probes=list(AVAILABLE_VALIDATION_PROBES),
            sandboxed=True,
            runner="temp-tree",
            artifacts=[str(Path(session.patch_path))],
            replay_key="",
            status="passed" if (not issues and not probe_failed) else "failed",
        ).as_dict()
        payload["probes"] = dict(payload["result"].get("probes", {}))
        return payload
    finally:
        cleanup_result = cleanup_patch_sandbox(session)
        payload["sandbox"]["cleanup_ok"] = bool(cleanup_result.get("ok", False))


__all__ = ["run_validation_stage"]
