from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from ace_lite.cli_app.config_resolve import _load_command_config, _resolve_shared_plan_config
from ace_lite.cli_app.config_resolve_defaults import (
    PLAN_MEMORY_CAPTURE_DEFAULTS,
    PLAN_MEMORY_FEEDBACK_DEFAULTS,
    PLAN_MEMORY_GATE_DEFAULTS,
    PLAN_MEMORY_NOTES_DEFAULTS,
    PLAN_MEMORY_POSTPROCESS_DEFAULTS,
    PLAN_MEMORY_PROFILE_DEFAULTS,
)
from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.params import (
    _to_candidate_ranker,
    _to_float_dict,
    _to_hybrid_fusion_mode,
    _to_retrieval_policy,
    _with_shared_plan_options,
)
from ace_lite.cli_app.progress import clear_progress, echo_done, echo_progress
from ace_lite.context_report import write_context_report_markdown
from ace_lite.entrypoint_runtime import (
    MemoryProviderKwargs,
    RunPlanRuntimeKwargs,
    build_memory_provider_kwargs_from_resolved,
    build_run_plan_kwargs_from_resolved,
)
from ace_lite.plan_application import (
    attach_plan_contract_summary,
    execute_timed_plan_with_fallback,
    resolve_plan_quick_fallback,
)
from ace_lite.plan_quick import build_plan_quick
from ace_lite.plan_timeout import (
    build_plan_timeout_fallback_payload,
    is_plan_timeout_debug_enabled,
    resolve_plan_timeout_seconds,
)
from ace_lite.scoring_config import (
    HYBRID_BM25_WEIGHT,
    HYBRID_COMBINED_SCALE,
    HYBRID_COVERAGE_WEIGHT,
    HYBRID_HEURISTIC_WEIGHT,
)


def _cli_module():
    import ace_lite.cli as cli_module

    return cli_module


