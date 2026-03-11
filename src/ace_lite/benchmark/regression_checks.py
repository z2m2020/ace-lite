"""Regression threshold and failure-detection helpers."""

from __future__ import annotations

from typing import Any

REGRESSION_THRESHOLD_PROFILES: dict[str, dict[str, float]] = {
    "default": {
        "precision_tolerance": 0.03,
        "noise_tolerance": 0.0,
        "latency_growth_factor": 1.2,
        "dependency_recall_floor": 0.0,
        "chunk_hit_tolerance": 0.05,
        "chunk_budget_growth_factor": 1.25,
        "validation_test_growth_factor": 1.50,
        "notes_hit_tolerance": 0.10,
        "profile_selected_tolerance": 1.0,
        "capture_trigger_tolerance": 0.20,
        "embedding_similarity_tolerance": 0.05,
        "embedding_rerank_ratio_tolerance": 0.10,
        "embedding_cache_hit_tolerance": 0.20,
        "embedding_fallback_tolerance": 0.10,
    },
    "strict": {
        "precision_tolerance": 0.01,
        "noise_tolerance": 0.0,
        "latency_growth_factor": 1.1,
        "dependency_recall_floor": 0.8,
        "chunk_hit_tolerance": 0.02,
        "chunk_budget_growth_factor": 1.15,
        "validation_test_growth_factor": 1.30,
        "notes_hit_tolerance": 0.05,
        "profile_selected_tolerance": 0.5,
        "capture_trigger_tolerance": 0.10,
        "embedding_similarity_tolerance": 0.02,
        "embedding_rerank_ratio_tolerance": 0.05,
        "embedding_cache_hit_tolerance": 0.10,
        "embedding_fallback_tolerance": 0.05,
    },
    "relaxed": {
        "precision_tolerance": 0.05,
        "noise_tolerance": 0.02,
        "latency_growth_factor": 1.35,
        "dependency_recall_floor": 0.0,
        "chunk_hit_tolerance": 0.08,
        "chunk_budget_growth_factor": 1.40,
        "validation_test_growth_factor": 2.00,
        "notes_hit_tolerance": 0.20,
        "profile_selected_tolerance": 2.0,
        "capture_trigger_tolerance": 0.30,
        "embedding_similarity_tolerance": 0.10,
        "embedding_rerank_ratio_tolerance": 0.20,
        "embedding_cache_hit_tolerance": 0.35,
        "embedding_fallback_tolerance": 0.20,
    },
}


