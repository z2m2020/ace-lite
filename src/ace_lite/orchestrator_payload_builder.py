from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_contracts import (
    PlanResponsePayload,
    project_orchestrator_state,
    validate_plan_response,
)
from ace_lite.pipeline.types import StageContext, StageMetric
from ace_lite.retrieval_shared import build_guarded_rollout_payload
from ace_lite.runtime_stats import build_learning_router_rollout_decision_payload
from ace_lite.schema import SCHEMA_VERSION
from ace_lite.validation.result import build_validation_result_v1


def build_default_validation_payload(*, policy_version: str) -> dict[str, Any]:
    result_payload = build_validation_result_v1(
        selected_tests=[],
        available_probes=["compile", "import", "tests"],
        sandboxed=False,
        runner="disabled",
        replay_key="",
        status="skipped",
    ).as_dict()
    return {
        "enabled": False,
        "reason": "disabled",
        "sandbox": {
            "enabled": False,
            "sandbox_root": "",
            "patch_applied": False,
            "cleanup_ok": False,
            "restore_ok": False,
            "apply_result": {},
        },
        "diagnostics": [],
        "diagnostic_count": 0,
        "xref_enabled": False,
        "xref": {
            "count": 0,
            "results": [],
            "errors": [],
            "budget_exhausted": False,
            "elapsed_ms": 0.0,
            "time_budget_ms": 0,
        },
        "probes": dict(result_payload.get("probes", {})),
        "result": result_payload,
        "patch_artifact_present": False,
        "policy_name": "general",
        "policy_version": str(policy_version),
    }


def build_orchestrator_plan_payload(
    *,
    query: str,
    repo: str,
    root: str,
    conventions: dict[str, Any],
    ctx: StageContext,
    stage_metrics: list[StageMetric],
    plugins_loaded: list[str],
    total_ms: float,
    contract_error: StageContractError | None,
    replay_cache_info: dict[str, Any] | None,
    pipeline_order: tuple[str, ...],
    policy_version: str,
    build_plugin_policy_summary_fn: Callable[[dict[str, Any], tuple[str, ...]], dict[str, Any]],
    extract_source_plan_failure_signal_summary_fn: Callable[[Any], dict[str, Any]],
    extract_source_plan_validation_feedback_summary_fn: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    projected = project_orchestrator_state(
        ctx.state,
        default_validation_payload=build_default_validation_payload(
            policy_version=policy_version
        ),
    )
    observability: dict[str, Any] = {
        "total_ms": total_ms,
        "stage_metrics": [
            {
                "stage": metric.stage,
                "elapsed_ms": metric.elapsed_ms,
                "plugins": metric.plugins,
                "tags": metric.tags,
            }
            for metric in stage_metrics
        ],
        "plugins_loaded": plugins_loaded,
        "plugin_action_log": list(projected["plugin_action_log"]),
        "plugin_conflicts": list(projected["plugin_conflicts"]),
        "plugin_policy_summary": build_plugin_policy_summary_fn(
            stage_summary=projected["plugin_policy_stage"],
            pipeline_order=pipeline_order,
        ),
    }
    if isinstance(replay_cache_info, dict):
        observability["plan_replay_cache"] = dict(replay_cache_info)
    observability["source_plan_failure_signal_summary"] = (
        extract_source_plan_failure_signal_summary_fn(projected["source_plan"])
    )
    adaptive_router = projected["index"].get("adaptive_router", {})
    if not isinstance(adaptive_router, dict):
        adaptive_router = {}
    card_summary = projected["source_plan"].get("card_summary", {})
    if not isinstance(card_summary, dict):
        card_summary = {}
    learning_router_rollout_decision = build_learning_router_rollout_decision_payload(
        adaptive_router=adaptive_router,
        card_summary=card_summary,
        validation_feedback_summary=extract_source_plan_validation_feedback_summary_fn(
            projected["source_plan"]
        ),
        failure_signal_summary=observability["source_plan_failure_signal_summary"],
    )
    observability["learning_router_rollout_decision"] = learning_router_rollout_decision
    guarded_rollout = build_guarded_rollout_payload(
        rollout_decision=learning_router_rollout_decision,
        enabled=False,
    )
    index_stage = projected["index"]
    if isinstance(index_stage, dict):
        adaptive_router = index_stage.get("adaptive_router", {})
        if isinstance(adaptive_router, dict):
            adaptive_router["guarded_rollout"] = dict(guarded_rollout)
    observability["guarded_rollout"] = dict(guarded_rollout)
    if projected["agent_loop"]:
        observability["agent_loop"] = dict(projected["agent_loop"])
    if projected["long_term_capture"]:
        observability["long_term_capture"] = list(projected["long_term_capture"])

    payload: PlanResponsePayload = {
        "schema_version": SCHEMA_VERSION,
        "query": query,
        "repo": repo,
        "root": root,
        "pipeline_order": list(pipeline_order),
        "conventions": {
            "count": conventions.get("count", 0),
            "rules_count": conventions.get("rules_count", 0),
            "loaded_files": [
                {
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                }
                for item in conventions.get("loaded_files", [])
                if isinstance(item, dict)
            ],
            "rules": [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "priority": item.get("priority", 0),
                    "always_load": bool(item.get("always_load", False)),
                    "globs": item.get("globs", []),
                }
                for item in conventions.get("rules", [])
                if isinstance(item, dict)
            ],
            "cache_hit": conventions.get("cache_hit", False),
        },
        "memory": projected["memory"],
        "index": projected["index"],
        "repomap": projected["repomap"],
        "augment": projected["augment"],
        "skills": projected["skills"],
        "source_plan": projected["source_plan"],
        "validation": projected["validation"],
        "observability": observability,
    }

    if contract_error is not None:
        payload["observability"]["error"] = {
            "type": "stage_contract_error",
            "stage": contract_error.stage or "",
            "error_code": contract_error.error_code,
            "reason": contract_error.reason,
            "message": contract_error.message,
            "context": contract_error.context,
        }
        payload["observability"]["contract_errors"] = list(projected["contract_errors"])

    return validate_plan_response(payload)


__all__ = ["build_default_validation_payload", "build_orchestrator_plan_payload"]
