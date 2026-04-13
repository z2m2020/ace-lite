from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.index_stage.embedding_runtime import EmbeddingRuntimeConfig
from ace_lite.pipeline.types import StageContext


@dataclass(slots=True)
class IndexRuntimeBootstrapResult:
    terms: list[str]
    memory_paths: list[str]
    policy: dict[str, Any]
    adaptive_router_payload: dict[str, Any]
    index_data: dict[str, Any]
    cache_info: dict[str, Any]
    effective_files_map: dict[str, dict[str, Any]]
    corpus_size: int
    effective_corpus_size: int
    index_hash: str
    benchmark_filter_payload: dict[str, Any]
    docs_policy_enabled: bool
    worktree_prior_enabled: bool
    worktree_policy_reason: str
    embedding_runtime: EmbeddingRuntimeConfig
    index_candidate_cache_path: Path
    index_candidate_cache_key: str
    index_candidate_cache_ttl_seconds: int
    index_candidate_cache_required_meta: dict[str, Any]
    index_candidate_cache: dict[str, Any]
    cache_hit_payload: dict[str, Any] | None


def _build_chunk_cache_required_meta(index_data: dict[str, Any]) -> dict[str, Any]:
    contract = (
        index_data.get("chunk_cache_contract", {})
        if isinstance(index_data.get("chunk_cache_contract"), dict)
        else {}
    )
    return {
        "chunk_cache_contract_schema_version": str(
            contract.get("schema_version") or ""
        ),
        "chunk_cache_contract_fingerprint": str(contract.get("fingerprint") or ""),
    }


