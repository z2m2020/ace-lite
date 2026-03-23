from __future__ import annotations

from ace_lite.index_stage import apply_graph_lookup_rerank


def test_apply_graph_lookup_rerank_boosts_with_scip_and_xref_signals() -> None:
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
    ]
    files_map = {
        "src/a.py": {
            "references": [{"qualified_name": "core.token.parse"}],
        },
        "src/b.py": {
            "references": [
                {"qualified_name": "core.auth.validate_token"},
                {"qualified_name": "core.session.ensure_session"},
            ],
        },
    }

    ranked, payload = apply_graph_lookup_rerank(
        candidates=candidates,
        files_map=files_map,
        terms=["validate", "token"],
        scip_inbound_counts={"src/a.py": 1.0, "src/b.py": 4.0},
        policy={
            "graph_lookup_enabled": True,
            "graph_lookup_scip_weight": 0.3,
            "graph_lookup_xref_weight": 0.2,
            "graph_lookup_query_weight": 0.2,
        },
    )

    assert payload["enabled"] is True
    assert payload["boosted_count"] == 2
    assert payload["normalization"] == "log1p"
    assert payload["max_inbound"] == 4.0
    assert payload["max_xref_count"] == 2.0
    assert payload["max_query_hits"] == 1.0
    assert ranked[0]["path"] == "src/b.py"
    assert float(ranked[0]["score"]) > float(ranked[1]["score"])
    assert "graph_lookup" in ranked[0]["score_breakdown"]


def test_apply_graph_lookup_rerank_respects_policy_disable() -> None:
    candidates = [{"path": "src/a.py", "score": 1.0}]
    ranked, payload = apply_graph_lookup_rerank(
        candidates=candidates,
        files_map={"src/a.py": {"references": []}},
        terms=["token"],
        scip_inbound_counts={"src/a.py": 5.0},
        policy={"graph_lookup_enabled": False},
    )

    assert ranked == candidates
    assert payload["enabled"] is False
    assert payload["reason"] == "disabled_by_policy"


def test_apply_graph_lookup_rerank_uses_symbol_import_and_coverage_signals() -> None:
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
    ]
    files_map = {
        "src/a.py": {
            "symbols": [{"qualified_name": "http.request.manager"}],
            "imports": [{"module": "http.pool.manager"}],
            "references": [],
        },
        "src/b.py": {
            "symbols": [{"qualified_name": "misc.Utility"}],
            "imports": [{"module": "misc.helpers"}],
            "references": [],
        },
    }

    ranked, payload = apply_graph_lookup_rerank(
        candidates=candidates,
        files_map=files_map,
        terms=["request", "pool", "manager"],
        scip_inbound_counts={},
        policy={
            "graph_lookup_enabled": True,
            "graph_lookup_scip_weight": 0.0,
            "graph_lookup_xref_weight": 0.0,
            "graph_lookup_query_weight": 0.0,
            "graph_lookup_symbol_weight": 0.4,
            "graph_lookup_import_weight": 0.4,
            "graph_lookup_coverage_weight": 0.2,
            "graph_lookup_log_norm": False,
        },
    )

    assert payload["enabled"] is True
    assert payload["normalization"] == "linear"
    assert payload["symbol_hit_paths"] == 1
    assert payload["import_hit_paths"] == 1
    assert payload["coverage_hit_paths"] == 1
    assert payload["max_symbol_hits"] == 1.0
    assert payload["max_import_hits"] == 1.0
    assert payload["max_query_coverage"] == 1.0
    assert ranked[0]["path"] == "src/a.py"
    assert float(ranked[0]["score"]) > float(ranked[1]["score"])
    assert "graph_lookup" in ranked[0]["score_breakdown"]
