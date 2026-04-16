"""Helpers for reading stage data from full ACE-Lite plan payloads.

These helpers provide one place to encode the fallback rules between the
top-level plan payload and the nested ``source_plan`` / ``validation``
sub-payloads used by the orchestrator output.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypeAlias, cast

from ace_lite.report_signals import (
    DEFAULT_REPORT_SIGNAL_KEYS,
    ReportSignalKey,
    coerce_payload,
    resolve_report_signal,
    resolve_report_signals,
    resolve_source_plan_payload,
)

SourcePlanListKey: TypeAlias = Literal[
    "candidate_chunks",
    "candidate_files",
    "validation_tests",
]
SourcePlanDictKey: TypeAlias = Literal[
    "evidence_summary",
    "confidence_summary",
    "subgraph_payload",
    "repomap",
]

__all__ = [
    "DEFAULT_REPORT_SIGNAL_KEYS",
    "coerce_payload",
    "resolve_candidate_chunks",
    "resolve_candidate_files",
    "resolve_candidate_review",
    "resolve_confidence_summary",
    "resolve_context_refine",
    "resolve_evidence_summary",
    "resolve_handoff_payload",
    "resolve_history_channel",
    "resolve_history_hits",
    "resolve_pipeline_stage_names",
    "resolve_repomap_payload",
    "resolve_report_signals",
    "resolve_session_end_report",
    "resolve_source_plan_payload",
    "resolve_subgraph_payload",
    "resolve_validation_findings",
    "resolve_validation_result",
    "resolve_validation_tests",
]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _resolve_source_plan_mapping(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = coerce_payload(plan_payload)
    sp = (
        _dict(source_plan)
        if isinstance(source_plan, Mapping)
        else resolve_source_plan_payload(payload)
    )
    return payload, sp


def _resolve_source_plan_list_value(
    plan_payload: Mapping[str, Any] | Any,
    *,
    key: SourcePlanListKey,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    payload, sp = _resolve_source_plan_mapping(plan_payload, source_plan=source_plan)
    return _list(sp.get(key, [])) or _list(payload.get(key, []))


def _resolve_source_plan_dict_value(
    plan_payload: Mapping[str, Any] | Any,
    *,
    key: SourcePlanDictKey,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload, sp = _resolve_source_plan_mapping(plan_payload, source_plan=source_plan)
    return _dict(sp.get(key, {})) or _dict(payload.get(key, {}))


def resolve_candidate_chunks(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    return _resolve_source_plan_list_value(
        plan_payload,
        key="candidate_chunks",
        source_plan=source_plan,
    )


def resolve_candidate_files(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    return _resolve_source_plan_list_value(
        plan_payload,
        key="candidate_files",
        source_plan=source_plan,
    )


def resolve_validation_tests(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    return _resolve_source_plan_list_value(
        plan_payload,
        key="validation_tests",
        source_plan=source_plan,
    )


def resolve_history_hits(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(
        plan_payload,
        cast(ReportSignalKey, "history_hits"),
        source_plan=source_plan,
    )


def resolve_history_channel(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    return _dict(payload.get("history_channel", {}))


def resolve_candidate_review(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(
        plan_payload,
        cast(ReportSignalKey, "candidate_review"),
        source_plan=source_plan,
    )


def resolve_context_refine(plan_payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = coerce_payload(plan_payload)
    return _dict(payload.get("context_refine", {}))


def resolve_validation_findings(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(
        plan_payload,
        cast(ReportSignalKey, "validation_findings"),
        source_plan=source_plan,
    )


def resolve_session_end_report(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(
        plan_payload,
        cast(ReportSignalKey, "session_end_report"),
        source_plan=source_plan,
    )


def resolve_handoff_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_report_signal(
        plan_payload,
        cast(ReportSignalKey, "handoff_payload"),
        source_plan=source_plan,
    )


def resolve_evidence_summary(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _resolve_source_plan_dict_value(
        plan_payload,
        key="evidence_summary",
        source_plan=source_plan,
    )


def resolve_confidence_summary(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _resolve_source_plan_dict_value(
        plan_payload,
        key="confidence_summary",
        source_plan=source_plan,
    )


def resolve_subgraph_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _resolve_source_plan_dict_value(
        plan_payload,
        key="subgraph_payload",
        source_plan=source_plan,
    )


def resolve_repomap_payload(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _resolve_source_plan_dict_value(
        plan_payload,
        key="repomap",
        source_plan=source_plan,
    )


def resolve_pipeline_stage_names(
    plan_payload: Mapping[str, Any] | Any,
    *,
    source_plan: Mapping[str, Any] | None = None,
) -> list[Any]:
    payload = coerce_payload(plan_payload)
    sp = (
        _dict(source_plan)
        if isinstance(source_plan, Mapping)
        else resolve_source_plan_payload(payload)
    )
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
    sp = (
        _dict(source_plan)
        if isinstance(source_plan, Mapping)
        else resolve_source_plan_payload(payload)
    )
    validation_result = _dict(sp.get("validation_result", {}))
    if validation_result:
        return validation_result
    validation_payload = _dict(payload.get("validation", {}))
    validation_result = _dict(validation_payload.get("result", {}))
    if validation_result:
        return validation_result
    return _dict(payload.get("validation_result", {}))