def _build_index_candidate_cache_settings_payload(
    *,
    retrieval_cfg: Any,
    chunking_cfg: Any,
    chunk_guard_cfg: Any,
    topological_shield_cfg: Any,
    router_cfg: Any,
    config: Any,
    policy: dict[str, Any],
    benchmark_filter_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "retrieval": {
            "exact_search_time_budget_ms": int(
                retrieval_cfg.exact_search_time_budget_ms
            ),
            "exact_search_max_paths": int(retrieval_cfg.exact_search_max_paths),
            "hybrid_re2_fusion_mode": str(retrieval_cfg.hybrid_re2_fusion_mode),
            "hybrid_re2_rrf_k": int(retrieval_cfg.hybrid_re2_rrf_k),
            "hybrid_re2_shortlist_min": int(retrieval_cfg.hybrid_re2_shortlist_min),
            "hybrid_re2_shortlist_factor": int(
                retrieval_cfg.hybrid_re2_shortlist_factor
            ),
            "hybrid_re2_bm25_weight": float(retrieval_cfg.hybrid_re2_bm25_weight),
            "hybrid_re2_heuristic_weight": float(
                retrieval_cfg.hybrid_re2_heuristic_weight
            ),
            "hybrid_re2_coverage_weight": float(
                retrieval_cfg.hybrid_re2_coverage_weight
            ),
            "hybrid_re2_combined_scale": float(
                retrieval_cfg.hybrid_re2_combined_scale
            ),
            "bm25_k1": float(retrieval_cfg.bm25_k1),
            "bm25_b": float(retrieval_cfg.bm25_b),
            "bm25_score_scale": float(retrieval_cfg.bm25_score_scale),
            "bm25_path_prior_factor": float(
                retrieval_cfg.bm25_path_prior_factor
            ),
            "bm25_shortlist_min": int(retrieval_cfg.bm25_shortlist_min),
            "bm25_shortlist_factor": int(retrieval_cfg.bm25_shortlist_factor),
            "heur_path_exact": float(retrieval_cfg.heur_path_exact),
            "heur_path_contains": float(retrieval_cfg.heur_path_contains),
            "heur_module_exact": float(retrieval_cfg.heur_module_exact),
            "heur_module_tail": float(retrieval_cfg.heur_module_tail),
            "heur_module_contains": float(retrieval_cfg.heur_module_contains),
            "heur_symbol_exact": float(retrieval_cfg.heur_symbol_exact),
            "heur_symbol_partial_factor": float(
                retrieval_cfg.heur_symbol_partial_factor
            ),
            "heur_symbol_partial_cap": float(retrieval_cfg.heur_symbol_partial_cap),
            "heur_import_factor": float(retrieval_cfg.heur_import_factor),
            "heur_import_cap": float(retrieval_cfg.heur_import_cap),
            "heur_content_symbol_factor": float(
                retrieval_cfg.heur_content_symbol_factor
            ),
            "heur_content_import_factor": float(
                retrieval_cfg.heur_content_import_factor
            ),
            "heur_content_cap": float(retrieval_cfg.heur_content_cap),
            "heur_depth_base": float(retrieval_cfg.heur_depth_base),
            "heur_depth_factor": float(retrieval_cfg.heur_depth_factor),
            "multi_channel_rrf_k": int(retrieval_cfg.multi_channel_rrf_k),
            "multi_channel_rrf_pool_cap": int(
                retrieval_cfg.multi_channel_rrf_pool_cap
            ),
            "multi_channel_rrf_code_cap": int(
                retrieval_cfg.multi_channel_rrf_code_cap
            ),
            "multi_channel_rrf_docs_cap": int(
                retrieval_cfg.multi_channel_rrf_docs_cap
            ),
            "multi_channel_rrf_memory_cap": int(
                retrieval_cfg.multi_channel_rrf_memory_cap
            ),
        },
        "chunking": {
            "diversity_enabled": bool(chunking_cfg.diversity_enabled),
            "diversity_path_penalty": float(chunking_cfg.diversity_path_penalty),
            "diversity_symbol_family_penalty": float(
                chunking_cfg.diversity_symbol_family_penalty
            ),
            "diversity_kind_penalty": float(chunking_cfg.diversity_kind_penalty),
            "diversity_locality_penalty": float(
                chunking_cfg.diversity_locality_penalty
            ),
            "diversity_locality_window": int(chunking_cfg.diversity_locality_window),
            "file_prior_weight": float(chunking_cfg.file_prior_weight),
            "path_match": float(chunking_cfg.path_match),
            "module_match": float(chunking_cfg.module_match),
            "symbol_exact": float(chunking_cfg.symbol_exact),
            "symbol_partial": float(chunking_cfg.symbol_partial),
            "signature_match": float(chunking_cfg.signature_match),
            "reference_factor": float(chunking_cfg.reference_factor),
            "reference_cap": float(chunking_cfg.reference_cap),
            "topological_max_attenuation": float(
                topological_shield_cfg.max_attenuation
            ),
            "topological_shared_parent_attenuation": float(
                topological_shield_cfg.shared_parent_attenuation
            ),
            "topological_adjacency_attenuation": float(
                topological_shield_cfg.adjacency_attenuation
            ),
            "guard_lambda_penalty": float(chunk_guard_cfg.lambda_penalty),
            "guard_min_pool": int(chunk_guard_cfg.min_pool),
            "guard_max_pool": int(chunk_guard_cfg.max_pool),
            "guard_min_marginal_utility": float(
                chunk_guard_cfg.min_marginal_utility
            ),
            "guard_compatibility_min_overlap": float(
                chunk_guard_cfg.compatibility_min_overlap
            ),
        },
        "embedding": {
            "rerank_pool": int(config.embedding_rerank_pool),
            "lexical_weight": float(config.embedding_lexical_weight),
            "semantic_weight": float(config.embedding_semantic_weight),
            "min_similarity": float(config.embedding_min_similarity),
            "fail_open": bool(config.embedding_fail_open),
        },
        "feedback": {
            "path": str(config.feedback_path),
            "max_entries": int(config.feedback_max_entries),
            "boost_per_select": float(config.feedback_boost_per_select),
            "max_boost": float(config.feedback_max_boost),
            "decay_days": float(config.feedback_decay_days),
        },
        "feature_flags": {
            "cochange_enabled": bool(config.cochange_enabled),
            "scip_enabled": bool(config.scip_enabled),
            "scip_base_weight": float(config.scip_base_weight),
        },
        "adaptive_router": {
            "enabled": bool(router_cfg.enabled),
            "mode": str(router_cfg.mode),
            "model_path": str(router_cfg.model_path),
            "state_path": str(router_cfg.state_path),
            "arm_set": str(router_cfg.arm_set),
            "online_bandit_enabled": bool(router_cfg.online_bandit_enabled),
            "online_bandit_experiment_enabled": bool(
                router_cfg.online_bandit_experiment_enabled
            ),
        },
        "benchmark_filters": dict(benchmark_filter_payload),
        "policy": {
            "name": str(policy.get("name", "general")),
            "version": str(policy.get("version", "")),
        },
    }


