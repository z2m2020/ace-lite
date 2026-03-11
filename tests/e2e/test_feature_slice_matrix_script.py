from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

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


def _write_benchmark_results(
    *,
    output_dir: Path,
    cases_path: Path,
    task_success_by_case: dict[str, float],
    precision_by_case: dict[str, float] | None = None,
    noise_by_case: dict[str, float] | None = None,
    dependency_recall_by_case: dict[str, float] | None = None,
    routing_source_by_case: dict[str, str] | None = None,
    metrics_overrides: dict[str, float] | None = None,
    comparison_lane_summary: dict[str, object] | None = None,
) -> None:
    precision_rows = precision_by_case or {}
    noise_rows = noise_by_case or {}
    dependency_rows = dependency_recall_by_case or {}
    routing_rows = routing_source_by_case or {}
    payload = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else []

    case_rows: list[dict[str, float | str]] = []
    task_success_values: list[float] = []
    precision_values: list[float] = []
    noise_values: list[float] = []
    dependency_values: list[float] = []

    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "")
        task_success = float(task_success_by_case.get(case_id, 1.0))
        precision = float(precision_rows.get(case_id, task_success))
        noise = float(noise_rows.get(case_id, 0.0 if task_success > 0.0 else 1.0))
        dependency_recall = float(dependency_rows.get(case_id, 0.0))
        row: dict[str, object] = {
            "case_id": case_id,
            "task_success_hit": task_success,
            "utility_hit": task_success,
            "precision_at_k": precision,
            "noise_rate": noise,
            "recall_hit": task_success,
            "dependency_recall": dependency_recall,
            "plan": {
                "skills": {
                    "routing_source": str(
                        routing_rows.get(case_id, routing_rows.get("*", ""))
                    ),
                }
            },
        }
        comparison_lane = str(item.get("comparison_lane") or "").strip()
        if comparison_lane:
            row["comparison_lane"] = comparison_lane
        case_rows.append(row)
        task_success_values.append(task_success)
        precision_values.append(precision)
        noise_values.append(noise)
        dependency_values.append(dependency_recall)

    metrics = {
        "task_success_rate": sum(task_success_values) / max(1, len(task_success_values)),
        "precision_at_k": sum(precision_values) / max(1, len(precision_values)),
        "noise_rate": sum(noise_values) / max(1, len(noise_values)),
        "dependency_recall": sum(dependency_values) / max(1, len(dependency_values)),
    }
    if metrics_overrides:
        for key, value in metrics_overrides.items():
            metrics[str(key)] = float(value)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"metrics": metrics, "cases": case_rows}
    if isinstance(comparison_lane_summary, dict):
        payload["comparison_lane_summary"] = comparison_lane_summary
    (output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_run_perturbation_slice_passes_and_renders_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        _write_benchmark_results(
            output_dir=output_dir,
            cases_path=cases_path,
            task_success_by_case={},
        )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_perturbation_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={"slices": {"perturbation": {"thresholds": {}}}},
    )

    assert slice_payload["passed"] is True
    assert [item["name"] for item in slice_payload["perturbations"]] == [
        "rename",
        "path_move",
        "doc_noise",
        "file_growth",
        "query_paraphrase",
    ]
    assert slice_payload["deltas"] == {
        "task_success_delta": 0.0,
        "precision_delta": 0.0,
        "noise_increase": 0.0,
    }

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-06T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert "## Perturbation Details" in markdown
    assert "| query_paraphrase | PASS | +0.0000 | +0.0000 | +0.0000 |" in markdown


def test_run_perturbation_slice_passes_chunk_guard_flags_and_renders_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_chunk_guard_flags: list[tuple[str, str, str, str, str]] = []

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if "--chunk-guard" in cmd:
            seen_chunk_guard_flags.append(
                (
                    output_dir.name,
                    str(cmd[cmd.index("--chunk-guard-mode") + 1]),
                    str(cmd[cmd.index("--chunk-guard-lambda-penalty") + 1]),
                    str(cmd[cmd.index("--chunk-guard-min-pool") + 1]),
                    str(cmd[cmd.index("--chunk-guard-min-marginal-utility") + 1]),
                )
            )
        _write_benchmark_results(
            output_dir=output_dir,
            cases_path=cases_path,
            task_success_by_case={},
        )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_perturbation_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "perturbation": {
                    "thresholds": {},
                    "perturbation": {
                        "chunk_guard_mode": "enforce",
                        "chunk_guard_lambda_penalty": 4.0,
                        "chunk_guard_min_pool": 1,
                        "chunk_guard_min_marginal_utility": 0.2,
                    },
                }
            }
        },
    )

    assert seen_chunk_guard_flags == [
        ("perturbation-baseline", "enforce", "4.0", "1", "0.2"),
        ("perturbation-perturbed", "enforce", "4.0", "1", "0.2"),
    ]
    assert slice_payload["chunk_guard"] == {
        "mode": "enforce",
        "lambda_penalty": 4.0,
        "min_pool": 1,
        "min_marginal_utility": 0.2,
    }

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-10T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert (
        "- Chunk guard: mode=enforce, lambda_penalty=4.00, min_pool=1, min_marginal_utility=0.20"
        in markdown
    )


