from __future__ import annotations

import importlib.util
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


def test_academic_optimization_benchmark_script_defaults() -> None:
    module = _load_script("run_academic_optimization_benchmark.py")

    root = Path(__file__).resolve().parents[2]
    paths = module._default_paths(root=root)
    query_expansion_paths = module._default_paths_for_lane(
        root=root,
        lane="query_expansion_experiment",
    )
    semantic_paths = module._default_paths_for_lane(root=root, lane="semantic_experiment")

    assert paths["cases"] == (root / "benchmark" / "cases" / "academic_optimization.yaml").resolve()
    assert paths["index"] == (root / "context-map" / "index.json").resolve()
    assert paths["output"] == (
        root / "artifacts" / "benchmark" / "academic_optimization" / "baseline" / "latest"
    ).resolve()
    assert paths["results"] == (paths["output"] / "results.json").resolve()
    assert paths["summary"] == (paths["output"] / "summary.json").resolve()
    assert paths["report"] == (paths["output"] / "report.md").resolve()
    assert query_expansion_paths["output"] == (
        root
        / "artifacts"
        / "benchmark"
        / "academic_optimization"
        / "query_expansion_experiment"
        / "latest"
    ).resolve()
    assert semantic_paths["output"] == (
        root / "artifacts" / "benchmark" / "academic_optimization" / "semantic_experiment" / "latest"
    ).resolve()


def test_academic_optimization_benchmark_script_builds_cli_commands() -> None:
    module = _load_script("run_academic_optimization_benchmark.py")

    root = Path(__file__).resolve().parents[2]
    paths = module._default_paths(root=root)
    index_cmd = module._build_index_command(
        paths=paths,
        languages="python,go",
    )
    benchmark_cmd = module._build_benchmark_command(
        paths=paths,
        repo="ace-lite",
        languages="python,go",
        warmup_runs=2,
    )
    report_cmd = module._build_report_command(paths=paths)

    assert index_cmd[0].endswith("ace-lite")
    assert "index" in index_cmd
    assert str(paths["index"]) in index_cmd
    assert "python,go" in index_cmd

    assert benchmark_cmd[0].endswith("ace-lite")
    assert benchmark_cmd[1:3] == ["benchmark", "run"]
    assert "--cases" in benchmark_cmd
    assert str(paths["cases"]) in benchmark_cmd
    assert "--repo" in benchmark_cmd
    assert "ace-lite" in benchmark_cmd
    assert "--warmup-runs" in benchmark_cmd
    assert "2" in benchmark_cmd
    assert benchmark_cmd.count("--memory-primary") == 1
    assert benchmark_cmd.count("--memory-secondary") == 1
    assert report_cmd[0] == sys.executable
    assert report_cmd[1].endswith("scripts/build_academic_optimization_report.py")
    assert report_cmd[-6:] == [
        "--results",
        str(paths["results"]),
        "--cases",
        str(paths["cases"]),
        "--output-dir",
        str(paths["output"]),
    ]

    assert module._default_query_expansion_enabled(lane="baseline") is True
    assert module._default_query_expansion_enabled(lane="semantic_experiment") is True
    assert module._default_query_expansion_enabled(lane="query_expansion_experiment") is False
    assert module._benchmark_env(query_expansion_enabled=False)[
        "ACE_LITE_QUERY_EXPANSION_ENABLED"
    ] == "0"

    semantic_cmd = module._build_benchmark_command(
        paths=paths,
        repo="ace-lite",
        languages="python,go",
        warmup_runs=1,
        embedding_enabled=True,
        embedding_provider="hash_cross",
        embedding_model="hash-cross-v1",
        embedding_rerank_pool=16,
    )
    assert "--embedding-enabled" in semantic_cmd
    assert semantic_cmd[semantic_cmd.index("--embedding-provider") + 1] == "hash_cross"
    assert semantic_cmd[semantic_cmd.index("--embedding-model") + 1] == "hash-cross-v1"
    assert semantic_cmd[semantic_cmd.index("--embedding-rerank-pool") + 1] == "16"

    report_cmd_with_baseline = module._build_report_command(
        paths={
            **paths,
            "baseline_summary": (root / "artifacts" / "benchmark" / "academic_optimization" / "latest" / "academic_summary.json").resolve(),
            "query_expansion_enabled": False,
        }
    )
    assert "--baseline-summary" in report_cmd_with_baseline
    assert report_cmd_with_baseline[report_cmd_with_baseline.index("--baseline-summary") + 1].endswith(
        "artifacts/benchmark/academic_optimization/latest/academic_summary.json"
    )
    assert "--query-expansion-enabled" in report_cmd_with_baseline
    assert report_cmd_with_baseline[report_cmd_with_baseline.index("--query-expansion-enabled") + 1] == "false"


def test_academic_optimization_benchmark_script_resolves_baseline_summary_with_legacy_fallback(
    tmp_path: Path,
) -> None:
    module = _load_script("run_academic_optimization_benchmark.py")

    root = tmp_path / "repo"
    legacy = root / "artifacts" / "benchmark" / "academic_optimization" / "latest"
    legacy.mkdir(parents=True)
    legacy_summary = legacy / "academic_summary.json"
    legacy_summary.write_text("{}", encoding="utf-8")

    resolved = module._resolve_existing_baseline_summary(root=root)

    assert resolved == legacy_summary.resolve()


def test_academic_optimization_benchmark_script_clears_candidate_cache(tmp_path: Path) -> None:
    module = _load_script("run_academic_optimization_benchmark.py")

    root = tmp_path / "repo"
    cache_path = root / "context-map" / "index_candidates" / "cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("{}", encoding="utf-8")

    assert module._candidate_cache_path(root=root) == cache_path.resolve()
    assert module._clear_candidate_cache(root=root) is True
    assert not cache_path.exists()
    assert module._clear_candidate_cache(root=root) is False
