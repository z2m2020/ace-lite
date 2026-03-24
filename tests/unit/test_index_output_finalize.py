from __future__ import annotations

from pathlib import Path
from typing import Any
from types import SimpleNamespace

from ace_lite.index_stage.output_finalize import finalize_index_stage_output
from ace_lite.index_stage.output_finalize import finalize_index_stage_output_from_state


def test_finalize_index_stage_output_attaches_filters_and_cache_metadata() -> None:
    captured: dict[str, Any] = {}

    def fake_build_index_stage_output(**kwargs):  # type: ignore[no-untyped-def]
        captured["build"] = kwargs
        return {"repo": kwargs["repo"], "candidate_files": [], "metadata": {}}

    def fake_clone_index_candidate_payload(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        captured["cloned_payload"] = dict(payload)
        return {"cloned": True, **payload}

    def fake_store_cached_index_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured["store"] = kwargs
        return True

    def fake_attach_index_candidate_cache_info(**kwargs):  # type: ignore[no-untyped-def]
        captured["attach"] = kwargs
        return {
            **kwargs["payload"],
            "candidate_cache": kwargs["cache_info"],
        }

    cache_info = {"hit": False, "store_written": False}
    payload = finalize_index_stage_output(
        repo="demo",
        root="/tmp/demo",
        terms=["router"],
        memory_paths=["docs/guide.md"],
        index_hash="idx",
        index_data={"file_count": 1},
        cache_info={"cache_hit": False},
        requested_ranker="bm25",
        selected_ranker="bm25",
        ranker_fallbacks=[],
        corpus_size=1,
        min_score_used=2,
        fusion_mode="rrf",
        hybrid_re2_rrf_k=60,
        top_k_files=4,
        candidate_relative_threshold=0.25,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=320,
        chunk_disclosure="snippet",
        candidates=[{"path": "src/app.py", "score": 1.0}],
        candidate_chunks=[],
        chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
        exact_search_payload={"enabled": False},
        docs_payload={"enabled": False},
        worktree_prior={"enabled": False},
        parallel_payload={"enabled": False},
        prior_payload={"enabled": False},
        graph_lookup_payload={"enabled": False},
        cochange_payload={"enabled": False},
        scip_payload={"enabled": False},
        embeddings_payload={"enabled": False},
        feedback_payload={"enabled": False},
        multi_channel_fusion_payload={"enabled": False},
        retrieval_refinement_payload={"enabled": True, "focus_paths": ["src/app.py"]},
        second_pass_payload={"enabled": False},
        refine_pass_payload={"enabled": False},
        chunk_semantic_rerank_payload={"enabled": False},
        topological_shield_payload={"enabled": False},
        chunk_guard_payload={"enabled": False},
        adaptive_router_payload={"enabled": False},
        policy_name="general",
        policy_version="v1",
        timings_ms={"index_cache_load": 1.0},
        benchmark_filter_payload={"requested": True, "include_paths": ["src/app.py"]},
        index_candidate_cache_path="context-map/index_candidates/cache.db",
        index_candidate_cache_key="cache-key",
        index_candidate_cache_ttl_seconds=1800,
        index_candidate_cache_required_meta={"policy_name": "general"},
        index_candidate_cache=cache_info,
        query="router",
        build_index_stage_output_fn=fake_build_index_stage_output,
        clone_index_candidate_payload_fn=fake_clone_index_candidate_payload,
        store_cached_index_candidates_fn=fake_store_cached_index_candidates,
        attach_index_candidate_cache_info_fn=fake_attach_index_candidate_cache_info,
    )

    assert captured["build"]["memory_paths"] == ["docs/guide.md"]
    assert payload["benchmark_filters"]["include_paths"] == ["src/app.py"]
    assert payload["retrieval_refinement"]["focus_paths"] == ["src/app.py"]
    assert captured["store"]["meta"]["query"] == "router"
    assert captured["store"]["meta"]["ttl_seconds"] == 1800
    assert captured["store"]["meta"]["trust_class"] == "exact"
    assert captured["cloned_payload"]["benchmark_filters"]["requested"] is True
    assert cache_info["store_written"] is True
    assert payload["candidate_cache"]["store_written"] is True


def test_finalize_index_stage_output_from_state_uses_state_contract() -> None:
    captured: dict[str, Any] = {}

    def fake_build_index_stage_output(**kwargs):  # type: ignore[no-untyped-def]
        captured["build"] = kwargs
        return {"repo": kwargs["repo"], "candidate_files": [], "metadata": {}}

    def fake_clone_index_candidate_payload(payload: dict[str, Any]) -> dict[str, Any]:
        captured["cloned_payload"] = dict(payload)
        return dict(payload)

    def fake_store_cached_index_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured["store"] = kwargs
        return False

    def fake_attach_index_candidate_cache_info(**kwargs):  # type: ignore[no-untyped-def]
        captured["attach"] = kwargs
        return {**kwargs["payload"], "candidate_cache": kwargs["cache_info"]}

    state = SimpleNamespace(
        terms=["router"],
        memory_paths=["docs/guide.md"],
        index_hash="idx",
        index_data={"file_count": 1},
        cache_info={"cache_hit": False},
        requested_ranker="bm25",
        selected_ranker="bm25",
        ranker_fallbacks=[],
        corpus_size=1,
        min_score_used=2,
        candidates=[{"path": "src/app.py", "score": 1.0}],
        candidate_chunks=[],
        chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
        exact_search_payload={"enabled": False},
        docs_payload={"enabled": False},
        worktree_prior={"enabled": False},
        parallel_payload={"enabled": False},
        prior_payload={"enabled": False},
        graph_lookup_payload={"enabled": False},
        cochange_payload={"enabled": False},
        scip_payload={"enabled": False},
        embeddings_payload={"enabled": False},
        feedback_payload={"enabled": False},
        multi_channel_fusion_payload={"enabled": False},
        retrieval_refinement_payload={"enabled": True, "focus_paths": ["src/app.py"]},
        second_pass_payload={"enabled": False},
        refine_pass_payload={"enabled": False},
        chunk_semantic_rerank_payload={"enabled": False},
        topological_shield_payload={"enabled": False},
        chunk_guard_payload={"enabled": False},
        adaptive_router_payload={"enabled": False},
        policy={"name": "general", "version": "v1"},
        benchmark_filter_payload={"requested": True, "include_paths": ["src/app.py"]},
        index_candidate_cache_path=Path("context-map/index_candidates/cache.db"),
        index_candidate_cache_key="cache-key",
        index_candidate_cache_ttl_seconds=1800,
        index_candidate_cache_required_meta={"policy_name": "general"},
        index_candidate_cache={"hit": False, "store_written": False},
    )

    payload = finalize_index_stage_output_from_state(
        state=state,
        repo="demo",
        root="/tmp/demo",
        fusion_mode="rrf",
        hybrid_re2_rrf_k=60,
        top_k_files=4,
        candidate_relative_threshold=0.25,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=320,
        chunk_disclosure="snippet",
        timings_ms={"index_cache_load": 1.0},
        query="router",
        policy_version="v1",
        build_index_stage_output_fn=fake_build_index_stage_output,
        clone_index_candidate_payload_fn=fake_clone_index_candidate_payload,
        store_cached_index_candidates_fn=fake_store_cached_index_candidates,
        attach_index_candidate_cache_info_fn=fake_attach_index_candidate_cache_info,
    )

    assert captured["build"]["memory_paths"] == ["docs/guide.md"]
    assert captured["build"]["top_k_files"] == 4
    assert captured["cloned_payload"]["retrieval_refinement"]["focus_paths"] == [
        "src/app.py"
    ]
    assert captured["store"]["cache_path"] == Path("context-map/index_candidates/cache.db")
    assert payload["candidate_cache"]["store_written"] is False
