from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

import yaml

RETRYABLE_GIT_NETWORK_ERROR_FRAGMENTS = (
    "schannel: failed to receive handshake",
    "ssl/tls connection failed",
    "gnutls recv error",
    "connection reset by peer",
    "the remote end hung up unexpectedly",
    "failed to connect",
    "operation timed out",
    "tlsv1 alert",
)

REPO_SIZE_BUCKET_THRESHOLDS = (
    ("repo_size_small", 128),
    ("repo_size_medium", 1024),
)

SLO_HARD_BUDGET_FEATURES = (
    (
        "parallel_time_budget_ms_mean",
        "parallel worktree/docs budget",
        "Hard cap for parallel document and worktree fan-out before the run must degrade.",
    ),
    (
        "embedding_time_budget_ms_mean",
        "embedding rerank budget",
        "Hard cap for semantic rerank latency before embedding-heavy paths must fail open.",
    ),
    (
        "chunk_semantic_time_budget_ms_mean",
        "chunk semantic rerank budget",
        "Hard cap for chunk-level semantic rerank before chunk packing must degrade.",
    ),
    (
        "xref_time_budget_ms_mean",
        "xref lookup budget",
        "Hard cap for graph and cross-reference expansion before xref work must be curtailed.",
    ),
)

SLO_DYNAMIC_DOWNGRADE_FEATURES = (
    (
        "parallel_docs_timeout_ratio",
        "parallel docs timeout",
        "Dynamic downgrade when parallel docs fan-out times out.",
    ),
    (
        "parallel_worktree_timeout_ratio",
        "parallel worktree timeout",
        "Dynamic downgrade when worktree fan-out times out.",
    ),
    (
        "embedding_time_budget_exceeded_ratio",
        "embedding budget exceeded",
        "Dynamic downgrade when semantic rerank exceeds its time budget.",
    ),
    (
        "embedding_adaptive_budget_ratio",
        "embedding adaptive budget",
        "Dynamic downgrade when embedding budget shrinks itself to stay local-first.",
    ),
    (
        "embedding_fallback_ratio",
        "embedding fail-open fallback",
        "Dynamic downgrade when embedding rerank falls back to the lexical path.",
    ),
    (
        "chunk_semantic_time_budget_exceeded_ratio",
        "chunk semantic budget exceeded",
        "Dynamic downgrade when chunk semantic rerank exceeds its time budget.",
    ),
    (
        "chunk_semantic_fallback_ratio",
        "chunk semantic fallback",
        "Dynamic downgrade when chunk semantic rerank falls back to lexical packing.",
    ),
    (
        "xref_budget_exhausted_ratio",
        "xref budget exhausted",
        "Dynamic downgrade when graph or cross-reference expansion is cut short.",
    ),
    (
        "slo_downgrade_case_rate",
        "case-level downgrade aggregate",
        "Aggregate rate of cases that hit at least one downgrade path.",
    ),
)


@dataclass
class CommandResult:
    cmd: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str


def _run_command(*, cmd: list[str], cwd: Path | None = None) -> CommandResult:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        cmd=cmd,
        cwd=str(cwd) if cwd else None,
        returncode=int(completed.returncode),
        stdout=str(completed.stdout or ""),
        stderr=str(completed.stderr or ""),
    )


def _require_success(result: CommandResult, *, label: str) -> None:
    if result.returncode == 0:
        return
    details = [
        f"{label} failed with exit code {result.returncode}",
        f"cmd: {' '.join(result.cmd)}",
    ]
    if result.cwd:
        details.append(f"cwd: {result.cwd}")
    if result.stdout.strip():
        details.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        details.append(f"stderr:\n{result.stderr.strip()}")
    raise RuntimeError("\n".join(details))


def _is_retryable_git_network_error(result: CommandResult) -> bool:
    if result.returncode == 0:
        return False

    combined = f"{result.stdout}\n{result.stderr}".lower()
    return any(
        fragment in combined for fragment in RETRYABLE_GIT_NETWORK_ERROR_FRAGMENTS
    )


def _run_checkout_command_with_retry(
    *,
    cmd: list[str],
    label: str,
    cwd: Path | None = None,
    attempts: int = 3,
    retry_delay_seconds: float = 1.0,
) -> CommandResult:
    last_result: CommandResult | None = None

    for attempt in range(1, max(1, attempts) + 1):
        result = _run_command(cmd=cmd, cwd=cwd)
        last_result = result
        if result.returncode == 0:
            return result
        if attempt >= attempts or not _is_retryable_git_network_error(result):
            _require_success(result, label=label)
        print(
            f"[matrix] transient git error during {label}; retrying "
            f"({attempt}/{attempts})...",
            file=sys.stderr,
        )
        sleep(retry_delay_seconds)

    assert last_result is not None
    return last_result


def _normalize_submodule_paths(raw: Any) -> tuple[str, ...]:
    if raw is True:
        return ()

    if isinstance(raw, str):
        candidate = str(raw).strip()
        return (candidate,) if candidate else ()

    if not isinstance(raw, list):
        return ()

    paths: list[str] = []
    for item in raw:
        candidate = str(item or "").strip()
        if candidate and candidate not in paths:
            paths.append(candidate)
    return tuple(paths)


def _load_index_file_count(*, index_path: Path) -> int:
    if not index_path.exists() or not index_path.is_file():
        return 0
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        value = int(payload.get("file_count", 0) or 0)
    except Exception:
        return 0
    return max(0, value)


def _classify_repo_size_bucket(*, file_count: int) -> str:
    normalized = max(0, int(file_count))
    if normalized <= 0:
        return "repo_size_unknown"
    for bucket_name, max_file_count in REPO_SIZE_BUCKET_THRESHOLDS:
        if normalized <= int(max_file_count):
            return bucket_name
    return "repo_size_large"


def _resolve_workload_bucket(
    *,
    repo_spec: dict[str, Any],
    file_count: int,
    retrieval_policy: str,
) -> str:
    explicit = str(repo_spec.get("workload_bucket") or "").strip().lower()
    if explicit:
        return explicit
    repo_size_bucket = _classify_repo_size_bucket(file_count=file_count)
    if repo_size_bucket != "repo_size_unknown":
        return repo_size_bucket
    policy = str(retrieval_policy or "auto").strip().lower() or "auto"
    return f"policy_{policy}"


def _sync_checkout_submodules(*, repo_name: str, target: Path, spec: dict[str, Any]) -> dict[str, Any]:
    raw = spec.get("submodules")
    enabled = bool(raw)
    if not enabled:
        return {
            "enabled": False,
            "paths": [],
        }

    paths = list(_normalize_submodule_paths(raw))
    sync_cmd = ["git", "-C", str(target), "submodule", "sync", "--recursive"]
    _run_checkout_command_with_retry(
        cmd=sync_cmd,
        label=f"submodule sync {repo_name}",
    )

    update_cmd = [
        "git",
        "-C",
        str(target),
        "submodule",
        "update",
        "--init",
        "--depth",
        "1",
        "--recursive",
    ]
    if paths:
        update_cmd.extend(["--", *paths])
    _run_checkout_command_with_retry(
        cmd=update_cmd,
        label=f"submodule update {repo_name}",
    )

    return {
        "enabled": True,
        "paths": paths,
    }


