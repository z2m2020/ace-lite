from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from ace_lite.release_freeze import (
    StepResult,
    load_yaml_config as _load_yaml_config,
    run_step as _run_step,
)

_DECISION_OBSERVABILITY_SCALAR_KEYS = (
    "case_count",
    "case_with_decisions_count",
    "case_with_decisions_rate",
    "decision_event_count",
)
_DECISION_OBSERVABILITY_MAPPING_KEYS = (
    "actions",
    "targets",
    "reasons",
    "outcomes",
)


def _load_matrix_summary(*, summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists() or not summary_path.is_file():
        return {}

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    repos_raw = payload.get("repos")
    repos = repos_raw if isinstance(repos_raw, list) else []

    threshold_failed_repos: list[dict[str, Any]] = []
    regressed_repos: list[dict[str, Any]] = []
    task_success_repos: list[dict[str, Any]] = []
    memory_metrics_repos: list[dict[str, Any]] = []
    embedding_metrics_repos: list[dict[str, Any]] = []
    latency_metrics_repos: list[dict[str, Any]] = []
    retrieval_metrics_repos: list[dict[str, Any]] = []

    for item in repos:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip() or "(unknown)"

        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        task_success_value = metrics.get("task_success_rate", metrics.get("utility_rate", 0.0))
        try:
            task_success_rate = max(0.0, float(task_success_value or 0.0))
        except Exception:
            task_success_rate = 0.0
        task_success_repos.append({"name": name, "task_success_rate": task_success_rate})
        latency_metrics_repos.append(
            {
                "name": name,
                "latency_p95_ms": max(0.0, float(metrics.get("latency_p95_ms", 0.0) or 0.0)),
                "repomap_latency_p95_ms": max(
                    0.0, float(metrics.get("repomap_latency_p95_ms", 0.0) or 0.0)
                ),
            }
        )
        retrieval_metrics_repos.append(
            {
                "name": name,
                "precision_at_k": max(
                    0.0, float(metrics.get("precision_at_k", 0.0) or 0.0)
                ),
                "noise_rate": max(0.0, float(metrics.get("noise_rate", 0.0) or 0.0)),
                "latency_p95_ms": max(
                    0.0, float(metrics.get("latency_p95_ms", 0.0) or 0.0)
                ),
                "chunk_hit_at_k": max(
                    0.0, float(metrics.get("chunk_hit_at_k", 0.0) or 0.0)
                ),
            }
        )
        memory_metrics_repos.append(
            {
                "name": name,
                "notes_hit_ratio": max(
                    0.0, float(metrics.get("notes_hit_ratio", 0.0) or 0.0)
                ),
                "profile_selected_mean": max(
                    0.0, float(metrics.get("profile_selected_mean", 0.0) or 0.0)
                ),
                "capture_trigger_ratio": max(
                    0.0, float(metrics.get("capture_trigger_ratio", 0.0) or 0.0)
                ),
            }
        )
        embedding_metrics_repos.append(
            {
                "name": name,
                "embedding_similarity_mean": float(
                    metrics.get("embedding_similarity_mean", 0.0) or 0.0
                ),
                "embedding_rerank_ratio": max(
                    0.0, float(metrics.get("embedding_rerank_ratio", 0.0) or 0.0)
                ),
                "embedding_cache_hit_ratio": max(
                    0.0, float(metrics.get("embedding_cache_hit_ratio", 0.0) or 0.0)
                ),
                "embedding_fallback_ratio": max(
                    0.0, float(metrics.get("embedding_fallback_ratio", 0.0) or 0.0)
                ),
                "embedding_enabled_ratio": max(
                    0.0, float(metrics.get("embedding_enabled_ratio", 0.0) or 0.0)
                ),
            }
        )

        threshold_failures_raw = item.get("failed_checks")
        threshold_failures = (
            threshold_failures_raw if isinstance(threshold_failures_raw, list) else []
        )
        if threshold_failures:
            threshold_failed_repos.append(
                {
                    "name": name,
                    "failure_count": len(threshold_failures),
                }
            )

        regressed = bool(item.get("benchmark_regressed", False))
        bench_failed_raw = item.get("benchmark_failed_checks")
        bench_failed = (
            [str(value).strip() for value in bench_failed_raw if str(value).strip()]
            if isinstance(bench_failed_raw, list)
            else []
        )
        if regressed or bench_failed:
            regressed_repos.append(
                {
                    "name": name,
                    "regressed": regressed,
                    "failed_checks": bench_failed,
                }
            )

    retrieval_policy_summary_raw = payload.get("retrieval_policy_summary")
    retrieval_policy_summary_source = (
        retrieval_policy_summary_raw
        if isinstance(retrieval_policy_summary_raw, list)
        else []
    )
    retrieval_policy_summary: list[dict[str, Any]] = []
    for item in retrieval_policy_summary_source:
        if not isinstance(item, dict):
            continue

        policy = str(item.get("retrieval_policy") or "auto").strip().lower() or "auto"
        repo_count = max(0, int(item.get("repo_count", 0) or 0))
        regressed_repo_count = max(0, int(item.get("regressed_repo_count", 0) or 0))
        retrieval_policy_summary.append(
            {
                "retrieval_policy": policy,
                "repo_count": repo_count,
                "regressed_repo_count": regressed_repo_count,
                "regressed_repo_rate": max(
                    0.0,
                    float(
                        item.get(
                            "regressed_repo_rate",
                            (float(regressed_repo_count) / float(repo_count))
                            if repo_count > 0
                            else 0.0,
                        )
                        or 0.0
                    ),
                ),
                "task_success_mean": max(
                    0.0, float(item.get("task_success_mean", 0.0) or 0.0)
                ),
                "positive_task_success_mean": max(
                    0.0,
                    float(item.get("positive_task_success_mean", 0.0) or 0.0),
                ),
                "retrieval_task_gap_rate_mean": max(
                    0.0,
                    float(item.get("retrieval_task_gap_rate_mean", 0.0) or 0.0),
                ),
                "precision_at_k_mean": max(
                    0.0, float(item.get("precision_at_k_mean", 0.0) or 0.0)
                ),
                "noise_rate_mean": max(
                    0.0, float(item.get("noise_rate_mean", 0.0) or 0.0)
                ),
                "latency_p95_ms_mean": max(
                    0.0, float(item.get("latency_p95_ms_mean", 0.0) or 0.0)
                ),
                "repomap_latency_p95_ms_mean": max(
                    0.0,
                    float(item.get("repomap_latency_p95_ms_mean", 0.0) or 0.0),
                ),
                "slo_downgrade_case_rate_mean": max(
                    0.0,
                    float(item.get("slo_downgrade_case_rate_mean", 0.0) or 0.0),
                ),
            }
        )

    plugin_policy_raw = payload.get("plugin_policy_summary")
    plugin_policy_source = plugin_policy_raw if isinstance(plugin_policy_raw, dict) else {}

    plugin_totals_raw = plugin_policy_source.get("totals")
    plugin_totals_source = plugin_totals_raw if isinstance(plugin_totals_raw, dict) else {}
    plugin_totals = {
        key: max(0, int(plugin_totals_source.get(key, 0) or 0))
        for key in ("applied", "conflicts", "blocked", "warn", "remote_applied")
    }

    mode_distribution_raw = plugin_policy_source.get("mode_distribution")
    mode_distribution_source = (
        mode_distribution_raw if isinstance(mode_distribution_raw, dict) else {}
    )
    mode_distribution: dict[str, int] = {}
    for key, value in mode_distribution_source.items():
        mode = str(key).strip().lower()
        if not mode:
            continue
        mode_distribution[mode] = max(0, int(value or 0))

    plugin_repos_raw = plugin_policy_source.get("repos")
    plugin_repos_source = plugin_repos_raw if isinstance(plugin_repos_raw, list) else []
    plugin_repos: list[dict[str, Any]] = []
    for item in plugin_repos_source:
        if not isinstance(item, dict):
            continue
        plugin_repos.append(
            {
                "name": str(item.get("name") or "").strip() or "(unknown)",
                "mode": str(item.get("mode") or "").strip().lower() or "(none)",
                "applied": max(0, int(item.get("applied", 0) or 0)),
                "conflicts": max(0, int(item.get("conflicts", 0) or 0)),
                "blocked": max(0, int(item.get("blocked", 0) or 0)),
                "warn": max(0, int(item.get("warn", 0) or 0)),
                "remote_applied": max(0, int(item.get("remote_applied", 0) or 0)),
            }
        )

    stage_latency_summary_raw = payload.get("stage_latency_summary")
    stage_latency_summary = (
        stage_latency_summary_raw if isinstance(stage_latency_summary_raw, dict) else {}
    )
    slo_budget_summary_raw = payload.get("slo_budget_summary")
    slo_budget_summary = (
        slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
    )
    decision_observability_summary_raw = payload.get("decision_observability_summary")
    decision_observability_summary = (
        decision_observability_summary_raw
        if isinstance(decision_observability_summary_raw, dict)
        else {}
    )

    return {
        "path": str(summary_path),
        "passed": bool(payload.get("passed", False)),
        "benchmark_regression_detected": bool(
            payload.get("benchmark_regression_detected", False)
        ),
        "repo_count": int(payload.get("repo_count", len(repos)) or 0),
        "threshold_failed_repos": threshold_failed_repos,
        "regressed_repos": regressed_repos,
        "task_success_repos": task_success_repos,
        "task_success_mean": (
            sum(item.get("task_success_rate", 0.0) for item in task_success_repos)
            / max(1, len(task_success_repos))
        ),
        "latency_metrics_repos": latency_metrics_repos,
        "latency_metrics_mean": {
            "latency_p95_ms": (
                sum(item.get("latency_p95_ms", 0.0) for item in latency_metrics_repos)
                / max(1, len(latency_metrics_repos))
            ),
            "repomap_latency_p95_ms": (
                sum(
                    item.get("repomap_latency_p95_ms", 0.0)
                    for item in latency_metrics_repos
                )
                / max(1, len(latency_metrics_repos))
            ),
        },
        "retrieval_metrics_repos": retrieval_metrics_repos,
        "retrieval_metrics_mean": {
            "precision_at_k": (
                sum(item.get("precision_at_k", 0.0) for item in retrieval_metrics_repos)
                / max(1, len(retrieval_metrics_repos))
            ),
            "noise_rate": (
                sum(item.get("noise_rate", 0.0) for item in retrieval_metrics_repos)
                / max(1, len(retrieval_metrics_repos))
            ),
            "latency_p95_ms": (
                sum(item.get("latency_p95_ms", 0.0) for item in retrieval_metrics_repos)
                / max(1, len(retrieval_metrics_repos))
            ),
            "chunk_hit_at_k": (
                sum(item.get("chunk_hit_at_k", 0.0) for item in retrieval_metrics_repos)
                / max(1, len(retrieval_metrics_repos))
            ),
        },
        "memory_metrics_repos": memory_metrics_repos,
        "memory_metrics_mean": {
            "notes_hit_ratio": (
                sum(item.get("notes_hit_ratio", 0.0) for item in memory_metrics_repos)
                / max(1, len(memory_metrics_repos))
            ),
            "profile_selected_mean": (
                sum(
                    item.get("profile_selected_mean", 0.0)
                    for item in memory_metrics_repos
                )
                / max(1, len(memory_metrics_repos))
            ),
            "capture_trigger_ratio": (
                sum(
                    item.get("capture_trigger_ratio", 0.0)
                    for item in memory_metrics_repos
                )
                / max(1, len(memory_metrics_repos))
            ),
        },
        "embedding_metrics_repos": embedding_metrics_repos,
        "embedding_metrics_mean": {
            "embedding_similarity_mean": (
                sum(
                    item.get("embedding_similarity_mean", 0.0)
                    for item in embedding_metrics_repos
                )
                / max(1, len(embedding_metrics_repos))
            ),
            "embedding_rerank_ratio": (
                sum(
                    item.get("embedding_rerank_ratio", 0.0)
                    for item in embedding_metrics_repos
                )
                / max(1, len(embedding_metrics_repos))
            ),
            "embedding_cache_hit_ratio": (
                sum(
                    item.get("embedding_cache_hit_ratio", 0.0)
                    for item in embedding_metrics_repos
                )
                / max(1, len(embedding_metrics_repos))
            ),
            "embedding_fallback_ratio": (
                sum(
                    item.get("embedding_fallback_ratio", 0.0)
                    for item in embedding_metrics_repos
                )
                / max(1, len(embedding_metrics_repos))
            ),
            "embedding_enabled_ratio": (
                sum(
                    item.get("embedding_enabled_ratio", 0.0)
                    for item in embedding_metrics_repos
                )
                / max(1, len(embedding_metrics_repos))
            ),
        },
        "retrieval_policy_summary": retrieval_policy_summary,
        "plugin_policy_summary": {
            "totals": plugin_totals,
            "mode_distribution": {
                key: mode_distribution[key] for key in sorted(mode_distribution)
            },
            "repos": plugin_repos,
        },
        "decision_observability_summary": decision_observability_summary,
        "stage_latency_summary": stage_latency_summary,
        "slo_budget_summary": slo_budget_summary,
    }


def _load_e2e_success_summary(*, summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists() or not summary_path.is_file():
        return {}

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    return {
        "path": str(summary_path),
        "passed": bool(payload.get("passed", False)),
        "case_count": max(0, int(payload.get("case_count", 0) or 0)),
        "passed_count": max(0, int(payload.get("passed_count", 0) or 0)),
        "failed_count": max(0, int(payload.get("failed_count", 0) or 0)),
        "task_success_rate": max(0.0, float(payload.get("task_success_rate", 0.0) or 0.0)),
        "failed_cases": payload.get("failed_cases") if isinstance(payload.get("failed_cases"), list) else [],
    }


def _coerce_gate_threshold(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        return -1
    return parsed if parsed >= 0 else -1


def _gate_threshold_from_mapping(mapping: dict[str, Any], key: str) -> int:
    if key not in mapping:
        return -1
    return _coerce_gate_threshold(mapping.get(key))


def _resolve_plugin_gate_config(
    *,
    matrix_config_path: Path,
    profile: str,
    cli_max_conflicts: int,
    cli_max_blocked: int,
    cli_max_warn: int,
) -> dict[str, Any]:
    selected_profile = str(profile or "").strip().lower()
    config: dict[str, Any] = {}

    if matrix_config_path.exists() and matrix_config_path.is_file():
        try:
            loaded = yaml.safe_load(matrix_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            config = loaded

    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}

    profiles_raw = freeze.get("plugin_policy_gate_profiles", config.get("plugin_policy_gate_profiles"))
    profiles = profiles_raw if isinstance(profiles_raw, dict) else {}

    if not selected_profile:
        default_profile = str(
            freeze.get("plugin_policy_gate_default_profile", "")
            or config.get("plugin_policy_gate_default_profile", "")
        ).strip().lower()
        selected_profile = default_profile

    selected_profile_payload_raw = profiles.get(selected_profile)
    selected_profile_payload = (
        selected_profile_payload_raw
        if isinstance(selected_profile_payload_raw, dict)
        else {}
    )

    resolved = {
        "max_conflicts": _coerce_gate_threshold(cli_max_conflicts),
        "max_blocked": _coerce_gate_threshold(cli_max_blocked),
        "max_warn": _coerce_gate_threshold(cli_max_warn),
    }

    used_cli = False
    used_profile = False

    for key in ("max_conflicts", "max_blocked", "max_warn"):
        if resolved[key] >= 0:
            used_cli = True
            continue
        resolved_value = _coerce_gate_threshold(selected_profile_payload.get(key, -1))
        if resolved_value >= 0:
            used_profile = True
        resolved[key] = resolved_value

    source = "disabled"
    if used_cli and used_profile:
        source = "mixed"
    elif used_cli:
        source = "cli"
    elif used_profile:
        source = "profile"

    return {
        "profile": selected_profile if selected_profile_payload else "",
        "profile_from_config": bool(selected_profile_payload),
        "source": source,
        "thresholds": resolved,
    }


def _coerce_success_floor(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        return -1.0
    return parsed if parsed >= 0.0 else -1.0


def _resolve_e2e_success_gate(
    *,
    matrix_config_path: Path,
    cli_success_floor: float,
) -> dict[str, Any]:
    resolved_floor = _coerce_success_floor(cli_success_floor)
    if resolved_floor >= 0.0:
        return {
            "enabled": True,
            "source": "cli",
            "min_success_rate": resolved_floor,
        }

    config: dict[str, Any] = {}
    if matrix_config_path.exists() and matrix_config_path.is_file():
        try:
            loaded = yaml.safe_load(matrix_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            config = loaded

    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    configured_floor = _coerce_success_floor(
        freeze.get("e2e_success_floor", config.get("e2e_success_floor", -1.0))
    )

    if configured_floor < 0.0:
        return {
            "enabled": False,
            "source": "disabled",
            "min_success_rate": -1.0,
        }

    return {
        "enabled": True,
        "source": "config",
        "min_success_rate": configured_floor,
    }


def _coerce_metric_floor(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        return -1.0
    return parsed if parsed >= 0.0 else -1.0


def _metric_threshold_from_mapping(mapping: dict[str, Any], key: str) -> float:
    raw = mapping.get(key, -1.0)
    try:
        return float(raw)
    except Exception:
        return -1.0


def _resolve_memory_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if matrix_config_path.exists() and matrix_config_path.is_file():
        try:
            loaded = yaml.safe_load(matrix_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            config = loaded

    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    memory_gate_raw = freeze.get("memory_gate", config.get("memory_gate", {}))
    memory_gate = memory_gate_raw if isinstance(memory_gate_raw, dict) else {}

    thresholds = {
        "min_notes_hit_ratio": _coerce_metric_floor(
            memory_gate.get("min_notes_hit_ratio", -1.0)
        ),
        "min_profile_selected_mean": _coerce_metric_floor(
            memory_gate.get("min_profile_selected_mean", -1.0)
        ),
        "min_capture_trigger_ratio": _coerce_metric_floor(
            memory_gate.get("min_capture_trigger_ratio", -1.0)
        ),
    }
    enabled = any(float(value) >= 0.0 for value in thresholds.values())
    return {
        "enabled": enabled,
        "source": "config" if enabled else "disabled",
        "thresholds": thresholds,
    }


def _evaluate_memory_gate(
    *,
    matrix_summary: dict[str, Any],
    min_notes_hit_ratio: float,
    min_profile_selected_mean: float,
    min_capture_trigger_ratio: float,
) -> list[dict[str, Any]]:
    checks = (
        ("notes_hit_ratio", min_notes_hit_ratio),
        ("profile_selected_mean", min_profile_selected_mean),
        ("capture_trigger_ratio", min_capture_trigger_ratio),
    )
    enabled_checks = [
        (metric, floor)
        for metric, floor in checks
        if isinstance(floor, (int, float)) and float(floor) >= 0.0
    ]
    if not enabled_checks:
        return []

    repos_raw = matrix_summary.get("memory_metrics_repos")
    repos = repos_raw if isinstance(repos_raw, list) else []
    failures: list[dict[str, Any]] = []

    for item in repos:
        if not isinstance(item, dict):
            continue
        repo = str(item.get("name") or "").strip() or "(unknown)"
        for metric, floor in enabled_checks:
            actual = max(0.0, float(item.get(metric, 0.0) or 0.0))
            if actual < float(floor):
                failures.append(
                    {
                        "repo": repo,
                        "metric": metric,
                        "actual": actual,
                        "operator": ">=",
                        "expected": float(floor),
                    }
                )
    return failures


def _resolve_embedding_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if matrix_config_path.exists() and matrix_config_path.is_file():
        try:
            loaded = yaml.safe_load(matrix_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            config = loaded

    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    embedding_gate_raw = freeze.get("embedding_gate", config.get("embedding_gate", {}))
    embedding_gate = embedding_gate_raw if isinstance(embedding_gate_raw, dict) else {}

    thresholds = {
        "min_embedding_enabled_ratio": _coerce_metric_floor(
            embedding_gate.get("min_embedding_enabled_ratio", -1.0)
        ),
        "min_embedding_similarity_mean": _coerce_metric_floor(
            embedding_gate.get("min_embedding_similarity_mean", -1.0)
        ),
        "min_embedding_rerank_ratio": _coerce_metric_floor(
            embedding_gate.get("min_embedding_rerank_ratio", -1.0)
        ),
        "min_embedding_cache_hit_ratio": _coerce_metric_floor(
            embedding_gate.get("min_embedding_cache_hit_ratio", -1.0)
        ),
        "max_embedding_fallback_ratio": _coerce_metric_floor(
            embedding_gate.get("max_embedding_fallback_ratio", -1.0)
        ),
    }
    enabled = any(float(value) >= 0.0 for value in thresholds.values())
    return {
        "enabled": enabled,
        "source": "config" if enabled else "disabled",
        "thresholds": thresholds,
    }


def _resolve_policy_guard_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if matrix_config_path.exists() and matrix_config_path.is_file():
        try:
            loaded = yaml.safe_load(matrix_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            config = loaded

    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    policy_guard_raw = freeze.get("policy_guard", config.get("policy_guard", {}))
    policy_guard = policy_guard_raw if isinstance(policy_guard_raw, dict) else {}

    thresholds = {
        "max_regressed_repo_rate": _coerce_metric_floor(
            policy_guard.get("max_regressed_repo_rate", -1.0)
        ),
        "min_task_success_mean": _coerce_metric_floor(
            policy_guard.get("min_task_success_mean", -1.0)
        ),
        "max_retrieval_task_gap_rate_mean": _coerce_metric_floor(
            policy_guard.get("max_retrieval_task_gap_rate_mean", -1.0)
        ),
        "max_noise_rate_mean": _coerce_metric_floor(
            policy_guard.get("max_noise_rate_mean", -1.0)
        ),
        "max_latency_p95_ms_mean": _coerce_metric_floor(
            policy_guard.get("max_latency_p95_ms_mean", -1.0)
        ),
        "max_slo_downgrade_case_rate_mean": _coerce_metric_floor(
            policy_guard.get("max_slo_downgrade_case_rate_mean", -1.0)
        ),
    }
    configured_mode_raw = str(policy_guard.get("mode") or "").strip().lower()
    configured_mode = configured_mode_raw.replace("-", "_")
    if configured_mode not in {"disabled", "report_only", "enforced"}:
        configured_mode = ""

    configured_enabled = policy_guard.get("enabled")
    thresholds_enabled = any(float(value) >= 0.0 for value in thresholds.values())
    if configured_mode:
        mode = configured_mode
        enabled = mode != "disabled"
        report_only = mode == "report_only"
        enforced = mode == "enforced"
        source = "config_mode"
    else:
        enabled = (
            bool(configured_enabled)
            if isinstance(configured_enabled, bool)
            else thresholds_enabled
        )
        report_only = False
        enforced = enabled
        mode = "enforced" if enabled else "disabled"
        source = "config" if enabled else "disabled"
        if isinstance(configured_enabled, bool):
            source = "config_flag"
    return {
        "enabled": enabled,
        "mode": mode,
        "report_only": report_only,
        "enforced": enforced,
        "source": source,
        "thresholds": thresholds,
    }


def _resolve_runtime_gate_config(
    *,
    matrix_config_path: Path,
    cli_enabled: bool | None,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if matrix_config_path.exists() and matrix_config_path.is_file():
        try:
            loaded = yaml.safe_load(matrix_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            config = loaded

    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    runtime_gate_raw = freeze.get("runtime_gate", {})
    runtime_gate = runtime_gate_raw if isinstance(runtime_gate_raw, dict) else {}

    configured_enabled = runtime_gate.get("enabled")
    enabled_from_config = (
        bool(configured_enabled)
        if isinstance(configured_enabled, bool)
        else True
    )

    if cli_enabled is None:
        return {
            "enabled": enabled_from_config,
            "source": "config"
            if isinstance(configured_enabled, bool)
            else "default",
        }

    return {
        "enabled": bool(cli_enabled),
        "source": "cli",
    }


def _coerce_threshold_mapping(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    thresholds: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        try:
            thresholds[name] = float(value)
        except Exception:
            continue
    return thresholds


def _evaluate_metric_thresholds(
    *,
    metrics: dict[str, Any],
    thresholds: dict[str, float],
    repo_name: str,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for key, expected in thresholds.items():
        if key.endswith("_min"):
            metric = key[:-4]
            actual = float(metrics.get(metric, 0.0) or 0.0)
            if actual < float(expected):
                failures.append(
                    {
                        "repo": repo_name,
                        "metric": metric,
                        "actual": actual,
                        "operator": ">=",
                        "expected": float(expected),
                    }
                )
            continue

        if key.endswith("_max"):
            metric = key[:-4]
            actual = float(metrics.get(metric, 0.0) or 0.0)
            if actual > float(expected):
                failures.append(
                    {
                        "repo": repo_name,
                        "metric": metric,
                        "actual": actual,
                        "operator": "<=",
                        "expected": float(expected),
                    }
                )
    return failures


def _resolve_tabiv3_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config = _load_yaml_config(path=matrix_config_path)
    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    gate_raw = freeze.get("tabiv3_gate", config.get("tabiv3_gate", {}))
    gate = gate_raw if isinstance(gate_raw, dict) else {}

    enabled = bool(gate.get("enabled", False))
    matrix_config = str(
        gate.get("matrix_config", "benchmark/matrix/tabiv3.yaml")
    ).strip() or "benchmark/matrix/tabiv3.yaml"
    thresholds = {
        "latency_p95_ms_max": max(
            0.0, float(gate.get("latency_p95_ms_max", 170.0) or 170.0)
        ),
        "repomap_latency_p95_ms_max": max(
            0.0,
            float(gate.get("repomap_latency_p95_ms_max", 110.0) or 110.0),
        ),
    }
    retry_count = max(0, int(gate.get("retry_count", 0) or 0))
    return {
        "enabled": enabled,
        "source": "config" if enabled else "disabled",
        "matrix_config": matrix_config,
        "thresholds": thresholds,
        "retry_count": retry_count,
    }


def _evaluate_tabiv3_gate(
    *,
    matrix_summary: dict[str, Any],
    latency_p95_ms_max: float,
    repomap_latency_p95_ms_max: float,
) -> list[dict[str, Any]]:
    rows_raw = matrix_summary.get("latency_metrics_repos")
    rows = rows_raw if isinstance(rows_raw, list) else []
    failures: list[dict[str, Any]] = []

    for item in rows:
        if not isinstance(item, dict):
            continue
        repo_name = str(item.get("name") or "").strip() or "(unknown)"
        failures.extend(
            _evaluate_metric_thresholds(
                metrics={
                    "latency_p95_ms": float(item.get("latency_p95_ms", 0.0) or 0.0),
                    "repomap_latency_p95_ms": float(
                        item.get("repomap_latency_p95_ms", 0.0) or 0.0
                    ),
                },
                thresholds={
                    "latency_p95_ms_max": float(latency_p95_ms_max),
                    "repomap_latency_p95_ms_max": float(repomap_latency_p95_ms_max),
                },
                repo_name=repo_name,
            )
        )

    return failures


def _load_benchmark_summary(*, summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists() or not summary_path.is_file():
        return {}

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    retrieval_control_plane_gate_summary_raw = payload.get(
        "retrieval_control_plane_gate_summary"
    )
    retrieval_control_plane_gate_summary = (
        retrieval_control_plane_gate_summary_raw
        if isinstance(retrieval_control_plane_gate_summary_raw, dict)
        else {}
    )
    retrieval_frontier_gate_summary_raw = payload.get(
        "retrieval_frontier_gate_summary"
    )
    retrieval_frontier_gate_summary = (
        retrieval_frontier_gate_summary_raw
        if isinstance(retrieval_frontier_gate_summary_raw, dict)
        else {}
    )
    deep_symbol_summary_raw = payload.get("deep_symbol_summary")
    deep_symbol_summary = (
        deep_symbol_summary_raw if isinstance(deep_symbol_summary_raw, dict) else {}
    )
    native_scip_summary_raw = payload.get("native_scip_summary")
    native_scip_summary = (
        native_scip_summary_raw if isinstance(native_scip_summary_raw, dict) else {}
    )
    validation_probe_summary_raw = payload.get("validation_probe_summary")
    validation_probe_summary = (
        validation_probe_summary_raw
        if isinstance(validation_probe_summary_raw, dict)
        else {}
    )
    source_plan_feedback_summary_raw = payload.get(
        "source_plan_validation_feedback_summary"
    )
    source_plan_feedback_summary = (
        source_plan_feedback_summary_raw
        if isinstance(source_plan_feedback_summary_raw, dict)
        else {}
    )
    source_plan_failure_signal_summary_raw = payload.get(
        "source_plan_failure_signal_summary"
    )
    source_plan_failure_signal_summary = (
        source_plan_failure_signal_summary_raw
        if isinstance(source_plan_failure_signal_summary_raw, dict)
        else {}
    )
    summary = {
        "path": str(summary_path),
        "repo": str(payload.get("repo", "") or ""),
        "case_count": max(0, int(payload.get("case_count", 0) or 0)),
        "regressed": bool(payload.get("regressed", False)),
        "failed_checks": (
            [str(item).strip() for item in payload.get("failed_checks", []) if str(item).strip()]
            if isinstance(payload.get("failed_checks"), list)
            else []
        ),
        "metrics": {
            key: float(value or 0.0)
            for key, value in metrics.items()
            if isinstance(key, str)
        },
    }
    gate_summary = {
            str(key): (
                bool(value)
                if isinstance(value, bool)
                else (
                    float(value)
                    if isinstance(value, (int, float))
                    else (
                        [str(item) for item in value if str(item).strip()]
                        if isinstance(value, list)
                        else value
                    )
                )
            )
            for key, value in retrieval_control_plane_gate_summary.items()
            if isinstance(key, str)
    }
    if gate_summary:
        summary["retrieval_control_plane_gate_summary"] = gate_summary
    frontier_gate_summary = {
            str(key): (
                bool(value)
                if isinstance(value, bool)
                else (
                    float(value)
                    if isinstance(value, (int, float))
                    else (
                        [str(item) for item in value if str(item).strip()]
                        if isinstance(value, list)
                        else value
                    )
                )
            )
            for key, value in retrieval_frontier_gate_summary.items()
            if isinstance(key, str)
    }
    if frontier_gate_summary:
        summary["retrieval_frontier_gate_summary"] = frontier_gate_summary
    deep_symbol_snapshot = {
        str(key): float(value or 0.0)
        for key, value in deep_symbol_summary.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    if deep_symbol_snapshot:
        summary["deep_symbol_summary"] = deep_symbol_snapshot
    native_scip_snapshot = {
        str(key): float(value or 0.0)
        for key, value in native_scip_summary.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    if native_scip_snapshot:
        summary["native_scip_summary"] = native_scip_snapshot
    validation_probe_snapshot = {
        str(key): float(value or 0.0)
        for key, value in validation_probe_summary.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    if validation_probe_snapshot:
        summary["validation_probe_summary"] = validation_probe_snapshot
    source_plan_feedback_snapshot = {
        str(key): float(value or 0.0)
        for key, value in source_plan_feedback_summary.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    if source_plan_feedback_snapshot:
        summary["source_plan_validation_feedback_summary"] = (
            source_plan_feedback_snapshot
        )
    source_plan_failure_signal_snapshot = {
        str(key): float(value or 0.0)
        for key, value in source_plan_failure_signal_summary.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    if source_plan_failure_signal_snapshot:
        summary["source_plan_failure_signal_summary"] = (
            source_plan_failure_signal_snapshot
        )
    return summary


def _build_metric_delta(
    *,
    current_metrics: dict[str, Any],
    previous_metrics: dict[str, Any],
    metric_names: list[str],
) -> dict[str, dict[str, float]]:
    delta: dict[str, dict[str, float]] = {}
    for metric in metric_names:
        if metric not in current_metrics or metric not in previous_metrics:
            continue
        current_value = float(current_metrics.get(metric, 0.0) or 0.0)
        previous_value = float(previous_metrics.get(metric, 0.0) or 0.0)
        delta[str(metric)] = {
            "current": current_value,
            "previous": previous_value,
            "delta": current_value - previous_value,
        }
    return delta


def _resolve_concept_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config = _load_yaml_config(path=matrix_config_path)
    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    gate_raw = freeze.get("concept_gate", config.get("concept_gate", {}))
    gate = gate_raw if isinstance(gate_raw, dict) else {}

    enabled = bool(gate.get("enabled", False))
    thresholds = _coerce_threshold_mapping(gate.get("thresholds"))
    if not thresholds:
        thresholds = {
            "precision_at_k_min": 0.60,
            "noise_rate_max": 0.40,
            "latency_p95_ms_max": 450.0,
            "chunk_hit_at_k_min": 0.80,
        }

    return {
        "enabled": enabled,
        "source": "config" if enabled else "disabled",
        "cases": str(gate.get("cases", "benchmark/cases/p1_concepts.yaml") or "benchmark/cases/p1_concepts.yaml"),
        "repo": str(gate.get("repo", "ace-lite-engine") or "ace-lite-engine"),
        "root": str(gate.get("root", ".") or "."),
        "skills_dir": str(gate.get("skills_dir", "skills") or "skills"),
        "top_k_files": max(1, int(gate.get("top_k_files", 6) or 6)),
        "min_candidate_score": max(0, int(gate.get("min_candidate_score", 2) or 2)),
        "candidate_ranker": str(gate.get("candidate_ranker", "heuristic") or "heuristic"),
        "retrieval_policy": str(gate.get("retrieval_policy", "auto") or "auto"),
        "chunk_top_k": max(1, int(gate.get("chunk_top_k", 24) or 24)),
        "cochange_enabled": bool(gate.get("cochange", False)),
        "retry_count": max(0, int(gate.get("retry_count", 0) or 0)),
        "thresholds": thresholds,
    }


def _resolve_external_concept_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config = _load_yaml_config(path=matrix_config_path)
    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    gate_raw = freeze.get(
        "external_concept_gate", config.get("external_concept_gate", {})
    )
    gate = gate_raw if isinstance(gate_raw, dict) else {}

    enabled = bool(gate.get("enabled", False))
    thresholds = _coerce_threshold_mapping(gate.get("thresholds"))
    if not thresholds:
        thresholds = {
            "precision_at_k_min": 0.58,
            "noise_rate_max": 0.42,
            "latency_p95_ms_max": 450.0,
            "chunk_hit_at_k_min": 0.80,
        }
    return {
        "enabled": enabled,
        "source": "config" if enabled else "disabled",
        "matrix_config": str(
            gate.get("matrix_config", "benchmark/matrix/external_howwhy.yaml")
            or "benchmark/matrix/external_howwhy.yaml"
        ),
        "thresholds": thresholds,
    }


def _resolve_feature_slices_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config = _load_yaml_config(path=matrix_config_path)
    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    gate_raw = freeze.get("feature_slices_gate", config.get("feature_slices_gate", {}))
    gate = gate_raw if isinstance(gate_raw, dict) else {}

    enabled = bool(gate.get("enabled", False))
    feature_config = str(
        gate.get("config", "benchmark/matrix/feature_slices.yaml")
        or "benchmark/matrix/feature_slices.yaml"
    ).strip() or "benchmark/matrix/feature_slices.yaml"
    return {
        "enabled": enabled,
        "source": "config" if enabled else "disabled",
        "config": feature_config,
    }


def _load_feature_slices_summary(*, summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists() or not summary_path.is_file():
        return {}

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return payload if isinstance(payload, dict) else {}


def _evaluate_feature_slices_gate(*, summary: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if not summary:
        failures.append(
            {
                "repo": "feature_slices_gate",
                "metric": "summary",
                "actual": "missing",
                "operator": "==",
                "expected": "present",
                "reason": "summary_missing",
            }
        )
        return failures

    if bool(summary.get("passed", False)):
        return failures

    slices_raw = summary.get("slices")
    slices = slices_raw if isinstance(slices_raw, list) else []
    if not slices:
        failures.append(
            {
                "repo": "feature_slices_gate",
                "metric": "slices",
                "actual": 0.0,
                "operator": ">=",
                "expected": 1.0,
                "reason": "no_slices",
            }
        )
        return failures

    for item in slices:
        if not isinstance(item, dict):
            continue
        if bool(item.get("passed", False)):
            continue
        name = str(item.get("name") or "").strip() or "(unknown)"
        item_failures_raw = item.get("failures")
        item_failures = (
            item_failures_raw if isinstance(item_failures_raw, list) else []
        )
        if not item_failures:
            failures.append(
                {
                    "repo": "feature_slices_gate",
                    "metric": "slice_passed",
                    "slice": name,
                    "actual": 0.0,
                    "operator": "==",
                    "expected": 1.0,
                    "reason": "slice_failed",
                }
            )
            continue
        for failure in item_failures:
            if not isinstance(failure, dict):
                continue
            failures.append(
                {
                    "repo": "feature_slices_gate",
                    "metric": str(failure.get("metric") or "slice_failure"),
                    "slice": name,
                    "actual": failure.get("actual"),
                    "operator": str(failure.get("operator") or ""),
                    "expected": failure.get("expected"),
                }
            )
    return failures


def _evaluate_concept_gate(
    *,
    benchmark_summary: dict[str, Any],
    concept_gate_config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not benchmark_summary:
        return [
            {
                "repo": "concept_gate",
                "metric": "summary",
                "actual": 0.0,
                "operator": "==",
                "expected": 1.0,
            }
        ]

    thresholds_raw = concept_gate_config.get("thresholds")
    thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
    metrics_raw = benchmark_summary.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

    repo_name = (
        str(benchmark_summary.get("repo", "") or "").strip()
        or str(concept_gate_config.get("repo", "ace-lite-engine") or "ace-lite-engine")
    )
    failures = _evaluate_metric_thresholds(
        metrics=metrics,
        thresholds={key: float(value) for key, value in thresholds.items()},
        repo_name=repo_name,
    )
    if int(benchmark_summary.get("case_count", 0) or 0) <= 0:
        failures.append(
            {
                "repo": repo_name,
                "metric": "case_count",
                "actual": 0.0,
                "operator": ">=",
                "expected": 1.0,
            }
        )
    return failures


def _evaluate_external_concept_gate(
    *,
    matrix_summary: dict[str, Any],
    thresholds: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    retrieval_mean_raw = matrix_summary.get("retrieval_metrics_mean")
    retrieval_mean = (
        retrieval_mean_raw if isinstance(retrieval_mean_raw, dict) else {}
    )
    metrics = {
        "precision_at_k": float(retrieval_mean.get("precision_at_k", 0.0) or 0.0),
        "noise_rate": float(retrieval_mean.get("noise_rate", 0.0) or 0.0),
        "latency_p95_ms": float(retrieval_mean.get("latency_p95_ms", 0.0) or 0.0),
        "chunk_hit_at_k": float(retrieval_mean.get("chunk_hit_at_k", 0.0) or 0.0),
    }
    failures = _evaluate_metric_thresholds(
        metrics=metrics,
        thresholds={key: float(value) for key, value in thresholds.items()},
        repo_name="external_concept_gate",
    )
    repo_count = max(0, int(matrix_summary.get("repo_count", 0) or 0))
    if repo_count <= 0:
        failures.append(
            {
                "repo": "external_concept_gate",
                "metric": "repo_count",
                "actual": float(repo_count),
                "operator": ">=",
                "expected": 1.0,
            }
        )
    return failures, metrics


def _evaluate_embedding_gate(
    *,
    matrix_summary: dict[str, Any],
    min_embedding_enabled_ratio: float,
    min_embedding_similarity_mean: float,
    min_embedding_rerank_ratio: float,
    min_embedding_cache_hit_ratio: float,
    max_embedding_fallback_ratio: float,
) -> list[dict[str, Any]]:
    checks = (
        ("embedding_similarity_mean", min_embedding_similarity_mean, ">="),
        ("embedding_rerank_ratio", min_embedding_rerank_ratio, ">="),
        ("embedding_cache_hit_ratio", min_embedding_cache_hit_ratio, ">="),
        ("embedding_fallback_ratio", max_embedding_fallback_ratio, "<="),
    )
    enabled_checks = [
        (metric, floor, operator)
        for metric, floor, operator in checks
        if isinstance(floor, (int, float)) and float(floor) >= 0.0
    ]
    enabled_ratio_threshold = (
        float(min_embedding_enabled_ratio)
        if isinstance(min_embedding_enabled_ratio, (int, float))
        else -1.0
    )
    if not enabled_checks and enabled_ratio_threshold < 0.0:
        return []

    repos_raw = matrix_summary.get("embedding_metrics_repos")
    repos = repos_raw if isinstance(repos_raw, list) else []
    failures: list[dict[str, Any]] = []

    for item in repos:
        if not isinstance(item, dict):
            continue
        repo = str(item.get("name") or "").strip() or "(unknown)"
        for metric, floor, operator in enabled_checks:
            actual = float(item.get(metric, 0.0) or 0.0)
            if operator == ">=" and actual < float(floor):
                failures.append(
                    {
                        "repo": repo,
                        "metric": metric,
                        "actual": actual,
                        "operator": operator,
                        "expected": float(floor),
                    }
                )
            if operator == "<=" and actual > float(floor):
                failures.append(
                    {
                        "repo": repo,
                        "metric": metric,
                        "actual": actual,
                        "operator": operator,
                        "expected": float(floor),
                    }
                )
    if enabled_ratio_threshold >= 0.0:
        means_raw = matrix_summary.get("embedding_metrics_mean")
        means = means_raw if isinstance(means_raw, dict) else {}
        actual_enabled_ratio = max(
            0.0, float(means.get("embedding_enabled_ratio", 0.0) or 0.0)
        )
        if actual_enabled_ratio < enabled_ratio_threshold:
            failures.append(
                {
                    "repo": "matrix",
                    "metric": "embedding_enabled_ratio",
                    "actual": actual_enabled_ratio,
                    "operator": ">=",
                    "expected": float(enabled_ratio_threshold),
                    "source": "matrix_mean",
                }
            )
    return failures


def _evaluate_e2e_success_gate(
    *,
    matrix_summary: dict[str, Any],
    min_success_rate: float,
    e2e_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if min_success_rate < 0.0:
        return []

    e2e = e2e_summary if isinstance(e2e_summary, dict) else {}
    e2e_case_count = max(0, int(e2e.get("case_count", 0) or 0))
    if e2e_case_count > 0 or ("task_success_rate" in e2e):
        try:
            actual = float(e2e.get("task_success_rate", 0.0) or 0.0)
        except Exception:
            actual = 0.0
        if actual < min_success_rate:
            return [
                {
                    "repo": "e2e_success_slice",
                    "metric": "task_success_rate",
                    "actual": actual,
                    "operator": ">=",
                    "expected": float(min_success_rate),
                    "source": "e2e_success_slice",
                }
            ]
        return []

    repos_raw = matrix_summary.get("task_success_repos")
    repos = repos_raw if isinstance(repos_raw, list) else []

    failures: list[dict[str, Any]] = []
    for item in repos:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or "(unknown)"
        try:
            actual = float(item.get("task_success_rate", 0.0) or 0.0)
        except Exception:
            actual = 0.0
        if actual < min_success_rate:
            failures.append(
                {
                    "repo": name,
                    "metric": "task_success_rate",
                    "actual": actual,
                    "operator": ">=",
                    "expected": float(min_success_rate),
                    "source": "benchmark_matrix",
                }
            )

    return failures


def _evaluate_plugin_policy_gate(
    *,
    matrix_summary: dict[str, Any],
    max_conflicts: int,
    max_blocked: int,
    max_warn: int,
) -> list[dict[str, Any]]:
    plugin_raw = matrix_summary.get("plugin_policy_summary")
    plugin = plugin_raw if isinstance(plugin_raw, dict) else {}

    totals_raw = plugin.get("totals")
    totals = totals_raw if isinstance(totals_raw, dict) else {}

    failures: list[dict[str, Any]] = []
    checks = (
        ("conflicts", int(max_conflicts)),
        ("blocked", int(max_blocked)),
        ("warn", int(max_warn)),
    )

    for key, threshold in checks:
        if threshold < 0:
            continue

        actual = max(0, int(totals.get(key, 0) or 0))
        if actual > threshold:
            failures.append(
                {
                    "metric": f"plugin_{key}",
                    "actual": actual,
                    "operator": "<=",
                    "expected": threshold,
                }
            )

    return failures


def _evaluate_retrieval_policy_guard(
    *,
    matrix_summary: dict[str, Any],
    max_regressed_repo_rate: float,
    min_task_success_mean: float,
    max_retrieval_task_gap_rate_mean: float,
    max_noise_rate_mean: float,
    max_latency_p95_ms_mean: float,
    max_slo_downgrade_case_rate_mean: float,
) -> list[dict[str, Any]]:
    thresholds = {
        "max_regressed_repo_rate": float(max_regressed_repo_rate),
        "min_task_success_mean": float(min_task_success_mean),
        "max_retrieval_task_gap_rate_mean": float(max_retrieval_task_gap_rate_mean),
        "max_noise_rate_mean": float(max_noise_rate_mean),
        "max_latency_p95_ms_mean": float(max_latency_p95_ms_mean),
        "max_slo_downgrade_case_rate_mean": float(
            max_slo_downgrade_case_rate_mean
        ),
    }
    enabled = any(value >= 0.0 for value in thresholds.values())
    if not enabled:
        return []

    rows_raw = matrix_summary.get("retrieval_policy_summary")
    rows = rows_raw if isinstance(rows_raw, list) else []
    if not rows:
        return [
            {
                "policy": "(missing)",
                "metric": "retrieval_policy_summary",
                "actual": "missing",
                "operator": "==",
                "expected": "present",
                "reason": "summary_missing",
            }
        ]

    failures: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue

        policy = str(item.get("retrieval_policy") or "auto").strip().lower() or "auto"
        checks = (
            (
                "regressed_repo_rate",
                float(item.get("regressed_repo_rate", 0.0) or 0.0),
                "<=",
                thresholds["max_regressed_repo_rate"],
            ),
            (
                "task_success_mean",
                float(item.get("task_success_mean", 0.0) or 0.0),
                ">=",
                thresholds["min_task_success_mean"],
            ),
            (
                "retrieval_task_gap_rate_mean",
                float(item.get("retrieval_task_gap_rate_mean", 0.0) or 0.0),
                "<=",
                thresholds["max_retrieval_task_gap_rate_mean"],
            ),
            (
                "noise_rate_mean",
                float(item.get("noise_rate_mean", 0.0) or 0.0),
                "<=",
                thresholds["max_noise_rate_mean"],
            ),
            (
                "latency_p95_ms_mean",
                float(item.get("latency_p95_ms_mean", 0.0) or 0.0),
                "<=",
                thresholds["max_latency_p95_ms_mean"],
            ),
            (
                "slo_downgrade_case_rate_mean",
                float(item.get("slo_downgrade_case_rate_mean", 0.0) or 0.0),
                "<=",
                thresholds["max_slo_downgrade_case_rate_mean"],
            ),
        )

        for metric, actual, operator, expected in checks:
            if expected < 0.0:
                continue
            failed = actual > expected if operator == "<=" else actual < expected
            if failed:
                failures.append(
                    {
                        "policy": policy,
                        "metric": metric,
                        "actual": actual,
                        "operator": operator,
                        "expected": expected,
                    }
                )

    return failures


def _resolve_validation_rich_gate_config(*, matrix_config_path: Path) -> dict[str, Any]:
    config = _load_yaml_config(path=matrix_config_path)
    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    gate_raw = freeze.get("validation_rich_gate", config.get("validation_rich_gate", {}))
    gate = gate_raw if isinstance(gate_raw, dict) else {}

    configured_mode_raw = str(gate.get("mode") or "").strip().lower()
    configured_mode = configured_mode_raw.replace("-", "_")
    if configured_mode not in {"disabled", "report_only", "enforced"}:
        configured_mode = ""

    if configured_mode:
        mode = configured_mode
        enabled = mode != "disabled"
        report_only = mode == "report_only"
        enforced = mode == "enforced"
        source = "config_mode"
    else:
        enabled = bool(gate.get("enabled", False))
        report_only = False
        enforced = enabled
        mode = "enforced" if enabled else "disabled"
        source = "config_flag" if enabled else "disabled"

    thresholds = _coerce_threshold_mapping(gate.get("thresholds"))
    return {
        "enabled": enabled,
        "mode": mode,
        "report_only": report_only,
        "enforced": enforced,
        "source": source,
        "thresholds": {
            "task_success_rate_min": _metric_threshold_from_mapping(
                thresholds, "task_success_rate_min"
            ),
            "precision_at_k_min": _metric_threshold_from_mapping(
                thresholds, "precision_at_k_min"
            ),
            "noise_rate_max": _metric_threshold_from_mapping(
                thresholds, "noise_rate_max"
            ),
            "latency_p95_ms_max": _metric_threshold_from_mapping(
                thresholds, "latency_p95_ms_max"
            ),
            "validation_test_count_min": _metric_threshold_from_mapping(
                thresholds, "validation_test_count_min"
            ),
            "missing_validation_rate_max": _metric_threshold_from_mapping(
                thresholds, "missing_validation_rate_max"
            ),
            "evidence_insufficient_rate_max": _metric_threshold_from_mapping(
                thresholds, "evidence_insufficient_rate_max"
            ),
        },
    }


def _evaluate_validation_rich_gate(
    *,
    benchmark_summary: dict[str, Any],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    enabled_thresholds = {
        key: float(value)
        for key, value in thresholds.items()
        if isinstance(value, (int, float)) and float(value) >= 0.0
    }
    if not enabled_thresholds:
        return []
    if not benchmark_summary:
        return [
            {
                "repo": "validation_rich_gate",
                "metric": "summary",
                "actual": "missing",
                "operator": "==",
                "expected": "present",
                "reason": "summary_missing",
            }
        ]

    metrics_raw = benchmark_summary.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    repo_name = str(benchmark_summary.get("repo", "") or "").strip() or "validation_rich_gate"
    failures = _evaluate_metric_thresholds(
        metrics=metrics,
        thresholds=enabled_thresholds,
        repo_name=repo_name,
    )
    if int(benchmark_summary.get("case_count", 0) or 0) <= 0:
        failures.append(
            {
                "repo": repo_name,
                "metric": "case_count",
                "actual": 0.0,
                "operator": ">=",
                "expected": 1.0,
            }
        )
    return failures


def _resolve_decision_observability_gate_config(
    *, matrix_config_path: Path
) -> dict[str, Any]:
    config = _load_yaml_config(path=matrix_config_path)
    freeze_raw = config.get("freeze")
    freeze = freeze_raw if isinstance(freeze_raw, dict) else {}
    gate_raw = freeze.get(
        "decision_observability_gate",
        config.get("decision_observability_gate", {}),
    )
    gate = gate_raw if isinstance(gate_raw, dict) else {}

    configured_mode_raw = str(gate.get("mode") or "").strip().lower()
    configured_mode = configured_mode_raw.replace("-", "_")
    if configured_mode not in {"disabled", "report_only", "enforced"}:
        configured_mode = ""

    if configured_mode:
        mode = configured_mode
        enabled = mode != "disabled"
        report_only = mode == "report_only"
        enforced = mode == "enforced"
        source = "config_mode"
    else:
        enabled = bool(gate.get("enabled", False))
        report_only = False
        enforced = enabled
        mode = "enforced" if enabled else "disabled"
        source = "config_flag" if enabled else "disabled"

    return {
        "enabled": enabled,
        "mode": mode,
        "report_only": report_only,
        "enforced": enforced,
        "source": source,
    }


def _evaluate_decision_observability_gate(
    *,
    matrix_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    if not matrix_summary:
        return [
            {
                "repo": "decision_observability_gate",
                "metric": "summary",
                "actual": "missing",
                "operator": "==",
                "expected": "present",
                "reason": "summary_missing",
            }
        ]

    summary_raw = matrix_summary.get("decision_observability_summary")
    if not isinstance(summary_raw, dict) or not summary_raw:
        return [
            {
                "repo": "decision_observability_gate",
                "metric": "decision_observability_summary",
                "actual": (
                    "missing"
                    if summary_raw is None or summary_raw == {}
                    else type(summary_raw).__name__
                ),
                "operator": "==",
                "expected": "present",
                "reason": "summary_missing",
            }
        ]

    summary = summary_raw
    failures: list[dict[str, Any]] = []
    scalar_values: dict[str, float] = {}
    bucket_totals: dict[str, float] = {}

    for key in _DECISION_OBSERVABILITY_SCALAR_KEYS:
        if key not in summary:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": key,
                    "actual": "missing",
                    "operator": "==",
                    "expected": "present",
                    "reason": "missing_field",
                }
            )
            continue
        value = summary.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": key,
                    "actual": type(value).__name__,
                    "operator": "==",
                    "expected": "number",
                    "reason": "invalid_type",
                }
            )
            continue
        numeric_value = float(value)
        scalar_values[key] = numeric_value
        if numeric_value < 0.0:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": key,
                    "actual": numeric_value,
                    "operator": ">=",
                    "expected": 0.0,
                    "reason": "negative_value",
                }
            )

    for key in _DECISION_OBSERVABILITY_MAPPING_KEYS:
        if key not in summary:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": key,
                    "actual": "missing",
                    "operator": "==",
                    "expected": "mapping",
                    "reason": "missing_field",
                }
            )
            continue
        counts_raw = summary.get(key)
        if not isinstance(counts_raw, dict):
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": key,
                    "actual": type(counts_raw).__name__,
                    "operator": "==",
                    "expected": "mapping",
                    "reason": "invalid_type",
                }
            )
            continue

        bucket_total = 0.0
        for bucket_name, bucket_value in counts_raw.items():
            if not isinstance(bucket_name, str) or not bucket_name.strip():
                failures.append(
                    {
                        "repo": "decision_observability_gate",
                        "metric": key,
                        "actual": repr(bucket_name),
                        "operator": "==",
                        "expected": "non_empty_bucket_key",
                        "reason": "invalid_bucket_key",
                    }
                )
                continue
            if isinstance(bucket_value, bool) or not isinstance(bucket_value, (int, float)):
                failures.append(
                    {
                        "repo": "decision_observability_gate",
                        "metric": key,
                        "bucket": bucket_name,
                        "actual": type(bucket_value).__name__,
                        "operator": "==",
                        "expected": "number",
                        "reason": "invalid_bucket_count",
                    }
                )
                continue
            numeric_bucket_value = float(bucket_value)
            if numeric_bucket_value < 0.0:
                failures.append(
                    {
                        "repo": "decision_observability_gate",
                        "metric": key,
                        "bucket": bucket_name,
                        "actual": numeric_bucket_value,
                        "operator": ">=",
                        "expected": 0.0,
                        "reason": "negative_bucket_count",
                    }
                )
                continue
            bucket_total += numeric_bucket_value
        bucket_totals[key] = bucket_total

    case_count = scalar_values.get("case_count")
    case_with_decisions_count = scalar_values.get("case_with_decisions_count")
    case_with_decisions_rate = scalar_values.get("case_with_decisions_rate")
    decision_event_count = scalar_values.get("decision_event_count")

    if (
        case_count is not None
        and case_with_decisions_count is not None
        and case_with_decisions_count > case_count
    ):
        failures.append(
            {
                "repo": "decision_observability_gate",
                "metric": "case_with_decisions_count",
                "actual": case_with_decisions_count,
                "operator": "<=",
                "expected": case_count,
                "reason": "count_exceeds_case_count",
            }
        )

    if (
        case_count is not None
        and case_with_decisions_count is not None
        and case_with_decisions_rate is not None
    ):
        expected_rate = (
            float(case_with_decisions_count) / float(case_count)
            if case_count > 0.0
            else 0.0
        )
        if not 0.0 <= case_with_decisions_rate <= 1.0:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": "case_with_decisions_rate",
                    "actual": case_with_decisions_rate,
                    "operator": "within",
                    "expected": "[0.0, 1.0]",
                    "reason": "rate_out_of_range",
                }
            )
        elif abs(case_with_decisions_rate - expected_rate) > 1e-6:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": "case_with_decisions_rate",
                    "actual": case_with_decisions_rate,
                    "operator": "==",
                    "expected": expected_rate,
                    "reason": "rate_mismatch",
                }
            )

    if decision_event_count is not None and case_with_decisions_count is not None:
        if decision_event_count > 0.0 and case_with_decisions_count <= 0.0:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": "decision_event_count",
                    "actual": decision_event_count,
                    "operator": "==",
                    "expected": 0.0,
                    "reason": "events_without_cases",
                }
            )
        for key in ("actions", "targets", "reasons"):
            bucket_total = bucket_totals.get(key)
            if bucket_total is None:
                continue
            if abs(bucket_total - decision_event_count) > 1e-6:
                failures.append(
                    {
                        "repo": "decision_observability_gate",
                        "metric": key,
                        "actual": bucket_total,
                        "operator": "==",
                        "expected": decision_event_count,
                        "reason": "bucket_total_mismatch",
                    }
                )
        outcomes_total = bucket_totals.get("outcomes")
        if outcomes_total is not None and outcomes_total > decision_event_count:
            failures.append(
                {
                    "repo": "decision_observability_gate",
                    "metric": "outcomes",
                    "actual": outcomes_total,
                    "operator": "<=",
                    "expected": decision_event_count,
                    "reason": "bucket_total_exceeds_event_count",
                }
            )

    return failures


def _policy_guard_blocks_release(
    *,
    config: dict[str, Any],
    failures: list[dict[str, Any]],
) -> bool:
    return bool(config.get("enforced", False)) and bool(failures)


def _render_markdown(*, payload: dict[str, Any]) -> str:
    steps = payload.get("steps", []) if isinstance(payload.get("steps"), list) else []

    lines: list[str] = [
        "# ACE-Lite Release Freeze Regression",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Passed: {payload.get('passed', False)}",
        f"- Elapsed: {float(payload.get('elapsed_seconds', 0.0) or 0.0):.2f}s",
        f"- Root: {payload.get('root', '')}",
        "",
        "## Step Results",
        "",
        "| Step | Status | Duration (s) | Exit Code |",
        "| --- | :---: | ---: | ---: |",
    ]

    for step in steps:
        if not isinstance(step, dict):
            continue
        lines.append(
            "| {name} | {status} | {duration:.3f} | {code} |".format(
                name=str(step.get("name", "")),
                status="PASS" if bool(step.get("passed", False)) else "FAIL",
                duration=float(step.get("elapsed_seconds", 0.0) or 0.0),
                code=int(step.get("returncode", 1) or 1),
            )
        )

    matrix_raw = payload.get("benchmark_matrix_summary")
    matrix: dict[str, Any] = matrix_raw if isinstance(matrix_raw, dict) else {}
    if matrix:
        lines.append("## Benchmark Matrix Summary")
        lines.append("")
        lines.append(f"- Passed: {bool(matrix.get('passed', False))}")
        lines.append(
            "- Benchmark regression detected: "
            f"{bool(matrix.get('benchmark_regression_detected', False))}"
        )
        lines.append(f"- Repo count: {int(matrix.get('repo_count', 0) or 0)}")
        lines.append(
            "- Task success mean: {value:.4f}".format(
                value=float(matrix.get("task_success_mean", 0.0) or 0.0)
            )
        )
        memory_means_raw = matrix.get("memory_metrics_mean")
        memory_means = memory_means_raw if isinstance(memory_means_raw, dict) else {}
        if memory_means:
            lines.append(
                "- Memory means: notes_hit_ratio={notes:.4f}, profile_selected_mean={profile:.4f}, capture_trigger_ratio={capture:.4f}".format(
                    notes=float(memory_means.get("notes_hit_ratio", 0.0) or 0.0),
                    profile=float(
                        memory_means.get("profile_selected_mean", 0.0) or 0.0
                    ),
                    capture=float(
                        memory_means.get("capture_trigger_ratio", 0.0) or 0.0
                    ),
                )
            )
        embedding_means_raw = matrix.get("embedding_metrics_mean")
        embedding_means = (
            embedding_means_raw if isinstance(embedding_means_raw, dict) else {}
        )
        if embedding_means:
            lines.append(
                "- Embedding means: enabled_ratio={enabled_ratio:.4f}, similarity={similarity:.4f}, rerank_ratio={rerank:.4f}, cache_hit={cache_hit:.4f}, fallback={fallback:.4f}".format(
                    enabled_ratio=float(
                        embedding_means.get("embedding_enabled_ratio", 0.0) or 0.0
                    ),
                    similarity=float(
                        embedding_means.get("embedding_similarity_mean", 0.0) or 0.0
                    ),
                    rerank=float(
                        embedding_means.get("embedding_rerank_ratio", 0.0) or 0.0
                    ),
                    cache_hit=float(
                        embedding_means.get("embedding_cache_hit_ratio", 0.0) or 0.0
                    ),
                    fallback=float(
                        embedding_means.get("embedding_fallback_ratio", 0.0) or 0.0
                    ),
                )
            )
        stage_latency_summary_raw = matrix.get("stage_latency_summary")
        stage_latency_summary = (
            stage_latency_summary_raw
            if isinstance(stage_latency_summary_raw, dict)
            else {}
        )
        if stage_latency_summary:
            total_stage_raw = stage_latency_summary.get("total")
            total_stage = (
                total_stage_raw if isinstance(total_stage_raw, dict) else {}
            )
            lines.append(
                "- Stage latency summary: total_mean={mean:.2f}ms, total_p95={p95:.2f}ms, index_p95={index:.2f}ms, repomap_p95={repomap:.2f}ms, source_plan_p95={source_plan:.2f}ms".format(
                    mean=float(total_stage.get("mean_ms", 0.0) or 0.0),
                    p95=float(total_stage.get("p95_ms", 0.0) or 0.0),
                    index=float(
                        (
                            stage_latency_summary.get("index", {})
                            if isinstance(stage_latency_summary.get("index", {}), dict)
                            else {}
                        ).get("p95_ms", 0.0)
                        or 0.0
                    ),
                    repomap=float(
                        (
                            stage_latency_summary.get("repomap", {})
                            if isinstance(stage_latency_summary.get("repomap", {}), dict)
                            else {}
                        ).get("p95_ms", 0.0)
                        or 0.0
                    ),
                    source_plan=float(
                        (
                            stage_latency_summary.get("source_plan", {})
                            if isinstance(
                                stage_latency_summary.get("source_plan", {}), dict
                            )
                            else {}
                        ).get("p95_ms", 0.0)
                        or 0.0
                    ),
                )
            )
        slo_budget_summary_raw = matrix.get("slo_budget_summary")
        slo_budget_summary = (
            slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
        )
        if slo_budget_summary:
            budget_limits_raw = slo_budget_summary.get("budget_limits_ms")
            budget_limits = (
                budget_limits_raw if isinstance(budget_limits_raw, dict) else {}
            )
            signals_raw = slo_budget_summary.get("signals")
            signals = signals_raw if isinstance(signals_raw, dict) else {}
            lines.append(
                "- SLO budget summary: downgrade_case_rate={rate:.4f}, parallel_budget={parallel:.2f}ms, embedding_budget={embedding:.2f}ms, chunk_semantic_budget={chunk:.2f}ms, xref_budget={xref:.2f}ms".format(
                    rate=float(
                        slo_budget_summary.get("downgrade_case_rate", 0.0) or 0.0
                    ),
                    parallel=float(
                        budget_limits.get("parallel_time_budget_ms_mean", 0.0) or 0.0
                    ),
                    embedding=float(
                        budget_limits.get("embedding_time_budget_ms_mean", 0.0)
                        or 0.0
                    ),
                    chunk=float(
                        budget_limits.get(
                            "chunk_semantic_time_budget_ms_mean", 0.0
                        )
                        or 0.0
                    ),
                    xref=float(
                        budget_limits.get("xref_time_budget_ms_mean", 0.0) or 0.0
                    ),
                )
            )
            lines.append(
                "- SLO signal rates: parallel_docs_timeout={parallel_docs:.4f}, embedding_budget_exceeded={embedding_budget:.4f}, embedding_fallback={embedding_fallback:.4f}, chunk_semantic_fallback={chunk_fallback:.4f}, xref_budget_exhausted={xref:.4f}".format(
                    parallel_docs=float(
                        (
                            signals.get("parallel_docs_timeout_ratio", {})
                            if isinstance(signals.get("parallel_docs_timeout_ratio", {}), dict)
                            else {}
                        ).get("rate", 0.0)
                        or 0.0
                    ),
                    embedding_budget=float(
                        (
                            signals.get("embedding_time_budget_exceeded_ratio", {})
                            if isinstance(
                                signals.get("embedding_time_budget_exceeded_ratio", {}),
                                dict,
                            )
                            else {}
                        ).get("rate", 0.0)
                        or 0.0
                    ),
                    embedding_fallback=float(
                        (
                            signals.get("embedding_fallback_ratio", {})
                            if isinstance(signals.get("embedding_fallback_ratio", {}), dict)
                            else {}
                        ).get("rate", 0.0)
                        or 0.0
                    ),
                    chunk_fallback=float(
                        (
                            signals.get("chunk_semantic_fallback_ratio", {})
                            if isinstance(
                                signals.get("chunk_semantic_fallback_ratio", {}), dict
                            )
                            else {}
                        ).get("rate", 0.0)
                        or 0.0
                    ),
                    xref=float(
                        (
                            signals.get("xref_budget_exhausted_ratio", {})
                            if isinstance(
                                signals.get("xref_budget_exhausted_ratio", {}), dict
                            )
                            else {}
                        ).get("rate", 0.0)
                        or 0.0
                    ),
                )
            )

        threshold_failed_raw = matrix.get("threshold_failed_repos")
        threshold_failed = (
            threshold_failed_raw if isinstance(threshold_failed_raw, list) else []
        )
        if threshold_failed:
            lines.append("- Threshold failed repos:")
            for item in threshold_failed:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"  - {item.get('name', '(unknown)')}: {int(item.get('failure_count', 0) or 0)} checks"
                )
        else:
            lines.append("- Threshold failed repos: (none)")

        regressed_raw = matrix.get("regressed_repos")
        regressed_repos = regressed_raw if isinstance(regressed_raw, list) else []
        if regressed_repos:
            lines.append("- Regressed repos:")
            for item in regressed_repos:
                if not isinstance(item, dict):
                    continue
                checks = item.get("failed_checks")
                checks_list = checks if isinstance(checks, list) else []
                lines.append(
                    "  - {name}: regressed={regressed}, failed_checks={checks}".format(
                        name=item.get("name", "(unknown)"),
                        regressed=bool(item.get("regressed", False)),
                        checks=",".join(str(value) for value in checks_list)
                        if checks_list
                        else "-",
                    )
                )
        else:
            lines.append("- Regressed repos: (none)")

        policy_summary_raw = matrix.get("retrieval_policy_summary")
        policy_summary = policy_summary_raw if isinstance(policy_summary_raw, list) else []
        if policy_summary:
            lines.append("- Retrieval policy summary:")
            for item in policy_summary:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {policy}: repos={repos}, regressed={regressed}, regressed_rate={regressed_rate:.4f}, task_success={task_success:.4f}, positive_task={positive_task:.4f}, gap_rate={gap_rate:.4f}, precision={precision:.4f}, noise={noise:.4f}, latency_p95_ms={latency:.2f}, repomap_p95_ms={repomap:.2f}, slo_downgrade={downgrade:.4f}".format(
                        policy=str(item.get("retrieval_policy", "auto") or "auto"),
                        repos=max(0, int(item.get("repo_count", 0) or 0)),
                        regressed=max(0, int(item.get("regressed_repo_count", 0) or 0)),
                        regressed_rate=float(
                            item.get("regressed_repo_rate", 0.0) or 0.0
                        ),
                        task_success=float(item.get("task_success_mean", 0.0) or 0.0),
                        positive_task=float(
                            item.get("positive_task_success_mean", 0.0) or 0.0
                        ),
                        gap_rate=float(
                            item.get("retrieval_task_gap_rate_mean", 0.0) or 0.0
                        ),
                        precision=float(
                            item.get("precision_at_k_mean", 0.0) or 0.0
                        ),
                        noise=float(item.get("noise_rate_mean", 0.0) or 0.0),
                        latency=float(
                            item.get("latency_p95_ms_mean", 0.0) or 0.0
                        ),
                        repomap=float(
                            item.get("repomap_latency_p95_ms_mean", 0.0) or 0.0
                        ),
                        downgrade=float(
                            item.get("slo_downgrade_case_rate_mean", 0.0) or 0.0
                        ),
                    )
                )
        else:
            lines.append("- Retrieval policy summary: (none)")

        plugin_summary_raw = matrix.get("plugin_policy_summary")
        plugin_summary = plugin_summary_raw if isinstance(plugin_summary_raw, dict) else {}
        plugin_totals_raw = plugin_summary.get("totals")
        plugin_totals = plugin_totals_raw if isinstance(plugin_totals_raw, dict) else {}
        plugin_mode_raw = plugin_summary.get("mode_distribution")
        plugin_mode = plugin_mode_raw if isinstance(plugin_mode_raw, dict) else {}
        plugin_repos_raw = plugin_summary.get("repos")
        plugin_repos = plugin_repos_raw if isinstance(plugin_repos_raw, list) else []

        lines.append(
            "- Plugin policy totals: applied={applied}, conflicts={conflicts}, blocked={blocked}, warn={warn}, remote_applied={remote}".format(
                applied=int(plugin_totals.get("applied", 0) or 0),
                conflicts=int(plugin_totals.get("conflicts", 0) or 0),
                blocked=int(plugin_totals.get("blocked", 0) or 0),
                warn=int(plugin_totals.get("warn", 0) or 0),
                remote=int(plugin_totals.get("remote_applied", 0) or 0),
            )
        )
        if plugin_mode:
            lines.append(
                "- Plugin policy modes: {items}".format(
                    items=", ".join(
                        f"{key!s}={int(value)}"
                        for key, value in sorted(plugin_mode.items())
                    )
                )
            )
        if plugin_repos:
            lines.append("- Plugin policy repos:")
            for item in plugin_repos:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {name}: mode={mode}, applied={applied}, conflicts={conflicts}, blocked={blocked}, warn={warn}, remote_applied={remote}".format(
                        name=str(item.get("name") or "(unknown)"),
                        mode=str(item.get("mode") or "(none)"),
                        applied=max(0, int(item.get("applied", 0) or 0)),
                        conflicts=max(0, int(item.get("conflicts", 0) or 0)),
                        blocked=max(0, int(item.get("blocked", 0) or 0)),
                        warn=max(0, int(item.get("warn", 0) or 0)),
                        remote=max(0, int(item.get("remote_applied", 0) or 0)),
                    )
                )
        lines.append("")

    validation_rich_raw = payload.get("validation_rich_benchmark")
    validation_rich = (
        validation_rich_raw if isinstance(validation_rich_raw, dict) else {}
    )
    if bool(validation_rich.get("enabled", False)):
        lines.append("## Validation-Rich Benchmark")
        lines.append("")
        lines.append(
            f"- Report only: {bool(validation_rich.get('report_only', True))}"
        )
        summary_path = str(validation_rich.get("summary_path", "") or "").strip()
        if summary_path:
            lines.append(f"- Summary: {summary_path}")
        previous_summary_path = str(
            validation_rich.get("previous_summary_path", "") or ""
        ).strip()
        if previous_summary_path:
            lines.append(f"- Previous summary: {previous_summary_path}")
        lines.append(
            f"- Loaded summary: {bool(validation_rich.get('loaded', False))}"
        )
        if previous_summary_path:
            lines.append(
                "- Loaded previous summary: {loaded}".format(
                    loaded=bool(validation_rich.get("previous_loaded", False))
                )
            )
        if bool(validation_rich.get("loaded", False)):
            repo_name = str(validation_rich.get("repo", "") or "").strip()
            if repo_name:
                lines.append(f"- Repo: {repo_name}")
            lines.append(
                f"- Case count: {int(validation_rich.get('case_count', 0) or 0)}"
            )
            lines.append(
                f"- Regressed: {bool(validation_rich.get('regressed', False))}"
            )
            failed_checks_raw = validation_rich.get("failed_checks")
            failed_checks = (
                failed_checks_raw if isinstance(failed_checks_raw, list) else []
            )
            lines.append(
                "- Failed checks: {checks}".format(
                    checks=",".join(str(item) for item in failed_checks)
                    if failed_checks
                    else "(none)"
                )
            )
            metrics_raw = validation_rich.get("metrics")
            metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
            lines.append(
                "- Metrics: task_success={task_success:.4f}, precision={precision:.4f}, noise={noise:.4f}, validation_test_count={validation_tests:.4f}, latency_p95_ms={latency:.2f}, evidence_insufficient={insufficient:.4f}, missing_validation={missing_validation:.4f}".format(
                    task_success=float(metrics.get("task_success_rate", 0.0) or 0.0),
                    precision=float(metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(metrics.get("noise_rate", 0.0) or 0.0),
                    validation_tests=float(
                        metrics.get("validation_test_count", 0.0) or 0.0
                    ),
                    latency=float(metrics.get("latency_p95_ms", 0.0) or 0.0),
                    insufficient=float(
                        metrics.get("evidence_insufficient_rate", 0.0) or 0.0
                    ),
                    missing_validation=float(
                        metrics.get("missing_validation_rate", 0.0) or 0.0
                    ),
                )
            )
            previous_metrics_raw = validation_rich.get("previous_metrics")
            previous_metrics = (
                previous_metrics_raw if isinstance(previous_metrics_raw, dict) else {}
            )
            if previous_metrics:
                lines.append(
                    "- Previous metrics: task_success={task_success:.4f}, precision={precision:.4f}, noise={noise:.4f}, validation_test_count={validation_tests:.4f}, latency_p95_ms={latency:.2f}, evidence_insufficient={insufficient:.4f}, missing_validation={missing_validation:.4f}".format(
                        task_success=float(
                            previous_metrics.get("task_success_rate", 0.0) or 0.0
                        ),
                        precision=float(
                            previous_metrics.get("precision_at_k", 0.0) or 0.0
                        ),
                        noise=float(previous_metrics.get("noise_rate", 0.0) or 0.0),
                        validation_tests=float(
                            previous_metrics.get("validation_test_count", 0.0) or 0.0
                        ),
                        latency=float(
                            previous_metrics.get("latency_p95_ms", 0.0) or 0.0
                        ),
                        insufficient=float(
                            previous_metrics.get("evidence_insufficient_rate", 0.0)
                            or 0.0
                        ),
                        missing_validation=float(
                            previous_metrics.get("missing_validation_rate", 0.0)
                            or 0.0
                        ),
                    )
                )
            gate_summary_raw = validation_rich.get("retrieval_control_plane_gate_summary")
            gate_summary = (
                gate_summary_raw if isinstance(gate_summary_raw, dict) else {}
            )
            if gate_summary:
                gate_failed_checks_raw = gate_summary.get("failed_checks")
                gate_failed_checks = (
                    gate_failed_checks_raw
                    if isinstance(gate_failed_checks_raw, list)
                    else []
                )
                lines.append(
                    "- Q2 retrieval control plane gate: passed={passed}, regression_evaluated={evaluated}, regression_detected={detected}, shadow_coverage={shadow:.4f}, risk_upgrade_gain={gain:.4f}, latency_p95_ms={latency:.2f}, failed_checks={failed_checks}".format(
                        passed=bool(gate_summary.get("gate_passed", False)),
                        evaluated=bool(gate_summary.get("regression_evaluated", False)),
                        detected=bool(
                            gate_summary.get("benchmark_regression_detected", False)
                        ),
                        shadow=float(
                            gate_summary.get("adaptive_router_shadow_coverage", 0.0)
                            or 0.0
                        ),
                        gain=float(
                            gate_summary.get("risk_upgrade_precision_gain", 0.0) or 0.0
                        ),
                        latency=float(gate_summary.get("latency_p95_ms", 0.0) or 0.0),
                        failed_checks=",".join(
                            str(item) for item in gate_failed_checks if str(item).strip()
                        )
                        or "(none)",
                    )
                )
            frontier_gate_summary_raw = validation_rich.get(
                "retrieval_frontier_gate_summary"
            )
            frontier_gate_summary = (
                frontier_gate_summary_raw
                if isinstance(frontier_gate_summary_raw, dict)
                else {}
            )
            if frontier_gate_summary:
                frontier_gate_failed_checks_raw = frontier_gate_summary.get(
                    "failed_checks"
                )
                frontier_gate_failed_checks = (
                    frontier_gate_failed_checks_raw
                    if isinstance(frontier_gate_failed_checks_raw, list)
                    else []
                )
                lines.append(
                    "- Q3 retrieval frontier gate: passed={passed}, deep_symbol_case_recall={recall:.4f}, native_scip_loaded_rate={native_scip:.4f}, precision_at_k={precision:.4f}, noise_rate={noise:.4f}, failed_checks={failed_checks}".format(
                        passed=bool(frontier_gate_summary.get("gate_passed", False)),
                        recall=float(
                            frontier_gate_summary.get(
                                "deep_symbol_case_recall", 0.0
                            )
                            or 0.0
                        ),
                        native_scip=float(
                            frontier_gate_summary.get(
                                "native_scip_loaded_rate", 0.0
                            )
                            or 0.0
                        ),
                        precision=float(
                            frontier_gate_summary.get("precision_at_k", 0.0)
                            or 0.0
                        ),
                        noise=float(
                            frontier_gate_summary.get("noise_rate", 0.0) or 0.0
                        ),
                        failed_checks=",".join(
                            str(item)
                            for item in frontier_gate_failed_checks
                            if str(item).strip()
                        )
                        or "(none)",
                    )
                )
            validation_probe_summary_raw = validation_rich.get(
                "validation_probe_summary"
            )
            validation_probe_summary = (
                validation_probe_summary_raw
                if isinstance(validation_probe_summary_raw, dict)
                else {}
            )
            if validation_probe_summary:
                lines.append(
                    "- Q4 validation probe summary: validation_test_count={test_count:.4f}, probe_enabled_ratio={enabled:.4f}, probe_executed_count_mean={executed:.4f}, probe_failure_rate={failure:.4f}".format(
                        test_count=float(
                            validation_probe_summary.get("validation_test_count", 0.0)
                            or 0.0
                        ),
                        enabled=float(
                            validation_probe_summary.get("probe_enabled_ratio", 0.0)
                            or 0.0
                        ),
                        executed=float(
                            validation_probe_summary.get(
                                "probe_executed_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        failure=float(
                            validation_probe_summary.get("probe_failure_rate", 0.0)
                            or 0.0
                        ),
                    )
                )
            source_plan_feedback_raw = validation_rich.get(
                "source_plan_validation_feedback_summary"
            )
            source_plan_feedback = (
                source_plan_feedback_raw
                if isinstance(source_plan_feedback_raw, dict)
                else {}
            )
            if source_plan_feedback:
                lines.append(
                    "- Q4 source-plan validation feedback: present_ratio={present:.4f}, failure_rate={failure:.4f}, issue_count_mean={issue:.4f}, probe_issue_count_mean={probe_issue:.4f}, probe_executed_count_mean={probe_executed:.4f}, selected_test_count_mean={selected:.4f}, executed_test_count_mean={executed:.4f}".format(
                        present=float(
                            source_plan_feedback.get("present_ratio", 0.0) or 0.0
                        ),
                        failure=float(
                            source_plan_feedback.get("failure_rate", 0.0) or 0.0
                        ),
                        issue=float(
                            source_plan_feedback.get("issue_count_mean", 0.0) or 0.0
                        ),
                        probe_issue=float(
                            source_plan_feedback.get("probe_issue_count_mean", 0.0)
                            or 0.0
                        ),
                        probe_executed=float(
                            source_plan_feedback.get(
                                "probe_executed_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        selected=float(
                            source_plan_feedback.get(
                                "selected_test_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        executed=float(
                            source_plan_feedback.get(
                                "executed_test_count_mean", 0.0
                            )
                            or 0.0
                        ),
                    )
                )
            previous_gate_summary_raw = validation_rich.get(
                "previous_retrieval_control_plane_gate_summary"
            )
            previous_gate_summary = (
                previous_gate_summary_raw
                if isinstance(previous_gate_summary_raw, dict)
                else {}
            )
            if previous_gate_summary:
                previous_gate_failed_checks_raw = previous_gate_summary.get(
                    "failed_checks"
                )
                previous_gate_failed_checks = (
                    previous_gate_failed_checks_raw
                    if isinstance(previous_gate_failed_checks_raw, list)
                    else []
                )
                lines.append(
                    "- Previous Q2 retrieval control plane gate: passed={passed}, regression_evaluated={evaluated}, regression_detected={detected}, shadow_coverage={shadow:.4f}, risk_upgrade_gain={gain:.4f}, latency_p95_ms={latency:.2f}, failed_checks={failed_checks}".format(
                        passed=bool(previous_gate_summary.get("gate_passed", False)),
                        evaluated=bool(
                            previous_gate_summary.get("regression_evaluated", False)
                        ),
                        detected=bool(
                            previous_gate_summary.get(
                                "benchmark_regression_detected", False
                            )
                        ),
                        shadow=float(
                            previous_gate_summary.get(
                                "adaptive_router_shadow_coverage", 0.0
                            )
                            or 0.0
                        ),
                        gain=float(
                            previous_gate_summary.get(
                                "risk_upgrade_precision_gain", 0.0
                            )
                            or 0.0
                        ),
                        latency=float(
                            previous_gate_summary.get("latency_p95_ms", 0.0) or 0.0
                        ),
                        failed_checks=",".join(
                            str(item)
                            for item in previous_gate_failed_checks
                            if str(item).strip()
                        )
                        or "(none)",
                    )
                )
            previous_frontier_gate_summary_raw = validation_rich.get(
                "previous_retrieval_frontier_gate_summary"
            )
            previous_frontier_gate_summary = (
                previous_frontier_gate_summary_raw
                if isinstance(previous_frontier_gate_summary_raw, dict)
                else {}
            )
            if previous_frontier_gate_summary:
                previous_frontier_failed_checks_raw = (
                    previous_frontier_gate_summary.get("failed_checks")
                )
                previous_frontier_failed_checks = (
                    previous_frontier_failed_checks_raw
                    if isinstance(previous_frontier_failed_checks_raw, list)
                    else []
                )
                lines.append(
                    "- Previous Q3 retrieval frontier gate: passed={passed}, deep_symbol_case_recall={recall:.4f}, native_scip_loaded_rate={native_scip:.4f}, precision_at_k={precision:.4f}, noise_rate={noise:.4f}, failed_checks={failed_checks}".format(
                        passed=bool(
                            previous_frontier_gate_summary.get(
                                "gate_passed", False
                            )
                        ),
                        recall=float(
                            previous_frontier_gate_summary.get(
                                "deep_symbol_case_recall", 0.0
                            )
                            or 0.0
                        ),
                        native_scip=float(
                            previous_frontier_gate_summary.get(
                                "native_scip_loaded_rate", 0.0
                            )
                            or 0.0
                        ),
                        precision=float(
                            previous_frontier_gate_summary.get(
                                "precision_at_k", 0.0
                            )
                            or 0.0
                        ),
                        noise=float(
                            previous_frontier_gate_summary.get("noise_rate", 0.0)
                            or 0.0
                        ),
                        failed_checks=",".join(
                            str(item)
                            for item in previous_frontier_failed_checks
                            if str(item).strip()
                        )
                        or "(none)",
                    )
                )
            previous_validation_probe_summary_raw = validation_rich.get(
                "previous_validation_probe_summary"
            )
            previous_validation_probe_summary = (
                previous_validation_probe_summary_raw
                if isinstance(previous_validation_probe_summary_raw, dict)
                else {}
            )
            if previous_validation_probe_summary:
                lines.append(
                    "- Previous Q4 validation probe summary: validation_test_count={test_count:.4f}, probe_enabled_ratio={enabled:.4f}, probe_executed_count_mean={executed:.4f}, probe_failure_rate={failure:.4f}".format(
                        test_count=float(
                            previous_validation_probe_summary.get(
                                "validation_test_count", 0.0
                            )
                            or 0.0
                        ),
                        enabled=float(
                            previous_validation_probe_summary.get(
                                "probe_enabled_ratio", 0.0
                            )
                            or 0.0
                        ),
                        executed=float(
                            previous_validation_probe_summary.get(
                                "probe_executed_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        failure=float(
                            previous_validation_probe_summary.get(
                                "probe_failure_rate", 0.0
                            )
                            or 0.0
                        ),
                    )
                )
            previous_source_plan_feedback_raw = validation_rich.get(
                "previous_source_plan_validation_feedback_summary"
            )
            previous_source_plan_feedback = (
                previous_source_plan_feedback_raw
                if isinstance(previous_source_plan_feedback_raw, dict)
                else {}
            )
            if previous_source_plan_feedback:
                lines.append(
                    "- Previous Q4 source-plan validation feedback: present_ratio={present:.4f}, failure_rate={failure:.4f}, issue_count_mean={issue:.4f}, probe_issue_count_mean={probe_issue:.4f}, probe_executed_count_mean={probe_executed:.4f}, selected_test_count_mean={selected:.4f}, executed_test_count_mean={executed:.4f}".format(
                        present=float(
                            previous_source_plan_feedback.get("present_ratio", 0.0)
                            or 0.0
                        ),
                        failure=float(
                            previous_source_plan_feedback.get("failure_rate", 0.0)
                            or 0.0
                        ),
                        issue=float(
                            previous_source_plan_feedback.get("issue_count_mean", 0.0)
                            or 0.0
                        ),
                        probe_issue=float(
                            previous_source_plan_feedback.get(
                                "probe_issue_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        probe_executed=float(
                            previous_source_plan_feedback.get(
                                "probe_executed_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        selected=float(
                            previous_source_plan_feedback.get(
                                "selected_test_count_mean", 0.0
                            )
                            or 0.0
                        ),
                        executed=float(
                            previous_source_plan_feedback.get(
                                "executed_test_count_mean", 0.0
                            )
                            or 0.0
                        ),
                    )
                )
            delta_raw = validation_rich.get("delta")
            delta = delta_raw if isinstance(delta_raw, dict) else {}
            if delta:
                lines.append("- Delta summary:")
                for metric in (
                    "task_success_rate",
                    "precision_at_k",
                    "noise_rate",
                    "latency_p95_ms",
                    "validation_test_count",
                    "evidence_insufficient_rate",
                    "missing_validation_rate",
                ):
                    item = delta.get(metric)
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        "  - {metric}: current={current:.4f}, previous={previous:.4f}, delta={delta_value:+.4f}".format(
                            metric=metric,
                            current=float(item.get("current", 0.0) or 0.0),
                            previous=float(item.get("previous", 0.0) or 0.0),
                            delta_value=float(item.get("delta", 0.0) or 0.0),
                        )
                    )
        else:
            lines.append("- Summary payload could not be loaded.")
        lines.append("")

    validation_rich_gate_raw = payload.get("validation_rich_gate")
    validation_rich_gate = (
        validation_rich_gate_raw if isinstance(validation_rich_gate_raw, dict) else {}
    )
    decision_observability_gate_raw = payload.get("decision_observability_gate")
    decision_observability_gate = (
        decision_observability_gate_raw
        if isinstance(decision_observability_gate_raw, dict)
        else {}
    )
    if bool(decision_observability_gate.get("enabled", False)):
        lines.append("## Decision Observability Gate")
        lines.append("")
        lines.append(
            f"- Passed: {bool(decision_observability_gate.get('passed', True))}"
        )
        lines.append(
            "- Mode: {mode}".format(
                mode=str(decision_observability_gate.get("mode", "disabled") or "disabled")
            )
        )
        lines.append(
            f"- Enforced: {bool(decision_observability_gate.get('enforced', False))}"
        )
        source_name = str(decision_observability_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        summary_path = str(
            decision_observability_gate.get("summary_path", "") or ""
        ).strip()
        if summary_path:
            lines.append(f"- Summary: {summary_path}")
        lines.append(
            "- Summary present: {present}".format(
                present=bool(decision_observability_gate.get("summary_present", False))
            )
        )
        required_scalar_keys = decision_observability_gate.get("required_scalar_keys")
        if isinstance(required_scalar_keys, list) and required_scalar_keys:
            lines.append(
                "- Required scalar keys: "
                + ", ".join(str(item) for item in required_scalar_keys)
            )
        required_mapping_keys = decision_observability_gate.get("required_mapping_keys")
        if isinstance(required_mapping_keys, list) and required_mapping_keys:
            lines.append(
                "- Required mapping keys: "
                + ", ".join(str(item) for item in required_mapping_keys)
            )
        summary_raw = decision_observability_gate.get("summary")
        summary = summary_raw if isinstance(summary_raw, dict) else {}
        if summary:
            lines.append(
                "- Cases with decisions: {count}/{case_count} ({rate:.4f})".format(
                    count=int(summary.get("case_with_decisions_count", 0) or 0),
                    case_count=int(summary.get("case_count", 0) or 0),
                    rate=float(summary.get("case_with_decisions_rate", 0.0) or 0.0),
                )
            )
            lines.append(
                "- Decision events: {count}".format(
                    count=int(summary.get("decision_event_count", 0) or 0)
                )
            )
        failures_raw = decision_observability_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                bucket = str(item.get("bucket", "") or "").strip()
                bucket_suffix = f", bucket={bucket}" if bucket else ""
                lines.append(
                    "  - {metric}: actual={actual}, expected {operator} {expected}{bucket}{reason}".format(
                        metric=str(item.get("metric", "")),
                        actual=item.get("actual"),
                        operator=str(item.get("operator", "")),
                        expected=item.get("expected"),
                        bucket=bucket_suffix,
                        reason=(
                            f" ({str(item.get('reason', '')).strip()})"
                            if str(item.get("reason", "")).strip()
                            else ""
                        ),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    if bool(validation_rich_gate.get("enabled", False)):
        lines.append("## Validation-Rich Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(validation_rich_gate.get('passed', True))}")
        lines.append(
            f"- Mode: {str(validation_rich_gate.get('mode', 'disabled') or 'disabled')}"
        )
        lines.append(
            f"- Enforced: {bool(validation_rich_gate.get('enforced', False))}"
        )
        source_name = str(validation_rich_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        summary_path = str(validation_rich_gate.get("summary_path", "") or "").strip()
        if summary_path:
            lines.append(f"- Summary: {summary_path}")
        thresholds_raw = validation_rich_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        lines.append(
            "- Thresholds: task_success_rate>={task_success:.4f}, precision_at_k>={precision:.4f}, noise_rate<={noise:.4f}, latency_p95_ms<={latency:.2f}, validation_test_count>={validation_tests:.4f}, missing_validation_rate<={missing_validation:.4f}, evidence_insufficient_rate<={insufficient:.4f}".format(
                task_success=float(thresholds.get("task_success_rate_min", -1.0) or -1.0),
                precision=float(thresholds.get("precision_at_k_min", -1.0) or -1.0),
                noise=float(thresholds.get("noise_rate_max", -1.0) or -1.0),
                latency=float(thresholds.get("latency_p95_ms_max", -1.0) or -1.0),
                validation_tests=float(
                    thresholds.get("validation_test_count_min", -1.0) or -1.0
                ),
                missing_validation=float(
                    thresholds.get("missing_validation_rate_max", -1.0) or -1.0
                ),
                insufficient=float(
                    thresholds.get("evidence_insufficient_rate_max", -1.0) or -1.0
                ),
            )
        )
        failures_raw = validation_rich_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {metric}: actual={actual}, expected {operator} {expected}{reason}".format(
                        metric=str(item.get("metric", "")),
                        actual=item.get("actual"),
                        operator=str(item.get("operator", "")),
                        expected=item.get("expected"),
                        reason=(
                            f" ({str(item.get('reason', '')).strip()})"
                            if str(item.get("reason", "")).strip()
                            else ""
                        ),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    plugin_gate_raw = payload.get("plugin_policy_gate")
    plugin_gate = plugin_gate_raw if isinstance(plugin_gate_raw, dict) else {}
    plugin_gate_enabled = bool(plugin_gate.get("enabled", False))
    if plugin_gate_enabled:
        lines.append("## Plugin Policy Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(plugin_gate.get('passed', True))}")
        profile_name = str(plugin_gate.get("profile", "") or "").strip()
        if profile_name:
            lines.append(f"- Profile: {profile_name}")
        source_name = str(plugin_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")

        thresholds_raw = plugin_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        lines.append(
            "- Thresholds: conflicts<={conflicts}, blocked<={blocked}, warn<={warn}".format(
                conflicts=int(
                    thresholds.get("max_conflicts", -1)
                ),
                blocked=int(
                    thresholds.get("max_blocked", -1)
                ),
                warn=int(thresholds.get("max_warn", -1)),
            )
        )

        failures_raw = plugin_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {metric}: actual={actual}, expected {operator} {expected}".format(
                        metric=str(item.get("metric", "")),
                        actual=int(item.get("actual", 0) or 0),
                        operator=str(item.get("operator", "")),
                        expected=int(item.get("expected", 0) or 0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    retrieval_policy_gate_raw = payload.get("retrieval_policy_guard")
    retrieval_policy_gate = (
        retrieval_policy_gate_raw if isinstance(retrieval_policy_gate_raw, dict) else {}
    )
    if bool(retrieval_policy_gate.get("enabled", False)):
        lines.append("## Retrieval Policy Guard")
        lines.append("")
        lines.append(f"- Passed: {bool(retrieval_policy_gate.get('passed', True))}")
        lines.append(
            f"- Mode: {str(retrieval_policy_gate.get('mode', 'disabled') or 'disabled')}"
        )
        lines.append(
            f"- Enforced: {bool(retrieval_policy_gate.get('enforced', False))}"
        )
        source_name = str(retrieval_policy_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")

        thresholds_raw = retrieval_policy_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        lines.append(
            "- Thresholds: regressed_repo_rate<={regressed_rate:.4f}, task_success_mean>={task_success:.4f}, retrieval_task_gap_rate_mean<={gap_rate:.4f}, noise_rate_mean<={noise:.4f}, latency_p95_ms_mean<={latency:.2f}, slo_downgrade_case_rate_mean<={downgrade:.4f}".format(
                regressed_rate=_metric_threshold_from_mapping(
                    thresholds, "max_regressed_repo_rate"
                ),
                task_success=_metric_threshold_from_mapping(
                    thresholds, "min_task_success_mean"
                ),
                gap_rate=_metric_threshold_from_mapping(
                    thresholds, "max_retrieval_task_gap_rate_mean"
                ),
                noise=_metric_threshold_from_mapping(
                    thresholds, "max_noise_rate_mean"
                ),
                latency=_metric_threshold_from_mapping(
                    thresholds, "max_latency_p95_ms_mean"
                ),
                downgrade=_metric_threshold_from_mapping(
                    thresholds, "max_slo_downgrade_case_rate_mean"
                ),
            )
        )

        failures_raw = retrieval_policy_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {policy}: {metric}={actual}, expected {operator} {expected}{reason}".format(
                        policy=str(item.get("policy", "(unknown)") or "(unknown)"),
                        metric=str(item.get("metric", "")),
                        actual=item.get("actual", ""),
                        operator=str(item.get("operator", "")),
                        expected=item.get("expected", ""),
                        reason=(
                            f" ({str(item.get('reason', '')).strip()})"
                            if str(item.get("reason", "")).strip()
                            else ""
                        ),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    tabiv3_gate_raw = payload.get("tabiv3_gate")
    tabiv3_gate = tabiv3_gate_raw if isinstance(tabiv3_gate_raw, dict) else {}
    if bool(tabiv3_gate.get("enabled", False)):
        lines.append("## TabIV3 Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(tabiv3_gate.get('passed', True))}")
        source_name = str(tabiv3_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        matrix_config = str(tabiv3_gate.get("matrix_config", "") or "").strip()
        if matrix_config:
            lines.append(f"- Matrix config: {matrix_config}")
        lines.append(f"- Repo count: {int(tabiv3_gate.get('repo_count', 0) or 0)}")
        lines.append(
            f"- Matrix summary passed: {bool(tabiv3_gate.get('matrix_summary_passed', False))}"
        )
        thresholds_raw = tabiv3_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        lines.append(
            "- Thresholds: latency_p95_ms<={latency:.2f}, repomap_latency_p95_ms<={repomap:.2f}".format(
                latency=float(thresholds.get("latency_p95_ms_max", 0.0) or 0.0),
                repomap=float(
                    thresholds.get("repomap_latency_p95_ms_max", 0.0) or 0.0
                ),
            )
        )
        failures_raw = tabiv3_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {repo}: {metric}={actual:.4f}, expected {operator} {expected:.4f}".format(
                        repo=str(item.get("repo", "(unknown)")),
                        metric=str(item.get("metric", "")),
                        actual=float(item.get("actual", 0.0) or 0.0),
                        operator=str(item.get("operator", "<=")),
                        expected=float(item.get("expected", 0.0) or 0.0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    concept_gate_raw = payload.get("concept_gate")
    concept_gate = concept_gate_raw if isinstance(concept_gate_raw, dict) else {}
    if bool(concept_gate.get("enabled", False)):
        lines.append("## Concept Benchmark Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(concept_gate.get('passed', True))}")
        source_name = str(concept_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        cases_path = str(concept_gate.get("cases", "") or "").strip()
        if cases_path:
            lines.append(f"- Cases: {cases_path}")
        lines.append(f"- Case count: {int(concept_gate.get('case_count', 0) or 0)}")
        execution_config_raw = concept_gate.get("execution_config")
        execution_config = (
            execution_config_raw if isinstance(execution_config_raw, dict) else {}
        )
        if execution_config:
            lines.append(
                "- Execution config: top_k_files={top_k_files}, min_candidate_score={min_score}, candidate_ranker={ranker}, retrieval_policy={policy}, chunk_top_k={chunk_top_k}, cochange={cochange}".format(
                    top_k_files=max(
                        1, int(execution_config.get("top_k_files", 0) or 0)
                    ),
                    min_score=max(
                        0,
                        int(execution_config.get("min_candidate_score", 0) or 0),
                    ),
                    ranker=str(
                        execution_config.get("candidate_ranker", "") or "heuristic"
                    ),
                    policy=str(
                        execution_config.get("retrieval_policy", "") or "auto"
                    ),
                    chunk_top_k=max(
                        1, int(execution_config.get("chunk_top_k", 0) or 0)
                    ),
                    cochange=bool(execution_config.get("cochange", False)),
                )
            )
        thresholds_raw = concept_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        if thresholds:
            lines.append(
                "- Thresholds: "
                + ", ".join(
                    f"{key}={float(value):.4f}"
                    for key, value in sorted(thresholds.items())
                )
            )
        metrics_raw = concept_gate.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        if metrics:
            lines.append(
                "- Metrics: precision_at_k={precision:.4f}, noise_rate={noise:.4f}, chunk_hit_at_k={chunk_hit:.4f}, latency_p95_ms={latency:.2f}".format(
                    precision=float(metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(metrics.get("noise_rate", 0.0) or 0.0),
                    chunk_hit=float(metrics.get("chunk_hit_at_k", 0.0) or 0.0),
                    latency=float(metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
        failures_raw = concept_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {repo}: {metric}={actual:.4f}, expected {operator} {expected:.4f}".format(
                        repo=str(item.get("repo", "(unknown)")),
                        metric=str(item.get("metric", "")),
                        actual=float(item.get("actual", 0.0) or 0.0),
                        operator=str(item.get("operator", ">=")),
                        expected=float(item.get("expected", 0.0) or 0.0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    external_concept_gate_raw = payload.get("external_concept_gate")
    external_concept_gate = (
        external_concept_gate_raw
        if isinstance(external_concept_gate_raw, dict)
        else {}
    )
    if bool(external_concept_gate.get("enabled", False)):
        lines.append("## External Concept Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(external_concept_gate.get('passed', True))}")
        source_name = str(external_concept_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        matrix_config = str(
            external_concept_gate.get("matrix_config", "") or ""
        ).strip()
        if matrix_config:
            lines.append(f"- Matrix config: {matrix_config}")
        lines.append(
            f"- Repo count: {int(external_concept_gate.get('repo_count', 0) or 0)}"
        )
        thresholds_raw = external_concept_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        if thresholds:
            lines.append(
                "- Thresholds: "
                + ", ".join(
                    f"{key}={float(value):.4f}"
                    for key, value in sorted(thresholds.items())
                )
            )
        metrics_raw = external_concept_gate.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        if metrics:
            lines.append(
                "- Metrics: precision_at_k={precision:.4f}, noise_rate={noise:.4f}, chunk_hit_at_k={chunk_hit:.4f}, latency_p95_ms={latency:.2f}".format(
                    precision=float(metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(metrics.get("noise_rate", 0.0) or 0.0),
                    chunk_hit=float(metrics.get("chunk_hit_at_k", 0.0) or 0.0),
                    latency=float(metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
        failures_raw = external_concept_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {repo}: {metric}={actual:.4f}, expected {operator} {expected:.4f}".format(
                        repo=str(item.get("repo", "(unknown)")),
                        metric=str(item.get("metric", "")),
                        actual=float(item.get("actual", 0.0) or 0.0),
                        operator=str(item.get("operator", ">=")),
                        expected=float(item.get("expected", 0.0) or 0.0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    feature_slices_gate_raw = payload.get("feature_slices_gate")
    feature_slices_gate = (
        feature_slices_gate_raw if isinstance(feature_slices_gate_raw, dict) else {}
    )
    if bool(feature_slices_gate.get("enabled", False)):
        lines.append("## Feature Slices Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(feature_slices_gate.get('passed', True))}")
        source_name = str(feature_slices_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        config_path = str(feature_slices_gate.get("config", "") or "").strip()
        if config_path:
            lines.append(f"- Config: {config_path}")
        summary_path = str(feature_slices_gate.get("summary_path", "") or "").strip()
        if summary_path:
            lines.append(f"- Summary: {summary_path}")
        lines.append(
            "- Summary passed: {passed}".format(
                passed=bool(feature_slices_gate.get("summary_passed", False))
            )
        )
        lines.append(
            "- Slice count: {count}".format(
                count=int(feature_slices_gate.get("slice_count", 0) or 0)
            )
        )
        failures_raw = feature_slices_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                slice_name = str(item.get("slice") or "").strip()
                slice_label = f" slice={slice_name}" if slice_name else ""
                reason = str(item.get("reason") or "").strip()
                reason_label = f" ({reason})" if reason else ""
                lines.append(
                    "  - {metric}:{slice_label} actual={actual}, expected {operator} {expected}{reason_label}".format(
                        metric=str(item.get("metric", "")),
                        slice_label=slice_label,
                        actual=str(item.get("actual", "")),
                        operator=str(item.get("operator", "")),
                        expected=str(item.get("expected", "")),
                        reason_label=reason_label,
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")


    e2e_gate_raw = payload.get("e2e_success_gate")
    e2e_gate = e2e_gate_raw if isinstance(e2e_gate_raw, dict) else {}
    if bool(e2e_gate.get("enabled", False)):
        lines.append("## End-to-End Success Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(e2e_gate.get('passed', True))}")
        lines.append(
            "- Minimum success rate: {value:.4f}".format(
                value=float(e2e_gate.get("min_success_rate", 0.0) or 0.0)
            )
        )
        source_name = str(e2e_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        source_metric = str(e2e_gate.get("source_metric", "") or "").strip()
        if source_metric:
            lines.append(f"- Metric source: {source_metric}")
        lines.append(
            "- Observed success rate: {value:.4f}".format(
                value=float(e2e_gate.get("task_success_rate", 0.0) or 0.0)
            )
        )
        case_count = int(e2e_gate.get("case_count", 0) or 0)
        if case_count > 0:
            lines.append(
                "- E2E cases: {case_count} (passed={passed_count}, failed={failed_count})".format(
                    case_count=case_count,
                    passed_count=int(e2e_gate.get("passed_count", 0) or 0),
                    failed_count=int(e2e_gate.get("failed_count", 0) or 0),
                )
            )
        failures_raw = e2e_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {repo}: {metric}={actual:.4f}, expected {operator} {expected:.4f}".format(
                        repo=str(item.get("repo", "(unknown)")),
                        metric=str(item.get("metric", "task_success_rate")),
                        actual=float(item.get("actual", 0.0) or 0.0),
                        operator=str(item.get("operator", ">=")),
                        expected=float(item.get("expected", 0.0) or 0.0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    runtime_gate_raw = payload.get("runtime_gate")
    runtime_gate = runtime_gate_raw if isinstance(runtime_gate_raw, dict) else {}
    if bool(runtime_gate.get("enabled", False)):
        lines.append("## Runtime Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(runtime_gate.get('passed', True))}")
        source_name = str(runtime_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        step_name = str(runtime_gate.get("step", "") or "").strip()
        if step_name:
            lines.append(f"- Step: {step_name}")
        failures_raw = runtime_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {metric}: actual={actual}, expected {operator} {expected} ({reason})".format(
                        metric=str(item.get("metric", "")),
                        actual=str(item.get("actual", "")),
                        operator=str(item.get("operator", "")),
                        expected=str(item.get("expected", "")),
                        reason=str(item.get("reason", "")),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    memory_gate_raw = payload.get("memory_gate")
    memory_gate = memory_gate_raw if isinstance(memory_gate_raw, dict) else {}
    if bool(memory_gate.get("enabled", False)):
        lines.append("## Memory Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(memory_gate.get('passed', True))}")
        source_name = str(memory_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        thresholds_raw = memory_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        lines.append(
            "- Thresholds: notes_hit_ratio>={notes:.4f}, profile_selected_mean>={profile:.4f}, capture_trigger_ratio>={capture:.4f}".format(
                notes=float(thresholds.get("min_notes_hit_ratio", -1.0) or -1.0),
                profile=float(
                    thresholds.get("min_profile_selected_mean", -1.0) or -1.0
                ),
                capture=float(
                    thresholds.get("min_capture_trigger_ratio", -1.0) or -1.0
                ),
            )
        )
        means_raw = memory_gate.get("means")
        means = means_raw if isinstance(means_raw, dict) else {}
        if means:
            lines.append(
                "- Means: notes_hit_ratio={notes:.4f}, profile_selected_mean={profile:.4f}, capture_trigger_ratio={capture:.4f}".format(
                    notes=float(means.get("notes_hit_ratio", 0.0) or 0.0),
                    profile=float(means.get("profile_selected_mean", 0.0) or 0.0),
                    capture=float(means.get("capture_trigger_ratio", 0.0) or 0.0),
                )
            )
        failures_raw = memory_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {repo}: {metric}={actual:.4f}, expected {operator} {expected:.4f}".format(
                        repo=str(item.get("repo", "(unknown)")),
                        metric=str(item.get("metric", "")),
                        actual=float(item.get("actual", 0.0) or 0.0),
                        operator=str(item.get("operator", ">=")),
                        expected=float(item.get("expected", 0.0) or 0.0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    embedding_gate_raw = payload.get("embedding_gate")
    embedding_gate = embedding_gate_raw if isinstance(embedding_gate_raw, dict) else {}
    if bool(embedding_gate.get("enabled", False)):
        lines.append("## Embedding Gate")
        lines.append("")
        lines.append(f"- Passed: {bool(embedding_gate.get('passed', True))}")
        source_name = str(embedding_gate.get("source", "") or "").strip()
        if source_name:
            lines.append(f"- Source: {source_name}")
        thresholds_raw = embedding_gate.get("thresholds")
        thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
        lines.append(
            "- Thresholds: enabled_ratio>={enabled_ratio:.4f}, similarity>={similarity:.4f}, rerank_ratio>={rerank:.4f}, cache_hit>={cache_hit:.4f}, fallback<={fallback:.4f}".format(
                enabled_ratio=float(
                    thresholds.get("min_embedding_enabled_ratio", -1.0) or -1.0
                ),
                similarity=float(
                    thresholds.get("min_embedding_similarity_mean", -1.0) or -1.0
                ),
                rerank=float(
                    thresholds.get("min_embedding_rerank_ratio", -1.0) or -1.0
                ),
                cache_hit=float(
                    thresholds.get("min_embedding_cache_hit_ratio", -1.0) or -1.0
                ),
                fallback=float(
                    thresholds.get("max_embedding_fallback_ratio", -1.0) or -1.0
                ),
            )
        )
        means_raw = embedding_gate.get("means")
        means = means_raw if isinstance(means_raw, dict) else {}
        if means:
            lines.append(
                "- Means: enabled_ratio={enabled_ratio:.4f}, similarity={similarity:.4f}, rerank_ratio={rerank:.4f}, cache_hit={cache_hit:.4f}, fallback={fallback:.4f}".format(
                    enabled_ratio=float(
                        means.get("embedding_enabled_ratio", 0.0) or 0.0
                    ),
                    similarity=float(
                        means.get("embedding_similarity_mean", 0.0) or 0.0
                    ),
                    rerank=float(
                        means.get("embedding_rerank_ratio", 0.0) or 0.0
                    ),
                    cache_hit=float(
                        means.get("embedding_cache_hit_ratio", 0.0) or 0.0
                    ),
                    fallback=float(
                        means.get("embedding_fallback_ratio", 0.0) or 0.0
                    ),
                )
            )
        failures_raw = embedding_gate.get("failures")
        failures = failures_raw if isinstance(failures_raw, list) else []
        if failures:
            lines.append("- Failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - {repo}: {metric}={actual:.4f}, expected {operator} {expected:.4f}".format(
                        repo=str(item.get("repo", "(unknown)")),
                        metric=str(item.get("metric", "")),
                        actual=float(item.get("actual", 0.0) or 0.0),
                        operator=str(item.get("operator", ">=")),
                        expected=float(item.get("expected", 0.0) or 0.0),
                    )
                )
        else:
            lines.append("- Failures: (none)")
        lines.append("")

    lines.append("")
    lines.append("## Commands")
    lines.append("")

    for step in steps:
        if not isinstance(step, dict):
            continue
        lines.append(f"### {step.get('name', '')}")
        lines.append("")
        lines.append(f"- cmd: `{step.get('command_line', '')}`")
        lines.append(f"- stdout: `{step.get('stdout_path', '')}`")
        lines.append(f"- stderr: `{step.get('stderr_path', '')}`")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _resolve_matrix_path(*, root: Path, matrix_config: str) -> Path:
    candidate = Path(matrix_config)
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release-freeze regression checks.")
    parser.add_argument(
        "--matrix-config",
        default="benchmark/matrix/repos.yaml",
        help="Benchmark matrix config path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/release-freeze/latest",
        help="Output directory for freeze regression report.",
    )
    parser.add_argument(
        "--validation-rich-summary",
        default="",
        help="Optional validation-rich benchmark summary.json path to include as report-only evidence.",
    )
    parser.add_argument(
        "--validation-rich-previous-summary",
        default="",
        help="Optional previous validation-rich benchmark summary.json path used for report-only delta comparison.",
    )
    parser.add_argument("--cli-bin", default="ace-lite", help="CLI binary name/path.")
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Fail if benchmark matrix thresholds fail.",
    )
    parser.add_argument(
        "--max-plugin-conflicts",
        type=int,
        default=-1,
        help="Optional freeze gate: maximum allowed plugin conflicts (negative disables).",
    )
    parser.add_argument(
        "--max-plugin-blocked",
        type=int,
        default=-1,
        help="Optional freeze gate: maximum allowed plugin blocked count (negative disables).",
    )
    parser.add_argument(
        "--max-plugin-warn",
        type=int,
        default=-1,
        help="Optional freeze gate: maximum allowed plugin warn count (negative disables).",
    )
    parser.add_argument(
        "--plugin-gate-profile",
        default="",
        help="Optional plugin gate profile name loaded from matrix config.",
    )
    parser.add_argument(
        "--e2e-success-floor",
        type=float,
        default=-1.0,
        help="Optional freeze gate: minimum task success rate per repo (negative disables).",
    )
    parser.add_argument(
        "--e2e-cases",
        default="benchmark/cases/e2e/internal.yaml",
        help="Case set used by standalone e2e success slice harness.",
    )
    parser.add_argument(
        "--skip-skill-validation",
        action="store_true",
        help="Skip cross-agent skill routing validation step.",
    )
    runtime_gate_group = parser.add_mutually_exclusive_group()
    runtime_gate_group.add_argument(
        "--runtime-gate",
        dest="runtime_gate",
        action="store_true",
        help="Enable runtime regression gate step.",
    )
    runtime_gate_group.add_argument(
        "--no-runtime-gate",
        dest="runtime_gate",
        action="store_false",
        help="Disable runtime regression gate step.",
    )
    parser.set_defaults(runtime_gate=None)
    parser.add_argument(
        "--skill-validation-repo-url",
        default="https://github.com/blockscout/frontend.git",
        help="Target repository URL for skill validation.",
    )
    parser.add_argument(
        "--skill-validation-repo-ref",
        default="main",
        help="Target repository git ref for skill validation.",
    )
    parser.add_argument(
        "--skill-validation-repo-name",
        default="blockscout-frontend",
        help="Target repository identifier for skill validation.",
    )
    parser.add_argument(
        "--skill-validation-min-pass-rate",
        type=float,
        default=1.0,
        help="Minimum skill validation pass rate required by freeze gate.",
    )
    parser.add_argument(
        "--skill-validation-apps",
        default="codex,opencode,claude-code",
        help="Comma-separated app scopes validated by skill gate.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    validation_rich_summary_arg = str(args.validation_rich_summary or "").strip()
    validation_rich_summary_path = (
        _resolve_matrix_path(root=root, matrix_config=validation_rich_summary_arg)
        if validation_rich_summary_arg
        else None
    )
    validation_rich_previous_summary_arg = str(
        args.validation_rich_previous_summary or ""
    ).strip()
    validation_rich_previous_summary_path = (
        _resolve_matrix_path(
            root=root, matrix_config=validation_rich_previous_summary_arg
        )
        if validation_rich_previous_summary_arg
        else None
    )

    matrix_output = output_dir / "benchmark-matrix"
    tabiv3_output = output_dir / "benchmark-matrix-tabiv3"
    e2e_output = output_dir / "e2e-success"
    concept_output = output_dir / "benchmark-concept-gate"
    external_concept_output = output_dir / "benchmark-matrix-external-concept"
    feature_slices_output = output_dir / "feature-slices"
    for stale_dir in (
        matrix_output,
        tabiv3_output,
        e2e_output,
        concept_output,
        external_concept_output,
        feature_slices_output,
    ):
        if stale_dir.exists():
            shutil.rmtree(stale_dir, ignore_errors=True)
        stale_dir.mkdir(parents=True, exist_ok=True)
    matrix_config_path = _resolve_matrix_path(root=root, matrix_config=args.matrix_config)
    e2e_cases_path = _resolve_matrix_path(root=root, matrix_config=args.e2e_cases)
    runtime_gate_config = _resolve_runtime_gate_config(
        matrix_config_path=matrix_config_path,
        cli_enabled=args.runtime_gate,
    )
    runtime_gate_enabled = bool(runtime_gate_config.get("enabled", True))
    tabiv3_gate_config = _resolve_tabiv3_gate_config(matrix_config_path=matrix_config_path)
    tabiv3_gate_enabled = bool(tabiv3_gate_config.get("enabled", False))
    tabiv3_matrix_config_path = _resolve_matrix_path(
        root=root,
        matrix_config=str(tabiv3_gate_config.get("matrix_config", "benchmark/matrix/tabiv3.yaml")),
    )
    tabiv3_gate_thresholds_raw = tabiv3_gate_config.get("thresholds")
    tabiv3_gate_thresholds = (
        tabiv3_gate_thresholds_raw
        if isinstance(tabiv3_gate_thresholds_raw, dict)
        else {
            "latency_p95_ms_max": 170.0,
            "repomap_latency_p95_ms_max": 110.0,
        }
    )
    tabiv3_gate_latency_p95_max = float(
        tabiv3_gate_thresholds.get("latency_p95_ms_max", 170.0) or 170.0
    )
    tabiv3_gate_repomap_latency_p95_max = float(
        tabiv3_gate_thresholds.get("repomap_latency_p95_ms_max", 110.0) or 110.0
    )
    tabiv3_gate_retry_count = max(0, int(tabiv3_gate_config.get("retry_count", 0) or 0))
    concept_gate_config = _resolve_concept_gate_config(matrix_config_path=matrix_config_path)
    concept_gate_enabled = bool(concept_gate_config.get("enabled", False))
    concept_gate_retry_count = max(0, int(concept_gate_config.get("retry_count", 0) or 0))
    concept_cases_path = _resolve_matrix_path(
        root=root, matrix_config=str(concept_gate_config.get("cases", "benchmark/cases/p1_concepts.yaml"))
    )
    concept_root_path = _resolve_matrix_path(
        root=root, matrix_config=str(concept_gate_config.get("root", "."))
    )
    concept_skills_dir = _resolve_matrix_path(
        root=root, matrix_config=str(concept_gate_config.get("skills_dir", "skills"))
    )
    external_concept_gate_config = _resolve_external_concept_gate_config(
        matrix_config_path=matrix_config_path
    )
    external_concept_gate_enabled = bool(
        external_concept_gate_config.get("enabled", False)
    )
    external_concept_matrix_config_path = _resolve_matrix_path(
        root=root,
        matrix_config=str(
            external_concept_gate_config.get(
                "matrix_config", "benchmark/matrix/external_howwhy.yaml"
            )
        ),
    )
    feature_slices_gate_config = _resolve_feature_slices_gate_config(
        matrix_config_path=matrix_config_path
    )
    feature_slices_gate_enabled = bool(feature_slices_gate_config.get("enabled", False))
    feature_slices_config_path = _resolve_matrix_path(
        root=root,
        matrix_config=str(
            feature_slices_gate_config.get("config", "benchmark/matrix/feature_slices.yaml")
        ),
    )

    skill_validation_output = output_dir / "skill-validation"
    skill_validation_report = skill_validation_output / "skill_validation_matrix.json"
    skill_validation_index = skill_validation_output / "skill_validation_index.json"
    skill_validation_repo_dir = root / "artifacts" / "repos-workdir" / "skill-validation"

    steps_spec: list[tuple[str, list[str]]] = []
    if tabiv3_gate_enabled:
        # Keep tabiv3 latency gate ahead of heavy test suites to reduce thermal/load skew.
        steps_spec.append(
            (
                "benchmark_matrix_tabiv3",
                [
                    sys.executable,
                    str(root / "scripts" / "run_benchmark_matrix.py"),
                    "--matrix-config",
                    str(tabiv3_matrix_config_path),
                    "--output-dir",
                    str(tabiv3_output),
                    "--cli-bin",
                    str(args.cli_bin),
                ],
            )
        )

    steps_spec.extend(
        [
            (
                "functional_pytest",
                [sys.executable, "-m", "pytest", "-q"],
            ),
            (
                "config_compatibility",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/integration/test_config_layering.py",
                    "tests/integration/test_cli_benchmark.py",
                    "tests/integration/test_cli_lsp_options.py",
                    "tests/integration/test_cli_repomap.py",
                    "tests/unit/test_schema.py",
                ],
            ),
        ]
    )
    if runtime_gate_enabled:
        steps_spec.append(
            (
                "runtime_regression",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/integration/test_cli_runtime.py",
                    "tests/unit/test_runtime_hot_reload.py",
                    "tests/unit/test_runtime_scheduler.py",
                ],
            )
        )

    if not args.skip_skill_validation:
        steps_spec.append(
            (
                "skill_validation_matrix",
                [
                    sys.executable,
                    str(root / "scripts" / "run_skill_validation.py"),
                    "--repo-url",
                    str(args.skill_validation_repo_url),
                    "--repo-ref",
                    str(args.skill_validation_repo_ref),
                    "--repo-name",
                    str(args.skill_validation_repo_name),
                    "--repo-dir",
                    str(skill_validation_repo_dir),
                    "--skills-dir",
                    str((root / "skills").resolve()),
                    "--index-cache-path",
                    str(skill_validation_index),
                    "--output-path",
                    str(skill_validation_report),
                    "--languages",
                    "typescript,javascript",
                    "--apps",
                    str(args.skill_validation_apps),
                    "--min-pass-rate",
                    str(float(args.skill_validation_min_pass_rate)),
                    "--fail-on-miss",
                ],
            )
        )

    steps_spec.append(
        (
            "e2e_success_slice",
            [
                sys.executable,
                str(root / "scripts" / "run_e2e_success_slice.py"),
                "--cases",
                str(e2e_cases_path),
                "--output-dir",
                str(e2e_output),
                "--cli-bin",
                str(args.cli_bin),
            ],
        )
    )

    steps_spec.append(
        (
            "benchmark_matrix",
            [
                sys.executable,
                str(root / "scripts" / "run_benchmark_matrix.py"),
                "--matrix-config",
                str(matrix_config_path),
                "--output-dir",
                str(matrix_output),
                "--cli-bin",
                str(args.cli_bin),
            ]
            + (["--fail-on-thresholds"] if args.fail_on_thresholds else []),
        )
    )
    if feature_slices_gate_enabled:
        steps_spec.append(
            (
                "feature_slices_gate",
                [
                    sys.executable,
                    str(root / "scripts" / "run_feature_slice_matrix.py"),
                    "--config",
                    str(feature_slices_config_path),
                    "--output-dir",
                    str(feature_slices_output),
                    "--cli-bin",
                    str(args.cli_bin),
                    "--fail-on-thresholds",
                ],
            )
        )
    if external_concept_gate_enabled:
        steps_spec.append(
            (
                "benchmark_matrix_external_concept",
                [
                    sys.executable,
                    str(root / "scripts" / "run_benchmark_matrix.py"),
                    "--matrix-config",
                    str(external_concept_matrix_config_path),
                    "--output-dir",
                    str(external_concept_output),
                    "--cli-bin",
                    str(args.cli_bin),
                    "--fail-on-thresholds",
                ],
            )
        )
    if concept_gate_enabled:
        concept_cochange_enabled = bool(
            concept_gate_config.get("cochange_enabled", False)
        )
        steps_spec.append(
            (
                "benchmark_concept_gate",
                [
                    str(args.cli_bin),
                    "benchmark",
                    "run",
                    "--cases",
                    str(concept_cases_path),
                    "--repo",
                    str(concept_gate_config.get("repo", "ace-lite-engine")),
                    "--root",
                    str(concept_root_path),
                    "--skills-dir",
                    str(concept_skills_dir),
                    "--top-k-files",
                    str(int(concept_gate_config.get("top_k_files", 6) or 6)),
                    "--min-candidate-score",
                    str(int(concept_gate_config.get("min_candidate_score", 2) or 2)),
                    "--candidate-ranker",
                    str(concept_gate_config.get("candidate_ranker", "heuristic")),
                    "--retrieval-policy",
                    str(concept_gate_config.get("retrieval_policy", "auto")),
                    "--chunk-top-k",
                    str(int(concept_gate_config.get("chunk_top_k", 24) or 24)),
                    "--cochange" if concept_cochange_enabled else "--no-cochange",
                    "--memory-primary",
                    "none",
                    "--memory-secondary",
                    "none",
                    "--no-include-plans",
                    "--no-include-case-details",
                    "--warmup-runs",
                    "1",
                    "--output",
                    str(concept_output),
                ],
            )
        )

    started = perf_counter()
    step_results: list[StepResult] = []

    for name, command in steps_spec:
        print(f"[freeze] running {name}...")
        result = _run_step(name=name, command=command, cwd=root, logs_dir=logs_dir)
        step_results.append(result)
        print(
            f"[freeze] {name} exit={result.returncode} elapsed={result.elapsed_seconds:.3f}s"
        )
        if (
            name == "benchmark_matrix_tabiv3"
            and result.returncode == 0
            and tabiv3_gate_enabled
            and tabiv3_gate_retry_count > 0
        ):
            retry_failures = _evaluate_tabiv3_gate(
                matrix_summary=_load_matrix_summary(
                    summary_path=tabiv3_output / "matrix_summary.json"
                ),
                latency_p95_ms_max=tabiv3_gate_latency_p95_max,
                repomap_latency_p95_ms_max=tabiv3_gate_repomap_latency_p95_max,
            )
            retry_attempt = 0
            while retry_failures and retry_attempt < tabiv3_gate_retry_count:
                retry_attempt += 1
                retry_name = f"{name}_retry_{retry_attempt}"
                print(f"[freeze] retrying {name} (attempt {retry_attempt}/{tabiv3_gate_retry_count})...")
                retry_result = _run_step(
                    name=retry_name, command=command, cwd=root, logs_dir=logs_dir
                )
                step_results.append(retry_result)
                print(
                    f"[freeze] {retry_name} exit={retry_result.returncode} elapsed={retry_result.elapsed_seconds:.3f}s"
                )
                if retry_result.returncode != 0:
                    result = retry_result
                    break
                retry_failures = _evaluate_tabiv3_gate(
                    matrix_summary=_load_matrix_summary(
                        summary_path=tabiv3_output / "matrix_summary.json"
                    ),
                    latency_p95_ms_max=tabiv3_gate_latency_p95_max,
                    repomap_latency_p95_ms_max=tabiv3_gate_repomap_latency_p95_max,
                )
        if (
            name == "benchmark_concept_gate"
            and result.returncode == 0
            and concept_gate_enabled
            and concept_gate_retry_count > 0
        ):
            retry_failures = _evaluate_concept_gate(
                benchmark_summary=_load_benchmark_summary(
                    summary_path=concept_output / "summary.json"
                ),
                concept_gate_config=concept_gate_config,
            )
            retry_attempt = 0
            while retry_failures and retry_attempt < concept_gate_retry_count:
                retry_attempt += 1
                retry_name = f"{name}_retry_{retry_attempt}"
                print(
                    f"[freeze] retrying {name} (attempt {retry_attempt}/{concept_gate_retry_count})..."
                )
                retry_result = _run_step(
                    name=retry_name, command=command, cwd=root, logs_dir=logs_dir
                )
                step_results.append(retry_result)
                print(
                    f"[freeze] {retry_name} exit={retry_result.returncode} elapsed={retry_result.elapsed_seconds:.3f}s"
                )
                if retry_result.returncode != 0:
                    result = retry_result
                    break
                retry_failures = _evaluate_concept_gate(
                    benchmark_summary=_load_benchmark_summary(
                        summary_path=concept_output / "summary.json"
                    ),
                    concept_gate_config=concept_gate_config,
                )
        if result.returncode != 0:
            break

    elapsed = perf_counter() - started
    required_step_names = [item[0] for item in steps_spec]
    required_step_lookup = set(required_step_names)
    executed_required_steps = [
        step.name for step in step_results if step.name in required_step_lookup
    ]
    base_passed = all(step.passed for step in step_results) and executed_required_steps == required_step_names

    matrix_summary = _load_matrix_summary(
        summary_path=matrix_output / "matrix_summary.json"
    )
    tabiv3_summary = _load_matrix_summary(
        summary_path=tabiv3_output / "matrix_summary.json"
    )
    e2e_summary = _load_e2e_success_summary(
        summary_path=e2e_output / "summary.json"
    )
    concept_summary = _load_benchmark_summary(
        summary_path=concept_output / "summary.json"
    )
    validation_rich_summary = (
        _load_benchmark_summary(summary_path=validation_rich_summary_path)
        if validation_rich_summary_path is not None
        else {}
    )
    validation_rich_previous_summary = (
        _load_benchmark_summary(summary_path=validation_rich_previous_summary_path)
        if validation_rich_previous_summary_path is not None
        else {}
    )
    validation_rich_delta = _build_metric_delta(
        current_metrics=(
            validation_rich_summary.get("metrics", {})
            if isinstance(validation_rich_summary.get("metrics"), dict)
            else {}
        ),
        previous_metrics=(
            validation_rich_previous_summary.get("metrics", {})
            if isinstance(validation_rich_previous_summary.get("metrics"), dict)
            else {}
        ),
        metric_names=[
            "task_success_rate",
            "precision_at_k",
            "noise_rate",
            "latency_p95_ms",
            "validation_test_count",
            "evidence_insufficient_rate",
            "missing_validation_rate",
        ],
    )
    external_concept_summary = _load_matrix_summary(
        summary_path=external_concept_output / "matrix_summary.json"
    )
    feature_slices_summary = _load_feature_slices_summary(
        summary_path=feature_slices_output / "feature_slices_summary.json"
    )
    validation_rich_gate_config = _resolve_validation_rich_gate_config(
        matrix_config_path=matrix_config_path
    )
    validation_rich_gate_thresholds_raw = validation_rich_gate_config.get("thresholds")
    validation_rich_gate_thresholds = (
        validation_rich_gate_thresholds_raw
        if isinstance(validation_rich_gate_thresholds_raw, dict)
        else {}
    )
    validation_rich_gate_enabled = bool(
        validation_rich_gate_config.get("enabled", False)
    )
    validation_rich_gate_failures = (
        _evaluate_validation_rich_gate(
            benchmark_summary=validation_rich_summary,
            thresholds={
                key: float(value)
                for key, value in validation_rich_gate_thresholds.items()
            },
        )
        if validation_rich_gate_enabled
        else []
    )
    validation_rich_gate_payload = {
        "enabled": validation_rich_gate_enabled,
        "passed": len(validation_rich_gate_failures) == 0,
        "mode": str(validation_rich_gate_config.get("mode", "disabled") or "disabled"),
        "report_only": bool(validation_rich_gate_config.get("report_only", False)),
        "enforced": bool(validation_rich_gate_config.get("enforced", False)),
        "source": str(validation_rich_gate_config.get("source", "") or "disabled"),
        "summary_path": str(validation_rich_summary_path)
        if validation_rich_summary_path is not None
        else "",
        "thresholds": {
            key: float(value)
            for key, value in validation_rich_gate_thresholds.items()
        },
        "failures": validation_rich_gate_failures,
    }

    plugin_gate_config = _resolve_plugin_gate_config(
        matrix_config_path=matrix_config_path,
        profile=str(args.plugin_gate_profile),
        cli_max_conflicts=int(args.max_plugin_conflicts),
        cli_max_blocked=int(args.max_plugin_blocked),
        cli_max_warn=int(args.max_plugin_warn),
    )
    plugin_gate_thresholds_raw = plugin_gate_config.get("thresholds")
    plugin_gate_thresholds = (
        plugin_gate_thresholds_raw
        if isinstance(plugin_gate_thresholds_raw, dict)
        else {"max_conflicts": -1, "max_blocked": -1, "max_warn": -1}
    )

    plugin_gate_failures = _evaluate_plugin_policy_gate(
        matrix_summary=matrix_summary,
        max_conflicts=_gate_threshold_from_mapping(plugin_gate_thresholds, "max_conflicts"),
        max_blocked=_gate_threshold_from_mapping(plugin_gate_thresholds, "max_blocked"),
        max_warn=_gate_threshold_from_mapping(plugin_gate_thresholds, "max_warn"),
    )
    plugin_gate_enabled = any(
        int(value) >= 0
        for value in (
            plugin_gate_thresholds.get("max_conflicts", -1),
            plugin_gate_thresholds.get("max_blocked", -1),
            plugin_gate_thresholds.get("max_warn", -1),
        )
    )
    plugin_gate_payload = {
        "enabled": plugin_gate_enabled,
        "passed": len(plugin_gate_failures) == 0,
        "profile": str(plugin_gate_config.get("profile", "") or ""),
        "profile_from_config": bool(plugin_gate_config.get("profile_from_config", False)),
        "source": str(plugin_gate_config.get("source", "") or "disabled"),
        "thresholds": {
            "max_conflicts": _gate_threshold_from_mapping(plugin_gate_thresholds, "max_conflicts"),
            "max_blocked": _gate_threshold_from_mapping(plugin_gate_thresholds, "max_blocked"),
            "max_warn": _gate_threshold_from_mapping(plugin_gate_thresholds, "max_warn"),
        },
        "failures": plugin_gate_failures,
    }
    retrieval_policy_guard_config = _resolve_policy_guard_config(
        matrix_config_path=matrix_config_path,
    )
    retrieval_policy_guard_thresholds_raw = retrieval_policy_guard_config.get(
        "thresholds"
    )
    retrieval_policy_guard_thresholds = (
        retrieval_policy_guard_thresholds_raw
        if isinstance(retrieval_policy_guard_thresholds_raw, dict)
        else {
            "max_regressed_repo_rate": -1.0,
            "min_task_success_mean": -1.0,
            "max_retrieval_task_gap_rate_mean": -1.0,
            "max_noise_rate_mean": -1.0,
            "max_latency_p95_ms_mean": -1.0,
            "max_slo_downgrade_case_rate_mean": -1.0,
        }
    )
    retrieval_policy_guard_enabled = bool(
        retrieval_policy_guard_config.get("enabled", False)
    )
    retrieval_policy_guard_mode = str(
        retrieval_policy_guard_config.get("mode", "disabled") or "disabled"
    )
    retrieval_policy_guard_enforced = bool(
        retrieval_policy_guard_config.get("enforced", False)
    )
    retrieval_policy_guard_report_only = bool(
        retrieval_policy_guard_config.get("report_only", False)
    )
    retrieval_policy_guard_failures = _evaluate_retrieval_policy_guard(
        matrix_summary=matrix_summary,
        max_regressed_repo_rate=_metric_threshold_from_mapping(
            retrieval_policy_guard_thresholds, "max_regressed_repo_rate"
        ),
        min_task_success_mean=_metric_threshold_from_mapping(
            retrieval_policy_guard_thresholds, "min_task_success_mean"
        ),
        max_retrieval_task_gap_rate_mean=_metric_threshold_from_mapping(
            retrieval_policy_guard_thresholds,
            "max_retrieval_task_gap_rate_mean",
        ),
        max_noise_rate_mean=_metric_threshold_from_mapping(
            retrieval_policy_guard_thresholds, "max_noise_rate_mean"
        ),
        max_latency_p95_ms_mean=_metric_threshold_from_mapping(
            retrieval_policy_guard_thresholds, "max_latency_p95_ms_mean"
        ),
        max_slo_downgrade_case_rate_mean=_metric_threshold_from_mapping(
            retrieval_policy_guard_thresholds,
            "max_slo_downgrade_case_rate_mean",
        ),
    )
    retrieval_policy_guard_payload = {
        "enabled": retrieval_policy_guard_enabled,
        "passed": len(retrieval_policy_guard_failures) == 0,
        "mode": retrieval_policy_guard_mode,
        "report_only": retrieval_policy_guard_report_only,
        "enforced": retrieval_policy_guard_enforced,
        "source": str(
            retrieval_policy_guard_config.get("source", "") or "disabled"
        ),
        "thresholds": {
            "max_regressed_repo_rate": _metric_threshold_from_mapping(
                retrieval_policy_guard_thresholds,
                "max_regressed_repo_rate",
            ),
            "min_task_success_mean": _metric_threshold_from_mapping(
                retrieval_policy_guard_thresholds,
                "min_task_success_mean",
            ),
            "max_retrieval_task_gap_rate_mean": _metric_threshold_from_mapping(
                retrieval_policy_guard_thresholds,
                "max_retrieval_task_gap_rate_mean",
            ),
            "max_noise_rate_mean": _metric_threshold_from_mapping(
                retrieval_policy_guard_thresholds,
                "max_noise_rate_mean",
            ),
            "max_latency_p95_ms_mean": _metric_threshold_from_mapping(
                retrieval_policy_guard_thresholds,
                "max_latency_p95_ms_mean",
            ),
            "max_slo_downgrade_case_rate_mean": _metric_threshold_from_mapping(
                retrieval_policy_guard_thresholds,
                "max_slo_downgrade_case_rate_mean",
            ),
        },
        "failures": retrieval_policy_guard_failures,
    }
    decision_observability_gate_config = _resolve_decision_observability_gate_config(
        matrix_config_path=matrix_config_path,
    )
    decision_observability_gate_enabled = bool(
        decision_observability_gate_config.get("enabled", False)
    )
    decision_observability_gate_failures: list[dict[str, Any]] = []
    if decision_observability_gate_enabled:
        decision_observability_gate_failures.extend(
            _evaluate_decision_observability_gate(matrix_summary=matrix_summary)
        )
    decision_observability_summary_raw = matrix_summary.get(
        "decision_observability_summary"
    )
    decision_observability_summary = (
        decision_observability_summary_raw
        if isinstance(decision_observability_summary_raw, dict)
        else {}
    )
    decision_observability_gate_payload = {
        "enabled": decision_observability_gate_enabled,
        "passed": len(decision_observability_gate_failures) == 0,
        "mode": str(
            decision_observability_gate_config.get("mode", "disabled") or "disabled"
        ),
        "report_only": bool(
            decision_observability_gate_config.get("report_only", False)
        ),
        "enforced": bool(
            decision_observability_gate_config.get("enforced", False)
        ),
        "source": str(
            decision_observability_gate_config.get("source", "") or "disabled"
        ),
        "summary_path": str(matrix_summary.get("path", "") or ""),
        "summary_present": bool(decision_observability_summary),
        "required_scalar_keys": list(_DECISION_OBSERVABILITY_SCALAR_KEYS),
        "required_mapping_keys": list(_DECISION_OBSERVABILITY_MAPPING_KEYS),
        "summary": (
            dict(decision_observability_summary)
            if decision_observability_summary
            else {}
        ),
        "failures": decision_observability_gate_failures,
    }

    tabiv3_gate_failures: list[dict[str, Any]] = []
    if tabiv3_gate_enabled:
        if not tabiv3_summary:
            tabiv3_gate_failures.append(
                {
                    "repo": "tabiv3",
                    "metric": "matrix_summary",
                    "actual": 0.0,
                    "operator": "==",
                    "expected": 1.0,
                }
            )
        else:
            tabiv3_gate_failures.extend(
                _evaluate_tabiv3_gate(
                    matrix_summary=tabiv3_summary,
                    latency_p95_ms_max=tabiv3_gate_latency_p95_max,
                    repomap_latency_p95_ms_max=tabiv3_gate_repomap_latency_p95_max,
                )
            )
    tabiv3_retry_attempts_executed = sum(
        1
        for step in step_results
        if str(step.name).startswith("benchmark_matrix_tabiv3_retry_")
    )
    tabiv3_gate_payload = {
        "enabled": tabiv3_gate_enabled,
        "passed": len(tabiv3_gate_failures) == 0,
        "source": str(tabiv3_gate_config.get("source", "disabled") or "disabled"),
        "matrix_config": str(tabiv3_matrix_config_path),
        "retry_count": int(tabiv3_gate_retry_count),
        "retry_attempts_executed": int(tabiv3_retry_attempts_executed),
        "repo_count": int(tabiv3_summary.get("repo_count", 0) or 0)
        if tabiv3_summary
        else 0,
        "matrix_summary_passed": bool(tabiv3_summary.get("passed", False))
        if tabiv3_summary
        else False,
        "thresholds": {
            "latency_p95_ms_max": float(tabiv3_gate_latency_p95_max),
            "repomap_latency_p95_ms_max": float(tabiv3_gate_repomap_latency_p95_max),
        },
        "failures": tabiv3_gate_failures,
    }

    concept_gate_thresholds_raw = concept_gate_config.get("thresholds")
    concept_gate_thresholds = (
        concept_gate_thresholds_raw
        if isinstance(concept_gate_thresholds_raw, dict)
        else {}
    )
    concept_gate_metrics = (
        concept_summary.get("metrics", {}) if isinstance(concept_summary, dict) else {}
    )
    concept_gate_failures: list[dict[str, Any]] = []
    if concept_gate_enabled:
        concept_gate_failures.extend(
            _evaluate_concept_gate(
                benchmark_summary=concept_summary,
                concept_gate_config=concept_gate_config,
            )
        )
    concept_retry_attempts_executed = sum(
        1
        for step in step_results
        if str(step.name).startswith("benchmark_concept_gate_retry_")
    )
    concept_gate_payload = {
        "enabled": concept_gate_enabled,
        "passed": len(concept_gate_failures) == 0,
        "source": str(concept_gate_config.get("source", "disabled") or "disabled"),
        "cases": str(concept_cases_path),
        "repo": str(concept_gate_config.get("repo", "ace-lite-engine")),
        "retry_count": int(concept_gate_retry_count),
        "retry_attempts_executed": int(concept_retry_attempts_executed),
        "execution_config": {
            "root": str(concept_root_path),
            "skills_dir": str(concept_skills_dir),
            "top_k_files": int(concept_gate_config.get("top_k_files", 6) or 6),
            "min_candidate_score": int(
                concept_gate_config.get("min_candidate_score", 2) or 2
            ),
            "candidate_ranker": str(
                concept_gate_config.get("candidate_ranker", "heuristic")
            ),
            "retrieval_policy": str(
                concept_gate_config.get("retrieval_policy", "auto")
            ),
            "chunk_top_k": int(concept_gate_config.get("chunk_top_k", 24) or 24),
            "cochange": bool(concept_gate_config.get("cochange_enabled", False)),
        },
        "case_count": int(concept_summary.get("case_count", 0) or 0)
        if concept_summary
        else 0,
        "thresholds": {
            key: float(value) for key, value in concept_gate_thresholds.items()
        },
        "metrics": {
            key: float(value)
            for key, value in concept_gate_metrics.items()
            if isinstance(key, str)
        },
        "failures": concept_gate_failures,
    }
    external_concept_gate_thresholds_raw = external_concept_gate_config.get("thresholds")
    external_concept_gate_thresholds = (
        external_concept_gate_thresholds_raw
        if isinstance(external_concept_gate_thresholds_raw, dict)
        else {}
    )
    external_concept_gate_failures: list[dict[str, Any]] = []
    external_concept_gate_metrics: dict[str, float] = {}
    if external_concept_gate_enabled:
        if not external_concept_summary:
            external_concept_gate_failures.append(
                {
                    "repo": "external_concept_gate",
                    "metric": "matrix_summary",
                    "actual": 0.0,
                    "operator": "==",
                    "expected": 1.0,
                }
            )
        else:
            (
                external_concept_gate_failures,
                external_concept_gate_metrics,
            ) = _evaluate_external_concept_gate(
                matrix_summary=external_concept_summary,
                thresholds={
                    key: float(value)
                    for key, value in external_concept_gate_thresholds.items()
                },
            )
    external_concept_gate_payload = {
        "enabled": external_concept_gate_enabled,
        "passed": len(external_concept_gate_failures) == 0,
        "source": str(
            external_concept_gate_config.get("source", "disabled") or "disabled"
        ),
        "matrix_config": str(external_concept_matrix_config_path),
        "repo_count": int(external_concept_summary.get("repo_count", 0) or 0)
        if external_concept_summary
        else 0,
        "matrix_summary_passed": bool(external_concept_summary.get("passed", False))
        if external_concept_summary
        else False,
        "thresholds": {
            key: float(value)
            for key, value in external_concept_gate_thresholds.items()
        },
        "metrics": {
            key: float(value)
            for key, value in external_concept_gate_metrics.items()
            if isinstance(key, str)
        },
        "failures": external_concept_gate_failures,
    }

    e2e_gate_config = _resolve_e2e_success_gate(
        matrix_config_path=matrix_config_path,
        cli_success_floor=float(args.e2e_success_floor),
    )
    e2e_gate_enabled = bool(e2e_gate_config.get("enabled", False))
    e2e_min_success_rate = float(e2e_gate_config.get("min_success_rate", -1.0) or -1.0)
    e2e_gate_failures = _evaluate_e2e_success_gate(
        matrix_summary=matrix_summary,
        min_success_rate=e2e_min_success_rate,
        e2e_summary=e2e_summary,
    )
    e2e_metric_source = "e2e_success_slice" if e2e_summary else "benchmark_matrix"
    e2e_gate_payload = {
        "enabled": e2e_gate_enabled,
        "passed": len(e2e_gate_failures) == 0,
        "source": str(e2e_gate_config.get("source", "disabled") or "disabled"),
        "source_metric": e2e_metric_source,
        "min_success_rate": e2e_min_success_rate,
        "task_success_rate": (
            float(e2e_summary.get("task_success_rate", 0.0) or 0.0)
            if e2e_summary
            else float(matrix_summary.get("task_success_mean", 0.0) or 0.0)
        ),
        "case_count": int(e2e_summary.get("case_count", 0) or 0) if e2e_summary else 0,
        "passed_count": int(e2e_summary.get("passed_count", 0) or 0) if e2e_summary else 0,
        "failed_count": int(e2e_summary.get("failed_count", 0) or 0) if e2e_summary else 0,
        "failures": e2e_gate_failures,
    }

    memory_gate_config = _resolve_memory_gate_config(
        matrix_config_path=matrix_config_path,
    )
    memory_gate_thresholds_raw = memory_gate_config.get("thresholds")
    memory_gate_thresholds = (
        memory_gate_thresholds_raw
        if isinstance(memory_gate_thresholds_raw, dict)
        else {
            "min_notes_hit_ratio": -1.0,
            "min_profile_selected_mean": -1.0,
            "min_capture_trigger_ratio": -1.0,
        }
    )
    memory_gate_enabled = bool(memory_gate_config.get("enabled", False))
    memory_gate_failures = _evaluate_memory_gate(
        matrix_summary=matrix_summary,
        min_notes_hit_ratio=float(
            memory_gate_thresholds.get("min_notes_hit_ratio", -1.0) or -1.0
        ),
        min_profile_selected_mean=float(
            memory_gate_thresholds.get("min_profile_selected_mean", -1.0) or -1.0
        ),
        min_capture_trigger_ratio=float(
            memory_gate_thresholds.get("min_capture_trigger_ratio", -1.0) or -1.0
        ),
    )
    memory_means_raw = matrix_summary.get("memory_metrics_mean")
    memory_means = memory_means_raw if isinstance(memory_means_raw, dict) else {}
    memory_gate_payload = {
        "enabled": memory_gate_enabled,
        "passed": len(memory_gate_failures) == 0,
        "source": str(memory_gate_config.get("source", "disabled") or "disabled"),
        "thresholds": {
            "min_notes_hit_ratio": float(
                memory_gate_thresholds.get("min_notes_hit_ratio", -1.0) or -1.0
            ),
            "min_profile_selected_mean": float(
                memory_gate_thresholds.get("min_profile_selected_mean", -1.0) or -1.0
            ),
            "min_capture_trigger_ratio": float(
                memory_gate_thresholds.get("min_capture_trigger_ratio", -1.0) or -1.0
            ),
        },
        "means": {
            "notes_hit_ratio": float(memory_means.get("notes_hit_ratio", 0.0) or 0.0),
            "profile_selected_mean": float(
                memory_means.get("profile_selected_mean", 0.0) or 0.0
            ),
            "capture_trigger_ratio": float(
                memory_means.get("capture_trigger_ratio", 0.0) or 0.0
            ),
        },
        "failures": memory_gate_failures,
    }
    embedding_gate_config = _resolve_embedding_gate_config(
        matrix_config_path=matrix_config_path,
    )
    embedding_gate_thresholds_raw = embedding_gate_config.get("thresholds")
    embedding_gate_thresholds = (
        embedding_gate_thresholds_raw
        if isinstance(embedding_gate_thresholds_raw, dict)
        else {
            "min_embedding_enabled_ratio": -1.0,
            "min_embedding_similarity_mean": -1.0,
            "min_embedding_rerank_ratio": -1.0,
            "min_embedding_cache_hit_ratio": -1.0,
            "max_embedding_fallback_ratio": -1.0,
        }
    )
    embedding_gate_enabled = bool(embedding_gate_config.get("enabled", False))
    embedding_gate_failures = _evaluate_embedding_gate(
        matrix_summary=matrix_summary,
        min_embedding_enabled_ratio=float(
            embedding_gate_thresholds.get("min_embedding_enabled_ratio", -1.0)
            or -1.0
        ),
        min_embedding_similarity_mean=float(
            embedding_gate_thresholds.get("min_embedding_similarity_mean", -1.0)
            or -1.0
        ),
        min_embedding_rerank_ratio=float(
            embedding_gate_thresholds.get("min_embedding_rerank_ratio", -1.0)
            or -1.0
        ),
        min_embedding_cache_hit_ratio=float(
            embedding_gate_thresholds.get("min_embedding_cache_hit_ratio", -1.0)
            or -1.0
        ),
        max_embedding_fallback_ratio=float(
            embedding_gate_thresholds.get("max_embedding_fallback_ratio", -1.0)
            or -1.0
        ),
    )
    embedding_means_raw = matrix_summary.get("embedding_metrics_mean")
    embedding_means = (
        embedding_means_raw if isinstance(embedding_means_raw, dict) else {}
    )
    embedding_gate_payload = {
        "enabled": embedding_gate_enabled,
        "passed": len(embedding_gate_failures) == 0,
        "source": str(embedding_gate_config.get("source", "disabled") or "disabled"),
        "thresholds": {
            "min_embedding_enabled_ratio": float(
                embedding_gate_thresholds.get("min_embedding_enabled_ratio", -1.0)
                or -1.0
            ),
            "min_embedding_similarity_mean": float(
                embedding_gate_thresholds.get("min_embedding_similarity_mean", -1.0)
                or -1.0
            ),
            "min_embedding_rerank_ratio": float(
                embedding_gate_thresholds.get("min_embedding_rerank_ratio", -1.0)
                or -1.0
            ),
            "min_embedding_cache_hit_ratio": float(
                embedding_gate_thresholds.get("min_embedding_cache_hit_ratio", -1.0)
                or -1.0
            ),
            "max_embedding_fallback_ratio": float(
                embedding_gate_thresholds.get("max_embedding_fallback_ratio", -1.0)
                or -1.0
            ),
        },
        "means": {
            "embedding_similarity_mean": float(
                embedding_means.get("embedding_similarity_mean", 0.0) or 0.0
            ),
            "embedding_rerank_ratio": float(
                embedding_means.get("embedding_rerank_ratio", 0.0) or 0.0
            ),
            "embedding_cache_hit_ratio": float(
                embedding_means.get("embedding_cache_hit_ratio", 0.0) or 0.0
            ),
            "embedding_fallback_ratio": float(
                embedding_means.get("embedding_fallback_ratio", 0.0) or 0.0
            ),
            "embedding_enabled_ratio": float(
                embedding_means.get("embedding_enabled_ratio", 0.0) or 0.0
            ),
        },
        "failures": embedding_gate_failures,
    }
    runtime_gate_failures: list[dict[str, Any]] = []
    runtime_step = next(
        (step for step in step_results if step.name == "runtime_regression"),
        None,
    )
    if runtime_gate_enabled:
        if runtime_step is None:
            runtime_gate_failures.append(
                {
                    "metric": "runtime_regression_step",
                    "actual": "missing",
                    "operator": "==",
                    "expected": "executed",
                    "reason": "step_not_executed",
                }
            )
        elif not runtime_step.passed:
            runtime_gate_failures.append(
                {
                    "metric": "runtime_regression_step",
                    "actual": int(runtime_step.returncode),
                    "operator": "==",
                    "expected": 0,
                    "reason": "step_failed",
                }
            )
    runtime_gate_payload = {
        "enabled": runtime_gate_enabled,
        "passed": len(runtime_gate_failures) == 0,
        "source": str(runtime_gate_config.get("source", "disabled") or "disabled"),
        "step": "runtime_regression",
        "failures": runtime_gate_failures,
    }

    feature_slices_gate_failures: list[dict[str, Any]] = []
    feature_slices_step = next(
        (step for step in step_results if step.name == "feature_slices_gate"),
        None,
    )
    if feature_slices_gate_enabled:
        if feature_slices_step is None:
            feature_slices_gate_failures.append(
                {
                    "repo": "feature_slices_gate",
                    "metric": "feature_slices_step",
                    "actual": "missing",
                    "operator": "==",
                    "expected": "executed",
                    "reason": "step_not_executed",
                }
            )
        elif not feature_slices_step.passed:
            feature_slices_gate_failures.append(
                {
                    "repo": "feature_slices_gate",
                    "metric": "feature_slices_step",
                    "actual": int(feature_slices_step.returncode),
                    "operator": "==",
                    "expected": 0,
                    "reason": "step_failed",
                }
            )
        else:
            feature_slices_gate_failures.extend(
                _evaluate_feature_slices_gate(summary=feature_slices_summary)
            )

    feature_slices_gate_payload = {
        "enabled": feature_slices_gate_enabled,
        "passed": len(feature_slices_gate_failures) == 0,
        "source": str(
            feature_slices_gate_config.get("source", "disabled") or "disabled"
        ),
        "config": str(feature_slices_config_path),
        "summary_path": str(feature_slices_output / "feature_slices_summary.json"),
        "summary_passed": bool(feature_slices_summary.get("passed", False))
        if feature_slices_summary
        else False,
        "slice_count": len(feature_slices_summary.get("slices", []))
        if isinstance(feature_slices_summary.get("slices"), list)
        else 0,
        "failures": feature_slices_gate_failures,
    }

    passed = (
        base_passed
        and (not tabiv3_gate_enabled or len(tabiv3_gate_failures) == 0)
        and (not concept_gate_enabled or len(concept_gate_failures) == 0)
        and (
            not external_concept_gate_enabled
            or len(external_concept_gate_failures) == 0
        )
        and (
            not feature_slices_gate_enabled
            or len(feature_slices_gate_failures) == 0
        )
        and (not runtime_gate_enabled or len(runtime_gate_failures) == 0)
        and (not plugin_gate_enabled or len(plugin_gate_failures) == 0)
        and (
            not _policy_guard_blocks_release(
                config=validation_rich_gate_config,
                failures=validation_rich_gate_failures,
            )
        )
        and (
            not _policy_guard_blocks_release(
                config=retrieval_policy_guard_config,
                failures=retrieval_policy_guard_failures,
            )
        )
        and (
            not _policy_guard_blocks_release(
                config=decision_observability_gate_config,
                failures=decision_observability_gate_failures,
            )
        )
        and (not e2e_gate_enabled or len(e2e_gate_failures) == 0)
        and (not memory_gate_enabled or len(memory_gate_failures) == 0)
        and (not embedding_gate_enabled or len(embedding_gate_failures) == 0)
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "passed": passed,
        "elapsed_seconds": round(elapsed, 3),
        "steps": [
            {
                "name": step.name,
                "passed": step.passed,
                "returncode": step.returncode,
                "elapsed_seconds": step.elapsed_seconds,
                "command": step.command,
                "command_line": " ".join(shlex.quote(item) for item in step.command),
                "stdout_path": step.stdout_path,
                "stderr_path": step.stderr_path,
            }
            for step in step_results
        ],
        "benchmark_matrix_summary": matrix_summary,
        "tabiv3_matrix_summary": tabiv3_summary,
        "concept_benchmark_summary": concept_summary,
        "validation_rich_benchmark": {
            "enabled": validation_rich_summary_path is not None,
            "report_only": True,
            "summary_path": str(validation_rich_summary_path)
            if validation_rich_summary_path is not None
            else "",
            "previous_summary_path": str(validation_rich_previous_summary_path)
            if validation_rich_previous_summary_path is not None
            else "",
            "loaded": bool(validation_rich_summary),
            "previous_loaded": bool(validation_rich_previous_summary),
            "repo": str(validation_rich_summary.get("repo", "") or ""),
            "case_count": int(validation_rich_summary.get("case_count", 0) or 0)
            if validation_rich_summary
            else 0,
            "regressed": bool(validation_rich_summary.get("regressed", False))
            if validation_rich_summary
            else False,
            "previous_repo": str(validation_rich_previous_summary.get("repo", "") or ""),
            "previous_case_count": int(
                validation_rich_previous_summary.get("case_count", 0) or 0
            )
            if validation_rich_previous_summary
            else 0,
            "previous_regressed": bool(
                validation_rich_previous_summary.get("regressed", False)
            )
            if validation_rich_previous_summary
            else False,
            "failed_checks": (
                validation_rich_summary.get("failed_checks", [])
                if isinstance(validation_rich_summary.get("failed_checks"), list)
                else []
            ),
            "previous_failed_checks": (
                validation_rich_previous_summary.get("failed_checks", [])
                if isinstance(validation_rich_previous_summary.get("failed_checks"), list)
                else []
            ),
            "metrics": (
                validation_rich_summary.get("metrics", {})
                if isinstance(validation_rich_summary.get("metrics"), dict)
                else {}
            ),
            "retrieval_control_plane_gate_summary": (
                validation_rich_summary.get("retrieval_control_plane_gate_summary", {})
                if isinstance(
                    validation_rich_summary.get(
                        "retrieval_control_plane_gate_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "retrieval_frontier_gate_summary": (
                validation_rich_summary.get("retrieval_frontier_gate_summary", {})
                if isinstance(
                    validation_rich_summary.get("retrieval_frontier_gate_summary", {}),
                    dict,
                )
                else {}
            ),
            "deep_symbol_summary": (
                validation_rich_summary.get("deep_symbol_summary", {})
                if isinstance(validation_rich_summary.get("deep_symbol_summary", {}), dict)
                else {}
            ),
            "native_scip_summary": (
                validation_rich_summary.get("native_scip_summary", {})
                if isinstance(validation_rich_summary.get("native_scip_summary", {}), dict)
                else {}
            ),
            "validation_probe_summary": (
                validation_rich_summary.get("validation_probe_summary", {})
                if isinstance(
                    validation_rich_summary.get("validation_probe_summary", {}), dict
                )
                else {}
            ),
            "source_plan_validation_feedback_summary": (
                validation_rich_summary.get(
                    "source_plan_validation_feedback_summary", {}
                )
                if isinstance(
                    validation_rich_summary.get(
                        "source_plan_validation_feedback_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "source_plan_failure_signal_summary": (
                validation_rich_summary.get("source_plan_failure_signal_summary", {})
                if isinstance(
                    validation_rich_summary.get(
                        "source_plan_failure_signal_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "previous_metrics": (
                validation_rich_previous_summary.get("metrics", {})
                if isinstance(validation_rich_previous_summary.get("metrics"), dict)
                else {}
            ),
            "previous_retrieval_control_plane_gate_summary": (
                validation_rich_previous_summary.get(
                    "retrieval_control_plane_gate_summary", {}
                )
                if isinstance(
                    validation_rich_previous_summary.get(
                        "retrieval_control_plane_gate_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "previous_retrieval_frontier_gate_summary": (
                validation_rich_previous_summary.get(
                    "retrieval_frontier_gate_summary", {}
                )
                if isinstance(
                    validation_rich_previous_summary.get(
                        "retrieval_frontier_gate_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "previous_deep_symbol_summary": (
                validation_rich_previous_summary.get("deep_symbol_summary", {})
                if isinstance(
                    validation_rich_previous_summary.get("deep_symbol_summary", {}),
                    dict,
                )
                else {}
            ),
            "previous_native_scip_summary": (
                validation_rich_previous_summary.get("native_scip_summary", {})
                if isinstance(
                    validation_rich_previous_summary.get("native_scip_summary", {}),
                    dict,
                )
                else {}
            ),
            "previous_validation_probe_summary": (
                validation_rich_previous_summary.get("validation_probe_summary", {})
                if isinstance(
                    validation_rich_previous_summary.get(
                        "validation_probe_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "previous_source_plan_validation_feedback_summary": (
                validation_rich_previous_summary.get(
                    "source_plan_validation_feedback_summary", {}
                )
                if isinstance(
                    validation_rich_previous_summary.get(
                        "source_plan_validation_feedback_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "previous_source_plan_failure_signal_summary": (
                validation_rich_previous_summary.get(
                    "source_plan_failure_signal_summary", {}
                )
                if isinstance(
                    validation_rich_previous_summary.get(
                        "source_plan_failure_signal_summary", {}
                    ),
                    dict,
                )
                else {}
            ),
            "delta": validation_rich_delta,
        },
        "decision_observability_gate": decision_observability_gate_payload,
        "validation_rich_gate": validation_rich_gate_payload,
        "external_concept_matrix_summary": external_concept_summary,
        "feature_slices_summary": feature_slices_summary,
        "e2e_success_summary": e2e_summary,
        "tabiv3_gate": tabiv3_gate_payload,
        "concept_gate": concept_gate_payload,
        "external_concept_gate": external_concept_gate_payload,
        "feature_slices_gate": feature_slices_gate_payload,
        "plugin_policy_gate": plugin_gate_payload,
        "retrieval_policy_guard": retrieval_policy_guard_payload,
        "e2e_success_gate": e2e_gate_payload,
        "runtime_gate": runtime_gate_payload,
        "memory_gate": memory_gate_payload,
        "embedding_gate": embedding_gate_payload,
    }

    report_json = output_dir / "freeze_regression.json"
    report_md = output_dir / "freeze_regression.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_render_markdown(payload=payload), encoding="utf-8")

    print(f"[freeze] report json: {report_json}")
    print(f"[freeze] report md:   {report_md}")

    if matrix_summary:
        print(
            "[freeze] matrix summary: passed={passed} regressed={regressed} repos={count}".format(
                passed=bool(matrix_summary.get("passed", False)),
                regressed=bool(
                    matrix_summary.get("benchmark_regression_detected", False)
                ),
                count=int(matrix_summary.get("repo_count", 0) or 0),
            )
        )

    if validation_rich_summary_path is not None:
        print(
            "[freeze] validation-rich benchmark: summary={summary} previous={previous} loaded={loaded} previous_loaded={previous_loaded} regressed={regressed} task_success={task_success:.4f} validation_tests={validation_tests:.4f} precision_delta={precision_delta:+.4f}".format(
                summary=str(validation_rich_summary_path),
                previous=(
                    str(validation_rich_previous_summary_path)
                    if validation_rich_previous_summary_path is not None
                    else ""
                ),
                loaded=bool(validation_rich_summary),
                previous_loaded=bool(validation_rich_previous_summary),
                regressed=bool(validation_rich_summary.get("regressed", False))
                if validation_rich_summary
                else False,
                task_success=float(
                    (
                        validation_rich_summary.get("metrics", {})
                        if isinstance(validation_rich_summary.get("metrics", {}), dict)
                        else {}
                    ).get("task_success_rate", 0.0)
                    or 0.0
                ),
                validation_tests=float(
                    (
                        validation_rich_summary.get("metrics", {})
                        if isinstance(validation_rich_summary.get("metrics", {}), dict)
                        else {}
                    ).get("validation_test_count", 0.0)
                    or 0.0
                ),
                precision_delta=float(
                    (
                        validation_rich_delta.get("precision_at_k", {})
                        if isinstance(validation_rich_delta.get("precision_at_k", {}), dict)
                        else {}
                    ).get("delta", 0.0)
                    or 0.0
                ),
            )
        )
    if validation_rich_gate_enabled:
        print(
            "[freeze] validation-rich gate: mode={mode} source={source} enforced={enforced} passed={passed} failures={count}".format(
                mode=str(validation_rich_gate_payload.get("mode", "disabled") or "disabled"),
                source=str(validation_rich_gate_payload.get("source", "") or "disabled"),
                enforced=bool(validation_rich_gate_payload.get("enforced", False)),
                passed=len(validation_rich_gate_failures) == 0,
                count=len(validation_rich_gate_failures),
            )
        )
    if decision_observability_gate_enabled:
        print(
            "[freeze] decision-observability gate: mode={mode} source={source} enforced={enforced} present={present} passed={passed} failures={count}".format(
                mode=str(
                    decision_observability_gate_payload.get("mode", "disabled")
                    or "disabled"
                ),
                source=str(
                    decision_observability_gate_payload.get("source", "")
                    or "disabled"
                ),
                enforced=bool(
                    decision_observability_gate_payload.get("enforced", False)
                ),
                present=bool(
                    decision_observability_gate_payload.get("summary_present", False)
                ),
                passed=len(decision_observability_gate_failures) == 0,
                count=len(decision_observability_gate_failures),
            )
        )

    if tabiv3_gate_enabled:
        print(
            "[freeze] tabiv3 gate: matrix={matrix} passed={passed} failures={count} latency<=({latency:.2f}, repomap<={repomap:.2f})".format(
                matrix=str(tabiv3_gate_payload.get("matrix_config", "")),
                passed=len(tabiv3_gate_failures) == 0,
                count=len(tabiv3_gate_failures),
                latency=float(
                    tabiv3_gate_payload.get("thresholds", {}).get(
                        "latency_p95_ms_max", 0.0
                    )
                    or 0.0
                ),
                repomap=float(
                    tabiv3_gate_payload.get("thresholds", {}).get(
                        "repomap_latency_p95_ms_max", 0.0
                    )
                    or 0.0
                ),
            )
        )

    if concept_gate_enabled:
        print(
            "[freeze] concept gate: cases={cases} passed={passed} failures={count} precision={precision:.4f} noise={noise:.4f} latency={latency:.2f}".format(
                cases=str(concept_gate_payload.get("cases", "")),
                passed=len(concept_gate_failures) == 0,
                count=len(concept_gate_failures),
                precision=float(
                    concept_gate_payload.get("metrics", {}).get("precision_at_k", 0.0)
                    or 0.0
                ),
                noise=float(
                    concept_gate_payload.get("metrics", {}).get("noise_rate", 0.0)
                    or 0.0
                ),
                latency=float(
                    concept_gate_payload.get("metrics", {}).get("latency_p95_ms", 0.0)
                    or 0.0
                ),
            )
        )
    if external_concept_gate_enabled:
        print(
            "[freeze] external concept gate: matrix={matrix} passed={passed} failures={count} precision={precision:.4f} noise={noise:.4f} latency={latency:.2f}".format(
                matrix=str(external_concept_gate_payload.get("matrix_config", "")),
                passed=len(external_concept_gate_failures) == 0,
                count=len(external_concept_gate_failures),
                precision=float(
                    external_concept_gate_payload.get("metrics", {}).get(
                        "precision_at_k", 0.0
                    )
                    or 0.0
                ),
                noise=float(
                    external_concept_gate_payload.get("metrics", {}).get(
                        "noise_rate", 0.0
                    )
                    or 0.0
                ),
                latency=float(
                    external_concept_gate_payload.get("metrics", {}).get(
                        "latency_p95_ms", 0.0
                    )
                    or 0.0
                ),
            )
        )

    if feature_slices_gate_enabled:
        print(
            "[freeze] feature slices gate: config={config} passed={passed} failures={count} summary_passed={summary_passed} slices={slice_count}".format(
                config=str(feature_slices_gate_payload.get("config", "")),
                passed=len(feature_slices_gate_failures) == 0,
                count=len(feature_slices_gate_failures),
                summary_passed=bool(feature_slices_gate_payload.get("summary_passed", False)),
                slice_count=int(feature_slices_gate_payload.get("slice_count", 0) or 0),
            )
        )

    if plugin_gate_enabled:
        print(
            "[freeze] plugin gate: profile={profile} source={source} passed={passed} failures={count}".format(
                profile=str(plugin_gate_payload.get("profile", "") or "(none)"),
                source=str(plugin_gate_payload.get("source", "") or "disabled"),
                passed=len(plugin_gate_failures) == 0,
                count=len(plugin_gate_failures),
            )
        )

    if retrieval_policy_guard_enabled:
        print(
            "[freeze] retrieval policy guard: mode={mode} source={source} enforced={enforced} passed={passed} failures={count}".format(
                mode=str(
                    retrieval_policy_guard_payload.get("mode", "disabled")
                    or "disabled"
                ),
                source=str(
                    retrieval_policy_guard_payload.get("source", "") or "disabled"
                ),
                enforced=bool(
                    retrieval_policy_guard_payload.get("enforced", False)
                ),
                passed=len(retrieval_policy_guard_failures) == 0,
                count=len(retrieval_policy_guard_failures),
            )
        )

    if e2e_gate_enabled:
        print(
            "[freeze] e2e gate: source={source} metric_source={metric_source} min_success_rate={floor:.4f} actual={actual:.4f} passed={passed} failures={count}".format(
                source=str(e2e_gate_payload.get("source", "") or "disabled"),
                metric_source=str(e2e_gate_payload.get("source_metric", "") or "benchmark_matrix"),
                floor=float(e2e_gate_payload.get("min_success_rate", 0.0) or 0.0),
                actual=float(e2e_gate_payload.get("task_success_rate", 0.0) or 0.0),
                passed=len(e2e_gate_failures) == 0,
                count=len(e2e_gate_failures),
            )
        )

    if runtime_gate_enabled:
        print(
            "[freeze] runtime gate: source={source} step={step} passed={passed} failures={count}".format(
                source=str(runtime_gate_payload.get("source", "") or "disabled"),
                step=str(runtime_gate_payload.get("step", "runtime_regression")),
                passed=len(runtime_gate_failures) == 0,
                count=len(runtime_gate_failures),
            )
        )

    if memory_gate_enabled:
        print(
            "[freeze] memory gate: source={source} passed={passed} failures={count} notes_hit={notes:.4f} profile_selected={profile:.4f} capture_trigger={capture:.4f}".format(
                source=str(memory_gate_payload.get("source", "") or "disabled"),
                passed=len(memory_gate_failures) == 0,
                count=len(memory_gate_failures),
                notes=float(
                    memory_gate_payload.get("means", {}).get("notes_hit_ratio", 0.0)
                    or 0.0
                ),
                profile=float(
                    memory_gate_payload.get("means", {}).get(
                        "profile_selected_mean", 0.0
                    )
                    or 0.0
                ),
                capture=float(
                    memory_gate_payload.get("means", {}).get(
                        "capture_trigger_ratio", 0.0
                    )
                    or 0.0
                ),
            )
        )
    if embedding_gate_enabled:
        print(
            "[freeze] embedding gate: source={source} passed={passed} failures={count} enabled_ratio={enabled_ratio:.4f} similarity={similarity:.4f} rerank={rerank:.4f} cache_hit={cache_hit:.4f} fallback={fallback:.4f}".format(
                source=str(embedding_gate_payload.get("source", "") or "disabled"),
                passed=len(embedding_gate_failures) == 0,
                count=len(embedding_gate_failures),
                enabled_ratio=float(
                    embedding_gate_payload.get("means", {}).get(
                        "embedding_enabled_ratio", 0.0
                    )
                    or 0.0
                ),
                similarity=float(
                    embedding_gate_payload.get("means", {}).get(
                        "embedding_similarity_mean", 0.0
                    )
                    or 0.0
                ),
                rerank=float(
                    embedding_gate_payload.get("means", {}).get(
                        "embedding_rerank_ratio", 0.0
                    )
                    or 0.0
                ),
                cache_hit=float(
                    embedding_gate_payload.get("means", {}).get(
                        "embedding_cache_hit_ratio", 0.0
                    )
                    or 0.0
                ),
                fallback=float(
                    embedding_gate_payload.get("means", {}).get(
                        "embedding_fallback_ratio", 0.0
                    )
                    or 0.0
                ),
            )
        )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
