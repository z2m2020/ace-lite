from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script():
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    module_name = "script_run_arm_sweeper_e2e"
    module_path = scripts_dir / "run_arm_sweeper.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_results(
    *,
    output_dir: Path,
    metrics: dict[str, float],
    cases: list[dict[str, float | str]],
    regressed: bool = False,
    failed_checks: list[str] | None = None,
    retrieval_control_plane_gate_summary: dict[str, object] | None = None,
    retrieval_frontier_gate_summary: dict[str, object] | None = None,
    deep_symbol_summary: dict[str, object] | None = None,
    native_scip_summary: dict[str, object] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps({"metrics": metrics, "cases": cases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "metrics": metrics,
                "regressed": regressed,
                "failed_checks": list(failed_checks or []),
                "task_success_summary": {
                    "task_success_rate": float(metrics.get("task_success_rate", 0.0) or 0.0)
                },
                "decision_observability_summary": {"decision_event_count": 1},
                "retrieval_control_plane_gate_summary": dict(
                    retrieval_control_plane_gate_summary or {}
                ),
                "retrieval_frontier_gate_summary": dict(
                    retrieval_frontier_gate_summary or {}
                ),
                "deep_symbol_summary": dict(deep_symbol_summary or {}),
                "native_scip_summary": dict(native_scip_summary or {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text("# report\n", encoding="utf-8")


def test_run_arm_sweeper_writes_summary_and_oracle_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()

    catalog_path = tmp_path / "arms.yaml"
    catalog_path.write_text(
        """
schema_version: ace-lite-arm-catalog-v1
name: test_v1
shared_overrides:
  top_k_files: 4
arms:
  - arm_id: auto_default
    label: auto_default
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
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        """
cases:
  - case_id: c1
    query: where auth lives
    expected_keys: [auth]
  - case_id: c2
    query: where token lives
    expected_keys: [token]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def fake_run_command(*, cmd, cwd=None):
        _ = cwd
        output_dir = Path(cmd[cmd.index("--output") + 1])
        config_pack_path = Path(cmd[cmd.index("--config-pack") + 1])
        pack = json.loads(config_pack_path.read_text(encoding="utf-8"))
        arm_id = str(pack["name"]).split(":")[-1]
        if arm_id == "auto_default":
            _write_results(
                output_dir=output_dir,
                metrics={
                    "task_success_rate": 0.5,
                    "precision_at_k": 0.5,
                    "noise_rate": 0.2,
                    "latency_p95_ms": 10.0,
                },
                retrieval_control_plane_gate_summary={"gate_passed": True},
                retrieval_frontier_gate_summary={"gate_passed": False},
                deep_symbol_summary={"case_count": 2.0, "recall": 0.81},
                native_scip_summary={"loaded_rate": 0.68},
                cases=[
                    {
                        "case_id": "c1",
                        "task_success_hit": 1.0,
                        "recall_hit": 1.0,
                        "precision_at_k": 0.7,
                        "noise_rate": 0.2,
                        "dependency_recall": 0.6,
                        "latency_ms": 8.0,
                    },
                    {
                        "case_id": "c2",
                        "task_success_hit": 0.0,
                        "recall_hit": 0.0,
                        "precision_at_k": 0.3,
                        "noise_rate": 0.3,
                        "dependency_recall": 0.4,
                        "latency_ms": 9.0,
                    },
                ],
            )
        else:
            _write_results(
                output_dir=output_dir,
                metrics={
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.7,
                    "noise_rate": 0.1,
                    "latency_p95_ms": 12.0,
                },
                retrieval_control_plane_gate_summary={"gate_passed": True},
                retrieval_frontier_gate_summary={"gate_passed": True},
                deep_symbol_summary={"case_count": 3.0, "recall": 0.92},
                native_scip_summary={"loaded_rate": 0.76},
                cases=[
                    {
                        "case_id": "c1",
                        "task_success_hit": 1.0,
                        "recall_hit": 1.0,
                        "precision_at_k": 0.8,
                        "noise_rate": 0.1,
                        "dependency_recall": 0.7,
                        "latency_ms": 10.0,
                    },
                    {
                        "case_id": "c2",
                        "task_success_hit": 1.0,
                        "recall_hit": 1.0,
                        "precision_at_k": 0.6,
                        "noise_rate": 0.1,
                        "dependency_recall": 0.8,
                        "latency_ms": 11.0,
                    },
                ],
                regressed=True,
                failed_checks=["precision_at_k"],
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            returncode=0,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    outputs = module.run_arm_sweeper(
        catalog_path=catalog_path,
        cases_path=cases_path,
        repo="demo",
        root=tmp_path,
        skills_dir=tmp_path / "skills",
        output_dir=tmp_path / "artifacts",
        python_exe=sys.executable,
    )

    summary = json.loads(Path(outputs["summary_json"]).read_text(encoding="utf-8"))
    assert summary["catalog"]["name"] == "test_v1"
    assert summary["best_arm_id"] == "general_rrf"
    assert [row["arm_id"] for row in summary["leaderboard"]] == [
        "general_rrf",
        "auto_default",
    ]
    assert summary["leaderboard"][0]["retrieval_frontier_gate_summary"] == {
        "gate_passed": True
    }
    assert summary["leaderboard"][0]["deep_symbol_summary"]["case_count"] == pytest.approx(3.0)
    assert summary["leaderboard"][0]["native_scip_summary"]["loaded_rate"] == pytest.approx(0.76)
    assert summary["leaderboard"][1]["retrieval_frontier_gate_summary"] == {
        "gate_passed": False
    }
    assert summary["oracle_relabel"]["case_count"] == 2
    assert summary["oracle_relabel"]["oracle_distribution"] == {
        "general_rrf": 2
    }
    summary_md = Path(outputs["summary_md"]).read_text(encoding="utf-8")
    assert "q3_gate" in summary_md
    assert "| general_rrf | 1.0000 | 0.7000 | 0.1000 | 12.00 | yes | pass | pass | 3.0000 | 0.7600 |" in summary_md
    assert "| auto_default | 0.5000 | 0.5000 | 0.2000 | 10.00 | no | pass | fail | 2.0000 | 0.6800 |" in summary_md

    oracle = json.loads(Path(outputs["oracle_relabel_json"]).read_text(encoding="utf-8"))
    assert oracle["case_count"] == 2
    assert [row["oracle_arm_id"] for row in oracle["labels"]] == [
        "general_rrf",
        "general_rrf",
    ]
    assert Path(outputs["summary_md"]).exists()
    assert Path(outputs["oracle_relabel_jsonl"]).exists()


def test_run_arm_sweeper_main_prints_output_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()

    catalog_path = tmp_path / "arms.yaml"
    catalog_path.write_text(
        """
schema_version: ace-lite-arm-catalog-v1
name: test_v1
arms:
  - arm_id: auto_default
    label: auto_default
    overrides:
      retrieval_policy: auto
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        """
cases:
  - case_id: c1
    query: q1
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def fake_run_command(*, cmd, cwd=None):
        _ = cwd
        output_dir = Path(cmd[cmd.index("--output") + 1])
        _write_results(
            output_dir=output_dir,
            metrics={
                "task_success_rate": 1.0,
                "precision_at_k": 1.0,
                "noise_rate": 0.0,
                "latency_p95_ms": 5.0,
            },
            cases=[
                {
                    "case_id": "c1",
                    "task_success_hit": 1.0,
                    "recall_hit": 1.0,
                    "precision_at_k": 1.0,
                    "noise_rate": 0.0,
                    "dependency_recall": 1.0,
                    "latency_ms": 5.0,
                }
            ],
        )
        return module.CommandResult(
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            returncode=0,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_arm_sweeper.py",
            "--catalog",
            str(catalog_path),
            "--cases",
            str(cases_path),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["arm_count"] == 1
    assert payload["best_arm_id"] == "auto_default"
