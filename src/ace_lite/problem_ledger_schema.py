from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.config_choices import MEMORY_GATE_MODE_CHOICES
from ace_lite.config_value_normalizers import validate_choice_value

SCHEMA_VERSION = "problem_ledger_v1"
REQUIRED_LEDGER_KEYS = (
    "schema_version",
    "generated_at",
    "git_sha",
    "phase",
    "problems",
)
REQUIRED_PROBLEM_KEYS = (
    "problem_id",
    "title",
    "symptom",
    "metric_name",
    "metric_formula",
    "data_source",
    "validation_method",
    "threshold_or_expected_direction",
    "current_baseline",
    "target_phase",
    "owner",
    "status",
    "can_gate_now",
    "gate_mode",
    "artifact_paths",
    "rollback_trigger",
    "notes",
)


def _require_mapping(value: Any, *, prefix: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{prefix} must be a dictionary")
    return value


def _require_string(value: Any, *, prefix: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{prefix} must be a non-empty string")
    return value


def _validate_problem(problem: Any, *, index: int) -> dict[str, Any]:
    payload = dict(_require_mapping(problem, prefix=f"problems[{index}]"))

    for key in REQUIRED_PROBLEM_KEYS:
        if key not in payload:
            raise ValueError(f"problems[{index}].{key} is required")

    for key in (
        "problem_id",
        "title",
        "symptom",
        "metric_name",
        "metric_formula",
        "data_source",
        "validation_method",
        "threshold_or_expected_direction",
        "target_phase",
        "owner",
        "status",
        "rollback_trigger",
        "notes",
    ):
        _require_string(payload.get(key), prefix=f"problems[{index}].{key}")

    if not isinstance(payload.get("can_gate_now"), bool):
        raise ValueError(f"problems[{index}].can_gate_now must be a boolean")

    gate_mode = _require_string(payload.get("gate_mode"), prefix=f"problems[{index}].gate_mode")
    payload["gate_mode"] = validate_choice_value(
        gate_mode,
        field_name=f"problems[{index}].gate_mode",
        choices=MEMORY_GATE_MODE_CHOICES,
    )

    artifact_paths = payload.get("artifact_paths")
    if not isinstance(artifact_paths, list):
        raise ValueError(f"problems[{index}].artifact_paths must be a list")
    for path_index, path in enumerate(artifact_paths):
        _require_string(path, prefix=f"problems[{index}].artifact_paths[{path_index}]")

    return payload


def validate_problem_ledger_payload(payload: Any) -> dict[str, Any]:
    ledger = dict(_require_mapping(payload, prefix="problem_ledger"))

    for key in REQUIRED_LEDGER_KEYS:
        if key not in ledger:
            raise ValueError(f"missing required top-level field: {key}")

    if ledger.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unexpected schema_version: {ledger.get('schema_version')!r}; expected {SCHEMA_VERSION!r}"
        )

    _require_string(ledger.get("generated_at"), prefix="generated_at")
    _require_string(ledger.get("git_sha"), prefix="git_sha")
    _require_string(ledger.get("phase"), prefix="phase")

    problems = ledger.get("problems")
    if not isinstance(problems, list):
        raise ValueError("problems must be a list")

    ledger["problems"] = [
        _validate_problem(problem, index=index) for index, problem in enumerate(problems)
    ]
    return ledger


__all__ = [
    "REQUIRED_LEDGER_KEYS",
    "REQUIRED_PROBLEM_KEYS",
    "SCHEMA_VERSION",
    "validate_problem_ledger_payload",
]
