from __future__ import annotations

from typing import Any

from ace_lite.index_stage.chunk_runtime import run_index_chunk_selection
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult


def test_run_index_chunk_selection_builds_runtime_config_and_deps() -> None:
    captured: dict[str, Any] = {}

    def fake_select_index_chunks(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return ChunkSelectionResult(
            candidate_chunks=[],
            chunk_metrics={"candidate_chunk_count": 0.0, "chunk_budget_used": 0.0},
            chunk_semantic_rerank_payload={"enabled": False, "reason": "disabled"},
            topological_shield_payload={"enabled": False, "mode": "off"},
            chunk_guard_payload={"enabled": False, "mode": "off", "reason": "disabled"},
        )

    def fake_apply_chunk_selection(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("should not be called directly by this helper test")

    def fake_mark_timing(label: str, started_at: float) -> None:
        _ = (label, started_at)

    result = run_index_chunk_selection(
        root="/tmp/demo",
        query="router",
        files_map={"src/app.py": {"module": "src.app"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["router"],
        policy={"chunk_semantic_rerank_enabled": False},
        index_hash="idx",
        embeddings_payload={"enabled": False},
        semantic_embedding_provider_impl=None,
        semantic_cross_encoder_provider=None,
        top_k_files=4,
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
        embedding_enabled=False,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        select_index_chunks_fn=fake_select_index_chunks,
        apply_chunk_selection_fn=fake_apply_chunk_selection,
        mark_timing_fn=fake_mark_timing,
        rerank_rows_embeddings_with_time_budget_fn=lambda **kwargs: ([], None),
        rerank_rows_cross_encoder_with_time_budget_fn=lambda **kwargs: ([], None),
    )

    assert result.chunk_guard_payload["mode"] == "off"
    runtime_config = captured["runtime_config"]
    deps = captured["deps"]
    assert runtime_config.top_k_files == 4
    assert runtime_config.chunk_top_k == 8
    assert runtime_config.chunk_per_file_limit == 2
    assert runtime_config.chunk_topological_shield_mode == "report_only"
    assert runtime_config.embedding_semantic_weight == 0.3
    assert deps.apply_chunk_selection is fake_apply_chunk_selection
    assert deps.mark_timing is fake_mark_timing
