from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.problem_surface import validate_problem_surface_payload
from ace_lite.problem_surface_schema import PROBLEM_SURFACE_SCHEMA_VERSION

"""Read benchmark and freeze artifacts into a report-only problem surface payload.

This module intentionally reuses the existing ``problem_surface_v1`` envelope and
adds PQ-oriented entries under ``surfaces``. It supports:

- benchmark ``results.json`` and ``summary.json`` metrics payloads
- nested benchmark summary sections used by validation-rich artifacts
- release-freeze ``freeze_regression.json`` payloads consumed by the repo's
  freeze trend tooling
"""

PQ_SURFACE_SPECS: dict[str, dict[str, Any]] = {
    "PQ-001": {
        "title": "retrieval_quality",
        "metric_names": ("task_success_rate", "precision_at_k", "noise_rate"),
    },
    "PQ-002": {
        "title": "quick_to_full_upgrade_worthiness",
        "metric_names": (
            "quick_to_full_upgrade_rate",
            "adaptive_router_shadow_coverage",
            "risk_upgrade_precision_gain",
        ),
    },
    "PQ-003": {
        "title": "evidence_strength_interpretability",
        "metric_names": (
            "evidence_strength_score",
            "deep_symbol_case_recall",
            "native_scip_loaded_rate",
        ),
    },
    "PQ-004": {
        "title": "validation_evidence_sufficiency",
        "metric_names": (
            "validation_coverage",
            "validation_test_count",
            "probe_enabled_ratio",
            "feedback_present_ratio",
            "feedback_executed_test_count_mean",
        ),
    },
    "PQ-005": {
        "title": "memory_coldstart_usefulness",
        "metric_names": (
            "memory_coldstart_usefulness",
            "notes_hit_ratio",
            "ltm_effective_hit_rate",
        ),
    },
    "PQ-006": {
        "title": "feedback_capture_loop",
        "metric_names": (
            "feedback_capture_rate",
            "capture_trigger_ratio",
            "dev_issue_capture_rate",
            "issue_to_benchmark_case_conversion_rate",
        ),
    },
    "PQ-007": {
        "title": "doctor_runtime_drift_control",
        "metric_names": ("doctor_drift_detected",),
    },
    "PQ-008": {
        "title": "cross_platform_smoke_stability",
        "metric_names": ("smoke_pass_rate",),
    },
    "PQ-009": {
        "title": "typed_contracts_coverage",
        "metric_names": ("typed_contracts_coverage",),
    },
    "PQ-010": {
        "title": "wave_throughput",
        "metric_names": ("wave_throughput_p50",),
    },
}

