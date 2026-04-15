"""Helpers for reading stage data from full ACE-Lite plan payloads.

These helpers provide one place to encode the fallback rules between the
top-level plan payload and the nested ``source_plan`` / ``validation``
sub-payloads used by the orchestrator output.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.report_signals import (
    coerce_payload,
    resolve_report_signal,
    resolve_report_signals,
    resolve_source_plan_payload,
)

__all__ = [
    "resolve_candidate_review",
    "coerce_payload",
    "resolve_candidate_chunks",
    "resolve_candidate_files",
    "resolve_context_refine",
    "resolve_confidence_summary",
    "resolve_evidence_summary",
    "resolve_history_channel",
    "resolve_history_hits",
    "resolve_handoff_payload",
    "resolve_pipeline_stage_names",
    "resolve_repomap_payload",
    "resolve_session_end_report",
    "resolve_source_plan_payload",
    "resolve_subgraph_payload",
    "resolve_report_signals",
    "resolve_validation_findings",
    "resolve_validation_result",
    "resolve_validation_tests",
]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def resolve_candidate_chunks(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _list(sp.get("candidate_chunks", [])) or _list(payload.get("candidate_chunks", []))


def resolve_candidate_files(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _list(sp.get("candidate_files", [])) or _list(payload.get("candidate_files", []))


def resolve_validation_tests(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _list(sp.get("validation_tests", [])) or _list(payload.get("validation_tests", []))


def resolve_history_hits(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(plan_payload, "history_hits", source_plan=source_plan)


def resolve_history_channel(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    return _dict(payload.get("history_channel", {}))


def resolve_candidate_review(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(plan_payload, "candidate_review", source_plan=source_plan)


def resolve_context_refine(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    return _dict(payload.get("context_refine", {}))


def resolve_validation_findings(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(plan_payload, "validation_findings", source_plan=source_plan)


def resolve_session_end_report(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(plan_payload, "session_end_report", source_plan=source_plan)


def resolve_handoff_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(plan_payload, "handoff_payload", source_plan=source_plan)


def resolve_evidence_summary(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _dict(sp.get("evidence_summary", {})) or _dict(payload.get("evidence_summary", {}))


def resolve_confidence_summary(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _dict(sp.get("confidence_summary", {})) or _dict(payload.get("confidence_summary", {}))


def resolve_subgraph_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _dict(sp.get("subgraph_payload", {})) or _dict(payload.get("subgraph_payload", {}))


def resolve_repomap_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return _dict(sp.get("repomap", {})) or _dict(payload.get("repomap", {}))


def resolve_pipeline_stage_names(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    return (
        _list(sp.get("stages", []))
        or _list(payload.get("pipeline_order", []))
        or _list(payload.get("stages", []))
    )


def resolve_validation_result(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    sp = _dict(source_plan) if isinstance(source_plan, Mapping) else resolve_source_plan_payload(payload)
    validation_result = _dict(sp.get("validation_result", {}))
    if validation_result:
        return validation_result
    validation_payload = _dict(payload.get("validation", {}))
    validation_result = _dict(validation_payload.get("result", {}))
    if validation_result:
        return validation_result
    return _dict(payload.get("validation_result", {}))
