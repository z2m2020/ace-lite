from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

VALIDATION_RESULT_SCHEMA_VERSION = "validation_result_v1"
VALIDATION_RESULT_STATUS_VALUES = ("passed", "failed", "degraded", "skipped")
VALIDATION_PROBE_STATUS_VALUES = ("disabled", "passed", "failed", "degraded", "skipped")


def _normalize_issue_list(*, value: Any, context: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{context}[{index}] must be a mapping")
        code = str(item.get("code") or "").strip()
        message = str(item.get("message") or "").strip()
        if not code:
            raise ValueError(f"{context}[{index}].code cannot be empty")
        if not message:
            raise ValueError(f"{context}[{index}].message cannot be empty")
        normalized.append(
            {
                "code": code,
                "message": message,
                "path": str(item.get("path") or "").strip().replace("\\", "/"),
                "severity": str(item.get("severity") or "error").strip() or "error",
                "line": max(0, int(item.get("line", 0) or 0)),
                "column": max(0, int(item.get("column", 0) or 0)),
            }
        )
    return tuple(normalized)


def _normalize_text_list(*, value: Any, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{context}[{index}] must be a string")
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


def _build_issue_section(*, issues: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    return {
        "ok": len(issues) == 0,
        "issues": [dict(item) for item in issues],
        "issue_count": len(issues),
    }


def _normalize_probe_results(*, value: Any, context: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    normalized: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{context}[{index}] must be a mapping")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError(f"{context}[{index}].name cannot be empty")
        if name in seen_names:
            raise ValueError(f"{context}[{index}].name must be unique")
        seen_names.add(name)
        status = str(item.get("status") or "").strip().lower()
        if status not in VALIDATION_PROBE_STATUS_VALUES:
            status = "disabled"
        issues = _normalize_issue_list(
            value=item.get("issues"),
            context=f"{context}[{index}].issues",
        )
        artifacts = _normalize_text_list(
            value=item.get("artifacts"),
            context=f"{context}[{index}].artifacts",
        )
        degraded_reasons = _normalize_text_list(
            value=item.get("degraded_reasons"),
            context=f"{context}[{index}].degraded_reasons",
        )
        executed = bool(item.get("executed", False))
        selected = bool(item.get("selected", executed))
        issue_count = len(issues)
        ok = status in {"disabled", "passed", "skipped"} and issue_count == 0
        normalized.append(
            {
                "name": name,
                "status": status,
                "ok": ok,
                "selected": selected,
                "executed": executed,
                "issue_count": issue_count,
                "issues": [dict(entry) for entry in issues],
                "artifacts": list(artifacts),
                "degraded_reasons": list(degraded_reasons),
                "timed_out": bool(item.get("timed_out", False)),
            }
        )
    return tuple(normalized)


def _build_probe_section(
    *,
    available: tuple[str, ...],
    results: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    selected_count = sum(1 for item in results if bool(item.get("selected", False)))
    executed_count = sum(1 for item in results if bool(item.get("executed", False)))
    issue_count = sum(int(item.get("issue_count", 0) or 0) for item in results)
    statuses = {str(item.get("status") or "").strip().lower() for item in results}
    if not results:
        status = "disabled"
    elif "failed" in statuses:
        status = "failed"
    elif "degraded" in statuses:
        status = "degraded"
    elif "passed" in statuses:
        status = "passed"
    elif "skipped" in statuses:
        status = "skipped"
    else:
        status = "disabled"
    return {
        "enabled": bool(available),
        "available": list(available),
        "results": [dict(item) for item in results],
        "selected_count": selected_count,
        "executed_count": executed_count,
        "issue_count": issue_count,
        "status": status,
    }


def _compute_comparison_key(*, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
        "utf-8",
        errors="ignore",
    )
    return hashlib.sha256(canonical).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class ValidationResultV1:
    syntax: dict[str, Any]
    type_results: dict[str, Any]
    tests: dict[str, Any]
    probes: dict[str, Any]
    environment: dict[str, Any]
    summary: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": VALIDATION_RESULT_SCHEMA_VERSION,
            "syntax": dict(self.syntax),
            "type": dict(self.type_results),
            "tests": dict(self.tests),
            "probes": dict(self.probes),
            "environment": dict(self.environment),
            "summary": dict(self.summary),
        }


def build_validation_result_v1(
    *,
    syntax_issues: list[dict[str, Any]] | None = None,
    type_issues: list[dict[str, Any]] | None = None,
    test_issues: list[dict[str, Any]] | None = None,
    selected_tests: list[str] | None = None,
    executed_tests: list[str] | None = None,
    probes: list[dict[str, Any]] | None = None,
    available_probes: list[str] | None = None,
    sandboxed: bool = True,
    runner: str = "sandbox",
    artifacts: list[str] | None = None,
    degraded_reasons: list[str] | None = None,
    replay_key: str = "",
    status: str | None = None,
) -> ValidationResultV1:
    normalized_syntax_issues = _normalize_issue_list(
        value=syntax_issues,
        context="syntax_issues",
    )
    normalized_type_issues = _normalize_issue_list(
        value=type_issues,
        context="type_issues",
    )
    normalized_test_issues = _normalize_issue_list(
        value=test_issues,
        context="test_issues",
    )
    normalized_selected_tests = _normalize_text_list(
        value=selected_tests,
        context="selected_tests",
    )
    normalized_executed_tests = _normalize_text_list(
        value=executed_tests,
        context="executed_tests",
    )
    normalized_available_probes = _normalize_text_list(
        value=available_probes,
        context="available_probes",
    )
    normalized_probe_results = _normalize_probe_results(
        value=probes,
        context="probes",
    )
    if not normalized_available_probes and normalized_probe_results:
        normalized_available_probes = tuple(
            str(item.get("name") or "").strip()
            for item in normalized_probe_results
            if str(item.get("name") or "").strip()
        )
    normalized_artifacts = _normalize_text_list(value=artifacts, context="artifacts")
    normalized_degraded_reasons = _normalize_text_list(
        value=degraded_reasons,
        context="degraded_reasons",
    )

    syntax = _build_issue_section(issues=normalized_syntax_issues)
    type_results = _build_issue_section(issues=normalized_type_issues)
    tests = _build_issue_section(issues=normalized_test_issues)
    tests["selected"] = list(normalized_selected_tests)
    tests["executed"] = list(normalized_executed_tests)
    probe_section = _build_probe_section(
        available=normalized_available_probes,
        results=normalized_probe_results,
    )

    environment = {
        "ok": len(normalized_degraded_reasons) == 0,
        "sandboxed": bool(sandboxed),
        "runner": str(runner or "").strip() or "sandbox",
        "artifacts": list(normalized_artifacts),
        "degraded_reasons": list(normalized_degraded_reasons),
    }

    probe_ok = str(probe_section.get("status") or "") in {"disabled", "passed", "skipped"}
    overall_ok = bool(
        syntax["ok"]
        and type_results["ok"]
        and tests["ok"]
        and probe_ok
        and environment["ok"]
    )
    effective_status = str(status or "").strip().lower()
    if effective_status not in VALIDATION_RESULT_STATUS_VALUES:
        effective_status = "passed" if overall_ok else (
            "degraded"
            if not environment["ok"] and syntax["ok"] and type_results["ok"] and tests["ok"] and probe_ok
            else "failed"
        )

    base_payload = {
        "schema_version": VALIDATION_RESULT_SCHEMA_VERSION,
        "syntax": syntax,
        "type": type_results,
        "tests": tests,
        "probes": probe_section,
        "environment": environment,
    }
    summary = {
        "ok": overall_ok,
        "status": effective_status,
        "issue_count": (
            int(syntax["issue_count"])
            + int(type_results["issue_count"])
            + int(tests["issue_count"])
            + int(probe_section["issue_count"])
        ),
        "replay_key": str(replay_key or "").strip(),
        "artifact_refs": list(normalized_artifacts),
        "comparison_key": _compute_comparison_key(payload=base_payload),
    }
    return ValidationResultV1(
        syntax=syntax,
        type_results=type_results,
        tests=tests,
        probes=probe_section,
        environment=environment,
        summary=summary,
    )


def compare_validation_results_v1(
    *,
    before: ValidationResultV1 | dict[str, Any],
    after: ValidationResultV1 | dict[str, Any],
) -> dict[str, Any]:
    before_payload = before.as_dict() if isinstance(before, ValidationResultV1) else before
    after_payload = after.as_dict() if isinstance(after, ValidationResultV1) else after
    if not isinstance(before_payload, dict) or not isinstance(after_payload, dict):
        raise ValueError("before and after must be ValidationResultV1 or mapping payloads")

    def _issue_codes(payload: dict[str, Any], key: str) -> set[str]:
        section = payload.get(key, {})
        issues = section.get("issues", []) if isinstance(section, dict) else []
        if not isinstance(issues, list):
            return set()
        return {
            str(item.get("code") or "").strip()
            for item in issues
            if isinstance(item, dict) and str(item.get("code") or "").strip()
        }

    def _probe_issue_codes(payload: dict[str, Any]) -> set[str]:
        probes = payload.get("probes", {})
        results = probes.get("results", []) if isinstance(probes, dict) else []
        if not isinstance(results, list):
            return set()
        codes: set[str] = set()
        for item in results:
            issues = item.get("issues", []) if isinstance(item, dict) else []
            if not isinstance(issues, list):
                continue
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                code = str(issue.get("code") or "").strip()
                if code:
                    codes.add(code)
        return codes

    before_codes = (
        _issue_codes(before_payload, "syntax")
        | _issue_codes(before_payload, "type")
        | _issue_codes(before_payload, "tests")
        | _probe_issue_codes(before_payload)
    )
    after_codes = (
        _issue_codes(after_payload, "syntax")
        | _issue_codes(after_payload, "type")
        | _issue_codes(after_payload, "tests")
        | _probe_issue_codes(after_payload)
    )
    before_summary = before_payload.get("summary", {}) if isinstance(before_payload.get("summary"), dict) else {}
    after_summary = after_payload.get("summary", {}) if isinstance(after_payload.get("summary"), dict) else {}

    return {
        "changed": before_summary.get("comparison_key") != after_summary.get("comparison_key"),
        "before_status": str(before_summary.get("status") or ""),
        "after_status": str(after_summary.get("status") or ""),
        "before_issue_count": int(before_summary.get("issue_count", 0) or 0),
        "after_issue_count": int(after_summary.get("issue_count", 0) or 0),
        "new_issue_codes": sorted(after_codes - before_codes),
        "resolved_issue_codes": sorted(before_codes - after_codes),
        "comparison_key_before": str(before_summary.get("comparison_key") or ""),
        "comparison_key_after": str(after_summary.get("comparison_key") or ""),
    }


def validate_validation_result_v1(
    *,
    contract: ValidationResultV1 | dict[str, Any],
    strict: bool = True,
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload = contract.as_dict() if isinstance(contract, ValidationResultV1) else contract
    if not isinstance(payload, dict):
        raise ValueError("contract must be ValidationResultV1 or a mapping payload")

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

    if payload.get("schema_version") != VALIDATION_RESULT_SCHEMA_VERSION:
        _add_violation(
            code="validation_result_schema_version_invalid",
            field="schema_version",
            message="schema_version must match validation_result_v1",
        )

    for section_name in ("syntax", "type", "tests"):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            _add_violation(
                code="validation_result_section_invalid",
                field=section_name,
                message=f"{section_name} must be a mapping",
                context={"section": section_name},
            )
            continue
        if not isinstance(section.get("ok"), bool):
            _add_violation(
                code="validation_result_section_ok_invalid",
                field=section_name,
                message=f"{section_name}.ok must be a bool",
                context={"section": section_name},
            )
        issues = section.get("issues")
        if not isinstance(issues, list):
            _add_violation(
                code="validation_result_section_issues_invalid",
                field=section_name,
                message=f"{section_name}.issues must be a list",
                context={"section": section_name},
            )
        if section_name == "tests":
            for field_name in ("selected", "executed"):
                if not isinstance(section.get(field_name), list):
                    _add_violation(
                        code="validation_result_tests_list_invalid",
                        field=f"tests.{field_name}",
                        message=f"tests.{field_name} must be a list",
                        context={"field": field_name},
                    )

    probes = payload.get("probes")
    if not isinstance(probes, dict):
        _add_violation(
            code="validation_result_probes_invalid",
            field="probes",
            message="probes must be a mapping",
        )
        probes = {}
    if not isinstance(probes.get("enabled"), bool):
        _add_violation(
            code="validation_result_probes_enabled_invalid",
            field="probes.enabled",
            message="probes.enabled must be a bool",
        )
    for field_name in ("available", "results"):
        if not isinstance(probes.get(field_name), list):
            _add_violation(
                code="validation_result_probes_list_invalid",
                field=f"probes.{field_name}",
                message=f"probes.{field_name} must be a list",
                context={"field": field_name},
            )
    for field_name in ("selected_count", "executed_count", "issue_count"):
        if not isinstance(probes.get(field_name), (int, float)):
            _add_violation(
                code="validation_result_probes_count_invalid",
                field=f"probes.{field_name}",
                message=f"probes.{field_name} must be numeric",
                context={"field": field_name},
            )
    probe_status = str(probes.get("status") or "").strip().lower()
    if probe_status not in VALIDATION_PROBE_STATUS_VALUES:
        _add_violation(
            code="validation_result_probes_status_invalid",
            field="probes.status",
            message="probes.status must be disabled, passed, failed, degraded, or skipped",
            context={"status": probe_status},
        )

    environment = payload.get("environment")
    if not isinstance(environment, dict):
        _add_violation(
            code="validation_result_environment_invalid",
            field="environment",
            message="environment must be a mapping",
        )
        environment = {}
    if not isinstance(environment.get("sandboxed"), bool):
        _add_violation(
            code="validation_result_environment_sandboxed_invalid",
            field="environment.sandboxed",
            message="environment.sandboxed must be a bool",
        )
    if not isinstance(environment.get("runner"), str):
        _add_violation(
            code="validation_result_environment_runner_invalid",
            field="environment.runner",
            message="environment.runner must be a string",
        )
    if not isinstance(environment.get("artifacts"), list):
        _add_violation(
            code="validation_result_environment_artifacts_invalid",
            field="environment.artifacts",
            message="environment.artifacts must be a list",
        )
    if not isinstance(environment.get("degraded_reasons"), list):
        _add_violation(
            code="validation_result_environment_degraded_reasons_invalid",
            field="environment.degraded_reasons",
            message="environment.degraded_reasons must be a list",
        )

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        _add_violation(
            code="validation_result_summary_invalid",
            field="summary",
            message="summary must be a mapping",
        )
        summary = {}
    if not isinstance(summary.get("ok"), bool):
        _add_violation(
            code="validation_result_summary_ok_invalid",
            field="summary.ok",
            message="summary.ok must be a bool",
        )
    status = str(summary.get("status") or "").strip().lower()
    if status not in VALIDATION_RESULT_STATUS_VALUES:
        _add_violation(
            code="validation_result_summary_status_invalid",
            field="summary.status",
            message="summary.status must be passed, failed, degraded, or skipped",
            context={"status": status},
        )
    if not isinstance(summary.get("issue_count"), (int, float)):
        _add_violation(
            code="validation_result_summary_issue_count_invalid",
            field="summary.issue_count",
            message="summary.issue_count must be numeric",
        )
    if not isinstance(summary.get("replay_key"), str):
        _add_violation(
            code="validation_result_summary_replay_key_invalid",
            field="summary.replay_key",
            message="summary.replay_key must be a string",
        )
    if not isinstance(summary.get("comparison_key"), str):
        _add_violation(
            code="validation_result_summary_comparison_key_invalid",
            field="summary.comparison_key",
            message="summary.comparison_key must be a string",
        )
    if not isinstance(summary.get("artifact_refs"), list):
        _add_violation(
            code="validation_result_summary_artifact_refs_invalid",
            field="summary.artifact_refs",
            message="summary.artifact_refs must be a list",
        )

    if strict and not summary.get("comparison_key"):
        _add_violation(
            code="validation_result_summary_comparison_key_empty",
            field="summary.comparison_key",
            message="summary.comparison_key must be non-empty in strict mode",
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
    "VALIDATION_RESULT_SCHEMA_VERSION",
    "ValidationResultV1",
    "build_validation_result_v1",
    "compare_validation_results_v1",
    "validate_validation_result_v1",
]
