from __future__ import annotations

from ace_lite.chunking.builder import build_candidate_chunks
from ace_lite.chunking.graph_prior import apply_query_aware_graph_prior


def test_apply_query_aware_graph_prior_boosts_graph_neighbor_chunk() -> None:
    files_map = {
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [
                {
                    "name": "handle_request",
                    "qualified_name": "src.use.handle_request",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 5,
                },
                {
                    "name": "resolve_token",
                    "qualified_name": "src.use.resolve_token",
                    "kind": "function",
                    "lineno": 7,
                    "end_lineno": 12,
                },
                {
                    "name": "misc_helper",
                    "qualified_name": "src.use.misc_helper",
                    "kind": "function",
                    "lineno": 14,
                    "end_lineno": 18,
                },
            ],
            "references": [
                {
                    "name": "resolve_token",
                    "qualified_name": "src.use.resolve_token",
                    "lineno": 3,
                    "kind": "call",
                }
            ],
            "imports": [],
        }
    }
    candidate_chunks = [
        {
            "path": "src/use.py",
            "qualified_name": "src.use.handle_request",
            "name": "handle_request",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 5,
            "score": 4.0,
            "score_breakdown": {"file_prior": 1.4, "symbol": 2.5},
        },
        {
            "path": "src/use.py",
            "qualified_name": "src.use.resolve_token",
            "name": "resolve_token",
            "kind": "function",
            "lineno": 7,
            "end_lineno": 12,
            "score": 0.6,
            "score_breakdown": {"file_prior": 0.6},
        },
        {
            "path": "src/use.py",
            "qualified_name": "src.use.misc_helper",
            "name": "misc_helper",
            "kind": "function",
            "lineno": 14,
            "end_lineno": 18,
            "score": 0.7,
            "score_breakdown": {"file_prior": 0.6},
        },
    ]

    ranked, payload = apply_query_aware_graph_prior(
        candidate_chunks=candidate_chunks,
        files_map=files_map,
        policy={
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 4,
            "chunk_graph_neighbor_limit": 4,
            "chunk_graph_edge_weight": 0.18,
            "chunk_graph_prior_cap": 0.3,
            "chunk_graph_seed_min_lexical": 1.0,
            "chunk_graph_seed_min_file_prior": 2.0,
            "chunk_graph_hub_soft_cap": 3,
            "chunk_graph_hub_penalty_weight": 0.04,
        },
    )

    helper = next(
        item for item in ranked if item["qualified_name"] == "src.use.resolve_token"
    )
    misc = next(
        item for item in ranked if item["qualified_name"] == "src.use.misc_helper"
    )
    seed = next(
        item for item in ranked if item["qualified_name"] == "src.use.handle_request"
    )

    assert payload["reason"] == "ok"
    assert payload["boosted_chunk_count"] == 1
    assert seed["score_breakdown"]["graph_seeded"] == 1.0
    assert helper["score"] > misc["score"]
    assert helper["score_breakdown"]["graph_prior"] > 0.0
    assert helper["score_breakdown"]["graph_transfer_count"] == 1.0


