from __future__ import annotations

from typing import Any

import pytest

from ace_lite.problem_ledger import (
    dump_problem_ledger,
    load_problem_ledger,
    validate_problem_ledger,
)
from ace_lite.problem_ledger_schema import SCHEMA_VERSION


def _build_problem(*, problem_id: str, gate_mode: str = "auto") -> dict[str, Any]:
    return {
        "problem_id": problem_id,
        "title": f"Problem {problem_id}",
        "symptom": "Retrieval quality drifts under repeated runs.",
        "metric_name": "top_k_recall",
        "metric_formula": "hits / expected_hits",
        "data_source": "benchmark/results.json",
        "validation_method": "benchmark regression comparison",
        "threshold_or_expected_direction": ">= baseline",
        "current_baseline": 0.72,
        "target_phase": "phase-1",
        "owner": "governance",
        "status": "open",
        "can_gate_now": False,
        "gate_mode": gate_mode,
        "artifact_paths": [f"artifacts/{problem_id}.json"],
        "rollback_trigger": "Recall drops below the release baseline.",
        "notes": "Track as schema metadata only; do not enforce gates here.",
    }


def _build_ledger() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-04-11T15:00:00Z",
        "git_sha": "fbda08a5d80fb6e24774f07e564a2f91db8d0018",
        "phase": "alpha",
        "problems": [
            _build_problem(problem_id="PQ-001", gate_mode="auto"),
            _build_problem(problem_id="PQ-003", gate_mode="never"),
        ],
    }


def test_problem_ledger_roundtrip_preserves_problem_ids() -> None:
    payload = _build_ledger()

    first_dump = dump_problem_ledger(payload)
    loaded = load_problem_ledger(first_dump)
    second_dump = dump_problem_ledger(loaded)

    assert second_dump["schema_version"] == "problem_ledger_v1"
    assert [item["problem_id"] for item in first_dump["problems"]] == [
        "PQ-001",
        "PQ-003",
    ]
    assert [item["problem_id"] for item in second_dump["problems"]] == [
        "PQ-001",
        "PQ-003",
    ]


def test_problem_ledger_validation_rejects_missing_problem_id() -> None:
    payload = _build_ledger()
    first_problem = dict(payload["problems"][0])
    first_problem.pop("problem_id")
    payload["problems"] = [first_problem, payload["problems"][1]]

    with pytest.raises(ValueError, match=r"problems\[0\]\.problem_id is required"):
        validate_problem_ledger(payload)


def test_problem_ledger_validation_rejects_invalid_gate_mode() -> None:
    payload = _build_ledger()
    first_problem = dict(payload["problems"][0])
    first_problem["gate_mode"] = "enforce"
    payload["problems"] = [first_problem, payload["problems"][1]]

    with pytest.raises(ValueError, match=r"Unsupported problems\[0\]\.gate_mode"):
        validate_problem_ledger(payload)
