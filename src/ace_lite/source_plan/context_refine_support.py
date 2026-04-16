from __future__ import annotations

from typing import Any, cast

from ace_lite.source_plan.report_only import build_candidate_review


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def resolve_source_plan_candidate_review(
    *,
    context_refine_state: Any,
    focused_files: list[str],
    candidate_chunks: list[dict[str, Any]],
    evidence_summary: dict[str, Any],
    failure_signal_summary: dict[str, Any],
    validation_tests: list[str],
) -> dict[str, Any]:
    context_refine_stage = _coerce_mapping(context_refine_state)
    candidate_review = _coerce_mapping(context_refine_stage.get("candidate_review"))
    if candidate_review:
        return candidate_review
    return cast(
        dict[str, Any],
        build_candidate_review(
            focused_files=focused_files,
            candidate_chunks=candidate_chunks,
            evidence_summary=evidence_summary,
            failure_signal_summary=failure_signal_summary,
            validation_tests=validation_tests,
        ),
    )


__all__ = ["resolve_source_plan_candidate_review"]
