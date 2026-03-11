from __future__ import annotations

from typing import Any

import click

from ace_lite.cli_app.config_resolve import _resolve_from_config
from ace_lite.cli_app.params import _to_bool, _to_float, _to_int
from ace_lite.router_reward_store import DEFAULT_REWARD_LOG_PATH


def resolve_benchmark_threshold_settings(
    *,
    ctx: click.Context,
    config: dict[str, Any],
    benchmark_threshold_profile: str,
    precision_tolerance: float | None,
    noise_tolerance: float | None,
    latency_growth_factor: float | None,
    dependency_recall_floor: float | None,
    chunk_hit_tolerance: float | None,
    chunk_budget_growth_factor: float | None,
    validation_test_growth_factor: float | None,
    notes_hit_tolerance: float | None,
    profile_selected_tolerance: float | None,
    capture_trigger_tolerance: float | None,
    embedding_similarity_tolerance: float | None,
    embedding_rerank_ratio_tolerance: float | None,
    embedding_cache_hit_tolerance: float | None,
    embedding_fallback_tolerance: float | None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "benchmark_threshold_profile": _resolve_from_config(
            ctx=ctx,
            param_name="benchmark_threshold_profile",
            current=benchmark_threshold_profile,
            config=config,
            paths=[("benchmark", "threshold_profile")],
            transform=lambda value: str(value).strip().lower(),
        ),
    }
    for name, current in (
        ("precision_tolerance", precision_tolerance),
        ("noise_tolerance", noise_tolerance),
        ("latency_growth_factor", latency_growth_factor),
        ("dependency_recall_floor", dependency_recall_floor),
        ("chunk_hit_tolerance", chunk_hit_tolerance),
        ("chunk_budget_growth_factor", chunk_budget_growth_factor),
        ("validation_test_growth_factor", validation_test_growth_factor),
        ("notes_hit_tolerance", notes_hit_tolerance),
        ("profile_selected_tolerance", profile_selected_tolerance),
        ("capture_trigger_tolerance", capture_trigger_tolerance),
        ("embedding_similarity_tolerance", embedding_similarity_tolerance),
        ("embedding_rerank_ratio_tolerance", embedding_rerank_ratio_tolerance),
        ("embedding_cache_hit_tolerance", embedding_cache_hit_tolerance),
        ("embedding_fallback_tolerance", embedding_fallback_tolerance),
    ):
        values[name] = _resolve_from_config(
            ctx=ctx,
            param_name=name,
            current=current,
            config=config,
            paths=[("benchmark", "thresholds", name)],
            transform=_to_float,
        )
    return values


def resolve_benchmark_run_settings(
    *,
    ctx: click.Context,
    config: dict[str, Any],
    warmup_runs: int,
    include_plans: bool,
    include_case_details: bool,
    reward_log_enabled: bool,
    reward_log_path: str,
    precomputed_skills_routing_enabled: bool,
) -> dict[str, Any]:
    return {
        "warmup_runs": _resolve_from_config(
            ctx=ctx,
            param_name="warmup_runs",
            current=warmup_runs,
            config=config,
            paths=[("benchmark", "warmup_runs")],
            transform=_to_int,
        ),
        "include_plans": _resolve_from_config(
            ctx=ctx,
            param_name="include_plans",
            current=include_plans,
            config=config,
            paths=[("benchmark", "include_plans")],
            transform=_to_bool,
        ),
        "include_case_details": _resolve_from_config(
            ctx=ctx,
            param_name="include_case_details",
            current=include_case_details,
            config=config,
            paths=[("benchmark", "include_case_details")],
            transform=_to_bool,
        ),
        "reward_log_enabled": _resolve_from_config(
            ctx=ctx,
            param_name="reward_log_enabled",
            current=reward_log_enabled,
            config=config,
            paths=[
                ("benchmark", "reward_log", "enabled"),
                ("benchmark", "reward_log_enabled"),
            ],
            transform=_to_bool,
        ),
        "reward_log_path": _resolve_from_config(
            ctx=ctx,
            param_name="reward_log_path",
            current=reward_log_path,
            config=config,
            paths=[
                ("benchmark", "reward_log", "path"),
                ("benchmark", "reward_log_path"),
            ],
            transform=lambda value: str(value or "").strip() or DEFAULT_REWARD_LOG_PATH,
        ),
        "precomputed_skills_routing_enabled": _resolve_from_config(
            ctx=ctx,
            param_name="precomputed_skills_routing_enabled",
            current=precomputed_skills_routing_enabled,
            config=config,
            paths=[
                ("benchmark", "skills", "precomputed_routing_enabled"),
                ("benchmark", "precomputed_skills_routing_enabled"),
            ],
            transform=_to_bool,
        ),
    }


def build_threshold_overrides(settings: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in settings.items()
        if key != "benchmark_threshold_profile" and value is not None
    }


def run_benchmark_and_write_outputs(
    *,
    orchestrator: Any,
    cases: list[dict[str, Any]],
    repo: str,
    root: str,
    time_range: str | None,
    start_date: str | None,
    end_date: str | None,
    baseline_metrics: dict[str, Any] | None,
    threshold_profile: str,
    threshold_overrides: dict[str, float],
    warmup_runs: int,
    include_plan_payload: bool,
    include_case_details: bool,
    reward_log_enabled: bool,
    reward_log_path: str,
    output_dir: str,
    runner_cls: Any,
    reward_log_writer_cls: Any,
    write_results_fn: Any,
    echo_json_fn: Any,
    merge_reward_log_summary_fn: Any,
) -> dict[str, Any]:
    reward_log_writer: Any = None
    reward_log_init_error = ""
    if reward_log_enabled:
        try:
            reward_log_writer = reward_log_writer_cls(path=reward_log_path)
        except Exception as exc:
            reward_log_init_error = " ".join(str(exc).split())[:256]

    runner = runner_cls(
        orchestrator,
        reward_log_writer=reward_log_writer,
        reward_log_enabled=bool(reward_log_enabled),
        reward_log_path=str(reward_log_path),
        reward_log_init_error=reward_log_init_error,
    )
    results = runner.run(
        cases=cases,
        repo=repo,
        root=root,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        baseline_metrics=baseline_metrics,
        threshold_profile=threshold_profile,
        threshold_overrides=threshold_overrides,
        warmup_runs=max(0, int(warmup_runs)),
        include_plan_payload=bool(include_plan_payload),
        include_case_details=bool(include_case_details),
    )
    reward_log_summary = results.get("reward_log_summary")
    if reward_log_writer is not None:
        try:
            close_stats = reward_log_writer.close()
        except Exception as exc:
            if isinstance(reward_log_summary, dict):
                reward_log_summary["error_count"] = (
                    max(0, int(reward_log_summary.get("error_count", 0) or 0)) + 1
                )
                reward_log_summary["last_error"] = " ".join(str(exc).split())[:256]
                reward_log_summary["status"] = "degraded"
        else:
            if isinstance(reward_log_summary, dict):
                merge_reward_log_summary_fn(reward_log_summary, close_stats)
    outputs = write_results_fn(results, output_dir=output_dir)
    echo_json_fn(outputs)
    return results


__all__ = [
    "build_threshold_overrides",
    "resolve_benchmark_run_settings",
    "resolve_benchmark_threshold_settings",
    "run_benchmark_and_write_outputs",
]
