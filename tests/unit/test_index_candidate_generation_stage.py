from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ace_lite.index_stage.candidate_fusion import CandidateFusionResult
from ace_lite.index_stage.candidate_generation import InitialCandidateGenerationResult
from ace_lite.index_stage.candidate_postprocess import CandidatePostprocessResult
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult
from ace_lite.index_stage.semantic_candidate_rerank import (
    SemanticCandidateRerankResult,
)
from ace_lite.index_stage.structural_rerank import StructuralRerankResult
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.stages.index import IndexStageConfig
from ace_lite.pipeline.stages.index import run_index
from ace_lite.pipeline.types import StageContext
from ace_lite.retrieval_shared import RetrievalIndexSnapshot


def _make_snapshot(files_map: dict[str, dict[str, Any]]) -> RetrievalIndexSnapshot:
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


def _make_config(
    tmp_path: Path,
    *,
    retrieval_overrides: dict[str, Any] | None = None,
    cochange_enabled: bool = False,
) -> IndexStageConfig:
    retrieval = {
        "top_k_files": 3,
        "min_candidate_score": 2,
        "candidate_ranker": "hybrid_re2",
        "exact_search_enabled": True,
        "exact_search_time_budget_ms": 40,
        "exact_search_max_paths": 5,
    }
    if retrieval_overrides:
        retrieval.update(retrieval_overrides)
    orchestrator_config = OrchestratorConfig.model_validate(
        {
            "index": {
                "cache_path": str(tmp_path / "context-map" / "index.json"),
                "languages": ["python"],
                "incremental": False,
            },
            "retrieval": retrieval,
            "repomap": {"enabled": False},
            "cochange": {"enabled": bool(cochange_enabled)},
            "embeddings": {"enabled": False},
            "lsp": {"enabled": False},
            "scip": {"enabled": False},
        }
    )
    return IndexStageConfig.from_orchestrator_config(
        config=orchestrator_config,
        tokenizer_model="gpt-4o-mini",
        cochange_neighbor_cap=1,
        cochange_min_neighbor_score=0.0,
        cochange_max_boost=0.0,
    )


def _base_worktree_prior() -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": "disabled",
        "changed_count": 0,
        "changed_paths": [],
        "seed_paths": [],
        "reverse_added_count": 0,
        "state_hash": "",
        "raw": {
            "enabled": False,
            "reason": "disabled",
            "changed_count": 0,
            "entries": [],
            "truncated": False,
            "error": "",
        },
    }


