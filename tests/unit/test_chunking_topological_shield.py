from __future__ import annotations

from ace_lite.chunking.builder import build_candidate_chunks


def _files_map() -> dict[str, dict[str, object]]:
    return {
        "src/service.py": {
            "module": "src.service",
            "language": "python",
            "symbols": [
                {
                    "kind": "method",
                    "name": "handle_request",
                    "qualified_name": "src.service.Service.handle_request",
                    "lineno": 1,
                    "end_lineno": 5,
                },
                {
                    "kind": "method",
                    "name": "resolve_token",
                    "qualified_name": "src.service.Service.resolve_token",
                    "lineno": 7,
                    "end_lineno": 12,
                },
                {
                    "kind": "function",
                    "name": "misc_helper",
                    "qualified_name": "src.service.misc_helper",
                    "lineno": 14,
                    "end_lineno": 18,
                },
            ],
            "references": [
                {
                    "name": "resolve_token",
                    "qualified_name": "src.service.Service.resolve_token",
                    "lineno": 3,
                    "kind": "call",
                }
            ],
            "imports": [],
        }
    }


def test_build_candidate_chunks_surfaces_report_only_topological_shield_metrics() -> None:
    files_map = _files_map()
    candidates = [{"path": "src/service.py", "score": 4.5, "module": "src.service"}]

    baseline_chunks, _ = build_candidate_chunks(
        root=".",
        files_map=files_map,
        candidates=candidates,
        terms=["handle_request"],
        top_k_files=1,
        top_k_chunks=3,
        per_file_limit=3,
        token_budget=512,
        disclosure_mode="refs",
        snippet_max_lines=6,
        snippet_max_chars=240,
        policy={
            "chunk_weight": 1.0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 4,
            "chunk_graph_neighbor_limit": 4,
            "chunk_graph_edge_weight": 0.18,
            "chunk_graph_prior_cap": 0.3,
            "chunk_graph_seed_min_lexical": 1.0,
            "chunk_graph_seed_min_file_prior": 3.0,
            "chunk_graph_hub_soft_cap": 3,
            "chunk_graph_hub_penalty_weight": 0.04,
        },
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=True,
        diversity_path_penalty=0.2,
        diversity_symbol_family_penalty=0.3,
        diversity_kind_penalty=0.1,
        diversity_locality_penalty=0.15,
        diversity_locality_window=24,
        topological_shield_enabled=False,
        topological_shield_mode="off",
        reference_hits_cache_key="topological-shield",
    )

    report_only_chunks, report_only_metrics = build_candidate_chunks(
        root=".",
        files_map=files_map,
        candidates=candidates,
        terms=["handle_request"],
        top_k_files=1,
        top_k_chunks=3,
        per_file_limit=3,
        token_budget=512,
        disclosure_mode="refs",
        snippet_max_lines=6,
        snippet_max_chars=240,
        policy={
            "chunk_weight": 1.0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 4,
            "chunk_graph_neighbor_limit": 4,
            "chunk_graph_edge_weight": 0.18,
            "chunk_graph_prior_cap": 0.3,
            "chunk_graph_seed_min_lexical": 1.0,
            "chunk_graph_seed_min_file_prior": 3.0,
            "chunk_graph_hub_soft_cap": 3,
            "chunk_graph_hub_penalty_weight": 0.04,
        },
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=True,
        diversity_path_penalty=0.2,
        diversity_symbol_family_penalty=0.3,
        diversity_kind_penalty=0.1,
        diversity_locality_penalty=0.15,
        diversity_locality_window=24,
        topological_shield_enabled=True,
        topological_shield_mode="report_only",
        topological_shield_max_attenuation=0.6,
        topological_shield_shared_parent_attenuation=0.2,
        topological_shield_adjacency_attenuation=0.5,
        reference_hits_cache_key="topological-shield",
    )

    assert [
        (item["qualified_name"], item["score"]) for item in report_only_chunks
    ] == [(item["qualified_name"], item["score"]) for item in baseline_chunks]

    helper = next(
        item
        for item in report_only_chunks
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )
    baseline_helper = next(
        item
        for item in baseline_chunks
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )

    assert helper["score"] == baseline_helper["score"]
    assert helper["score_breakdown"]["topological_shield_report_only"] == 1.0
    assert helper["score_breakdown"]["topological_shield_attenuation"] > 0.0
    assert (
        helper["score_breakdown"]["topological_shield_adjusted_score"]
        >= helper["score"]
    )
    assert report_only_metrics["topological_shield_enabled"] == 1.0
    assert report_only_metrics["topological_shield_report_only"] == 1.0
    assert report_only_metrics["topological_shield_attenuated_chunk_count"] == 1.0
    assert report_only_metrics["topological_shield_coverage_ratio"] == 1.0 / 3.0
    assert report_only_metrics["topological_shield_attenuation_total"] > 0.0
