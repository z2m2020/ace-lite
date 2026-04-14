from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.plan_contract_summary import build_plan_contract_summary
from ace_lite.plan_timeout import PlanTimeoutOutcome, execute_with_timeout

_REPORT_ONLY_ARTIFACT_FIELDS = (
    "context_report",
    "retrieval_graph_view",
    "skill_catalog",
    "benchmark_report",
    "benchmark_summary",
    "checkpoint_artifacts",
)
_TOP_LEVEL_STAGE_NAMES = (
    "memory",
    "index",
    "repomap",
    "augment",
    "skills",
    "source_plan",
    "validation",
)


@dataclass(frozen=True, slots=True)
class PlanQuickFallback:
    candidate_file_paths: list[str]
    steps: list[str]
    fallback_mode: str


@dataclass(frozen=True, slots=True)
class TimedPlanExecution:
    outcome: PlanTimeoutOutcome
    fallback: PlanQuickFallback

    @property
    def timed_out(self) -> bool:
        return bool(self.outcome.timed_out)

    @property
    def payload(self) -> dict[str, Any] | None:
        return self.outcome.payload


def resolve_plan_quick_fallback(
    *,
    plan_quick_fn: Any,
    normalized_query: str,
    root_path: str | Path,
    top_k_files: int,
    plan_quick_kwargs: dict[str, Any] | None = None,
) -> PlanQuickFallback:
    candidate_file_paths: list[str] = []
    steps: list[str] = []
    extra_kwargs = dict(plan_quick_kwargs or {})
    try:
        quick = plan_quick_fn(
            query=normalized_query,
            root=str(Path(root_path).resolve()),
            top_k_files=max(1, int(top_k_files)),
            repomap_top_k=max(8, int(top_k_files) * 4),
            budget_tokens=800,
            ranking_profile="graph",
            include_rows=False,
            **extra_kwargs,
        )
        quick_paths = quick.get("candidate_files", [])
        if isinstance(quick_paths, list):
            candidate_file_paths = [
                str(item).strip() for item in quick_paths if str(item).strip()
            ]
        quick_steps = quick.get("steps", [])
        if isinstance(quick_steps, list):
            steps = [str(item).strip() for item in quick_steps if str(item).strip()]
    except Exception:
        candidate_file_paths = []
        steps = []
    return PlanQuickFallback(
        candidate_file_paths=candidate_file_paths,
        steps=steps,
        fallback_mode="plan_quick" if candidate_file_paths else "none",
    )


def execute_timed_plan_with_fallback(
    *,
    run_payload: Callable[[], dict[str, Any]],
    timeout_seconds: float,
    debug_root: str | Path,
    debug_payload: dict[str, Any],
    debug_enabled: bool,
    fallback_resolver: Callable[[], PlanQuickFallback],
) -> TimedPlanExecution:
    outcome = execute_with_timeout(
        run_payload=run_payload,
        timeout_seconds=timeout_seconds,
        debug_root=debug_root,
        debug_payload=debug_payload,
        debug_enabled=debug_enabled,
    )
    fallback = (
        fallback_resolver()
        if outcome.timed_out
        else PlanQuickFallback(
            candidate_file_paths=[],
            steps=[],
            fallback_mode="none",
        )
    )
    return TimedPlanExecution(outcome=outcome, fallback=fallback)


def build_plan_contract_summary_from_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    normalized = sanitize_external_plan_payload(payload)
    index_payload = normalized.get("index")
    source_plan_payload = normalized.get("source_plan")
    if not isinstance(index_payload, dict) or not isinstance(source_plan_payload, dict):
        return {}
    return build_plan_contract_summary(
        index_payload=index_payload,
        source_plan_payload=source_plan_payload,
    )


def sanitize_external_plan_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for field in _REPORT_ONLY_ARTIFACT_FIELDS:
        payload.pop(field, None)
    for stage_name in _TOP_LEVEL_STAGE_NAMES:
        stage_payload = payload.get(stage_name)
        if not isinstance(stage_payload, dict):
            continue
        for field in _REPORT_ONLY_ARTIFACT_FIELDS:
            stage_payload.pop(field, None)
    return payload


def attach_plan_contract_summary(payload: Any) -> dict[str, Any]:
    normalized = sanitize_external_plan_payload(payload)
    summary = build_plan_contract_summary_from_payload(normalized)
    if summary:
        normalized["contract_summary"] = summary
    return normalized


__all__ = [
    "PlanQuickFallback",
    "TimedPlanExecution",
    "attach_plan_contract_summary",
    "build_plan_contract_summary_from_payload",
    "execute_timed_plan_with_fallback",
    "resolve_plan_quick_fallback",
    "sanitize_external_plan_payload",
]
