from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import click

from ace_lite.benchmark.diff import write_diff
from ace_lite.benchmark.report import write_report_from_json, write_results
from ace_lite.benchmark.reward_replay import write_reward_replay_artifacts
from ace_lite.benchmark.runner import BenchmarkRunner, load_baseline_metrics, load_cases
from ace_lite.benchmark.scoring import REGRESSION_THRESHOLD_PROFILES
from ace_lite.benchmark.tuning_report import write_tuning_report
from ace_lite.benchmark_application import create_benchmark_orchestrator_from_resolved
from ace_lite.cli_app.commands.benchmark_support import (
    attach_benchmark_runtime_stats_summary,
    build_benchmark_tuning_context_summary,
    build_threshold_overrides,
    resolve_benchmark_run_settings,
    resolve_benchmark_threshold_settings,
    run_benchmark_and_write_outputs,
)
from ace_lite.cli_app.config_resolve import (
    _load_command_config,
    _resolve_shared_plan_config,
)
from ace_lite.cli_app.config_resolve_defaults import (
    PLAN_MEMORY_CAPTURE_DEFAULTS,
    PLAN_MEMORY_FEEDBACK_DEFAULTS,
    PLAN_MEMORY_GATE_DEFAULTS,
    PLAN_MEMORY_NOTES_DEFAULTS,
    PLAN_MEMORY_POSTPROCESS_DEFAULTS,
    PLAN_MEMORY_PROFILE_DEFAULTS,
)
from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.cli_app.orchestrator_factory import create_memory_provider, create_orchestrator
from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.params import (
    _to_float_dict,
    _to_retrieval_policy,
    _with_shared_plan_options,
)
from ace_lite.cli_app.runtime_command_support import DEFAULT_RUNTIME_STATS_DB_PATH
from ace_lite.router_reward_store import DEFAULT_REWARD_LOG_PATH, AsyncRewardLogWriter
from ace_lite.scoring_config import (
    HYBRID_BM25_WEIGHT,
    HYBRID_COMBINED_SCALE,
    HYBRID_COVERAGE_WEIGHT,
    HYBRID_HEURISTIC_WEIGHT,
)


@click.group("benchmark", help="Benchmark retrieval and context quality.")
def benchmark_group() -> None:
    pass


def _merge_reward_log_summary(summary: dict[str, Any], stats: Any) -> None:
    if not isinstance(summary, dict) or not isinstance(stats, dict):
        return
    if "path" in stats:
        summary["path"] = stats["path"]
    if "pending_count" in stats:
        summary["pending_count"] = stats["pending_count"]
    if "written_count" in stats:
        summary["written_count"] = stats["written_count"]
    if "error_count" in stats:
        summary["error_count"] = (
            max(0, int(summary.get("error_count", 0) or 0))
            + max(0, int(stats.get("error_count", 0) or 0))
        )
    stats_last_error = " ".join(str(stats.get("last_error") or "").split())[:256]
    if stats_last_error:
        summary["last_error"] = stats_last_error
    enabled = bool(summary.get("enabled", False))
    active = bool(enabled and summary.get("active", False))
    error_count = max(0, int(summary.get("error_count", 0) or 0))
    last_error = str(summary.get("last_error") or "").strip()
    if not enabled:
        summary["status"] = "disabled"
    elif not active or error_count > 0 or last_error:
        summary["status"] = "degraded"
    else:
        summary["status"] = "enabled"


@benchmark_group.command("diff", help="Compare two benchmark result JSON files and write a delta report.")
@click.option(
    "--a",
    "a_path",
    required=True,
    type=click.Path(path_type=str),
    help="Path to benchmark results.json or summary.json for variant A.",
)
@click.option(
    "--b",
    "b_path",
    required=True,
    type=click.Path(path_type=str),
    help="Path to benchmark results.json or summary.json for variant B.",
)
@click.option(
    "--output",
    "output_dir",
    default="artifacts/benchmark/diff/latest",
    show_default=True,
    type=click.Path(path_type=str),
    help="Output directory for diff artifacts.",
)
def benchmark_diff_command(a_path: str, b_path: str, output_dir: str) -> None:
    outputs = write_diff(a_path=a_path, b_path=b_path, output_dir=output_dir)
    echo_json(outputs)


