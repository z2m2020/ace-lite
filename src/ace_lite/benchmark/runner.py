from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from ace_lite.benchmark.case_contracts import normalize_benchmark_case
from ace_lite.benchmark.report_metrics import ALL_METRIC_ORDER, normalize_metrics
from ace_lite.benchmark.scoring import (
    aggregate_metrics,
    build_adaptive_router_arm_summary,
    build_adaptive_router_observability_summary,
    build_adaptive_router_pair_summary,
    build_agent_loop_control_plane_summary,
    build_chunk_cache_contract_summary,
    build_chunk_stage_miss_summary,
    build_comparison_lane_summary,
    build_decision_observability_summary,
    build_deep_symbol_summary,
    build_evidence_insufficiency_summary,
    build_feedback_loop_summary,
    build_feedback_observability_summary,
    build_learning_router_rollout_summary,
    build_ltm_explainability_summary,
    build_missing_context_risk_summary,
    build_native_scip_summary,
    build_preference_observability_summary,
    build_repomap_seed_summary,
    build_retrieval_context_observability_summary,
    build_retrieval_control_plane_gate_summary,
    build_retrieval_default_strategy_summary,
    build_retrieval_frontier_gate_summary,
    build_slo_budget_summary,
    build_context_refine_summary,
    build_source_plan_card_summary,
    build_source_plan_failure_signal_summary,
    build_source_plan_validation_feedback_summary,
    build_stage_latency_summary,
    build_validation_branch_gate_summary,
    build_validation_branch_summary,
    build_validation_probe_summary,
    build_workload_taxonomy_summary,
    build_wave1_context_governance_summary,
    compare_metrics,
    detect_regression,
    evaluate_case_result,
    resolve_regression_thresholds,
)
from ace_lite.router_reward_store import make_reward_event


