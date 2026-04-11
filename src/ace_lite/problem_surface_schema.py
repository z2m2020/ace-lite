from __future__ import annotations

from typing import Any

PROBLEM_SURFACE_SCHEMA_NAME = "problem_surface"
PROBLEM_SURFACE_SCHEMA_VERSION = "problem_surface_v1"
PROBLEM_SURFACE_SCHEMA_LABEL = "ace-lite-problem-surface-v1"

PROBLEM_SURFACE_REQUIRED_KEYS = (
    "schema_version",
    "generated_at",
    "git_sha",
    "phase",
    "inputs",
    "surfaces",
    "warnings",
)

PROBLEM_SURFACE_INPUT_NAMES = (
    "context_report",
    "confidence_summary",
    "validation_feedback",
)

PROBLEM_SURFACE_SURFACE_NAMES = (
    "context",
    "confidence",
    "validation",
)


def build_problem_surface_schema_document() -> dict[str, Any]:
    return {
        "schema_name": PROBLEM_SURFACE_SCHEMA_NAME,
        "schema_version": PROBLEM_SURFACE_SCHEMA_VERSION,
        "schema_label": PROBLEM_SURFACE_SCHEMA_LABEL,
        "required_keys": list(PROBLEM_SURFACE_REQUIRED_KEYS),
        "inputs": list(PROBLEM_SURFACE_INPUT_NAMES),
        "surfaces": list(PROBLEM_SURFACE_SURFACE_NAMES),
    }


__all__ = [
    "PROBLEM_SURFACE_INPUT_NAMES",
    "PROBLEM_SURFACE_REQUIRED_KEYS",
    "PROBLEM_SURFACE_SCHEMA_LABEL",
    "PROBLEM_SURFACE_SCHEMA_NAME",
    "PROBLEM_SURFACE_SCHEMA_VERSION",
    "PROBLEM_SURFACE_SURFACE_NAMES",
    "build_problem_surface_schema_document",
]
