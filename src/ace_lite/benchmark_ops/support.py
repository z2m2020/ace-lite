from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CommandResult:
    cmd: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str


def run_command(
    *,
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return CommandResult(
        cmd=cmd,
        cwd=str(cwd) if cwd else None,
        returncode=int(completed.returncode),
        stdout=str(completed.stdout or ""),
        stderr=str(completed.stderr or ""),
    )


def require_success(result: CommandResult, *, label: str) -> None:
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


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_benchmark_metrics(results_path: Path) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    task_success_rate = float(
        metrics.get("task_success_rate", metrics.get("utility_rate", 0.0)) or 0.0
    )
    return {
        key: task_success_rate if key == "task_success_rate" else float(value or 0.0)
        for key, value in metrics.items()
        if isinstance(key, str)
    } | {"task_success_rate": task_success_rate}


def read_benchmark_results(results_path: Path) -> dict[str, Any]:
    if not results_path.exists() or not results_path.is_file():
        return {}
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_benchmark_case_rows(results_path: Path) -> dict[str, dict[str, float]]:
    payload = read_benchmark_results(results_path)
    cases_raw = payload.get("cases")
    cases = cases_raw if isinstance(cases_raw, list) else []
    rows: dict[str, dict[str, float]] = {}
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            continue
        rows[case_id] = {
            "task_success_hit": float(
                item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
            ),
            "precision_at_k": float(item.get("precision_at_k", 0.0) or 0.0),
            "noise_rate": float(item.get("noise_rate", 0.0) or 0.0),
            "recall_hit": float(item.get("recall_hit", 0.0) or 0.0),
            "dependency_recall": float(item.get("dependency_recall", 0.0) or 0.0),
        }
    return rows


def _is_volatile_case_key(key: str) -> bool:
    normalized = str(key or "").strip()
    if not normalized:
        return False
    return normalized == "latency_ms" or normalized.endswith("_latency_ms")


def _normalize_case_value(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            name = str(key or "")
            if _is_volatile_case_key(name):
                continue
            normalized[name] = _normalize_case_value(value[key])
        return normalized
    if isinstance(value, list):
        return [_normalize_case_value(item) for item in value]
    if isinstance(value, float):
        return round(float(value), 6)
    return value


def read_benchmark_case_fingerprints(results_path: Path) -> dict[str, Any]:
    payload = read_benchmark_results(results_path)
    cases_raw = payload.get("cases")
    cases = cases_raw if isinstance(cases_raw, list) else []
    fingerprints: dict[str, Any] = {}
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            continue
        fingerprints[case_id] = _normalize_case_value(item)
    return fingerprints


def read_benchmark_case_routing_source(results_path: Path) -> str:
    payload = read_benchmark_results(results_path)
    cases_raw = payload.get("cases")
    cases = cases_raw if isinstance(cases_raw, list) else []
    sources: list[str] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        plan = item.get("plan")
        if not isinstance(plan, dict):
            continue
        skills = plan.get("skills")
        if not isinstance(skills, dict):
            continue
        source = str(skills.get("routing_source") or "").strip()
        if source and source not in sources:
            sources.append(source)
    if len(sources) == 1:
        return sources[0]
    if not sources:
        return ""
    return ",".join(sources)


def read_benchmark_comparison_lane_metrics(
    results_path: Path,
    *,
    lane: str,
) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    summary_raw = payload.get("comparison_lane_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    lanes_raw = summary.get("lanes")
    lanes = lanes_raw if isinstance(lanes_raw, list) else []
    for item in lanes:
        if not isinstance(item, dict):
            continue
        if str(item.get("comparison_lane") or "").strip() != lane:
            continue
        metrics: dict[str, float] = {}
        for key, value in item.items():
            if not isinstance(key, str) or key == "comparison_lane":
                continue
            try:
                metrics[key] = float(value or 0.0)
            except Exception:
                continue
        return metrics
    return {}


def _normalize_summary_mapping(summary_raw: Any) -> dict[str, Any]:
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return {}

    normalized: dict[str, Any] = {}
    for key, value in summary.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, bool):
            normalized[key] = bool(value)
            continue
        if isinstance(value, (int, float)):
            normalized[key] = float(value)
            continue
        if isinstance(value, list):
            normalized[key] = [str(item) for item in value if str(item).strip()]
            continue
        normalized[key] = value
    return normalized


def read_benchmark_retrieval_control_plane_gate_summary(
    results_path: Path,
) -> dict[str, Any]:
    payload = read_benchmark_results(results_path)
    return _normalize_summary_mapping(payload.get("retrieval_control_plane_gate_summary"))


def read_benchmark_retrieval_frontier_gate_summary(
    results_path: Path,
) -> dict[str, Any]:
    payload = read_benchmark_results(results_path)
    return _normalize_summary_mapping(payload.get("retrieval_frontier_gate_summary"))


def read_benchmark_repomap_seed_summary(results_path: Path) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    summary_raw = payload.get("repomap_seed_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

    metric_aliases = {
        "worktree_seed_count_mean": (
            "worktree_seed_count_mean",
            "repomap_worktree_seed_count_mean",
        ),
        "subgraph_seed_count_mean": (
            "subgraph_seed_count_mean",
            "repomap_subgraph_seed_count_mean",
        ),
        "seed_candidates_count_mean": (
            "seed_candidates_count_mean",
            "repomap_seed_candidates_count_mean",
        ),
        "cache_hit_ratio": ("cache_hit_ratio", "repomap_cache_hit_ratio"),
        "precompute_hit_ratio": (
            "precompute_hit_ratio",
            "repomap_precompute_hit_ratio",
        ),
    }
    normalized: dict[str, float] = {}
    for key, aliases in metric_aliases.items():
        raw_value: Any = None
        for alias in aliases:
            if alias in summary:
                raw_value = summary.get(alias)
                break
        if raw_value is None:
            for alias in aliases:
                if alias in metrics:
                    raw_value = metrics.get(alias)
                    break
        if raw_value is None:
            continue
        try:
            normalized[key] = float(raw_value or 0.0)
        except Exception:
            continue
    return normalized


def read_benchmark_validation_probe_summary(results_path: Path) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    summary_raw = payload.get("validation_probe_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

    metric_aliases = {
        "validation_test_count": ("validation_test_count",),
        "probe_enabled_ratio": (
            "probe_enabled_ratio",
            "validation_probe_enabled_ratio",
        ),
        "probe_executed_count_mean": (
            "probe_executed_count_mean",
            "validation_probe_executed_count_mean",
        ),
        "probe_failure_rate": (
            "probe_failure_rate",
            "validation_probe_failure_rate",
        ),
    }
    normalized: dict[str, float] = {}
    for key, aliases in metric_aliases.items():
        raw_value: Any = None
        for alias in aliases:
            if alias in summary:
                raw_value = summary.get(alias)
                break
        if raw_value is None:
            for alias in aliases:
                if alias in metrics:
                    raw_value = metrics.get(alias)
                    break
        if raw_value is None:
            continue
        try:
            normalized[key] = float(raw_value or 0.0)
        except Exception:
            continue
    return normalized


def read_benchmark_source_plan_validation_feedback_summary(
    results_path: Path,
) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    summary_raw = payload.get("source_plan_validation_feedback_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

    metric_aliases = {
        "present_ratio": (
            "present_ratio",
            "source_plan_validation_feedback_present_ratio",
        ),
        "issue_count_mean": (
            "issue_count_mean",
            "source_plan_validation_feedback_issue_count_mean",
        ),
        "failure_rate": (
            "failure_rate",
            "source_plan_validation_feedback_failure_rate",
        ),
        "probe_issue_count_mean": (
            "probe_issue_count_mean",
            "source_plan_validation_feedback_probe_issue_count_mean",
        ),
        "probe_executed_count_mean": (
            "probe_executed_count_mean",
            "source_plan_validation_feedback_probe_executed_count_mean",
        ),
        "probe_failure_rate": (
            "probe_failure_rate",
            "source_plan_validation_feedback_probe_failure_rate",
        ),
        "selected_test_count_mean": (
            "selected_test_count_mean",
            "source_plan_validation_feedback_selected_test_count_mean",
        ),
        "executed_test_count_mean": (
            "executed_test_count_mean",
            "source_plan_validation_feedback_executed_test_count_mean",
        ),
    }
    normalized: dict[str, float] = {}
    for key, aliases in metric_aliases.items():
        raw_value: Any = None
        for alias in aliases:
            if alias in summary:
                raw_value = summary.get(alias)
                break
        if raw_value is None:
            for alias in aliases:
                if alias in metrics:
                    raw_value = metrics.get(alias)
                    break
        if raw_value is None:
            continue
        try:
            normalized[key] = float(raw_value or 0.0)
        except Exception:
            continue
    return normalized


def read_benchmark_deep_symbol_summary(results_path: Path) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    summary_raw = payload.get("deep_symbol_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

    metric_aliases = {
        "case_count": ("case_count", "deep_symbol_case_count"),
        "recall": ("recall", "deep_symbol_case_recall"),
    }
    normalized: dict[str, float] = {}
    for key, aliases in metric_aliases.items():
        raw_value: Any = None
        for alias in aliases:
            if alias in summary:
                raw_value = summary.get(alias)
                break
        if raw_value is None:
            for alias in aliases:
                if alias in metrics:
                    raw_value = metrics.get(alias)
                    break
        if raw_value is None:
            continue
        try:
            normalized[key] = float(raw_value or 0.0)
        except Exception:
            continue
    return normalized


def read_benchmark_native_scip_summary(results_path: Path) -> dict[str, float]:
    payload = read_benchmark_results(results_path)
    summary_raw = payload.get("native_scip_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}

    metric_aliases = {
        "loaded_rate": ("loaded_rate", "native_scip_loaded_rate"),
        "document_count_mean": (
            "document_count_mean",
            "native_scip_document_count_mean",
        ),
        "definition_occurrence_count_mean": (
            "definition_occurrence_count_mean",
            "native_scip_definition_occurrence_count_mean",
        ),
        "reference_occurrence_count_mean": (
            "reference_occurrence_count_mean",
            "native_scip_reference_occurrence_count_mean",
        ),
        "symbol_definition_count_mean": (
            "symbol_definition_count_mean",
            "native_scip_symbol_definition_count_mean",
        ),
    }
    normalized: dict[str, float] = {}
    for key, aliases in metric_aliases.items():
        raw_value: Any = None
        for alias in aliases:
            if alias in summary:
                raw_value = summary.get(alias)
                break
        if raw_value is None:
            for alias in aliases:
                if alias in metrics:
                    raw_value = metrics.get(alias)
                    break
        if raw_value is None:
            continue
        try:
            normalized[key] = float(raw_value or 0.0)
        except Exception:
            continue
    return normalized


__all__ = [
    "CommandResult",
    "load_yaml",
    "read_benchmark_case_fingerprints",
    "read_benchmark_case_routing_source",
    "read_benchmark_case_rows",
    "read_benchmark_comparison_lane_metrics",
    "read_benchmark_deep_symbol_summary",
    "read_benchmark_native_scip_summary",
    "read_benchmark_retrieval_control_plane_gate_summary",
    "read_benchmark_retrieval_frontier_gate_summary",
    "read_benchmark_repomap_seed_summary",
    "read_benchmark_source_plan_validation_feedback_summary",
    "read_benchmark_validation_probe_summary",
    "read_benchmark_metrics",
    "read_benchmark_results",
    "require_success",
    "run_command",
]