@click.command(
    "plan",
    help="Build a source plan from memory->index->repomap->augment->skills->source_plan.",
    epilog=get_help_template("plan"),
)
@click.option("--query", required=True, help="User query for planning.")
@click.option(
    "--progress/--no-progress",
    default=True,
    show_default=True,
    help="Show progress indicators during execution.",
)
@click.option(
    "--quick/--no-quick",
    default=False,
    show_default=True,
    help="Use quick mode: skip memory/skill stages, use index-only retrieval.",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    show_default=True,
    help="Validate parameters and show effective config without executing.",
)
@click.option(
    "--timeout-seconds",
    default=None,
    type=float,
    show_default="env ACE_LITE_PLAN_TIMEOUT_SECONDS or 25",
    help="Overall timeout for full plan execution. On timeout, falls back to plan_quick suggestions.",
)
@click.option(
    "--output-json",
    default=None,
    type=str,
    help="Optional path to write the plan payload JSON (UTF-8). Relative paths are resolved under --root.",
)
@click.option(
    "--context-report-path",
    default=None,
    type=str,
    help=(
        "Optional path to write a ContextReport Markdown file (UTF-8). "
        "Relative paths are resolved under --root. "
        "Default: do not write a report."
    ),
)
@_with_shared_plan_options
@click.pass_context
def plan_command(
    ctx: click.Context,
    query: str,
    progress: bool,
    quick: bool,
    dry_run: bool,
    timeout_seconds: float | None,
    output_json: str | None,
    context_report_path: str | None,
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
) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    progress = bool(progress and sys.stderr.isatty())

    # Handle --quick mode
    if quick:
        from ace_lite.cli_app.commands.plan_quick import run_plan_quick

        if progress:
            click.echo("Running in quick mode (skipping memory/skill stages)")
        echo_progress("Building quick plan...")
        payload = run_plan_quick(
            query=query,
            root=root,
            top_k=top_k_files,
            languages=languages,
            tokenizer_model=tokenizer_model,
        )
        if progress:
            clear_progress()
            echo_done("Quick plan built")
        payload["_quick_mode"] = True
        if output_json:
            target = Path(str(output_json)).expanduser()
            if not target.is_absolute():
                target = Path(root) / target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        echo_json(payload)
        return

    # Handle --dry-run mode
    if dry_run:
        if progress:
            click.echo("Running in dry-run mode (validating parameters only)")
        # Validate config loading
        config = _load_command_config(root)
        # Show effective configuration
        dry_run_info = {
            "ok": True,
            "event": "plan_dry_run",
            "query": query,
            "repo": repo,
            "root": str(Path(root).resolve()),
            "effective_config": {
                "top_k_files": top_k_files,
                "timeout_seconds": timeout_seconds,
                "retrieval_preset": retrieval_preset,
                "languages": languages,
                "lsp_enabled": lsp_enabled,
                "embedding_enabled": embedding_enabled,
                "repomap_enabled": repomap_enabled,
                "cochange_enabled": cochange_enabled,
            },
            "message": "Dry run successful. Configuration is valid.",
        }
        if progress:
            echo_done("Dry run completed")
        if verbose:
            click.echo(json.dumps(dry_run_info, ensure_ascii=False, indent=2), err=True)
        echo_json(dry_run_info)
        return

    config = _load_command_config(root)
    repomap_signal_weights_payload: dict[str, float] | None = None
    if repomap_signal_weights:
        parsed = json.loads(repomap_signal_weights)
        repomap_signal_weights_payload = _to_float_dict(parsed)

    resolved = _resolve_shared_plan_config(
        ctx=ctx,
        config=config,
        namespace="plan",
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
        memory_profile_enabled=bool(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_enabled"]),
        memory_profile_path=str(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_path"]),
        memory_profile_top_n=int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_top_n"]),
        memory_profile_token_budget=int(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_token_budget"]
        ),
        memory_profile_expiry_enabled=bool(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_expiry_enabled"]
        ),
        memory_profile_ttl_days=int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_ttl_days"]),
        memory_profile_max_age_days=int(
            PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_max_age_days"]
        ),
        memory_feedback_enabled=bool(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_enabled"]),
        memory_feedback_path=str(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_path"]),
        memory_feedback_max_entries=int(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_max_entries"]
        ),
        memory_feedback_boost_per_select=float(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_boost_per_select"]
        ),
        memory_feedback_max_boost=float(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_max_boost"]),
        memory_feedback_decay_days=float(
            PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_decay_days"]
        ),
        memory_capture_enabled=bool(PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_enabled"]),
        memory_capture_notes_path=str(PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_notes_path"]),
        memory_capture_min_query_length=int(
            PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_min_query_length"]
        ),
        memory_capture_keywords=PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_keywords"],
        memory_notes_enabled=bool(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_enabled"]),
        memory_notes_path=str(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_path"]),
        memory_notes_limit=int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_limit"]),
        memory_notes_mode=str(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_mode"]),
        memory_notes_expiry_enabled=bool(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_expiry_enabled"]),
        memory_notes_ttl_days=int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_ttl_days"]),
        memory_notes_max_age_days=int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_max_age_days"]),
        memory_postprocess_enabled=bool(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_enabled"]
        ),
        memory_postprocess_noise_filter_enabled=bool(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_noise_filter_enabled"]
        ),
        memory_postprocess_length_norm_anchor_chars=int(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_length_norm_anchor_chars"]
        ),
        memory_postprocess_time_decay_half_life_days=float(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_time_decay_half_life_days"]
        ),
        memory_postprocess_hard_min_score=float(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_hard_min_score"]
        ),
        memory_postprocess_diversity_enabled=bool(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_diversity_enabled"]
        ),
        memory_postprocess_diversity_similarity_threshold=float(
            PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_diversity_similarity_threshold"]
        ),
        precomputed_skills_routing_enabled=precomputed_skills_routing_enabled,
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

    cli_module = _cli_module()
    memory_provider_kwargs: MemoryProviderKwargs = build_memory_provider_kwargs_from_resolved(
        resolved=resolved,
        primary=memory_primary,
        secondary=memory_secondary,
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        timeout_seconds=memory_timeout,
        user_id=user_id,
        app=app,
        limit=memory_limit,
    )
    memory_provider = cli_module.create_memory_provider(**memory_provider_kwargs)

    timeout_resolution = resolve_plan_timeout_seconds(timeout_seconds=timeout_seconds)
    debug_dump_enabled = is_plan_timeout_debug_enabled()
    run_plan_kwargs: RunPlanRuntimeKwargs = build_run_plan_kwargs_from_resolved(
        resolved=resolved,
        skills_dir=skills_dir,
        retrieval_policy=_to_retrieval_policy(resolved["retrieval_policy"]),
    )

    if progress:
        click.echo("Building source plan...", err=True)
        echo_progress("Loading memory...")

    def _run_plan_payload():
        if progress:
            echo_progress("Building index candidates...")
        result = cli_module.run_plan(
            query=query,
            repo=repo,
            root=root,
            skills_dir=skills_dir,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            memory_provider=memory_provider,
            **run_plan_kwargs,
        )
        if progress:
            echo_progress("Generating source plan...")
        return result

    execution = execute_timed_plan_with_fallback(
        run_payload=_run_plan_payload,
        timeout_seconds=timeout_resolution.seconds,
        debug_root=root,
        debug_payload={
            "entrypoint": "cli",
            "query": str(query),
            "repo": str(repo),
            "root": str(root),
            "timeout_source": timeout_resolution.source,
            "timeout_raw": timeout_resolution.raw,
        },
        debug_enabled=debug_dump_enabled,
        fallback_resolver=lambda: resolve_plan_quick_fallback(
            plan_quick_fn=build_plan_quick,
            normalized_query=str(query),
            root_path=root,
            top_k_files=max(1, int(resolved["top_k_files"])),
            plan_quick_kwargs={
                "languages": str(resolved["languages"]),
                "tokenizer_model": str(resolved["tokenizer_model"]),
            },
        ),
    )

    if progress:
        if execution.timed_out:
            clear_progress()
            click.echo("Plan timed out, using fallback suggestions")
        else:
            clear_progress()
            echo_done("Plan built")

    if execution.timed_out:
        payload = build_plan_timeout_fallback_payload(
            query=str(query),
            repo=str(repo),
            root=str(root),
            candidate_file_paths=execution.fallback.candidate_file_paths,
            steps=execution.fallback.steps,
            timeout_seconds=timeout_resolution.seconds,
            elapsed_ms=float(execution.outcome.elapsed_ms),
            fallback_mode=execution.fallback.fallback_mode,
            debug_dump_path=execution.outcome.debug_dump_path,
            chunk_token_budget=max(64, int(resolved["chunk_token_budget"])),
            chunk_disclosure=str(resolved["chunk_disclosure"]).strip().lower(),
            policy_name=str(resolved["retrieval_policy"]),
            policy_version=str(resolved["policy_version"]),
        )
    else:
        payload = execution.payload or {}
    if execution.timed_out:
        payload["_plan_timeout_fallback"] = True
    payload = attach_plan_contract_summary(payload)
    if context_report_path:
        report_target = Path(str(context_report_path)).expanduser()
        if not report_target.is_absolute():
            report_target = Path(root) / report_target
        write_context_report_markdown(payload, report_target)
    if output_json:
        target = Path(str(output_json)).expanduser()
        if not target.is_absolute():
            target = Path(root) / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    echo_json(payload)


__all__ = ["plan_command"]
