from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite.run_manifest import append_run_manifest_entry
from ace_lite.run_manifest_schema import (
    RUN_MANIFEST_SCHEMA_VERSION,
    validate_run_manifest_entry,
)


def _entry(*, unit_id: str, status: str = "pending") -> dict[str, object]:
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "unit_id": unit_id,
        "phase": "phase0",
        "priority": "high",
        "owner_role": "senior_engineer",
        "status": status,
        "depends_on": ["ALH1-0004.T0"],
        "path_set": ["src/ace_lite/run_manifest.py"],
        "forbidden_paths": ["src/ace_lite/mcp_server"],
        "goal": "Record append-only task execution metadata.",
        "deliverable": "A JSONL row per task execution.",
        "input_contracts": ["task spec"],
        "output_contracts": ["validated run_manifest_v1 row"],
        "metrics_touched": ["execution_traceability"],
        "verification_commands": ["pytest -q tests/unit/test_run_manifest.py"],
        "artifacts_emitted": ["context-map/run_manifest.jsonl"],
        "rollback_steps": ["Remove the appended JSONL row if needed."],
        "done_definition": ["Entry validates against run_manifest_v1."],
        "failure_signals": ["status is invalid"],
    }


def test_run_manifest_schema_rejects_invalid_status_values() -> None:
    with pytest.raises(ValueError, match=r"status must be one of"):
        validate_run_manifest_entry(_entry(unit_id="ALH1-0004.T1", status="unknown"))


def test_run_manifest_appends_jsonl_rows_and_each_row_validates(tmp_path: Path) -> None:
    manifest_path = tmp_path / "run_manifest.jsonl"

    first = append_run_manifest_entry(
        manifest_path=manifest_path,
        entry=_entry(unit_id="ALH1-0004.T1", status="pending"),
    )
    second = append_run_manifest_entry(
        manifest_path=manifest_path,
        entry=_entry(unit_id="ALH1-0004.T2", status="done"),
    )

    lines = manifest_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert first["unit_id"] == "ALH1-0004.T1"
    assert second["unit_id"] == "ALH1-0004.T2"

    payloads = [json.loads(line) for line in lines]
    assert [payload["unit_id"] for payload in payloads] == ["ALH1-0004.T1", "ALH1-0004.T2"]
    for payload in payloads:
        validated = validate_run_manifest_entry(payload)
        assert validated["schema_version"] == RUN_MANIFEST_SCHEMA_VERSION
