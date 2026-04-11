from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RUN_MANIFEST_SCHEMA_VERSION = "run_manifest_v1"
RUN_MANIFEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "unit_id",
    "phase",
    "priority",
    "owner_role",
    "status",
    "depends_on",
    "path_set",
    "forbidden_paths",
    "goal",
    "deliverable",
    "input_contracts",
    "output_contracts",
    "metrics_touched",
    "verification_commands",
    "artifacts_emitted",
    "rollback_steps",
    "done_definition",
    "failure_signals",
)
RUN_MANIFEST_STATUS_VALUES: tuple[str, ...] = (
    "pending",
    "in_progress",
    "blocked",
    "done",
    "failed",
    "cancelled",
)


def _ensure_non_empty_str(*, value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _normalize_string_list(*, value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        token = item.strip()
        if not token:
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        normalized.append(token)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class RunManifestEntryV1:
    unit_id: str
    phase: str
    priority: str
    owner_role: str
    status: str
    depends_on: tuple[str, ...]
    path_set: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    goal: str
    deliverable: str
    input_contracts: tuple[str, ...]
    output_contracts: tuple[str, ...]
    metrics_touched: tuple[str, ...]
    verification_commands: tuple[str, ...]
    artifacts_emitted: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    done_definition: tuple[str, ...]
    failure_signals: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "unit_id": self.unit_id,
            "phase": self.phase,
            "priority": self.priority,
            "owner_role": self.owner_role,
            "status": self.status,
            "depends_on": list(self.depends_on),
            "path_set": list(self.path_set),
            "forbidden_paths": list(self.forbidden_paths),
            "goal": self.goal,
            "deliverable": self.deliverable,
            "input_contracts": list(self.input_contracts),
            "output_contracts": list(self.output_contracts),
            "metrics_touched": list(self.metrics_touched),
            "verification_commands": list(self.verification_commands),
            "artifacts_emitted": list(self.artifacts_emitted),
            "rollback_steps": list(self.rollback_steps),
            "done_definition": list(self.done_definition),
            "failure_signals": list(self.failure_signals),
        }


def build_run_manifest_entry(
    *,
    unit_id: str,
    phase: str,
    priority: str,
    owner_role: str,
    status: str,
    depends_on: list[str],
    path_set: list[str],
    forbidden_paths: list[str],
    goal: str,
    deliverable: str,
    input_contracts: list[str],
    output_contracts: list[str],
    metrics_touched: list[str],
    verification_commands: list[str],
    artifacts_emitted: list[str],
    rollback_steps: list[str],
    done_definition: list[str],
    failure_signals: list[str],
) -> RunManifestEntryV1:
    normalized_status = _ensure_non_empty_str(value=status, field_name="status").lower()
    if normalized_status not in RUN_MANIFEST_STATUS_VALUES:
        allowed = ", ".join(RUN_MANIFEST_STATUS_VALUES)
        raise ValueError(f"status must be one of: {allowed}")

    return RunManifestEntryV1(
        unit_id=_ensure_non_empty_str(value=unit_id, field_name="unit_id"),
        phase=_ensure_non_empty_str(value=phase, field_name="phase"),
        priority=_ensure_non_empty_str(value=priority, field_name="priority"),
        owner_role=_ensure_non_empty_str(value=owner_role, field_name="owner_role"),
        status=normalized_status,
        depends_on=_normalize_string_list(value=depends_on, field_name="depends_on"),
        path_set=_normalize_string_list(value=path_set, field_name="path_set"),
        forbidden_paths=_normalize_string_list(
            value=forbidden_paths,
            field_name="forbidden_paths",
        ),
        goal=_ensure_non_empty_str(value=goal, field_name="goal"),
        deliverable=_ensure_non_empty_str(value=deliverable, field_name="deliverable"),
        input_contracts=_normalize_string_list(
            value=input_contracts,
            field_name="input_contracts",
        ),
        output_contracts=_normalize_string_list(
            value=output_contracts,
            field_name="output_contracts",
        ),
        metrics_touched=_normalize_string_list(
            value=metrics_touched,
            field_name="metrics_touched",
        ),
        verification_commands=_normalize_string_list(
            value=verification_commands,
            field_name="verification_commands",
        ),
        artifacts_emitted=_normalize_string_list(
            value=artifacts_emitted,
            field_name="artifacts_emitted",
        ),
        rollback_steps=_normalize_string_list(
            value=rollback_steps,
            field_name="rollback_steps",
        ),
        done_definition=_normalize_string_list(
            value=done_definition,
            field_name="done_definition",
        ),
        failure_signals=_normalize_string_list(
            value=failure_signals,
            field_name="failure_signals",
        ),
    )


def validate_run_manifest_entry(entry: RunManifestEntryV1 | dict[str, Any]) -> dict[str, Any]:
    payload = entry.as_dict() if isinstance(entry, RunManifestEntryV1) else entry
    if not isinstance(payload, dict):
        raise ValueError("run manifest entry must be a dictionary")

    schema_version = str(payload.get("schema_version") or RUN_MANIFEST_SCHEMA_VERSION)
    if schema_version != RUN_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"schema_version must match {RUN_MANIFEST_SCHEMA_VERSION}")

    missing = [field for field in RUN_MANIFEST_REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))

    return build_run_manifest_entry(
        unit_id=payload["unit_id"],
        phase=payload["phase"],
        priority=payload["priority"],
        owner_role=payload["owner_role"],
        status=payload["status"],
        depends_on=payload["depends_on"],
        path_set=payload["path_set"],
        forbidden_paths=payload["forbidden_paths"],
        goal=payload["goal"],
        deliverable=payload["deliverable"],
        input_contracts=payload["input_contracts"],
        output_contracts=payload["output_contracts"],
        metrics_touched=payload["metrics_touched"],
        verification_commands=payload["verification_commands"],
        artifacts_emitted=payload["artifacts_emitted"],
        rollback_steps=payload["rollback_steps"],
        done_definition=payload["done_definition"],
        failure_signals=payload["failure_signals"],
    ).as_dict()
