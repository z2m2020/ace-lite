from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_problem_ledger.py"


def _run_builder(tmp_path: Path, *extra_args: str) -> dict:
    output_path = tmp_path / "problem_ledger.json"
    env = os.environ.copy()
    python_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = python_path if not existing else python_path + os.pathsep + existing

    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--output", str(output_path), *extra_args],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert output_path.exists()
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_problem_ledger_builder_emits_report_only_payload_with_no_inputs(tmp_path: Path) -> None:
    payload = _run_builder(tmp_path)

    assert payload["schema_version"] == "problem_ledger_v1"
    assert payload["phase"] == "report_only"
    assert len(payload["problems"]) >= 8

    problem_ids = [item["problem_id"] for item in payload["problems"]]
    assert problem_ids[:8] == [
        "PQ-001",
        "PQ-002",
        "PQ-003",
        "PQ-004",
        "PQ-005",
        "PQ-006",
        "PQ-007",
        "PQ-008",
    ]

    for item in payload["problems"]:
        assert item["can_gate_now"] is False
        assert item["gate_mode"] == "report_only"
        assert item["current_baseline"] == "unknown"
        assert isinstance(item["artifact_paths"], list)


def test_problem_ledger_builder_populates_artifact_paths_for_synthetic_inputs(
    tmp_path: Path,
) -> None:
    benchmark_root = tmp_path / "benchmark"
    freeze_root = tmp_path / "freeze"
    benchmark_root.mkdir()
    freeze_root.mkdir()

    (benchmark_root / "summary.json").write_text(
        json.dumps(
            {
                "retrieval_control_plane_gate_summary": {
                    "gate_passed": False,
                    "adaptive_router_shadow_coverage": 0.82,
                },
                "retrieval_frontier_gate_summary": {
                    "gate_passed": False,
                    "precision_at_k": 0.77,
                },
                "deep_symbol_summary": {"recall": 0.66},
                "native_scip_summary": {"loaded_rate": 0.91},
                "validation_probe_summary": {"validation_test_count": 6},
                "source_plan_validation_feedback_summary": {"present_ratio": 0.5},
                "source_plan_failure_signal_summary": {"present_ratio": 0.25},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (benchmark_root / "results.json").write_text("{}\n", encoding="utf-8")
    (benchmark_root / "report.md").write_text("# Synthetic report\n", encoding="utf-8")
    (benchmark_root / "archive_manifest.json").write_text("{}\n", encoding="utf-8")
    (benchmark_root / "promotion_decision.json").write_text("{}\n", encoding="utf-8")

    (freeze_root / "freeze_regression.json").write_text(
        json.dumps({"passed": False}, indent=2),
        encoding="utf-8",
    )
    (freeze_root / "report.md").write_text("# Freeze report\n", encoding="utf-8")

    gate_registry_path = tmp_path / "gate_registry.json"
    gate_registry_path.write_text(
        json.dumps(
            {
                "problems": [
                    {
                        "problem_id": "PQ-010",
                        "title": "Registry-backed governance state",
                        "can_gate_now": True,
                        "gate_mode": "always",
                        "current_baseline": "configured",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = _run_builder(
        tmp_path,
        "--benchmark-artifacts-root",
        str(benchmark_root),
        "--freeze-artifacts-root",
        str(freeze_root),
        "--gate-registry-path",
        str(gate_registry_path),
    )

    problems = {item["problem_id"]: item for item in payload["problems"]}

    assert "PQ-009" in problems
    assert "PQ-010" in problems
    assert problems["PQ-001"]["artifact_paths"]
    assert problems["PQ-004"]["artifact_paths"]
    assert problems["PQ-009"]["artifact_paths"]
    assert problems["PQ-010"]["artifact_paths"] == [str(gate_registry_path.resolve())]

    assert problems["PQ-005"]["current_baseline"] == 0.82
    assert problems["PQ-006"]["current_baseline"] == 0.77
    assert problems["PQ-008"]["current_baseline"] == 0.91
    assert problems["PQ-010"]["can_gate_now"] is True
    assert problems["PQ-010"]["gate_mode"] == "always"
    assert problems["PQ-010"]["current_baseline"] == "configured"

    assert all(isinstance(item["artifact_paths"], list) for item in problems.values())
