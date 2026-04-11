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
    "load_problem_surface_payload",
    "loads_problem_surface_payload",
    "validate_problem_surface_payload",
]

SCHEMA_VERSION = PROBLEM_SURFACE_SCHEMA_VERSION


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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


def _normalize_context_surface(context_report: Mapping[str, Any] | Any) -> dict[str, Any]:
    report = _dict(context_report)
    summary = _dict(report.get("summary"))
    confidence_breakdown = _dict(report.get("confidence_breakdown"))

    return {
        "artifact": _str(report.get("schema_version")) or "context_report_v1",
        "query": _str(report.get("query")),
        "repo": _str(report.get("repo")),
        "root": _str(report.get("root")),
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
    summary = _dict(confidence_summary)
    return {
        "artifact": _str(summary.get("schema_version")) or "confidence_summary",
        "extracted_count": _int(summary.get("extracted_count", 0)),
        "inferred_count": _int(summary.get("inferred_count", 0)),
        "ambiguous_count": _int(summary.get("ambiguous_count", 0)),
        "unknown_count": _int(summary.get("unknown_count", 0)),
        "total_count": _int(summary.get("total_count", 0)),
    }


def _normalize_validation_surface(validation_feedback: Mapping[str, Any] | Any) -> dict[str, Any]:
    summary = _dict(validation_feedback)
    return {
        "artifact": _str(summary.get("schema_version")) or "validation_feedback_summary",
        "status": _str(summary.get("status")) or "skipped",
        "issue_count": _int(summary.get("issue_count", 0)),
        "probe_status": _str(summary.get("probe_status")) or "disabled",
        "probe_issue_count": _int(summary.get("probe_issue_count", 0)),
        "probe_executed_count": _int(summary.get("probe_executed_count", 0)),
        "selected_test_count": _int(summary.get("selected_test_count", 0)),
        "executed_test_count": _int(summary.get("executed_test_count", 0)),
    }


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