def _stub_pipeline_after_generation(monkeypatch, index_stage) -> None:  # type: ignore[no-untyped-def]
    def fake_postprocess_candidates(*, candidates, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return CandidatePostprocessResult(
            candidates=list(candidates),
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 0,
                "candidate_count_after": 0,
                "max_passes": 1,
            },
        )

    def fake_apply_structural_rerank(*, candidates, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return StructuralRerankResult(
            candidates=list(candidates),
            cochange_payload={"enabled": False, "cache_mode": "disabled"},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={"enabled": False, "reason": "disabled"},
        )

    def fake_apply_semantic_candidate_rerank(  # type: ignore[no-untyped-def]
        *, candidates, **kwargs
    ):
        _ = kwargs
        return SemanticCandidateRerankResult(
            candidates=list(candidates),
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        )

    def fake_select_index_chunks(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return ChunkSelectionResult(
            candidate_chunks=[],
            chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        )

    monkeypatch.setattr(index_stage, "postprocess_candidates", fake_postprocess_candidates)
    monkeypatch.setattr(index_stage, "apply_structural_rerank", fake_apply_structural_rerank)
    monkeypatch.setattr(
        index_stage,
        "apply_semantic_candidate_rerank",
        fake_apply_semantic_candidate_rerank,
    )
    monkeypatch.setattr(index_stage, "select_index_chunks", fake_select_index_chunks)


def _stub_chunk_selection(monkeypatch, index_stage) -> None:  # type: ignore[no-untyped-def]
    def fake_select_index_chunks(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return ChunkSelectionResult(
            candidate_chunks=[],
            chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        )

    monkeypatch.setattr(index_stage, "select_index_chunks", fake_select_index_chunks)


def test_run_index_delegates_initial_candidate_generation(monkeypatch, tmp_path: Path) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
        "src/beta.py": {"module": "src.beta", "language": "python"},
    }
    captured: dict[str, Any] = {}

    def fake_gather_initial_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="heuristic",
            ranker_fallbacks=["tiny_corpus"],
            min_score_used=1,
            candidates=[
                {"path": "src/alpha.py", "score": 7.0},
                {"path": "src/beta.py", "score": 5.0},
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.75,
            worktree_elapsed_ms=0.25,
            raw_worktree=None,
        )

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["router", "cache"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(index_stage, "gather_initial_candidates", fake_gather_initial_candidates)
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(query="router cache", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert captured["terms"] == ["router", "cache"]
    assert captured["corpus_size"] == 2
    assert captured["top_k_files"] == 3
    assert captured["runtime_profile"].candidate_ranker == "hybrid_re2"
    assert "*.py" in captured["exact_search_include_globs"]
    assert payload["candidate_ranking"]["requested"] == "hybrid_re2"
    assert payload["candidate_ranking"]["selected"] == "heuristic"
    assert payload["candidate_ranking"]["fallbacks"] == ["tiny_corpus"]
    assert payload["candidate_ranking"]["min_score_used"] == 1
    assert payload["metadata"]["timings_ms"]["docs_signals"] == 0.75
    assert payload["metadata"]["timings_ms"]["worktree_prior"] == 0.25


def test_run_index_disables_worktree_prior_for_explicit_benchmark_scope(
    monkeypatch, tmp_path: Path
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/runtime.py": {"module": "src.runtime", "language": "python"},
        "tests/test_runtime.py": {"module": "tests.test_runtime", "language": "python"},
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["runtime", "mcp"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )

    def fake_gather_initial_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return InitialCandidateGenerationResult(
            requested_ranker="heuristic",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[{"path": "src/runtime.py", "score": 5.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        )

    monkeypatch.setattr(index_stage, "gather_initial_candidates", fake_gather_initial_candidates)
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(
            query="runtime mcp",
            repo="demo",
            root=str(tmp_path),
            state={
                "benchmark_filters": {
                    "include_paths": ["src/runtime.py", "tests/test_runtime.py"],
                }
            },
        ),
        config=_make_config(tmp_path, cochange_enabled=True),
    )

    assert captured["worktree_prior_enabled"] is False
    assert payload["benchmark_filters"]["worktree_policy_enabled"] is False
    assert payload["benchmark_filters"]["worktree_policy_reason"] == (
        "benchmark_filter_explicit_scope"
    )


def test_run_index_preserves_candidate_generation_candidate_order(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/first.py": {"module": "src.first", "language": "python"},
        "src/second.py": {"module": "src.second", "language": "python"},
        "src/third.py": {"module": "src.third", "language": "python"},
    }

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["needle"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="bm25_lite",
            selected_ranker="heuristic",
            ranker_fallbacks=["empty_retrieval"],
            min_score_used=2,
            candidates=[
                {"path": "src/second.py", "score": 9.0},
                {"path": "src/first.py", "score": 8.0},
                {"path": "src/third.py", "score": 7.0},
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(query="needle", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    candidate_paths = [item["path"] for item in payload["candidate_files"]]
    assert candidate_paths == ["src/second.py", "src/first.py", "src/third.py"]
    assert payload["candidate_ranking"]["requested"] == "bm25_lite"
    assert payload["candidate_ranking"]["selected"] == "heuristic"
    assert payload["candidate_ranking"]["fallbacks"] == ["empty_retrieval"]


def test_run_index_delegates_candidate_fusion_pool(monkeypatch, tmp_path: Path) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
        "src/beta.py": {"module": "src.beta", "language": "python"},
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["router"],
    )
    monkeypatch.setattr(
        index_stage,
        "extract_memory_paths",
        lambda **kwargs: ["docs/guide.md"],
    )
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v2",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="heuristic",
            ranker_fallbacks=["tiny_corpus"],
            min_score_used=1,
            candidates=[{"path": "src/alpha.py", "score": 5.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )

    def fake_refine_candidate_pool(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return CandidateFusionResult(
            candidates=[{"path": "src/alpha.py", "score": 5.0}],
            second_pass_payload={
                "triggered": True,
                "applied": False,
                "reason": "low_candidate_count",
                "retry_ranker": "hybrid_re2",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": True,
                "triggered": True,
                "applied": False,
                "reason": "low_candidate_count",
                "retry_ranker": "hybrid_re2",
                "candidate_count_before": 1,
                "candidate_count_after": 1,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "cache_mode": "disabled"},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={"enabled": False, "reason": "disabled"},
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": True,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 60,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        )

    monkeypatch.setattr(index_stage, "refine_candidate_pool", fake_refine_candidate_pool)
    _stub_chunk_selection(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(query="router", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert captured["selected_ranker"] == "heuristic"
    assert captured["memory_paths"] == ["docs/guide.md"]
    assert captured["docs_payload"]["enabled"] is False
    assert captured["top_k_files"] == 3
    assert captured["multi_channel_rrf_enabled"] is True
    assert payload["candidate_ranking"]["second_pass"]["reason"] == "low_candidate_count"
    assert payload["candidate_ranking"]["refine_pass"]["retry_ranker"] == "hybrid_re2"


def test_run_index_preserves_candidate_fusion_payloads(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
        "src/beta.py": {"module": "src.beta", "language": "python"},
    }

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["router"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v2",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="heuristic",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[
                {"path": "src/beta.py", "score": 6.0},
                {"path": "src/alpha.py", "score": 5.0},
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "refine_candidate_pool",
        lambda **kwargs: CandidateFusionResult(
            candidates=[
                {"path": "src/beta.py", "score": 6.0},
                {"path": "src/alpha.py", "score": 5.0},
            ],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 0,
                "candidate_count_after": 0,
                "max_passes": 1,
            },
            cochange_payload={"enabled": True, "neighbors_added": 2},
            scip_payload={"enabled": True, "loaded": True},
            graph_lookup_payload={
                "enabled": True,
                "boosted_count": 1,
                "query_hit_paths": 1,
            },
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": True,
                "reason": "applied",
                "boosted_candidate_count": 1,
                "boosted_unique_paths": 1,
                "matched_event_count": 1,
                "event_count": 2,
            },
            multi_channel_fusion_payload={
                "enabled": True,
                "applied": True,
                "reason": "applied",
                "rrf_k": 60,
                "caps": {"pool": 8, "code": 4, "docs": 2, "memory": 2},
                "channels": {
                    "code": {"count": 2, "cap": 4, "top": ["src/beta.py"]},
                    "docs": {"count": 0, "cap": 2, "top": []},
                    "memory": {"count": 0, "cap": 2, "top": []},
                },
                "fused": {"scored_count": 2, "pool_size": 2, "top": ["src/beta.py"]},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        ),
    )
    _stub_chunk_selection(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(query="router", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert [item["path"] for item in payload["candidate_files"]] == [
        "src/beta.py",
        "src/alpha.py",
    ]
    assert payload["cochange"]["neighbors_added"] == 2
    assert payload["scip"]["loaded"] is True
    assert payload["graph_lookup"]["boosted_count"] == 1
    assert payload["feedback"]["boosted_candidate_count"] == 1
    assert payload["multi_channel_fusion"]["applied"] is True


def test_run_index_delegates_final_output_assembly(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
        "src/beta.py": {"module": "src.beta", "language": "python"},
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["router"],
    )
    monkeypatch.setattr(
        index_stage,
        "extract_memory_paths",
        lambda **kwargs: ["docs/guide.md", "src/alpha.py"],
    )
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="heuristic",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[{"path": "src/alpha.py", "score": 6.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=1.25,
            worktree_elapsed_ms=0.5,
            raw_worktree=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "refine_candidate_pool",
        lambda **kwargs: CandidateFusionResult(
            candidates=[{"path": "src/alpha.py", "score": 6.0}],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 0,
                "candidate_count_after": 0,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={"enabled": False, "boosted_count": 0, "query_hit_paths": 0},
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": False,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 0,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        ),
    )
    _stub_chunk_selection(monkeypatch, index_stage)

    def fake_build_index_stage_output(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {
            "repo": kwargs["repo"],
            "targets": ["docs/guide.md", "src/alpha.py"],
            "candidate_files": [],
            "metadata": {"timings_ms": kwargs["timings_ms"]},
        }

    monkeypatch.setattr(index_stage, "build_index_stage_output", fake_build_index_stage_output)

    payload = run_index(
        ctx=StageContext(query="router", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert captured["memory_paths"] == ["docs/guide.md", "src/alpha.py"]
    assert captured["candidates"] == [{"path": "src/alpha.py", "score": 6.0}]
    assert captured["candidate_chunks"] == []
    assert captured["chunk_metrics"]["candidate_chunk_count"] == 0.0
    assert captured["timings_ms"]["docs_signals"] == 1.25
    assert captured["timings_ms"]["worktree_prior"] == 0.5
    assert payload["targets"] == ["docs/guide.md", "src/alpha.py"]


def test_run_index_emits_shadow_router_choice_in_shadow_mode(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import json
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
    }
    model_path = tmp_path / "context-map" / "router" / "model.json"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        json.dumps(
            {
                "arm_set": "retrieval_policy_shadow",
                "policy_arms": {
                    "feature": {"arm_id": "feature_graph", "confidence": 0.91}
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["implement", "helper"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "feature",
            "version": "v1",
            "docs_enabled": False,
            "embedding_enabled": True,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="hybrid_re2",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[{"path": "src/alpha.py", "score": 6.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(query="implement helper", repo="demo", root=str(tmp_path)),
        config=_make_config(
            tmp_path,
            retrieval_overrides={
                "retrieval_policy": "feature",
                "adaptive_router_enabled": True,
                "adaptive_router_mode": "shadow",
                "adaptive_router_model_path": "context-map/router/model.json",
                "adaptive_router_arm_set": "retrieval_policy_shadow",
            },
        ),
    )

    assert payload["adaptive_router"]["arm_id"] == "feature"
    assert payload["adaptive_router"]["shadow_arm_id"] == "feature_graph"
    assert payload["adaptive_router"]["shadow_confidence"] == 0.91
    assert payload["metadata"]["router_shadow_arm_id"] == "feature_graph"


def test_run_index_shadow_mode_preserves_executed_outputs_until_explicitly_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import json
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
        "src/beta.py": {"module": "src.beta", "language": "python"},
    }
    model_path = tmp_path / "context-map" / "router" / "model.json"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        json.dumps(
            {
                "arm_set": "retrieval_policy_shadow",
                "policy_arms": {
                    "feature": {"arm_id": "feature_graph", "confidence": 0.91}
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["implement", "helper"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "feature",
            "version": "v1",
            "docs_enabled": False,
            "embedding_enabled": True,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="hybrid_re2",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[
                {"path": "src/beta.py", "score": 7.0},
                {"path": "src/alpha.py", "score": 6.0},
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    observe_payload = run_index(
        ctx=StageContext(query="implement helper", repo="demo", root=str(tmp_path)),
        config=_make_config(
            tmp_path,
            retrieval_overrides={
                "retrieval_policy": "feature",
                "adaptive_router_enabled": True,
                "adaptive_router_mode": "observe",
                "adaptive_router_model_path": "context-map/router/model.json",
                "adaptive_router_arm_set": "retrieval_policy_shadow",
            },
        ),
    )
    shadow_payload = run_index(
        ctx=StageContext(query="implement helper", repo="demo", root=str(tmp_path)),
        config=_make_config(
            tmp_path,
            retrieval_overrides={
                "retrieval_policy": "feature",
                "adaptive_router_enabled": True,
                "adaptive_router_mode": "shadow",
                "adaptive_router_model_path": "context-map/router/model.json",
                "adaptive_router_arm_set": "retrieval_policy_shadow",
            },
        ),
    )

    assert observe_payload["candidate_files"] == shadow_payload["candidate_files"]
    assert (
        observe_payload["metadata"]["selection_fingerprint"]
        == shadow_payload["metadata"]["selection_fingerprint"]
    )
    assert observe_payload["candidate_ranking"]["selected"] == "hybrid_re2"
    assert shadow_payload["candidate_ranking"]["selected"] == "hybrid_re2"
    assert observe_payload["adaptive_router"]["arm_id"] == "feature"
    assert shadow_payload["adaptive_router"]["arm_id"] == "feature"
    assert observe_payload["adaptive_router"]["shadow_arm_id"] == ""
    assert shadow_payload["adaptive_router"]["shadow_arm_id"] == "feature_graph"


def test_run_index_delegates_chunk_selection_runtime_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["router"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="heuristic",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[{"path": "src/alpha.py", "score": 6.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "refine_candidate_pool",
        lambda **kwargs: CandidateFusionResult(
            candidates=[{"path": "src/alpha.py", "score": 6.0}],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 0,
                "candidate_count_after": 0,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={"enabled": False, "boosted_count": 0, "query_hit_paths": 0},
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": False,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 0,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        ),
    )

    def fake_select_index_chunks(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return ChunkSelectionResult(
            candidate_chunks=[],
            chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        )

    monkeypatch.setattr(index_stage, "select_index_chunks", fake_select_index_chunks)
    monkeypatch.setattr(
        index_stage,
        "build_index_stage_output",
        lambda **kwargs: {"repo": kwargs["repo"], "targets": [], "candidate_files": []},
    )

    run_index(
        ctx=StageContext(query="router", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    runtime_config = captured["runtime_config"]
    assert runtime_config.top_k_files == 3
    assert runtime_config.chunk_top_k > 0
    assert runtime_config.chunk_per_file_limit > 0
    assert runtime_config.tokenizer_model == "gpt-4o-mini"
    assert runtime_config.chunk_guard_mode == "off"
    assert runtime_config.embedding_enabled is False
    assert captured["candidates"] == [{"path": "src/alpha.py", "score": 6.0}]


def test_run_index_reuses_candidate_cache_and_preserves_order_and_scores(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
        "src/beta.py": {"module": "src.beta", "language": "python"},
    }
    call_counts = {"gather": 0, "refine": 0, "chunks": 0}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["alpha", "beta"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )

    def fake_gather_initial_candidates(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        call_counts["gather"] += 1
        return InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="hybrid_re2",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[
                {
                    "path": "src/beta.py",
                    "module": "src.beta",
                    "score": 7.0,
                    "score_breakdown": {"heuristic": 7.0},
                },
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                },
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        )

    def fake_refine_candidate_pool(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        call_counts["refine"] += 1
        return CandidateFusionResult(
            candidates=[
                {
                    "path": "src/beta.py",
                    "module": "src.beta",
                    "score": 7.0,
                    "score_breakdown": {"heuristic": 7.0},
                },
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                },
            ],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 2,
                "candidate_count_after": 2,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={"enabled": False, "boosted_count": 0, "query_hit_paths": 0},
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": False,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 0,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        )

    def fake_select_index_chunks(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        call_counts["chunks"] += 1
        return ChunkSelectionResult(
            candidate_chunks=[
                {
                    "path": "src/beta.py",
                    "qualified_name": "src.beta.answer",
                    "kind": "function",
                    "lineno": 12,
                    "score_breakdown": {"candidate": 7.0},
                    "score_embedding": 0.0,
                }
            ],
            chunk_metrics={"candidate_chunk_count": 1.0, "chunk_budget_used": 32.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        )

    monkeypatch.setattr(index_stage, "gather_initial_candidates", fake_gather_initial_candidates)
    monkeypatch.setattr(index_stage, "refine_candidate_pool", fake_refine_candidate_pool)
    monkeypatch.setattr(index_stage, "select_index_chunks", fake_select_index_chunks)

    first = run_index(
        ctx=StageContext(query="find beta", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )
    second = run_index(
        ctx=StageContext(query="find beta", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert first["candidate_cache"]["hit"] is False
    assert first["candidate_cache"]["store_written"] is True
    assert Path(first["candidate_cache"]["path"]).exists()
    marker = json.loads(
        Path(first["candidate_cache"]["path"]).read_text(encoding="utf-8")
    )
    assert marker["backend"] == "stage_artifact_cache"
    assert (
        tmp_path / "context-map" / "index_candidates" / "stage-artifact-cache.db"
    ).exists()

    assert second["candidate_cache"]["hit"] is True
    assert second["candidate_cache"]["store_written"] is False
    assert call_counts == {"gather": 1, "refine": 1, "chunks": 1}
    assert [row["path"] for row in second["candidate_files"]] == [
        "src/beta.py",
        "src/alpha.py",
    ]
    assert [row["score"] for row in second["candidate_files"]] == [7.0, 6.0]
    assert second["candidate_files"] == first["candidate_files"]
    assert second["candidate_chunks"] == first["candidate_chunks"]
    assert (
        second["metadata"]["selection_fingerprint"]
        == first["metadata"]["selection_fingerprint"]
    )


def test_run_index_candidate_cache_hit_refreshes_live_index_cache_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
    }
    snapshot_holder = {
        "value": RetrievalIndexSnapshot(
            index_payload={
                "files": dict(files_map),
                "file_count": 1,
                "indexed_at": "first-build",
                "languages_covered": ["python"],
                "parser": {"engine": "tree-sitter"},
            },
            cache_info={"cache_hit": False, "mode": "full_build", "changed_files": 0},
            files_map=dict(files_map),
            corpus_size=1,
            index_hash="hash-v1",
        )
    }

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: snapshot_holder["value"],
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["alpha"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="heuristic",
            ranker_fallbacks=["tiny_corpus"],
            min_score_used=2,
            candidates=[
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                }
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "refine_candidate_pool",
        lambda **kwargs: CandidateFusionResult(
            candidates=[
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                }
            ],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 1,
                "candidate_count_after": 1,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={
                "enabled": False,
                "boosted_count": 0,
                "query_hit_paths": 0,
            },
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": False,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 0,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "select_index_chunks",
        lambda **kwargs: ChunkSelectionResult(
            candidate_chunks=[
                {
                    "path": "src/alpha.py",
                    "qualified_name": "src.alpha.answer",
                    "kind": "function",
                    "lineno": 12,
                    "score_breakdown": {"candidate": 6.0},
                    "score_embedding": 0.0,
                }
            ],
            chunk_metrics={"candidate_chunk_count": 1.0, "chunk_budget_used": 16.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        ),
    )

    first = run_index(
        ctx=StageContext(query="find alpha", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    snapshot_holder["value"] = RetrievalIndexSnapshot(
        index_payload={
            "files": dict(files_map),
            "file_count": 1,
            "indexed_at": "second-cache-only",
            "languages_covered": ["python", "markdown"],
            "parser": {"engine": "tree-sitter", "version": "test"},
        },
        cache_info={"cache_hit": True, "mode": "cache_only", "changed_files": 0},
        files_map=dict(files_map),
        corpus_size=1,
        index_hash="hash-v1",
    )

    second = run_index(
        ctx=StageContext(query="find alpha", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert first["candidate_cache"]["hit"] is False
    assert second["candidate_cache"]["hit"] is True
    assert second["cache"] == {
        "cache_hit": True,
        "mode": "cache_only",
        "changed_files": 0,
    }
    assert second["index_hash"] == "hash-v1"
    assert second["file_count"] == 1
    assert second["indexed_at"] == "second-cache-only"
    assert second["languages_covered"] == ["python", "markdown"]
    assert second["parser"] == {"engine": "tree-sitter", "version": "test"}
    assert second["metadata"]["candidate_cache_reused"] is True
    assert second["metadata"]["cached_payload_timings_ms"] == first["metadata"]["timings_ms"]


def test_run_index_candidate_cache_hit_clears_stale_vcs_worktree_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
    }

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["alpha"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                }
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree={"enabled": True, "reason": "ok", "changed_count": 3},
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "refine_candidate_pool",
        lambda **kwargs: CandidateFusionResult(
            candidates=[
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                }
            ],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 1,
                "candidate_count_after": 1,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={
                "enabled": False,
                "boosted_count": 0,
                "query_hit_paths": 0,
            },
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": False,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 0,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "select_index_chunks",
        lambda **kwargs: ChunkSelectionResult(
            candidate_chunks=[
                {
                    "path": "src/alpha.py",
                    "qualified_name": "src.alpha.answer",
                    "kind": "function",
                    "lineno": 12,
                    "score_breakdown": {"candidate": 6.0},
                    "score_embedding": 0.0,
                }
            ],
            chunk_metrics={"candidate_chunk_count": 1.0, "chunk_budget_used": 16.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        ),
    )

    first_ctx = StageContext(query="find alpha", repo="demo", root=str(tmp_path))
    first = run_index(
        ctx=first_ctx,
        config=_make_config(tmp_path, cochange_enabled=True),
    )

    second_ctx = StageContext(
        query="find alpha",
        repo="demo",
        root=str(tmp_path),
        state={"__vcs_worktree": {"enabled": True, "reason": "stale"}},
    )
    second = run_index(
        ctx=second_ctx,
        config=_make_config(tmp_path, cochange_enabled=True),
    )

    assert first["candidate_cache"]["hit"] is False
    assert first_ctx.state["__vcs_worktree"]["enabled"] is True
    assert second["candidate_cache"]["hit"] is True
    assert "__vcs_worktree" not in second_ctx.state


def test_run_index_candidate_cache_hit_preserves_disabled_worktree_policy_for_benchmark_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
    }
    benchmark_filters = {"include_paths": ["src/alpha.py"]}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["alpha"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": "v1",
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )
    monkeypatch.setattr(
        index_stage,
        "gather_initial_candidates",
        lambda **kwargs: InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                }
            ],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "refine_candidate_pool",
        lambda **kwargs: CandidateFusionResult(
            candidates=[
                {
                    "path": "src/alpha.py",
                    "module": "src.alpha",
                    "score": 6.0,
                    "score_breakdown": {"heuristic": 6.0},
                }
            ],
            second_pass_payload={
                "triggered": False,
                "applied": False,
                "reason": "n/a",
                "retry_ranker": "",
            },
            refine_pass_payload={
                "enabled": True,
                "trigger_condition_met": False,
                "triggered": False,
                "applied": False,
                "reason": "",
                "retry_ranker": "",
                "candidate_count_before": 1,
                "candidate_count_after": 1,
                "max_passes": 1,
            },
            cochange_payload={"enabled": False, "neighbors_added": 0},
            scip_payload={"enabled": False, "loaded": False},
            graph_lookup_payload={
                "enabled": False,
                "boosted_count": 0,
                "query_hit_paths": 0,
            },
            embeddings_payload={
                "enabled": False,
                "reason": "disabled",
                "runtime_provider": "",
                "runtime_model": "",
                "runtime_dimension": 0,
                "auto_normalized": False,
                "normalized_fields": [],
                "normalization_notes": [],
            },
            feedback_payload={
                "enabled": False,
                "reason": "disabled",
                "boosted_candidate_count": 0,
                "boosted_unique_paths": 0,
                "matched_event_count": 0,
                "event_count": 0,
            },
            multi_channel_fusion_payload={
                "enabled": False,
                "applied": False,
                "reason": "disabled",
                "rrf_k": 0,
                "caps": {"pool": 0, "code": 0, "docs": 0, "memory": 0},
                "channels": {
                    "code": {"count": 0, "cap": 0, "top": []},
                    "docs": {"count": 0, "cap": 0, "top": []},
                    "memory": {"count": 0, "cap": 0, "top": []},
                },
                "fused": {"scored_count": 0, "pool_size": 0, "top": []},
                "warning": None,
            },
            semantic_embedding_provider_impl=None,
            semantic_cross_encoder_provider=None,
        ),
    )
    monkeypatch.setattr(
        index_stage,
        "select_index_chunks",
        lambda **kwargs: ChunkSelectionResult(
            candidate_chunks=[
                {
                    "path": "src/alpha.py",
                    "qualified_name": "src.alpha.answer",
                    "kind": "function",
                    "lineno": 12,
                    "score_breakdown": {"candidate": 6.0},
                    "score_embedding": 0.0,
                }
            ],
            chunk_metrics={"candidate_chunk_count": 1.0, "chunk_budget_used": 16.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        ),
    )

    first_ctx = StageContext(
        query="find alpha",
        repo="demo",
        root=str(tmp_path),
        state={"benchmark_filters": dict(benchmark_filters)},
    )
    first = run_index(
        ctx=first_ctx,
        config=_make_config(tmp_path, cochange_enabled=True),
    )

    second_ctx = StageContext(
        query="find alpha",
        repo="demo",
        root=str(tmp_path),
        state={
            "benchmark_filters": dict(benchmark_filters),
            "__vcs_worktree": {"enabled": True, "reason": "stale"},
        },
    )
    second = run_index(
        ctx=second_ctx,
        config=_make_config(tmp_path, cochange_enabled=True),
    )

    assert first["candidate_cache"]["hit"] is False
    assert second["candidate_cache"]["hit"] is True
    assert second_ctx.state["__vcs_worktree"]["enabled"] is False
    assert (
        second_ctx.state["__vcs_worktree"]["reason"]
        == "benchmark_filter_explicit_scope"
    )


def test_run_index_candidate_cache_invalidates_when_policy_version_changes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/alpha.py": {"module": "src.alpha", "language": "python"},
    }
    call_count = {"gather": 0}
    policy_version = {"value": "v1"}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["alpha"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "general",
            "version": policy_version["value"],
            "docs_enabled": False,
            "index_parallel_enabled": False,
        },
    )

    def fake_gather_initial_candidates(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        call_count["gather"] += 1
        return InitialCandidateGenerationResult(
            requested_ranker="heuristic",
            selected_ranker="heuristic",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[{"path": "src/alpha.py", "module": "src.alpha", "score": 6.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        )

    monkeypatch.setattr(index_stage, "gather_initial_candidates", fake_gather_initial_candidates)
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    first = run_index(
        ctx=StageContext(query="alpha", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )
    policy_version["value"] = "v2"
    second = run_index(
        ctx=StageContext(query="alpha", repo="demo", root=str(tmp_path)),
        config=_make_config(tmp_path),
    )

    assert first["candidate_cache"]["hit"] is False
    assert second["candidate_cache"]["hit"] is False
    assert second["candidate_cache"]["store_written"] is True
    assert call_count["gather"] == 2


def test_run_index_disables_docs_for_code_only_benchmark_include_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import ace_lite.pipeline.stages.index as index_stage

    files_map = {
        "src/runtime.py": {"module": "src.runtime", "language": "python"},
        "tests/test_runtime.py": {"module": "tests.test_runtime", "language": "python"},
        "docs/guide.md": {"module": "docs.guide", "language": "markdown"},
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        index_stage,
        "load_retrieval_index_snapshot",
        lambda **kwargs: _make_snapshot(files_map),
    )
    monkeypatch.setattr(
        index_stage,
        "extract_retrieval_terms",
        lambda **kwargs: ["runtime", "doctor"],
    )
    monkeypatch.setattr(index_stage, "extract_memory_paths", lambda **kwargs: [])
    monkeypatch.setattr(
        index_stage,
        "resolve_retrieval_policy",
        lambda **kwargs: {
            "name": "doc_intent",
            "version": "v2",
            "docs_enabled": True,
            "index_parallel_enabled": False,
        },
    )

    def fake_gather_initial_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="hybrid_re2",
            ranker_fallbacks=[],
            min_score_used=2,
            candidates=[{"path": "src/runtime.py", "score": 7.0}],
            exact_search_payload={"enabled": False, "applied": False},
            docs_payload={"enabled": False, "reason": "disabled", "section_count": 0},
            worktree_prior=_base_worktree_prior(),
            parallel_payload={"enabled": False},
            prior_payload={"docs_hint_paths": 0},
            docs_elapsed_ms=0.0,
            worktree_elapsed_ms=0.0,
            raw_worktree=None,
        )

    monkeypatch.setattr(index_stage, "gather_initial_candidates", fake_gather_initial_candidates)
    _stub_pipeline_after_generation(monkeypatch, index_stage)

    payload = run_index(
        ctx=StageContext(
            query="runtime doctor",
            repo="demo",
            root=str(tmp_path),
            state={
                "benchmark_filters": {
                    "include_paths": [
                        "src/runtime.py",
                        "tests/test_runtime.py",
                    ]
                }
            },
        ),
        config=_make_config(tmp_path, retrieval_overrides={"candidate_ranker": "hybrid_re2"}),
    )

    assert captured["docs_policy_enabled"] is False
    assert payload["benchmark_filters"]["docs_policy_enabled"] is False
    assert payload["benchmark_filters"]["docs_policy_reason"] == "benchmark_include_paths_code_only"
