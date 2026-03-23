from __future__ import annotations

from ace_lite.index_stage.structural_rerank import apply_structural_rerank


def test_apply_structural_rerank_marks_policy_disabled_cochange() -> None:
    timings: list[str] = []

    result = apply_structural_rerank(
        root=".",
        files_map={"src/a.py": {}},
        candidates=[{"path": "src/a.py", "score": 1.0}],
        memory_paths=["src/a.py"],
        terms=["alpha"],
        policy={
            "cochange_enabled": False,
            "graph_lookup_enabled": False,
        },
        cochange_enabled=True,
        cochange_cache_path="context-map/cochange.json",
        cochange_lookback_commits=100,
        cochange_half_life_days=30.0,
        cochange_neighbor_cap=8,
        top_k_files=4,
        cochange_top_neighbors=4,
        cochange_boost_weight=1.0,
        cochange_min_neighbor_score=0.1,
        cochange_max_boost=1.0,
        scip_enabled=False,
        scip_index_path="context-map/scip/index.json",
        scip_provider="auto",
        scip_generate_fallback=True,
        mark_timing=lambda name, started: timings.append(name),
    )

    assert result.cochange_payload["cache_mode"] == "policy_disabled"
    assert result.cochange_payload["enabled"] is False
    assert result.scip_payload["enabled"] is False
    assert result.graph_lookup_payload["reason"] == "disabled_by_policy"
    assert timings == ["cochange", "scip_boost", "graph_lookup"]


def test_apply_structural_rerank_loads_scip_graph_for_graph_lookup() -> None:
    captured: dict[str, object] = {}

    def fake_scip(**kwargs):  # type: ignore[no-untyped-def]
        candidates = list(kwargs["candidates"])
        payload = {
            "enabled": True,
            "loaded": True,
            "edge_count": 3,
            "boost_applied": 1,
            "path": str(kwargs["index_path"]),
            "provider": "scip-test",
            "generate_fallback": bool(kwargs["generate_fallback"]),
            "fallback_generated": False,
        }
        return candidates, payload

    def fake_load_graph(index_path, *, provider):  # type: ignore[no-untyped-def]
        captured["index_path"] = str(index_path)
        captured["provider"] = provider
        return {"inbound_counts": {"src/a.py": 3, "src/b.py": 1}}

    def fake_graph_lookup(**kwargs):  # type: ignore[no-untyped-def]
        captured["scip_inbound_counts"] = dict(kwargs["scip_inbound_counts"])
        payload = {
            "enabled": True,
            "reason": "ok",
            "boosted_count": 1,
            "weights": {"scip": 0.1, "xref": 0.0, "query_xref": 0.0},
            "normalization": "log1p",
            "query_terms_count": len(kwargs["terms"]),
            "candidate_count": len(kwargs["candidates"]),
            "pool_size": len(kwargs["candidates"]),
            "scip_signal_paths": len(kwargs["scip_inbound_counts"]),
            "xref_signal_paths": 0,
            "query_hit_paths": 1,
            "max_inbound": 3.0,
            "max_xref_count": 0.0,
            "max_query_hits": 1.0,
            "max_symbol_hits": 0.0,
            "max_import_hits": 0.0,
            "max_query_coverage": 0.5,
            "guard_max_candidates": 64,
            "guard_min_query_terms": 0,
            "guard_max_query_terms": 64,
        }
        return list(kwargs["candidates"]), payload

    result = apply_structural_rerank(
        root="repo-root",
        files_map={"src/a.py": {}, "src/b.py": {}},
        candidates=[{"path": "src/a.py", "score": 2.0}],
        memory_paths=[],
        terms=["alpha", "beta"],
        policy={"graph_lookup_enabled": True},
        cochange_enabled=False,
        cochange_cache_path="context-map/cochange.json",
        cochange_lookback_commits=100,
        cochange_half_life_days=30.0,
        cochange_neighbor_cap=8,
        top_k_files=4,
        cochange_top_neighbors=4,
        cochange_boost_weight=1.0,
        cochange_min_neighbor_score=0.1,
        cochange_max_boost=1.0,
        scip_enabled=True,
        scip_index_path="context-map/scip/index.json",
        scip_provider="auto",
        scip_generate_fallback=False,
        mark_timing=lambda name, started: None,
        scip_fn=fake_scip,
        graph_lookup_fn=fake_graph_lookup,
        load_graph_fn=fake_load_graph,
    )

    assert captured["provider"] == "scip-test"
    assert str(captured["index_path"]).replace("\\", "/").endswith(
        "context-map/scip/index.json"
    )
    assert captured["scip_inbound_counts"] == {"src/a.py": 3.0, "src/b.py": 1.0}
    assert result.scip_payload["loaded"] is True
    assert result.graph_lookup_payload["reason"] == "ok"
    assert result.graph_lookup_payload["guarded"] is False
    assert result.graph_lookup_payload["weights"] == {
        "scip": 0.1,
        "xref": 0.0,
        "query_xref": 0.0,
        "symbol": 0.0,
        "import": 0.0,
        "coverage": 0.0,
    }
    assert result.graph_lookup_payload["normalization"] == "log1p"
    assert result.graph_lookup_payload["guard_max_candidates"] == 64
    assert result.graph_lookup_payload["guard_min_query_terms"] == 0
    assert result.graph_lookup_payload["guard_max_query_terms"] == 64
    assert result.graph_lookup_payload["query_hit_paths"] == 1
    assert result.graph_lookup_payload["symbol_hit_paths"] == 0
    assert result.graph_lookup_payload["import_hit_paths"] == 0
    assert result.graph_lookup_payload["coverage_hit_paths"] == 0
    assert result.graph_lookup_payload["max_inbound"] == 3.0
    assert result.graph_lookup_payload["max_symbol_hits"] == 0.0
    assert result.graph_lookup_payload["max_import_hits"] == 0.0
    assert result.graph_lookup_payload["max_query_coverage"] == 0.5


