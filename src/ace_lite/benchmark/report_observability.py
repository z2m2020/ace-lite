from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_observability_core import (
    append_evidence_insufficiency_summary as _append_evidence_insufficiency_summary_impl,
)
from ace_lite.benchmark.report_observability_core import (
    append_missing_context_risk_summary as _append_missing_context_risk_summary_impl,
)
from ace_lite.benchmark.report_observability_core import (
    append_reward_log_summary as _append_reward_log_summary_impl,
)
from ace_lite.benchmark.report_observability_core import (
    format_decision_event as _format_decision_event_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_decision_observability_summary as _append_decision_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_retrieval_control_plane_gate_summary as _append_retrieval_control_plane_gate_summary_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_wave1_context_governance_summary as _append_wave1_context_governance_summary_impl,
)
from ace_lite.benchmark.report_observability_governance import (
    append_workload_taxonomy_summary as _append_workload_taxonomy_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_feedback_loop_summary as _append_feedback_loop_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_feedback_observability_summary as _append_feedback_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_ltm_explainability_summary as _append_ltm_explainability_summary_impl,
)
from ace_lite.benchmark.report_observability_memory import (
    append_preference_observability_summary as _append_preference_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_adaptive_router_observability_summary as _append_adaptive_router_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_context_refine_summary as _append_context_refine_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_retrieval_context_observability_summary as _append_retrieval_context_observability_summary_impl,
)
from ace_lite.benchmark.report_observability_routing import (
    append_retrieval_default_strategy_summary as _append_retrieval_default_strategy_summary_impl,
)


def append_preference_observability_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_preference_observability_summary_impl(lines, results)


def append_feedback_observability_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_feedback_observability_summary_impl(lines, results)


def append_evidence_insufficiency_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_evidence_insufficiency_summary_impl(lines, results)


def append_missing_context_risk_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_missing_context_risk_summary_impl(lines, results)


def append_ltm_explainability_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_ltm_explainability_summary_impl(lines, results)


def append_feedback_loop_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_feedback_loop_summary_impl(lines, results)


def append_retrieval_context_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    _append_retrieval_context_observability_summary_impl(lines, results)


def append_retrieval_default_strategy_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_retrieval_default_strategy_summary_impl(lines, results)


def append_adaptive_router_observability_summary(
    lines: list[str],
    results: dict[str, Any],
) -> None:
    _append_adaptive_router_observability_summary_impl(lines, results)


def append_reward_log_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_reward_log_summary_impl(lines, results)


def append_wave1_context_governance_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_wave1_context_governance_summary_impl(lines, results)


def append_context_refine_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_context_refine_summary_impl(lines, results)


def append_retrieval_control_plane_gate_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_retrieval_control_plane_gate_summary_impl(lines, results)


def append_decision_observability_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_decision_observability_summary_impl(lines, results)


def append_workload_taxonomy_summary(lines: list[str], results: dict[str, Any]) -> None:
    _append_workload_taxonomy_summary_impl(lines, results)


def format_decision_event(event: dict[str, Any]) -> str:
    return _format_decision_event_impl(event)


__all__ = [
    "append_adaptive_router_observability_summary",
    "append_context_refine_summary",
    "append_decision_observability_summary",
    "append_evidence_insufficiency_summary",
    "append_feedback_loop_summary",
    "append_feedback_observability_summary",
    "append_ltm_explainability_summary",
    "append_missing_context_risk_summary",
    "append_preference_observability_summary",
    "append_retrieval_context_observability_summary",
    "append_retrieval_control_plane_gate_summary",
    "append_retrieval_default_strategy_summary",
    "append_reward_log_summary",
    "append_wave1_context_governance_summary",
    "append_workload_taxonomy_summary",
    "format_decision_event",
]
