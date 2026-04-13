"""Minimal problem surface schema for cross-artifact evidence mapping.

This module normalizes a small report-only payload that maps evidence artifacts
from ``context_report_v1``, confidence summary helpers, and validation feedback
summary helpers onto a single stable ``problem_surface_v1`` surface.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ace_lite.problem_surface_schema import (
    PROBLEM_SURFACE_REQUIRED_KEYS,
    PROBLEM_SURFACE_SCHEMA_VERSION,
)

__all__ = [
    "SCHEMA_VERSION",
    "build_problem_surface_payload",
    "dump_problem_surface_payload",
    "dumps_problem_surface_payload",
    "extract_confidence_summary_input",
    "extract_context_report_input",
    "extract_problem_surface_payload",
    "extract_validation_feedback_input",
    "load_problem_surface_payload",
    "loads_problem_surface_payload",
    "validate_problem_surface_payload",
]

SCHEMA_VERSION = PROBLEM_SURFACE_SCHEMA_VERSION


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping_dict(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else _dict(value)


def _dedup_warnings(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        warning = _str(item).strip()
        if not warning or warning in seen:
            continue
        seen.add(warning)
        deduped.append(warning)
    return deduped


def _unknown_str(value: Any) -> str:
    return _str(value).strip() or "unknown"


def _source_plan_dict(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = _mapping_dict(plan_payload)
    return _mapping_dict(payload.get("source_plan"))


def _validation_dict(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = _mapping_dict(plan_payload)
    return _mapping_dict(payload.get("validation"))


def _resolve_validation_feedback_summary(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = _mapping_dict(plan_payload)
    source_plan = _source_plan_dict(payload)
    validate_steps = source_plan.get("steps")
    if isinstance(validate_steps, list):
        for step in validate_steps:
            step_dict = _mapping_dict(step)
            if _str(step_dict.get("stage")).strip() != "validate":
                continue
            summary = _mapping_dict(step_dict.get("validation_feedback_summary"))
            if summary:
                return summary

    validation_payload = _validation_dict(payload)
    for candidate in (
        validation_payload.get("validation_feedback_summary"),
        payload.get("validation_feedback_summary"),
        validation_payload.get("summary"),
        _mapping_dict(validation_payload.get("result")).get("summary"),
        payload.get("validation_result"),
    ):
        summary = _mapping_dict(candidate)
        if summary:
            return summary
    return {}


def _normalize_context_surface(context_report: Mapping[str, Any] | Any) -> dict[str, Any]:
    report = _mapping_dict(context_report)
    summary = _dict(report.get("summary"))
    confidence_breakdown = _dict(report.get("confidence_breakdown"))

    return {
        "artifact": _str(report.get("schema_version")) or "context_report_v1",
        "query": _unknown_str(report.get("query")),
        "repo": _unknown_str(report.get("repo")),
        "root": _unknown_str(report.get("root")),
        "candidate_file_count": _int(summary.get("candidate_file_count", 0)),
        "candidate_chunk_count": _int(summary.get("candidate_chunk_count", 0)),
        "validation_test_count": _int(summary.get("validation_test_count", 0)),
        "degraded_reason_count": _int(summary.get("degraded_reason_count", 0)),
        "degraded_reasons": [
            _str(item).strip()
            for item in _list(report.get("degraded_reasons"))
            if _str(item).strip()
        ],
        "warnings": [
            _str(item).strip() for item in _list(report.get("warnings")) if _str(item).strip()
        ],
        "confidence_total_count": _int(confidence_breakdown.get("total_count", 0)),
    }


def _normalize_confidence_surface(confidence_summary: Mapping[str, Any] | Any) -> dict[str, Any]:
    summary = _mapping_dict(confidence_summary)
    return {
        "artifact": _str(summary.get("schema_version")) or "confidence_summary",
        "extracted_count": _int(summary.get("extracted_count", 0)),
        "inferred_count": _int(summary.get("inferred_count", 0)),
        "ambiguous_count": _int(summary.get("ambiguous_count", 0)),
        "unknown_count": _int(summary.get("unknown_count", 0)),
        "total_count": _int(summary.get("total_count", 0)),
    }


def _normalize_validation_surface(validation_feedback: Mapping[str, Any] | Any) -> dict[str, Any]:
    summary = _mapping_dict(validation_feedback)
    return {
        "artifact": _str(summary.get("schema_version")) or "validation_feedback_summary",
        "status": _unknown_str(summary.get("status")),
        "issue_count": _int(summary.get("issue_count", 0)),
        "probe_status": _unknown_str(summary.get("probe_status")),
        "probe_issue_count": _int(summary.get("probe_issue_count", 0)),
        "probe_executed_count": _int(summary.get("probe_executed_count", 0)),
        "selected_test_count": _int(summary.get("selected_test_count", 0)),
        "executed_test_count": _int(summary.get("executed_test_count", 0)),
    }


def extract_context_report_input(
    plan_payload: Mapping[str, Any] | Any,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        payload = _mapping_dict(plan_payload)
        source_plan = _source_plan_dict(payload)
        context_report = _mapping_dict(payload.get("context_report"))
        if context_report:
            return context_report, warnings

        candidate_chunks = _list(source_plan.get("candidate_chunks")) or _list(
            payload.get("candidate_chunks")
        )
        candidate_files = _list(source_plan.get("candidate_files")) or _list(
            payload.get("candidate_files")
        )
        validation_tests = _list(source_plan.get("validation_tests")) or _list(
            payload.get("validation_tests")
        )
        confidence_summary = _mapping_dict(source_plan.get("confidence_summary")) or _mapping_dict(
            payload.get("confidence_summary")
        )

        unique_paths: set[str] = set()
        for item in candidate_files:
            item_dict = _mapping_dict(item)
            path = _str(item_dict.get("path")).strip()
            if path:
                unique_paths.add(path)
        for item in candidate_chunks:
            item_dict = _mapping_dict(item)
            path = _str(item_dict.get("path")).strip()
            if path:
                unique_paths.add(path)

        degraded_reasons = [
            _str(item).strip()
            for item in _list(payload.get("degraded_reasons"))
            if _str(item).strip()
        ]
        if payload.get("_plan_timeout_fallback"):
            degraded_reasons.append("plan_timeout_fallback")

        warnings.append("missing_context_report")
        return {
            "schema_version": "context_report_v1",
            "query": _unknown_str(payload.get("query") or source_plan.get("query")),
            "repo": _unknown_str(payload.get("repo") or source_plan.get("repo")),
            "root": _unknown_str(payload.get("root") or source_plan.get("root")),
            "summary": {
                "candidate_file_count": len(unique_paths),
                "candidate_chunk_count": len(candidate_chunks),
                "validation_test_count": len(validation_tests),
                "degraded_reason_count": len(degraded_reasons),
            },
            "confidence_breakdown": {
                "total_count": _int(confidence_summary.get("total_count"), len(candidate_chunks)),
            },
            "degraded_reasons": degraded_reasons,
            "warnings": ["context_report_inferred_from_plan_payload"],
        }, warnings
    except Exception as exc:
        return {
            "schema_version": "context_report_v1",
            "query": "unknown",
            "repo": "unknown",
            "root": "unknown",
            "summary": {},
            "confidence_breakdown": {"total_count": 0},
            "degraded_reasons": [],
            "warnings": [f"context_report_extractor_error:{type(exc).__name__}"],
        }, [f"context_report_extractor_error:{type(exc).__name__}"]


def extract_confidence_summary_input(
    plan_payload: Mapping[str, Any] | Any,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        payload = _mapping_dict(plan_payload)
        source_plan = _source_plan_dict(payload)
        confidence_summary = _mapping_dict(source_plan.get("confidence_summary")) or _mapping_dict(
            payload.get("confidence_summary")
        )
        if confidence_summary:
            return confidence_summary, warnings

        context_report = _mapping_dict(payload.get("context_report"))
        confidence_breakdown = _mapping_dict(context_report.get("confidence_breakdown"))
        total_count = _int(confidence_breakdown.get("total_count"), 0)
        warnings.append("missing_confidence_summary")
        return {
            "schema_version": "confidence_summary",
            "extracted_count": _int(confidence_breakdown.get("extracted_count"), 0),
            "inferred_count": _int(confidence_breakdown.get("inferred_count"), 0),
            "ambiguous_count": _int(confidence_breakdown.get("ambiguous_count"), 0),
            "unknown_count": _int(confidence_breakdown.get("unknown_count"), total_count),
            "total_count": total_count,
        }, warnings
    except Exception as exc:
        return {
            "schema_version": "confidence_summary",
            "extracted_count": 0,
            "inferred_count": 0,
            "ambiguous_count": 0,
            "unknown_count": 0,
            "total_count": 0,
        }, [f"confidence_summary_extractor_error:{type(exc).__name__}"]


def extract_validation_feedback_input(
    plan_payload: Mapping[str, Any] | Any,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        summary = _resolve_validation_feedback_summary(plan_payload)
        if summary:
            return summary, warnings

        warnings.append("missing_validation_feedback")
        return {
            "schema_version": "validation_feedback_summary",
            "status": "unknown",
            "issue_count": 0,
            "probe_status": "unknown",
            "probe_issue_count": 0,
            "probe_executed_count": 0,
            "selected_test_count": 0,
            "executed_test_count": 0,
        }, warnings
    except Exception as exc:
        return {
            "schema_version": "validation_feedback_summary",
            "status": "unknown",
            "issue_count": 0,
            "probe_status": "unknown",
            "probe_issue_count": 0,
            "probe_executed_count": 0,
            "selected_test_count": 0,
            "executed_test_count": 0,
        }, [f"validation_feedback_extractor_error:{type(exc).__name__}"]


def extract_problem_surface_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    git_sha: str = "",
    phase: str = "problem_discovery",
    generated_at: str | None = None,
) -> dict[str, Any]:
    try:
        context_report, context_warnings = extract_context_report_input(plan_payload)
        confidence_summary, confidence_warnings = extract_confidence_summary_input(plan_payload)
        validation_feedback, validation_warnings = extract_validation_feedback_input(plan_payload)
        payload = build_problem_surface_payload(
            context_report=context_report,
            confidence_summary=confidence_summary,
            validation_feedback=validation_feedback,
            git_sha=git_sha,
            phase=phase,
            generated_at=generated_at,
        )
        payload["warnings"] = _dedup_warnings(
            _list(payload.get("warnings"))
            + context_warnings
            + confidence_warnings
            + validation_warnings
        )
        return payload
    except Exception as exc:
        payload = build_problem_surface_payload(
            context_report={
                "schema_version": "context_report_v1",
                "query": "unknown",
                "repo": "unknown",
                "root": "unknown",
                "summary": {},
                "confidence_breakdown": {"total_count": 0},
            },
            confidence_summary={
                "schema_version": "confidence_summary",
                "extracted_count": 0,
                "inferred_count": 0,
                "ambiguous_count": 0,
                "unknown_count": 0,
                "total_count": 0,
            },
            validation_feedback={
                "schema_version": "validation_feedback_summary",
                "status": "unknown",
                "issue_count": 0,
                "probe_status": "unknown",
                "probe_issue_count": 0,
                "probe_executed_count": 0,
                "selected_test_count": 0,
                "executed_test_count": 0,
            },
            git_sha=git_sha,
            phase=phase,
            generated_at=generated_at,
        )
        payload["warnings"] = _dedup_warnings(
            _list(payload.get("warnings"))
            + [f"problem_surface_extractor_error:{type(exc).__name__}"]
        )
        return payload


def build_problem_surface_payload(
    *,
    context_report: Mapping[str, Any] | Any = None,
    confidence_summary: Mapping[str, Any] | Any = None,
    validation_feedback: Mapping[str, Any] | Any = None,
    git_sha: str = "",
    phase: str = "problem_discovery",
    generated_at: str | None = None,
) -> dict[str, Any]:
    context_payload = _dict(context_report)
    confidence_payload = _dict(confidence_summary)
    validation_payload = _dict(validation_feedback)

    warnings: list[str] = []
    if not context_payload:
        warnings.append("missing_context_report")
    if not confidence_payload:
        warnings.append("missing_confidence_summary")
    if not validation_payload:
        warnings.append("missing_validation_feedback")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _str(generated_at) or _utc_now(),
        "git_sha": _str(git_sha),
        "phase": _str(phase) or "problem_discovery",
        "inputs": {
            "context_report": {
                "present": bool(context_payload),
                "schema_version": _str(context_payload.get("schema_version")),
            },
            "confidence_summary": {
                "present": bool(confidence_payload),
                "schema_version": _str(confidence_payload.get("schema_version")),
            },
            "validation_feedback": {
                "present": bool(validation_payload),
                "schema_version": _str(validation_payload.get("schema_version")),
            },
        },
        "surfaces": {
            "context": _normalize_context_surface(context_payload),
            "confidence": _normalize_confidence_surface(confidence_payload),
            "validation": _normalize_validation_surface(validation_payload),
        },
        "warnings": warnings,
    }


def validate_problem_surface_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    normalized = _dict(payload)
    if not normalized:
        raise ValueError("problem_surface payload must be a dictionary")

    for key in PROBLEM_SURFACE_REQUIRED_KEYS:
        if key not in normalized:
            raise ValueError(f"{key} is required")

    if _str(normalized.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if (
        not isinstance(normalized.get("generated_at"), str)
        or not _str(normalized.get("generated_at")).strip()
    ):
        raise ValueError("generated_at must be a non-empty string")
    if not isinstance(normalized.get("git_sha"), str):
        raise ValueError("git_sha must be a string")
    if not isinstance(normalized.get("phase"), str) or not _str(normalized.get("phase")).strip():
        raise ValueError("phase must be a non-empty string")
    if not isinstance(normalized.get("inputs"), dict):
        raise ValueError("inputs must be a dictionary")
    if not isinstance(normalized.get("surfaces"), dict):
        raise ValueError("surfaces must be a dictionary")
    if not isinstance(normalized.get("warnings"), list):
        raise ValueError("warnings must be a list")

    return dump_problem_surface_payload(normalized)


def dump_problem_surface_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    normalized = _dict(payload)
    return {
        "schema_version": _str(normalized.get("schema_version")) or SCHEMA_VERSION,
        "generated_at": _str(normalized.get("generated_at")),
        "git_sha": _str(normalized.get("git_sha")),
        "phase": _str(normalized.get("phase")),
        "inputs": _dict(normalized.get("inputs")),
        "surfaces": _dict(normalized.get("surfaces")),
        "warnings": [_str(item) for item in _list(normalized.get("warnings"))],
    }


def load_problem_surface_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    return validate_problem_surface_payload(payload)


def dumps_problem_surface_payload(payload: Mapping[str, Any] | Any) -> str:
    return json.dumps(load_problem_surface_payload(payload), indent=2, sort_keys=True)


def loads_problem_surface_payload(value: str) -> dict[str, Any]:
    return load_problem_surface_payload(json.loads(value))