@benchmark_group.command(
    "replay-rewards",
    help="Replay router reward logs into offline-learning dataset artifacts.",
)
@click.option(
    "--input",
    "input_path",
    default=DEFAULT_REWARD_LOG_PATH,
    show_default=True,
    type=click.Path(path_type=str),
    help="Path to the router reward log JSONL input.",
)
@click.option(
    "--output",
    "output_dir",
    default="artifacts/benchmark/reward-replay/latest",
    show_default=True,
    type=click.Path(path_type=str),
    help="Output directory for replay dataset artifacts.",
)
def benchmark_replay_rewards_command(input_path: str, output_dir: str) -> None:
    source = Path(input_path)
    if not source.exists() or not source.is_file():
        raise click.ClickException(f"reward log not found: {source}")
    outputs = write_reward_replay_artifacts(
        input_path=input_path,
        output_dir=output_dir,
    )
    echo_json(outputs)


@benchmark_group.command(
    "tune-report",
    help="Generate report-only offline tuning recommendations from benchmark results or summary artifacts.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(path_type=str),
    help="Path to benchmark results.json or summary.json input.",
)
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    type=click.Path(path_type=str),
    help="Optional baseline benchmark results.json or summary.json input.",
)
@click.option(
    "--output",
    "output_dir",
    default="artifacts/benchmark/tune-report/latest",
    show_default=True,
    type=click.Path(path_type=str),
    help="Output directory for tune-report artifacts.",
)
def benchmark_tune_report_command(
    input_path: str,
    baseline_path: str | None,
    output_dir: str,
) -> None:
    outputs = write_tuning_report(
        input_path=input_path,
        baseline_path=baseline_path,
        output_dir=output_dir,
    )
    echo_json(outputs)