def test_run_perturbation_slice_fails_on_file_growth_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        cases_payload = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
        cases = cases_payload.get("cases", []) if isinstance(cases_payload, dict) else []
        case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
        if "file-growth-perturbed" in case_ids:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"file-growth-perturbed": 0.0},
                precision_by_case={"file-growth-perturbed": 0.0},
                noise_by_case={"file-growth-perturbed": 1.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_perturbation_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "perturbation": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    failures = slice_payload["failures"]
    assert any(
        item["perturbation"] == "file_growth" and item["metric"] == "task_success_hit"
        for item in failures
    )
    assert any(
        item["perturbation"] == "file_growth" and item["metric"] == "noise_increase"
        for item in failures
    )


def test_run_perturbation_slice_fails_on_query_paraphrase_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        cases_payload = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
        cases = cases_payload.get("cases", []) if isinstance(cases_payload, dict) else []
        case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
        if "query-paraphrase-perturbed" in case_ids:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"query-paraphrase-perturbed": 0.0},
                precision_by_case={"query-paraphrase-perturbed": 0.0},
                noise_by_case={"query-paraphrase-perturbed": 1.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_perturbation_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "perturbation": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    failures = slice_payload["failures"]
    assert any(
        item["perturbation"] == "query_paraphrase" and item["metric"] == "task_success_hit"
        for item in failures
    )
    assert any(
        item["perturbation"] == "query_paraphrase" and item["metric"] == "noise_increase"
        for item in failures
    )


def test_run_late_interaction_slice_passes_when_provider_does_not_regress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_providers: list[str] = []

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        provider = str(cmd[cmd.index("--embedding-provider") + 1])
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        seen_providers.append(provider)
        if provider == "hash_colbert":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 1.0},
                noise_by_case={"late-interaction-01": 0.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 1.0},
                noise_by_case={"late-interaction-01": 0.0},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_late_interaction_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "late_interaction": {
                    "thresholds": {
                        "precision_delta_min": 0.0,
                        "noise_delta_min": 0.0,
                    },
                    "late_interaction": {
                        "off_provider": "hash_cross",
                        "on_provider": "hash_colbert",
                    },
                }
            }
        },
    )

    assert seen_providers == ["hash_cross", "hash_colbert"]
    assert slice_payload["passed"] is True
    assert slice_payload["providers"] == {
        "off": "hash_cross",
        "on": "hash_colbert",
    }
    assert slice_payload["deltas"] == {
        "precision_delta": 0.0,
        "noise_delta": 0.0,
    }


