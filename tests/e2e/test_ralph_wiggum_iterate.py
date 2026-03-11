from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "ralph_wiggum_iterate.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location("ralph_wiggum_iterate", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pick_next_params_baseline_uses_default_ranker_weights_and_policy() -> None:
    module = _load_script_module()
    mode, params = module._pick_next_params(
        iteration=1,
        rng=random.Random(7),
        best_params=module.IterationParams(
            top_k_files=8,
            min_candidate_score=2,
            candidate_relative_threshold=0.0,
            candidate_ranker="heuristic",
            hybrid_re2_fusion_mode="linear",
            hybrid_re2_rrf_k=60,
            repomap_signal_weights=None,
            retrieval_policy="auto",
        ),
        last_metrics=None,
        recall_floor=0.95,
        explore_rate=0.3,
        candidate_ranker_choices=["heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid"],
        repomap_signal_weight_choices=[None, {"base": 0.75, "graph": 0.2, "import_depth": 0.05}],
        retrieval_policy_choices=["auto", "bugfix_test", "feature", "refactor", "general"],
        hybrid_fusion_mode_choices=["linear", "rrf"],
        hybrid_rrf_k_choices=[45, 60, 75],
    )

    assert mode == "baseline"
    assert params.candidate_ranker == "heuristic"
    assert params.hybrid_re2_fusion_mode == "linear"
    assert params.hybrid_re2_rrf_k == 60
    assert params.repomap_signal_weights is None
    assert params.retrieval_policy == "auto"


def test_pick_next_params_restart_deterministic_with_seed() -> None:
    module = _load_script_module()
    best = module.IterationParams(
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        repomap_signal_weights=None,
        retrieval_policy="auto",
    )
    rankers = ["heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid"]
    weights = [None, {"base": 0.7, "graph": 0.25, "import_depth": 0.05}]
    policies = ["auto", "bugfix_test", "feature"]

    rng1 = random.Random(20260210)
    rng2 = random.Random(20260210)

    mode1, params1 = module._pick_next_params(
        iteration=10,
        rng=rng1,
        best_params=best,
        last_metrics={"recall_at_k": 1.0},
        recall_floor=0.95,
        explore_rate=0.0,
        candidate_ranker_choices=rankers,
        repomap_signal_weight_choices=weights,
        retrieval_policy_choices=policies,
        hybrid_fusion_mode_choices=["linear", "rrf"],
        hybrid_rrf_k_choices=[45, 60, 75],
    )
    mode2, params2 = module._pick_next_params(
        iteration=10,
        rng=rng2,
        best_params=best,
        last_metrics={"recall_at_k": 1.0},
        recall_floor=0.95,
        explore_rate=0.0,
        candidate_ranker_choices=rankers,
        repomap_signal_weight_choices=weights,
        retrieval_policy_choices=policies,
        hybrid_fusion_mode_choices=["linear", "rrf"],
        hybrid_rrf_k_choices=[45, 60, 75],
    )

    assert mode1 == "restart"
    assert mode1 == mode2
    assert params1 == params2
    assert params1.retrieval_policy in policies


def test_parse_candidate_rankers_includes_rrf_hybrid() -> None:
    module = _load_script_module()

    parsed = module._parse_candidate_rankers(
        "heuristic,rrf_hybrid,invalid,hybrid_re2,rrf_hybrid"
    )

    assert parsed == ["heuristic", "rrf_hybrid", "hybrid_re2"]


def test_parse_hybrid_fusion_modes_and_rrf_ks() -> None:
    module = _load_script_module()

    modes = module._parse_hybrid_fusion_modes("rrf,linear,invalid")
    rrf_ks = module._parse_hybrid_rrf_ks("75,abc,45,75")

    assert modes == ["rrf", "linear"]
    assert rrf_ks == [75, 45]


def test_parse_repomap_signal_weight_sets_supports_optional_sets() -> None:
    module = _load_script_module()

    parsed = module._parse_repomap_signal_weight_sets(
        '[null, {"base": 0.8, "graph": 0.15, "import_depth": 0.05}]'
    )

    assert parsed[0] is None
    assert parsed[1] == {"base": 0.8, "graph": 0.15, "import_depth": 0.05}


