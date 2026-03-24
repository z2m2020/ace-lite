from __future__ import annotations

import json
from pathlib import Path

from ace_lite.chunking.builder import build_candidate_chunks
from ace_lite.chunking.graph_closure import apply_graph_closure_bonus


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


def test_apply_graph_closure_bonus_rewards_graph_near_sibling() -> None:
    candidate_chunks = [
        {
            "path": "src/service.py",
            "qualified_name": "src.service.Service.handle_request",
            "name": "handle_request",
            "kind": "method",
            "lineno": 1,
            "end_lineno": 5,
            "score": 4.0,
            "score_breakdown": {"file_prior": 1.4, "symbol": 2.5},
        },
        {
            "path": "src/service.py",
            "qualified_name": "src.service.Service.resolve_token",
            "name": "resolve_token",
            "kind": "method",
            "lineno": 7,
            "end_lineno": 12,
            "score": 0.6,
            "score_breakdown": {"file_prior": 0.6},
        },
        {
            "path": "src/service.py",
            "qualified_name": "src.service.misc_helper",
            "name": "misc_helper",
            "kind": "function",
            "lineno": 14,
            "end_lineno": 18,
            "score": 0.7,
            "score_breakdown": {"file_prior": 0.6},
        },
    ]

    ranked, payload = apply_graph_closure_bonus(
        candidate_chunks=candidate_chunks,
        files_map=_files_map(),
        policy={
            "chunk_graph_closure_enabled": True,
            "chunk_graph_closure_seed_limit": 4,
            "chunk_graph_closure_neighbor_limit": 4,
            "chunk_graph_closure_bonus_weight": 0.12,
            "chunk_graph_closure_bonus_cap": 0.2,
            "chunk_graph_closure_seed_min_lexical": 1.0,
            "chunk_graph_closure_seed_min_file_prior": 2.0,
        },
        cache_key="graph-closure-bonus",
    )

    sibling = next(
        item
        for item in ranked
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )
    misc = next(
        item for item in ranked if item["qualified_name"] == "src.service.misc_helper"
    )

    assert payload["reason"] == "ok"
    assert payload["boosted_chunk_count"] == 1
    assert sibling["score"] > misc["score"]
    assert sibling["score_breakdown"]["graph_closure_bonus"] == 0.12
    assert sibling["score_breakdown"]["graph_closure_support_count"] == 1.0


def test_apply_graph_closure_bonus_surfaces_graph_provider_fallback() -> None:
    ranked, payload = apply_graph_closure_bonus(
        candidate_chunks=[
            {
                "path": "src/service.py",
                "qualified_name": "src.service.Service.handle_request",
                "name": "handle_request",
                "kind": "method",
                "lineno": 1,
                "end_lineno": 5,
                "score": 4.0,
                "score_breakdown": {"file_prior": 1.4, "symbol": 2.5},
            },
            {
                "path": "src/service.py",
                "qualified_name": "src.service.Service.resolve_token",
                "name": "resolve_token",
                "kind": "method",
                "lineno": 7,
                "end_lineno": 12,
                "score": 0.6,
                "score_breakdown": {"file_prior": 0.6},
            },
        ],
        files_map=_files_map(),
        policy={
            "chunk_graph_closure_enabled": True,
            "chunk_graph_closure_seed_limit": 4,
            "chunk_graph_closure_neighbor_limit": 4,
            "chunk_graph_closure_bonus_weight": 0.12,
            "chunk_graph_closure_bonus_cap": 0.2,
            "chunk_graph_closure_seed_min_lexical": 1.0,
            "chunk_graph_closure_seed_min_file_prior": 2.0,
            "chunk_graph_context_provider": "scip",
        },
        cache_key="graph-closure-provider-fallback",
    )

    sibling = next(
        item
        for item in ranked
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )

    assert payload["reason"] == "ok"
    assert payload["graph_provider_requested"] == "scip"
    assert payload["graph_provider_selected"] == "adjacency"
    assert payload["graph_provider_fallback"] is True
    assert payload["graph_fallback_reason"] == "scip_source_unavailable"
    assert payload["graph_scope"] == "symbol"
    assert sibling["score_breakdown"]["graph_closure_bonus"] == 0.12


