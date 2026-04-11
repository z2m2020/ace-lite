from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.problem_ledger_schema import SCHEMA_VERSION, validate_problem_ledger_payload


@dataclass(frozen=True, slots=True)
class ProblemRecord:
    problem_id: str
    title: str
    symptom: str
    metric_name: str
    metric_formula: str
    data_source: str
    validation_method: str
    threshold_or_expected_direction: str
    current_baseline: Any
    target_phase: str
    owner: str
    status: str
    can_gate_now: bool
    gate_mode: str
    artifact_paths: tuple[str, ...]
    rollback_trigger: str
    notes: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProblemRecord:
        return cls(
            problem_id=str(payload["problem_id"]),
            title=str(payload["title"]),
            symptom=str(payload["symptom"]),
            metric_name=str(payload["metric_name"]),
            metric_formula=str(payload["metric_formula"]),
            data_source=str(payload["data_source"]),
            validation_method=str(payload["validation_method"]),
            threshold_or_expected_direction=str(payload["threshold_or_expected_direction"]),
            current_baseline=payload["current_baseline"],
            target_phase=str(payload["target_phase"]),
            owner=str(payload["owner"]),
            status=str(payload["status"]),
            can_gate_now=bool(payload["can_gate_now"]),
            gate_mode=str(payload["gate_mode"]),
            artifact_paths=tuple(str(path) for path in payload["artifact_paths"]),
            rollback_trigger=str(payload["rollback_trigger"]),
            notes=str(payload["notes"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "title": self.title,
            "symptom": self.symptom,
            "metric_name": self.metric_name,
            "metric_formula": self.metric_formula,
            "data_source": self.data_source,
            "validation_method": self.validation_method,
            "threshold_or_expected_direction": self.threshold_or_expected_direction,
            "current_baseline": self.current_baseline,
            "target_phase": self.target_phase,
            "owner": self.owner,
            "status": self.status,
            "can_gate_now": self.can_gate_now,
            "gate_mode": self.gate_mode,
            "artifact_paths": list(self.artifact_paths),
            "rollback_trigger": self.rollback_trigger,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ProblemLedger:
    generated_at: str
    git_sha: str
    phase: str
    problems: tuple[ProblemRecord, ...]
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProblemLedger:
        validated = validate_problem_ledger_payload(payload)
        return cls(
            schema_version=str(validated["schema_version"]),
            generated_at=str(validated["generated_at"]),
            git_sha=str(validated["git_sha"]),
            phase=str(validated["phase"]),
            problems=tuple(ProblemRecord.from_dict(problem) for problem in validated["problems"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "git_sha": self.git_sha,
            "phase": self.phase,
            "problems": [problem.as_dict() for problem in self.problems],
        }


def load_problem_ledger(payload: dict[str, Any]) -> ProblemLedger:
    return ProblemLedger.from_dict(payload)


def validate_problem_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_problem_ledger_payload(payload)


def dump_problem_ledger(ledger: ProblemLedger | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ledger, ProblemLedger):
        return ledger.as_dict()
    return load_problem_ledger(ledger).as_dict()


__all__ = [
    "ProblemLedger",
    "ProblemRecord",
    "dump_problem_ledger",
    "load_problem_ledger",
    "validate_problem_ledger",
]