def test_apply_query_aware_graph_prior_caps_and_suppresses_hubs() -> None:
    files_map = {
        "src/defs/helper.py": {
            "module": "src.defs.helper",
            "language": "python",
            "symbols": [
                {
                    "name": "Helper",
                    "qualified_name": "src.defs.helper.Helper",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 4,
                }
            ],
            "references": [],
            "imports": [],
        },
        "src/defs/logger.py": {
            "module": "src.defs.logger",
            "language": "python",
            "symbols": [
                {
                    "name": "Logger",
                    "qualified_name": "src.defs.logger.Logger",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 4,
                }
            ],
            "references": [],
            "imports": [],
        },
        "src/use_a.py": {
            "module": "src.use_a",
            "language": "python",
            "symbols": [
                {
                    "name": "handle_a",
                    "qualified_name": "src.use_a.handle_a",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 6,
                }
            ],
            "references": [
                {
                    "name": "Helper",
                    "qualified_name": "src.defs.helper.Helper",
                    "lineno": 2,
                    "kind": "call",
                },
                {
                    "name": "Logger",
                    "qualified_name": "src.defs.logger.Logger",
                    "lineno": 3,
                    "kind": "call",
                },
            ],
            "imports": [],
        },
        "src/use_b.py": {
            "module": "src.use_b",
            "language": "python",
            "symbols": [
                {
                    "name": "handle_b",
                    "qualified_name": "src.use_b.handle_b",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 6,
                }
            ],
            "references": [
                {
                    "name": "Helper",
                    "qualified_name": "src.defs.helper.Helper",
                    "lineno": 2,
                    "kind": "call",
                },
                {
                    "name": "Logger",
                    "qualified_name": "src.defs.logger.Logger",
                    "lineno": 3,
                    "kind": "call",
                },
            ],
            "imports": [],
        },
        "src/noise_x.py": {
            "module": "src.noise_x",
            "language": "python",
            "symbols": [
                {
                    "name": "noise_x",
                    "qualified_name": "src.noise_x.noise_x",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 3,
                }
            ],
            "references": [
                {
                    "name": "Logger",
                    "qualified_name": "src.defs.logger.Logger",
                    "lineno": 2,
                    "kind": "call",
                }
            ],
            "imports": [],
        },
        "src/noise_y.py": {
            "module": "src.noise_y",
            "language": "python",
            "symbols": [
                {
                    "name": "noise_y",
                    "qualified_name": "src.noise_y.noise_y",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 3,
                }
            ],
            "references": [
                {
                    "name": "Logger",
                    "qualified_name": "src.defs.logger.Logger",
                    "lineno": 2,
                    "kind": "call",
                }
            ],
            "imports": [],
        },
    }
    candidate_chunks = [
        {
            "path": "src/use_a.py",
            "qualified_name": "src.use_a.handle_a",
            "name": "handle_a",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 6,
            "score": 4.0,
            "score_breakdown": {"file_prior": 1.4, "symbol": 2.5},
        },
        {
            "path": "src/use_b.py",
            "qualified_name": "src.use_b.handle_b",
            "name": "handle_b",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 6,
            "score": 3.8,
            "score_breakdown": {"file_prior": 1.4, "symbol": 2.5},
        },
        {
            "path": "src/defs/helper.py",
            "qualified_name": "src.defs.helper.Helper",
            "name": "Helper",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 4,
            "score": 0.6,
            "score_breakdown": {"file_prior": 0.6},
        },
        {
            "path": "src/defs/logger.py",
            "qualified_name": "src.defs.logger.Logger",
            "name": "Logger",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 4,
            "score": 0.6,
            "score_breakdown": {"file_prior": 0.6},
        },
    ]

    ranked, payload = apply_query_aware_graph_prior(
        candidate_chunks=candidate_chunks,
        files_map=files_map,
        policy={
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 4,
            "chunk_graph_neighbor_limit": 4,
                "chunk_graph_edge_weight": 0.18,
                "chunk_graph_prior_cap": 0.2,
                "chunk_graph_seed_min_lexical": 1.0,
                "chunk_graph_seed_min_file_prior": 2.0,
                "chunk_graph_hub_soft_cap": 2,
                "chunk_graph_hub_penalty_weight": 0.09,
                "chunk_graph_max_hub_penalty": 0.2,
            },
        )

    helper = next(
        item for item in ranked if item["qualified_name"] == "src.defs.helper.Helper"
    )
    logger = next(
        item for item in ranked if item["qualified_name"] == "src.defs.logger.Logger"
    )

    assert payload["reason"] == "ok"
    assert payload["graph_prior_total"] == 0.2
    assert payload["hub_suppressed_chunk_count"] == 1
    assert helper["score_breakdown"]["graph_prior"] == 0.2
    assert logger["score_breakdown"]["graph_transfer_count"] == 2.0
    assert logger["score_breakdown"]["graph_hub_penalty"] < 0.0
    assert "graph_prior" not in logger["score_breakdown"]


def test_build_candidate_chunks_surfaces_graph_prior_metrics() -> None:
    files_map = {
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [
                {
                    "kind": "function",
                    "name": "handle_request",
                    "qualified_name": "src.use.handle_request",
                    "lineno": 1,
                    "end_lineno": 5,
                },
                {
                    "kind": "function",
                    "name": "resolve_token",
                    "qualified_name": "src.use.resolve_token",
                    "lineno": 7,
                    "end_lineno": 12,
                },
                {
                    "kind": "function",
                    "name": "misc_helper",
                    "qualified_name": "src.use.misc_helper",
                    "lineno": 14,
                    "end_lineno": 18,
                },
            ],
            "references": [
                {
                    "name": "resolve_token",
                    "qualified_name": "src.use.resolve_token",
                    "lineno": 3,
                    "kind": "call",
                }
            ],
            "imports": [],
        }
    }
    candidates = [{"path": "src/use.py", "score": 4.5, "module": "src.use"}]

    selected, metrics = build_candidate_chunks(
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
        diversity_enabled=False,
        diversity_path_penalty=0.0,
        diversity_symbol_family_penalty=0.0,
        diversity_kind_penalty=0.0,
        diversity_locality_penalty=0.0,
        diversity_locality_window=24,
        reference_hits_cache_key="graph-prior-metrics",
    )

    helper = next(
        item for item in selected if item["qualified_name"] == "src.use.resolve_token"
    )

    assert helper["score_breakdown"]["graph_prior"] > 0.0
    assert metrics["graph_prior_chunk_count"] == 1.0
    assert metrics["graph_prior_coverage_ratio"] == 1.0 / 3.0
    assert metrics["graph_seeded_chunk_count"] == 1.0
    assert metrics["graph_transfer_count"] == 1.0