def test_run_late_interaction_slice_fails_on_precision_and_noise_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        provider = str(cmd[cmd.index("--embedding-provider") + 1])
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if provider == "hash_colbert":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"late-interaction-01": 0.0},
                precision_by_case={"late-interaction-01": 0.0},
                noise_by_case={"late-interaction-01": 1.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 1.0},
                noise_by_case={"late-interaction-01": 0.0},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_late_interaction_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "late_interaction": {
                    "thresholds": {
                        "precision_delta_min": 0.0,
                        "noise_delta_min": 0.0,
                    },
                    "late_interaction": {
                        "off_provider": "hash_cross",
                        "on_provider": "hash_colbert",
                    },
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    failures = slice_payload["failures"]
    assert any(item["metric"] == "precision_delta" for item in failures)
    assert any(item["metric"] == "noise_delta" for item in failures)


def test_run_feedback_slice_passes_when_feedback_improves_precision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if str(output_dir.name).endswith("feedback-on"):
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"feedback-01": 1.0},
                precision_by_case={"feedback-01": 1.0},
                noise_by_case={"feedback-01": 0.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"feedback-01": 0.0},
                precision_by_case={"feedback-01": 0.0},
                noise_by_case={"feedback-01": 1.0},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_feedback_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "feedback": {
                    "thresholds": {
                        "precision_delta_min": 0.5,
                        "noise_delta_min": 0.5,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is True
    assert slice_payload["deltas"] == {
        "precision_delta": 1.0,
        "noise_delta": 1.0,
    }
    assert Path(slice_payload["on"]["output_dir"]).name == "feedback-on"


def test_run_feedback_slice_fails_when_feedback_regresses_precision_and_noise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if str(output_dir.name).endswith("feedback-on"):
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"feedback-01": 0.0},
                precision_by_case={"feedback-01": 0.25},
                noise_by_case={"feedback-01": 0.75},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"feedback-01": 1.0},
                precision_by_case={"feedback-01": 1.0},
                noise_by_case={"feedback-01": 0.0},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_feedback_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "feedback": {
                    "thresholds": {
                        "precision_delta_min": 0.0,
                        "noise_delta_min": 0.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    assert {item["metric"] for item in slice_payload["failures"]} == {
        "precision_delta",
        "noise_delta",
    }


def test_run_temporal_slice_fails_when_time_window_regresses_precision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_temporal_flags: list[tuple[str, str]] = []

    def fake_run_command(*, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if "--start-date" in cmd and "--end-date" in cmd:
            seen_temporal_flags.append(
                (
                    str(cmd[cmd.index("--start-date") + 1]),
                    str(cmd[cmd.index("--end-date") + 1]),
                )
            )
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"temporal-01": 0.0},
                precision_by_case={"temporal-01": 0.0},
                noise_by_case={"temporal-01": 1.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"temporal-01": 1.0},
                precision_by_case={"temporal-01": 1.0},
                noise_by_case={"temporal-01": 0.0},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_temporal_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "temporal": {
                    "thresholds": {
                        "precision_delta_min": 0.0,
                        "noise_delta_min": 0.0,
                    },
                    "time": {
                        "start_date": "2026-02-10",
                        "end_date": "2026-02-15",
                    },
                }
            }
        },
    )

    assert seen_temporal_flags == [("2026-02-10", "2026-02-15")]
    assert slice_payload["passed"] is False
    failures = slice_payload["failures"]
    assert any(item["metric"] == "precision_delta" for item in failures)
    assert any(item["metric"] == "noise_delta" for item in failures)


def test_run_late_interaction_slice_passes_and_records_provider_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        provider = cmd[cmd.index("--embedding-provider") + 1]
        if provider == "hash_cross":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 0.5},
                noise_by_case={"late-interaction-01": 0.4},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 1.0},
                noise_by_case={"late-interaction-01": 0.0},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_late_interaction_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "late_interaction": {
                    "thresholds": {
                        "precision_delta_min": 0.0,
                        "noise_delta_min": 0.0,
                    },
                    "late_interaction": {
                        "off_provider": "hash_cross",
                        "on_provider": "hash_colbert",
                    },
                }
            }
        },
    )

    assert slice_payload["passed"] is True
    assert slice_payload["providers"] == {
        "off": "hash_cross",
        "on": "hash_colbert",
    }
    assert slice_payload["deltas"]["precision_delta"] == pytest.approx(0.5)
    assert slice_payload["deltas"]["noise_delta"] == pytest.approx(0.4)


def test_run_late_interaction_slice_fails_on_provider_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        provider = cmd[cmd.index("--embedding-provider") + 1]
        if provider == "hash_cross":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 1.0},
                noise_by_case={"late-interaction-01": 0.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"late-interaction-01": 0.25},
                noise_by_case={"late-interaction-01": 0.75},
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_late_interaction_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "late_interaction": {
                    "thresholds": {
                        "precision_delta_min": 0.0,
                        "noise_delta_min": 0.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    assert {item["metric"] for item in slice_payload["failures"]} == {
        "precision_delta",
        "noise_delta",
    }


def test_run_dependency_recall_slice_passes_when_graph_profile_is_not_worse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_profiles: list[str] = []

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        profile = str(cmd[cmd.index("--repomap-ranking-profile") + 1])
        seen_profiles.append(profile)
        if profile == "graph_seeded":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"dependency-recall-01": 1.0},
                noise_by_case={"dependency-recall-01": 0.0},
                metrics_overrides={
                    "dependency_recall": 1.0,
                    "latency_p95_ms": 18.0,
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"dependency-recall-01": 1.0},
                noise_by_case={"dependency-recall-01": 0.0},
                metrics_overrides={
                    "dependency_recall": 0.5,
                    "latency_p95_ms": 15.0,
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_dependency_recall_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "dependency_recall": {
                    "thresholds": {
                        "dependency_recall_min": 0.8,
                        "dependency_recall_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 2.0,
                    },
                    "dependency_recall": {
                        "off_repomap_ranking_profile": "heuristic",
                        "on_repomap_ranking_profile": "graph_seeded",
                    },
                }
            }
        },
    )

    assert seen_profiles == ["heuristic", "graph_seeded"]
    assert slice_payload["passed"] is True
    assert slice_payload["profiles"] == {
        "off": "heuristic",
        "on": "graph_seeded",
    }
    assert slice_payload["deltas"]["dependency_recall_delta"] == pytest.approx(0.5)
    assert slice_payload["deltas"]["latency_growth_factor"] == pytest.approx(1.2)

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-06T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert "## Dependency Recall Details" in markdown
    assert "| graph_seeded | 1.0000 | 1.0000 | 0.0000 | 18.00 |" in markdown


