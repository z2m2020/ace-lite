from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click

from ace_lite.cli_app.config_resolve import _resolve_from_config
from ace_lite.cli_app.params import _to_bool, _to_float, _to_int
from ace_lite.cli_app.runtime_command_support import (
    DEFAULT_RUNTIME_STATS_DB_PATH,
    load_runtime_stats_summary,
)
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
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
    runtime_stats_enabled: bool,
    runtime_stats_db_path: str,
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
        "runtime_stats_enabled": _resolve_from_config(
            ctx=ctx,
            param_name="runtime_stats_enabled",
            current=runtime_stats_enabled,
            config=config,
            paths=[
                ("benchmark", "runtime_stats", "enabled"),
                ("benchmark", "runtime_stats_enabled"),
            ],
            transform=_to_bool,
        ),
        "runtime_stats_db_path": _resolve_from_config(
            ctx=ctx,
            param_name="runtime_stats_db_path",
            current=runtime_stats_db_path,
            config=config,
            paths=[
                ("benchmark", "runtime_stats", "db_path"),
                ("benchmark", "runtime_stats_db_path"),
            ],
            transform=lambda value: str(value or "").strip()
            or DEFAULT_RUNTIME_STATS_DB_PATH,
        ),
    }


def build_threshold_overrides(settings: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in settings.items()
        if key != "benchmark_threshold_profile" and value is not None
    }


def build_benchmark_tuning_context_summary(
    *,
    resolved: dict[str, Any],
    threshold_profile: str,
    threshold_overrides: dict[str, float],
    warmup_runs: int,
    include_plan_payload: bool,
    include_case_details: bool,
) -> dict[str, Any]:
    return {
        "report_only": True,
        "runtime_profile": str(resolved.get("runtime_profile") or "").strip() or None,
        "threshold_profile": str(threshold_profile or "").strip() or "default",
        "threshold_overrides": {
            str(key): float(value)
            for key, value in dict(threshold_overrides or {}).items()
        },
        "run_settings": {
            "warmup_runs": max(0, int(warmup_runs)),
            "include_plan_payload": bool(include_plan_payload),
            "include_case_details": bool(include_case_details),
        },
        "retrieval": dict(resolved.get("retrieval", {}))
        if isinstance(resolved.get("retrieval"), dict)
        else {},
        "chunk": dict(resolved.get("chunk", {}))
        if isinstance(resolved.get("chunk"), dict)
        else {},
        "scip": dict(resolved.get("scip", {}))
        if isinstance(resolved.get("scip"), dict)
        else {},
        "embeddings": dict(resolved.get("embeddings", {}))
        if isinstance(resolved.get("embeddings"), dict)
        else {},
        "cochange": dict(resolved.get("cochange", {}))
        if isinstance(resolved.get("cochange"), dict)
        else {},
        "adaptive_router": dict(resolved.get("adaptive_router", {}))
        if isinstance(resolved.get("adaptive_router"), dict)
        else {},
    }


def _resolve_feedback_configured_path(
    *,
    root: str | Path | None,
    configured_path: str,
) -> str:
    candidate = Path(str(configured_path or "").strip() or "~/.ace-lite/profile.json").expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    if root is None:
        return str(candidate)
    return str((Path(root).expanduser() / candidate).resolve())


def _resolve_feedback_runtime_store(
    *,
    root: str | Path | None,
    orchestrator: Any,
) -> dict[str, Any]:
    config = getattr(orchestrator, "config", None)
    memory = getattr(config, "memory", None)
    feedback = getattr(memory, "feedback", None)
    enabled = bool(getattr(feedback, "enabled", False))
    configured_path = str(
        getattr(feedback, "path", "~/.ace-lite/profile.json") or "~/.ace-lite/profile.json"
    ).strip() or "~/.ace-lite/profile.json"
    resolved_configured_path = _resolve_feedback_configured_path(
        root=root,
        configured_path=configured_path,
    )
    max_entries = max(0, int(getattr(feedback, "max_entries", 512) or 512))
    store = None
    if enabled:
        store = SelectionFeedbackStore(
            profile_path=resolved_configured_path,
            max_entries=max_entries,
        )
    return {
        "enabled": enabled,
        "configured_path": configured_path,
        "resolved_configured_path": resolved_configured_path,
        "max_entries": max_entries,
        "store": store,
    }


