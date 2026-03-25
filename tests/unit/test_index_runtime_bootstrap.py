from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ace_lite.index_stage.embedding_runtime import EmbeddingRuntimeConfig
from ace_lite.index_stage.runtime_bootstrap import bootstrap_index_runtime
from ace_lite.pipeline.types import StageContext


def _make_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        cache_path=tmp_path / "context-map" / "index.json",
        languages=["python"],
        incremental=False,
        cochange_enabled=True,
        embedding_enabled=False,
        embedding_provider="hash",
        embedding_model="hash-v1",
        embedding_dimension=256,
        embedding_rerank_pool=0,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        feedback_enabled=False,
        feedback_path=str(tmp_path / "feedback.jsonl"),
        feedback_max_entries=200,
        feedback_boost_per_select=0.2,
        feedback_max_boost=1.0,
        feedback_decay_days=30.0,
        scip_enabled=False,
        scip_base_weight=0.0,
        retrieval=SimpleNamespace(
            retrieval_policy="general",
            policy_version="v1",
            candidate_ranker="hybrid_re2",
            top_k_files=3,
            min_candidate_score=2,
            candidate_relative_threshold=0.25,
            exact_search_enabled=True,
            deterministic_refine_enabled=True,
            exact_search_time_budget_ms=40,
            exact_search_max_paths=5,
            hybrid_re2_fusion_mode="rrf",
            hybrid_re2_rrf_k=60,
            hybrid_re2_shortlist_min=8,
            hybrid_re2_shortlist_factor=3,
            hybrid_re2_bm25_weight=1.0,
            hybrid_re2_heuristic_weight=1.0,
            hybrid_re2_coverage_weight=0.2,
            hybrid_re2_combined_scale=1.0,
            bm25_k1=1.2,
            bm25_b=0.75,
            bm25_score_scale=1.0,
            bm25_path_prior_factor=0.15,
            bm25_shortlist_min=8,
            bm25_shortlist_factor=3,
            heur_path_exact=2.0,
            heur_path_contains=1.0,
            heur_module_exact=1.2,
            heur_module_tail=0.8,
            heur_module_contains=0.4,
            heur_symbol_exact=1.8,
            heur_symbol_partial_factor=0.75,
            heur_symbol_partial_cap=1.0,
            heur_import_factor=0.4,
            heur_import_cap=1.0,
            heur_content_symbol_factor=0.2,
            heur_content_import_factor=0.1,
            heur_content_cap=1.0,
            heur_depth_base=1.0,
            heur_depth_factor=0.05,
            multi_channel_rrf_enabled=False,
            multi_channel_rrf_k=30,
            multi_channel_rrf_pool_cap=50,
            multi_channel_rrf_code_cap=20,
            multi_channel_rrf_docs_cap=10,
            multi_channel_rrf_memory_cap=10,
            adaptive_router=SimpleNamespace(
                enabled=False,
                mode="off",
                model_path="router.json",
                state_path="router-state.json",
                arm_set="default",
                online_bandit_enabled=False,
                online_bandit_experiment_enabled=False,
            ),
        ),
        chunking=SimpleNamespace(
            top_k=8,
            per_file_limit=2,
            token_budget=320,
            disclosure="snippet",
            diversity_enabled=True,
            diversity_path_penalty=0.2,
            diversity_symbol_family_penalty=0.3,
            diversity_kind_penalty=0.1,
            diversity_locality_penalty=0.15,
            diversity_locality_window=24,
            file_prior_weight=1.0,
            path_match=1.2,
            module_match=0.9,
            symbol_exact=1.8,
            symbol_partial=0.6,
            signature_match=0.4,
            reference_factor=0.2,
            reference_cap=1.0,
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
    )