def test_apply_structural_rerank_skips_graph_lookup_when_candidate_guard_triggers() -> None:
    called = {"graph": False}

    def fake_graph_lookup(**kwargs):  # type: ignore[no-untyped-def]
        called["graph"] = True
        return list(kwargs["candidates"]), {"enabled": True, "reason": "ok"}

    result = apply_structural_rerank(
        root=".",
        files_map={"src/a.py": {}, "src/b.py": {}},
        candidates=[
            {"path": "src/a.py", "score": 2.0},
            {"path": "src/b.py", "score": 1.0},
        ],
        memory_paths=[],
        terms=["alpha"],
        policy={
            "graph_lookup_enabled": True,
            "graph_lookup_max_candidates": 1,
        },
        cochange_enabled=False,
        cochange_cache_path="context-map/cochange.json",
        cochange_lookback_commits=100,
        cochange_half_life_days=30.0,
        cochange_neighbor_cap=8,
        top_k_files=4,
        cochange_top_neighbors=4,
        cochange_boost_weight=1.0,
        cochange_min_neighbor_score=0.1,
        cochange_max_boost=1.0,
        scip_enabled=False,
        scip_index_path="context-map/scip/index.json",
        scip_provider="auto",
        scip_generate_fallback=True,
        mark_timing=lambda name, started: None,
        graph_lookup_fn=fake_graph_lookup,
    )

    assert called["graph"] is False
    assert result.graph_lookup_payload["reason"] == "candidate_count_guarded"
    assert result.graph_lookup_payload["guarded"] is True
    assert result.graph_lookup_payload["guard_max_candidates"] == 1
    assert result.graph_lookup_payload["weights"] == {
        "scip": 0.0,
        "xref": 0.0,
        "query_xref": 0.0,
        "symbol": 0.0,
        "import": 0.0,
        "coverage": 0.0,
    }
    assert result.graph_lookup_payload["symbol_hit_paths"] == 0
    assert result.graph_lookup_payload["import_hit_paths"] == 0
    assert result.graph_lookup_payload["coverage_hit_paths"] == 0
    assert result.graph_lookup_payload["max_symbol_hits"] == 0.0
    assert result.graph_lookup_payload["max_import_hits"] == 0.0
    assert result.graph_lookup_payload["max_query_coverage"] == 0.0
