from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.index_stage.candidate_fusion import CandidateFusionResult
from ace_lite.index_stage.candidate_fusion_runtime import run_index_candidate_fusion


def test_run_index_candidate_fusion_builds_candidate_fusion_deps() -> None:
    captured: dict[str, Any] = {}

    def fake_refine_candidate_pool(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return CandidateFusionResult(
            candidates=[{"path": "src/app.py", "score": 1.0}],
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

    def fake_postprocess_candidates(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_apply_structural_rerank(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_apply_semantic_candidate_rerank(
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_apply_feedback_boost(
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_apply_multi_channel_rrf_fusion(
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_merge_candidate_lists(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_resolve_embedding_runtime_config(
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_build_embedding_stats(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_rerank_cross_encoder_with_time_budget(
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        raise AssertionError("deps should be forwarded, not invoked directly")

    def fake_mark_timing(label: str, started_at: float) -> None:
        _ = (label, started_at)

    result = run_index_candidate_fusion(
        root="/tmp/demo",
        repo="ace-lite-engine",
        query="router",
        terms=["router"],
        files_map={"src/app.py": {"module": "src.app"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        memory_paths=["src/app.py"],
        docs_payload={"enabled": False},
        policy={"version": "v1"},
        selected_ranker="bm25",
        top_k_files=4,
        candidate_relative_threshold=0.25,
        refine_enabled=True,
        rank_candidates=lambda **kwargs: [],
        index_hash="idx",
        cochange_enabled=True,
        cochange_cache_path="tmp/cochange.json",
        cochange_lookback_commits=40,
        cochange_half_life_days=14.0,
        cochange_neighbor_cap=16,
        cochange_top_neighbors=8,
        cochange_boost_weight=0.3,
        cochange_min_neighbor_score=0.05,
        cochange_max_boost=0.4,
        scip_enabled=True,
        scip_index_path="context-map/scip.json",
        scip_provider="scip",
        scip_generate_fallback=False,
        scip_base_weight=0.65,
        embedding_index_path=Path("context-map/embeddings/index.json"),
        embedding_enabled=True,
        embedding_provider="ollama",
        embedding_model="demo",
        embedding_dimension=1024,
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.1,
        embedding_fail_open=True,
        feedback_enabled=False,
        feedback_path="tmp/feedback.jsonl",
        feedback_max_entries=50,
        feedback_boost_per_select=0.2,
        feedback_max_boost=0.8,
        feedback_decay_days=30.0,
        multi_channel_rrf_enabled=True,
        multi_channel_rrf_k=60,
        multi_channel_rrf_pool_cap=40,
        multi_channel_rrf_code_cap=20,
        multi_channel_rrf_docs_cap=12,
        multi_channel_rrf_memory_cap=10,
        refine_candidate_pool_fn=fake_refine_candidate_pool,
        postprocess_candidates_fn=fake_postprocess_candidates,
        apply_structural_rerank_fn=fake_apply_structural_rerank,
        apply_semantic_candidate_rerank_fn=fake_apply_semantic_candidate_rerank,
        apply_feedback_boost_fn=fake_apply_feedback_boost,
        apply_multi_channel_rrf_fusion_fn=fake_apply_multi_channel_rrf_fusion,
        merge_candidate_lists_fn=fake_merge_candidate_lists,
        resolve_embedding_runtime_config_fn=fake_resolve_embedding_runtime_config,
        build_embedding_stats_fn=fake_build_embedding_stats,
        rerank_cross_encoder_with_time_budget_fn=(
            fake_rerank_cross_encoder_with_time_budget
        ),
        mark_timing_fn=fake_mark_timing,
        retrieval_refinement={"focus_paths": ["src/app.py"]},
    )

    assert result.candidates == [{"path": "src/app.py", "score": 1.0}]
    assert captured["top_k_files"] == 4
    assert captured["candidate_relative_threshold"] == 0.25
    assert captured["embedding_dimension"] == 1024
    assert captured["multi_channel_rrf_k"] == 60
    assert captured["scip_base_weight"] == 0.65
    assert captured["retrieval_refinement"] == {"focus_paths": ["src/app.py"]}
    deps = captured["deps"]
    assert deps.postprocess_candidates is fake_postprocess_candidates
    assert deps.apply_structural_rerank is fake_apply_structural_rerank
    assert deps.apply_semantic_candidate_rerank is fake_apply_semantic_candidate_rerank
    assert deps.apply_feedback_boost is fake_apply_feedback_boost
    assert deps.apply_multi_channel_rrf_fusion is fake_apply_multi_channel_rrf_fusion
    assert deps.merge_candidate_lists is fake_merge_candidate_lists
    assert deps.resolve_embedding_runtime_config is fake_resolve_embedding_runtime_config
    assert deps.build_embedding_stats is fake_build_embedding_stats
    assert (
        deps.rerank_cross_encoder_with_time_budget
        is fake_rerank_cross_encoder_with_time_budget
    )
    assert deps.mark_timing is fake_mark_timing