def _empty_durable_preference_capture_summary(
    *,
    enabled: bool,
    configured_path: str,
    resolved_configured_path: str,
    repo: str,
    user_id: str | None = None,
    profile_key: str | None = None,
    preference_kind: str,
    signal_source: str,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "configured_path": configured_path,
        "resolved_configured_path": resolved_configured_path,
        "store_path": "",
        "user_id": str(user_id or "").strip(),
        "repo_key": str(repo or "").strip(),
        "profile_key": str(profile_key or "").strip(),
        "preference_kind": preference_kind,
        "signal_source": signal_source,
        "event_count": 0,
        "distinct_target_path_count": 0,
        "total_weight": 0.0,
        "latest_created_at": "",
        "by_kind": {},
        "by_signal_source": {},
    }


def _load_durable_preference_capture_snapshot(
    *,
    root: str | Path | None,
    orchestrator: Any,
    repo: str,
    user_id: str | None = None,
    profile_key: str | None = None,
    preference_kind: str = "selection_feedback",
    signal_source: str = "feedback_store",
) -> dict[str, Any]:
    runtime_store = _resolve_feedback_runtime_store(
        root=root,
        orchestrator=orchestrator,
    )
    if not runtime_store["enabled"] or runtime_store["store"] is None:
        return _empty_durable_preference_capture_summary(
            enabled=bool(runtime_store["enabled"]),
            configured_path=str(runtime_store["configured_path"]),
            resolved_configured_path=str(runtime_store["resolved_configured_path"]),
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind=preference_kind,
            signal_source=signal_source,
        )

    store = runtime_store["store"]
    durable_store = DurablePreferenceCaptureStore(db_path=store.path)
    summary = durable_store.summarize(
        user_id=user_id,
        repo_key=str(repo or "").strip(),
        profile_key=profile_key,
        preference_kind=preference_kind,
        signal_source=signal_source,
    )
    payload = dict(summary)
    payload.update(
        {
            "enabled": True,
            "configured_path": str(runtime_store["configured_path"]),
            "resolved_configured_path": str(runtime_store["resolved_configured_path"]),
            "store_path": str(store.path),
            "user_id": str(user_id or "").strip(),
            "repo_key": str(repo or "").strip(),
            "profile_key": str(profile_key or "").strip(),
            "preference_kind": preference_kind,
            "signal_source": signal_source,
        }
    )
    return payload


def _record_benchmark_retrieval_preference_event(
    *,
    results: dict[str, Any],
    root: str | Path | None,
    orchestrator: Any,
    repo: str,
    session_id: str,
    user_id: str | None,
    profile_key: str | None,
) -> dict[str, Any]:
    runtime_store = _resolve_feedback_runtime_store(
        root=root,
        orchestrator=orchestrator,
    )
    if not runtime_store["enabled"] or runtime_store["store"] is None:
        return _empty_durable_preference_capture_summary(
            enabled=bool(runtime_store["enabled"]),
            configured_path=str(runtime_store["configured_path"]),
            resolved_configured_path=str(runtime_store["resolved_configured_path"]),
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind="retrieval_preference",
            signal_source="benchmark",
        )

    retrieval_summary = results.get("retrieval_context_observability_summary")
    if not isinstance(retrieval_summary, dict) or not retrieval_summary:
        return _load_durable_preference_capture_snapshot(
            root=root,
            orchestrator=orchestrator,
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind="retrieval_preference",
            signal_source="benchmark",
        )

    generated_at = str(results.get("generated_at") or "").strip()
    session_key = session_id or generated_at or "benchmark"
    durable_store = DurablePreferenceCaptureStore(
        db_path=runtime_store["store"].path,
    )
    durable_store.record(
        {
            "event_id": f"benchmark-retrieval-preference:{repo}:{session_key}",
            "user_id": str(user_id or "").strip(),
            "repo_key": str(repo or "").strip(),
            "profile_key": str(profile_key or "").strip(),
            "preference_kind": "retrieval_preference",
            "signal_source": "benchmark",
            "signal_key": f"benchmark.retrieval_context:{session_key}",
            "target_path": "_benchmark/retrieval_context_summary",
            "value_text": (
                "available_case_rate={available:.4f} coverage_ratio_mean={coverage:.4f}".format(
                    available=float(
                        retrieval_summary.get("available_case_rate", 0.0) or 0.0
                    ),
                    coverage=float(
                        retrieval_summary.get("coverage_ratio_mean", 0.0) or 0.0
                    ),
                )
            ),
            "weight": float(
                retrieval_summary.get("coverage_ratio_mean", 0.0) or 0.0
            ),
            "payload": {
                "generated_at": generated_at,
                "session_id": session_id,
                "summary": dict(retrieval_summary),
            },
            "created_at": generated_at,
        }
    )
    return _load_durable_preference_capture_snapshot(
        root=root,
        orchestrator=orchestrator,
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        preference_kind="retrieval_preference",
        signal_source="benchmark",
    )


