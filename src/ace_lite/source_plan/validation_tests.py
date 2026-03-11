"""Validation test selection helpers for the source_plan stage."""

from __future__ import annotations

from typing import Any


def select_validation_tests(*, tests: dict[str, Any], limit: int = 6) -> list[str]:
    """Select a minimal set of validation tests from augment test signals.

    Priority:
    1) tests.suggested_tests
    2) tests.failures (suite::name)

    Args:
        tests: Tests payload produced by augment stage.
        limit: Maximum number of returned test identifiers.

    Returns:
        List of unique test identifiers.
    """
    if not isinstance(tests, dict):
        return []

    selected: list[str] = []

    def add(label: Any) -> None:
        normalized = str(label or "").strip()
        if normalized and normalized not in selected:
            selected.append(normalized)

    resolved_limit = max(1, int(limit))

    suggested = tests.get("suggested_tests")
    if isinstance(suggested, list):
        for item in suggested:
            add(item)
            if len(selected) >= resolved_limit:
                return selected[:resolved_limit]

    failures = tests.get("failures")
    if isinstance(failures, list):
        for item in failures:
            if not isinstance(item, dict):
                continue
            suite = str(item.get("suite") or "").strip()
            name = str(item.get("name") or "").strip()
            label = f"{suite}::{name}" if suite and name else (name or suite)
            add(label)
            if len(selected) >= resolved_limit:
                return selected[:resolved_limit]

    return selected[:resolved_limit]


__all__ = ["select_validation_tests"]

