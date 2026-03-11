from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from click.testing import CliRunner

from ace_lite.cli import cli
from ace_lite.router_reward_store import append_reward_event
from ace_lite.router_reward_store import DEFAULT_REWARD_LOG_PATH
from ace_lite.router_reward_store import make_reward_event


def _seed_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "auth.py").write_text("def validate_token(x):\n    return bool(x)\n", encoding="utf-8")
    (root / "skills" / "s.md").write_text("---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n", encoding="utf-8")
    (root / "benchmark" / "cases" / "default.yaml").write_text(
        "cases:\n  - case_id: c1\n    query: where validate token\n    expected_keys: [validate_token, auth]\n    top_k: 4\n",
        encoding="utf-8",
    )


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_benchmark_run_and_report(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--candidate-ranker",
            "hybrid_re2",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--warmup-runs",
            "1",
            "--no-include-plans",
            "--no-include-case-details",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    results_json = Path(payload["results_json"])
    report_md = Path(payload["report_md"])
    summary_json = Path(payload["summary_json"])

    assert results_json.exists()
    assert report_md.exists()
    assert summary_json.exists()
    results_payload = json.loads(results_json.read_text(encoding="utf-8"))
    assert results_payload["warmup_runs"] == 1
    assert results_payload["warmup_plan_calls"] >= 1
    assert results_payload["include_plan_payload"] is False
    assert results_payload["include_case_details"] is False
    assert results_payload["cases"]
    assert "plan" not in results_payload["cases"][0]
    assert "candidate_paths" not in results_payload["cases"][0]
    assert "validation_tests" not in results_payload["cases"][0]
    assert results_payload["reward_log_summary"] == {
        "enabled": False,
        "active": False,
        "status": "disabled",
        "path": DEFAULT_REWARD_LOG_PATH,
        "eligible_case_count": 0,
        "submitted_count": 0,
        "pending_count": 0,
        "written_count": 0,
        "error_count": 0,
        "last_error": "",
    }
    summary_payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary_payload["case_count"] == 1
    assert summary_payload["reward_log_summary"]["status"] == "disabled"

    report_result = runner.invoke(
        cli,
        [
            "benchmark",
            "report",
            "--input",
            str(results_json),
        ],
        env=_cli_env(tmp_path),
    )
    assert report_result.exit_code == 0
    report_path = Path(report_result.output.strip())
    assert report_path.exists()
    assert "## Reward Log Summary" in report_path.read_text(encoding="utf-8")


def test_cli_benchmark_run_can_export_runtime_stats_snapshot(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--runtime-stats",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    summary_json = Path(payload["summary_json"])
    report_md = Path(payload["report_md"])
    summary_payload = json.loads(summary_json.read_text(encoding="utf-8"))
    runtime_stats = summary_payload["runtime_stats_summary"]
    assert runtime_stats["latest_match"]["repo_key"] == "demo"
    assert runtime_stats["summary"]["session"]["counters"]["invocation_count"] == 1
    assert runtime_stats["summary"]["all_time"]["counters"]["invocation_count"] == 1
    assert "## Runtime Stats Summary" in report_md.read_text(encoding="utf-8")


def test_cli_benchmark_fail_on_regression(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"
    baseline_path = tmp_path / "artifacts" / "benchmark" / "baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "recall_at_k": 1.0,
                    "precision_at_k": 1.0,
                    "utility_rate": 1.0,
                    "noise_rate": 0.0,
                    "latency_p95_ms": 0.1,
                }
            }
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--baseline",
            str(baseline_path),
            "--benchmark-threshold-profile",
            "strict",
            "--validation-test-growth-factor",
            "1.7",
            "--dependency-recall-floor",
            "0.85",
            "--chunk-hit-tolerance",
            "0.03",
            "--chunk-budget-growth-factor",
            "1.2",
            "--fail-on-regression",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "benchmark regression detected" in result.output
    assert (output_dir / "results.json").exists()
    assert (output_dir / "report.md").exists()

    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert payload["threshold_profile"] == "strict"
    assert payload["regression_thresholds"]["validation_test_growth_factor"] == 1.7
    assert payload["regression_thresholds"]["dependency_recall_floor"] == 0.85
    assert payload["regression_thresholds"]["chunk_hit_tolerance"] == 0.03
    assert payload["regression_thresholds"]["chunk_budget_growth_factor"] == 1.2
    assert "failed_thresholds" in payload["regression"]


def test_cli_benchmark_uses_repo_config_threshold_profile(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"
    baseline_path = tmp_path / "artifacts" / "benchmark" / "baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "recall_at_k": 1.0,
                    "precision_at_k": 1.0,
                    "utility_rate": 1.0,
                    "noise_rate": 0.0,
                    "latency_p95_ms": 0.1,
                }
            }
        ),
        encoding="utf-8",
    )

    (tmp_path / ".ace-lite.yml").write_text(
        "benchmark:\n  threshold_profile: strict\n  thresholds:\n    validation_test_growth_factor: 1.9\n    dependency_recall_floor: 0.82\n    chunk_hit_tolerance: 0.01\n    chunk_budget_growth_factor: 1.18\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--baseline",
            str(baseline_path),
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert payload["threshold_profile"] == "strict"
    assert payload["regression_thresholds"]["validation_test_growth_factor"] == 1.9
    assert payload["regression_thresholds"]["dependency_recall_floor"] == 0.82
    assert payload["regression_thresholds"]["chunk_hit_tolerance"] == 0.01
    assert payload["regression_thresholds"]["chunk_budget_growth_factor"] == 1.18


def test_cli_benchmark_reports_complete_threshold_keys(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"
    baseline_path = tmp_path / "artifacts" / "benchmark" / "baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "recall_at_k": 1.0,
                    "precision_at_k": 1.0,
                    "utility_rate": 1.0,
                    "noise_rate": 0.0,
                    "latency_p95_ms": 0.1,
                }
            }
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--baseline",
            str(baseline_path),
            "--benchmark-threshold-profile",
            "strict",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    thresholds = payload["regression_thresholds"]
    assert set(thresholds.keys()) == {
        "precision_tolerance",
        "noise_tolerance",
        "latency_growth_factor",
        "dependency_recall_floor",
        "chunk_hit_tolerance",
        "chunk_budget_growth_factor",
        "validation_test_growth_factor",
        "notes_hit_tolerance",
        "profile_selected_tolerance",
        "capture_trigger_tolerance",
        "embedding_similarity_tolerance",
        "embedding_rerank_ratio_tolerance",
        "embedding_cache_hit_tolerance",
        "embedding_fallback_tolerance",
    }


