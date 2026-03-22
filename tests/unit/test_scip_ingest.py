from __future__ import annotations

import json
from pathlib import Path

from ace_lite.index_stage import apply_scip_boost
from ace_lite.scip.loader import load_scip_edges


def test_load_scip_edges_supports_native_scip_json(tmp_path: Path) -> None:
    payload = {
        "metadata": {"toolInfo": {"name": "scip-python"}},
        "documents": [
            {
                "relative_path": "src/a.py",
                "occurrences": [
                    {"symbol": "scip-python python demo src/a.py A#", "symbol_roles": 1},
                    {"symbol": "scip-python python demo src/b.py B#", "symbol_roles": 8},
                ],
            },
            {
                "relative_path": "src/b.py",
                "occurrences": [
                    {"symbol": "scip-python python demo src/b.py B#", "symbol_roles": 1},
                ],
            },
        ],
    }
    path = tmp_path / "context-map" / "scip" / "native.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scip_edges(path, provider="scip")

    assert loaded["loaded"] is True
    assert loaded["provider"] == "scip"
    assert loaded["edge_count"] == 1
    assert loaded["document_count"] == 2
    assert loaded["definition_occurrence_count"] == 2
    assert loaded["reference_occurrence_count"] == 1
    assert loaded["symbol_definition_count"] == 2
    assert loaded["inbound_counts"]["src/b.py"] == 1.0
    assert loaded["edges"] == [
        {"source": "src/a.py", "target": "src/b.py", "weight": 1.0}
    ]


def test_load_scip_edges_auto_prefers_native_scip_json(tmp_path: Path) -> None:
    payload = {
        "documents": [
            {
                "relative_path": "src/a.py",
                "occurrences": [
                    {"symbol": "demo src/a.py A#", "symbol_roles": 1},
                ],
            }
        ]
    }
    path = tmp_path / "context-map" / "scip" / "native-auto.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scip_edges(path, provider="auto")

    assert loaded["loaded"] is True
    assert loaded["provider"] == "scip"
    assert loaded["schema_version"] == "scip"


def test_load_scip_edges_supports_xref_json(tmp_path: Path) -> None:
    payload = {
        "schema_version": "xref-json-1",
        "edges": [
            {"from": "src/a.py", "to": "src/b.py", "weight": 2},
            {"source": "src/c.py", "target": "src/b.py", "weight": 1},
        ],
    }
    path = tmp_path / "context-map" / "scip" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scip_edges(path, provider="xref_json")

    assert loaded["loaded"] is True
    assert loaded["provider"] == "xref_json"
    assert loaded["edge_count"] == 2
    assert loaded["inbound_counts"]["src/b.py"] == 3.0


def test_load_scip_edges_supports_stack_graphs_json(tmp_path: Path) -> None:
    payload = {
        "schema_version": "stack-graphs-1",
        "graph_edges": [
            {
                "from": {"path": "src/one.py"},
                "to": {"path": "src/two.py"},
            }
        ],
    }
    path = tmp_path / "context-map" / "scip" / "stack.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scip_edges(path, provider="stack_graphs_json")

    assert loaded["loaded"] is True
    assert loaded["provider"] == "stack_graphs_json"
    assert loaded["edge_count"] == 1
    assert loaded["inbound_counts"]["src/two.py"] == 1.0


def test_orchestrator_apply_scip_boost_uses_xref_provider(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    scip_path = tmp_path / "context-map" / "scip" / "external.json"
    scip_path.parent.mkdir(parents=True, exist_ok=True)
    scip_path.write_text(
        json.dumps(
            {
                "schema_version": "xref-json-1",
                "edges": [
                    {"from": "src/a.py", "to": "src/b.py", "weight": 5}
                ],
            }
        ),
        encoding="utf-8",
    )

    files_map = {
        "src/a.py": {"symbols": [{"name": "A", "qualified_name": "src.a.A"}], "references": []},
        "src/b.py": {"symbols": [{"name": "B", "qualified_name": "src.b.B"}], "references": []},
    }
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
    ]

    boosted, payload = apply_scip_boost(
        index_path=scip_path,
        provider="xref_json",
        generate_fallback=False,
        files_map=files_map,
        candidates=candidates,
        policy={"scip_weight": 1.0},
    )

    assert payload["loaded"] is True
    assert payload["provider"] == "xref_json"
    assert payload["fallback_generated"] is False
    assert boosted[0]["path"] == "src/b.py"


def test_orchestrator_apply_scip_boost_surfaces_native_scip_observability(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    scip_path = tmp_path / "context-map" / "scip" / "native.json"
    scip_path.parent.mkdir(parents=True, exist_ok=True)
    scip_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "relative_path": "src/a.py",
                        "occurrences": [
                            {
                                "symbol": "scip-python python demo src/a.py A#",
                                "symbol_roles": 1,
                            },
                            {
                                "symbol": "scip-python python demo src/b.py B#",
                                "symbol_roles": 8,
                            },
                        ],
                    },
                    {
                        "relative_path": "src/b.py",
                        "occurrences": [
                            {
                                "symbol": "scip-python python demo src/b.py B#",
                                "symbol_roles": 1,
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    files_map = {
        "src/a.py": {"symbols": [{"name": "A", "qualified_name": "src.a.A"}], "references": []},
        "src/b.py": {"symbols": [{"name": "B", "qualified_name": "src.b.B"}], "references": []},
    }
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
    ]

    boosted, payload = apply_scip_boost(
        index_path=scip_path,
        provider="scip",
        generate_fallback=False,
        files_map=files_map,
        candidates=candidates,
        policy={"scip_weight": 1.0},
    )

    assert payload["loaded"] is True
    assert payload["provider"] == "scip"
    assert payload["schema_version"] == "scip"
    assert payload["document_count"] == 2
    assert payload["definition_occurrence_count"] == 2
    assert payload["reference_occurrence_count"] == 1
    assert payload["symbol_definition_count"] == 2
    assert boosted[0]["path"] == "src/b.py"


def test_orchestrator_apply_scip_boost_without_fallback_when_missing(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    boosted, payload = apply_scip_boost(
        index_path=tmp_path / "context-map" / "scip" / "missing.json",
        provider="xref_json",
        generate_fallback=False,
        files_map={"src/a.py": {"symbols": [], "references": []}},
        candidates=[{"path": "src/a.py", "score": 1.0, "score_breakdown": {}}],
        policy={"scip_weight": 1.0},
    )

    assert payload["loaded"] is False
    assert payload["fallback_generated"] is False
    assert boosted[0]["path"] == "src/a.py"
