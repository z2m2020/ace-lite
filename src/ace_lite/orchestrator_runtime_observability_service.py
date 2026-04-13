from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.types import StageMetric
from ace_lite.runtime_stats import (
    RuntimeInvocationStats,
    normalize_runtime_stage_latencies,
)
from ace_lite.tracing import export_stage_trace_jsonl, export_stage_trace_otlp

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DurableStatsTagRule:
    tag: str
    reasons: tuple[str, ...]
    min_int: int | None = None

    def matches(self, tags: dict[str, Any]) -> bool:
        if self.min_int is not None:
            try:
                return int(tags.get(self.tag, 0) or 0) >= self.min_int
            except Exception:
                return False
        return bool(tags.get(self.tag, False))


REPLAY_REASON_RULES: dict[str, tuple[str, ...]] = {
    "invalid_cached_payload": ("plan_replay_invalid_cached_payload",),
    "store_failed": ("plan_replay_store_failed",),
}

COMMON_TAG_RULES: tuple[DurableStatsTagRule, ...] = (
    DurableStatsTagRule(tag="slot_policy_blocked", reasons=("plugin_policy_blocked",), min_int=1),
    DurableStatsTagRule(tag="slot_policy_warn", reasons=("plugin_policy_warn",), min_int=1),
)

STAGE_TAG_RULES: dict[str, tuple[DurableStatsTagRule, ...]] = {
    "memory": (
        DurableStatsTagRule(tag="fallback", reasons=("memory_fallback",)),
        DurableStatsTagRule(
            tag="memory_namespace_fallback",
            reasons=("memory_namespace_fallback",),
        ),
    ),
    "index": (
        DurableStatsTagRule(
            tag="candidate_ranker_fallback",
            reasons=("candidate_ranker_fallback",),
        ),
        DurableStatsTagRule(
            tag="embedding_time_budget_exceeded",
            reasons=("embedding_time_budget_exceeded", "latency_budget_exceeded"),
        ),
        DurableStatsTagRule(
            tag="embedding_fallback",
            reasons=("embedding_fallback",),
        ),
        DurableStatsTagRule(
            tag="chunk_semantic_time_budget_exceeded",
            reasons=("chunk_semantic_time_budget_exceeded", "latency_budget_exceeded"),
        ),
        DurableStatsTagRule(
            tag="chunk_semantic_fallback",
            reasons=("chunk_semantic_fallback",),
        ),
        DurableStatsTagRule(
            tag="chunk_guard_fallback",
            reasons=("chunk_guard_fallback",),
        ),
        DurableStatsTagRule(
            tag="parallel_docs_timed_out",
            reasons=("parallel_docs_timeout", "latency_budget_exceeded"),
        ),
        DurableStatsTagRule(
            tag="parallel_worktree_timed_out",
            reasons=("parallel_worktree_timeout", "latency_budget_exceeded"),
        ),
        DurableStatsTagRule(
            tag="router_fallback_applied",
            reasons=("router_fallback_applied",),
        ),
    ),
    "augment": (
        DurableStatsTagRule(
            tag="xref_budget_exhausted",
            reasons=("xref_budget_exhausted", "latency_budget_exceeded"),
        ),
    ),
    "skills": (
        DurableStatsTagRule(
            tag="budget_exhausted",
            reasons=("skills_budget_exhausted",),
        ),
        DurableStatsTagRule(
            tag="skipped_for_budget_count",
            reasons=("skills_budget_exhausted",),
            min_int=1,
        ),
    ),
}