LOWER_IS_BETTER = {"noise_rate", "doctor_drift_detected"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str(value: Any) -> str:
    return str(value) if value is not None else ""


def _load_json(path: str | Path | None) -> tuple[str, dict[str, Any]]:
    if path is None:
        return "", {}

    source = Path(path)
    if not source.exists() or not source.is_file():
        return str(source), {}

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return str(source), {}
    return str(source), payload if isinstance(payload, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _copy_metrics(
    normalized: dict[str, float],
    source: dict[str, Any],
    *metric_names: str,
) -> None:
    for metric_name in metric_names:
        number = _coerce_float(source.get(metric_name))
        if number is not None:
            normalized[metric_name] = number


def _coerce_results_metrics(payload: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}

    metrics = _dict(payload.get("metrics"))
    for key, value in metrics.items():
        number = _coerce_float(value)
        if number is not None:
            normalized[str(key)] = number

    control_plane = _dict(payload.get("retrieval_control_plane_gate_summary"))
    frontier = _dict(payload.get("retrieval_frontier_gate_summary"))
    validation_probe = _dict(payload.get("validation_probe_summary"))
    source_plan_feedback = _dict(payload.get("source_plan_validation_feedback_summary"))
    deep_symbol = _dict(payload.get("deep_symbol_summary"))
    native_scip = _dict(payload.get("native_scip_summary"))

    _copy_metrics(
        normalized,
        control_plane,
        "adaptive_router_shadow_coverage",
        "risk_upgrade_precision_gain",
    )
    _copy_metrics(
        normalized,
        frontier,
        "deep_symbol_case_recall",
        "native_scip_loaded_rate",
        "precision_at_k",
        "noise_rate",
    )
    _copy_metrics(normalized, validation_probe, "validation_test_count", "probe_enabled_ratio")
    _copy_metrics(normalized, source_plan_feedback, "executed_test_count_mean")

    feedback_present_ratio = _coerce_float(source_plan_feedback.get("present_ratio"))
    if feedback_present_ratio is not None:
        normalized["feedback_present_ratio"] = feedback_present_ratio
        normalized.setdefault("feedback_capture_rate", feedback_present_ratio)

    feedback_executed_test_count_mean = _coerce_float(
        source_plan_feedback.get("executed_test_count_mean")
    )
    if feedback_executed_test_count_mean is not None:
        normalized["feedback_executed_test_count_mean"] = feedback_executed_test_count_mean

    deep_symbol_recall = _coerce_float(deep_symbol.get("recall"))
    if deep_symbol_recall is not None:
        normalized.setdefault("deep_symbol_case_recall", deep_symbol_recall)

    native_scip_loaded_rate = _coerce_float(native_scip.get("loaded_rate"))
    if native_scip_loaded_rate is not None:
        normalized.setdefault("native_scip_loaded_rate", native_scip_loaded_rate)

    return normalized


def _coerce_freeze_metrics(payload: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}

    payload = _dict(payload)

    task_success_mean = _coerce_float(payload.get("task_success_mean"))
    if task_success_mean is not None:
        normalized["task_success_rate"] = task_success_mean

    _copy_metrics(
        normalized,
        _dict(payload.get("retrieval_metrics_mean")),
        "precision_at_k",
        "noise_rate",
        "latency_p95_ms",
        "chunk_hit_at_k",
    )
    _copy_metrics(
        normalized,
        _dict(payload.get("latency_metrics_mean")),
        "latency_p95_ms",
        "repomap_latency_p95_ms",
    )
    _copy_metrics(
        normalized,
        _dict(payload.get("memory_metrics_mean")),
        "notes_hit_ratio",
        "profile_selected_mean",
        "capture_trigger_ratio",
    )
    _copy_metrics(
        normalized,
        _dict(payload.get("embedding_metrics_mean")),
        "embedding_similarity_mean",
        "embedding_rerank_ratio",
        "embedding_cache_hit_ratio",
        "embedding_fallback_ratio",
        "embedding_enabled_ratio",
    )

    tabiv3_means = _dict(_dict(payload.get("tabiv3_matrix_summary")).get("latency_metrics_mean"))
    concept_metrics = _dict(_dict(payload.get("concept_gate")).get("metrics"))
    embedding_means = _dict(_dict(payload.get("embedding_gate")).get("means"))
    validation_rich = _dict(payload.get("validation_rich_benchmark"))
    control_plane = _dict(validation_rich.get("retrieval_control_plane_gate_summary"))
    frontier = _dict(validation_rich.get("retrieval_frontier_gate_summary"))
    validation_probe = _dict(validation_rich.get("validation_probe_summary"))
    source_plan_feedback = _dict(validation_rich.get("source_plan_validation_feedback_summary"))
    deep_symbol = _dict(validation_rich.get("deep_symbol_summary"))
    native_scip = _dict(validation_rich.get("native_scip_summary"))

    _copy_metrics(normalized, tabiv3_means, "latency_p95_ms", "repomap_latency_p95_ms")
    _copy_metrics(normalized, concept_metrics, "precision_at_k", "noise_rate")
    _copy_metrics(normalized, embedding_means, "embedding_enabled_ratio")
    _copy_metrics(
        normalized,
        control_plane,
        "adaptive_router_shadow_coverage",
        "risk_upgrade_precision_gain",
    )
    _copy_metrics(
        normalized,
        frontier,
        "deep_symbol_case_recall",
        "native_scip_loaded_rate",
        "precision_at_k",
        "noise_rate",
    )
    _copy_metrics(normalized, validation_probe, "validation_test_count", "probe_enabled_ratio")
    _copy_metrics(normalized, source_plan_feedback, "executed_test_count_mean")

    feedback_present_ratio = _coerce_float(source_plan_feedback.get("present_ratio"))
    if feedback_present_ratio is not None:
        normalized["feedback_present_ratio"] = feedback_present_ratio
        normalized.setdefault("feedback_capture_rate", feedback_present_ratio)

    feedback_executed_test_count_mean = _coerce_float(
        source_plan_feedback.get("executed_test_count_mean")
    )
    if feedback_executed_test_count_mean is not None:
        normalized["feedback_executed_test_count_mean"] = feedback_executed_test_count_mean

    deep_symbol_recall = _coerce_float(deep_symbol.get("recall"))
    if deep_symbol_recall is not None:
        normalized.setdefault("deep_symbol_case_recall", deep_symbol_recall)

    native_scip_loaded_rate = _coerce_float(native_scip.get("loaded_rate"))
    if native_scip_loaded_rate is not None:
        normalized.setdefault("native_scip_loaded_rate", native_scip_loaded_rate)

    if "validation_coverage" not in normalized:
        validation_test_count = normalized.get("validation_test_count")
        if validation_test_count is not None:
            normalized["validation_coverage"] = validation_test_count

    return normalized


def _expected_direction(metric_name: str) -> str:
    return "lower_is_better" if metric_name in LOWER_IS_BETTER else "higher_is_better"


def build_problem_surface_from_benchmark_artifacts(
    *,
    results_path: str | Path | None = None,
    freeze_regression_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    git_sha: str = "",
    phase: str = "problem_discovery",
    generated_at: str | None = None,
) -> dict[str, Any]:
    results_artifact_path, results_payload = _load_json(results_path)
    freeze_artifact_path, freeze_payload = _load_json(freeze_regression_path)
    summary_artifact_path, summary_payload = _load_json(summary_path)

    artifact_metrics: list[tuple[str, dict[str, float]]] = [
        (results_artifact_path, _coerce_results_metrics(results_payload)),
        (freeze_artifact_path, _coerce_freeze_metrics(freeze_payload)),
        (summary_artifact_path, _coerce_results_metrics(summary_payload)),
    ]

    surfaces: dict[str, Any] = {}
    warnings: list[str] = []
    for artifact_path, metrics in artifact_metrics:
        if artifact_path and not metrics:
            warnings.append(f"no_metrics_loaded:{artifact_path}")

    for problem_id, spec in PQ_SURFACE_SPECS.items():
        metric_entries: list[dict[str, Any]] = []
        artifact_paths: list[str] = []
        seen_artifact_paths: set[str] = set()
        missing_metric_names: list[str] = []

        for metric_name in spec["metric_names"]:
            matched = False
            for artifact_path, metrics in artifact_metrics:
                if not artifact_path or metric_name not in metrics:
                    continue
                matched = True
                metric_entries.append(
                    {
                        "metric_name": metric_name,
                        "value": metrics[metric_name],
                        "expected_direction": _expected_direction(metric_name),
                        "artifact_path": artifact_path,
                    }
                )
                if artifact_path not in seen_artifact_paths:
                    artifact_paths.append(artifact_path)
                    seen_artifact_paths.add(artifact_path)
            if not matched:
                missing_metric_names.append(metric_name)

        surfaces[problem_id] = {
            "problem_id": problem_id,
            "title": spec["title"],
            "status": "observed" if metric_entries else "missing",
            "report_only": True,
            "metric_entries": metric_entries,
            "artifact_paths": artifact_paths,
            "missing_metric_names": missing_metric_names,
        }

    payload = {
        "schema_version": PROBLEM_SURFACE_SCHEMA_VERSION,
        "generated_at": _str(generated_at) or _utc_now(),
        "git_sha": _str(git_sha),
        "phase": _str(phase) or "problem_discovery",
        "inputs": {
            "results_json": {
                "present": bool(results_payload),
                "path": results_artifact_path,
            },
            "freeze_regression_json": {
                "present": bool(freeze_payload),
                "path": freeze_artifact_path,
            },
            "summary_json": {
                "present": bool(summary_payload),
                "path": summary_artifact_path,
            },
        },
        "surfaces": surfaces,
        "warnings": warnings,
    }
    return validate_problem_surface_payload(payload)


__all__ = [
    "PQ_SURFACE_SPECS",
    "build_problem_surface_from_benchmark_artifacts",
]