def _record_benchmark_packing_preference_event(
    *,
    results: dict[str, Any],
    root: str | Path | None,
    orchestrator: Any,
    repo: str,
    session_id: str,
    user_id: str | None,
    profile_key: str | None,
) -> dict[str, Any]:
    runtime_store = _resolve_feedback_runtime_store(
        root=root,
        orchestrator=orchestrator,
    )
    if not runtime_store["enabled"] or runtime_store["store"] is None:
        return _empty_durable_preference_capture_summary(
            enabled=bool(runtime_store["enabled"]),
            configured_path=str(runtime_store["configured_path"]),
            resolved_configured_path=str(runtime_store["resolved_configured_path"]),
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind="packing_preference",
            signal_source="benchmark",
        )

    metrics = results.get("metrics")
    metrics = dict(metrics) if isinstance(metrics, dict) else {}
    if not metrics:
        return _load_durable_preference_capture_snapshot(
            root=root,
            orchestrator=orchestrator,
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind="packing_preference",
            signal_source="benchmark",
        )

    packing_summary = {
        "graph_closure_preference_enabled_ratio": float(
            metrics.get("source_plan_graph_closure_preference_enabled_ratio", 0.0)
            or 0.0
        ),
        "graph_closure_preferred_count_mean": float(
            metrics.get("source_plan_graph_closure_preferred_count_mean", 0.0)
            or 0.0
        ),
        "focused_file_promoted_count_mean": float(
            metrics.get("source_plan_focused_file_promoted_count_mean", 0.0) or 0.0
        ),
        "packed_path_count_mean": float(
            metrics.get("source_plan_packed_path_count_mean", 0.0) or 0.0
        ),
    }
    generated_at = str(results.get("generated_at") or "").strip()
    session_key = session_id or generated_at or "benchmark"
    durable_store = DurablePreferenceCaptureStore(
        db_path=runtime_store["store"].path,
    )
    durable_store.record(
        {
            "event_id": f"benchmark-packing-preference:{repo}:{session_key}",
            "user_id": str(user_id or "").strip(),
            "repo_key": str(repo or "").strip(),
            "profile_key": str(profile_key or "").strip(),
            "preference_kind": "packing_preference",
            "signal_source": "benchmark",
            "signal_key": f"benchmark.source_plan_packing:{session_key}",
            "target_path": "_benchmark/source_plan_packing_summary",
            "value_text": (
                "enabled_ratio={enabled:.4f} packed_path_count_mean={packed:.4f}".format(
                    enabled=float(
                        packing_summary["graph_closure_preference_enabled_ratio"]
                    ),
                    packed=float(packing_summary["packed_path_count_mean"]),
                )
            ),
            "weight": float(
                packing_summary["graph_closure_preference_enabled_ratio"]
            ),
            "payload": {
                "generated_at": generated_at,
                "session_id": session_id,
                "summary": packing_summary,
            },
            "created_at": generated_at,
        }
    )
    return _load_durable_preference_capture_snapshot(
        root=root,
        orchestrator=orchestrator,
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        preference_kind="packing_preference",
        signal_source="benchmark",
    )