def test_bootstrap_index_runtime_returns_cache_hit_payload_and_updates_ctx_state(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    files_map = {
        "src/app.py": {"module": "src.app", "language": "python"},
        "docs/guide.md": {"module": "docs.guide", "language": "markdown"},
    }
    ctx = StageContext(
        query="app routing",
        repo="demo",
        root=str(tmp_path),
        state={},
    )
    timings_ms: dict[str, float] = {}

    result = bootstrap_index_runtime(
        ctx=ctx,
        config=config,
        content_version="index-candidates-v1",
        timings_ms=timings_ms,
        mark_timing=lambda label, started_at: timings_ms.setdefault(label, 1.0),
        extract_retrieval_terms_fn=lambda **kwargs: ["app", "routing"],
        extract_memory_paths_fn=lambda **kwargs: [],
        resolve_retrieval_policy_fn=lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_candidate_cache_ttl_seconds": 30,
        },
        resolve_shadow_router_arm_fn=lambda **kwargs: {"enabled": False},
        resolve_online_bandit_gate_fn=lambda **kwargs: {"enabled": False},
        build_adaptive_router_payload_fn=lambda **kwargs: {
            "policy_name": kwargs["policy"]["name"]
        },
        load_retrieval_index_snapshot_fn=lambda **kwargs: SimpleNamespace(
            index_payload={"files": dict(files_map), "file_count": len(files_map)},
            cache_info={"cache_hit": True, "mode": "cache_only", "changed_files": 0},
            files_map=dict(files_map),
            corpus_size=len(files_map),
            index_hash="idx-1",
        ),
        resolve_benchmark_candidate_filters_fn=lambda stage_ctx: {
            "requested": True,
            "include_paths": ["src/app.py"],
            "include_globs": [],
            "exclude_paths": [],
            "exclude_globs": [],
        },
        filter_files_map_for_benchmark_fn=lambda current_files, **kwargs: (
            {"src/app.py": current_files["src/app.py"]},
            1,
        ),
        resolve_docs_policy_for_benchmark_fn=lambda **kwargs: (
            False,
            "benchmark_include_paths_code_only",
        ),
        resolve_worktree_policy_for_benchmark_fn=lambda **kwargs: (
            False,
            "benchmark_filter_explicit_scope",
        ),
        resolve_embedding_runtime_config_fn=lambda **kwargs: EmbeddingRuntimeConfig(
            provider="hash",
            model="hash-v1",
            dimension=256,
            normalized_fields=(),
            notes=(),
        ),
        resolve_repo_relative_path_fn=lambda **kwargs: str(kwargs["configured_path"]),
        default_index_candidate_cache_path_fn=lambda **kwargs: (
            tmp_path / "context-map" / "index-candidates.json"
        ),
        build_index_candidate_cache_key_fn=lambda **kwargs: "cache-key",
        load_cached_index_candidates_checked_fn=lambda **kwargs: {
            "candidate_files": [],
            "metadata": {},
        },
        build_disabled_worktree_prior_fn=lambda **kwargs: {
            "enabled": False,
            "reason": kwargs["reason"],
        },
        refresh_cached_index_candidate_payload_fn=lambda **kwargs: {
            "candidate_files": [],
            "metadata": {"timings_ms": dict(kwargs["timings_ms"])},
        },
        attach_index_candidate_cache_info_fn=lambda **kwargs: {
            **kwargs["payload"],
            "candidate_cache": kwargs["cache_info"],
        },
    )

    assert result.cache_hit_payload is not None
    assert result.cache_hit_payload["candidate_cache"]["hit"] is True
    assert result.index_candidate_cache_key == "cache-key"
    assert result.index_candidate_cache_required_meta["content_version"] == (
        "index-candidates-v1"
    )
    assert (
        result.index_candidate_cache_required_meta["chunk_cache_contract_schema_version"]
        == ""
    )
    assert (
        result.index_candidate_cache_required_meta["chunk_cache_contract_fingerprint"]
        == ""
    )
    assert result.benchmark_filter_payload["files_map_applied"] is True
    assert ctx.state["__policy"]["name"] == "general"
    assert ctx.state["__index_files"] == {
        "src/app.py": {"module": "src.app", "language": "python"}
    }
    assert ctx.state["__vcs_worktree"] == {
        "enabled": False,
        "reason": "benchmark_filter_explicit_scope",
    }


def test_bootstrap_index_runtime_attaches_chunk_cache_contract_meta(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    ctx = StageContext(
        query="app routing",
        repo="demo",
        root=str(tmp_path),
        state={},
    )
    timings_ms: dict[str, float] = {}

    result = bootstrap_index_runtime(
        ctx=ctx,
        config=config,
        content_version="index-candidates-v1",
        timings_ms=timings_ms,
        mark_timing=lambda label, started_at: timings_ms.setdefault(label, 1.0),
        extract_retrieval_terms_fn=lambda **kwargs: ["app", "routing"],
        extract_memory_paths_fn=lambda **kwargs: [],
        resolve_retrieval_policy_fn=lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_candidate_cache_ttl_seconds": 30,
        },
        resolve_shadow_router_arm_fn=lambda **kwargs: {"enabled": False},
        resolve_online_bandit_gate_fn=lambda **kwargs: {"enabled": False},
        build_adaptive_router_payload_fn=lambda **kwargs: {
            "policy_name": kwargs["policy"]["name"]
        },
        load_retrieval_index_snapshot_fn=lambda **kwargs: SimpleNamespace(
            index_payload={
                "files": {"src/app.py": {"module": "src.app", "language": "python"}},
                "file_count": 1,
                "chunk_cache_contract": {
                    "schema_version": "chunk-cache-contract-v1",
                    "fingerprint": "chunk-fp",
                    "file_count": 1,
                    "chunk_count": 2,
                },
            },
            cache_info={"cache_hit": True, "mode": "cache_only", "changed_files": 0},
            files_map={"src/app.py": {"module": "src.app", "language": "python"}},
            corpus_size=1,
            index_hash="idx-1",
        ),
        resolve_benchmark_candidate_filters_fn=lambda stage_ctx: {
            "requested": False,
            "include_paths": [],
            "include_globs": [],
            "exclude_paths": [],
            "exclude_globs": [],
        },
        filter_files_map_for_benchmark_fn=lambda current_files, **kwargs: (
            current_files,
            0,
        ),
        resolve_docs_policy_for_benchmark_fn=lambda **kwargs: (False, "disabled"),
        resolve_worktree_policy_for_benchmark_fn=lambda **kwargs: (True, "enabled"),
        resolve_embedding_runtime_config_fn=lambda **kwargs: EmbeddingRuntimeConfig(
            provider="hash",
            model="hash-v1",
            dimension=256,
            normalized_fields=(),
            notes=(),
        ),
        resolve_repo_relative_path_fn=lambda **kwargs: str(kwargs["configured_path"]),
        default_index_candidate_cache_path_fn=lambda **kwargs: (
            tmp_path / "context-map" / "index-candidates.json"
        ),
        build_index_candidate_cache_key_fn=lambda **kwargs: "cache-key",
        load_cached_index_candidates_checked_fn=lambda **kwargs: None,
        build_disabled_worktree_prior_fn=lambda **kwargs: {
            "enabled": False,
            "reason": kwargs["reason"],
        },
        refresh_cached_index_candidate_payload_fn=lambda **kwargs: kwargs["payload"],
        attach_index_candidate_cache_info_fn=lambda **kwargs: kwargs["payload"],
    )

    assert (
        result.index_candidate_cache_required_meta["chunk_cache_contract_schema_version"]
        == "chunk-cache-contract-v1"
    )
    assert (
        result.index_candidate_cache_required_meta["chunk_cache_contract_fingerprint"]
        == "chunk-fp"
    )
