from __future__ import annotations

import json
import logging
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
from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.params import (
    _to_candidate_ranker,
    _to_float_dict,
    _to_hybrid_fusion_mode,
    _to_retrieval_policy,
    _with_shared_plan_options,
)
from ace_lite.plan_quick import build_plan_quick
from ace_lite.plan_timeout import (
    build_plan_timeout_fallback_payload,
    execute_with_timeout,
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
)
@click.option("--query", required=True, help="User query for planning.")
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
@_with_shared_plan_options
@click.pass_context
def plan_command(
    ctx: click.Context,
    query: str,
    timeout_seconds: float | None,
    output_json: str | None,
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
    memory_provider = cli_module.create_memory_provider(
        primary=memory_primary,
        secondary=memory_secondary,
        memory_strategy=str(resolved["memory_strategy"]).strip().lower(),
        memory_hybrid_limit=max(1, int(resolved["memory_hybrid_limit"])),
        memory_cache_enabled=bool(resolved["memory_cache_enabled"]),
        memory_cache_path=str(resolved["memory_cache_path"]),
        memory_cache_ttl_seconds=max(1, int(resolved["memory_cache_ttl_seconds"])),
        memory_cache_max_entries=max(16, int(resolved["memory_cache_max_entries"])),
        memory_notes_enabled=bool(resolved["memory_notes_enabled"]),
        memory_notes_path=str(resolved["memory_notes_path"]).strip()
        or "context-map/memory_notes.jsonl",
        memory_notes_limit=max(1, int(resolved["memory_notes_limit"])),
        memory_notes_mode=str(resolved["memory_notes_mode"]).strip().lower()
        or "supplement",
        memory_notes_expiry_enabled=bool(resolved["memory_notes_expiry_enabled"]),
        memory_notes_ttl_days=max(1, int(resolved["memory_notes_ttl_days"])),
        memory_notes_max_age_days=max(1, int(resolved["memory_notes_max_age_days"])),
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        timeout_seconds=memory_timeout,
        user_id=user_id,
        app=app,
        limit=memory_limit,
    )

    timeout_resolution = resolve_plan_timeout_seconds(timeout_seconds=timeout_seconds)
    debug_dump_enabled = is_plan_timeout_debug_enabled()

    def _run_plan_payload():
        return cli_module.run_plan(
            query=query,
            repo=repo,
            root=root,
            skills_dir=skills_dir,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            memory_provider=memory_provider,
            memory_config=dict(resolved["memory"]),
            memory_disclosure_mode=str(resolved["memory_disclosure_mode"])
            .strip()
            .lower(),
            memory_preview_max_chars=max(32, int(resolved["memory_preview_max_chars"])),
            memory_strategy=str(resolved["memory_strategy"]).strip().lower(),
            memory_gate_enabled=bool(resolved["memory_gate_enabled"]),
            memory_gate_mode=str(resolved["memory_gate_mode"]).strip().lower() or "auto",
            memory_timeline_enabled=bool(resolved["memory_timeline_enabled"]),
            memory_container_tag=resolved["memory_container_tag"],
            memory_auto_tag_mode=resolved["memory_auto_tag_mode"],
            memory_profile_enabled=bool(resolved["memory_profile_enabled"]),
            memory_profile_path=str(resolved["memory_profile_path"]).strip()
            or "~/.ace-lite/profile.json",
            memory_profile_top_n=max(1, int(resolved["memory_profile_top_n"])),
            memory_profile_token_budget=max(
                1,
                int(resolved["memory_profile_token_budget"]),
            ),
            memory_profile_expiry_enabled=bool(resolved["memory_profile_expiry_enabled"]),
            memory_profile_ttl_days=max(1, int(resolved["memory_profile_ttl_days"])),
            memory_profile_max_age_days=max(
                1,
                int(resolved["memory_profile_max_age_days"]),
            ),
            memory_feedback_enabled=bool(resolved["memory_feedback_enabled"]),
            memory_feedback_path=str(resolved["memory_feedback_path"]).strip()
            or "~/.ace-lite/profile.json",
            memory_feedback_max_entries=max(
                0, int(resolved["memory_feedback_max_entries"])
            ),
            memory_feedback_boost_per_select=max(
                0.0, float(resolved["memory_feedback_boost_per_select"])
            ),
            memory_feedback_max_boost=max(
                0.0, float(resolved["memory_feedback_max_boost"])
            ),
            memory_feedback_decay_days=max(
                0.0, float(resolved["memory_feedback_decay_days"])
            ),
            memory_capture_enabled=bool(resolved["memory_capture_enabled"]),
            memory_capture_notes_path=str(resolved["memory_capture_notes_path"])
            .strip()
            or "context-map/memory_notes.jsonl",
            memory_capture_min_query_length=max(
                1,
                int(resolved["memory_capture_min_query_length"]),
            ),
            memory_capture_keywords=list(resolved["memory_capture_keywords"]),
            memory_notes_enabled=bool(resolved["memory_notes_enabled"]),
            memory_notes_path=str(resolved["memory_notes_path"]).strip()
            or "context-map/memory_notes.jsonl",
            memory_notes_limit=max(1, int(resolved["memory_notes_limit"])),
            memory_notes_mode=str(resolved["memory_notes_mode"]).strip().lower()
            or "supplement",
            memory_notes_expiry_enabled=bool(resolved["memory_notes_expiry_enabled"]),
            memory_notes_ttl_days=max(1, int(resolved["memory_notes_ttl_days"])),
            memory_notes_max_age_days=max(
                1, int(resolved["memory_notes_max_age_days"])
            ),
            memory_postprocess_enabled=bool(resolved["memory_postprocess_enabled"]),
            memory_postprocess_noise_filter_enabled=bool(
                resolved["memory_postprocess_noise_filter_enabled"]
            ),
            memory_postprocess_length_norm_anchor_chars=max(
                1, int(resolved["memory_postprocess_length_norm_anchor_chars"])
            ),
            memory_postprocess_time_decay_half_life_days=max(
                0.0, float(resolved["memory_postprocess_time_decay_half_life_days"])
            ),
            memory_postprocess_hard_min_score=max(
                0.0, float(resolved["memory_postprocess_hard_min_score"])
            ),
            memory_postprocess_diversity_enabled=bool(
                resolved["memory_postprocess_diversity_enabled"]
            ),
            memory_postprocess_diversity_similarity_threshold=max(
                0.0,
                min(
                    1.0,
                    float(resolved["memory_postprocess_diversity_similarity_threshold"]),
                ),
            ),
            skills_config={
                "dir": skills_dir,
                **dict(resolved["skills"]),
            },
            index_config=dict(resolved["index"]),
            embedding_enabled=bool(resolved["embedding_enabled"]),
            embedding_provider=str(resolved["embedding_provider"]),
            embedding_model=str(resolved["embedding_model"]),
            embedding_dimension=max(1, int(resolved["embedding_dimension"])),
            embedding_index_path=str(resolved["embedding_index_path"]),
            embedding_rerank_pool=max(1, int(resolved["embedding_rerank_pool"])),
            embedding_lexical_weight=float(resolved["embedding_lexical_weight"]),
            embedding_semantic_weight=float(resolved["embedding_semantic_weight"]),
            embedding_min_similarity=float(resolved["embedding_min_similarity"]),
            embedding_fail_open=bool(resolved["embedding_fail_open"]),
            embeddings_config=dict(resolved["embeddings"]),
            adaptive_router_config=dict(resolved["adaptive_router"]),
            plan_replay_cache_config=dict(resolved["plan_replay_cache"]),
            retrieval_config=dict(resolved["retrieval"]),
            repomap_config=dict(resolved["repomap"]),
            lsp_config=dict(resolved["lsp"]),
            plugins_config=dict(resolved["plugins"]),
            chunking_config=dict(resolved["chunk"]),
            tokenizer_config=dict(resolved["tokenizer"]),
            cochange_config=dict(resolved["cochange"]),
            retrieval_policy=_to_retrieval_policy(resolved["retrieval_policy"]),
            policy_version=str(resolved["policy_version"]),
            junit_xml=resolved["junit_xml"],
            coverage_json=resolved["coverage_json"],
            sbfl_json=resolved["sbfl_json"],
            sbfl_metric=str(resolved["sbfl_metric"]),
            tests_config=dict(resolved["tests"]),
            scip_enabled=bool(resolved["scip_enabled"]),
            scip_index_path=str(resolved["scip_index_path"]),
            scip_provider=str(resolved["scip_provider"]),
            scip_generate_fallback=bool(resolved["scip_generate_fallback"]),
            scip_config=dict(resolved["scip"]),
            trace_export_enabled=bool(resolved["trace_export_enabled"]),
            trace_export_path=str(resolved["trace_export_path"]),
            trace_otlp_enabled=bool(resolved["trace_otlp_enabled"]),
            trace_otlp_endpoint=str(resolved["trace_otlp_endpoint"]),
            trace_otlp_timeout_seconds=float(resolved["trace_otlp_timeout_seconds"]),
            trace_config=dict(resolved["trace"]),
        )

    outcome = execute_with_timeout(
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
    )

    if outcome.timed_out:
        candidate_file_paths: list[str] = []
        plan_steps: list[str] = []
        try:
            quick = build_plan_quick(
                query=str(query),
                root=root,
                languages=str(resolved["languages"]),
                top_k_files=max(1, int(resolved["top_k_files"])),
                repomap_top_k=max(8, int(resolved["top_k_files"]) * 4),
                budget_tokens=800,
                ranking_profile="graph",
                include_rows=False,
                tokenizer_model=str(resolved["tokenizer_model"]),
            )
            quick_paths = quick.get("candidate_files", [])
            if isinstance(quick_paths, list):
                candidate_file_paths = [
                    str(item).strip() for item in quick_paths if str(item).strip()
                ]
            quick_steps = quick.get("steps", [])
            if isinstance(quick_steps, list):
                plan_steps = [
                    str(item).strip() for item in quick_steps if str(item).strip()
                ]
        except Exception:
            candidate_file_paths = []
            plan_steps = []

        fallback_mode = "plan_quick" if candidate_file_paths else "none"
        payload = build_plan_timeout_fallback_payload(
            query=str(query),
            repo=str(repo),
            root=str(root),
            candidate_file_paths=candidate_file_paths,
            steps=plan_steps,
            timeout_seconds=timeout_resolution.seconds,
            elapsed_ms=float(outcome.elapsed_ms),
            fallback_mode=fallback_mode,
            debug_dump_path=outcome.debug_dump_path,
            chunk_token_budget=max(64, int(resolved["chunk_token_budget"])),
            chunk_disclosure=str(resolved["chunk_disclosure"]).strip().lower(),
            policy_name=str(resolved["retrieval_policy"]),
            policy_version=str(resolved["policy_version"]),
        )
    else:
        payload = outcome.payload or {}
    if output_json:
        target = Path(str(output_json)).expanduser()
        if not target.is_absolute():
            target = Path(root) / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    echo_json(payload)


__all__ = ["plan_command"]