def _record_benchmark_validation_preference_event(
    *,
    results: dict[str, Any],
    root: str | Path | None,
    orchestrator: Any,
    repo: str,
    session_id: str,
    user_id: str | None,
    profile_key: str | None,
) -> dict[str, Any]:
    runtime_store = _resolve_feedback_runtime_store(
        root=root,
        orchestrator=orchestrator,
    )
    if not runtime_store["enabled"] or runtime_store["store"] is None:
        return _empty_durable_preference_capture_summary(
            enabled=bool(runtime_store["enabled"]),
            configured_path=str(runtime_store["configured_path"]),
            resolved_configured_path=str(runtime_store["resolved_configured_path"]),
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind="validation_preference",
            signal_source="benchmark",
        )

    metrics = results.get("metrics")
    metrics = dict(metrics) if isinstance(metrics, dict) else {}
    evidence_summary = results.get("evidence_insufficiency_summary")
    evidence_summary = (
        dict(evidence_summary) if isinstance(evidence_summary, dict) else {}
    )
    task_success_summary = results.get("task_success_summary")
    task_success_summary = (
        dict(task_success_summary) if isinstance(task_success_summary, dict) else {}
    )
    if not metrics and not evidence_summary and not task_success_summary:
        return _load_durable_preference_capture_snapshot(
            root=root,
            orchestrator=orchestrator,
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            preference_kind="validation_preference",
            signal_source="benchmark",
        )

    validation_summary = {
        "missing_validation_rate": float(
            metrics.get("missing_validation_rate", 0.0) or 0.0
        ),
        "validation_test_count_mean": float(
            metrics.get("validation_test_count", 0.0) or 0.0
        ),
        "evidence_insufficient_rate": float(
            metrics.get("evidence_insufficient_rate", 0.0) or 0.0
        ),
        "evidence_summary": evidence_summary,
        "task_success_summary": task_success_summary,
    }
    missing_validation_rate_value = validation_summary.get(
        "missing_validation_rate", 0.0
    )
    evidence_insufficient_rate_value = validation_summary.get(
        "evidence_insufficient_rate", 0.0
    )
    missing_validation_rate = (
        float(missing_validation_rate_value)
        if isinstance(missing_validation_rate_value, (int, float, str))
        else 0.0
    )
    evidence_insufficient_rate = (
        float(evidence_insufficient_rate_value)
        if isinstance(evidence_insufficient_rate_value, (int, float, str))
        else 0.0
    )
    generated_at = str(results.get("generated_at") or "").strip()
    session_key = session_id or generated_at or "benchmark"
    durable_store = DurablePreferenceCaptureStore(
        db_path=runtime_store["store"].path,
    )
    durable_store.record(
        {
            "event_id": f"benchmark-validation-preference:{repo}:{session_key}",
            "user_id": str(user_id or "").strip(),
            "repo_key": str(repo or "").strip(),
            "profile_key": str(profile_key or "").strip(),
            "preference_kind": "validation_preference",
            "signal_source": "benchmark",
            "signal_key": f"benchmark.validation:{session_key}",
            "target_path": "_benchmark/validation_summary",
            "value_text": (
                f"missing_validation_rate={missing_validation_rate:.4f} evidence_insufficient_rate={evidence_insufficient_rate:.4f}"
            ),
            "weight": missing_validation_rate,
            "payload": {
                "generated_at": generated_at,
                "session_id": session_id,
                "summary": validation_summary,
            },
            "created_at": generated_at,
        }
    )
    return _load_durable_preference_capture_snapshot(
        root=root,
        orchestrator=orchestrator,
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        preference_kind="validation_preference",
        signal_source="benchmark",
    )