def resolve_regression_thresholds(
    *,
    profile: str,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    normalized = str(profile or "default").strip().lower()
    if normalized not in REGRESSION_THRESHOLD_PROFILES:
        raise ValueError(f"unsupported threshold profile: {profile}")

    thresholds = dict(REGRESSION_THRESHOLD_PROFILES[normalized])
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        if key in thresholds:
            thresholds[key] = float(value)
    return thresholds


def detect_regression(
    *,
    current: dict[str, float],
    baseline: dict[str, float],
    precision_tolerance: float = 0.03,
    noise_tolerance: float = 0.0,
    latency_growth_factor: float = 1.2,
    dependency_recall_floor: float = 0.0,
    chunk_hit_tolerance: float = 0.05,
    chunk_budget_growth_factor: float = 1.25,
    validation_test_growth_factor: float = 1.50,
    notes_hit_tolerance: float = 0.10,
    profile_selected_tolerance: float = 1.0,
    capture_trigger_tolerance: float = 0.20,
    embedding_similarity_tolerance: float = 0.05,
    embedding_rerank_ratio_tolerance: float = 0.10,
    embedding_cache_hit_tolerance: float = 0.20,
    embedding_fallback_tolerance: float = 0.10,
) -> dict[str, Any]:
    current_precision = float(current.get("precision_at_k", 0.0))
    baseline_precision = float(baseline.get("precision_at_k", 0.0))
    current_noise = float(current.get("noise_rate", 0.0))
    baseline_noise = float(baseline.get("noise_rate", 0.0))
    baseline_latency = float(baseline.get("latency_p95_ms", 0.0))
    current_latency = float(current.get("latency_p95_ms", 0.0))
    current_dependency_recall = float(current.get("dependency_recall", 0.0))
    current_chunk_hit = float(current.get("chunk_hit_at_k", 0.0))
    baseline_chunk_hit = float(baseline.get("chunk_hit_at_k", 0.0))
    current_chunk_budget = float(current.get("chunk_budget_used", 0.0))
    baseline_chunk_budget = float(baseline.get("chunk_budget_used", 0.0))
    current_validation_test_count = float(current.get("validation_test_count", 0.0))
    baseline_validation_test_count = float(baseline.get("validation_test_count", 0.0))
    current_notes_hit_ratio = float(current.get("notes_hit_ratio", 0.0))
    baseline_notes_hit_ratio = float(baseline.get("notes_hit_ratio", 0.0))
    current_profile_selected = float(current.get("profile_selected_mean", 0.0))
    baseline_profile_selected = float(baseline.get("profile_selected_mean", 0.0))
    current_capture_trigger_ratio = float(current.get("capture_trigger_ratio", 0.0))
    baseline_capture_trigger_ratio = float(baseline.get("capture_trigger_ratio", 0.0))
    current_embedding_similarity = float(current.get("embedding_similarity_mean", 0.0))
    baseline_embedding_similarity = float(
        baseline.get("embedding_similarity_mean", 0.0)
    )
    current_embedding_rerank_ratio = float(current.get("embedding_rerank_ratio", 0.0))
    baseline_embedding_rerank_ratio = float(
        baseline.get("embedding_rerank_ratio", 0.0)
    )
    current_embedding_cache_hit = float(current.get("embedding_cache_hit_ratio", 0.0))
    baseline_embedding_cache_hit = float(
        baseline.get("embedding_cache_hit_ratio", 0.0)
    )
    current_embedding_fallback = float(current.get("embedding_fallback_ratio", 0.0))
    baseline_embedding_fallback = float(
        baseline.get("embedding_fallback_ratio", 0.0)
    )

    precision_threshold = baseline_precision - precision_tolerance
    noise_threshold = baseline_noise + noise_tolerance
    latency_threshold = (
        baseline_latency * latency_growth_factor if baseline_latency > 0 else 0.0
    )
    chunk_hit_threshold = baseline_chunk_hit - chunk_hit_tolerance
    chunk_budget_threshold = (
        baseline_chunk_budget * chunk_budget_growth_factor
        if baseline_chunk_budget > 0
        else 0.0
    )
    validation_test_threshold = (
        baseline_validation_test_count * validation_test_growth_factor
        if baseline_validation_test_count > 0
        else 0.0
    )
    notes_hit_threshold = baseline_notes_hit_ratio - notes_hit_tolerance
    profile_selected_threshold = baseline_profile_selected - profile_selected_tolerance
    capture_trigger_threshold = (
        baseline_capture_trigger_ratio - capture_trigger_tolerance
    )
    embedding_similarity_threshold = (
        baseline_embedding_similarity - embedding_similarity_tolerance
    )
    embedding_rerank_ratio_threshold = (
        baseline_embedding_rerank_ratio - embedding_rerank_ratio_tolerance
    )
    embedding_cache_hit_threshold = (
        baseline_embedding_cache_hit - embedding_cache_hit_tolerance
    )
    embedding_fallback_threshold = (
        baseline_embedding_fallback + embedding_fallback_tolerance
    )

    precision_regressed = current_precision < precision_threshold
    noise_regressed = current_noise > noise_threshold
    latency_regressed = baseline_latency > 0 and current_latency > latency_threshold
    dependency_regressed = current_dependency_recall < dependency_recall_floor
    chunk_hit_regressed = current_chunk_hit < chunk_hit_threshold
    chunk_budget_regressed = (
        baseline_chunk_budget > 0 and current_chunk_budget > chunk_budget_threshold
    )
    validation_test_regressed = (
        baseline_validation_test_count > 0
        and current_validation_test_count > validation_test_threshold
    )
    notes_hit_regressed = current_notes_hit_ratio < notes_hit_threshold
    profile_selected_regressed = current_profile_selected < profile_selected_threshold
    capture_trigger_regressed = (
        current_capture_trigger_ratio < capture_trigger_threshold
    )
    embedding_similarity_regressed = (
        baseline_embedding_similarity > 0.0
        and current_embedding_similarity < embedding_similarity_threshold
    )
    embedding_rerank_ratio_regressed = (
        baseline_embedding_rerank_ratio > 0.0
        and current_embedding_rerank_ratio < embedding_rerank_ratio_threshold
    )
    embedding_cache_hit_regressed = (
        baseline_embedding_cache_hit > 0.0
        and current_embedding_cache_hit < embedding_cache_hit_threshold
    )
    embedding_fallback_regressed = (
        current_embedding_fallback > embedding_fallback_threshold
    )

    failed_checks: list[str] = []
    failed_thresholds: list[dict[str, Any]] = []

    if precision_regressed:
        failed_checks.append("precision_at_k")
        failed_thresholds.append(
            {
                "metric": "precision_at_k",
                "operator": "<",
                "current": current_precision,
                "threshold": precision_threshold,
            }
        )
    if noise_regressed:
        failed_checks.append("noise_rate")
        failed_thresholds.append(
            {
                "metric": "noise_rate",
                "operator": ">",
                "current": current_noise,
                "threshold": noise_threshold,
            }
        )
    if latency_regressed:
        failed_checks.append("latency_p95_ms")
        failed_thresholds.append(
            {
                "metric": "latency_p95_ms",
                "operator": ">",
                "current": current_latency,
                "threshold": latency_threshold,
            }
        )
    if dependency_regressed:
        failed_checks.append("dependency_recall")
        failed_thresholds.append(
            {
                "metric": "dependency_recall",
                "operator": "<",
                "current": current_dependency_recall,
                "threshold": float(dependency_recall_floor),
            }
        )
    if chunk_hit_regressed:
        failed_checks.append("chunk_hit_at_k")
        failed_thresholds.append(
            {
                "metric": "chunk_hit_at_k",
                "operator": "<",
                "current": current_chunk_hit,
                "threshold": chunk_hit_threshold,
            }
        )
    if chunk_budget_regressed:
        failed_checks.append("chunk_budget_used")
        failed_thresholds.append(
            {
                "metric": "chunk_budget_used",
                "operator": ">",
                "current": current_chunk_budget,
                "threshold": chunk_budget_threshold,
            }
        )
    if validation_test_regressed:
        failed_checks.append("validation_test_count")
        failed_thresholds.append(
            {
                "metric": "validation_test_count",
                "operator": ">",
                "current": current_validation_test_count,
                "threshold": validation_test_threshold,
            }
        )
    if notes_hit_regressed:
        failed_checks.append("notes_hit_ratio")
        failed_thresholds.append(
            {
                "metric": "notes_hit_ratio",
                "operator": "<",
                "current": current_notes_hit_ratio,
                "threshold": notes_hit_threshold,
            }
        )
    if profile_selected_regressed:
        failed_checks.append("profile_selected_mean")
        failed_thresholds.append(
            {
                "metric": "profile_selected_mean",
                "operator": "<",
                "current": current_profile_selected,
                "threshold": profile_selected_threshold,
            }
        )
    if capture_trigger_regressed:
        failed_checks.append("capture_trigger_ratio")
        failed_thresholds.append(
            {
                "metric": "capture_trigger_ratio",
                "operator": "<",
                "current": current_capture_trigger_ratio,
                "threshold": capture_trigger_threshold,
            }
        )
    if embedding_similarity_regressed:
        failed_checks.append("embedding_similarity_mean")
        failed_thresholds.append(
            {
                "metric": "embedding_similarity_mean",
                "operator": "<",
                "current": current_embedding_similarity,
                "threshold": embedding_similarity_threshold,
            }
        )
    if embedding_rerank_ratio_regressed:
        failed_checks.append("embedding_rerank_ratio")
        failed_thresholds.append(
            {
                "metric": "embedding_rerank_ratio",
                "operator": "<",
                "current": current_embedding_rerank_ratio,
                "threshold": embedding_rerank_ratio_threshold,
            }
        )
    if embedding_cache_hit_regressed:
        failed_checks.append("embedding_cache_hit_ratio")
        failed_thresholds.append(
            {
                "metric": "embedding_cache_hit_ratio",
                "operator": "<",
                "current": current_embedding_cache_hit,
                "threshold": embedding_cache_hit_threshold,
            }
        )
    if embedding_fallback_regressed:
        failed_checks.append("embedding_fallback_ratio")
        failed_thresholds.append(
            {
                "metric": "embedding_fallback_ratio",
                "operator": ">",
                "current": current_embedding_fallback,
                "threshold": embedding_fallback_threshold,
            }
        )

    return {
        "regressed": bool(failed_checks),
        "failed_checks": failed_checks,
        "failed_thresholds": failed_thresholds,
    }


__all__ = [
    "REGRESSION_THRESHOLD_PROFILES",
    "detect_regression",
    "resolve_regression_thresholds",
]