def test_cli_benchmark_passes_grouped_config_objects_to_factory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_repo(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
benchmark:
  skills:
    precomputed_routing_enabled: false
  embeddings:
    enabled: true
    provider: ollama
    model: bge-m3
    dimension: 1024
    index_path: context-map/embeddings/custom.json
    rerank_pool: 32
    lexical_weight: 0.55
    semantic_weight: 0.45
    min_similarity: 0.1
    fail_open: false
  index:
    cache_path: context-map/custom-index.json
    incremental: false
    conventions_files:
      - STYLE.md
  retrieval:
    top_k_files: 2
    min_candidate_score: 4
    candidate_relative_threshold: 0.2
    candidate_ranker: bm25_lite
    exact_search_enabled: true
    deterministic_refine_enabled: false
    exact_search_time_budget_ms: 90
    exact_search_max_paths: 7
    hybrid_re2_fusion_mode: rrf
    hybrid_re2_rrf_k: 75
    hybrid_re2_bm25_weight: 0.4
    hybrid_re2_heuristic_weight: 0.35
    hybrid_re2_coverage_weight: 0.25
    hybrid_re2_combined_scale: 1.2
  adaptive_router:
    enabled: true
    mode: shadow
    model_path: custom/router/model.json
    state_path: custom/router/state.json
    arm_set: retrieval_policy_shadow
  plugins:
    enabled: false
    remote_slot_policy_mode: warn
    remote_slot_allowlist:
      - observability.mcp_plugins
      - source_plan.writeback_template
  repomap:
    enabled: false
    top_k: 4
    neighbor_limit: 11
    budget_tokens: 420
    ranking_profile: graph_seeded
    signal_weights:
      imports: 1.5
      cochange: 0.75
  lsp:
    enabled: true
    top_n: 9
    commands:
      python:
        - pylsp
    xref_enabled: true
    xref_top_n: 6
    time_budget_ms: 2200
    xref_commands:
      python:
        - pylsp-xref
  chunk:
    top_k: 5
    per_file_limit: 2
    disclosure: signature
    signature: true
    token_budget: 700
    snippet:
      max_lines: 9
      max_chars: 320
    guard:
      mode: report_only
  tokenizer:
    model: gpt-4.1-nano
  cochange:
    enabled: false
    cache_path: context-map/cochange/custom.json
    lookback_commits: 128
    half_life_days: 14.0
    top_neighbors: 6
    boost_weight: 0.75
  tests:
    junit_xml: artifacts/junit.xml
    coverage_json: artifacts/coverage.json
    sbfl:
      json_path: artifacts/sbfl.json
      metric: dstar
  scip:
    enabled: true
    index_path: context-map/scip/custom-index.json
    provider: scip_lite
    generate_fallback: false
  trace:
    export_enabled: true
    export_path: context-map/traces/benchmark-config-trace.jsonl
    otlp_enabled: true
    otlp_endpoint: file://context-map/traces/benchmark-trace-otlp.json
    otlp_timeout_seconds: 2.5
  plan_replay_cache:
    enabled: true
    cache_path: custom/plan-replay/cache.json
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}
    orchestrator_sentinel = object()

    class FakeBenchmarkRunner:
        def __init__(self, orchestrator: object, **kwargs: Any) -> None:
            captured["orchestrator"] = orchestrator
            captured["benchmark_runner_kwargs"] = kwargs

        def run(self, **kwargs: Any) -> dict[str, Any]:
            captured["runner_kwargs"] = kwargs
            return {"cases": [], "metrics": {}, "regression": {}}

    def fake_create_orchestrator(**kwargs: Any) -> object:
        captured.update(kwargs)
        return orchestrator_sentinel

    def fake_write_results(results: dict[str, Any], output_dir: str) -> dict[str, str]:
        captured["results"] = results
        captured["output_dir"] = output_dir
        return {
            "results_json": str(Path(output_dir) / "results.json"),
            "report_md": str(Path(output_dir) / "report.md"),
            "summary_json": str(Path(output_dir) / "summary.json"),
        }

    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.create_memory_provider",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.create_orchestrator",
        fake_create_orchestrator,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.BenchmarkRunner",
        FakeBenchmarkRunner,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.write_results",
        fake_write_results,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output",
            str(tmp_path / "artifacts" / "benchmark" / "capture"),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["orchestrator"] is orchestrator_sentinel
    assert captured["skills_config"] == {
        "dir": str(tmp_path / "skills"),
        "precomputed_routing_enabled": False,
    }
    assert captured["index_config"] == {
        "languages": ["python"],
        "cache_path": "context-map/custom-index.json",
        "incremental": False,
        "conventions_files": ["STYLE.md"],
    }
    assert captured["embeddings_config"] == {
        "enabled": True,
        "provider": "ollama",
        "model": "bge-m3",
        "dimension": 1024,
        "index_path": "context-map/embeddings/custom.json",
        "rerank_pool": 32,
        "lexical_weight": 0.55,
        "semantic_weight": 0.45,
        "min_similarity": 0.1,
        "fail_open": False,
    }
    assert captured["adaptive_router_config"] == {
        "enabled": True,
        "mode": "shadow",
        "model_path": "custom/router/model.json",
        "state_path": "custom/router/state.json",
        "arm_set": "retrieval_policy_shadow",
    }
    assert captured["plugins_config"] == {
        "enabled": False,
        "remote_slot_policy_mode": "warn",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }
    assert captured["repomap_config"] == {
        "enabled": False,
        "top_k": 4,
        "neighbor_limit": 11,
        "budget_tokens": 420,
        "ranking_profile": "graph_seeded",
        "signal_weights": {"imports": 1.5, "cochange": 0.75},
    }
    assert captured["lsp_config"] == {
        "enabled": True,
        "top_n": 9,
        "commands": {"python": ["pylsp"]},
        "xref_enabled": True,
        "xref_top_n": 6,
        "time_budget_ms": 2200,
        "xref_commands": {"python": ["pylsp-xref"]},
    }
    assert captured["retrieval_config"] == {
        "top_k_files": 2,
        "min_candidate_score": 4,
        "candidate_relative_threshold": 0.2,
        "candidate_ranker": "bm25_lite",
        "exact_search_enabled": True,
        "deterministic_refine_enabled": False,
        "exact_search_time_budget_ms": 90,
        "exact_search_max_paths": 7,
        "hybrid_re2_fusion_mode": "rrf",
        "hybrid_re2_rrf_k": 75,
        "hybrid_re2_bm25_weight": 0.4,
        "hybrid_re2_heuristic_weight": 0.35,
        "hybrid_re2_coverage_weight": 0.25,
        "hybrid_re2_combined_scale": 1.2,
        "adaptive_router": {
            "enabled": True,
            "mode": "shadow",
            "model_path": "custom/router/model.json",
            "state_path": "custom/router/state.json",
            "arm_set": "retrieval_policy_shadow",
        },
    }
    assert captured["chunking_config"] == {
        "top_k": 5,
        "per_file_limit": 2,
        "disclosure": "signature",
        "signature": True,
        "snippet": {"max_lines": 9, "max_chars": 320},
        "token_budget": 700,
        "topological_shield": {
            "enabled": False,
            "mode": "off",
            "max_attenuation": 0.6,
            "shared_parent_attenuation": 0.2,
            "adjacency_attenuation": 0.5,
        },
        "guard": {
            "enabled": True,
            "mode": "report_only",
            "lambda_penalty": 0.8,
            "min_pool": 4,
            "max_pool": 32,
            "min_marginal_utility": 0.0,
            "compatibility_min_overlap": 0.3,
        },
    }
    assert captured["tokenizer_config"] == {"model": "gpt-4.1-nano"}
    assert captured["cochange_config"] == {
        "enabled": False,
        "cache_path": "context-map/cochange/custom.json",
        "lookback_commits": 128,
        "half_life_days": 14.0,
        "top_neighbors": 6,
        "boost_weight": 0.75,
    }
    assert captured["tests_config"] == {
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl_json": "artifacts/sbfl.json",
        "sbfl_metric": "dstar",
    }
    assert captured["scip_config"] == {
        "enabled": True,
        "index_path": "context-map/scip/custom-index.json",
        "provider": "scip_lite",
        "generate_fallback": False,
    }
    assert captured["trace_config"] == {
        "export_enabled": True,
        "export_path": "context-map/traces/benchmark-config-trace.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/benchmark-trace-otlp.json",
        "otlp_timeout_seconds": 2.5,
    }
    assert captured["plan_replay_cache_config"] == {
        "enabled": True,
        "cache_path": "custom/plan-replay/cache.json",
    }


