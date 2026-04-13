from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def test_workspace_summary_benchmark_assets_cover_summary_routing_lane() -> None:
    root = Path(__file__).resolve().parents[2]
    cases = json.loads(
        (root / "benchmark" / "workspace" / "cases" / "summary_routing_cases.json").read_text(
            encoding="utf-8"
        )
    )
    baseline = json.loads(
        (root / "benchmark" / "workspace" / "baseline" / "summary_routing.json").read_text(
            encoding="utf-8"
        )
    )

    assert [item["id"] for item in cases["cases"]] == [
        "workspace-summary-ui-01",
        "workspace-summary-ops-02",
        "workspace-summary-baseline-control-03",
    ]
    assert baseline["checks"]["hit_at_k"]["min"] == 1.0
    assert baseline["checks"]["summary_match_case_rate"]["min"] == 0.666667
    assert baseline["checks"]["summary_promoted_case_rate"]["min"] == 0.666667


def test_workspace_summary_benchmark_script_defaults() -> None:
    module = _load_script("run_workspace_summary_benchmark.py")
    root = Path(__file__).resolve().parents[2]
    paths = module._default_paths(root=root)

    assert paths["cases"] == (
        root / "benchmark" / "workspace" / "cases" / "summary_routing_cases.json"
    ).resolve()
    assert paths["baseline"] == (
        root / "benchmark" / "workspace" / "baseline" / "summary_routing.json"
    ).resolve()
    assert paths["output"] == (
        root / "artifacts" / "benchmark" / "workspace_summary" / "latest"
    ).resolve()
    assert paths["manifest"] == (paths["output"] / "fixture" / "workspace.yaml").resolve()


def test_workspace_summary_benchmark_script_builds_comparison_payload() -> None:
    module = _load_script("run_workspace_summary_benchmark.py")

    comparison = module._build_comparison(
        without_summary={
            "metrics": {"hit_at_k": 0.333333, "mrr": 0.333333, "avg_latency_ms": 10.0},
            "cases": [
                {
                    "id": "c1",
                    "query": "pager alert router",
                    "expected_repos": ["zulu-ops"],
                    "predicted_repos": ["alpha-core"],
                    "hit": False,
                }
            ],
        },
        with_summary={
            "metrics": {
                "hit_at_k": 1.0,
                "mrr": 1.0,
                "avg_latency_ms": 12.0,
                "summary_match_case_rate": 1.0,
                "summary_promoted_case_rate": 1.0,
            },
            "cases": [
                {
                    "id": "c1",
                    "query": "pager alert router",
                    "expected_repos": ["zulu-ops"],
                    "predicted_repos": ["zulu-ops"],
                    "hit": True,
                    "summary_routing": {
                        "matched_repos": ["zulu-ops"],
                        "promoted_expected_repo": True,
                    },
                }
            ],
            "baseline_check": {"ok": True, "checked_metrics": ["hit_at_k"]},
        },
    )

    assert comparison["metric_delta"]["hit_at_k"]["delta"] == 0.666667
    assert comparison["metric_delta"]["summary_promoted_case_rate"]["with_summary"] == 1.0
    assert comparison["case_comparison"][0]["expected_repo_promoted"] is True
    assert comparison["case_comparison"][0]["matched_summary_repos"] == ["zulu-ops"]


def test_workspace_summary_benchmark_script_main_writes_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script("run_workspace_summary_benchmark.py")
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "workspace-summary"

    responses = iter(
        [
            {"artifacts": {"summary": str(output_dir / "fixture" / "context-map" / "workspace" / "summary-index.v1.json")}},
            {
                "metrics": {"hit_at_k": 0.333333, "mrr": 0.333333, "avg_latency_ms": 10.0},
                "cases": [],
            },
            {
                "metrics": {
                    "hit_at_k": 1.0,
                    "mrr": 1.0,
                    "avg_latency_ms": 12.0,
                    "summary_match_case_rate": 0.666667,
                    "summary_promoted_case_rate": 0.666667,
                },
                "cases": [],
                "baseline_check": {"ok": True, "checked_metrics": ["hit_at_k"]},
            },
        ]
    )

    monkeypatch.setattr(module, "_run_json_command", lambda **kwargs: next(responses))

    exit_code = module.main(
        [
            "--root",
            str(root),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "comparison.json").exists()
    assert (output_dir / "comparison.md").exists()
    comparison = json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))
    assert comparison["metric_delta"]["summary_match_case_rate"]["with_summary"] == 0.666667
    markdown = (output_dir / "comparison.md").read_text(encoding="utf-8")
    assert "# Workspace Summary Benchmark Comparison" in markdown
