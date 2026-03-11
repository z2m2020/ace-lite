from __future__ import annotations

from ace_lite.index_stage.config_adapter import (
    build_index_stage_config_from_orchestrator,
)
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.stages.index import (
    IndexAdaptiveRouterConfig,
    IndexChunkGuardConfig,
    IndexChunkingConfig,
    IndexRetrievalConfig,
    IndexStageConfig,
    IndexTopologicalShieldConfig,
)


def test_index_stage_config_from_orchestrator_config_maps_fields() -> None:
    config = OrchestratorConfig(
        index={
            "cache_path": "context-map/custom_index.json",
            "languages": ["python"],
            "incremental": False,
        },
        retrieval={
            "retrieval_policy": "feature",
            "policy_version": "v9",
            "adaptive_router_enabled": True,
            "adaptive_router_mode": "shadow",
            "adaptive_router_model_path": "context-map/router/custom-model.json",
            "adaptive_router_state_path": "context-map/router/custom-state.json",
            "adaptive_router_arm_set": "retrieval_policy_shadow",
            "adaptive_router_online_bandit_enabled": True,
            "adaptive_router_online_bandit_experiment_enabled": True,
            "candidate_ranker": "hybrid_re2",
            "top_k_files": 3,
            "min_candidate_score": 5,
            "candidate_relative_threshold": 0.25,
            "deterministic_refine_enabled": False,
            "hybrid_re2_fusion_mode": "rrf",
            "hybrid_re2_rrf_k": 77,
        },
        embeddings={
            "enabled": True,
            "provider": "hash_cross",
            "model": "hash-cross-v1",
            "dimension": 16,
            "index_path": "context-map/embeddings/custom.json",
            "rerank_pool": 9,
            "lexical_weight": 0.2,
            "semantic_weight": 0.8,
            "min_similarity": 0.1,
            "fail_open": False,
        },
        chunking={
            "top_k": 10,
            "per_file_limit": 4,
            "token_budget": 999,
            "disclosure": "snippet",
            "snippet_max_lines": 7,
            "snippet_max_chars": 42,
            "guard": {
                "enabled": True,
                "mode": "report_only",
                "lambda_penalty": 0.9,
                "min_pool": 5,
                "max_pool": 40,
                "min_marginal_utility": 0.1,
                "compatibility_min_overlap": 0.4,
            },
            "diversity_enabled": False,
            "diversity_path_penalty": 0.11,
            "diversity_symbol_family_penalty": 0.22,
            "diversity_kind_penalty": 0.33,
            "diversity_locality_penalty": 0.44,
            "diversity_locality_window": 55,
        },
        cochange={
            "enabled": True,
            "cache_path": "context-map/cochange_custom.json",
            "lookback_commits": 10,
            "half_life_days": 11.0,
            "top_neighbors": 12,
            "boost_weight": 1.25,
        },
        memory={
            "feedback": {
                "enabled": True,
                "path": "context-map/profile.json",
                "max_entries": 7,
                "boost_per_select": 0.2,
                "max_boost": 0.8,
                "decay_days": 10.0,
            }
        },
        scip={
            "enabled": True,
            "index_path": "context-map/scip/custom.json",
            "provider": "auto",
            "generate_fallback": False,
        },
    )

    stage_cfg = IndexStageConfig.from_orchestrator_config(
        config=config,
        tokenizer_model="gpt-4o-mini",
        cochange_neighbor_cap=64,
        cochange_min_neighbor_score=0.15,
        cochange_max_boost=0.8,
    )

    assert stage_cfg.cache_path.as_posix().endswith("context-map/custom_index.json")
    assert stage_cfg.languages == ["python"]
    assert stage_cfg.incremental is False

    assert stage_cfg.retrieval.retrieval_policy == "feature"
    assert stage_cfg.retrieval.policy_version == "v9"
    assert stage_cfg.retrieval.adaptive_router.enabled is True
    assert stage_cfg.retrieval.adaptive_router.mode == "shadow"
    assert (
        stage_cfg.retrieval.adaptive_router.model_path
        == "context-map/router/custom-model.json"
    )
    assert (
        stage_cfg.retrieval.adaptive_router.state_path
        == "context-map/router/custom-state.json"
    )
    assert stage_cfg.retrieval.adaptive_router.arm_set == "retrieval_policy_shadow"
    assert stage_cfg.retrieval.adaptive_router.online_bandit_enabled is True
    assert stage_cfg.retrieval.adaptive_router.online_bandit_experiment_enabled is True
    assert stage_cfg.retrieval.candidate_ranker == "hybrid_re2"
    assert stage_cfg.retrieval.top_k_files == 3
    assert stage_cfg.retrieval.min_candidate_score == 5
    assert stage_cfg.retrieval.candidate_relative_threshold == 0.25
    assert stage_cfg.retrieval.deterministic_refine_enabled is False
    assert stage_cfg.retrieval.hybrid_re2_fusion_mode == "rrf"
    assert stage_cfg.retrieval.hybrid_re2_rrf_k == 77

    assert stage_cfg.embedding_enabled is True
    assert stage_cfg.embedding_provider == "hash_cross"
    assert stage_cfg.embedding_model == "hash-cross-v1"
    assert stage_cfg.embedding_dimension == 16
    assert stage_cfg.embedding_index_path == "context-map/embeddings/custom.json"
    assert stage_cfg.embedding_rerank_pool == 9
    assert stage_cfg.embedding_lexical_weight == 0.2
    assert stage_cfg.embedding_semantic_weight == 0.8
    assert stage_cfg.embedding_min_similarity == 0.1
    assert stage_cfg.embedding_fail_open is False

    assert stage_cfg.chunking.top_k == 10
    assert stage_cfg.chunking.per_file_limit == 4
    assert stage_cfg.chunking.token_budget == 999
    assert stage_cfg.chunking.disclosure == "snippet"
    assert stage_cfg.chunking.snippet_max_lines == 7
    assert stage_cfg.chunking.snippet_max_chars == 42
    assert stage_cfg.chunking.tokenizer_model == "gpt-4o-mini"
    assert stage_cfg.chunking.guard.enabled is True
    assert stage_cfg.chunking.guard.mode == "report_only"
    assert stage_cfg.chunking.guard.lambda_penalty == 0.9
    assert stage_cfg.chunking.guard.min_pool == 5
    assert stage_cfg.chunking.guard.max_pool == 40
    assert stage_cfg.chunking.guard.min_marginal_utility == 0.1
    assert stage_cfg.chunking.guard.compatibility_min_overlap == 0.4
    assert stage_cfg.chunking.diversity_enabled is False
    assert stage_cfg.chunking.diversity_path_penalty == 0.11
    assert stage_cfg.chunking.diversity_symbol_family_penalty == 0.22
    assert stage_cfg.chunking.diversity_kind_penalty == 0.33
    assert stage_cfg.chunking.diversity_locality_penalty == 0.44
    assert stage_cfg.chunking.diversity_locality_window == 55

    assert stage_cfg.cochange_enabled is True
    assert stage_cfg.cochange_cache_path == "context-map/cochange_custom.json"
    assert stage_cfg.cochange_lookback_commits == 10
    assert stage_cfg.cochange_half_life_days == 11.0
    assert stage_cfg.cochange_neighbor_cap == 64
    assert stage_cfg.cochange_top_neighbors == 12
    assert stage_cfg.cochange_boost_weight == 1.25
    assert stage_cfg.cochange_min_neighbor_score == 0.15
    assert stage_cfg.cochange_max_boost == 0.8

    assert stage_cfg.feedback_enabled is True
    assert stage_cfg.feedback_path == "context-map/profile.json"
    assert stage_cfg.feedback_max_entries == 7
    assert stage_cfg.feedback_boost_per_select == 0.2
    assert stage_cfg.feedback_max_boost == 0.8
    assert stage_cfg.feedback_decay_days == 10.0

    assert stage_cfg.scip_enabled is True
    assert stage_cfg.scip_index_path == "context-map/scip/custom.json"
    assert stage_cfg.scip_provider == "auto"
    assert stage_cfg.scip_generate_fallback is False


def test_index_stage_config_adapter_matches_classmethod() -> None:
    config = OrchestratorConfig()

    via_classmethod = IndexStageConfig.from_orchestrator_config(
        config=config,
        tokenizer_model="gpt-4o-mini",
        cochange_neighbor_cap=8,
        cochange_min_neighbor_score=0.15,
        cochange_max_boost=0.4,
    )
    via_adapter = build_index_stage_config_from_orchestrator(
        config=config,
        tokenizer_model="gpt-4o-mini",
        cochange_neighbor_cap=8,
        cochange_min_neighbor_score=0.15,
        cochange_max_boost=0.4,
        stage_config_cls=IndexStageConfig,
        retrieval_config_cls=IndexRetrievalConfig,
        adaptive_router_config_cls=IndexAdaptiveRouterConfig,
        chunking_config_cls=IndexChunkingConfig,
        topological_shield_config_cls=IndexTopologicalShieldConfig,
        chunk_guard_config_cls=IndexChunkGuardConfig,
    )

    assert via_adapter == via_classmethod
