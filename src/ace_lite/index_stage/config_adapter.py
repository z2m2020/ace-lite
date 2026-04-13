from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar, cast

StageConfigT = TypeVar("StageConfigT")


def build_index_stage_config_from_orchestrator(
    *,
    config: Any,
    tokenizer_model: str,
    cochange_neighbor_cap: int,
    cochange_min_neighbor_score: float,
    cochange_max_boost: float,
    stage_config_cls: type[StageConfigT],
    retrieval_config_cls: type[Any],
    adaptive_router_config_cls: type[Any],
    chunking_config_cls: type[Any],
    topological_shield_config_cls: type[Any],
    chunk_guard_config_cls: type[Any],
) -> StageConfigT:
    stage_config_ctor = cast(Any, stage_config_cls)
    retrieval_config_ctor = cast(Any, retrieval_config_cls)
    adaptive_router_config_ctor = cast(Any, adaptive_router_config_cls)
    chunking_config_ctor = cast(Any, chunking_config_cls)
    topological_shield_config_ctor = cast(Any, topological_shield_config_cls)
    chunk_guard_config_ctor = cast(Any, chunk_guard_config_cls)

    index_config = getattr(config, "index", None)
    retrieval_config = getattr(config, "retrieval", None)
    embeddings_config = getattr(config, "embeddings", None)
    chunking_config = getattr(config, "chunking", None)
    topological_shield_config = getattr(chunking_config, "topological_shield", None)
    chunk_guard_config = getattr(chunking_config, "guard", None)
    cochange_config = getattr(config, "cochange", None)
    memory_config = getattr(config, "memory", None)
    feedback_config = getattr(memory_config, "feedback", None)
    scip_config = getattr(config, "scip", None)

    return cast(
        StageConfigT,
        stage_config_ctor(
        cache_path=Path(
            str(getattr(index_config, "cache_path", "context-map/index.json"))
        ),
        languages=list(getattr(index_config, "languages", None) or []),
        incremental=bool(getattr(index_config, "incremental", True)),
        retrieval=retrieval_config_ctor(
            retrieval_policy=str(
                getattr(retrieval_config, "retrieval_policy", "auto")
            ),
            policy_version=str(getattr(retrieval_config, "policy_version", "v1")),
            adaptive_router=adaptive_router_config_ctor(
                enabled=bool(
                    getattr(retrieval_config, "adaptive_router_enabled", False)
                ),
                mode=str(getattr(retrieval_config, "adaptive_router_mode", "observe")),
                model_path=str(
                    getattr(
                        retrieval_config,
                        "adaptive_router_model_path",
                        "context-map/router/model.json",
                    )
                ),
                state_path=str(
                    getattr(
                        retrieval_config,
                        "adaptive_router_state_path",
                        "context-map/router/state.json",
                    )
                ),
                arm_set=str(
                    getattr(
                        retrieval_config,
                        "adaptive_router_arm_set",
                        "retrieval_policy_v1",
                    )
                ),
                online_bandit_enabled=bool(
                    getattr(
                        retrieval_config,
                        "adaptive_router_online_bandit_enabled",
                        False,
                    )
                ),
                online_bandit_experiment_enabled=bool(
                    getattr(
                        retrieval_config,
                        "adaptive_router_online_bandit_experiment_enabled",
                        False,
                    )
                ),
            ),
            candidate_ranker=str(
                getattr(retrieval_config, "candidate_ranker", "heuristic")
            ),
            top_k_files=int(getattr(retrieval_config, "top_k_files", 8)),
            min_candidate_score=int(
                getattr(retrieval_config, "min_candidate_score", 2)
            ),
            candidate_relative_threshold=float(
                getattr(retrieval_config, "candidate_relative_threshold", 0.0)
            ),
            deterministic_refine_enabled=bool(
                getattr(retrieval_config, "deterministic_refine_enabled", True)
            ),
            hybrid_re2_fusion_mode=str(
                getattr(retrieval_config, "hybrid_re2_fusion_mode", "linear")
            ),
            hybrid_re2_rrf_k=int(
                getattr(retrieval_config, "hybrid_re2_rrf_k", 60)
            ),
            hybrid_re2_shortlist_min=int(
                getattr(retrieval_config, "hybrid_re2_shortlist_min", 12)
            ),
            hybrid_re2_shortlist_factor=int(
                getattr(retrieval_config, "hybrid_re2_shortlist_factor", 4)
            ),
            hybrid_re2_bm25_weight=float(
                getattr(retrieval_config, "hybrid_re2_bm25_weight", 0.0) or 0.0
            ),
            hybrid_re2_heuristic_weight=float(
                getattr(retrieval_config, "hybrid_re2_heuristic_weight", 0.0) or 0.0
            ),
            hybrid_re2_coverage_weight=float(
                getattr(retrieval_config, "hybrid_re2_coverage_weight", 0.0) or 0.0
            ),
            hybrid_re2_combined_scale=float(
                getattr(retrieval_config, "hybrid_re2_combined_scale", 0.0) or 0.0
            ),
            bm25_k1=float(getattr(retrieval_config, "bm25_k1", 1.2) or 1.2),
            bm25_b=float(getattr(retrieval_config, "bm25_b", 0.75) or 0.75),
            bm25_score_scale=float(
                getattr(retrieval_config, "bm25_score_scale", 4.0) or 4.0
            ),
            bm25_path_prior_factor=float(
                getattr(retrieval_config, "bm25_path_prior_factor", 0.1) or 0.1
            ),
            bm25_shortlist_min=int(
                getattr(retrieval_config, "bm25_shortlist_min", 16) or 16
            ),
            bm25_shortlist_factor=int(
                getattr(retrieval_config, "bm25_shortlist_factor", 6) or 6
            ),
            heur_path_exact=float(
                getattr(retrieval_config, "heur_path_exact", 3.0) or 3.0
            ),
            heur_path_contains=float(
                getattr(retrieval_config, "heur_path_contains", 2.0) or 2.0
            ),
            heur_module_exact=float(
                getattr(retrieval_config, "heur_module_exact", 3.0) or 3.0
            ),
            heur_module_tail=float(
                getattr(retrieval_config, "heur_module_tail", 2.5) or 2.5
            ),
            heur_module_contains=float(
                getattr(retrieval_config, "heur_module_contains", 1.5) or 1.5
            ),
            heur_symbol_exact=float(
                getattr(retrieval_config, "heur_symbol_exact", 3.0) or 3.0
            ),
            heur_symbol_partial_factor=float(
                getattr(retrieval_config, "heur_symbol_partial_factor", 0.75)
                or 0.75
            ),
            heur_symbol_partial_cap=float(
                getattr(retrieval_config, "heur_symbol_partial_cap", 2.0) or 2.0
            ),
            heur_import_factor=float(
                getattr(retrieval_config, "heur_import_factor", 0.5) or 0.5
            ),
            heur_import_cap=float(
                getattr(retrieval_config, "heur_import_cap", 1.5) or 1.5
            ),
            heur_content_symbol_factor=float(
                getattr(retrieval_config, "heur_content_symbol_factor", 0.2) or 0.2
            ),
            heur_content_import_factor=float(
                getattr(retrieval_config, "heur_content_import_factor", 0.1) or 0.1
            ),
            heur_content_cap=float(
                getattr(retrieval_config, "heur_content_cap", 1.0) or 1.0
            ),
            heur_depth_base=float(
                getattr(retrieval_config, "heur_depth_base", 1.4) or 1.4
            ),
            heur_depth_factor=float(
                getattr(retrieval_config, "heur_depth_factor", 0.15) or 0.15
            ),
            exact_search_enabled=bool(
                getattr(retrieval_config, "exact_search_enabled", False)
            ),
            exact_search_time_budget_ms=int(
                getattr(retrieval_config, "exact_search_time_budget_ms", 40)
            ),
            exact_search_max_paths=int(
                getattr(retrieval_config, "exact_search_max_paths", 24)
            ),
            multi_channel_rrf_enabled=bool(
                getattr(retrieval_config, "multi_channel_rrf_enabled", False)
            ),
            multi_channel_rrf_k=int(
                getattr(retrieval_config, "multi_channel_rrf_k", 60)
            ),
            multi_channel_rrf_pool_cap=int(
                getattr(retrieval_config, "multi_channel_rrf_pool_cap", 0) or 0
            ),
            multi_channel_rrf_code_cap=int(
                getattr(retrieval_config, "multi_channel_rrf_code_cap", 0) or 0
            ),
            multi_channel_rrf_docs_cap=int(
                getattr(retrieval_config, "multi_channel_rrf_docs_cap", 0) or 0
            ),
            multi_channel_rrf_memory_cap=int(
                getattr(retrieval_config, "multi_channel_rrf_memory_cap", 0) or 0
            ),
        ),
        embedding_enabled=bool(getattr(embeddings_config, "enabled", False)),
        embedding_provider=str(getattr(embeddings_config, "provider", "hash")),
        embedding_model=str(getattr(embeddings_config, "model", "hash-v1")),
        embedding_dimension=int(getattr(embeddings_config, "dimension", 256)),
        embedding_index_path=str(
            getattr(embeddings_config, "index_path", "context-map/embeddings/index.json")
        ),
        embedding_rerank_pool=int(getattr(embeddings_config, "rerank_pool", 24)),
        embedding_lexical_weight=float(
            getattr(embeddings_config, "lexical_weight", 0.7)
        ),
        embedding_semantic_weight=float(
            getattr(embeddings_config, "semantic_weight", 0.3)
        ),
        embedding_min_similarity=float(
            getattr(embeddings_config, "min_similarity", 0.0)
        ),
        embedding_fail_open=bool(getattr(embeddings_config, "fail_open", True)),
        chunking=chunking_config_ctor(
            top_k=int(getattr(chunking_config, "top_k", 24)),
            per_file_limit=int(getattr(chunking_config, "per_file_limit", 3)),
            token_budget=int(getattr(chunking_config, "token_budget", 1200)),
            disclosure=str(getattr(chunking_config, "disclosure", "refs")),
            snippet_max_lines=int(getattr(chunking_config, "snippet_max_lines", 18)),
            snippet_max_chars=int(getattr(chunking_config, "snippet_max_chars", 1200)),
            tokenizer_model=str(tokenizer_model or "gpt-4o-mini"),
            diversity_enabled=bool(
                getattr(chunking_config, "diversity_enabled", True)
            ),
            diversity_path_penalty=float(
                getattr(chunking_config, "diversity_path_penalty", 0.2)
            ),
            diversity_symbol_family_penalty=float(
                getattr(chunking_config, "diversity_symbol_family_penalty", 0.3)
            ),
            diversity_kind_penalty=float(
                getattr(chunking_config, "diversity_kind_penalty", 0.1)
            ),
            diversity_locality_penalty=float(
                getattr(chunking_config, "diversity_locality_penalty", 0.15)
            ),
            diversity_locality_window=int(
                getattr(chunking_config, "diversity_locality_window", 24)
            ),
            file_prior_weight=float(
                getattr(chunking_config, "file_prior_weight", 0.35) or 0.35
            ),
            path_match=float(getattr(chunking_config, "path_match", 1.0) or 1.0),
            module_match=float(
                getattr(chunking_config, "module_match", 0.8) or 0.8
            ),
            symbol_exact=float(
                getattr(chunking_config, "symbol_exact", 2.5) or 2.5
            ),
            symbol_partial=float(
                getattr(chunking_config, "symbol_partial", 1.4) or 1.4
            ),
            signature_match=float(
                getattr(chunking_config, "signature_match", 0.5) or 0.5
            ),
            reference_factor=float(
                getattr(chunking_config, "reference_factor", 0.3) or 0.3
            ),
            reference_cap=float(
                getattr(chunking_config, "reference_cap", 2.5) or 2.5
            ),
            topological_shield=topological_shield_config_ctor(
                enabled=bool(
                    getattr(topological_shield_config, "enabled", False)
                ),
                mode=str(getattr(topological_shield_config, "mode", "off")),
                max_attenuation=float(
                    getattr(topological_shield_config, "max_attenuation", 0.6) or 0.6
                ),
                shared_parent_attenuation=float(
                    getattr(
                        topological_shield_config,
                        "shared_parent_attenuation",
                        0.2,
                    )
                    or 0.2
                ),
                adjacency_attenuation=float(
                    getattr(topological_shield_config, "adjacency_attenuation", 0.5)
                    or 0.5
                ),
            ),
            guard=chunk_guard_config_ctor(
                enabled=bool(getattr(chunk_guard_config, "enabled", False)),
                mode=str(getattr(chunk_guard_config, "mode", "off")),
                lambda_penalty=float(
                    getattr(chunk_guard_config, "lambda_penalty", 0.8) or 0.8
                ),
                min_pool=int(getattr(chunk_guard_config, "min_pool", 4) or 4),
                max_pool=int(getattr(chunk_guard_config, "max_pool", 32) or 32),
                min_marginal_utility=float(
                    getattr(chunk_guard_config, "min_marginal_utility", 0.0) or 0.0
                ),
                compatibility_min_overlap=float(
                    getattr(chunk_guard_config, "compatibility_min_overlap", 0.3)
                    or 0.3
                ),
            ),
        ),
        cochange_enabled=bool(getattr(cochange_config, "enabled", True)),
        cochange_cache_path=str(
            getattr(cochange_config, "cache_path", "context-map/cochange.json")
        ),
        cochange_lookback_commits=int(
            getattr(cochange_config, "lookback_commits", 400)
        ),
        cochange_half_life_days=float(
            getattr(cochange_config, "half_life_days", 60.0)
        ),
        cochange_neighbor_cap=max(1, int(cochange_neighbor_cap)),
        cochange_top_neighbors=int(getattr(cochange_config, "top_neighbors", 12)),
        cochange_boost_weight=float(getattr(cochange_config, "boost_weight", 1.5)),
        cochange_min_neighbor_score=float(cochange_min_neighbor_score),
        cochange_max_boost=float(cochange_max_boost),
        feedback_enabled=bool(getattr(feedback_config, "enabled", False)),
        feedback_path=str(
            getattr(feedback_config, "path", "~/.ace-lite/profile.json")
        ),
        feedback_max_entries=int(getattr(feedback_config, "max_entries", 512)),
        feedback_boost_per_select=float(
            getattr(feedback_config, "boost_per_select", 0.15)
        ),
        feedback_max_boost=float(getattr(feedback_config, "max_boost", 0.6)),
        feedback_decay_days=float(getattr(feedback_config, "decay_days", 60.0)),
        scip_enabled=bool(getattr(scip_config, "enabled", False)),
        scip_index_path=str(
            getattr(scip_config, "index_path", "context-map/scip/index.json")
        ),
        scip_provider=str(getattr(scip_config, "provider", "auto")),
        scip_generate_fallback=bool(
            getattr(scip_config, "generate_fallback", True)
        ),
        scip_base_weight=float(getattr(scip_config, "base_weight", 0.5) or 0.5),
        ),
    )


__all__ = ["build_index_stage_config_from_orchestrator"]
