from __future__ import annotations

import importlib


def test_index_stage_package_exports_are_lazy_and_workspace_imports_succeed() -> None:
    index_stage = importlib.import_module("ace_lite.index_stage")
    retrieval_shared = importlib.import_module("ace_lite.retrieval_shared")
    workspace_benchmark = importlib.import_module("ace_lite.workspace.benchmark")

    assert callable(index_stage.extract_terms)
    assert callable(index_stage.select_initial_candidates)
    assert callable(retrieval_shared.normalize_candidate_ranker)
    assert callable(workspace_benchmark.run_workspace_benchmark)