def _coerce_thresholds(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    thresholds: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            thresholds[name] = float(value)
        except Exception:
            continue
    return thresholds


def _evaluate_thresholds(*, metrics: dict[str, Any], thresholds: dict[str, float]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []

    for key, expected in thresholds.items():
        if key.endswith("_min"):
            metric = key[:-4]
            current = float(metrics.get(metric, 0.0) or 0.0)
            if current < expected:
                failures.append(
                    {
                        "metric": metric,
                        "operator": ">=",
                        "expected": expected,
                        "actual": current,
                    }
                )
            continue

        if key.endswith("_max"):
            metric = key[:-4]
            current = float(metrics.get(metric, 0.0) or 0.0)
            if current > expected:
                failures.append(
                    {
                        "metric": metric,
                        "operator": "<=",
                        "expected": expected,
                        "actual": current,
                    }
                )

    return failures


def _resolve_cases_path(*, project_root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def _resolve_skills_path(*, project_root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def _load_summary_payload(*, summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists() or not summary_path.is_file():
        return {}

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return payload if isinstance(payload, dict) else {}


def _extract_failed_check_names(summary: dict[str, Any]) -> list[str]:
    raw = summary.get("failed_checks")
    if not isinstance(raw, list):
        return []

    output: list[str] = []
    for item in raw:
        name = str(item).strip()
        if name:
            output.append(name)
    return output


def _extract_retrieval_policy(
    *,
    summary: dict[str, Any],
    repo_spec: dict[str, Any],
    defaults: dict[str, Any],
) -> str:
    raw = summary.get("retrieval_policy")
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized:
            return normalized

    fallback = str(
        repo_spec.get("retrieval_policy", defaults.get("retrieval_policy", "auto"))
        or "auto"
    )
    normalized_fallback = fallback.strip().lower()
    return normalized_fallback if normalized_fallback else "auto"


def _extract_plugin_policy_summary(results_payload: dict[str, Any]) -> dict[str, Any]:
    raw = results_payload.get("plugin_policy_summary")
    if not isinstance(raw, dict):
        return {}

    totals_raw = raw.get("totals")
    totals = totals_raw if isinstance(totals_raw, dict) else {}

    compact_totals: dict[str, int] = {}
    for key in ("applied", "conflicts", "blocked", "warn", "remote_applied"):
        compact_totals[key] = max(0, int(totals.get(key, 0) or 0))

    mode = str(raw.get("mode") or "").strip().lower()
    return {
        "mode": mode if mode else "(none)",
        "totals": compact_totals,
    }


def _task_success_rate_from_metrics(metrics: dict[str, Any]) -> float:
    return max(
        0.0,
        float(metrics.get("task_success_rate", metrics.get("utility_rate", 0.0)) or 0.0),
    )


def _extract_task_success_summary(
    *,
    summary: dict[str, Any],
    results_payload: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    raw = summary.get("task_success_summary")
    if not isinstance(raw, dict):
        raw = results_payload.get("task_success_summary")
    task_success = raw if isinstance(raw, dict) else {}

    case_count = max(0, int(task_success.get("case_count", 0) or 0))
    negative_control_case_count = max(
        0, int(task_success.get("negative_control_case_count", 0) or 0)
    )
    positive_case_count = max(
        0,
        int(
            task_success.get(
                "positive_case_count",
                max(0, case_count - negative_control_case_count),
            )
            or 0
        ),
    )
    retrieval_task_gap_count = max(
        0, int(task_success.get("retrieval_task_gap_count", 0) or 0)
    )
    retrieval_task_gap_rate = float(
        task_success.get(
            "retrieval_task_gap_rate",
            (
                float(retrieval_task_gap_count) / float(case_count)
                if case_count > 0
                else 0.0
            ),
        )
        or 0.0
    )

    return {
        "case_count": case_count,
        "positive_case_count": positive_case_count,
        "negative_control_case_count": negative_control_case_count,
        "task_success_rate": float(
            task_success.get("task_success_rate", _task_success_rate_from_metrics(metrics))
            or 0.0
        ),
        "positive_task_success_rate": float(
            task_success.get(
                "positive_task_success_rate",
                _task_success_rate_from_metrics(metrics) if positive_case_count > 0 else 0.0,
            )
            or 0.0
        ),
        "negative_control_task_success_rate": float(
            task_success.get("negative_control_task_success_rate", 0.0) or 0.0
        ),
        "retrieval_task_gap_count": retrieval_task_gap_count,
        "retrieval_task_gap_rate": retrieval_task_gap_rate,
    }


def _build_retrieval_policy_summary(*, repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, float | int]] = {}

    for item in repos:
        policy = str(item.get("retrieval_policy") or "auto").strip().lower() or "auto"
        bucket = buckets.setdefault(
            policy,
            {
                "repo_count": 0,
                "regressed_repo_count": 0,
                "task_success_total": 0.0,
                "positive_task_success_total": 0.0,
                "retrieval_task_gap_rate_total": 0.0,
                "precision_total": 0.0,
                "noise_total": 0.0,
                "latency_total": 0.0,
                "repomap_latency_total": 0.0,
                "slo_downgrade_total": 0.0,
            },
        )
        bucket["repo_count"] += 1

        regressed = bool(item.get("benchmark_regressed", False))
        failed = item.get("benchmark_failed_checks")
        has_failed_checks = isinstance(failed, list) and any(
            str(entry).strip() for entry in failed
        )
        if regressed or has_failed_checks:
            bucket["regressed_repo_count"] += 1

        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        task_success_summary_raw = item.get("task_success_summary")
        task_success_summary = (
            task_success_summary_raw if isinstance(task_success_summary_raw, dict) else {}
        )
        slo_budget_summary_raw = item.get("slo_budget_summary")
        slo_budget_summary = (
            slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
        )

        task_success = float(
            task_success_summary.get(
                "task_success_rate",
                _task_success_rate_from_metrics(metrics),
            )
            or 0.0
        )
        positive_task_success = float(
            task_success_summary.get("positive_task_success_rate", task_success) or 0.0
        )
        bucket["task_success_total"] += task_success
        bucket["positive_task_success_total"] += positive_task_success
        bucket["retrieval_task_gap_rate_total"] += float(
            task_success_summary.get("retrieval_task_gap_rate", 0.0) or 0.0
        )
        bucket["precision_total"] += float(metrics.get("precision_at_k", 0.0) or 0.0)
        bucket["noise_total"] += float(metrics.get("noise_rate", 0.0) or 0.0)
        bucket["latency_total"] += float(metrics.get("latency_p95_ms", 0.0) or 0.0)
        bucket["repomap_latency_total"] += float(
            metrics.get("repomap_latency_p95_ms", 0.0) or 0.0
        )
        bucket["slo_downgrade_total"] += float(
            slo_budget_summary.get("downgrade_case_rate", 0.0) or 0.0
        )

    rows: list[dict[str, Any]] = []
    for policy in sorted(buckets):
        bucket = buckets[policy]
        repo_count = max(1, int(bucket.get("repo_count", 0) or 0))
        regressed_repo_count = max(0, int(bucket.get("regressed_repo_count", 0) or 0))
        rows.append(
            {
                "retrieval_policy": policy,
                "repo_count": repo_count,
                "regressed_repo_count": regressed_repo_count,
                "regressed_repo_rate": float(regressed_repo_count) / float(repo_count),
                "task_success_mean": float(bucket.get("task_success_total", 0.0) or 0.0)
                / float(repo_count),
                "positive_task_success_mean": float(
                    bucket.get("positive_task_success_total", 0.0) or 0.0
                )
                / float(repo_count),
                "retrieval_task_gap_rate_mean": float(
                    bucket.get("retrieval_task_gap_rate_total", 0.0) or 0.0
                )
                / float(repo_count),
                "precision_at_k_mean": float(
                    bucket.get("precision_total", 0.0) or 0.0
                )
                / float(repo_count),
                "noise_rate_mean": float(bucket.get("noise_total", 0.0) or 0.0)
                / float(repo_count),
                "latency_p95_ms_mean": float(
                    bucket.get("latency_total", 0.0) or 0.0
                )
                / float(repo_count),
                "repomap_latency_p95_ms_mean": float(
                    bucket.get("repomap_latency_total", 0.0) or 0.0
                )
                / float(repo_count),
                "slo_downgrade_case_rate_mean": float(
                    bucket.get("slo_downgrade_total", 0.0) or 0.0
                )
                / float(repo_count),
            }
        )

    return rows


def _build_plugin_policy_summary(*, repos: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("applied", "conflicts", "blocked", "warn", "remote_applied")
    totals: dict[str, int] = {key: 0 for key in keys}
    mode_distribution: dict[str, int] = {}
    repo_rows: list[dict[str, Any]] = []

    for item in repos:
        plugin_raw = item.get("plugin_policy_summary")
        plugin = plugin_raw if isinstance(plugin_raw, dict) else {}

        mode = str(plugin.get("mode") or "").strip().lower() or "(none)"
        mode_distribution[mode] = mode_distribution.get(mode, 0) + 1

        totals_raw = plugin.get("totals")
        policy_totals = totals_raw if isinstance(totals_raw, dict) else {}

        row: dict[str, Any] = {
            "name": str(item.get("name") or "").strip() or "(unknown)",
            "mode": mode,
        }
        has_signal = mode != "(none)"

        for key in keys:
            value = max(0, int(policy_totals.get(key, 0) or 0))
            totals[key] += value
            row[key] = value
            if value > 0:
                has_signal = True

        if has_signal:
            repo_rows.append(row)

    repo_rows.sort(key=lambda item: (str(item.get("name", "")), str(item.get("mode", ""))))

    return {
        "totals": totals,
        "mode_distribution": {
            mode: mode_distribution[mode] for mode in sorted(mode_distribution)
        },
        "repos": repo_rows,
    }


def _build_task_success_rows(*, repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in repos:
        metrics = item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {}
        summary_raw = item.get("task_success_summary")
        summary = summary_raw if isinstance(summary_raw, dict) else {}
        case_count = max(0, int(summary.get("case_count", 0) or 0))
        retrieval_task_gap_count = max(
            0, int(summary.get("retrieval_task_gap_count", 0) or 0)
        )
        rows.append(
            {
                "name": str(item.get("name") or "").strip() or "(unknown)",
                "task_success_rate": float(
                    summary.get("task_success_rate", _task_success_rate_from_metrics(metrics))
                    or 0.0
                ),
                "case_count": case_count,
                "negative_control_case_count": max(
                    0, int(summary.get("negative_control_case_count", 0) or 0)
                ),
                "retrieval_task_gap_count": retrieval_task_gap_count,
                "retrieval_task_gap_rate": float(
                    summary.get(
                        "retrieval_task_gap_rate",
                        (
                            float(retrieval_task_gap_count) / float(case_count)
                            if case_count > 0
                            else 0.0
                        ),
                    )
                    or 0.0
                ),
            }
        )
    return rows


def _extract_nested_summary(
    *, summary: dict[str, Any], results_payload: dict[str, Any], key: str
) -> dict[str, Any]:
    raw = summary.get(key)
    if not isinstance(raw, dict):
        raw = results_payload.get(key)
    return raw if isinstance(raw, dict) else {}


def _case_weight(item: dict[str, Any]) -> int:
    summary_raw = item.get("task_success_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    return max(1, int(summary.get("case_count", 0) or 0))


def _build_stage_latency_summary(*, repos: list[dict[str, Any]]) -> dict[str, Any]:
    stage_names = ("memory", "index", "repomap", "augment", "skills", "source_plan", "total")
    summary: dict[str, Any] = {}
    total_weight = sum(_case_weight(item) for item in repos) or 1

    for stage in stage_names:
        weighted_mean = 0.0
        weighted_p95 = 0.0
        weighted_median = 0.0
        for item in repos:
            stage_summary_raw = item.get("stage_latency_summary")
            stage_summary = (
                stage_summary_raw if isinstance(stage_summary_raw, dict) else {}
            )
            stage_metrics_raw = stage_summary.get(stage)
            stage_metrics = (
                stage_metrics_raw if isinstance(stage_metrics_raw, dict) else {}
            )
            weight = _case_weight(item)
            weighted_mean += float(stage_metrics.get("mean_ms", 0.0) or 0.0) * weight
            weighted_p95 += float(stage_metrics.get("p95_ms", 0.0) or 0.0) * weight
            weighted_median += (
                float(stage_metrics.get("median_ms", 0.0) or 0.0) * weight
            )

        bucket: dict[str, float] = {
            "mean_ms": weighted_mean / float(total_weight),
            "p95_ms": weighted_p95 / float(total_weight),
        }
        if stage == "total":
            bucket["median_ms"] = weighted_median / float(total_weight)
        summary[stage] = bucket

    return summary


def _build_slo_budget_summary(*, repos: list[dict[str, Any]]) -> dict[str, Any]:
    signal_names = (
        "parallel_docs_timeout_ratio",
        "parallel_worktree_timeout_ratio",
        "embedding_time_budget_exceeded_ratio",
        "embedding_adaptive_budget_ratio",
        "embedding_fallback_ratio",
        "chunk_semantic_time_budget_exceeded_ratio",
        "chunk_semantic_fallback_ratio",
        "xref_budget_exhausted_ratio",
    )
    total_case_count = sum(_case_weight(item) for item in repos)
    if total_case_count <= 0:
        total_case_count = 1

    budget_limits = {
        "parallel_time_budget_ms_mean": 0.0,
        "embedding_time_budget_ms_mean": 0.0,
        "chunk_semantic_time_budget_ms_mean": 0.0,
        "xref_time_budget_ms_mean": 0.0,
    }
    signal_counts = {name: 0 for name in signal_names}
    downgrade_case_count = 0

    for item in repos:
        weight = _case_weight(item)
        summary_raw = item.get("slo_budget_summary")
        summary = summary_raw if isinstance(summary_raw, dict) else {}
        budget_limits_raw = summary.get("budget_limits_ms")
        limits = budget_limits_raw if isinstance(budget_limits_raw, dict) else {}
        signals_raw = summary.get("signals")
        signals = signals_raw if isinstance(signals_raw, dict) else {}

        for key in budget_limits:
            budget_limits[key] += float(limits.get(key, 0.0) or 0.0) * weight

        downgrade_case_count += max(
            0, int(summary.get("downgrade_case_count", 0) or 0)
        )
        for name in signal_names:
            signal_raw = signals.get(name)
            signal = signal_raw if isinstance(signal_raw, dict) else {}
            signal_counts[name] += max(0, int(signal.get("count", 0) or 0))

    normalized_limits = {
        key: float(value) / float(total_case_count) for key, value in budget_limits.items()
    }
    return {
        "case_count": total_case_count,
        "budget_limits_ms": normalized_limits,
        "downgrade_case_count": downgrade_case_count,
        "downgrade_case_rate": float(downgrade_case_count) / float(total_case_count),
        "signals": {
            name: {
                "count": signal_counts[name],
                "rate": float(signal_counts[name]) / float(total_case_count),
            }
            for name in signal_names
        },
    }


def _build_latency_slo_bucket_summary(*, repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    bucket_order = {
        "repo_size_small": 0,
        "repo_size_medium": 1,
        "repo_size_large": 2,
        "repo_size_unknown": 3,
    }

    for item in repos:
        bucket_name = str(item.get("workload_bucket") or "").strip() or "policy_auto"
        bucket = buckets.setdefault(
            bucket_name,
            {
                "repos": [],
                "repo_names": [],
                "retrieval_policies": set(),
                "file_counts": [],
            },
        )
        bucket["repos"].append(item)
        repo_name = str(item.get("name") or "").strip()
        if repo_name:
            bucket["repo_names"].append(repo_name)
        policy = str(item.get("retrieval_policy") or "auto").strip().lower() or "auto"
        bucket["retrieval_policies"].add(policy)
        file_count = max(0, int(item.get("index_file_count", 0) or 0))
        if file_count > 0:
            bucket["file_counts"].append(file_count)

    rows: list[dict[str, Any]] = []
    for bucket_name in sorted(
        buckets,
        key=lambda item: (bucket_order.get(item, 99), item),
    ):
        bucket = buckets[bucket_name]
        file_counts = list(bucket.get("file_counts", []))
        summary: dict[str, Any] = {
            "workload_bucket": bucket_name,
            "repo_count": len(bucket.get("repos", [])),
            "repo_names": sorted(bucket.get("repo_names", [])),
            "retrieval_policies": sorted(bucket.get("retrieval_policies", set())),
            "stage_latency_summary": _build_stage_latency_summary(
                repos=list(bucket.get("repos", []))
            ),
            "slo_budget_summary": _build_slo_budget_summary(
                repos=list(bucket.get("repos", []))
            ),
        }
        if file_counts:
            summary["file_count_mean"] = float(sum(file_counts)) / float(len(file_counts))
            summary["file_count_min"] = min(file_counts)
            summary["file_count_max"] = max(file_counts)
        else:
            summary["file_count_mean"] = 0.0
        rows.append(summary)

    return rows


def _build_latency_slo_summary(*, summary: dict[str, Any]) -> dict[str, Any]:
    repos_raw = summary.get("repos")
    repos = repos_raw if isinstance(repos_raw, list) else []
    stage_latency_summary_raw = summary.get("stage_latency_summary")
    stage_latency_summary = (
        stage_latency_summary_raw if isinstance(stage_latency_summary_raw, dict) else {}
    )
    slo_budget_summary_raw = summary.get("slo_budget_summary")
    slo_budget_summary = (
        slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
    )
    threshold_small = int(REPO_SIZE_BUCKET_THRESHOLDS[0][1])
    threshold_medium = int(REPO_SIZE_BUCKET_THRESHOLDS[1][1])
    return {
        "generated_at": str(summary.get("generated_at", "") or ""),
        "matrix_config": str(summary.get("matrix_config", "") or ""),
        "repo_count": int(summary.get("repo_count", len(repos)) or len(repos)),
        "bucket_strategy": {
            "preferred_source": "repo_spec.workload_bucket",
            "fallback_source": "index_file_count -> repo_size bucket -> retrieval_policy",
            "repo_size_thresholds": {
                "repo_size_small_max_file_count": threshold_small,
                "repo_size_medium_max_file_count": threshold_medium,
                "repo_size_large_min_file_count": threshold_medium + 1,
            },
        },
        "hard_budget_features": [
            {
                "metric": metric,
                "label": label,
                "description": description,
            }
            for metric, label, description in SLO_HARD_BUDGET_FEATURES
        ],
        "dynamic_downgrade_features": [
            {
                "metric": metric,
                "label": label,
                "description": description,
            }
            for metric, label, description in SLO_DYNAMIC_DOWNGRADE_FEATURES
        ],
        "stage_latency_summary": dict(stage_latency_summary),
        "slo_budget_summary": dict(slo_budget_summary),
        "workload_buckets": _build_latency_slo_bucket_summary(repos=repos),
    }


def _build_latency_slo_summary_markdown(*, payload: dict[str, Any]) -> str:
    stage_latency_summary_raw = payload.get("stage_latency_summary")
    stage_latency_summary = (
        stage_latency_summary_raw if isinstance(stage_latency_summary_raw, dict) else {}
    )
    slo_budget_summary_raw = payload.get("slo_budget_summary")
    slo_budget_summary = (
        slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
    )
    bucket_strategy_raw = payload.get("bucket_strategy")
    bucket_strategy = (
        bucket_strategy_raw if isinstance(bucket_strategy_raw, dict) else {}
    )
    repo_size_thresholds_raw = bucket_strategy.get("repo_size_thresholds")
    repo_size_thresholds = (
        repo_size_thresholds_raw
        if isinstance(repo_size_thresholds_raw, dict)
        else {}
    )

    lines: list[str] = [
        "# ACE-Lite Latency and SLO Summary",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Matrix config: {payload.get('matrix_config', '')}",
        f"- Repo count: {int(payload.get('repo_count', 0) or 0)}",
        "- Bucket strategy: preferred={preferred}, fallback={fallback}".format(
            preferred=str(bucket_strategy.get("preferred_source", "") or "(none)"),
            fallback=str(bucket_strategy.get("fallback_source", "") or "(none)"),
        ),
        "- Repo size thresholds: small<={small}, medium<={medium}, large>={large}".format(
            small=int(repo_size_thresholds.get("repo_size_small_max_file_count", 0) or 0),
            medium=int(
                repo_size_thresholds.get("repo_size_medium_max_file_count", 0) or 0
            ),
            large=int(repo_size_thresholds.get("repo_size_large_min_file_count", 0) or 0),
        ),
        "",
        "## Hard Budget Features",
        "",
        "| Metric | Label | Why It Is Hard-Budgeted |",
        "| --- | --- | --- |",
    ]

    hard_features_raw = payload.get("hard_budget_features")
    hard_features = hard_features_raw if isinstance(hard_features_raw, list) else []
    for item in hard_features:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {metric} | {label} | {description} |".format(
                metric=str(item.get("metric", "") or ""),
                label=str(item.get("label", "") or ""),
                description=str(item.get("description", "") or ""),
            )
        )
    lines.extend(
        [
            "",
            "## Dynamic Downgrade Features",
            "",
            "| Metric | Label | Downgrade Behavior |",
            "| --- | --- | --- |",
        ]
    )

    dynamic_features_raw = payload.get("dynamic_downgrade_features")
    dynamic_features = (
        dynamic_features_raw if isinstance(dynamic_features_raw, list) else []
    )
    for item in dynamic_features:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {metric} | {label} | {description} |".format(
                metric=str(item.get("metric", "") or ""),
                label=str(item.get("label", "") or ""),
                description=str(item.get("description", "") or ""),
            )
        )

    lines.extend(
        [
            "",
            "## Overall Stage Latency",
            "",
            "| Stage | Mean (ms) | P95 (ms) |",
            "| --- | ---: | ---: |",
        ]
    )
    for stage in ("memory", "index", "repomap", "augment", "skills", "source_plan", "total"):
        stage_raw = stage_latency_summary.get(stage)
        stage_metrics = stage_raw if isinstance(stage_raw, dict) else {}
        lines.append(
            "| {stage} | {mean:.2f} | {p95:.2f} |".format(
                stage=stage,
                mean=float(stage_metrics.get("mean_ms", 0.0) or 0.0),
                p95=float(stage_metrics.get("p95_ms", 0.0) or 0.0),
            )
        )

    budget_limits_raw = slo_budget_summary.get("budget_limits_ms")
    budget_limits = budget_limits_raw if isinstance(budget_limits_raw, dict) else {}
    signals_raw = slo_budget_summary.get("signals")
    signals = signals_raw if isinstance(signals_raw, dict) else {}
    lines.extend(
        [
            "",
            "## Overall SLO Budget",
            "",
            "- Downgrade cases: {count}/{case_count} ({rate:.4f})".format(
                count=int(slo_budget_summary.get("downgrade_case_count", 0) or 0),
                case_count=int(slo_budget_summary.get("case_count", 0) or 0),
                rate=float(slo_budget_summary.get("downgrade_case_rate", 0.0) or 0.0),
            ),
            "",
            "| Budget | Mean (ms) |",
            "| --- | ---: |",
        ]
    )
    for metric, _label, _description in SLO_HARD_BUDGET_FEATURES:
        lines.append(
            "| {metric} | {value:.2f} |".format(
                metric=metric,
                value=float(budget_limits.get(metric, 0.0) or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "| Signal | Count | Rate |",
            "| --- | ---: | ---: |",
        ]
    )
    for metric, _label, _description in SLO_DYNAMIC_DOWNGRADE_FEATURES:
        if metric == "slo_downgrade_case_rate":
            lines.append(
                "| {metric} | {count} | {rate:.4f} |".format(
                    metric=metric,
                    count=int(slo_budget_summary.get("downgrade_case_count", 0) or 0),
                    rate=float(
                        slo_budget_summary.get("downgrade_case_rate", 0.0) or 0.0
                    ),
                )
            )
            continue
        signal_raw = signals.get(metric)
        signal = signal_raw if isinstance(signal_raw, dict) else {}
        lines.append(
            "| {metric} | {count} | {rate:.4f} |".format(
                metric=metric,
                count=int(signal.get("count", 0) or 0),
                rate=float(signal.get("rate", 0.0) or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Workload Buckets",
            "",
            "| Bucket | Repo Count | File Count Mean | Total P95 (ms) | Index P95 (ms) | Repomap P95 (ms) | Downgrade Rate | Policies |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    workload_buckets_raw = payload.get("workload_buckets")
    workload_buckets = (
        workload_buckets_raw if isinstance(workload_buckets_raw, list) else []
    )
    for item in workload_buckets:
        if not isinstance(item, dict):
            continue
        bucket_stage_raw = item.get("stage_latency_summary")
        bucket_stage = bucket_stage_raw if isinstance(bucket_stage_raw, dict) else {}
        total_raw = bucket_stage.get("total")
        total = total_raw if isinstance(total_raw, dict) else {}
        index_raw = bucket_stage.get("index")
        index_stage = index_raw if isinstance(index_raw, dict) else {}
        repomap_raw = bucket_stage.get("repomap")
        repomap_stage = repomap_raw if isinstance(repomap_raw, dict) else {}
        bucket_slo_raw = item.get("slo_budget_summary")
        bucket_slo = bucket_slo_raw if isinstance(bucket_slo_raw, dict) else {}
        lines.append(
            "| {bucket} | {repo_count} | {file_count_mean:.1f} | {total_p95:.2f} | {index_p95:.2f} | {repomap_p95:.2f} | {downgrade_rate:.4f} | {policies} |".format(
                bucket=str(item.get("workload_bucket", "") or ""),
                repo_count=int(item.get("repo_count", 0) or 0),
                file_count_mean=float(item.get("file_count_mean", 0.0) or 0.0),
                total_p95=float(total.get("p95_ms", 0.0) or 0.0),
                index_p95=float(index_stage.get("p95_ms", 0.0) or 0.0),
                repomap_p95=float(repomap_stage.get("p95_ms", 0.0) or 0.0),
                downgrade_rate=float(
                    bucket_slo.get("downgrade_case_rate", 0.0) or 0.0
                ),
                policies=", ".join(
                    str(value)
                    for value in item.get("retrieval_policies", [])
                    if str(value).strip()
                )
                or "(none)",
            )
        )

    for item in workload_buckets:
        if not isinstance(item, dict):
            continue
        bucket_name = str(item.get("workload_bucket", "") or "")
        bucket_stage_raw = item.get("stage_latency_summary")
        bucket_stage = bucket_stage_raw if isinstance(bucket_stage_raw, dict) else {}
        bucket_slo_raw = item.get("slo_budget_summary")
        bucket_slo = bucket_slo_raw if isinstance(bucket_slo_raw, dict) else {}
        bucket_limits_raw = bucket_slo.get("budget_limits_ms")
        bucket_limits = bucket_limits_raw if isinstance(bucket_limits_raw, dict) else {}
        bucket_signals_raw = bucket_slo.get("signals")
        bucket_signals = bucket_signals_raw if isinstance(bucket_signals_raw, dict) else {}
        lines.extend(
            [
                "",
                f"### {bucket_name}",
                "",
                "- Repo names: {names}".format(
                    names=", ".join(
                        str(value)
                        for value in item.get("repo_names", [])
                        if str(value).strip()
                    )
                    or "(none)"
                ),
                "- Retrieval policies: {policies}".format(
                    policies=", ".join(
                        str(value)
                        for value in item.get("retrieval_policies", [])
                        if str(value).strip()
                    )
                    or "(none)"
                ),
                "- File count mean: {mean:.1f}".format(
                    mean=float(item.get("file_count_mean", 0.0) or 0.0)
                ),
                "",
                "| Stage | P95 (ms) |",
                "| --- | ---: |",
            ]
        )
        for stage in ("memory", "index", "repomap", "augment", "skills", "source_plan", "total"):
            stage_raw = bucket_stage.get(stage)
            stage_metrics = stage_raw if isinstance(stage_raw, dict) else {}
            lines.append(
                "| {stage} | {p95:.2f} |".format(
                    stage=stage,
                    p95=float(stage_metrics.get("p95_ms", 0.0) or 0.0),
                )
            )
        lines.extend(
            [
                "",
                "| Budget/Signal | Value |",
                "| --- | ---: |",
            ]
        )
        for metric, _label, _description in SLO_HARD_BUDGET_FEATURES:
            lines.append(
                "| {metric} | {value:.2f} |".format(
                    metric=metric,
                    value=float(bucket_limits.get(metric, 0.0) or 0.0),
                )
            )
        for metric, _label, _description in SLO_DYNAMIC_DOWNGRADE_FEATURES:
            if metric == "slo_downgrade_case_rate":
                lines.append(
                    "| {metric} | {value:.4f} |".format(
                        metric=metric,
                        value=float(bucket_slo.get("downgrade_case_rate", 0.0) or 0.0),
                    )
                )
                continue
            signal_raw = bucket_signals.get(metric)
            signal = signal_raw if isinstance(signal_raw, dict) else {}
            lines.append(
                "| {metric} | {value:.4f} |".format(
                    metric=metric,
                    value=float(signal.get("rate", 0.0) or 0.0),
                )
            )

    return "\n".join(lines).strip() + "\n"


def _ensure_checkout(*, workspace: Path, spec: dict[str, Any]) -> dict[str, Any]:
    name = str(spec.get("name") or "").strip()
    if not name:
        raise ValueError("repo matrix item missing name")

    url = str(spec.get("url") or "").strip()
    if not url:
        raise ValueError(f"repo matrix item {name} missing url")

    ref = str(spec.get("ref") or "main").strip()
    target = workspace / name

    if not (target / ".git").exists():
        if target.exists():
            raise ValueError(f"checkout target exists without .git: {target}")
        _run_checkout_command_with_retry(
            cmd=["git", "clone", "--depth", "1", "--branch", ref, url, str(target)],
            label=f"clone {name}",
        )
    else:
        _run_checkout_command_with_retry(
            cmd=["git", "-C", str(target), "fetch", "--depth", "1", "origin", ref],
            label=f"fetch {name}",
        )
        checkout = _run_command(cmd=["git", "-C", str(target), "checkout", "--force", "FETCH_HEAD"])
        _require_success(checkout, label=f"checkout {name}")

    submodules = _sync_checkout_submodules(repo_name=name, target=target, spec=spec)

    rev = _run_command(cmd=["git", "-C", str(target), "rev-parse", "HEAD"])
    _require_success(rev, label=f"resolve head {name}")

    return {
        "name": name,
        "root": str(target.resolve()),
        "ref": ref,
        "resolved_commit": str(rev.stdout or "").strip(),
        "submodules": submodules,
    }


def _run_repo_benchmark(
    *,
    project_root: Path,
    cli_bin: str,
    repo_spec: dict[str, Any],
    defaults: dict[str, Any],
    global_thresholds: dict[str, float],
    repos_workspace: Path,
    output_root: Path,
) -> dict[str, Any]:
    started = perf_counter()
    checkout = _ensure_checkout(workspace=repos_workspace, spec=repo_spec)

    name = checkout["name"]
    repo_root = Path(checkout["root"])
    repo_id = str(repo_spec.get("repo") or name)
    languages = str(repo_spec.get("languages") or defaults.get("languages") or "python,typescript,javascript,go")
    retrieval_policy = str(
        repo_spec.get("retrieval_policy", defaults.get("retrieval_policy", "auto"))
        or "auto"
    ).strip().lower() or "auto"

    cases_path = _resolve_cases_path(project_root=project_root, value=str(repo_spec.get("cases") or ""))
    if not cases_path.exists():
        raise FileNotFoundError(f"benchmark cases not found for {name}: {cases_path}")

    repo_output = output_root / name
    repo_output.mkdir(parents=True, exist_ok=True)
    index_path = repo_output / "index.json"

    skills_dir = _resolve_skills_path(project_root=project_root, value=str(defaults.get("skills_dir", "skills")))

    index_cmd = [
        cli_bin,
        "index",
        "--root",
        str(repo_root),
        "--languages",
        languages,
        "--output",
        str(index_path),
    ]
    _require_success(_run_command(cmd=index_cmd), label=f"index {name}")

    benchmark_cmd = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        repo_id,
        "--root",
        str(repo_root),
        "--skills-dir",
        str(skills_dir),
        "--top-k-files",
        str(int(repo_spec.get("top_k_files", defaults.get("top_k_files", 8)))),
        "--min-candidate-score",
        str(int(repo_spec.get("min_candidate_score", defaults.get("min_candidate_score", 2)))),
        "--candidate-relative-threshold",
        str(float(repo_spec.get("candidate_relative_threshold", defaults.get("candidate_relative_threshold", 0.0)))),
        "--candidate-ranker",
        str(repo_spec.get("candidate_ranker", defaults.get("candidate_ranker", "heuristic"))),
        "--retrieval-policy",
        retrieval_policy,
        "--chunk-top-k",
        str(int(repo_spec.get("chunk_top_k", defaults.get("chunk_top_k", 24)))),
        "--chunk-per-file-limit",
        str(
            int(
                repo_spec.get(
                    "chunk_per_file_limit", defaults.get("chunk_per_file_limit", 3)
                )
            )
        ),
        "--chunk-token-budget",
        str(
            int(
                repo_spec.get(
                    "chunk_token_budget", defaults.get("chunk_token_budget", 1200)
                )
            )
        ),
        "--languages",
        languages,
        "--index-cache-path",
        str(index_path),
        "--memory-primary",
        str(defaults.get("memory_primary", "none")),
        "--memory-secondary",
        str(defaults.get("memory_secondary", "none")),
        "--warmup-runs",
        str(int(repo_spec.get("warmup_runs", defaults.get("warmup_runs", 0)))),
        "--app",
        str(defaults.get("app", "codex")),
        "--output",
        str(repo_output),
    ]

    embedding_enabled = bool(
        repo_spec.get("embedding_enabled", defaults.get("embedding_enabled", False))
    )
    if embedding_enabled:
        benchmark_cmd.append("--embedding-enabled")
    else:
        benchmark_cmd.append("--no-embedding-enabled")

    benchmark_cmd.extend(
        [
            "--embedding-provider",
            str(repo_spec.get("embedding_provider", defaults.get("embedding_provider", "hash"))),
            "--embedding-model",
            str(repo_spec.get("embedding_model", defaults.get("embedding_model", "hash-v1"))),
            "--embedding-dimension",
            str(
                int(
                    repo_spec.get(
                        "embedding_dimension",
                        defaults.get("embedding_dimension", 256),
                    )
                )
            ),
            "--embedding-index-path",
            str(
                repo_spec.get(
                    "embedding_index_path",
                    defaults.get(
                        "embedding_index_path",
                        repo_output / "embeddings" / "index.json",
                    ),
                )
            ),
            "--embedding-rerank-pool",
            str(
                int(
                    repo_spec.get(
                        "embedding_rerank_pool",
                        defaults.get("embedding_rerank_pool", 24),
                    )
                )
            ),
            "--embedding-lexical-weight",
            str(
                float(
                    repo_spec.get(
                        "embedding_lexical_weight",
                        defaults.get("embedding_lexical_weight", 0.7),
                    )
                )
            ),
            "--embedding-semantic-weight",
            str(
                float(
                    repo_spec.get(
                        "embedding_semantic_weight",
                        defaults.get("embedding_semantic_weight", 0.3),
                    )
                )
            ),
            "--embedding-min-similarity",
            str(
                float(
                    repo_spec.get(
                        "embedding_min_similarity",
                        defaults.get("embedding_min_similarity", 0.0),
                    )
                )
            ),
        ]
    )
    if bool(repo_spec.get("embedding_fail_open", defaults.get("embedding_fail_open", True))):
        benchmark_cmd.append("--embedding-fail-open")
    else:
        benchmark_cmd.append("--no-embedding-fail-open")

    if bool(repo_spec.get("cochange", defaults.get("cochange", False))):
        benchmark_cmd.append("--cochange")
    else:
        benchmark_cmd.append("--no-cochange")

    if bool(repo_spec.get("repomap", defaults.get("repomap", True))):
        benchmark_cmd.append("--repomap")
    else:
        benchmark_cmd.append("--no-repomap")

    if bool(repo_spec.get("index_incremental", defaults.get("index_incremental", False))):
        benchmark_cmd.append("--index-incremental")
    else:
        benchmark_cmd.append("--no-index-incremental")

    if bool(
        repo_spec.get(
            "chunk_diversity_enabled",
            defaults.get("chunk_diversity_enabled", True),
        )
    ):
        benchmark_cmd.append("--chunk-diversity-enabled")
    else:
        benchmark_cmd.append("--no-chunk-diversity-enabled")

    benchmark_result = _run_command(cmd=benchmark_cmd)
    _require_success(benchmark_result, label=f"benchmark {name}")

    results_path = repo_output / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"results.json not found for {name}: {results_path}")

    results_payload = json.loads(results_path.read_text(encoding="utf-8"))
    metrics = results_payload.get("metrics", {}) if isinstance(results_payload.get("metrics"), dict) else {}

    summary_path = repo_output / "summary.json"
    summary_payload = _load_summary_payload(summary_path=summary_path)
    if not metrics and isinstance(summary_payload.get("metrics"), dict):
        metrics = summary_payload.get("metrics", {})

    benchmark_failed_checks = _extract_failed_check_names(summary_payload)
    benchmark_regressed = bool(summary_payload.get("regressed", False))
    resolved_retrieval_policy = _extract_retrieval_policy(
        summary=summary_payload,
        repo_spec=repo_spec,
        defaults=defaults,
    )
    plugin_policy_summary = _extract_plugin_policy_summary(results_payload)
    task_success_summary = _extract_task_success_summary(
        summary=summary_payload,
        results_payload=results_payload,
        metrics=metrics,
    )
    stage_latency_summary = _extract_nested_summary(
        summary=summary_payload,
        results_payload=results_payload,
        key="stage_latency_summary",
    )
    slo_budget_summary = _extract_nested_summary(
        summary=summary_payload,
        results_payload=results_payload,
        key="slo_budget_summary",
    )
    index_path = repo_output / "index.json"
    index_file_count = _load_index_file_count(index_path=index_path)
    workload_bucket = _resolve_workload_bucket(
        repo_spec=repo_spec,
        file_count=index_file_count,
        retrieval_policy=resolved_retrieval_policy,
    )

    if not benchmark_failed_checks:
        regression = results_payload.get("regression")
        if isinstance(regression, dict):
            benchmark_regressed = bool(regression.get("regressed", benchmark_regressed))
            raw_fallback = regression.get("failed_checks")
            if isinstance(raw_fallback, list):
                benchmark_failed_checks = [
                    str(item).strip() for item in raw_fallback if str(item).strip()
                ]

    thresholds = dict(global_thresholds)
    thresholds.update(_coerce_thresholds(repo_spec.get("thresholds")))
    failures = _evaluate_thresholds(metrics=metrics, thresholds=thresholds)

    elapsed_s = perf_counter() - started

    return {
        "name": name,
        "repo": repo_id,
        "url": str(repo_spec.get("url") or ""),
        "requested_ref": str(repo_spec.get("ref") or ""),
        "resolved_commit": checkout.get("resolved_commit", ""),
        "root": checkout.get("root", ""),
        "cases": str(cases_path),
        "languages": languages,
        "results_json": str(results_path),
        "summary_json": str(summary_path) if summary_path.exists() else "",
        "report_md": str(repo_output / "report.md"),
        "index_json": str(index_path) if index_path.exists() else "",
        "index_file_count": index_file_count,
        "metrics": metrics,
        "retrieval_policy": resolved_retrieval_policy,
        "workload_bucket": workload_bucket,
        "plugin_policy_summary": plugin_policy_summary,
        "task_success_summary": task_success_summary,
        "stage_latency_summary": stage_latency_summary,
        "slo_budget_summary": slo_budget_summary,
        "benchmark_regressed": benchmark_regressed,
        "benchmark_failed_checks": benchmark_failed_checks,
        "thresholds": thresholds,
        "failed_checks": failures,
        "passed": len(failures) == 0,
        "elapsed_seconds": round(elapsed_s, 3),
    }


def _build_summary_markdown(*, summary: dict[str, Any]) -> str:
    repos = summary.get("repos", []) if isinstance(summary.get("repos"), list) else []
    lines: list[str] = [
        "# ACE-Lite Benchmark Matrix",
        "",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Matrix config: {summary.get('matrix_config', '')}",
        f"- Passed: {summary.get('passed', False)}",
        f"- Repo count: {len(repos)}",
        f"- Task success mean: {float(summary.get('task_success_mean', 0.0) or 0.0):.4f}",
        f"- Negative control cases: {int(summary.get('negative_control_case_count', 0) or 0)}",
        f"- Retrieval-task gap count: {int(summary.get('retrieval_task_gap_count', 0) or 0)}",
        "",
        "## Repo Results",
        "",
        "| Repo | Retrieval Policy | Passed | Regressed | Failed Checks | Recall | Task Success | Precision | Noise | Dependency | Neg Ctrls | Gap Rate | Repomap p95 (ms) | Latency p95 (ms) | Chunk Hit | Notes Hit | Profile Selected | Capture Trigger | Emb Sim Mean | Emb Rerank | Emb Fallback |",
        "| --- | --- | :---: | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    stage_latency_summary_raw = summary.get("stage_latency_summary")
    stage_latency_summary = (
        stage_latency_summary_raw
        if isinstance(stage_latency_summary_raw, dict)
        else {}
    )
    if stage_latency_summary:
        total_stage_raw = stage_latency_summary.get("total")
        total_stage = total_stage_raw if isinstance(total_stage_raw, dict) else {}
        lines.extend(
            [
                "## Stage Latency Summary",
                "",
                "- total: mean={mean:.2f}ms, p95={p95:.2f}ms".format(
                    mean=float(total_stage.get("mean_ms", 0.0) or 0.0),
                    p95=float(total_stage.get("p95_ms", 0.0) or 0.0),
                ),
                "- index: p95={value:.2f}ms".format(
                    value=float(
                        (
                            stage_latency_summary.get("index", {})
                            if isinstance(stage_latency_summary.get("index", {}), dict)
                            else {}
                        ).get("p95_ms", 0.0)
                        or 0.0
                    )
                ),
                "- repomap: p95={value:.2f}ms".format(
                    value=float(
                        (
                            stage_latency_summary.get("repomap", {})
                            if isinstance(stage_latency_summary.get("repomap", {}), dict)
                            else {}
                        ).get("p95_ms", 0.0)
                        or 0.0
                    )
                ),
                "",
            ]
        )

    slo_budget_summary_raw = summary.get("slo_budget_summary")
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
        lines.extend(
            [
                "## SLO Budget Summary",
                "",
                "- downgrade_case_rate={rate:.4f}".format(
                    rate=float(
                        slo_budget_summary.get("downgrade_case_rate", 0.0) or 0.0
                    )
                ),
                "- budget_limits_ms: parallel={parallel:.2f}, embedding={embedding:.2f}, chunk_semantic={chunk:.2f}, xref={xref:.2f}".format(
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
                    xref=float(budget_limits.get("xref_time_budget_ms_mean", 0.0) or 0.0),
                ),
                "- signal_rates: "
                + ", ".join(
                    "{name}={rate:.4f}".format(
                        name=name,
                        rate=float(
                            (
                                signals.get(name, {})
                                if isinstance(signals.get(name, {}), dict)
                                else {}
                            ).get("rate", 0.0)
                            or 0.0
                        ),
                    )
                    for name in (
                        "parallel_docs_timeout_ratio",
                        "embedding_time_budget_exceeded_ratio",
                        "embedding_fallback_ratio",
                        "chunk_semantic_fallback_ratio",
                        "xref_budget_exhausted_ratio",
                    )
                ),
                "",
            ]
        )

    for item in repos:
        if not isinstance(item, dict):
            continue
        metrics = item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {}
        task_success_summary_raw = item.get("task_success_summary")
        task_success_summary = (
            task_success_summary_raw if isinstance(task_success_summary_raw, dict) else {}
        )
        bench_failed_raw = item.get("benchmark_failed_checks")
        bench_failed = (
            [str(value).strip() for value in bench_failed_raw if str(value).strip()]
            if isinstance(bench_failed_raw, list)
            else []
        )
        lines.append(
            "| {repo} | {policy} | {passed} | {regressed} | {bench_failed} | {recall:.4f} | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {dependency:.4f} | {negative_controls} | {gap_rate:.4f} | {repomap_latency:.2f} | {latency:.2f} | {chunk_hit:.4f} | {notes_hit:.4f} | {profile_selected:.4f} | {capture_trigger:.4f} | {embedding_similarity:.4f} | {embedding_rerank:.4f} | {embedding_fallback:.4f} |".format(
                repo=str(item.get("name", "")),
                policy=str(item.get("retrieval_policy", "auto") or "auto"),
                passed="✅" if bool(item.get("passed", False)) else "❌",
                regressed="⚠️" if bool(item.get("benchmark_regressed", False)) else "-",
                bench_failed=", ".join(bench_failed) if bench_failed else "-",
                recall=float(metrics.get("recall_at_k", 0.0) or 0.0),
                task_success=float(
                    task_success_summary.get(
                        "task_success_rate",
                        _task_success_rate_from_metrics(metrics),
                    )
                    or 0.0
                ),
                precision=float(metrics.get("precision_at_k", 0.0) or 0.0),
                noise=float(metrics.get("noise_rate", 0.0) or 0.0),
                dependency=float(metrics.get("dependency_recall", 0.0) or 0.0),
                negative_controls=int(
                    task_success_summary.get("negative_control_case_count", 0) or 0
                ),
                gap_rate=float(
                    task_success_summary.get("retrieval_task_gap_rate", 0.0) or 0.0
                ),
                repomap_latency=float(
                    metrics.get("repomap_latency_p95_ms", 0.0) or 0.0
                ),
                latency=float(metrics.get("latency_p95_ms", 0.0) or 0.0),
                chunk_hit=float(metrics.get("chunk_hit_at_k", 0.0) or 0.0),
                notes_hit=float(metrics.get("notes_hit_ratio", 0.0) or 0.0),
                profile_selected=float(
                    metrics.get("profile_selected_mean", 0.0) or 0.0
                ),
                capture_trigger=float(
                    metrics.get("capture_trigger_ratio", 0.0) or 0.0
                ),
                embedding_similarity=float(
                    metrics.get("embedding_similarity_mean", 0.0) or 0.0
                ),
                embedding_rerank=float(
                    metrics.get("embedding_rerank_ratio", 0.0) or 0.0
                ),
                embedding_fallback=float(
                    metrics.get("embedding_fallback_ratio", 0.0) or 0.0
                ),
            )
        )

    lines.append("")
    lines.append("## Threshold Failures")
    lines.append("")

    any_failures = False
    for item in repos:
        if not isinstance(item, dict):
            continue
        failed = item.get("failed_checks", []) if isinstance(item.get("failed_checks"), list) else []
        if not failed:
            continue

        any_failures = True
        lines.append(f"### {item.get('name', 'unknown')}")
        for check in failed:
            if not isinstance(check, dict):
                continue
            lines.append(
                "- {metric}: actual={actual:.4f}, expected {operator} {expected:.4f}".format(
                    metric=str(check.get("metric", "")),
                    actual=float(check.get("actual", 0.0) or 0.0),
                    operator=str(check.get("operator", "")),
                    expected=float(check.get("expected", 0.0) or 0.0),
                )
            )
        lines.append("")

    if not any_failures:
        lines.append("- None")
        lines.append("")

    lines.append("## Benchmark Regression Signals")
    lines.append("")

    any_regressions = False
    for item in repos:
        if not isinstance(item, dict):
            continue
        failed = (
            item.get("benchmark_failed_checks", [])
            if isinstance(item.get("benchmark_failed_checks"), list)
            else []
        )
        regressed = bool(item.get("benchmark_regressed", False))
        if not regressed and not failed:
            continue

        any_regressions = True
        lines.append(f"### {item.get('name', 'unknown')}")
        lines.append(f"- regressed: {regressed}")
        lines.append(
            f"- failed_checks: {', '.join(str(value) for value in failed) if failed else '(none)'}"
        )
        lines.append("")

    if not any_regressions:
        lines.append("- None")
        lines.append("")

    lines.append("## Retrieval Policy Summary")
    lines.append("")

    policy_rows = summary.get("retrieval_policy_summary", []) if isinstance(summary.get("retrieval_policy_summary"), list) else []
    if policy_rows:
        lines.append(
            "| Retrieval Policy | Repo Count | Regressed Repo Count | Regressed Rate | Task Success | Positive Task | Gap Rate | Precision | Noise | Latency p95 (ms) | Repomap p95 (ms) | SLO Downgrade |"
        )
        lines.append(
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
        )
        for row in policy_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| {policy} | {repo_count} | {regressed} | {regressed_rate:.4f} | {task_success:.4f} | {positive_task_success:.4f} | {gap_rate:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} | {repomap_latency:.2f} | {downgrade:.4f} |".format(
                    policy=str(row.get("retrieval_policy", "auto") or "auto"),
                    repo_count=int(row.get("repo_count", 0) or 0),
                    regressed=int(row.get("regressed_repo_count", 0) or 0),
                    regressed_rate=float(row.get("regressed_repo_rate", 0.0) or 0.0),
                    task_success=float(row.get("task_success_mean", 0.0) or 0.0),
                    positive_task_success=float(
                        row.get("positive_task_success_mean", 0.0) or 0.0
                    ),
                    gap_rate=float(
                        row.get("retrieval_task_gap_rate_mean", 0.0) or 0.0
                    ),
                    precision=float(row.get("precision_at_k_mean", 0.0) or 0.0),
                    noise=float(row.get("noise_rate_mean", 0.0) or 0.0),
                    latency=float(row.get("latency_p95_ms_mean", 0.0) or 0.0),
                    repomap_latency=float(
                        row.get("repomap_latency_p95_ms_mean", 0.0) or 0.0
                    ),
                    downgrade=float(
                        row.get("slo_downgrade_case_rate_mean", 0.0) or 0.0
                    ),
                )
            )
        lines.append("")
    else:
        lines.append("- None")
        lines.append("")

    lines.append("## Plugin Policy Summary")
    lines.append("")

    plugin_summary_raw = summary.get("plugin_policy_summary")
    plugin_summary = plugin_summary_raw if isinstance(plugin_summary_raw, dict) else {}
    totals_raw = plugin_summary.get("totals")
    totals = totals_raw if isinstance(totals_raw, dict) else {}
    mode_dist_raw = plugin_summary.get("mode_distribution")
    mode_distribution = mode_dist_raw if isinstance(mode_dist_raw, dict) else {}
    repos_raw = plugin_summary.get("repos")
    plugin_repos = repos_raw if isinstance(repos_raw, list) else []

    if totals or mode_distribution or plugin_repos:
        lines.append(
            "- totals: applied={applied}, conflicts={conflicts}, blocked={blocked}, warn={warn}, remote_applied={remote}".format(
                applied=int(totals.get("applied", 0) or 0),
                conflicts=int(totals.get("conflicts", 0) or 0),
                blocked=int(totals.get("blocked", 0) or 0),
                warn=int(totals.get("warn", 0) or 0),
                remote=int(totals.get("remote_applied", 0) or 0),
            )
        )
        if mode_distribution:
            lines.append(
                "- mode_distribution: {items}".format(
                    items=", ".join(
                        f"{key!s}={int(value)}"
                        for key, value in sorted(mode_distribution.items())
                    )
                )
            )
        if plugin_repos:
            lines.append("")
            lines.append("| Repo | Mode | applied | conflicts | blocked | warn | remote_applied |")
            lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
            for item in plugin_repos:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| {name} | {mode} | {applied} | {conflicts} | {blocked} | {warn} | {remote} |".format(
                        name=str(item.get("name", "") or "(unknown)"),
                        mode=str(item.get("mode", "") or "(none)"),
                        applied=int(item.get("applied", 0) or 0),
                        conflicts=int(item.get("conflicts", 0) or 0),
                        blocked=int(item.get("blocked", 0) or 0),
                        warn=int(item.get("warn", 0) or 0),
                        remote=int(item.get("remote_applied", 0) or 0),
                    )
                )
        lines.append("")
    else:
        lines.append("- None")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACE-Lite benchmark matrix across multiple repositories.")
    parser.add_argument("--matrix-config", default="benchmark/matrix/repos.yaml", help="Matrix YAML config path.")
    parser.add_argument("--repos-workdir", default="artifacts/benchmark/matrix/repos", help="Directory for checked-out benchmark repositories.")
    parser.add_argument("--output-dir", default="artifacts/benchmark/matrix/latest", help="Directory for matrix results outputs.")
    parser.add_argument("--cli-bin", default="ace-lite", help="CLI binary name/path.")
    parser.add_argument("--fail-on-thresholds", action="store_true", help="Exit non-zero if any repo fails thresholds.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    matrix_path = Path(args.matrix_config)
    if not matrix_path.is_absolute():
        matrix_path = project_root / matrix_path

    if not matrix_path.exists():
        raise FileNotFoundError(f"matrix config not found: {matrix_path}")

    config = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("matrix config must be an object")

    defaults = config.get("defaults", {}) if isinstance(config.get("defaults"), dict) else {}
    global_thresholds = _coerce_thresholds(config.get("thresholds"))

    repos = config.get("repos", [])
    if not isinstance(repos, list) or not repos:
        raise ValueError("matrix config repos must be a non-empty list")

    repos_workspace = Path(args.repos_workdir)
    if not repos_workspace.is_absolute():
        repos_workspace = project_root / repos_workspace
    repos_workspace.mkdir(parents=True, exist_ok=True)

    output_root = Path(args.output_dir)
    if not output_root.is_absolute():
        output_root = project_root / output_root
    output_root.mkdir(parents=True, exist_ok=True)

    started = perf_counter()
    repo_results: list[dict[str, Any]] = []

    for item in repos:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        print(f"[matrix] running benchmark for {name}...")
        repo_result = _run_repo_benchmark(
            project_root=project_root,
            cli_bin=str(args.cli_bin),
            repo_spec=item,
            defaults=defaults,
            global_thresholds=global_thresholds,
            repos_workspace=repos_workspace,
            output_root=output_root,
        )
        repo_results.append(repo_result)
        failed_checks = (
            repo_result.get("benchmark_failed_checks", [])
            if isinstance(repo_result.get("benchmark_failed_checks"), list)
            else []
        )
        print(
            "[matrix] {name}: policy={policy} passed={passed} regressed={regressed} failed_checks={failed_checks} task_success={task_success:.4f} precision={precision:.4f} noise={noise:.4f} repomap_p95={repomap_latency:.2f} latency_p95={latency:.2f} notes_hit={notes_hit:.4f} capture_trigger={capture_trigger:.4f} emb_sim={embedding_similarity:.4f} emb_fallback={embedding_fallback:.4f}".format(
                name=name,
                policy=str(repo_result.get("retrieval_policy", "auto") or "auto"),
                passed=repo_result.get("passed", False),
                regressed=repo_result.get("benchmark_regressed", False),
                failed_checks=",".join(str(value) for value in failed_checks) if failed_checks else "-",
                task_success=float(
                    repo_result.get("task_success_summary", {}).get(
                        "task_success_rate",
                        _task_success_rate_from_metrics(repo_result.get("metrics", {})),
                    )
                    or 0.0
                ),
                precision=float(repo_result.get("metrics", {}).get("precision_at_k", 0.0) or 0.0),
                noise=float(repo_result.get("metrics", {}).get("noise_rate", 0.0) or 0.0),
                repomap_latency=float(
                    repo_result.get("metrics", {}).get("repomap_latency_p95_ms", 0.0)
                    or 0.0
                ),
                latency=float(repo_result.get("metrics", {}).get("latency_p95_ms", 0.0) or 0.0),
                notes_hit=float(repo_result.get("metrics", {}).get("notes_hit_ratio", 0.0) or 0.0),
                capture_trigger=float(repo_result.get("metrics", {}).get("capture_trigger_ratio", 0.0) or 0.0),
                embedding_similarity=float(
                    repo_result.get("metrics", {}).get("embedding_similarity_mean", 0.0)
                    or 0.0
                ),
                embedding_fallback=float(
                    repo_result.get("metrics", {}).get("embedding_fallback_ratio", 0.0)
                    or 0.0
                ),
            )
        )

    passed = all(bool(item.get("passed", False)) for item in repo_results)
    regression_detected = any(
        bool(item.get("benchmark_regressed", False)) for item in repo_results
    )
    elapsed_s = perf_counter() - started
    task_success_repos = _build_task_success_rows(repos=repo_results)
    total_task_success_cases = sum(
        int(item.get("case_count", 0) or 0) for item in task_success_repos
    )
    total_negative_control_cases = sum(
        int(item.get("negative_control_case_count", 0) or 0) for item in task_success_repos
    )
    total_retrieval_task_gap_count = sum(
        int(item.get("retrieval_task_gap_count", 0) or 0) for item in task_success_repos
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_config": str(matrix_path),
        "passed": passed,
        "benchmark_regression_detected": regression_detected,
        "repo_count": len(repo_results),
        "elapsed_seconds": round(elapsed_s, 3),
        "retrieval_policy_summary": _build_retrieval_policy_summary(repos=repo_results),
        "plugin_policy_summary": _build_plugin_policy_summary(repos=repo_results),
        "task_success_repos": task_success_repos,
        "task_success_mean": (
            sum(item.get("task_success_rate", 0.0) for item in task_success_repos)
            / max(1, len(task_success_repos))
        ),
        "stage_latency_summary": _build_stage_latency_summary(repos=repo_results),
        "slo_budget_summary": _build_slo_budget_summary(repos=repo_results),
        "negative_control_case_count": total_negative_control_cases,
        "retrieval_task_gap_count": total_retrieval_task_gap_count,
        "retrieval_task_gap_rate": (
            float(total_retrieval_task_gap_count) / float(total_task_success_cases)
            if total_task_success_cases > 0
            else 0.0
        ),
        "repos": repo_results,
    }
    latency_slo_summary = _build_latency_slo_summary(summary=summary)

    summary_json = output_root / "matrix_summary.json"
    summary_md = output_root / "matrix_summary.md"
    latency_slo_json = output_root / "latency_slo_summary.json"
    latency_slo_md = output_root / "latency_slo_summary.md"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(_build_summary_markdown(summary=summary), encoding="utf-8")
    latency_slo_json.write_text(
        json.dumps(latency_slo_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    latency_slo_md.write_text(
        _build_latency_slo_summary_markdown(payload=latency_slo_summary),
        encoding="utf-8",
    )

    print(f"[matrix] summary json: {summary_json}")
    print(f"[matrix] summary md:   {summary_md}")
    print(f"[matrix] latency/slo json: {latency_slo_json}")
    print(f"[matrix] latency/slo md:   {latency_slo_md}")

    if args.fail_on_thresholds and not passed:
        print("[matrix] threshold checks failed", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