def test_run_perf_routing_slice_passes_and_renders_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_routes: list[str] = []

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        precomputed_enabled = "--precomputed-skills-routing" in cmd
        seen_routes.append("precomputed" if precomputed_enabled else "same_stage")
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if precomputed_enabled:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={
                    "perf-routing-01": 1.0,
                    "perf-routing-02": 1.0,
                },
                noise_by_case={
                    "perf-routing-01": 0.0,
                    "perf-routing-02": 0.0,
                },
                routing_source_by_case={"*": "precomputed"},
                metrics_overrides={
                    "task_success_rate": 1.0,
                    "precision_at_k": 1.0,
                    "noise_rate": 0.0,
                    "latency_p95_ms": 10.0,
                    "skills_latency_p95_ms": 4.0,
                    "skills_token_budget_used_mean": 180.0,
                    "skills_budget_exhausted_ratio": 0.0,
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={
                    "perf-routing-01": 0.5,
                    "perf-routing-02": 0.5,
                },
                noise_by_case={
                    "perf-routing-01": 0.5,
                    "perf-routing-02": 0.5,
                },
                routing_source_by_case={"*": "same_stage"},
                metrics_overrides={
                    "task_success_rate": 1.0,
                    "precision_at_k": 0.5,
                    "noise_rate": 0.5,
                    "latency_p95_ms": 12.0,
                    "skills_latency_p95_ms": 4.0,
                    "skills_token_budget_used_mean": 180.0,
                    "skills_budget_exhausted_ratio": 0.0,
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_perf_routing_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "perf_routing": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 1.0,
                        "skills_latency_growth_factor_max": 1.0,
                        "skills_token_budget_used_increase_max": 0.0,
                        "skills_budget_exhausted_increase_max": 0.0,
                    },
                    "perf_routing": {
                        "retrieval_policy": "general",
                        "off_precomputed_skills_routing": False,
                        "on_precomputed_skills_routing": True,
                    },
                }
            }
        },
    )

    assert seen_routes == ["same_stage", "precomputed"]
    assert slice_payload["passed"] is True
    assert slice_payload["policy"] == "general"
    assert slice_payload["routing_sources"] == {
        "off": "same_stage",
        "on": "precomputed",
    }
    assert slice_payload["precomputed_routing_enabled"] == {
        "off": False,
        "on": True,
    }
    assert slice_payload["deltas"] == {
        "task_success_delta": 0.0,
        "precision_delta": 0.5,
        "noise_increase": -0.5,
        "latency_growth_factor": pytest.approx(10.0 / 12.0),
        "skills_latency_growth_factor": 1.0,
        "skills_token_budget_used_increase": 0.0,
        "skills_budget_exhausted_increase": 0.0,
    }

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-06T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert "## Skills Routing Details" in markdown
    assert "- Retrieval policy: general" in markdown
    assert (
        "| same_stage | 1.0000 | 0.5000 | 0.5000 | 12.00 | 4.00 | 180.00 | 0.0000 |"
        in markdown
    )
    assert (
        "| precomputed | 1.0000 | 1.0000 | 0.0000 | 10.00 | 4.00 | 180.00 | 0.0000 |"
        in markdown
    )