class BenchmarkRunner:
    _POLICY_COUNTER_KEYS = (
        "applied",
        "conflicts",
        "blocked",
        "warn",
        "remote_applied",
    )

    def __init__(
        self,
        orchestrator: Any,
        reward_log_writer: Any | None = None,
        reward_log_enabled: bool | None = None,
        reward_log_path: str = "",
        reward_log_init_error: str = "",
    ) -> None:
        self._orchestrator = orchestrator
        self._reward_log_writer = reward_log_writer
        self._reward_log_enabled = (
            bool(reward_log_writer is not None)
            if reward_log_enabled is None
            else bool(reward_log_enabled)
        )
        self._reward_log_path = str(reward_log_path or "").strip()
        self._reward_log_init_error = self._normalize_error(reward_log_init_error)

    @staticmethod
    def _normalize_error(value: Any, *, max_len: int = 256) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        return " ".join(raw.split())[:max_len]

    def _build_reward_log_summary(self) -> dict[str, Any]:
        enabled = bool(self._reward_log_enabled)
        active = bool(enabled and self._reward_log_writer is not None)
        init_error = self._reward_log_init_error
        error_count = 1 if enabled and init_error and not active else 0
        status = "disabled"
        if enabled:
            status = "enabled" if active and error_count <= 0 else "degraded"
        return {
            "enabled": enabled,
            "active": active,
            "status": status,
            "path": self._reward_log_path,
            "eligible_case_count": 0,
            "submitted_count": 0,
            "pending_count": 0,
            "written_count": 0,
            "error_count": error_count,
            "last_error": init_error,
        }

    @staticmethod
    def _merge_reward_log_stats(
        summary: dict[str, Any],
        stats: dict[str, Any],
    ) -> None:
        if "path" in stats:
            summary["path"] = stats["path"]
        if "pending_count" in stats:
            summary["pending_count"] = stats["pending_count"]
        if "written_count" in stats:
            summary["written_count"] = stats["written_count"]
        if "error_count" in stats:
            summary["error_count"] = (
                max(0, int(summary.get("error_count", 0) or 0))
                + max(0, int(stats.get("error_count", 0) or 0))
            )
        stats_last_error = BenchmarkRunner._normalize_error(stats.get("last_error", ""))
        if stats_last_error:
            summary["last_error"] = stats_last_error

    @staticmethod
    def _finalize_reward_log_status(summary: dict[str, Any]) -> None:
        enabled = bool(summary.get("enabled", False))
        active = bool(summary.get("active", False))
        error_count = max(0, int(summary.get("error_count", 0) or 0))
        last_error = str(summary.get("last_error") or "").strip()
        if not enabled:
            summary["status"] = "disabled"
        elif not active or error_count > 0 or last_error:
            summary["status"] = "degraded"
        else:
            summary["status"] = "enabled"

    @staticmethod
    def _iter_valid_cases(
        cases: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], str]]:
        valid: list[tuple[dict[str, Any], str]] = []
        for case in cases:
            query = str(case.get("query", "")).strip()
            if not query:
                continue
            valid.append((case, query))
        return valid

    @staticmethod
    def _resolve_case_plan_filters(case: dict[str, Any]) -> dict[str, Any] | None:
        filters = case.get("filters")
        if not isinstance(filters, dict) or not filters:
            return None
        return dict(filters)

    def _run_warmups(
        self,
        *,
        valid_cases: list[tuple[dict[str, Any], str]],
        repo: str,
        root: str,
        time_range: str | None,
        start_date: str | None,
        end_date: str | None,
        warmup_runs: int,
    ) -> int:
        if warmup_runs <= 0:
            return 0

        warmup_plans = 0
        for _ in range(warmup_runs):
            for case, query in valid_cases:
                plan_kwargs: dict[str, Any] = {
                    "query": query,
                    "repo": repo,
                    "root": root,
                    "time_range": time_range,
                    "start_date": start_date,
                    "end_date": end_date,
                }
                case_filters = self._resolve_case_plan_filters(case)
                if case_filters is not None:
                    plan_kwargs["filters"] = case_filters
                self._orchestrator.plan(
                    **plan_kwargs,
                )
                warmup_plans += 1
        return warmup_plans

    @classmethod
    def _extract_plugin_policy_summary(
        cls, plan_payload: dict[str, Any]
    ) -> dict[str, Any]:
        observability_raw = plan_payload.get("observability")
        observability: dict[str, Any] = (
            observability_raw if isinstance(observability_raw, dict) else {}
        )

        summary_raw = observability.get("plugin_policy_summary")
        summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}

        totals_candidate = summary.get("totals")
        totals_raw: dict[str, Any] = (
            totals_candidate if isinstance(totals_candidate, dict) else {}
        )
        totals = {
            key: max(0, int(totals_raw.get(key, 0) or 0))
            for key in cls._POLICY_COUNTER_KEYS
        }

        allowlist_candidate = summary.get("allowlist")
        allowlist_raw: list[Any] = (
            allowlist_candidate if isinstance(allowlist_candidate, list) else []
        )
        allowlist = [str(item).strip() for item in allowlist_raw if str(item).strip()]

        mode = str(summary.get("mode") or "").strip().lower()

        by_stage_candidate = summary.get("by_stage")
        by_stage_raw: list[Any] = (
            by_stage_candidate if isinstance(by_stage_candidate, list) else []
        )
        by_stage: list[dict[str, Any]] = []
        for item in by_stage_raw:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "").strip()
            if not stage:
                continue
            normalized = {
                key: max(0, int(item.get(key, 0) or 0))
                for key in cls._POLICY_COUNTER_KEYS
            }
            by_stage.append({"stage": stage, **normalized})

        return {
            "mode": mode,
            "allowlist": allowlist,
            "totals": totals,
            "by_stage": by_stage,
        }

    @classmethod
    def _aggregate_plugin_policy_summary(
        cls, case_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        totals = {key: 0 for key in cls._POLICY_COUNTER_KEYS}
        mode_distribution: dict[str, int] = {}
        allowlist_union: set[str] = set()
        by_stage_totals: dict[str, dict[str, int]] = {}

        for item in case_results:
            if not isinstance(item, dict):
                continue
            policy_raw = item.get("plugin_policy_summary")
            if not isinstance(policy_raw, dict):
                continue
            policy: dict[str, Any] = policy_raw

            policy_totals_candidate = policy.get("totals")
            policy_totals: dict[str, Any] = (
                policy_totals_candidate
                if isinstance(policy_totals_candidate, dict)
                else {}
            )
            for key in cls._POLICY_COUNTER_KEYS:
                totals[key] += max(0, int(policy_totals.get(key, 0) or 0))

            mode = str(policy.get("mode") or "").strip().lower()
            if mode:
                mode_distribution[mode] = mode_distribution.get(mode, 0) + 1

            allowlist_candidate = policy.get("allowlist")
            allowlist: list[Any] = (
                allowlist_candidate if isinstance(allowlist_candidate, list) else []
            )
            for slot in allowlist:
                normalized = str(slot).strip()
                if normalized:
                    allowlist_union.add(normalized)

            by_stage_candidate = policy.get("by_stage")
            by_stage_rows: list[Any] = (
                by_stage_candidate if isinstance(by_stage_candidate, list) else []
            )
            for row in by_stage_rows:
                if not isinstance(row, dict):
                    continue
                stage = str(row.get("stage") or "").strip()
                if not stage:
                    continue
                stage_bucket = by_stage_totals.setdefault(
                    stage, {key: 0 for key in cls._POLICY_COUNTER_KEYS}
                )
                for key in cls._POLICY_COUNTER_KEYS:
                    stage_bucket[key] += max(0, int(row.get(key, 0) or 0))

        count = max(1, len(case_results))
        per_case_mean = {
            key: float(totals[key]) / float(count) for key in cls._POLICY_COUNTER_KEYS
        }

        by_stage: list[dict[str, Any]] = []
        by_stage_per_case_mean: list[dict[str, Any]] = []
        for stage in sorted(by_stage_totals):
            counters = by_stage_totals[stage]
            by_stage.append({"stage": stage, **counters})
            by_stage_per_case_mean.append(
                {
                    "stage": stage,
                    **{
                        key: float(counters[key]) / float(count)
                        for key in cls._POLICY_COUNTER_KEYS
                    },
                }
            )

        dominant_mode = ""
        if mode_distribution:
            dominant_mode = sorted(
                mode_distribution.items(), key=lambda item: (-item[1], item[0])
            )[0][0]

        return {
            "mode": dominant_mode,
            "mode_distribution": mode_distribution,
            "allowlist": sorted(allowlist_union),
            "totals": totals,
            "per_case_mean": per_case_mean,
            "by_stage": by_stage,
            "by_stage_per_case_mean": by_stage_per_case_mean,
        }

    @staticmethod
    def _aggregate_task_success_summary(
        case_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        case_count = len(case_results)
        if case_count <= 0:
            return {
                "case_count": 0,
                "positive_case_count": 0,
                "negative_control_case_count": 0,
                "task_success_rate": 0.0,
                "positive_task_success_rate": 0.0,
                "negative_control_task_success_rate": 0.0,
                "retrieval_task_gap_count": 0,
                "retrieval_task_gap_rate": 0.0,
            }

        total_task_success = 0.0
        positive_case_count = 0
        positive_task_success = 0.0
        negative_control_case_count = 0
        negative_control_task_success = 0.0
        retrieval_task_gap_count = 0

        for item in case_results:
            if not isinstance(item, dict):
                continue

            task_success_hit = float(
                item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
            )
            total_task_success += task_success_hit

            mode = str(item.get("task_success_mode") or "").strip().lower() or "positive"
            if mode == "negative_control":
                negative_control_case_count += 1
                negative_control_task_success += task_success_hit
            else:
                positive_case_count += 1
                positive_task_success += task_success_hit

            recall_hit = float(item.get("recall_hit", 0.0) or 0.0)
            if recall_hit > 0.0 and task_success_hit <= 0.0:
                retrieval_task_gap_count += 1

        return {
            "case_count": case_count,
            "positive_case_count": positive_case_count,
            "negative_control_case_count": negative_control_case_count,
            "task_success_rate": total_task_success / float(case_count),
            "positive_task_success_rate": (
                positive_task_success / float(positive_case_count)
                if positive_case_count > 0
                else 0.0
            ),
            "negative_control_task_success_rate": (
                negative_control_task_success / float(negative_control_case_count)
                if negative_control_case_count > 0
                else 0.0
            ),
            "retrieval_task_gap_count": retrieval_task_gap_count,
            "retrieval_task_gap_rate": (
                float(retrieval_task_gap_count) / float(case_count)
            ),
        }

    @staticmethod
    def _build_router_reward_event(case_result: dict[str, Any]) -> dict[str, Any] | None:
        if float(case_result.get("router_enabled", 0.0) or 0.0) <= 0.0:
            return None
        query_id = str(case_result.get("case_id") or "").strip()
        chosen_arm_id = str(case_result.get("router_arm_id") or "").strip()
        if not query_id or not chosen_arm_id:
            return None
        return make_reward_event(
            query_id=query_id,
            chosen_arm_id=chosen_arm_id,
            shadow_arm_id=str(case_result.get("router_shadow_arm_id") or "").strip(),
            router_mode=str(case_result.get("router_mode") or "").strip(),
            context_features={
                "policy_profile": str(case_result.get("policy_profile") or "").strip(),
                "comparison_lane": str(case_result.get("comparison_lane") or "").strip(),
                "router_arm_set": str(case_result.get("router_arm_set") or "").strip(),
                "router_confidence": float(case_result.get("router_confidence", 0.0) or 0.0),
                "router_experiment_enabled": bool(
                    float(
                        case_result.get("router_experiment_enabled", 0.0) or 0.0
                    )
                    > 0.0
                ),
                "router_fallback_applied": bool(
                    float(case_result.get("router_fallback_applied", 0.0) or 0.0) > 0.0
                ),
                "router_fallback_reason": str(
                    case_result.get("router_fallback_reason") or ""
                ).strip(),
            },
            is_exploration=bool(
                float(case_result.get("router_is_exploration", 0.0) or 0.0) > 0.0
            ),
            reward_source="benchmark_task_success",
            reward_value=float(
                case_result.get(
                    "task_success_hit",
                    case_result.get("utility_hit", 0.0),
                )
                or 0.0
            ),
            reward_metadata={
                "precision_at_k": float(case_result.get("precision_at_k", 0.0) or 0.0),
                "noise_rate": float(case_result.get("noise_rate", 0.0) or 0.0),
                "latency_ms": float(case_result.get("latency_ms", 0.0) or 0.0),
                "task_success_mode": str(case_result.get("task_success_mode") or "").strip(),
            },
        )

    def run(
        self,
        *,
        cases: list[dict[str, Any]],
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        baseline_metrics: dict[str, float] | None = None,
        threshold_profile: str = "default",
        threshold_overrides: dict[str, float] | None = None,
        warmup_runs: int = 0,
        include_plan_payload: bool = True,
        include_case_details: bool = True,
    ) -> dict[str, Any]:
        resolved_warmup_runs = max(0, int(warmup_runs))
        valid_cases = self._iter_valid_cases(cases)
        reward_log_summary = self._build_reward_log_summary()
        warmup_plans = self._run_warmups(
            valid_cases=valid_cases,
            repo=repo,
            root=root,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            warmup_runs=resolved_warmup_runs,
        )

        case_results: list[dict[str, Any]] = []
        for case, query in valid_cases:
            started = perf_counter()
            plan_kwargs: dict[str, Any] = {
                "query": query,
                "repo": repo,
                "root": root,
                "time_range": time_range,
                "start_date": start_date,
                "end_date": end_date,
            }
            case_filters = self._resolve_case_plan_filters(case)
            if case_filters is not None:
                plan_kwargs["filters"] = case_filters
            payload = self._orchestrator.plan(**plan_kwargs)
            latency_ms = (perf_counter() - started) * 1000.0

            case_result = evaluate_case_result(
                case=case,
                plan_payload=payload,
                latency_ms=latency_ms,
                include_case_details=include_case_details,
            )
            case_result["plugin_policy_summary"] = self._extract_plugin_policy_summary(
                payload
            )
            if include_plan_payload:
                case_result["plan"] = payload
            case_results.append(case_result)
            reward_event = self._build_router_reward_event(case_result)
            if reward_event is not None:
                reward_log_summary["eligible_case_count"] = (
                    max(0, int(reward_log_summary.get("eligible_case_count", 0) or 0)) + 1
                )
                if self._reward_log_writer is not None:
                    try:
                        self._reward_log_writer.submit(event=reward_event)
                    except Exception as exc:
                        reward_log_summary["error_count"] = (
                            max(0, int(reward_log_summary.get("error_count", 0) or 0)) + 1
                        )
                        reward_log_summary["last_error"] = self._normalize_error(exc)
                    else:
                        reward_log_summary["submitted_count"] = (
                            max(0, int(reward_log_summary.get("submitted_count", 0) or 0))
                            + 1
                        )

        if self._reward_log_writer is not None:
            try:
                flush_stats = self._reward_log_writer.flush()
            except Exception as exc:
                reward_log_summary["error_count"] = (
                    max(0, int(reward_log_summary.get("error_count", 0) or 0)) + 1
                )
                reward_log_summary["last_error"] = self._normalize_error(exc)
            else:
                if isinstance(flush_stats, dict):
                    self._merge_reward_log_stats(reward_log_summary, flush_stats)

        self._finalize_reward_log_status(reward_log_summary)

        metrics = aggregate_metrics(case_results)
        policy_profile_distribution: dict[str, int] = {}
        for item in case_results:
            if not isinstance(item, dict):
                continue
            profile = str(item.get("policy_profile") or "").strip() or "(unknown)"
            policy_profile_distribution[profile] = (
                policy_profile_distribution.get(profile, 0) + 1
            )

        output: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo": repo,
            "root": root,
            "case_count": len(case_results),
            "metrics": metrics,
            "stage_latency_summary": build_stage_latency_summary(case_results),
            "slo_budget_summary": build_slo_budget_summary(case_results),
            "task_success_summary": self._aggregate_task_success_summary(case_results),
            "decision_observability_summary": build_decision_observability_summary(
                case_results
            ),
            "adaptive_router_arm_summary": build_adaptive_router_arm_summary(
                case_results
            ),
            "learning_router_rollout_summary": build_learning_router_rollout_summary(
                case_results
            ),
            "adaptive_router_observability_summary": (
                build_adaptive_router_observability_summary(case_results)
            ),
            "adaptive_router_pair_summary": build_adaptive_router_pair_summary(
                case_results
            ),
            "comparison_lane_summary": build_comparison_lane_summary(case_results),
            "evidence_insufficiency_summary": build_evidence_insufficiency_summary(
                case_results
            ),
            "missing_context_risk_summary": build_missing_context_risk_summary(
                case_results
            ),
            "feedback_loop_summary": build_feedback_loop_summary(case_results),
            "feedback_observability_summary": build_feedback_observability_summary(
                case_results
            ),
            "context_refine_summary": build_context_refine_summary(case_results),
            "workload_taxonomy_summary": build_workload_taxonomy_summary(case_results),
            "ltm_explainability_summary": build_ltm_explainability_summary(
                case_results
            ),
            "preference_observability_summary": (
                build_preference_observability_summary(case_results)
            ),
            "retrieval_default_strategy_summary": (
                build_retrieval_default_strategy_summary(case_results)
            ),
            "agent_loop_control_plane_summary": (
                build_agent_loop_control_plane_summary(case_results)
            ),
            "retrieval_context_observability_summary": (
                build_retrieval_context_observability_summary(case_results)
            ),
            "chunk_cache_contract_summary": build_chunk_cache_contract_summary(
                case_results
            ),
            "chunk_stage_miss_summary": build_chunk_stage_miss_summary(case_results),
            "cases": case_results,
            "warmup_runs": resolved_warmup_runs,
            "warmup_plan_calls": warmup_plans,
            "include_plan_payload": bool(include_plan_payload),
            "include_case_details": bool(include_case_details),
            "reward_log_summary": reward_log_summary,
            "plugin_policy_summary": self._aggregate_plugin_policy_summary(
                case_results
            ),
            "policy_profile_distribution": policy_profile_distribution,
        }

        if baseline_metrics is not None:
            thresholds = resolve_regression_thresholds(
                profile=threshold_profile, overrides=threshold_overrides
            )
            output["threshold_profile"] = threshold_profile
            output["regression_thresholds"] = thresholds
            output["baseline_metrics"] = baseline_metrics
            output["delta"] = compare_metrics(
                current=metrics, baseline=baseline_metrics
            )
            output["regression"] = detect_regression(
                current=metrics, baseline=baseline_metrics, **thresholds
            )

        output["retrieval_control_plane_gate_summary"] = (
            build_retrieval_control_plane_gate_summary(
                metrics=metrics,
                regression=output.get("regression"),
            )
        )
        output["retrieval_frontier_gate_summary"] = (
            build_retrieval_frontier_gate_summary(metrics=metrics)
        )
        output["repomap_seed_summary"] = build_repomap_seed_summary(metrics=metrics)
        output["deep_symbol_summary"] = build_deep_symbol_summary(metrics=metrics)
        output["native_scip_summary"] = build_native_scip_summary(metrics=metrics)
        output["validation_probe_summary"] = build_validation_probe_summary(
            metrics=metrics
        )
        output["validation_branch_summary"] = build_validation_branch_summary(
            metrics=metrics
        )
        output["validation_branch_gate_summary"] = (
            build_validation_branch_gate_summary(metrics=metrics)
        )
        output["source_plan_card_summary"] = build_source_plan_card_summary(
            metrics=metrics
        )
        output["source_plan_failure_signal_summary"] = (
            build_source_plan_failure_signal_summary(metrics=metrics)
        )
        output["source_plan_validation_feedback_summary"] = (
            build_source_plan_validation_feedback_summary(metrics=metrics)
        )
        output["wave1_context_governance_summary"] = (
            build_wave1_context_governance_summary(case_results)
        )

        return output


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    data = yaml.safe_load(source.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        if isinstance(data.get("cases"), list):
            return [
                normalize_benchmark_case(item)
                for item in data["cases"]
                if isinstance(item, dict)
            ]
        return []

    if isinstance(data, list):
        return [normalize_benchmark_case(item) for item in data if isinstance(item, dict)]

    return []


def load_baseline_metrics(path: str | Path) -> dict[str, float] | None:
    source = Path(path)
    if not source.exists() or not source.is_file():
        return None

    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None

    metrics_raw = raw.get("metrics", raw)
    if not isinstance(metrics_raw, dict):
        return None
    metrics = normalize_metrics(metrics_raw)
    return {
        metric: float(metrics.get(metric, 0.0) or 0.0) for metric in ALL_METRIC_ORDER
    }


__all__ = ["BenchmarkRunner", "load_baseline_metrics", "load_cases"]
