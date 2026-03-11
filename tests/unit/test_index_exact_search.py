from __future__ import annotations

from pathlib import Path

from ace_lite.exact_search import ExactSearchResult
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult
from ace_lite.index_stage.structural_rerank import StructuralRerankResult
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.stages.index import IndexStageConfig, run_index
from ace_lite.pipeline.types import StageContext
from ace_lite.retrieval_shared import RetrievalIndexSnapshot


def test_index_stage_exact_search_injects_deep_candidate(monkeypatch, tmp_path: Path) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    deep_path = "src/a/b/c/d/e/f/g/bar.py"
    shallow_path = "src/foo.py"

    (tmp_path / Path(deep_path)).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / Path(deep_path)).write_text("def needle():\n    return 1\n", encoding="utf-8")
    (tmp_path / Path(shallow_path)).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / Path(shallow_path)).write_text("def ok():\n    return 0\n", encoding="utf-8")

    files_map = {
        shallow_path: {"module": "src.foo", "language": "python", "symbols": [], "imports": []},
        deep_path: {"module": "src.a.b.c.d.e.f.g.bar", "language": "python", "symbols": [], "imports": []},
    }

    def fake_load_retrieval_index_snapshot(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return RetrievalIndexSnapshot(
            index_payload={
                "files": dict(files_map),
                "file_count": len(files_map),
                "indexed_at": "test",
                "languages_covered": ["python"],
                "parser": {},
            },
            cache_info={"cache_hit": True, "mode": "test", "changed_files": 0},
            files_map=dict(files_map),
            corpus_size=len(files_map),
            index_hash="test-hash",
        )

    def fake_run_exact_search_ripgrep(*, root, query, include_globs, timeout_ms):  # type: ignore[no-untyped-def]
        return ExactSearchResult(
            hits_by_path={deep_path: 5},
            reason="ok",
            timed_out=False,
            returncode=0,
            elapsed_ms=1.0,
            stderr="",
        )

    def fake_collect_docs_signals(*, root, query, terms, enabled, intent_weight, max_sections):  # type: ignore[no-untyped-def]
        return {"enabled": False, "reason": "disabled", "elapsed_ms": 0.0, "section_count": 0}

    def fake_apply_candidate_priors(  # type: ignore[no-untyped-def]
        *, candidates, files_map, docs_payload, worktree_prior, policy, top_k_files, query, query_terms
    ):
        return candidates, {}

    def fake_apply_structural_rerank(  # type: ignore[no-untyped-def]
        *,
        root,
        files_map,
        candidates,
        memory_paths,
        terms,
        policy,
        cochange_enabled,
        cochange_cache_path,
        cochange_lookback_commits,
        cochange_half_life_days,
        cochange_neighbor_cap,
        top_k_files,
        cochange_top_neighbors,
        cochange_boost_weight,
        cochange_min_neighbor_score,
        cochange_max_boost,
        scip_enabled,
        scip_index_path,
        scip_provider,
        scip_generate_fallback,
        mark_timing,
    ) -> StructuralRerankResult:
        return StructuralRerankResult(
            candidates=list(candidates),
            cochange_payload={"enabled": False, "cache_mode": "disabled", "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False, "edge_count": 0},
            graph_lookup_payload={"enabled": False, "reason": "disabled"},
        )

    def fake_apply_chunk_selection(  # type: ignore[no-untyped-def]
        *,
        root,
        query,
        files_map,
        candidates,
        terms,
        top_k_files,
        chunk_top_k,
        chunk_per_file_limit,
        chunk_token_budget,
        chunk_guard_enabled,
        chunk_guard_mode,
        chunk_guard_lambda_penalty,
        chunk_guard_min_pool,
        chunk_guard_max_pool,
        chunk_guard_min_marginal_utility,
        chunk_guard_compatibility_min_overlap,
        chunk_disclosure,
        chunk_snippet_max_lines,
        chunk_snippet_max_chars,
        policy,
        tokenizer_model,
        chunk_diversity_enabled,
        chunk_diversity_path_penalty,
        chunk_diversity_symbol_family_penalty,
        chunk_diversity_kind_penalty,
        chunk_diversity_locality_penalty,
        chunk_diversity_locality_window,
        chunk_topological_shield_enabled,
        chunk_topological_shield_mode,
        chunk_topological_shield_max_attenuation,
        chunk_topological_shield_shared_parent_attenuation,
        chunk_topological_shield_adjacency_attenuation,
        index_hash,
        embedding_enabled,
        embedding_lexical_weight,
        embedding_semantic_weight,
        embedding_min_similarity,
        embeddings_payload,
        semantic_embedding_provider_impl,
        semantic_cross_encoder_provider,
        mark_timing,
        rerank_rows_embeddings_with_time_budget,
        rerank_rows_cross_encoder_with_time_budget,
    ) -> ChunkSelectionResult:
        return ChunkSelectionResult(
            candidate_chunks=[],
            chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        )

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        fake_load_retrieval_index_snapshot,
    )
    monkeypatch.setattr(index_stage, "run_exact_search_ripgrep", fake_run_exact_search_ripgrep)
    monkeypatch.setattr(index_stage, "collect_docs_signals", fake_collect_docs_signals)
    monkeypatch.setattr(index_stage, "apply_candidate_priors", fake_apply_candidate_priors)
    monkeypatch.setattr(index_stage, "apply_structural_rerank", fake_apply_structural_rerank)
    monkeypatch.setattr(index_stage, "apply_chunk_selection", fake_apply_chunk_selection)

    orchestrator_config = OrchestratorConfig.model_validate(
        {
            "index": {
                "cache_path": str(tmp_path / "context-map" / "index.json"),
                "languages": ["python"],
                "incremental": False,
            },
            "retrieval": {
                "top_k_files": 8,
                "min_candidate_score": 1,
                "candidate_ranker": "heuristic",
                "exact_search_enabled": True,
                "exact_search_time_budget_ms": 20,
                "exact_search_max_paths": 5,
            },
            "repomap": {"enabled": False},
            "cochange": {"enabled": False},
            "embeddings": {"enabled": False},
            "lsp": {"enabled": False},
            "scip": {"enabled": False},
        }
    )

    config = IndexStageConfig.from_orchestrator_config(
        config=orchestrator_config,
        tokenizer_model="gpt-4o-mini",
        cochange_neighbor_cap=1,
        cochange_min_neighbor_score=0.0,
        cochange_max_boost=0.0,
    )
    ctx = StageContext(query="needle", repo="demo", root=str(tmp_path))
    payload = run_index(ctx=ctx, config=config)

    candidate_paths = [str(item.get("path") or "") for item in payload.get("candidate_files", [])]
    assert deep_path in candidate_paths

    exact = payload["candidate_ranking"]["exact_search"]
    assert exact["enabled"] is True
    assert exact["applied"] is True
    assert exact["injected_count"] == 1
