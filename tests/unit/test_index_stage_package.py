from __future__ import annotations

import importlib


def test_index_stage_package_exports_are_lazy_and_workspace_imports_succeed() -> None:
    index_stage = importlib.import_module("ace_lite.index_stage")
    retrieval_shared = importlib.import_module("ace_lite.retrieval_shared")
    workspace_benchmark = importlib.import_module("ace_lite.workspace.benchmark")

    assert callable(index_stage.extract_terms)
    assert callable(index_stage.resolve_benchmark_candidate_filters)
    assert callable(index_stage.filter_candidate_rows)
    assert callable(index_stage.select_initial_candidates)
    assert callable(index_stage.apply_multi_channel_rrf_fusion)
    assert callable(index_stage.build_adaptive_router_payload)
    assert callable(index_stage.build_disabled_docs_payload)
    assert callable(index_stage.merge_candidate_lists)
    assert callable(index_stage.normalize_repo_path)
    assert callable(index_stage.rerank_cross_encoder_with_time_budget)
    assert callable(index_stage.resolve_repo_relative_path)
    assert callable(index_stage.rerank_rows_embeddings_with_time_budget)
    assert callable(index_stage.resolve_parallel_future)
    assert callable(retrieval_shared.normalize_candidate_ranker)
    assert callable(workspace_benchmark.run_workspace_benchmark)
