from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script():
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    module_name = "script_run_arm_sweeper_unit"
    module_path = scripts_dir / "run_arm_sweeper.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_load_arm_catalog_normalizes_schema_and_overrides(tmp_path: Path) -> None:
    module = _load_script()
    manifest_path = tmp_path / "arms.yaml"
    manifest_path.write_text(
        """
schema_version: ace-lite-arm-catalog-v1
name: v-test
shared_overrides:
  top_k_files: 6
arms:
  - arm_id: auto_default
    overrides:
      retrieval_policy: auto
  - arm_id: general_rrf
    label: general_rrf
    overrides:
      retrieval_policy: general
      candidate_ranker: rrf_hybrid
""".strip()
        + "\n",
        encoding="utf-8",
    )

    payload = module.load_arm_catalog(manifest_path)
    assert payload["name"] == "v-test"
    assert payload["shared_overrides"] == {"top_k_files": 6}
    assert payload["arms"] == [
        {
            "arm_id": "auto_default",
            "label": "auto_default",
            "description": "",
            "overrides": {"retrieval_policy": "auto"},
        },
        {
            "arm_id": "general_rrf",
            "label": "general_rrf",
            "description": "",
            "overrides": {
                "retrieval_policy": "general",
                "candidate_ranker": "rrf_hybrid",
            },
        },
    ]


def test_build_benchmark_command_uses_cli_module_contract(tmp_path: Path) -> None:
    module = _load_script()
    cmd = module._build_benchmark_command(
        python_exe=sys.executable,
        cases_path=tmp_path / "cases.yaml",
        repo="demo",
        root=tmp_path,
        skills_dir=tmp_path / "skills",
        output_dir=tmp_path / "out",
        config_pack_path=tmp_path / "pack.json",
        warmup_runs=2,
        memory_primary="none",
        memory_secondary="none",
    )

    assert cmd[:5] == [sys.executable, "-m", "ace_lite.cli", "benchmark", "run"]
    assert "--config-pack" in cmd
    assert cmd[cmd.index("--warmup-runs") + 1] == "2"
    assert "--no-include-plans" in cmd
    assert "--no-include-case-details" in cmd


def test_build_oracle_relabel_prefers_task_success_then_noise_then_arm_id() -> None:
    module = _load_script()
    oracle = module.build_oracle_relabel(
        cases=[
            {"case_id": "c1", "query": "q1", "expected_keys": ["auth"]},
            {"case_id": "c2", "query": "q2", "expected_keys": ["token"]},
        ],
        arm_results=[
            {
                "arm_id": "z_arm",
                "label": "z_arm",
                "cases": [
                    {
                        "case_id": "c1",
                        "task_success_hit": 1.0,
                        "recall_hit": 1.0,
                        "precision_at_k": 0.8,
                        "dependency_recall": 0.9,
                        "noise_rate": 0.2,
                        "latency_ms": 9.0,
                    },
                    {
                        "case_id": "c2",
                        "task_success_hit": 0.0,
                        "recall_hit": 0.0,
                        "precision_at_k": 0.2,
                        "dependency_recall": 0.1,
                        "noise_rate": 0.5,
                        "latency_ms": 7.0,
                    },
                ],
            },
            {
                "arm_id": "a_arm",
                "label": "a_arm",
                "cases": [
                    {
                        "case_id": "c1",
                        "task_success_hit": 1.0,
                        "recall_hit": 1.0,
                        "precision_at_k": 0.8,
                        "dependency_recall": 0.9,
                        "noise_rate": 0.2,
                        "latency_ms": 9.0,
                    },
                    {
                        "case_id": "c2",
                        "task_success_hit": 1.0,
                        "recall_hit": 1.0,
                        "precision_at_k": 0.7,
                        "dependency_recall": 0.8,
                        "noise_rate": 0.1,
                        "latency_ms": 8.0,
                    },
                ],
            },
        ],
    )

    assert oracle["oracle_distribution"] == {"a_arm": 2}
    assert [row["oracle_arm_id"] for row in oracle["labels"]] == ["a_arm", "a_arm"]


def test_build_summary_orders_leaderboard_by_contract() -> None:
    module = _load_script()
    summary = module.build_summary(
        catalog={"name": "default_v1", "path": "benchmark/arms/default_v1.yaml", "arms": [1, 2]},
        cases_path=Path("benchmark/cases/default.yaml"),
        arm_results=[
            {
                "arm_id": "slower_better",
                "label": "slower_better",
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.6,
                    "noise_rate": 0.2,
                    "latency_p95_ms": 20.0,
                },
                "task_success_summary": {"task_success_rate": 1.0},
                "decision_observability_summary": {},
                "results_json": "a",
                "summary_json": "b",
                "report_md": "c",
            },
            {
                "arm_id": "faster_worse",
                "label": "faster_worse",
                "regressed": False,
                "failed_checks": [],
                "metrics": {
                    "task_success_rate": 0.5,
                    "precision_at_k": 0.9,
                    "noise_rate": 0.1,
                    "latency_p95_ms": 5.0,
                },
                "task_success_summary": {"task_success_rate": 0.5},
                "decision_observability_summary": {},
                "results_json": "d",
                "summary_json": "e",
                "report_md": "f",
            },
        ],
        oracle_relabel={
            "case_count": 3,
            "oracle_distribution": {"slower_better": 2, "faster_worse": 1},
        },
    )

    assert summary["best_arm_id"] == "slower_better"
    assert [row["arm_id"] for row in summary["leaderboard"]] == [
        "slower_better",
        "faster_worse",
    ]