def test_run_dependency_recall_slice_fails_when_graph_profile_regresses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        profile = str(cmd[cmd.index("--repomap-ranking-profile") + 1])
        if profile == "graph_seeded":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"dependency-recall-01": 0.0},
                precision_by_case={"dependency-recall-01": 0.25},
                noise_by_case={"dependency-recall-01": 0.75},
                metrics_overrides={
                    "dependency_recall": 0.3,
                    "latency_p95_ms": 36.0,
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={"dependency-recall-01": 1.0},
                noise_by_case={"dependency-recall-01": 0.0},
                metrics_overrides={
                    "dependency_recall": 0.9,
                    "latency_p95_ms": 12.0,
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_dependency_recall_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "dependency_recall": {
                    "thresholds": {
                        "dependency_recall_min": 0.8,
                        "dependency_recall_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 2.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    assert {item["metric"] for item in slice_payload["failures"]} == {
        "dependency_recall",
        "dependency_recall_delta",
        "precision_delta",
        "noise_increase",
        "latency_growth_factor",
    }


def test_run_perf_routing_slice_fails_when_precomputed_routing_regresses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        precomputed_enabled = "--precomputed-skills-routing" in cmd
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if precomputed_enabled:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={
                    "perf-routing-01": 0.0,
                    "perf-routing-02": 0.0,
                },
                precision_by_case={
                    "perf-routing-01": 0.0,
                    "perf-routing-02": 0.0,
                },
                noise_by_case={
                    "perf-routing-01": 1.0,
                    "perf-routing-02": 1.0,
                },
                routing_source_by_case={"*": "same_stage"},
                metrics_overrides={
                    "task_success_rate": 0.0,
                    "precision_at_k": 0.0,
                    "noise_rate": 1.0,
                    "latency_p95_ms": 24.0,
                    "skills_latency_p95_ms": 9.0,
                    "skills_token_budget_used_mean": 220.0,
                    "skills_budget_exhausted_ratio": 0.5,
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={
                    "perf-routing-01": 1.0,
                    "perf-routing-02": 1.0,
                },
                noise_by_case={
                    "perf-routing-01": 0.0,
                    "perf-routing-02": 0.0,
                },
                routing_source_by_case={"*": "same_stage"},
                metrics_overrides={
                    "task_success_rate": 1.0,
                    "precision_at_k": 1.0,
                    "noise_rate": 0.0,
                    "latency_p95_ms": 12.0,
                    "skills_latency_p95_ms": 4.0,
                    "skills_token_budget_used_mean": 180.0,
                    "skills_budget_exhausted_ratio": 0.0,
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_perf_routing_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "perf_routing": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 1.0,
                        "skills_latency_growth_factor_max": 1.0,
                        "skills_token_budget_used_increase_max": 0.0,
                        "skills_budget_exhausted_increase_max": 0.0,
                    },
                    "perf_routing": {
                        "retrieval_policy": "general",
                        "off_precomputed_skills_routing": False,
                        "on_precomputed_skills_routing": True,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    assert {item["metric"] for item in slice_payload["failures"]} == {
        "on_routing_source",
        "task_success_rate",
        "task_success_delta",
        "precision_delta",
        "noise_increase",
        "latency_growth_factor",
        "skills_latency_growth_factor",
        "skills_token_budget_used_increase",
        "skills_budget_exhausted_increase",
    }


def test_run_stale_majority_slice_passes_and_renders_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_chunk_guard_flags: list[tuple[str, str, str, str]] = []

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if "--chunk-guard" in cmd:
            seen_chunk_guard_flags.append(
                (
                    str(cmd[cmd.index("--chunk-guard-mode") + 1]),
                    str(cmd[cmd.index("--chunk-guard-lambda-penalty") + 1]),
                    str(cmd[cmd.index("--chunk-guard-min-pool") + 1]),
                    str(cmd[cmd.index("--chunk-guard-min-marginal-utility") + 1]),
                )
            )
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"stale-majority-01": 1.0},
                precision_by_case={"stale-majority-01": 1.0},
                noise_by_case={"stale-majority-01": 0.0},
                metrics_overrides={"latency_p95_ms": 18.0},
                comparison_lane_summary={
                    "total_case_count": 1,
                    "labeled_case_count": 1,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "stale_majority",
                            "case_count": 1,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "chunk_guard_report_only_ratio": 1.0,
                            "chunk_guard_filtered_case_rate": 0.0,
                            "chunk_guard_filtered_count_mean": 0.0,
                            "chunk_guard_filter_ratio_mean": 0.0,
                            "chunk_guard_expected_retained_hit_rate_mean": 1.0,
                            "chunk_guard_report_only_improved_rate": 1.0,
                            "chunk_guard_pairwise_conflict_count_mean": 2.0,
                        }
                    ],
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"stale-majority-01": 1.0},
                precision_by_case={"stale-majority-01": 1.0},
                noise_by_case={"stale-majority-01": 0.0},
                metrics_overrides={"latency_p95_ms": 12.0},
                comparison_lane_summary={
                    "total_case_count": 1,
                    "labeled_case_count": 1,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "stale_majority",
                            "case_count": 1,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "chunk_guard_report_only_ratio": 0.0,
                            "chunk_guard_filtered_case_rate": 0.0,
                            "chunk_guard_filtered_count_mean": 0.0,
                            "chunk_guard_filter_ratio_mean": 0.0,
                            "chunk_guard_expected_retained_hit_rate_mean": 0.0,
                            "chunk_guard_report_only_improved_rate": 0.0,
                            "chunk_guard_pairwise_conflict_count_mean": 0.0,
                        }
                    ],
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_stale_majority_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "stale_majority": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 2.0,
                        "pairwise_conflict_count_mean_min": 1.0,
                        "expected_retained_hit_rate_min": 1.0,
                        "report_only_improved_rate_min": 1.0,
                    },
                    "stale_majority": {
                        "chunk_guard_mode": "report_only",
                        "chunk_guard_lambda_penalty": 4.0,
                        "chunk_guard_min_pool": 1,
                        "chunk_guard_min_marginal_utility": 0.2,
                    },
                }
            }
        },
    )

    assert seen_chunk_guard_flags == [("report_only", "4.0", "1", "0.2")]
    assert slice_payload["passed"] is True
    assert slice_payload["deltas"]["pairwise_conflict_count_delta"] == pytest.approx(2.0)
    assert slice_payload["on"]["lane_metrics"]["chunk_guard_expected_retained_hit_rate_mean"] == pytest.approx(
        1.0
    )

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-09T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert "## Stale Majority Details" in markdown
    assert "| on | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 2.0000 | 18.00 |" in markdown


