"""Expectation helpers for benchmark case evaluation."""

from __future__ import annotations

from typing import Any


def coerce_task_success_config(case: dict[str, Any]) -> dict[str, Any]:
    raw = case.get("task_success")
    config = raw if isinstance(raw, dict) else {}

    mode = str(config.get("mode") or "").strip().lower() or "positive"
    if mode not in {"positive", "negative_control"}:
        mode = "positive"

    require_recall_hit = bool(config.get("require_recall_hit", True))
    try:
        min_validation_tests = max(0, int(config.get("min_validation_tests", 0) or 0))
    except Exception:
        min_validation_tests = 0

    return {
        "mode": mode,
        "require_recall_hit": require_recall_hit,
        "min_validation_tests": min_validation_tests,
    }


def evaluate_task_success(
    *,
    case: dict[str, Any],
    expected: list[str],
    recall_hit: float,
    validation_tests: list[Any],
) -> dict[str, Any]:
    config = coerce_task_success_config(case)
    failed_checks: list[str] = []
    if config["require_recall_hit"] and expected and float(recall_hit) < 1.0:
        failed_checks.append("recall_hit")
    if len(validation_tests) < int(config["min_validation_tests"]):
        failed_checks.append("validation_tests")
    return {
        "config": config,
        "failed_checks": failed_checks,
        "hit": 1.0 if not failed_checks else 0.0,
    }


def _coerce_chunk_guard_expectation(case: dict[str, Any]) -> dict[str, Any]:
    raw = case.get("chunk_guard_expectation")
    config = raw if isinstance(raw, dict) else {}

    scenario = str(config.get("scenario") or "").strip().lower()
    expected_retained_raw = config.get("expected_retained_refs", [])
    expected_filtered_raw = config.get("expected_filtered_refs", [])
    expected_retained_refs = (
        [str(item).strip() for item in expected_retained_raw if str(item).strip()]
        if isinstance(expected_retained_raw, list)
        else []
    )
    expected_filtered_refs = (
        [str(item).strip() for item in expected_filtered_raw if str(item).strip()]
        if isinstance(expected_filtered_raw, list)
        else []
    )

    applicable = bool(scenario) and (
        bool(expected_retained_refs) or bool(expected_filtered_refs)
    )
    return {
        "applicable": applicable,
        "scenario": scenario if applicable else "",
        "expected_retained_refs": expected_retained_refs,
        "expected_filtered_refs": expected_filtered_refs,
    }


def evaluate_chunk_guard_expectation(
    *,
    case: dict[str, Any],
    chunk_guard_payload: dict[str, Any],
) -> dict[str, Any]:
    expectation = _coerce_chunk_guard_expectation(case)
    if not expectation["applicable"]:
        return {
            "applicable": False,
            "scenario": "",
            "expected_retained_refs": [],
            "expected_filtered_refs": [],
            "retained_hits": [],
            "filtered_hits": [],
            "expected_retained_hit": False,
            "expected_filtered_hit_count": 0,
            "expected_filtered_hit_rate": 0.0,
            "report_only_improved": False,
        }

    retained_raw = chunk_guard_payload.get("retained_refs", [])
    retained_refs = retained_raw if isinstance(retained_raw, list) else []
    normalized_retained = {str(item).strip() for item in retained_refs if str(item).strip()}
    filtered_raw = chunk_guard_payload.get("filtered_refs", [])
    filtered_refs = filtered_raw if isinstance(filtered_raw, list) else []
    normalized_filtered = {str(item).strip() for item in filtered_refs if str(item).strip()}

    expected_retained_refs = list(expectation["expected_retained_refs"])
    expected_filtered_refs = list(expectation["expected_filtered_refs"])
    retained_hits = [
        item for item in expected_retained_refs if item in normalized_retained
    ]
    filtered_hits = [
        item for item in expected_filtered_refs if item in normalized_filtered
    ]
    expected_retained_hit = (
        True if not expected_retained_refs else len(retained_hits) == len(expected_retained_refs)
    )
    filtered_expected_count = len(expected_filtered_refs)
    filtered_hit_count = len(filtered_hits)
    filtered_hit_rate = (
        float(filtered_hit_count) / float(filtered_expected_count)
        if filtered_expected_count > 0
        else 0.0
    )
    report_only_improved = bool(expected_retained_hit) and (
        filtered_expected_count <= 0 or filtered_hit_count == filtered_expected_count
    )
    return {
        "applicable": True,
        "scenario": str(expectation["scenario"]),
        "expected_retained_refs": expected_retained_refs,
        "expected_filtered_refs": expected_filtered_refs,
        "retained_hits": retained_hits,
        "filtered_hits": filtered_hits,
        "expected_retained_hit": expected_retained_hit,
        "expected_filtered_hit_count": filtered_hit_count,
        "expected_filtered_hit_rate": filtered_hit_rate,
        "report_only_improved": report_only_improved,
    }


__all__ = [
    "coerce_task_success_config",
    "evaluate_chunk_guard_expectation",
    "evaluate_task_success",
]