def test_parse_retrieval_policies_filters_and_deduplicates() -> None:
    module = _load_script_module()

    parsed = module._parse_retrieval_policies("bugfix_test,feature,invalid,bugfix_test,auto")

    assert parsed == ["bugfix_test", "feature", "auto"]


def test_build_policy_summary_aggregates_policy_metrics() -> None:
    module = _load_script_module()

    auto_params = module.IterationParams(
        top_k_files=6,
        min_candidate_score=2,
        candidate_relative_threshold=0.2,
        candidate_ranker="heuristic",
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        repomap_signal_weights=None,
        retrieval_policy="auto",
    )
    bugfix_params = module.IterationParams(
        top_k_files=4,
        min_candidate_score=1,
        candidate_relative_threshold=0.3,
        candidate_ranker="bm25_lite",
        hybrid_re2_fusion_mode="rrf",
        hybrid_re2_rrf_k=75,
        repomap_signal_weights={"base": 0.7, "graph": 0.25, "import_depth": 0.05},
        retrieval_policy="bugfix_test",
    )

    rows = module._build_policy_summary(
        [
            module.IterationResult(
                iteration=1,
                mode="baseline",
                params=auto_params,
                metrics={"recall_at_k": 1.0, "precision_at_k": 0.4, "noise_rate": 0.6},
                objective=0.4,
                candidate_count_mean=3.0,
                missed_cases=[],
            ),
            module.IterationResult(
                iteration=2,
                mode="explore",
                params=auto_params,
                metrics={"recall_at_k": 0.9, "precision_at_k": 0.6, "noise_rate": 0.4},
                objective=0.35,
                candidate_count_mean=3.0,
                missed_cases=[],
            ),
            module.IterationResult(
                iteration=3,
                mode="exploit",
                params=bugfix_params,
                metrics={"recall_at_k": 0.95, "precision_at_k": 0.7, "noise_rate": 0.3},
                objective=0.7,
                candidate_count_mean=2.0,
                missed_cases=[],
            ),
        ]
    )

    assert [item["retrieval_policy"] for item in rows] == ["auto", "bugfix_test"]
    assert rows[0]["runs"] == 2
    assert rows[0]["mean_precision_at_k"] == 0.5
    assert rows[0]["best_objective"] == 0.4
    assert rows[1]["runs"] == 1
    assert rows[1]["mean_recall_at_k"] == 0.95


def test_write_markdown_report_keeps_objective_reporting(tmp_path: Path) -> None:
    module = _load_script_module()
    output_path = tmp_path / "report.md"

    params = module.IterationParams(
        top_k_files=4,
        min_candidate_score=2,
        candidate_relative_threshold=0.3,
        candidate_ranker="bm25_lite",
        hybrid_re2_fusion_mode="rrf",
        hybrid_re2_rrf_k=75,
        repomap_signal_weights={"base": 0.75, "graph": 0.2, "import_depth": 0.05},
        retrieval_policy="feature",
    )
    result = module.IterationResult(
        iteration=1,
        mode="baseline",
        params=params,
        metrics={
            "recall_at_k": 0.95,
            "precision_at_k": 0.50,
            "noise_rate": 0.40,
            "dependency_recall": 0.80,
            "latency_p95_ms": 42.0,
        },
        objective=0.50,
        candidate_count_mean=3.0,
        missed_cases=[],
    )

    module._write_markdown_report(
        output_path=output_path,
        generated_at="2026-02-10T00:00:00+00:00",
        repo="ace-lite-engine",
        root="/tmp/repo",
        cases_path="benchmark/cases/default.yaml",
        recall_floor=0.95,
        iteration_results=[result],
        best_result=result,
    )

    report_text = output_path.read_text(encoding="utf-8")
    assert "Objective: precision_at_k - 5 * max(0, 0.95 - recall_at_k)" in report_text
    assert "candidate_ranker" in report_text
    assert "hybrid_re2_fusion_mode" in report_text
    assert "hybrid_re2_rrf_k" in report_text
    assert "repomap_signal_weights" in report_text
    assert "retrieval_policy" in report_text
    assert "| retrieval_policy | feature |" in report_text
    assert "## Policy Summary" in report_text
    assert "| feature | 1 | 0.5000 | 0.5000 | 0.9500 | 0.5000 | 0.4000 |" in report_text