def test_run_stale_majority_slice_fails_when_anchor_or_conflict_signal_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if "--chunk-guard" in cmd:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"stale-majority-01": 1.0},
                precision_by_case={"stale-majority-01": 1.0},
                noise_by_case={"stale-majority-01": 0.0},
                metrics_overrides={"latency_p95_ms": 18.0},
                comparison_lane_summary={
                    "total_case_count": 1,
                    "labeled_case_count": 1,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "stale_majority",
                            "case_count": 1,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "chunk_guard_report_only_ratio": 1.0,
                            "chunk_guard_filtered_case_rate": 0.0,
                            "chunk_guard_filtered_count_mean": 0.0,
                            "chunk_guard_filter_ratio_mean": 0.0,
                            "chunk_guard_expected_retained_hit_rate_mean": 0.0,
                            "chunk_guard_report_only_improved_rate": 0.0,
                            "chunk_guard_pairwise_conflict_count_mean": 0.0,
                        }
                    ],
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"stale-majority-01": 1.0},
                precision_by_case={"stale-majority-01": 1.0},
                noise_by_case={"stale-majority-01": 0.0},
                metrics_overrides={"latency_p95_ms": 12.0},
                comparison_lane_summary={
                    "total_case_count": 1,
                    "labeled_case_count": 1,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "stale_majority",
                            "case_count": 1,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "chunk_guard_report_only_ratio": 0.0,
                            "chunk_guard_filtered_case_rate": 0.0,
                            "chunk_guard_filtered_count_mean": 0.0,
                            "chunk_guard_filter_ratio_mean": 0.0,
                            "chunk_guard_expected_retained_hit_rate_mean": 0.0,
                            "chunk_guard_report_only_improved_rate": 0.0,
                            "chunk_guard_pairwise_conflict_count_mean": 0.0,
                        }
                    ],
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_stale_majority_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "stale_majority": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 2.0,
                        "pairwise_conflict_count_mean_min": 1.0,
                        "expected_retained_hit_rate_min": 1.0,
                        "report_only_improved_rate_min": 1.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    assert {item["metric"] for item in slice_payload["failures"]} == {
        "pairwise_conflict_count_mean",
        "expected_retained_hit_rate",
        "report_only_improved_rate",
    }


