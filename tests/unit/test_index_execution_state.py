from __future__ import annotations

from types import SimpleNamespace

from ace_lite.index_stage.execution_state import (
    apply_candidate_generation_runtime_to_state,
    apply_post_generation_runtime_to_state,
    build_index_stage_execution_state,
)


def test_build_index_stage_execution_state_from_bootstrap() -> None:
    bootstrap = SimpleNamespace(
        terms=["router"],
        memory_paths=["docs/guide.md"],
        policy={"name": "general"},
        adaptive_router_payload={"enabled": False},
        index_data={"file_count": 1},
        cache_info={"cache_hit": False},
        effective_files_map={"src/app.py": {"module": "src.app"}},
        corpus_size=10,
        effective_corpus_size=8,
        index_hash="idx",
        benchmark_filter_payload={"requested": False},
        docs_policy_enabled=True,
        worktree_prior_enabled=False,
        worktree_policy_reason="disabled",
        embedding_runtime=SimpleNamespace(provider="ollama"),
        index_candidate_cache_path="context-map/cache.db",
        index_candidate_cache_key="cache-key",
        index_candidate_cache_ttl_seconds=1800,
        index_candidate_cache_required_meta={"policy_name": "general"},
        index_candidate_cache={"hit": False},
    )

    state = build_index_stage_execution_state(bootstrap=bootstrap)

    assert state.terms == ["router"]
    assert state.memory_paths == ["docs/guide.md"]
    assert state.index_hash == "idx"
    assert state.corpus_size == 10
    assert state.index_candidate_cache_key == "cache-key"


def test_apply_candidate_generation_runtime_to_state_updates_timings_and_worktree() -> None:
    bootstrap = SimpleNamespace(
        terms=[],
        memory_paths=[],
        policy={},
        adaptive_router_payload={},
        index_data={},
        cache_info={},
        effective_files_map={},
        corpus_size=0,
        effective_corpus_size=0,
        index_hash="",
        benchmark_filter_payload={},
        docs_policy_enabled=False,
        worktree_prior_enabled=False,
        worktree_policy_reason="",
        embedding_runtime=None,
        index_candidate_cache_path="",
        index_candidate_cache_key="",
        index_candidate_cache_ttl_seconds=0,
        index_candidate_cache_required_meta={},
        index_candidate_cache={},
    )
    state = build_index_stage_execution_state(bootstrap=bootstrap)
    runtime = SimpleNamespace(
        initial_candidates=SimpleNamespace(
            requested_ranker="bm25",
            selected_ranker="heuristic",
            ranker_fallbacks=["tiny_corpus"],
            min_score_used=2,
            candidates=[{"path": "src/app.py", "score": 1.0}],
            exact_search_payload={"enabled": False},
            docs_payload={"enabled": False},
            worktree_prior={"enabled": False},
            parallel_payload={"enabled": False},
            prior_payload={"enabled": False},
        ),
        docs_timing_ms=1.25,
        worktree_timing_ms=0.5,
        raw_worktree={"changed_paths": ["src/app.py"]},
    )
    timings_ms: dict[str, float] = {}
    ctx_state: dict[str, object] = {}

    apply_candidate_generation_runtime_to_state(
        state=state,
        candidate_generation_runtime=runtime,
        timings_ms=timings_ms,
        cochange_enabled=True,
        ctx_state=ctx_state,
    )

    assert state.requested_ranker == "bm25"
    assert state.candidates == [{"path": "src/app.py", "score": 1.0}]
    assert timings_ms["docs_signals"] == 1.25
    assert timings_ms["worktree_prior"] == 0.5
    assert ctx_state["__vcs_worktree"] == {"changed_paths": ["src/app.py"]}


def test_apply_post_generation_runtime_to_state_updates_outputs() -> None:
    bootstrap = SimpleNamespace(
        terms=[],
        memory_paths=[],
        policy={},
        adaptive_router_payload={},
        index_data={},
        cache_info={},
        effective_files_map={},
        corpus_size=0,
        effective_corpus_size=0,
        index_hash="",
        benchmark_filter_payload={},
        docs_policy_enabled=False,
        worktree_prior_enabled=False,
        worktree_policy_reason="",
        embedding_runtime=None,
        index_candidate_cache_path="",
        index_candidate_cache_key="",
        index_candidate_cache_ttl_seconds=0,
        index_candidate_cache_required_meta={},
        index_candidate_cache={},
    )
    state = build_index_stage_execution_state(bootstrap=bootstrap)
    runtime = SimpleNamespace(
        candidates=[{"path": "src/app.py", "score": 1.0}],
        second_pass_payload={"enabled": False},
        refine_pass_payload={"enabled": False},
        retrieval_refinement_payload={"enabled": False},
        cochange_payload={"enabled": False},
        scip_payload={"enabled": False},
        graph_lookup_payload={"enabled": False},
        embeddings_payload={"enabled": False},
        feedback_payload={"enabled": False},
        multi_channel_fusion_payload={"enabled": False},
        semantic_embedding_provider_impl=None,
        semantic_cross_encoder_provider=None,
        benchmark_filter_payload={"requested": True, "applied": True},
        candidate_chunks=[{"path": "src/app.py", "lineno": 12}],
        chunk_metrics={"candidate_chunk_count": 1.0},
        chunk_semantic_rerank_payload={"enabled": False},
        topological_shield_payload={"enabled": False},
        chunk_guard_payload={"enabled": False},
    )

    apply_post_generation_runtime_to_state(
        state=state,
        post_generation_runtime=runtime,
    )

    assert state.candidates == [{"path": "src/app.py", "score": 1.0}]
    assert state.benchmark_filter_payload["applied"] is True
    assert state.candidate_chunks == [{"path": "src/app.py", "lineno": 12}]
    assert state.chunk_metrics == {"candidate_chunk_count": 1.0}
