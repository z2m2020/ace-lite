from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.problem_surface import validate_problem_surface_payload
from ace_lite.problem_surface_schema import PROBLEM_SURFACE_SCHEMA_VERSION

PQ_SURFACE_SPECS: dict[str, dict[str, Any]] = {
    "PQ-001": {
        "title": "retrieval_quality",
        "metric_names": ("task_success_rate", "precision_at_k", "noise_rate"),
    },
    "PQ-002": {
        "title": "quick_to_full_upgrade_worthiness",
        "metric_names": ("quick_to_full_upgrade_rate",),
    },
    "PQ-003": {
        "title": "evidence_strength_interpretability",
        "metric_names": ("evidence_strength_score",),
    },
    "PQ-004": {
        "title": "validation_evidence_sufficiency",
        "metric_names": ("validation_coverage", "validation_test_count"),
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
    except Exception:
        return str(source), {}
    return str(source), payload if isinstance(payload, dict) else {}


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_results_metrics(payload: dict[str, Any]) -> dict[str, float]:
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    normalized: dict[str, float] = {}
    for key, value in metrics.items():
        number = _coerce_float(value)
        if number is not None:
            normalized[str(key)] = number
    return normalized


def _coerce_freeze_metrics(payload: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}

    task_success_mean = _coerce_float(payload.get("task_success_mean"))
    if task_success_mean is not None:
        normalized["task_success_rate"] = task_success_mean

    mapping_sections = {
        "retrieval_metrics_mean": (
            "precision_at_k",
            "noise_rate",
            "latency_p95_ms",
            "chunk_hit_at_k",
        ),
        "latency_metrics_mean": ("latency_p95_ms", "repomap_latency_p95_ms"),
        "memory_metrics_mean": (
            "notes_hit_ratio",
            "profile_selected_mean",
            "capture_trigger_ratio",
        ),
        "embedding_metrics_mean": (
            "embedding_similarity_mean",
            "embedding_rerank_ratio",
            "embedding_cache_hit_ratio",
            "embedding_fallback_ratio",
            "embedding_enabled_ratio",
        ),
    }

    for section_name, metric_names in mapping_sections.items():
        section_raw = payload.get(section_name)
        section = section_raw if isinstance(section_raw, dict) else {}
        for metric_name in metric_names:
            number = _coerce_float(section.get(metric_name))
            if number is not None:
                normalized[metric_name] = number

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