def test_run_topological_shield_slice_passes_and_renders_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if output_dir.name == "topological-shield-off":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={},
                noise_by_case={},
                metrics_overrides={"latency_p95_ms": 12.0},
                comparison_lane_summary={
                    "total_case_count": 2,
                    "labeled_case_count": 2,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "topological_shield",
                            "case_count": 2,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "graph_hub_penalty_total_mean": 0.18,
                            "topological_shield_report_only_ratio": 0.0,
                            "topological_shield_attenuated_chunk_count_mean": 0.0,
                            "topological_shield_attenuation_total_mean": 0.0,
                        }
                    ],
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={},
                noise_by_case={},
                metrics_overrides={"latency_p95_ms": 18.0},
                comparison_lane_summary={
                    "total_case_count": 2,
                    "labeled_case_count": 2,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "topological_shield",
                            "case_count": 2,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "graph_hub_penalty_total_mean": 0.18,
                            "topological_shield_report_only_ratio": 1.0,
                            "topological_shield_attenuated_chunk_count_mean": 0.5,
                            "topological_shield_attenuation_total_mean": 0.2,
                        }
                    ],
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_topological_shield_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "topological_shield": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 2.0,
                        "attenuated_chunk_count_mean_min": 0.5,
                        "attenuation_total_mean_min": 0.05,
                        "require_repeat_fingerprints_equal": True,
                        "require_repeat_lane_metrics_equal": True,
                    },
                    "topological_shield": {
                        "mode": "report_only",
                        "max_attenuation": 0.6,
                        "shared_parent_attenuation": 0.2,
                        "adjacency_attenuation": 0.5,
                    },
                }
            }
        },
    )

    assert slice_payload["passed"] is True
    assert slice_payload["deltas"]["attenuated_chunk_count_delta"] == pytest.approx(0.5)
    assert slice_payload["repeat"]["case_fingerprints_equal"] is True
    assert slice_payload["repeat"]["lane_metrics_equal"] is True

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-09T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert "## Topological Shield Details" in markdown
    assert "| on | 1.0000 | 1.0000 | 0.0000 | 0.5000 | 0.2000 | 0.1800 | 18.00 | PASS |" in markdown


def test_run_topological_shield_slice_fails_when_structural_or_repeat_signal_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        if output_dir.name == "topological-shield-off":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={},
                noise_by_case={},
                metrics_overrides={"latency_p95_ms": 12.0},
                comparison_lane_summary={
                    "total_case_count": 2,
                    "labeled_case_count": 2,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "topological_shield",
                            "case_count": 2,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "graph_hub_penalty_total_mean": 0.18,
                            "topological_shield_report_only_ratio": 0.0,
                            "topological_shield_attenuated_chunk_count_mean": 0.0,
                            "topological_shield_attenuation_total_mean": 0.0,
                        }
                    ],
                },
            )
        elif output_dir.name == "topological-shield-repeat":
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"topological-shield-hub-heavy-02": 0.0},
                precision_by_case={"topological-shield-hub-heavy-02": 0.0},
                noise_by_case={"topological-shield-hub-heavy-02": 1.0},
                metrics_overrides={"latency_p95_ms": 18.0},
                comparison_lane_summary={
                    "total_case_count": 2,
                    "labeled_case_count": 2,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "topological_shield",
                            "case_count": 2,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "graph_hub_penalty_total_mean": 0.18,
                            "topological_shield_report_only_ratio": 1.0,
                            "topological_shield_attenuated_chunk_count_mean": 0.0,
                            "topological_shield_attenuation_total_mean": 0.0,
                        }
                    ],
                },
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={},
                noise_by_case={},
                metrics_overrides={"latency_p95_ms": 18.0},
                comparison_lane_summary={
                    "total_case_count": 2,
                    "labeled_case_count": 2,
                    "lane_count": 1,
                    "lanes": [
                        {
                            "comparison_lane": "topological_shield",
                            "case_count": 2,
                            "task_success_rate": 1.0,
                            "recall_at_k": 1.0,
                            "graph_hub_penalty_total_mean": 0.18,
                            "topological_shield_report_only_ratio": 1.0,
                            "topological_shield_attenuated_chunk_count_mean": 0.0,
                            "topological_shield_attenuation_total_mean": 0.0,
                        }
                    ],
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_topological_shield_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "topological_shield": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "latency_growth_factor_max": 2.0,
                        "attenuated_chunk_count_mean_min": 0.5,
                        "attenuation_total_mean_min": 0.05,
                        "require_repeat_fingerprints_equal": True,
                        "require_repeat_lane_metrics_equal": True,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    assert {item["metric"] for item in slice_payload["failures"]} == {
        "topological_shield_attenuated_chunk_count_mean",
        "topological_shield_attenuation_total_mean",
        "repeat_case_fingerprints_equal",
    }


def test_run_repomap_perturbation_slice_passes_and_renders_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")
    seen_profiles: list[str] = []

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        assert "--repomap" in cmd
        profile = str(cmd[cmd.index("--repomap-ranking-profile") + 1])
        seen_profiles.append(profile)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        _write_benchmark_results(
            output_dir=output_dir,
            cases_path=cases_path,
            task_success_by_case={},
            precision_by_case={
                "graph-rename-base": 1.0,
                "graph-path-move-base": 1.0,
                "graph-rename-perturbed": 1.0,
                "graph-path-move-perturbed": 1.0,
            },
            noise_by_case={
                "graph-rename-base": 0.0,
                "graph-path-move-base": 0.0,
                "graph-rename-perturbed": 0.0,
                "graph-path-move-perturbed": 0.0,
            },
            dependency_recall_by_case={
                "graph-rename-base": 1.0,
                "graph-path-move-base": 1.0,
                "graph-rename-perturbed": 1.0,
                "graph-path-move-perturbed": 1.0,
            },
        )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_repomap_perturbation_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "repomap_perturbation": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "dependency_recall_min": 0.8,
                        "dependency_recall_delta_min": 0.0,
                    },
                    "repomap_perturbation": {
                        "repomap_ranking_profile": "graph_seeded",
                    },
                }
            }
        },
    )

    assert seen_profiles == ["graph_seeded", "graph_seeded"]
    assert slice_payload["passed"] is True
    assert slice_payload["profiles"] == {"repomap": "graph_seeded"}
    assert [item["name"] for item in slice_payload["perturbations"]] == [
        "dependency_rename",
        "dependency_path_move",
    ]
    assert slice_payload["deltas"] == {
        "task_success_delta": 0.0,
        "precision_delta": 0.0,
        "noise_increase": 0.0,
        "dependency_recall_delta": 0.0,
    }

    markdown = module._render_markdown(
        {
            "generated_at": "2026-03-06T00:00:00Z",
            "passed": True,
            "slices": [slice_payload],
        }
    )
    assert "## Repomap Perturbation Details" in markdown
    assert "| dependency_path_move | PASS | +0.0000 | +0.0000 | +0.0000 | +0.0000 |" in markdown


