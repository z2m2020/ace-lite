from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ace_lite.index_stage.stage_runtime import (
    IndexStageRuntimeDeps,
    execute_index_stage_runtime,
)


def _unexpected(**kwargs):  # type: ignore[no-untyped-def]
    raise AssertionError(f"unexpected call: {sorted(kwargs)}")


def _make_config() -> SimpleNamespace:
    return SimpleNamespace(
        languages=["python"],
        retrieval=SimpleNamespace(
            top_k_files=4,
            exact_search_enabled=True,
            exact_search_time_budget_ms=50,
            exact_search_max_paths=8,
            candidate_relative_threshold=0.2,
            deterministic_refine_enabled=True,
            multi_channel_rrf_enabled=False,
            multi_channel_rrf_k=60,
            multi_channel_rrf_pool_cap=32,
            multi_channel_rrf_code_cap=16,
            multi_channel_rrf_docs_cap=8,
            multi_channel_rrf_memory_cap=8,
            hybrid_re2_rrf_k=40,
            policy_version="v1",
        ),
        chunking=SimpleNamespace(
            top_k=8,
            per_file_limit=2,
            token_budget=320,
            disclosure="snippet",
            snippet_max_lines=18,
            snippet_max_chars=1200,
            tokenizer_model="gpt-4o-mini",
            diversity_enabled=True,
            diversity_path_penalty=0.2,
            diversity_symbol_family_penalty=0.3,
            diversity_kind_penalty=0.1,
            diversity_locality_penalty=0.15,
            diversity_locality_window=24,
            topological_shield=SimpleNamespace(
                enabled=True,
                mode="report_only",
                max_attenuation=0.6,
                shared_parent_attenuation=0.2,
                adjacency_attenuation=0.5,
            ),
            guard=SimpleNamespace(
                enabled=False,
                mode="off",
                lambda_penalty=0.8,
                min_pool=4,
                max_pool=32,
                min_marginal_utility=0.0,
                compatibility_min_overlap=0.3,
            ),
        ),
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
    )


def _make_deps(**overrides: Any) -> IndexStageRuntimeDeps:
    return IndexStageRuntimeDeps(
        content_version="index-candidates-v1",
        bootstrap_index_runtime_fn=overrides.get("bootstrap_index_runtime_fn", _unexpected),
        build_index_stage_execution_state_fn=overrides.get(
            "build_index_stage_execution_state_fn",
            _unexpected,
        ),
        build_index_retrieval_runtime_fn=overrides.get(
            "build_index_retrieval_runtime_fn",
            _unexpected,
        ),
        run_index_candidate_generation_fn=overrides.get(
            "run_index_candidate_generation_fn",
            _unexpected,
        ),
        apply_candidate_generation_runtime_to_state_fn=overrides.get(
            "apply_candidate_generation_runtime_to_state_fn",
            _unexpected,
        ),
        resolve_repo_relative_path_fn=overrides.get(
            "resolve_repo_relative_path_fn",
            _unexpected,
        ),
        run_index_post_generation_runtime_fn=overrides.get(
            "run_index_post_generation_runtime_fn",
            _unexpected,
        ),
        apply_post_generation_runtime_to_state_fn=overrides.get(
            "apply_post_generation_runtime_to_state_fn",
            _unexpected,
        ),
        finalize_index_stage_output_from_state_fn=overrides.get(
            "finalize_index_stage_output_from_state_fn",
            _unexpected,
        ),
        normalize_fusion_mode_fn=overrides.get("normalize_fusion_mode_fn", lambda value: value),
        build_retrieval_runtime_profile_fn=overrides.get(
            "build_retrieval_runtime_profile_fn",
            lambda **kwargs: kwargs,
        ),
        bootstrap_helpers=overrides.get("bootstrap_helpers", {}),
        candidate_generation_helpers=overrides.get("candidate_generation_helpers", {}),
        post_generation_helpers=overrides.get("post_generation_helpers", {}),
        finalize_helpers=overrides.get("finalize_helpers", {}),
    )