@dataclass(slots=True)
class RuntimeObservabilityService:
    config: Any
    pipeline_order: tuple[str, ...]
    resolve_repo_relative_path_fn: Callable[..., Path]
    durable_stats_store_factory: Callable[[], Any]
    durable_stats_session_id: str

    def export_stage_trace(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
        total_ms: float,
        stage_metrics: list[StageMetric],
        plugin_policy_summary: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.config.trace.export_enabled and not self.config.trace.otlp_enabled:
            return {"enabled": False}

        result: dict[str, Any] = {"enabled": True}

        if self.config.trace.export_enabled:
            output_path = self.resolve_repo_relative_path_fn(
                root=root,
                configured_path=str(self.config.trace.export_path),
            )
            try:
                result.update(
                    export_stage_trace_jsonl(
                        output_path=output_path,
                        query=query,
                        repo=repo,
                        root=root,
                        started_at=started_at,
                        total_ms=total_ms,
                        stage_metrics=stage_metrics,
                        pipeline_order=list(self.pipeline_order),
                        plugin_policy_summary=plugin_policy_summary,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "trace.export.error",
                    extra={
                        "path": str(output_path),
                        "error": str(exc),
                    },
                )
                result.update(
                    {
                        "exported": False,
                        "path": str(output_path),
                        "error": str(exc),
                    }
                )

        if self.config.trace.otlp_enabled:
            endpoint = str(self.config.trace.otlp_endpoint)
            resolved_endpoint = endpoint
            if endpoint.startswith("file://"):
                raw_path = endpoint.replace("file://", "", 1)
                candidate = Path(raw_path)
                if not candidate.is_absolute():
                    resolved = self.resolve_repo_relative_path_fn(
                        root=root,
                        configured_path=raw_path,
                    )
                    resolved_endpoint = f"file://{resolved}"
            elif endpoint and not endpoint.startswith(("http://", "https://")):
                resolved_endpoint = str(
                    self.resolve_repo_relative_path_fn(
                        root=root,
                        configured_path=endpoint,
                    )
                )

            try:
                otlp_result = export_stage_trace_otlp(
                    endpoint=resolved_endpoint,
                    query=query,
                    repo=repo,
                    root=root,
                    started_at=started_at,
                    total_ms=total_ms,
                    stage_metrics=stage_metrics,
                    pipeline_order=list(self.pipeline_order),
                    plugin_policy_summary=plugin_policy_summary,
                    timeout_seconds=self.config.trace.otlp_timeout_seconds,
                )
                result["otlp"] = otlp_result
                if not self.config.trace.export_enabled:
                    result["exported"] = bool(otlp_result.get("exported", False))
                    result["trace_id"] = otlp_result.get("trace_id", "")
                    result["otel_trace_id"] = otlp_result.get("otel_trace_id", "")
                    result["span_count"] = int(otlp_result.get("span_count", 0) or 0)
                    result["format"] = "otlp"
            except Exception as exc:
                logger.warning(
                    "trace.otlp.export.error",
                    extra={
                        "endpoint": str(resolved_endpoint),
                        "error": str(exc),
                    },
                )
                result["otlp"] = {
                    "enabled": True,
                    "exported": False,
                    "endpoint": str(resolved_endpoint),
                    "error": str(exc),
                }

        return result

    def record_durable_stats(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
        total_ms: float,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
        learning_router_rollout_decision: dict[str, Any],
    ) -> dict[str, Any]:
        invocation_id = self.build_invocation_id(
            query=query,
            repo=repo,
            root=root,
            started_at=started_at,
        )
        degraded_reason_codes = self.collect_durable_stats_reasons(
            stage_metrics=stage_metrics,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
            trace_export=trace_export,
        )
        status = self.derive_status(
            contract_error=contract_error,
            degraded_reason_codes=degraded_reason_codes,
        )
        learning_router_payload = dict(learning_router_rollout_decision)
        try:
            store = self.durable_stats_store_factory()
            store.record_invocation(
                RuntimeInvocationStats(
                    invocation_id=invocation_id,
                    session_id=self.durable_stats_session_id,
                    repo_key=repo,
                    status=status,
                    total_latency_ms=round(float(total_ms), 6),
                    started_at=started_at.astimezone(timezone.utc).isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    contract_error_code=contract_error.error_code
                    if contract_error is not None
                    else "",
                    degraded_reason_codes=tuple(degraded_reason_codes),
                    stage_latencies=normalize_runtime_stage_latencies(
                        tuple(
                            {"stage_name": item.stage, "elapsed_ms": item.elapsed_ms}
                            for item in stage_metrics
                        )
                        + (
                            {
                                "stage_name": "total",
                                "elapsed_ms": round(float(total_ms), 6),
                            },
                        )
                    ),
                    learning_router_rollout_decision=learning_router_payload,
                    plan_replay_hit=bool((replay_cache_info or {}).get("hit", False)),
                    plan_replay_safe_hit=bool(
                        (replay_cache_info or {}).get("safe_hit", False)
                    ),
                    plan_replay_store_written=bool(
                        (replay_cache_info or {}).get("stored", False)
                    ),
                    trace_exported=bool(trace_export.get("exported", False)),
                    trace_export_failed=bool(
                        trace_export.get("enabled", False)
                        and not trace_export.get("exported", False)
                    ),
                )
            )
            return {
                "enabled": True,
                "recorded": True,
                "session_id": self.durable_stats_session_id,
                "invocation_id": invocation_id,
                "status": status,
                "db_path": str(getattr(store, "db_path", "")),
                "learning_router_rollout_decision": learning_router_payload,
            }
        except Exception as exc:
            logger.warning(
                "durable.stats.record.error",
                extra={"repo": repo, "error": str(exc)},
            )
            return {
                "enabled": True,
                "recorded": False,
                "session_id": self.durable_stats_session_id,
                "invocation_id": invocation_id,
                "status": status,
                "error": str(exc),
                "learning_router_rollout_decision": learning_router_payload,
            }

    @staticmethod
    def build_invocation_id(
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
    ) -> str:
        invocation_seed = "|".join(
            (
                repo,
                root,
                query,
                started_at.astimezone(timezone.utc).isoformat(),
            )
        )
        return hashlib.sha256(invocation_seed.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def derive_status(
        *,
        contract_error: StageContractError | None,
        degraded_reason_codes: list[str],
    ) -> str:
        if contract_error is not None:
            return "failed"
        if degraded_reason_codes:
            return "degraded"
        return "succeeded"

    @staticmethod
    def collect_durable_stats_reasons(
        *,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
    ) -> list[str]:
        reasons: set[str] = set()
        if contract_error is not None:
            reasons.add("contract_error")
        replay_reason = str((replay_cache_info or {}).get("reason") or "").strip().lower()
        reasons.update(REPLAY_REASON_RULES.get(replay_reason, ()))
        if trace_export.get("enabled", False) and not trace_export.get("exported", False):
            reasons.add("trace_export_failed")
        for metric in stage_metrics:
            tags = metric.tags if isinstance(metric.tags, dict) else {}
            RuntimeObservabilityService._apply_tag_rules(
                tags=tags,
                rules=COMMON_TAG_RULES,
                reasons=reasons,
            )
            RuntimeObservabilityService._apply_tag_rules(
                tags=tags,
                rules=STAGE_TAG_RULES.get(metric.stage, ()),
                reasons=reasons,
            )
            if metric.stage == "validation":
                reasons.update(
                    RuntimeObservabilityService._collect_validation_reasons(tags=tags)
                )
            if metric.stage == "source_plan":
                reasons.update(
                    RuntimeObservabilityService._collect_source_plan_reasons(tags=tags)
                )
            if metric.stage == "agent_loop":
                reasons.update(
                    RuntimeObservabilityService._collect_agent_loop_reasons(tags=tags)
                )
        return sorted(reasons)

    @staticmethod
    def _apply_tag_rules(
        *,
        tags: dict[str, Any],
        rules: tuple[DurableStatsTagRule, ...],
        reasons: set[str],
    ) -> None:
        for rule in rules:
            if rule.matches(tags):
                reasons.update(rule.reasons)

    @staticmethod
    def _collect_validation_reasons(*, tags: dict[str, Any]) -> set[str]:
        reasons: set[str] = set()
        validation_reason = str(tags.get("reason") or "").strip().lower()
        sandbox_apply_reason = str(tags.get("sandbox_apply_reason") or "").strip().lower()
        sandbox_apply_timed_out = bool(tags.get("sandbox_apply_timed_out", False))
        if sandbox_apply_timed_out or sandbox_apply_reason == "timeout":
            reasons.update({"validation_timeout", "latency_budget_exceeded"})
        elif (
            validation_reason == "patch_apply_failed"
            or sandbox_apply_reason == "apply_failed"
        ):
            reasons.add("validation_apply_failed")
        return reasons

    @staticmethod
    def _collect_source_plan_reasons(*, tags: dict[str, Any]) -> set[str]:
        reasons: set[str] = set()
        direct_count = int(tags.get("evidence_direct_count", 0) or 0)
        neighbor_count = int(tags.get("evidence_neighbor_context_count", 0) or 0)
        hint_only_count = int(tags.get("evidence_hint_only_count", 0) or 0)
        candidate_chunk_count = int(tags.get("candidate_chunk_count", 0) or 0)
        validation_test_count = int(tags.get("validation_test_count", 0) or 0)
        hint_only_ratio = RuntimeObservabilityService._safe_float(
            tags.get("evidence_hint_only_ratio", 0.0)
        )
        if validation_test_count <= 0:
            reasons.add("evidence_insufficient")
        if direct_count <= 0 and (
            candidate_chunk_count <= 0
            or hint_only_count > 0
            or neighbor_count > 0
        ):
            reasons.add("evidence_insufficient")
        if direct_count > 0 and hint_only_count > 0 and hint_only_ratio >= 0.5:
            reasons.add("noisy_hit")
        return reasons

    @staticmethod
    def _collect_agent_loop_reasons(*, tags: dict[str, Any]) -> set[str]:
        reasons: set[str] = set()
        stop_reason = str(tags.get("stop_reason") or "").strip().lower()
        iteration_count = int(tags.get("iteration_count", 0) or 0)
        if stop_reason == "max_iterations" and iteration_count > 0:
            reasons.add("repeated_retry")
        return reasons

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0


__all__ = [
    "COMMON_TAG_RULES",
    "REPLAY_REASON_RULES",
    "STAGE_TAG_RULES",
    "DurableStatsTagRule",
    "RuntimeObservabilityService",
]
