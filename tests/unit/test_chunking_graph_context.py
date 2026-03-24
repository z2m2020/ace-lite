from __future__ import annotations

import json
from pathlib import Path

from ace_lite.chunking.graph_context import get_graph_context


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


def test_get_graph_context_defaults_to_adjacency_provider() -> None:
    context = get_graph_context(
        files_map=_files_map(),
        cache_key="graph-context-default",
        policy={},
    )

    assert context["loaded"] is True
    assert context["provider_requested"] == "auto"
    assert context["provider_selected"] == "adjacency"
    assert context["provider_fallback"] is False
    assert context["fallback_reason"] == ""
    assert context["graph_scope"] == "symbol"
    assert context["adjacency"]


def test_get_graph_context_falls_back_from_scip_to_adjacency() -> None:
    context = get_graph_context(
        files_map=_files_map(),
        cache_key="graph-context-scip",
        policy={"chunk_graph_context_provider": "scip"},
    )

    assert context["loaded"] is True
    assert context["provider_requested"] == "scip"
    assert context["provider_selected"] == "adjacency"
    assert context["provider_fallback"] is True
    assert context["fallback_reason"] == "scip_source_unavailable"
    assert context["graph_scope"] == "symbol"
    assert context["adjacency"]


def test_get_graph_context_loads_native_scip_source_with_projection_fallback(
    tmp_path: Path,
) -> None:
    scip_path = tmp_path / "context-map" / "scip" / "index.json"
    scip_path.parent.mkdir(parents=True, exist_ok=True)
    scip_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "relative_path": "src/a.py",
                        "occurrences": [
                            {"symbol": "demo src/a.py A#", "symbol_roles": 1},
                            {"symbol": "demo src/b.py B#", "symbol_roles": 8},
                        ],
                    },
                    {
                        "relative_path": "src/b.py",
                        "occurrences": [
                            {"symbol": "demo src/b.py B#", "symbol_roles": 1},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    context = get_graph_context(
        root=str(tmp_path),
        files_map=_files_map(),
        cache_key="graph-context-native-scip",
        policy={
            "chunk_graph_context_provider": "scip",
            "scip_index_path": "context-map/scip/index.json",
        },
    )

    assert context["provider_requested"] == "scip"
    assert context["provider_selected"] == "adjacency"
    assert context["provider_fallback"] is True
    assert context["fallback_reason"] == "file_scope_symbol_projection_pending"
    assert context["source_provider_selected"] == "scip"
    assert context["source_provider_loaded"] is True
    assert context["source_graph_scope"] == "file"
    assert context["source_edge_count"] == 1
    assert context["source_projection_fallback"] is True
    assert context["source_projection_reason"] == "file_scope_symbol_projection_pending"
    assert context["file_adjacency"] == {"src/a.py": ["src/b.py"]}
