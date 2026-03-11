from __future__ import annotations

from pathlib import Path

from ace_lite.index_stage import apply_scip_boost
from ace_lite.scip import generate_scip_index, load_scip_edges


def test_generate_and_load_scip_index(tmp_path: Path) -> None:
    index_files = {
        "src/a.py": {
            "symbols": [{"name": "Alpha", "qualified_name": "src.a.Alpha"}],
            "references": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
        },
        "src/b.py": {
            "symbols": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
            "references": [{"name": "Alpha", "qualified_name": "src.a.Alpha"}],
        },
    }

    output_path = tmp_path / "context-map" / "scip" / "index.json"

    generated = generate_scip_index(index_files=index_files, output_path=output_path)
    loaded = load_scip_edges(output_path)

    assert generated["edge_count"] == 2
    assert loaded["loaded"] is True
    assert loaded["edge_count"] == 2
    assert loaded["inbound_counts"]["src/a.py"] == 1.0
    assert loaded["inbound_counts"]["src/b.py"] == 1.0
    assert loaded["degree_centrality"]["src/a.py"] == 2.0
    assert loaded["degree_centrality"]["src/b.py"] == 2.0
    assert abs(float(loaded["pagerank"]["src/a.py"]) - float(loaded["pagerank"]["src/b.py"])) < 1e-6
    assert abs(sum(float(v) for v in loaded["pagerank"].values()) - 1.0) < 1e-6


def test_orchestrator_apply_scip_boost_prefers_high_inbound(tmp_path: Path, fake_skill_manifest) -> None:
    files_map = {
        "src/a.py": {
            "symbols": [{"name": "Alpha", "qualified_name": "src.a.Alpha"}],
            "references": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
        },
        "src/b.py": {
            "symbols": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
            "references": [],
        },
    }
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
    ]

    boosted, payload = apply_scip_boost(
        index_path=tmp_path / "context-map" / "scip" / "index.json",
        provider="scip_lite",
        generate_fallback=True,
        files_map=files_map,
        candidates=candidates,
        policy={"scip_weight": 1.0},
    )

    assert payload["enabled"] is True
    assert payload["loaded"] is True
    assert payload["boost_applied"] >= 1
    assert boosted[0]["path"] == "src/b.py"
    assert "scip" in boosted[0]["score_breakdown"]


def test_orchestrator_apply_scip_boost_can_use_pagerank(tmp_path: Path, fake_skill_manifest) -> None:
    files_map = {
        "src/a.py": {
            "symbols": [{"name": "Alpha", "qualified_name": "src.a.Alpha"}],
            "references": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
        },
        "src/b.py": {
            "symbols": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
            "references": [{"name": "Alpha", "qualified_name": "src.a.Alpha"}],
        },
        "src/c.py": {
            "symbols": [{"name": "Gamma", "qualified_name": "src.c.Gamma"}],
            "references": [{"name": "Beta", "qualified_name": "src.b.Beta"}],
        },
    }
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/c.py", "score": 1.0, "score_breakdown": {}},
    ]

    boosted, payload = apply_scip_boost(
        index_path=tmp_path / "context-map" / "scip" / "index.json",
        provider="scip_lite",
        generate_fallback=True,
        files_map=files_map,
        candidates=candidates,
        policy={"scip_weight": 0.0, "scip_pagerank_weight": 1.0},
    )

    assert payload["enabled"] is True
    assert payload["loaded"] is True
    assert payload["boost_applied"] >= 1
    assert boosted[0]["path"] == "src/b.py"
    assert "scip_pagerank" in boosted[0]["score_breakdown"]