def test_execute_index_stage_runtime_returns_cache_hit_payload() -> None:
    captured: dict[str, Any] = {}
    extract_terms_token = object()

    def fake_bootstrap_index_runtime(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SimpleNamespace(cache_hit_payload={"cached": True})

    result = execute_index_stage_runtime(
        ctx=SimpleNamespace(root="/tmp/demo", query="router", repo="demo", state={}),
        config=_make_config(),
        deps=_make_deps(
            bootstrap_index_runtime_fn=fake_bootstrap_index_runtime,
            bootstrap_helpers={"extract_retrieval_terms_fn": extract_terms_token},
        ),
    )

    assert result == {"cached": True}
    assert captured["content_version"] == "index-candidates-v1"
    assert captured["extract_retrieval_terms_fn"] is extract_terms_token


def test_execute_index_stage_runtime_wires_runtime_stages() -> None:
    captured: dict[str, Any] = {}
    state = SimpleNamespace(
        policy={"version": "v1"},
        index_hash="idx",
        terms=["router"],
        effective_files_map={"src/app.py": {"module": "src.app"}},
        effective_corpus_size=1,
        docs_policy_enabled=False,
        worktree_prior_enabled=False,
        selected_ranker="",
        candidates=[],
        memory_paths=[],
        docs_payload={"enabled": False},
        benchmark_filter_payload={"requested": True},
    )
    gather_token = object()
    refine_token = object()
    build_output_token = object()

    def fake_bootstrap_index_runtime(**kwargs):  # type: ignore[no-untyped-def]
        captured["bootstrap"] = kwargs
        return SimpleNamespace(cache_hit_payload=None)

    def fake_build_index_stage_execution_state(**kwargs):  # type: ignore[no-untyped-def]
        captured["state"] = kwargs
        return state

    def fake_build_index_retrieval_runtime(**kwargs):  # type: ignore[no-untyped-def]
        captured["retrieval"] = kwargs
        return SimpleNamespace(
            fusion_mode="rrf",
            runtime_profile=SimpleNamespace(candidate_ranker="hybrid_re2"),
            parallel_requested=True,
            parallel_time_budget_ms=75,
            rank_candidates=lambda **inner_kwargs: inner_kwargs,
        )

    def fake_run_index_candidate_generation(**kwargs):  # type: ignore[no-untyped-def]
        captured["candidate_generation"] = kwargs
        return SimpleNamespace(initial_candidates=None, docs_timing_ms=1.25, worktree_timing_ms=0.5, raw_worktree=None)

    def fake_apply_candidate_generation_runtime_to_state(**kwargs):  # type: ignore[no-untyped-def]
        captured["candidate_state"] = kwargs
        kwargs["state"].selected_ranker = "hybrid_re2"
        kwargs["state"].candidates = [{"path": "src/app.py", "score": 8.0}]

    def fake_resolve_repo_relative_path(**kwargs):  # type: ignore[no-untyped-def]
        captured["embedding_path"] = kwargs
        return "context-map/embeddings/index.json"

    def fake_run_index_post_generation_runtime(**kwargs):  # type: ignore[no-untyped-def]
        captured["post_generation"] = kwargs
        return SimpleNamespace(
            candidates=[{"path": "src/app.py", "score": 9.0}],
            second_pass_payload={"enabled": False},
            refine_pass_payload={"enabled": True},
            cochange_payload={"enabled": False},
            scip_payload={"enabled": False},
            graph_lookup_payload={"enabled": False},
            embeddings_payload={"enabled": False},
            feedback_payload={"enabled": False},
            multi_channel_fusion_payload={"enabled": False},
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
            benchmark_filter_payload={"applied": True},
            candidate_chunks=[{"path": "src/app.py", "lineno": 12}],
            chunk_metrics={"candidate_chunk_count": 1.0},
            chunk_semantic_rerank_payload={"enabled": False},
            topological_shield_payload={"enabled": False},
            chunk_guard_payload={"enabled": False},
        )

    def fake_apply_post_generation_runtime_to_state(**kwargs):  # type: ignore[no-untyped-def]
        captured["post_state"] = kwargs
        kwargs["state"].candidates = list(kwargs["post_generation_runtime"].candidates)

    def fake_finalize_index_stage_output_from_state(**kwargs):  # type: ignore[no-untyped-def]
        captured["finalize"] = kwargs
        return {"ok": True, "timings_ms": dict(kwargs["timings_ms"])}

    result = execute_index_stage_runtime(
        ctx=SimpleNamespace(root="/tmp/demo", query="router", repo="demo", state={}),
        config=_make_config(),
        deps=_make_deps(
            bootstrap_index_runtime_fn=fake_bootstrap_index_runtime,
            build_index_stage_execution_state_fn=fake_build_index_stage_execution_state,
            build_index_retrieval_runtime_fn=fake_build_index_retrieval_runtime,
            run_index_candidate_generation_fn=fake_run_index_candidate_generation,
            apply_candidate_generation_runtime_to_state_fn=fake_apply_candidate_generation_runtime_to_state,
            resolve_repo_relative_path_fn=fake_resolve_repo_relative_path,
            run_index_post_generation_runtime_fn=fake_run_index_post_generation_runtime,
            apply_post_generation_runtime_to_state_fn=fake_apply_post_generation_runtime_to_state,
            finalize_index_stage_output_from_state_fn=fake_finalize_index_stage_output_from_state,
            bootstrap_helpers={"extract_retrieval_terms_fn": object()},
            candidate_generation_helpers={"gather_initial_candidates_fn": gather_token},
            post_generation_helpers={"refine_candidate_pool_fn": refine_token},
            finalize_helpers={"build_index_stage_output_fn": build_output_token},
        ),
    )

    assert captured["state"]["bootstrap"].cache_hit_payload is None
    assert captured["retrieval"]["terms"] == ["router"]
    assert captured["candidate_generation"]["gather_initial_candidates_fn"] is gather_token
    assert captured["candidate_generation"]["parallel_requested"] is True
    assert captured["post_generation"]["refine_candidate_pool_fn"] is refine_token
    assert captured["post_generation"]["selected_ranker"] == "hybrid_re2"
    assert captured["finalize"]["build_index_stage_output_fn"] is build_output_token
    assert captured["finalize"]["policy_version"] == "v1"
    assert result["ok"] is True