def test_apply_graph_closure_bonus_surfaces_loaded_scip_source_metadata(
    tmp_path: Path,
) -> None:
    scip_path = tmp_path / "context-map" / "scip" / "index.json"
    scip_path.parent.mkdir(parents=True, exist_ok=True)
    scip_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "relative_path": "src/service.py",
                        "occurrences": [
                            {"symbol": "demo src/service.py Service#", "symbol_roles": 1},
                            {"symbol": "demo src/dep.py Dep#", "symbol_roles": 8},
                        ],
                    },
                    {
                        "relative_path": "src/dep.py",
                        "occurrences": [
                            {"symbol": "demo src/dep.py Dep#", "symbol_roles": 1},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    ranked, payload = apply_graph_closure_bonus(
        root=str(tmp_path),
        candidate_chunks=[
            {
                "path": "src/service.py",
                "qualified_name": "src.service.Service.handle_request",
                "name": "handle_request",
                "kind": "method",
                "lineno": 1,
                "end_lineno": 5,
                "score": 4.0,
                "score_breakdown": {"file_prior": 1.4, "symbol": 2.5},
            },
            {
                "path": "src/service.py",
                "qualified_name": "src.service.Service.resolve_token",
                "name": "resolve_token",
                "kind": "method",
                "lineno": 7,
                "end_lineno": 12,
                "score": 0.6,
                "score_breakdown": {"file_prior": 0.6},
            },
        ],
        files_map=_files_map(),
        policy={
            "chunk_graph_closure_enabled": True,
            "chunk_graph_closure_seed_limit": 4,
            "chunk_graph_closure_neighbor_limit": 4,
            "chunk_graph_closure_bonus_weight": 0.12,
            "chunk_graph_closure_bonus_cap": 0.2,
            "chunk_graph_closure_seed_min_lexical": 1.0,
            "chunk_graph_closure_seed_min_file_prior": 2.0,
            "chunk_graph_context_provider": "scip",
            "scip_index_path": "context-map/scip/index.json",
        },
        cache_key="graph-closure-loaded-scip-source",
    )

    sibling = next(
        item
        for item in ranked
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )

    assert payload["reason"] == "ok"
    assert payload["graph_provider_selected"] == "adjacency"
    assert payload["graph_fallback_reason"] == "file_scope_symbol_projection_pending"
    assert payload["graph_source_provider_selected"] == "scip"
    assert payload["graph_source_provider_loaded"] is True
    assert payload["graph_source_graph_scope"] == "file"
    assert payload["graph_source_edge_count"] == 1
    assert payload["graph_source_projection_fallback"] is True
    assert payload["graph_source_projection_reason"] == "file_scope_symbol_projection_pending"
    assert sibling["score_breakdown"]["graph_closure_bonus"] == 0.12


def test_build_candidate_chunks_applies_graph_closure_bonus_independent_of_graph_prior() -> None:
    candidates = [{"path": "src/service.py", "score": 4.5, "module": "src.service"}]

    baseline_chunks, _ = build_candidate_chunks(
        root=".",
        files_map=_files_map(),
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
            "chunk_graph_prior_enabled": False,
            "chunk_graph_closure_enabled": False,
        },
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=False,
        diversity_path_penalty=0.0,
        diversity_symbol_family_penalty=0.0,
        diversity_kind_penalty=0.0,
        diversity_locality_penalty=0.0,
        diversity_locality_window=24,
        reference_hits_cache_key="graph-closure-builder",
    )

    closure_chunks, closure_metrics = build_candidate_chunks(
        root=".",
        files_map=_files_map(),
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
            "chunk_graph_prior_enabled": False,
            "chunk_graph_closure_enabled": True,
            "chunk_graph_closure_seed_limit": 4,
            "chunk_graph_closure_neighbor_limit": 4,
            "chunk_graph_closure_bonus_weight": 0.12,
            "chunk_graph_closure_bonus_cap": 0.2,
            "chunk_graph_closure_seed_min_lexical": 1.0,
            "chunk_graph_closure_seed_min_file_prior": 3.0,
        },
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=False,
        diversity_path_penalty=0.0,
        diversity_symbol_family_penalty=0.0,
        diversity_kind_penalty=0.0,
        diversity_locality_penalty=0.0,
        diversity_locality_window=24,
        reference_hits_cache_key="graph-closure-builder",
    )

    baseline_sibling = next(
        item
        for item in baseline_chunks
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )
    closure_sibling = next(
        item
        for item in closure_chunks
        if item["qualified_name"] == "src.service.Service.resolve_token"
    )

    assert closure_sibling["score"] > baseline_sibling["score"]
    assert closure_sibling["score_breakdown"]["graph_closure_bonus"] == 0.12
    assert "graph_prior" not in closure_sibling["score_breakdown"]
    assert closure_metrics["graph_closure_enabled"] == 1.0
    assert closure_metrics["graph_closure_boosted_chunk_count"] == 1.0
    assert closure_metrics["graph_closure_coverage_ratio"] > 0.0
    assert closure_metrics["graph_closure_anchor_count"] == 1.0
    assert closure_metrics["graph_closure_support_edge_count"] == 1.0
    assert closure_metrics["graph_closure_total"] == 0.12