def test_cli_plan_accepts_candidate_ranker(tmp_path: Path) -> None:
    _seed_repo(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement auth helper",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--candidate-ranker",
            "rrf_hybrid",
            "--hybrid-re2-rrf-k",
            "75",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_benchmark_run_accepts_candidate_ranker(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--candidate-ranker",
            "bm25_lite",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_help_lists_shared_candidate_options() -> None:
    runner = CliRunner()

    plan_help = runner.invoke(cli, ["plan", "--help"])
    assert plan_help.exit_code == 0
    assert "--retrieval-preset" in plan_help.output
    assert "--top-k-files" in plan_help.output
    assert "--candidate-ranker" in plan_help.output
    assert "--hybrid-re2-fusion-mode" in plan_help.output
    assert "--hybrid-re2-rrf-k" in plan_help.output
    assert "--embedding-enabled" in plan_help.output
    assert "--embedding-provider" in plan_help.output
    assert "--embedding-index-path" in plan_help.output
    assert "--chunk-top-k" in plan_help.output
    assert "--chunk-diversity-enabled" in plan_help.output
    assert "--cochange" in plan_help.output
    assert "--retrieval-policy" in plan_help.output
    assert "--junit-xml" in plan_help.output
    assert "--failed-test-report" in plan_help.output
    assert "--sbfl-metric" in plan_help.output
    assert "--scip" in plan_help.output
    assert "--scip-provider" in plan_help.output
    assert "--scip-generate-fallback" in plan_help.output
    assert "--languages" in plan_help.output
    assert "--memory-primary" in plan_help.output
    assert "--precomputed-skills-routing" in plan_help.output
    assert "--adaptive-router" in plan_help.output
    assert "--adaptive-router-mode" in plan_help.output
    assert "--adaptive-router-model-path" in plan_help.output
    assert "--adaptive-router-state-path" in plan_help.output
    assert "--adaptive-router-arm-set" in plan_help.output
    assert "--trace-export" in plan_help.output
    assert "--trace-export-path" in plan_help.output
    assert "--trace-otlp" in plan_help.output
    assert "--trace-otlp-endpoint" in plan_help.output

    benchmark_help = runner.invoke(cli, ["benchmark", "run", "--help"])
    assert benchmark_help.exit_code == 0
    assert "--retrieval-preset" in benchmark_help.output
    assert "--top-k-files" in benchmark_help.output
    assert "--candidate-ranker" in benchmark_help.output
    assert "--hybrid-re2-fusion-mode" in benchmark_help.output
    assert "--hybrid-re2-rrf-k" in benchmark_help.output
    assert "--embedding-enabled" in benchmark_help.output
    assert "--embedding-provider" in benchmark_help.output
    assert "--embedding-index-path" in benchmark_help.output
    assert "--chunk-top-k" in benchmark_help.output
    assert "--chunk-diversity-enabled" in benchmark_help.output
    assert "--cochange" in benchmark_help.output
    assert "--retrieval-policy" in benchmark_help.output
    assert "--junit-xml" in benchmark_help.output
    assert "--failed-test-report" in benchmark_help.output
    assert "--sbfl-metric" in benchmark_help.output
    assert "--scip" in benchmark_help.output
    assert "--scip-provider" in benchmark_help.output
    assert "--scip-generate-fallback" in benchmark_help.output
    assert "--languages" in benchmark_help.output
    assert "--memory-primary" in benchmark_help.output
    assert "--adaptive-router" in benchmark_help.output
    assert "--adaptive-router-mode" in benchmark_help.output
    assert "--adaptive-router-model-path" in benchmark_help.output
    assert "--adaptive-router-state-path" in benchmark_help.output
    assert "--adaptive-router-arm-set" in benchmark_help.output
    assert "--trace-export" in benchmark_help.output
    assert "--trace-export-path" in benchmark_help.output
    assert "--trace-otlp" in benchmark_help.output
    assert "--trace-otlp-endpoint" in benchmark_help.output
    assert "--warmup-runs" in benchmark_help.output
    assert "--include-plans" in benchmark_help.output
    assert "--include-case-details" in benchmark_help.output
    assert "--reward-log" in benchmark_help.output
    assert "--reward-log-path" in benchmark_help.output
    assert "--dependency-recall-floor" in benchmark_help.output
    assert "--chunk-hit-tolerance" in benchmark_help.output
    assert "--chunk-budget-growth-factor" in benchmark_help.output
    assert "--validation-test-growth-factor" in benchmark_help.output
    assert "--embedding-similarity-tolerance" in benchmark_help.output
    assert "--embedding-rerank-ratio-tolerance" in benchmark_help.output
    assert "--embedding-cache-hit-tolerance" in benchmark_help.output
    assert "--embedding-fallback-tolerance" in benchmark_help.output
    assert "--precomputed-skills-routing" in benchmark_help.output


def test_cli_plan_and_benchmark_share_core_option_defaults() -> None:
    plan_command = cli.commands["plan"]
    benchmark_run = cli.commands["benchmark"].commands["run"]

    plan_options = {
        option.name: option
        for option in plan_command.params
        if isinstance(option, click.Option)
    }
    benchmark_options = {
        option.name: option
        for option in benchmark_run.params
        if isinstance(option, click.Option)
    }

    shared_option_names = (
        "retrieval_preset",
        "top_k_files",
        "min_candidate_score",
        "deterministic_refine_enabled",
        "candidate_ranker",
        "hybrid_re2_fusion_mode",
        "hybrid_re2_rrf_k",
        "embedding_enabled",
        "embedding_provider",
        "embedding_model",
        "embedding_dimension",
        "embedding_rerank_pool",
        "embedding_lexical_weight",
        "embedding_semantic_weight",
        "embedding_min_similarity",
        "embedding_fail_open",
        "chunk_top_k",
        "chunk_per_file_limit",
        "chunk_disclosure",
        "chunk_signature",
        "chunk_token_budget",
        "memory_strategy",
        "memory_hybrid_limit",
        "memory_cache_enabled",
        "memory_cache_ttl_seconds",
        "memory_cache_max_entries",
        "memory_disclosure_mode",
        "memory_preview_max_chars",
        "precomputed_skills_routing_enabled",
        "adaptive_router_enabled",
        "adaptive_router_mode",
        "adaptive_router_model_path",
        "adaptive_router_state_path",
        "adaptive_router_arm_set",
        "cochange_enabled",
        "cochange_lookback_commits",
        "cochange_top_neighbors",
    )

    for option_name in shared_option_names:
        assert plan_options[option_name].default == benchmark_options[option_name].default
        assert tuple(plan_options[option_name].opts) == tuple(
            benchmark_options[option_name].opts
        )
    assert plan_options["retrieval_preset"].default == "none"
    assert plan_options["candidate_ranker"].default == "rrf_hybrid"
    assert plan_options["memory_disclosure_mode"].default == "compact"



def test_cli_plan_default_chunk_signature_disabled(tmp_path: Path) -> None:
    _seed_repo(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "validate token",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--no-cochange",
            "--no-repomap",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    chunks = payload["index"]["candidate_chunks"]
    assert chunks
    assert all(str(item.get("signature") or "") == "" for item in chunks)



def test_cli_benchmark_run_toggles_skills_precomputed_routing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    base_args = [
        "benchmark",
        "run",
        "--cases",
        str(tmp_path / "benchmark" / "cases" / "default.yaml"),
        "--repo",
        "demo",
        "--root",
        str(tmp_path),
        "--skills-dir",
        str(tmp_path / "skills"),
        "--languages",
        "python",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
    ]

    off_output_dir = tmp_path / "artifacts" / "benchmark" / "same-stage"
    off_result = runner.invoke(
        cli,
        [
            *base_args,
            "--no-precomputed-skills-routing",
            "--output",
            str(off_output_dir),
        ],
        env=_cli_env(tmp_path),
    )
    assert off_result.exit_code == 0
    off_payload = json.loads((off_output_dir / "results.json").read_text(encoding="utf-8"))
    assert off_payload["cases"][0]["plan"]["skills"]["routing_source"] == "same_stage"

    on_output_dir = tmp_path / "artifacts" / "benchmark" / "precomputed"
    on_result = runner.invoke(
        cli,
        [
            *base_args,
            "--precomputed-skills-routing",
            "--output",
            str(on_output_dir),
        ],
        env=_cli_env(tmp_path),
    )
    assert on_result.exit_code == 0
    on_payload = json.loads((on_output_dir / "results.json").read_text(encoding="utf-8"))
    assert on_payload["cases"][0]["plan"]["skills"]["routing_source"] == "precomputed"


def test_cli_benchmark_run_writes_trace_export_jsonl(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"
    trace_path = tmp_path / "context-map" / "traces" / "benchmark-trace.jsonl"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--trace-export",
            "--trace-export-path",
            str(trace_path),
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert trace_path.exists()
    lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    first = json.loads(lines[0])
    assert first["kind"] == "pipeline"



def test_cli_benchmark_run_reads_trace_export_from_config(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"
    trace_path = tmp_path / "context-map" / "traces" / "benchmark-config-trace.jsonl"

    (tmp_path / ".ace-lite.yml").write_text(
        f"""
benchmark:
  trace:
    export_enabled: true
    export_path: {trace_path.as_posix()}
""".lstrip(),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert trace_path.exists()


def test_cli_benchmark_run_reads_reward_log_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_repo(tmp_path)
    output_dir = tmp_path / "artifacts" / "benchmark" / "latest"
    reward_log_path = tmp_path / "context-map" / "router" / "benchmark-rewards.jsonl"

    (tmp_path / ".ace-lite.yml").write_text(
        f"""
benchmark:
  reward_log:
    enabled: true
    path: {reward_log_path.as_posix()}
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    class FakeRewardLogWriter:
        def __init__(self, *, path: str, max_workers: int = 1) -> None:
            captured["path"] = path
            captured["max_workers"] = max_workers

        def flush(self) -> dict[str, Any]:
            return {
                "path": captured["path"],
                "pending_count": 0,
                "written_count": 0,
                "error_count": 0,
                "last_error": "",
            }

        def close(self) -> dict[str, Any]:
            captured["closed"] = True
            return self.flush()

    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.AsyncRewardLogWriter",
        FakeRewardLogWriter,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(tmp_path / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert Path(captured["path"]) == reward_log_path
    assert captured["closed"] is True
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert payload["reward_log_summary"]["enabled"] is True
    assert payload["reward_log_summary"]["active"] is True
    assert payload["reward_log_summary"]["status"] == "enabled"
    assert Path(payload["reward_log_summary"]["path"]) == reward_log_path


def test_cli_benchmark_run_ignores_foreign_cwd_config_for_target_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target_root = tmp_path / "target"
    foreign_root = tmp_path / "foreign"
    foreign_cwd = foreign_root / "workspace"
    _seed_repo(target_root)
    foreign_cwd.mkdir(parents=True, exist_ok=True)
    (foreign_root / ".git").mkdir(parents=True, exist_ok=True)

    (target_root / ".ace-lite.yml").write_text(
        """
benchmark:
  adaptive_router:
    enabled: true
    mode: shadow
    arm_set: retrieval_policy_shadow
    online_bandit:
      enabled: true
      experiment_enabled: true
  reward_log:
    enabled: true
    path: context-map/router/target-benchmark-rewards.jsonl
""".lstrip(),
        encoding="utf-8",
    )
    (foreign_cwd / ".ace-lite.yml").write_text(
        """
benchmark:
  adaptive_router:
    enabled: false
  reward_log:
    enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(foreign_cwd)

    captured: dict[str, Any] = {}
    orchestrator_sentinel = object()

    class FakeBenchmarkRunner:
        def __init__(self, orchestrator: object, **kwargs: Any) -> None:
            captured["orchestrator"] = orchestrator
            captured["benchmark_runner_kwargs"] = kwargs

        def run(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "cases": [],
                "metrics": {},
                "regression": {},
                "reward_log_summary": {
                    "enabled": True,
                    "active": True,
                    "status": "enabled",
                    "path": captured["reward_log_path"],
                    "eligible_case_count": 0,
                    "submitted_count": 0,
                    "pending_count": 0,
                    "written_count": 0,
                    "error_count": 0,
                    "last_error": "",
                },
            }

    def fake_create_orchestrator(**kwargs: Any) -> object:
        captured["adaptive_router_config"] = kwargs["adaptive_router_config"]
        return orchestrator_sentinel

    def fake_write_results(results: dict[str, Any], output_dir: str) -> dict[str, str]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        results_path = output / "results.json"
        summary_path = output / "summary.json"
        report_path = output / "report.md"
        results_path.write_text(json.dumps(results), encoding="utf-8")
        summary_path.write_text(json.dumps({"reward_log_summary": results["reward_log_summary"]}), encoding="utf-8")
        report_path.write_text("# report\n", encoding="utf-8")
        return {
            "results_json": str(results_path),
            "report_md": str(report_path),
            "summary_json": str(summary_path),
        }

    class FakeRewardLogWriter:
        def __init__(self, *, path: str, max_workers: int = 1) -> None:
            captured["reward_log_path"] = path
            captured["reward_log_max_workers"] = max_workers

        def close(self) -> dict[str, Any]:
            return {
                "path": captured["reward_log_path"],
                "pending_count": 0,
                "written_count": 0,
                "error_count": 0,
                "last_error": "",
            }

    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.create_memory_provider",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.create_orchestrator",
        fake_create_orchestrator,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.BenchmarkRunner",
        FakeBenchmarkRunner,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.write_results",
        fake_write_results,
    )
    monkeypatch.setattr(
        "ace_lite.cli_app.commands.benchmark.AsyncRewardLogWriter",
        FakeRewardLogWriter,
    )

    runner = CliRunner()
    output_dir = target_root / "artifacts" / "benchmark" / "capture"
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(target_root / "benchmark" / "cases" / "default.yaml"),
            "--repo",
            "demo",
            "--root",
            str(target_root),
            "--skills-dir",
            str(target_root / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output",
            str(output_dir),
        ],
        env=_cli_env(target_root),
    )

    assert result.exit_code == 0
    assert captured["orchestrator"] is orchestrator_sentinel
    assert captured["adaptive_router_config"] == {
        "enabled": True,
        "mode": "shadow",
        "model_path": "context-map/router/model.json",
        "state_path": "context-map/router/state.json",
        "arm_set": "retrieval_policy_shadow",
        "online_bandit": {"enabled": True, "experiment_enabled": True},
    }
    assert captured["reward_log_path"] == "context-map/router/target-benchmark-rewards.jsonl"


def test_cli_benchmark_replay_rewards_writes_dataset_and_summary(tmp_path: Path) -> None:
    reward_log_path = tmp_path / "context-map" / "router" / "rewards.jsonl"
    output_dir = tmp_path / "artifacts" / "benchmark" / "reward-replay"

    append_reward_event(
        path=reward_log_path,
        event=make_reward_event(
            query_id="q1",
            chosen_arm_id="feature",
            reward_source="benchmark_task_success",
            reward_value=1.0,
            observed_at="2026-03-10T00:00:00+00:00",
            reward_observed_at="2026-03-10T00:00:05+00:00",
            context_features={"policy_profile": "feature"},
        ),
    )
    with reward_log_path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "schema_version": "0.9",
                    "query": "q2",
                    "arm_id": "general_hybrid",
                    "source": "ci_test_pass",
                    "reward": 0.5,
                    "logged_at": "2026-03-10T00:00:00+00:00",
                    "reward_ts": "2026-03-10T00:00:10+00:00",
                    "features": {"policy_profile": "general"},
                }
            )
            + "\n"
        )
        fh.write("{not-json}\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            "replay-rewards",
            "--input",
            str(reward_log_path),
            "--output",
            str(output_dir),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    dataset_path = Path(payload["dataset_jsonl"])
    summary_path = Path(payload["summary_json"])
    assert payload["event_count"] == 2
    assert payload["query_count"] == 2
    assert dataset_path.exists()
    assert summary_path.exists()
    dataset_rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(dataset_rows) == 2
    assert dataset_rows[1]["source_schema_version"] == "0.9"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["event_count"] == 2
    assert summary["total_row_count"] == 3
    assert summary["skipped_row_count"] == 1
    assert summary["query_count"] == 2