def test_run_repomap_perturbation_slice_fails_on_dependency_recall_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_feature_slice_matrix.py")

    def fake_run_command(
        *,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        _ = (cwd, env)
        output_dir = Path(cmd[cmd.index("--output") + 1])
        cases_path = Path(cmd[cmd.index("--cases") + 1])
        cases_payload = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
        cases = cases_payload.get("cases", []) if isinstance(cases_payload, dict) else []
        case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
        if "graph-path-move-perturbed" in case_ids:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={"graph-path-move-perturbed": 0.0},
                precision_by_case={"graph-path-move-perturbed": 0.0},
                noise_by_case={"graph-path-move-perturbed": 1.0},
                dependency_recall_by_case={"graph-path-move-perturbed": 0.0},
            )
        else:
            _write_benchmark_results(
                output_dir=output_dir,
                cases_path=cases_path,
                task_success_by_case={},
                precision_by_case={
                    "graph-rename-base": 1.0,
                    "graph-path-move-base": 1.0,
                    "graph-rename-perturbed": 1.0,
                },
                noise_by_case={
                    "graph-rename-base": 0.0,
                    "graph-path-move-base": 0.0,
                    "graph-rename-perturbed": 0.0,
                },
                dependency_recall_by_case={
                    "graph-rename-base": 1.0,
                    "graph-path-move-base": 1.0,
                    "graph-rename-perturbed": 1.0,
                },
            )
        return module.CommandResult(
            cmd=cmd,
            cwd=None,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    slice_payload = module._run_repomap_perturbation_slice(
        cli_bin="ace-lite",
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        config={
            "slices": {
                "repomap_perturbation": {
                    "thresholds": {
                        "task_success_min": 1.0,
                        "task_success_delta_min": 0.0,
                        "precision_delta_min": 0.0,
                        "noise_increase_max": 0.0,
                        "dependency_recall_min": 0.8,
                        "dependency_recall_delta_min": 0.0,
                    }
                }
            }
        },
    )

    assert slice_payload["passed"] is False
    failures = slice_payload["failures"]
    assert any(
        item["perturbation"] == "dependency_path_move"
        and item["metric"] == "dependency_recall"
        for item in failures
    )
    assert any(
        item["perturbation"] == "dependency_path_move"
        and item["metric"] == "dependency_recall_delta"
        for item in failures
    )
    assert any(
        item["perturbation"] == "dependency_path_move"
        and item["metric"] == "noise_increase"
        for item in failures
    )
