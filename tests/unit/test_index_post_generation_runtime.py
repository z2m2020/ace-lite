from __future__ import annotations

from ace_lite.index_stage.benchmark_candidate_runtime import (
    BenchmarkCandidateFilterResult,
)
from ace_lite.index_stage.candidate_fusion import CandidateFusionResult
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult
from ace_lite.index_stage.post_generation_runtime import (
    run_index_post_generation_runtime,
)


def test_run_index_post_generation_runtime_wires_fusion_filter_and_chunk() -> None:
    captured: dict[str, object] = {}

    def fake_run_index_candidate_fusion(**kwargs):  # type: ignore[no-untyped-def]
        captured["fusion"] = kwargs
        return CandidateFusionResult(
            candidates=[{"path": "src/alpha.py", "score": 8.0}],
            second_pass_payload={"enabled": False},
            refine_pass_payload={"enabled": False},
            cochange_payload={"enabled": False},
            scip_payload={"enabled": False},
            graph_lookup_payload={"enabled": False},
            embeddings_payload={"enabled": False},
            feedback_payload={"enabled": False},
            multi_channel_fusion_payload={"enabled": False},
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        )

    def fake_apply_benchmark_candidate_filters(
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        captured["benchmark"] = kwargs
        return BenchmarkCandidateFilterResult(
            candidates=[{"path": "src/alpha.py", "score": 8.0}],
            benchmark_filter_payload={"requested": True, "applied": True},
        )

    def fake_run_index_chunk_selection(**kwargs):  # type: ignore[no-untyped-def]
        captured["chunk"] = kwargs
        return ChunkSelectionResult(
            candidate_chunks=[{"path": "src/alpha.py", "lineno": 12}],
            chunk_metrics={"candidate_chunk_count": 1.0, "chunk_budget_used": 32.0},
            chunk_semantic_rerank_payload={"enabled": False},
            topological_shield_payload={"enabled": False},
            chunk_guard_payload={"enabled": False},
        )

    result = run_index_post_generation_runtime(
        root="/tmp/demo",
        repo="demo",
        query="router",
        terms=["router"],
        files_map={"src/alpha.py": {"module": "src.alpha"}},
        candidates=[{"path": "src/alpha.py", "score": 8.0}],
        memory_paths=[],
        docs_payload={"enabled": False},
        policy={"version": "v1"},
        selected_ranker="bm25",
        top_k_files=4,
        candidate_relative_threshold=0.25,
        refine_enabled=True,
        rank_candidates=lambda **kwargs: [],
        index_hash="idx",
        cochange_enabled=False,
        cochange_cache_path="tmp/cochange.json",
        cochange_lookback_commits=10,
        cochange_half_life_days=14.0,
        cochange_neighbor_cap=8,
        cochange_top_neighbors=4,
        cochange_boost_weight=0.3,
        cochange_min_neighbor_score=0.05,
        cochange_max_boost=0.4,
        scip_enabled=False,
        scip_index_path="context-map/scip.json",
        scip_provider="scip",
        scip_generate_fallback=False,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_enabled=False,
        embedding_provider="ollama",
        embedding_model="demo",
        embedding_dimension=1024,
        embedding_rerank_pool=16,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        feedback_enabled=False,
        feedback_path="tmp/feedback.jsonl",
        feedback_max_entries=50,
        feedback_boost_per_select=0.2,
        feedback_max_boost=0.8,
        feedback_decay_days=30.0,
        multi_channel_rrf_enabled=False,
        multi_channel_rrf_k=60,
        multi_channel_rrf_pool_cap=32,
        multi_channel_rrf_code_cap=16,
        multi_channel_rrf_docs_cap=8,
        multi_channel_rrf_memory_cap=8,
        benchmark_filter_payload={"requested": True},
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=320,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=18,
        chunk_snippet_max_chars=1200,
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.2,
        chunk_diversity_symbol_family_penalty=0.3,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
        chunk_topological_shield_enabled=True,
        chunk_topological_shield_mode="report_only",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        run_index_candidate_fusion_fn=fake_run_index_candidate_fusion,
        apply_benchmark_candidate_filters_fn=fake_apply_benchmark_candidate_filters,
        run_index_chunk_selection_fn=fake_run_index_chunk_selection,
        refine_candidate_pool_fn=lambda **kwargs: None,
        postprocess_candidates_fn=lambda **kwargs: None,
        apply_structural_rerank_fn=lambda **kwargs: None,
        apply_semantic_candidate_rerank_fn=lambda **kwargs: None,
        apply_feedback_boost_fn=lambda **kwargs: ([], {}),
        apply_multi_channel_rrf_fusion_fn=lambda **kwargs: ([], {}),
        merge_candidate_lists_fn=lambda **kwargs: [],
        resolve_embedding_runtime_config_fn=lambda **kwargs: None,
        build_embedding_stats_fn=lambda **kwargs: {},
        rerank_cross_encoder_with_time_budget_fn=lambda **kwargs: ([], None),
        filter_candidate_rows_fn=lambda **kwargs: ([], 0),
        select_index_chunks_fn=lambda **kwargs: None,
        apply_chunk_selection_fn=lambda **kwargs: None,
        mark_timing_fn=lambda label, started_at: None,
        rerank_rows_embeddings_with_time_budget_fn=lambda **kwargs: ([], None),
        rerank_rows_cross_encoder_with_time_budget_fn=lambda **kwargs: ([], None),
    )

    assert isinstance(captured["fusion"], dict)
    assert isinstance(captured["benchmark"], dict)
    assert isinstance(captured["chunk"], dict)
    assert captured["fusion"]["selected_ranker"] == "bm25"  # type: ignore[index]
    assert captured["chunk"]["chunk_top_k"] == 8  # type: ignore[index]
    assert result.candidates == [{"path": "src/alpha.py", "score": 8.0}]
    assert result.benchmark_filter_payload["applied"] is True
    assert result.candidate_chunks == [{"path": "src/alpha.py", "lineno": 12}]
