from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any

from ace_lite.agent_loop.contracts import build_agent_loop_branch_batch_v1
from ace_lite.concurrency import LaneConfig, LanePool
from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
from ace_lite.preference_capture_store import (
    record_branch_outcome_preference_capture,
)
from ace_lite.subprocess_utils import run_capture_output
from ace_lite.validation.patch_artifact import validate_patch_artifact_contract_v1
from ace_lite.validation.result import (
    build_validation_result_v1,
    score_validation_branch_result_v1,
    select_best_validation_branch_candidate_v1,
)
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


def _select_valid_patch_artifact(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    validation = validate_patch_artifact_contract_v1(
        contract=candidate,
        strict=True,
        fail_closed=True,
    )
    if not validation.get("ok", False):
        return {}
    return dict(candidate)


def _select_source_plan_patch_artifact(source_plan_stage: dict[str, Any]) -> dict[str, Any]:
    direct = _select_valid_patch_artifact(source_plan_stage.get("patch_artifact"))
    if direct:
        return direct
    multi = source_plan_stage.get("patch_artifacts")
    if not isinstance(multi, list):
        return {}
    for item in multi:
        selected = _select_valid_patch_artifact(item)
        if selected:
            return selected
    return {}


def _patch_artifact_identity(candidate: dict[str, Any]) -> tuple[
    str,
    tuple[str, ...],
    tuple[tuple[str, str], ...],
    str,
]:
    manifest = tuple(
        str(path).strip().replace("\\", "/")
        for path in candidate.get("target_file_manifest", [])
        if isinstance(path, str) and str(path).strip()
    )
    operations = tuple(
        (
            str(entry.get("op") or "").strip(),
            str(entry.get("path") or "").strip().replace("\\", "/"),
        )
        for entry in candidate.get("operations", [])
        if isinstance(entry, dict)
    )
    return (
        str(candidate.get("schema_version") or "").strip(),
        manifest,
        operations,
        str(candidate.get("patch_text") or ""),
    )


def _collect_validation_patch_artifacts(
    *,
    patch_artifact: dict[str, Any] | None,
    source_plan_stage: dict[str, Any],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], tuple[tuple[str, str], ...], str]] = set()
    raw_candidates: list[Any] = [patch_artifact, source_plan_stage.get("patch_artifact")]
    multi = source_plan_stage.get("patch_artifacts")
    if isinstance(multi, list):
        raw_candidates.extend(multi)
    for item in raw_candidates:
        candidate = _select_valid_patch_artifact(item)
        if not candidate:
            continue
        identity = _patch_artifact_identity(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(candidate)
    return selected


def _estimate_patch_scope_lines(patch_artifact: dict[str, Any]) -> int:
    operations = patch_artifact.get("operations", [])
    if not isinstance(operations, list):
        return 0
    hunk_count = sum(
        max(0, int(item.get("hunk_count", 0) or 0))
        for item in operations
        if isinstance(item, dict)
    )
    if hunk_count > 0:
        return hunk_count
    return sum(1 for item in operations if isinstance(item, dict))


def _decorate_validation_payload_with_branch_artifacts(
    *,
    payload: dict[str, Any],
    branch_candidates: list[dict[str, Any]],
    branch_selection: dict[str, Any],
    patch_artifacts_by_branch: dict[str, dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    winner_branch_id = str(branch_selection.get("winner_branch_id") or "").strip()
    selected_patch_artifact = patch_artifacts_by_branch.get(winner_branch_id, {})
    rejected_rows_raw = (
        branch_selection.get("rejected", [])
        if isinstance(branch_selection.get("rejected"), list)
        else []
    )
    rejected_patch_artifacts: list[dict[str, Any]] = []
    rejected_artifact_refs: dict[str, list[str]] = {}
    ordered_patch_artifacts: list[dict[str, Any]] = []

    if isinstance(selected_patch_artifact, dict) and selected_patch_artifact:
        payload["patch_artifact"] = dict(selected_patch_artifact)
        ordered_patch_artifacts.append(dict(selected_patch_artifact))

    for item in rejected_rows_raw:
        if not isinstance(item, dict):
            continue
        branch_id = str(item.get("branch_id") or "").strip()
        if not branch_id:
            continue
        patch_artifact = patch_artifacts_by_branch.get(branch_id, {})
        rejected_row = {
            "branch_id": branch_id,
            "rejected_reason": str(item.get("rejected_reason") or "").strip(),
            "patch_artifact": dict(patch_artifact) if isinstance(patch_artifact, dict) else {},
        }
        rejected_artifact_refs[branch_id] = [
            f"validation.rejected_patch_artifacts[{len(rejected_patch_artifacts)}].patch_artifact"
        ]
        rejected_patch_artifacts.append(rejected_row)
        if rejected_row["patch_artifact"]:
            ordered_patch_artifacts.append(dict(rejected_row["patch_artifact"]))

    if ordered_patch_artifacts:
        payload["patch_artifacts"] = ordered_patch_artifacts
    if rejected_patch_artifacts:
        payload["rejected_patch_artifacts"] = rejected_patch_artifacts
    if winner_branch_id:
        payload["selected_branch_id"] = winner_branch_id

    branch_batch_candidates: list[dict[str, Any]] = []
    for candidate in branch_candidates:
        if not isinstance(candidate, dict):
            continue
        branch_id = str(candidate.get("branch_id") or "").strip()
        artifact_refs: list[str] = []
        if branch_id and branch_id == winner_branch_id and selected_patch_artifact:
            artifact_refs = ["validation.patch_artifact"]
        elif branch_id:
            artifact_refs = list(rejected_artifact_refs.get(branch_id, []))
        enriched = dict(candidate)
        enriched["artifact_refs"] = artifact_refs
        branch_batch_candidates.append(enriched)

    if branch_batch_candidates:
        payload["branch_batch"] = build_agent_loop_branch_batch_v1(
            candidates=branch_batch_candidates,
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        ).as_dict()
    payload["branch_selection"] = dict(branch_selection)
    return payload


def _build_branch_outcome_preference_capture(
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    branch_selection = (
        dict(payload.get("branch_selection"))
        if isinstance(payload.get("branch_selection"), dict)
        else {}
    )
    if not branch_selection:
        return {}
    rejected = (
        branch_selection.get("rejected", [])
        if isinstance(branch_selection.get("rejected"), list)
        else []
    )
    branch_batch = (
        dict(payload.get("branch_batch"))
        if isinstance(payload.get("branch_batch"), dict)
        else {}
    )
    metadata = (
        dict(branch_batch.get("metadata"))
        if isinstance(branch_batch.get("metadata"), dict)
        else {}
    )
    patch_artifact = (
        dict(payload.get("patch_artifact"))
        if isinstance(payload.get("patch_artifact"), dict)
        else {}
    )
    target_file_manifest = [
        str(path).strip().replace("\\", "/")
        for path in patch_artifact.get("target_file_manifest", [])
        if isinstance(path, str) and str(path).strip()
    ]
    result = dict(payload.get("result")) if isinstance(payload.get("result"), dict) else {}
    summary = dict(result.get("summary")) if isinstance(result.get("summary"), dict) else {}
    rejected_patch_artifacts = (
        payload.get("rejected_patch_artifacts", [])
        if isinstance(payload.get("rejected_patch_artifacts"), list)
        else []
    )
    rejected_artifact_count = sum(
        1
        for item in rejected_patch_artifacts
        if isinstance(item, dict) and isinstance(item.get("patch_artifact"), dict) and item.get("patch_artifact")
    )
    candidate_count = max(
        0,
        int(branch_batch.get("candidate_count", 0) or 0),
    )
    rejected_rows = [dict(item) for item in rejected if isinstance(item, dict)]
    if candidate_count <= 1 or not rejected_rows:
        return {}
    return {
        "schema_version": "branch_outcome_preference_capture_v1",
        "selected_branch_id": str(
            payload.get("selected_branch_id") or branch_selection.get("winner_branch_id") or ""
        ).strip(),
        "candidate_count": candidate_count,
        "ranked_branch_ids": [
            str(item).strip()
            for item in branch_selection.get("ranked_branch_ids", [])
            if str(item).strip()
        ]
        if isinstance(branch_selection.get("ranked_branch_ids"), list)
        else [],
        "rejected_count": len(rejected_rows),
        "rejected_reasons": [
            str(item.get("rejected_reason") or "").strip()
            for item in rejected_rows
            if str(item.get("rejected_reason") or "").strip()
        ],
        "winner_patch_scope_lines": max(
            0,
            int(branch_selection.get("winner_patch_scope_lines", 0) or 0),
        ),
        "winner_status": str(summary.get("status") or "").strip(),
        "winner_artifact_present": bool(patch_artifact),
        "rejected_artifact_count": rejected_artifact_count,
        "execution_mode": str(metadata.get("execution_mode") or "").strip(),
        "candidate_origin": str(metadata.get("candidate_origin") or "").strip(),
        "source": str(metadata.get("source") or "").strip(),
        "target_file_manifest": target_file_manifest,
        "winner_validation_branch_score": (
            dict(branch_selection.get("winner_validation_branch_score"))
            if isinstance(branch_selection.get("winner_validation_branch_score"), dict)
            else {}
        ),
        "rejected": rejected_rows,
    }


def _attach_branch_outcome_preference_capture(
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    capture = _build_branch_outcome_preference_capture(payload=payload)
    if capture:
        payload["branch_outcome_preference_capture"] = capture
    return payload


def _record_branch_outcome_preference_capture(
    *,
    payload: dict[str, Any],
    store: DurablePreferenceCaptureStore | None,
    repo_key: str,
    query: str,
    user_id: str | None,
    profile_key: str | None,
) -> dict[str, Any]:
    capture = (
        dict(payload.get("branch_outcome_preference_capture"))
        if isinstance(payload.get("branch_outcome_preference_capture"), dict)
        else {}
    )
    if not capture:
        return payload
    if store is None:
        return payload
    payload["branch_outcome_preference_capture_record"] = (
        record_branch_outcome_preference_capture(
            store=store,
            repo_key=repo_key,
            query=query,
            branch_outcome_capture=capture,
            user_id=user_id,
            profile_key=profile_key,
            signal_source="runtime",
        )
    )
    return payload


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


def _build_initial_validation_payload(
    *,
    enabled: bool,
    include_xref: bool,
    sandbox_timeout_seconds: float,
    validation_tests: list[str],
    patch_artifact_present: bool,
    policy_name: str,
    policy_version: str,
) -> dict[str, Any]:
    initial_result = build_validation_result_v1(
        selected_tests=[str(item) for item in validation_tests if isinstance(item, str)],
        available_probes=list(AVAILABLE_VALIDATION_PROBES),
        sandboxed=False,
        runner="disabled",
        replay_key="",
        status="skipped",
    ).as_dict()
    return {
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
        "patch_artifact_present": bool(patch_artifact_present),
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
    }


def _run_validation_candidate(
    *,
    root: str,
    query: str,
    source_plan_stage: dict[str, Any],
    index_stage: dict[str, Any],
    include_xref: bool,
    top_n: int,
    xref_top_n: int,
    sandbox_timeout_seconds: float,
    broker: LspDiagnosticsBroker,
    patch_artifact: dict[str, Any],
    validation_tests: list[str],
    policy_name: str,
    policy_version: str,
) -> dict[str, Any]:
    payload = _build_initial_validation_payload(
        enabled=True,
        include_xref=include_xref,
        sandbox_timeout_seconds=sandbox_timeout_seconds,
        validation_tests=validation_tests,
        patch_artifact_present=True,
        policy_name=policy_name,
        policy_version=policy_version,
    )
    session = bootstrap_patch_sandbox(
        repo_root=root,
        patch_artifact=patch_artifact,
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
    preference_capture_store: DurablePreferenceCaptureStore | None = None,
    preference_capture_repo_key: str = "",
    preference_capture_user_id: str | None = None,
    preference_capture_profile_key: str | None = None,
) -> dict[str, Any]:
    validation_tests = (
        source_plan_stage.get("validation_tests", [])
        if isinstance(source_plan_stage.get("validation_tests"), list)
        else []
    )
    selected_patch_artifacts = _collect_validation_patch_artifacts(
        patch_artifact=patch_artifact,
        source_plan_stage=source_plan_stage,
    )
    payload = _build_initial_validation_payload(
        enabled=enabled,
        include_xref=include_xref,
        sandbox_timeout_seconds=sandbox_timeout_seconds,
        validation_tests=validation_tests,
        patch_artifact_present=bool(selected_patch_artifacts),
        policy_name=policy_name,
        policy_version=policy_version,
    )
    if not enabled:
        return payload
    if broker is None:
        payload["reason"] = "broker_unavailable"
        return payload
    if not selected_patch_artifacts:
        payload["reason"] = "patch_artifact_missing"
        return payload
    if len(selected_patch_artifacts) == 1:
        candidate_payload = _run_validation_candidate(
            root=root,
            query=query,
            source_plan_stage=source_plan_stage,
            index_stage=index_stage,
            include_xref=include_xref,
            top_n=top_n,
            xref_top_n=xref_top_n,
            sandbox_timeout_seconds=sandbox_timeout_seconds,
            broker=broker,
            patch_artifact=selected_patch_artifacts[0],
            validation_tests=validation_tests,
            policy_name=policy_name,
            policy_version=policy_version,
        )
        single_branch_id = "candidate-1"
        branch_candidates = [
            {
                "branch_id": single_branch_id,
                "validation_branch_score": score_validation_branch_result_v1(
                    before=dict(payload.get("result", {})),
                    after=candidate_payload.get("result", {}),
                ),
                "patch_scope_lines": _estimate_patch_scope_lines(selected_patch_artifacts[0]),
                "artifact_refs": [],
            }
        ]
        branch_selection = select_best_validation_branch_candidate_v1(
            candidates=branch_candidates
        )
        decorated = _decorate_validation_payload_with_branch_artifacts(
            payload=candidate_payload,
            branch_candidates=branch_candidates,
            branch_selection=branch_selection,
            patch_artifacts_by_branch={single_branch_id: dict(selected_patch_artifacts[0])},
            metadata={
                "source": "validation_stage",
                "candidate_origin": "source_plan.patch_artifacts",
                "execution_mode": "serial",
            },
        )
        decorated = _attach_branch_outcome_preference_capture(payload=decorated)
        return _record_branch_outcome_preference_capture(
            payload=decorated,
            store=preference_capture_store,
            repo_key=preference_capture_repo_key,
            query=query,
            user_id=preference_capture_user_id,
            profile_key=preference_capture_profile_key,
        )

    lane_pool = LanePool(
        [
            LaneConfig(name=f"branch_{index + 1}", max_workers=1)
            for index in range(len(selected_patch_artifacts))
        ]
    )
    try:
        futures_by_branch: dict[str, tuple[Any, dict[str, Any]]] = {}
        for index, candidate_patch_artifact in enumerate(selected_patch_artifacts):
            branch_id = f"candidate-{index + 1}"
            future = lane_pool.submit(
                f"branch_{index + 1}",
                _run_validation_candidate,
                root=root,
                query=query,
                source_plan_stage=source_plan_stage,
                index_stage=index_stage,
                include_xref=include_xref,
                top_n=top_n,
                xref_top_n=xref_top_n,
                sandbox_timeout_seconds=sandbox_timeout_seconds,
                broker=broker,
                patch_artifact=candidate_patch_artifact,
                validation_tests=validation_tests,
                policy_name=policy_name,
                policy_version=policy_version,
            )
            futures_by_branch[branch_id] = (future, candidate_patch_artifact)

        baseline_result = dict(payload.get("result", {}))
        candidate_payloads: dict[str, dict[str, Any]] = {}
        branch_candidates: list[dict[str, Any]] = []
        for branch_id, (future, candidate_patch_artifact) in futures_by_branch.items():
            candidate_payload = future.result()
            candidate_payloads[branch_id] = candidate_payload
            branch_candidates.append(
                {
                    "branch_id": branch_id,
                    "validation_branch_score": score_validation_branch_result_v1(
                        before=baseline_result,
                        after=candidate_payload.get("result", {}),
                    ),
                    "patch_scope_lines": _estimate_patch_scope_lines(candidate_patch_artifact),
                    "artifact_refs": [],
                }
            )
    finally:
        lane_pool.shutdown(wait=True, cancel_futures=False)

    branch_selection = select_best_validation_branch_candidate_v1(
        candidates=branch_candidates
    )
    winner_branch_id = str(branch_selection.get("winner_branch_id") or "").strip()
    winner_payload = candidate_payloads.get(winner_branch_id, payload)
    decorated = _decorate_validation_payload_with_branch_artifacts(
        payload=winner_payload,
        branch_candidates=branch_candidates,
        branch_selection=branch_selection,
        patch_artifacts_by_branch={
            branch_id: dict(candidate_patch_artifact)
            for branch_id, (_, candidate_patch_artifact) in futures_by_branch.items()
        },
        metadata={
            "source": "validation_stage",
            "candidate_origin": "source_plan.patch_artifacts",
            "execution_mode": "parallel",
        },
    )
    decorated = _attach_branch_outcome_preference_capture(payload=decorated)
    return _record_branch_outcome_preference_capture(
        payload=decorated,
        store=preference_capture_store,
        repo_key=preference_capture_repo_key,
        query=query,
        user_id=preference_capture_user_id,
        profile_key=preference_capture_profile_key,
    )


__all__ = ["run_validation_stage"]