def bootstrap_index_runtime(
    *,
    ctx: StageContext,
    config: Any,
    content_version: str,
    timings_ms: dict[str, float],
    mark_timing: Callable[[str, float], None],
    extract_retrieval_terms_fn: Callable[..., list[str]],
    extract_memory_paths_fn: Callable[..., list[str]],
    resolve_retrieval_policy_fn: Callable[..., dict[str, Any]],
    resolve_shadow_router_arm_fn: Callable[..., dict[str, Any]],
    resolve_online_bandit_gate_fn: Callable[..., dict[str, Any]],
    build_adaptive_router_payload_fn: Callable[..., dict[str, Any]],
    load_retrieval_index_snapshot_fn: Callable[..., Any],
    resolve_benchmark_candidate_filters_fn: Callable[..., dict[str, Any]],
    filter_files_map_for_benchmark_fn: Callable[..., tuple[dict[str, dict[str, Any]], int]],
    resolve_docs_policy_for_benchmark_fn: Callable[..., tuple[bool, str]],
    resolve_worktree_policy_for_benchmark_fn: Callable[..., tuple[bool, str]],
    resolve_embedding_runtime_config_fn: Callable[..., EmbeddingRuntimeConfig],
    resolve_repo_relative_path_fn: Callable[..., str],
    default_index_candidate_cache_path_fn: Callable[..., Path],
    build_index_candidate_cache_key_fn: Callable[..., str],
    load_cached_index_candidates_checked_fn: Callable[..., dict[str, Any] | None],
    build_disabled_worktree_prior_fn: Callable[..., dict[str, Any]],
    refresh_cached_index_candidate_payload_fn: Callable[..., dict[str, Any]],
    attach_index_candidate_cache_info_fn: Callable[..., dict[str, Any]],
) -> IndexRuntimeBootstrapResult:
    retrieval_cfg = config.retrieval
    router_cfg = retrieval_cfg.adaptive_router
    chunking_cfg = config.chunking
    topological_shield_cfg = chunking_cfg.topological_shield
    chunk_guard_cfg = chunking_cfg.guard

    timing_started = perf_counter()
    memory_stage = (
        ctx.state.get("memory", {}) if isinstance(ctx.state.get("memory"), dict) else {}
    )
    terms = extract_retrieval_terms_fn(query=ctx.query, memory_stage=memory_stage)
    memory_paths = extract_memory_paths_fn(memory_stage=memory_stage, root=ctx.root)
    mark_timing("term_extraction", timing_started)

    timing_started = perf_counter()
    policy = resolve_retrieval_policy_fn(
        query=ctx.query,
        retrieval_policy=retrieval_cfg.retrieval_policy,
        policy_version=retrieval_cfg.policy_version,
        cochange_enabled=config.cochange_enabled,
        embedding_enabled=config.embedding_enabled,
    )
    shadow_router = resolve_shadow_router_arm_fn(
        enabled=router_cfg.enabled,
        mode=router_cfg.mode,
        model_path=resolve_repo_relative_path_fn(
            root=ctx.root,
            configured_path=router_cfg.model_path,
        ),
        arm_set=router_cfg.arm_set,
        executed_policy_name=str(policy.get("name", "")).strip(),
        candidate_ranker=retrieval_cfg.candidate_ranker,
        embedding_enabled=bool(policy.get("embedding_enabled", config.embedding_enabled)),
    )
    online_bandit_gate = resolve_online_bandit_gate_fn(
        enabled=router_cfg.online_bandit_enabled,
        experiment_enabled=router_cfg.online_bandit_experiment_enabled,
        state_path=resolve_repo_relative_path_fn(
            root=ctx.root,
            configured_path=router_cfg.state_path,
        ),
    )
    adaptive_router_payload = build_adaptive_router_payload_fn(
        enabled=bool(router_cfg.enabled),
        mode=str(router_cfg.mode),
        model_path=str(router_cfg.model_path),
        state_path=str(router_cfg.state_path),
        arm_set=str(router_cfg.arm_set),
        policy=policy,
        shadow=shadow_router,
        online_bandit=online_bandit_gate,
    )
    ctx.state["__policy"] = policy
    mark_timing("policy_resolution", timing_started)

    timing_started = perf_counter()
    snapshot = load_retrieval_index_snapshot_fn(
        root_dir=ctx.root,
        cache_path=str(config.cache_path),
        languages=config.languages,
        incremental=config.incremental,
        fail_open=True,
        include_index_hash=True,
    )
    index_data = snapshot.index_payload
    cache_info = snapshot.cache_info
    mark_timing("index_cache_load", timing_started)

    files_map = snapshot.files_map
    index_hash = snapshot.index_hash
    corpus_size = snapshot.corpus_size
    benchmark_filter_payload = resolve_benchmark_candidate_filters_fn(ctx)
    effective_files_map = files_map
    effective_corpus_size = corpus_size
    if benchmark_filter_payload["requested"]:
        filtered_files_map, removed_file_count = filter_files_map_for_benchmark_fn(
            files_map,
            include_paths=list(benchmark_filter_payload["include_paths"]),
            include_globs=list(benchmark_filter_payload["include_globs"]),
            exclude_paths=list(benchmark_filter_payload["exclude_paths"]),
            exclude_globs=list(benchmark_filter_payload["exclude_globs"]),
        )
        benchmark_filter_payload["files_map_count_before"] = len(files_map)
        benchmark_filter_payload["files_map_count_after"] = len(filtered_files_map)
        benchmark_filter_payload["dropped_files_map_count"] = int(removed_file_count)
        if filtered_files_map:
            effective_files_map = filtered_files_map
            effective_corpus_size = len(filtered_files_map)
            benchmark_filter_payload["files_map_applied"] = True
            benchmark_filter_payload["files_map_fallback_to_unfiltered"] = False
        else:
            benchmark_filter_payload["files_map_applied"] = False
            benchmark_filter_payload["files_map_fallback_to_unfiltered"] = True
    else:
        benchmark_filter_payload["files_map_count_before"] = len(files_map)
        benchmark_filter_payload["files_map_count_after"] = len(files_map)
        benchmark_filter_payload["dropped_files_map_count"] = 0
        benchmark_filter_payload["files_map_applied"] = False
        benchmark_filter_payload["files_map_fallback_to_unfiltered"] = False
    ctx.state["__index_files"] = effective_files_map

    docs_policy_enabled, docs_policy_reason = resolve_docs_policy_for_benchmark_fn(
        policy_docs_enabled=bool(policy.get("docs_enabled", True)),
        benchmark_filter_payload=benchmark_filter_payload,
    )
    benchmark_filter_payload["docs_policy_enabled"] = bool(docs_policy_enabled)
    benchmark_filter_payload["docs_policy_reason"] = str(docs_policy_reason)
    worktree_prior_enabled, worktree_policy_reason = (
        resolve_worktree_policy_for_benchmark_fn(
            worktree_prior_enabled=bool(config.cochange_enabled),
            benchmark_filter_payload=benchmark_filter_payload,
        )
    )
    benchmark_filter_payload["worktree_policy_enabled"] = bool(worktree_prior_enabled)
    benchmark_filter_payload["worktree_policy_reason"] = str(worktree_policy_reason)

    embedding_runtime = resolve_embedding_runtime_config_fn(
        provider=str(config.embedding_provider),
        model=str(config.embedding_model),
        dimension=int(config.embedding_dimension),
    )
    index_candidate_cache_path = default_index_candidate_cache_path_fn(root=ctx.root)
    index_candidate_cache_ttl_seconds = max(
        0, int(policy.get("index_candidate_cache_ttl_seconds", 1800) or 1800)
    )
    index_candidate_cache_required_meta = {
        "policy_name": str(policy.get("name", "general")),
        "policy_version": str(policy.get("version", retrieval_cfg.policy_version)),
        "index_hash": str(index_hash or ""),
        "content_version": content_version,
        **_build_chunk_cache_required_meta(index_data),
    }
    index_candidate_cache_key = build_index_candidate_cache_key_fn(
        query=ctx.query,
        terms=terms,
        memory_paths=memory_paths,
        index_hash=index_hash,
        policy=policy,
        requested_ranker=str(retrieval_cfg.candidate_ranker),
        top_k_files=int(retrieval_cfg.top_k_files),
        min_candidate_score=int(retrieval_cfg.min_candidate_score),
        candidate_relative_threshold=float(retrieval_cfg.candidate_relative_threshold),
        chunk_top_k=int(chunking_cfg.top_k),
        chunk_per_file_limit=int(chunking_cfg.per_file_limit),
        chunk_token_budget=int(chunking_cfg.token_budget),
        chunk_disclosure=str(chunking_cfg.disclosure),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        deterministic_refine_enabled=bool(retrieval_cfg.deterministic_refine_enabled),
        embedding_enabled=bool(config.embedding_enabled),
        embedding_provider=str(embedding_runtime.provider),
        embedding_model=str(embedding_runtime.model),
        embedding_dimension=int(embedding_runtime.dimension),
        feedback_enabled=bool(config.feedback_enabled),
        multi_channel_rrf_enabled=bool(retrieval_cfg.multi_channel_rrf_enabled)
        or str(policy.get("version", "")).strip().lower().startswith("v2"),
        chunk_guard_mode=str(chunk_guard_cfg.mode),
        topological_shield_mode=str(topological_shield_cfg.mode),
        settings_payload=_build_index_candidate_cache_settings_payload(
            retrieval_cfg=retrieval_cfg,
            chunking_cfg=chunking_cfg,
            chunk_guard_cfg=chunk_guard_cfg,
            topological_shield_cfg=topological_shield_cfg,
            router_cfg=router_cfg,
            config=config,
            policy=policy,
            benchmark_filter_payload=benchmark_filter_payload,
        ),
        content_version=content_version,
    )
    index_candidate_cache = {
        "enabled": True,
        "hit": False,
        "store_written": False,
        "cache_key": str(index_candidate_cache_key),
        "path": str(index_candidate_cache_path),
        "ttl_seconds": int(index_candidate_cache_ttl_seconds),
        "content_version": content_version,
    }

    cached_index_payload = load_cached_index_candidates_checked_fn(
        cache_path=index_candidate_cache_path,
        key=index_candidate_cache_key,
        max_age_seconds=index_candidate_cache_ttl_seconds,
        required_meta=index_candidate_cache_required_meta,
    )
    cache_hit_payload: dict[str, Any] | None = None
    if cached_index_payload is not None:
        index_candidate_cache["hit"] = True
        if bool(config.cochange_enabled) and not worktree_prior_enabled:
            ctx.state["__vcs_worktree"] = build_disabled_worktree_prior_fn(
                reason=worktree_policy_reason
            )
        else:
            ctx.state.pop("__vcs_worktree", None)
        refreshed_cached_payload = refresh_cached_index_candidate_payload_fn(
            payload=cached_index_payload,
            index_data=index_data,
            cache_info=cache_info,
            index_hash=index_hash,
            timings_ms=timings_ms,
            benchmark_filter_payload=benchmark_filter_payload,
        )
        cache_hit_payload = attach_index_candidate_cache_info_fn(
            payload=refreshed_cached_payload,
            cache_info=index_candidate_cache,
        )

    return IndexRuntimeBootstrapResult(
        terms=terms,
        memory_paths=memory_paths,
        policy=policy,
        adaptive_router_payload=adaptive_router_payload,
        index_data=index_data,
        cache_info=cache_info,
        effective_files_map=effective_files_map,
        corpus_size=corpus_size,
        effective_corpus_size=effective_corpus_size,
        index_hash=str(index_hash or ""),
        benchmark_filter_payload=benchmark_filter_payload,
        docs_policy_enabled=bool(docs_policy_enabled),
        worktree_prior_enabled=bool(worktree_prior_enabled),
        worktree_policy_reason=str(worktree_policy_reason),
        embedding_runtime=embedding_runtime,
        index_candidate_cache_path=index_candidate_cache_path,
        index_candidate_cache_key=str(index_candidate_cache_key),
        index_candidate_cache_ttl_seconds=int(index_candidate_cache_ttl_seconds),
        index_candidate_cache_required_meta=index_candidate_cache_required_meta,
        index_candidate_cache=index_candidate_cache,
        cache_hit_payload=cache_hit_payload,
    )
