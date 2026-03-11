from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_script(name: str):
    module_name = f"script_{name.replace('.', '_')}"
    module_path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_log_friction_event_main_appends_jsonl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("log_friction_event.py")
    output_path = tmp_path / "events.jsonl"

    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: SimpleNamespace(
            output=str(output_path),
            stage="planning",
            expected="focused candidates",
            actual="noisy candidates",
            query="improve quality planning",
            manual_fix="tighten retrieval policy",
            severity="medium",
            status="open",
            source="manual",
            root_cause="retrieval_noise",
            time_cost_min=4.0,
            tag=["mcp", "retrieval"],
            context_json='{"hint":"use ace_plan"}',
        ),
    )

    exit_code = module.main()
    assert exit_code == 0
    rows = [line for line in output_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["stage"] == "planning"
    assert payload["severity"] == "medium"


def test_build_friction_report_handles_empty_log(tmp_path: Path) -> None:
    module = _load_script("build_friction_report.py")
    events_path = tmp_path / "events.jsonl"
    output_dir = tmp_path / "out"

    summary = module.build_report(
        events_path=events_path,
        output_dir=output_dir,
        min_severity="low",
        status="all",
        top_n=5,
        fail_on_open_count=-1,
    )

    assert summary["passed"] is True
    assert summary["aggregate"]["event_count"] == 0
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "report.md").exists()


def test_build_friction_report_fail_on_open_count(tmp_path: Path) -> None:
    module = _load_script("build_friction_report.py")
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "stage": "quality_gate",
                        "severity": "high",
                        "status": "open",
                        "expected": "pass",
                        "actual": "fail",
                        "time_cost_min": 5,
                        "root_cause": "quality_gate_command_failure",
                    }
                ),
                ""
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    summary = module.build_report(
        events_path=events_path,
        output_dir=output_dir,
        min_severity="medium",
        status="all",
        top_n=5,
        fail_on_open_count=0,
    )

    assert summary["passed"] is False
    assert summary["aggregate"]["open_count"] == 1
