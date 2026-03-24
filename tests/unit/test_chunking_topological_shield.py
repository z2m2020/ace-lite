from __future__ import annotations

import json
from pathlib import Path

from ace_lite.chunking.builder import build_candidate_chunks
from ace_lite.chunking.topological_shield import compute_topological_shield


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


def test_compute_topological_shield_surfaces_graph_provider_fallback() -> None:
    payload = compute_topological_shield(
        candidate={
            "path": "src/service.py",
            "qualified_name": "src.service.Service.resolve_token",
            "name": "resolve_token",
            "kind": "method",
            "lineno": 7,
            "end_lineno": 12,
            "score_breakdown": {"graph_prior": 0.18},
        },
        selected=[
            {
                "path": "src/service.py",
                "qualified_name": "src.service.Service.handle_request",
                "name": "handle_request",
                "kind": "method",
                "lineno": 1,
                "end_lineno": 5,
                "score_breakdown": {"graph_seeded": 1.0},
            }
        ],
        files_map=_files_map(),
        cache_key="topological-shield-provider-fallback",
        base_penalty=0.5,
        base_score=1.0,
        enabled=True,
        mode="report_only",
        max_attenuation=0.6,
        shared_parent_attenuation=0.2,
        adjacency_attenuation=0.5,
        policy={"chunk_graph_context_provider": "scip"},
    )

    assert payload["reason"] == "ok"
    assert payload["graph_provider_requested"] == "scip"
    assert payload["graph_provider_selected"] == "adjacency"
    assert payload["graph_provider_fallback"] is True
    assert payload["graph_fallback_reason"] == "scip_source_unavailable"
    assert payload["graph_scope"] == "symbol"


def test_compute_topological_shield_surfaces_loaded_scip_source_metadata(
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

    payload = compute_topological_shield(
        root=str(tmp_path),
        candidate={
            "path": "src/service.py",
            "qualified_name": "src.service.Service.resolve_token",
            "name": "resolve_token",
            "kind": "method",
            "lineno": 7,
            "end_lineno": 12,
            "score_breakdown": {"graph_prior": 0.18},
        },
        selected=[
            {
                "path": "src/service.py",
                "qualified_name": "src.service.Service.handle_request",
                "name": "handle_request",
                "kind": "method",
                "lineno": 1,
                "end_lineno": 5,
                "score_breakdown": {"graph_seeded": 1.0},
            }
        ],
        files_map=_files_map(),
        cache_key="topological-shield-loaded-scip-source",
        base_penalty=0.5,
        base_score=1.0,
        enabled=True,
        mode="report_only",
        max_attenuation=0.6,
        shared_parent_attenuation=0.2,
        adjacency_attenuation=0.5,
        policy={
            "chunk_graph_context_provider": "scip",
            "scip_index_path": "context-map/scip/index.json",
        },
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