def attach_benchmark_runtime_stats_summary(
    *,
    results: dict[str, Any],
    orchestrator: Any,
    repo: str,
    root: str | Path | None,
    runtime_stats_enabled: bool,
    runtime_stats_db_path: str,
    home_path: str | None,
    user_id: str | None = None,
    profile_key: str | None = None,
) -> dict[str, Any]:
    if not runtime_stats_enabled:
        return results
    session_id = str(
        getattr(orchestrator, "_durable_stats_session_id", "") or ""
    ).strip()
    payload = load_runtime_stats_summary(
        db_path=runtime_stats_db_path,
        session_id=session_id or None,
        repo_key=repo,
        home_path=home_path,
    )
    preference_snapshot: dict[str, Any] = {}
    preference_summary = results.get("preference_observability_summary")
    if isinstance(preference_summary, dict) and preference_summary:
        preference_snapshot["preference_observability_summary"] = dict(
            preference_summary
        )
    feedback_summary = results.get("feedback_observability_summary")
    if isinstance(feedback_summary, dict) and feedback_summary:
        preference_snapshot["feedback_observability_summary"] = dict(feedback_summary)
    durable_preference_capture_summary = _load_durable_preference_capture_snapshot(
        root=root,
        orchestrator=orchestrator,
        repo=repo,
    )
    if durable_preference_capture_summary:
        preference_snapshot["durable_preference_capture_summary"] = (
            durable_preference_capture_summary
        )
    if str(user_id or "").strip() or str(profile_key or "").strip():
        durable_preference_capture_scoped_summary = (
            _load_durable_preference_capture_snapshot(
                root=root,
                orchestrator=orchestrator,
                repo=repo,
                user_id=user_id,
                profile_key=profile_key,
            )
        )
        if durable_preference_capture_scoped_summary:
            preference_snapshot["durable_preference_capture_scoped_summary"] = (
                durable_preference_capture_scoped_summary
            )
    durable_retrieval_preference_summary = (
        _record_benchmark_retrieval_preference_event(
            results=results,
            root=root,
            orchestrator=orchestrator,
            repo=repo,
            session_id=session_id,
            user_id=user_id,
            profile_key=profile_key,
        )
    )
    if durable_retrieval_preference_summary:
        preference_snapshot["durable_retrieval_preference_summary"] = (
            durable_retrieval_preference_summary
        )
    durable_packing_preference_summary = _record_benchmark_packing_preference_event(
        results=results,
        root=root,
        orchestrator=orchestrator,
        repo=repo,
        session_id=session_id,
        user_id=user_id,
        profile_key=profile_key,
    )
    if durable_packing_preference_summary:
        preference_snapshot["durable_packing_preference_summary"] = (
            durable_packing_preference_summary
        )
    durable_validation_preference_summary = (
        _record_benchmark_validation_preference_event(
            results=results,
            root=root,
            orchestrator=orchestrator,
            repo=repo,
            session_id=session_id,
            user_id=user_id,
            profile_key=profile_key,
        )
    )
    if durable_validation_preference_summary:
        preference_snapshot["durable_validation_preference_summary"] = (
            durable_validation_preference_summary
        )
    if preference_snapshot:
        payload = dict(payload)
        payload["preference_snapshot"] = preference_snapshot
    updated = dict(results)
    updated["runtime_stats_summary"] = payload
    return updated


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
    runtime_stats_enabled: bool,
    runtime_stats_db_path: str,
    home_path: str | None,
    user_id: str | None,
    profile_key: str | None,
    output_dir: str,
    runner_cls: Any,
    reward_log_writer_cls: Any,
    write_results_fn: Any,
    echo_json_fn: Any,
    merge_reward_log_summary_fn: Any,
    attach_runtime_stats_summary_fn: Any,
    tuning_context_summary: dict[str, Any] | None = None,
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
    if isinstance(tuning_context_summary, dict) and tuning_context_summary:
        results = dict(results)
        results["tuning_context_summary"] = dict(tuning_context_summary)
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
    results = attach_runtime_stats_summary_fn(
        results=results,
        orchestrator=orchestrator,
        repo=repo,
        root=root,
        runtime_stats_enabled=bool(runtime_stats_enabled),
        runtime_stats_db_path=str(runtime_stats_db_path),
        home_path=home_path,
        user_id=user_id,
        profile_key=profile_key,
    )
    outputs = write_results_fn(results, output_dir=output_dir)
    echo_json_fn(outputs)
    return cast(dict[str, Any], results)


__all__ = [
    "attach_benchmark_runtime_stats_summary",
    "build_benchmark_tuning_context_summary",
    "build_threshold_overrides",
    "resolve_benchmark_run_settings",
    "resolve_benchmark_threshold_settings",
    "run_benchmark_and_write_outputs",
]