@benchmark_group.command(
    "run",
    help="Run benchmark cases and write JSON/Markdown reports.",
    epilog=get_help_template("benchmark"),
)
@click.option(
    "--cases",
    "cases_path",
    default="benchmark/cases/default.yaml",
    show_default=True,
    type=click.Path(path_type=str),
    help="Benchmark cases YAML/JSON path.",
)
@_with_shared_plan_options
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    type=click.Path(path_type=str),
    help="Optional baseline benchmark JSON path.",
)
@click.option(
    "--benchmark-threshold-profile",
    default="default",
    show_default=True,
    type=click.Choice(sorted(REGRESSION_THRESHOLD_PROFILES.keys()), case_sensitive=False),
    help="Regression threshold profile.",
)
@click.option(
    "--precision-tolerance",
    default=None,
    type=float,
    help="Optional override for precision tolerance.",
)
@click.option(
    "--noise-tolerance",
    default=None,
    type=float,
    help="Optional override for noise tolerance.",
)
@click.option(
    "--latency-growth-factor",
    default=None,
    type=float,
    help="Optional override for latency growth factor.",
)
@click.option(
    "--dependency-recall-floor",
    default=None,
    type=float,
    help="Optional override for dependency recall floor.",
)
@click.option(
    "--chunk-hit-tolerance",
    default=None,
    type=float,
    help="Optional override for chunk hit tolerance.",
)
@click.option(
    "--chunk-budget-growth-factor",
    default=None,
    type=float,
    help="Optional override for chunk budget growth factor.",
)
@click.option(
    "--validation-test-growth-factor",
    default=None,
    type=float,
    help="Optional override for validation test count growth factor.",
)
@click.option(
    "--notes-hit-tolerance",
    default=None,
    type=float,
    help="Optional override for notes hit ratio tolerance.",
)
@click.option(
    "--profile-selected-tolerance",
    default=None,
    type=float,
    help="Optional override for profile selected mean tolerance.",
)
@click.option(
    "--capture-trigger-tolerance",
    default=None,
    type=float,
    help="Optional override for capture trigger ratio tolerance.",
)
@click.option(
    "--embedding-similarity-tolerance",
    default=None,
    type=float,
    help="Optional override for embedding similarity mean tolerance.",
)
@click.option(
    "--embedding-rerank-ratio-tolerance",
    default=None,
    type=float,
    help="Optional override for embedding rerank ratio tolerance.",
)
@click.option(
    "--embedding-cache-hit-tolerance",
    default=None,
    type=float,
    help="Optional override for embedding cache-hit ratio tolerance.",
)
@click.option(
    "--embedding-fallback-tolerance",
    default=None,
    type=float,
    help="Optional override for embedding fallback ratio tolerance.",
)
@click.option(
    "--warmup-runs",
    default=0,
    show_default=True,
    type=int,
    help="Warmup passes executed before measured benchmark run.",
)
@click.option(
    "--include-plans/--no-include-plans",
    default=True,
    show_default=True,
    help="Include per-case full plan payload in benchmark results.",
)
@click.option(
    "--include-case-details/--no-include-case-details",
    default=True,
    show_default=True,
    help="Include per-case candidate detail fields in benchmark results.",
)
@click.option(
    "--reward-log/--no-reward-log",
    "reward_log_enabled",
    default=False,
    show_default=True,
    help="Opt in to append-only router reward logging for benchmark runs.",
)
@click.option(
    "--reward-log-path",
    default=DEFAULT_REWARD_LOG_PATH,
    show_default=True,
    type=click.Path(path_type=str),
    help="Append-only reward log JSONL path used when reward logging is enabled.",
)
@click.option(
    "--runtime-stats/--no-runtime-stats",
    "runtime_stats_enabled",
    default=False,
    show_default=True,
    help="Include durable runtime stats snapshot in benchmark artifacts.",
)
@click.option(
    "--runtime-stats-db-path",
    default=DEFAULT_RUNTIME_STATS_DB_PATH,
    show_default=True,
    type=click.Path(path_type=str),
    help="Durable runtime stats SQLite path used for benchmark export.",
)
@click.option(
    "--fail-on-regression/--no-fail-on-regression",
    default=False,
    show_default=True,
    help="Exit with non-zero code if regression is detected.",
)
@click.option(
    "--output",
    "output_dir",
    default="artifacts/benchmark/latest",
    show_default=True,
    type=click.Path(path_type=str),
    help="Output directory for benchmark artifacts.",
)
@click.pass_context
def benchmark_run_command(
    ctx: click.Context,
    cases_path: str,
    runtime_profile: str | None,
    repo: str,
    root: str,
    skills_dir: str,
    config_pack: str | None,
    time_range: str | None,
    start_date: str | None,
    end_date: str | None,
    precomputed_skills_routing_enabled: bool,
    adaptive_router_enabled: bool,
    adaptive_router_mode: str,
    adaptive_router_model_path: str,
    adaptive_router_state_path: str,
    adaptive_router_arm_set: str,
    plan_replay_cache_enabled: bool,
    plan_replay_cache_path: str,
    retrieval_preset: str,
    top_k_files: int,
    min_candidate_score: int,
    candidate_relative_threshold: float,
    candidate_ranker: str,
    exact_search: bool,
    deterministic_refine_enabled: bool,
    exact_search_time_budget_ms: int,
    exact_search_max_paths: int,
    hybrid_re2_fusion_mode: str,
    hybrid_re2_rrf_k: int,
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_index_path: str,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
    languages: str,
    index_cache_path: str,
    index_incremental: bool,
    conventions_files: tuple[str, ...],
    plugins_enabled: bool,
    remote_slot_policy_mode: str,
    remote_slot_allowlist: str,
    repomap_enabled: bool,
    repomap_top_k: int,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_ranking_profile: str,
    repomap_signal_weights: str | None,
    verbose: bool,
    lsp_enabled: bool,
    lsp_top_n: int,
    lsp_cmds: tuple[str, ...],
    lsp_xref_enabled: bool,
    lsp_xref_top_n: int,
    lsp_time_budget_ms: int,
    lsp_xref_cmds: tuple[str, ...],
    memory_primary: str,
    memory_secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    memory_timeout: float,
    user_id: str | None,
    app: str | None,
    memory_limit: int,
    memory_disclosure_mode: str,
    memory_preview_max_chars: int,
    memory_strategy: str,
    memory_cache_enabled: bool,
    memory_cache_path: str,
    memory_cache_ttl_seconds: int,
    memory_cache_max_entries: int,
    memory_timeline_enabled: bool,
    memory_container_tag: str | None,
    memory_auto_tag_mode: str | None,
    memory_hybrid_limit: int,
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_disclosure: str,
    chunk_signature: bool,
    chunk_snippet_max_lines: int,
    chunk_snippet_max_chars: int,
    chunk_token_budget: int,
    chunk_guard_enabled: bool,
    chunk_guard_mode: str,
    chunk_guard_lambda_penalty: float,
    chunk_guard_min_pool: int,
    chunk_guard_max_pool: int,
    chunk_guard_min_marginal_utility: float,
    chunk_guard_compatibility_min_overlap: float,
    chunk_diversity_enabled: bool,
    chunk_diversity_path_penalty: float,
    chunk_diversity_symbol_family_penalty: float,
    chunk_diversity_kind_penalty: float,
    chunk_diversity_locality_penalty: float,
    chunk_diversity_locality_window: int,
    tokenizer_model: str,
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    retrieval_policy: str,
    policy_version: str,
    junit_xml: str | None,
    coverage_json: str | None,
    sbfl_json: str | None,
    sbfl_metric: str,
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
    trace_export_enabled: bool,
    trace_export_path: str,
    trace_otlp_enabled: bool,
    trace_otlp_endpoint: str,
    trace_otlp_timeout_seconds: float,
    baseline_path: str | None,
    benchmark_threshold_profile: str,
    precision_tolerance: float | None,
    noise_tolerance: float | None,
    latency_growth_factor: float | None,
    dependency_recall_floor: float | None,
    chunk_hit_tolerance: float | None,
    chunk_budget_growth_factor: float | None,
    validation_test_growth_factor: float | None,
    notes_hit_tolerance: float | None,
    profile_selected_tolerance: float | None,
    capture_trigger_tolerance: float | None,
    embedding_similarity_tolerance: float | None,
    embedding_rerank_ratio_tolerance: float | None,
    embedding_cache_hit_tolerance: float | None,
    embedding_fallback_tolerance: float | None,
    warmup_runs: int,
    include_plans: bool,
    include_case_details: bool,
    reward_log_enabled: bool,
    reward_log_path: str,
    runtime_stats_enabled: bool,
    runtime_stats_db_path: str,
    fail_on_regression: bool,
    output_dir: str,
) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = _load_command_config(root)
    repomap_signal_weights_payload: dict[str, float] | None = None
    if repomap_signal_weights:
        parsed = json.loads(repomap_signal_weights)
        repomap_signal_weights_payload = _to_float_dict(parsed)
    run_settings = resolve_benchmark_run_settings(
        ctx=ctx,
        config=config,
        warmup_runs=warmup_runs,
        include_plans=include_plans,
        include_case_details=include_case_details,
        reward_log_enabled=reward_log_enabled,
        reward_log_path=reward_log_path,
        precomputed_skills_routing_enabled=precomputed_skills_routing_enabled,
        runtime_stats_enabled=runtime_stats_enabled,
        runtime_stats_db_path=runtime_stats_db_path,
    )

    resolved = _resolve_shared_plan_config(
        ctx=ctx,
        config=config,
        namespace="benchmark",
        config_pack=config_pack,
        runtime_profile=runtime_profile,
        retrieval_preset=retrieval_preset,
        adaptive_router_enabled=adaptive_router_enabled,
        adaptive_router_mode=adaptive_router_mode,
        adaptive_router_model_path=adaptive_router_model_path,
        adaptive_router_state_path=adaptive_router_state_path,
        adaptive_router_arm_set=adaptive_router_arm_set,
        top_k_files=top_k_files,
        min_candidate_score=min_candidate_score,
        candidate_relative_threshold=candidate_relative_threshold,
        candidate_ranker=candidate_ranker,
        exact_search_enabled=exact_search,
        deterministic_refine_enabled=deterministic_refine_enabled,
        exact_search_time_budget_ms=exact_search_time_budget_ms,
        exact_search_max_paths=exact_search_max_paths,
        hybrid_re2_fusion_mode=hybrid_re2_fusion_mode,
        hybrid_re2_rrf_k=hybrid_re2_rrf_k,
        hybrid_re2_bm25_weight=float(HYBRID_BM25_WEIGHT),
        hybrid_re2_heuristic_weight=float(HYBRID_HEURISTIC_WEIGHT),
        hybrid_re2_coverage_weight=float(HYBRID_COVERAGE_WEIGHT),
        hybrid_re2_combined_scale=float(HYBRID_COMBINED_SCALE),
        embedding_enabled=embedding_enabled,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_index_path=embedding_index_path,
        embedding_rerank_pool=embedding_rerank_pool,
        embedding_lexical_weight=embedding_lexical_weight,
        embedding_semantic_weight=embedding_semantic_weight,
        embedding_min_similarity=embedding_min_similarity,
        embedding_fail_open=embedding_fail_open,
        languages=languages,
        index_cache_path=index_cache_path,
        index_incremental=index_incremental,
        conventions_files=conventions_files,
        plugins_enabled=plugins_enabled,
        remote_slot_policy_mode=remote_slot_policy_mode,
        remote_slot_allowlist=remote_slot_allowlist,
        repomap_enabled=repomap_enabled,
        repomap_top_k=repomap_top_k,
        repomap_neighbor_limit=repomap_neighbor_limit,
        repomap_budget_tokens=repomap_budget_tokens,
        repomap_ranking_profile=repomap_ranking_profile,
        repomap_signal_weights=repomap_signal_weights_payload,
        lsp_enabled=lsp_enabled,
        lsp_top_n=lsp_top_n,
        lsp_cmds=lsp_cmds,
        lsp_xref_enabled=lsp_xref_enabled,
        lsp_xref_top_n=lsp_xref_top_n,
        lsp_time_budget_ms=lsp_time_budget_ms,
        lsp_xref_cmds=lsp_xref_cmds,
        memory_disclosure_mode=memory_disclosure_mode,
        memory_preview_max_chars=memory_preview_max_chars,
        memory_strategy=memory_strategy,
        memory_gate_enabled=bool(PLAN_MEMORY_GATE_DEFAULTS["memory_gate_enabled"]),
        memory_gate_mode=str(PLAN_MEMORY_GATE_DEFAULTS["memory_gate_mode"]),
        memory_cache_enabled=memory_cache_enabled,
        memory_cache_path=memory_cache_path,
        memory_cache_ttl_seconds=memory_cache_ttl_seconds,
        memory_cache_max_entries=memory_cache_max_entries,
        memory_timeline_enabled=memory_timeline_enabled,
        memory_container_tag=memory_container_tag,
        memory_auto_tag_mode=memory_auto_tag_mode,
        memory_profile_enabled=bool(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_enabled"]
        ),
        memory_profile_path=str(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_path"]),
        memory_profile_top_n=int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_top_n"]),
        memory_profile_token_budget=int(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_token_budget"]
        ),
        memory_profile_expiry_enabled=bool(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_expiry_enabled"]
        ),
        memory_profile_ttl_days=int(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_ttl_days"]
        ),
        memory_profile_max_age_days=int(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_max_age_days"]
        ),
        memory_feedback_enabled=bool(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_enabled"]
        ),
        memory_feedback_path=str(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_path"]),
        memory_feedback_max_entries=int(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_max_entries"]
        ),
        memory_feedback_boost_per_select=float(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_boost_per_select"]
        ),
        memory_feedback_max_boost=float(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_max_boost"]
        ),
        memory_feedback_decay_days=float(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_decay_days"]
        ),
        memory_capture_enabled=bool(
            PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_enabled"]
        ),
        memory_capture_notes_path=str(
            PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_notes_path"]
        ),
        memory_capture_min_query_length=int(
            PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_min_query_length"]
        ),
        memory_capture_keywords=PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_keywords"],
        memory_notes_enabled=bool(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_enabled"]),
        memory_notes_path=str(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_path"]),
        memory_notes_limit=int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_limit"]),
        memory_notes_mode=str(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_mode"]),
        memory_notes_expiry_enabled=bool(
            PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_expiry_enabled"]
        ),
        memory_notes_ttl_days=int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_ttl_days"]),
        memory_notes_max_age_days=int(
            PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_max_age_days"]
        ),
        memory_postprocess_enabled=bool(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_enabled"]
        ),
        memory_postprocess_noise_filter_enabled=bool(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_noise_filter_enabled"]
        ),
        memory_postprocess_length_norm_anchor_chars=int(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS[
                "memory_postprocess_length_norm_anchor_chars"
            ]
        ),
        memory_postprocess_time_decay_half_life_days=float(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS[
                "memory_postprocess_time_decay_half_life_days"
            ]
        ),
        memory_postprocess_hard_min_score=float(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_hard_min_score"]
        ),
        memory_postprocess_diversity_enabled=bool(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_diversity_enabled"]
        ),
        memory_postprocess_diversity_similarity_threshold=float(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS[
                "memory_postprocess_diversity_similarity_threshold"
            ]
        ),
        precomputed_skills_routing_enabled=bool(
            run_settings["precomputed_skills_routing_enabled"]
        ),
        plan_replay_cache_enabled=plan_replay_cache_enabled,
        plan_replay_cache_path=plan_replay_cache_path,
        memory_hybrid_limit=memory_hybrid_limit,
        chunk_top_k=chunk_top_k,
        chunk_per_file_limit=chunk_per_file_limit,
        chunk_disclosure=chunk_disclosure,
        chunk_signature=chunk_signature,
        chunk_snippet_max_lines=chunk_snippet_max_lines,
        chunk_snippet_max_chars=chunk_snippet_max_chars,
        chunk_token_budget=chunk_token_budget,
        chunk_guard_enabled=chunk_guard_enabled,
        chunk_guard_mode=chunk_guard_mode,
        chunk_guard_lambda_penalty=chunk_guard_lambda_penalty,
        chunk_guard_min_pool=chunk_guard_min_pool,
        chunk_guard_max_pool=chunk_guard_max_pool,
        chunk_guard_min_marginal_utility=chunk_guard_min_marginal_utility,
        chunk_guard_compatibility_min_overlap=chunk_guard_compatibility_min_overlap,
        chunk_diversity_enabled=chunk_diversity_enabled,
        chunk_diversity_path_penalty=chunk_diversity_path_penalty,
        chunk_diversity_symbol_family_penalty=chunk_diversity_symbol_family_penalty,
        chunk_diversity_kind_penalty=chunk_diversity_kind_penalty,
        chunk_diversity_locality_penalty=chunk_diversity_locality_penalty,
        chunk_diversity_locality_window=chunk_diversity_locality_window,
        tokenizer_model=tokenizer_model,
        cochange_enabled=cochange_enabled,
        cochange_cache_path=cochange_cache_path,
        cochange_lookback_commits=cochange_lookback_commits,
        cochange_half_life_days=cochange_half_life_days,
        cochange_top_neighbors=cochange_top_neighbors,
        cochange_boost_weight=cochange_boost_weight,
        retrieval_policy=retrieval_policy,
        policy_version=policy_version,
        junit_xml=junit_xml,
        coverage_json=coverage_json,
        sbfl_json=sbfl_json,
        sbfl_metric=sbfl_metric,
        scip_enabled=scip_enabled,
        scip_index_path=scip_index_path,
        scip_provider=scip_provider,
        scip_generate_fallback=scip_generate_fallback,
        trace_export_enabled=trace_export_enabled,
        trace_export_path=trace_export_path,
        trace_otlp_enabled=trace_otlp_enabled,
        trace_otlp_endpoint=trace_otlp_endpoint,
        trace_otlp_timeout_seconds=trace_otlp_timeout_seconds,
    )
    threshold_settings = resolve_benchmark_threshold_settings(
        ctx=ctx,
        config=config,
        benchmark_threshold_profile=benchmark_threshold_profile,
        precision_tolerance=precision_tolerance,
        noise_tolerance=noise_tolerance,
        latency_growth_factor=latency_growth_factor,
        dependency_recall_floor=dependency_recall_floor,
        chunk_hit_tolerance=chunk_hit_tolerance,
        chunk_budget_growth_factor=chunk_budget_growth_factor,
        validation_test_growth_factor=validation_test_growth_factor,
        notes_hit_tolerance=notes_hit_tolerance,
        profile_selected_tolerance=profile_selected_tolerance,
        capture_trigger_tolerance=capture_trigger_tolerance,
        embedding_similarity_tolerance=embedding_similarity_tolerance,
        embedding_rerank_ratio_tolerance=embedding_rerank_ratio_tolerance,
        embedding_cache_hit_tolerance=embedding_cache_hit_tolerance,
        embedding_fallback_tolerance=embedding_fallback_tolerance,
    )
    cases = load_cases(cases_path)

    orchestrator = create_benchmark_orchestrator_from_resolved(
        create_memory_provider_fn=create_memory_provider,
        create_orchestrator_fn=create_orchestrator,
        resolved=resolved,
        skills_dir=skills_dir,
        retrieval_policy=_to_retrieval_policy(resolved["retrieval_policy"]),
        memory_primary=memory_primary,
        memory_secondary=memory_secondary,
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        memory_timeout=memory_timeout,
        user_id=user_id,
        app=app,
        memory_limit=memory_limit,
    )

    threshold_overrides = build_threshold_overrides(threshold_settings)
    tuning_context_summary = build_benchmark_tuning_context_summary(
        resolved=resolved,
        threshold_profile=str(threshold_settings["benchmark_threshold_profile"]),
        threshold_overrides=threshold_overrides,
        warmup_runs=int(run_settings["warmup_runs"]),
        include_plan_payload=bool(run_settings["include_plans"]),
        include_case_details=bool(run_settings["include_case_details"]),
    )

    baseline_metrics = load_baseline_metrics(baseline_path) if baseline_path else None
    results = run_benchmark_and_write_outputs(
        orchestrator=orchestrator,
        cases=cases,
        repo=repo,
        root=root,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        baseline_metrics=baseline_metrics,
        threshold_profile=str(threshold_settings["benchmark_threshold_profile"]),
        threshold_overrides=threshold_overrides,
        warmup_runs=int(run_settings["warmup_runs"]),
        include_plan_payload=bool(run_settings["include_plans"]),
        include_case_details=bool(run_settings["include_case_details"]),
        tuning_context_summary=tuning_context_summary,
        reward_log_enabled=bool(run_settings["reward_log_enabled"]),
        reward_log_path=str(run_settings["reward_log_path"]),
        runtime_stats_enabled=bool(run_settings["runtime_stats_enabled"]),
        runtime_stats_db_path=str(run_settings["runtime_stats_db_path"]),
        home_path=os.environ.get("HOME") or os.environ.get("USERPROFILE"),
        user_id=user_id,
        profile_key=str(resolved.get("runtime_profile") or "").strip() or None,
        output_dir=output_dir,
        runner_cls=BenchmarkRunner,
        reward_log_writer_cls=AsyncRewardLogWriter,
        write_results_fn=write_results,
        echo_json_fn=echo_json,
        merge_reward_log_summary_fn=_merge_reward_log_summary,
        attach_runtime_stats_summary_fn=attach_benchmark_runtime_stats_summary,
    )

    regression = results.get("regression", {})
    if (
        fail_on_regression
        and isinstance(regression, dict)
        and bool(regression.get("regressed"))
    ):
        raise click.ClickException("benchmark regression detected")


@benchmark_group.command("report", help="Generate Markdown report from benchmark JSON results.")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(path_type=str),
    help="Path to benchmark results JSON.",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(path_type=str),
    help="Optional output Markdown path.",
)
def benchmark_report_command(input_path: str, output_path: str | None) -> None:
    path = write_report_from_json(input_path=input_path, output_path=output_path)
    click.echo(path)


__all__ = ["benchmark_group"]
