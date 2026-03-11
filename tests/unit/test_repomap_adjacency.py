from __future__ import annotations

from ace_lite.repomap.adjacency import (
    _assign_references_to_enclosing_symbols,
    _build_symbol_adjacency,
)
from ace_lite.repomap.builder import build_stage_precompute_payload


def test_assign_references_to_enclosing_symbols_prefers_narrowest_span() -> None:
    files = {
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [
                {
                    "name": "Service",
                    "qualified_name": "src.use.Service",
                    "kind": "class",
                    "lineno": 1,
                    "end_lineno": 30,
                },
                {
                    "name": "handle",
                    "qualified_name": "src.use.Service.handle",
                    "kind": "method",
                    "lineno": 10,
                    "end_lineno": 20,
                },
            ],
            "references": [
                {
                    "name": "Foo",
                    "qualified_name": "src.defs.Foo",
                    "lineno": 12,
                    "kind": "call",
                },
                {
                    "name": "Bar",
                    "qualified_name": "src.defs.Bar",
                    "lineno": 28,
                    "kind": "reference",
                },
            ],
        }
    }

    assignments = _assign_references_to_enclosing_symbols(files=files)

    class_id = "src/use.py|1|30|src.use.Service"
    method_id = "src/use.py|10|20|src.use.Service.handle"

    assert assignments[method_id] == [
        {
            "path": "src/use.py",
            "lineno": 12,
            "name": "Foo",
            "qualified_name": "src.defs.Foo",
            "kind": "call",
        }
    ]
    assert assignments[class_id] == [
        {
            "path": "src/use.py",
            "lineno": 28,
            "name": "Bar",
            "qualified_name": "src.defs.Bar",
            "kind": "reference",
        }
    ]


def test_build_symbol_adjacency_orders_equal_weight_targets_deterministically() -> None:
    files = {
        "src/defs/beta.py": {
            "module": "src.defs.beta",
            "language": "python",
            "symbols": [
                {
                    "name": "Beta",
                    "qualified_name": "src.defs.beta.Beta",
                    "kind": "class",
                    "lineno": 1,
                    "end_lineno": 3,
                }
            ],
            "references": [],
        },
        "src/defs/alpha.py": {
            "module": "src.defs.alpha",
            "language": "python",
            "symbols": [
                {
                    "name": "Alpha",
                    "qualified_name": "src.defs.alpha.Alpha",
                    "kind": "class",
                    "lineno": 1,
                    "end_lineno": 3,
                }
            ],
            "references": [],
        },
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [
                {
                    "name": "run",
                    "qualified_name": "src.use.run",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 10,
                }
            ],
            "references": [
                {
                    "name": "Beta",
                    "qualified_name": "src.defs.beta.Beta",
                    "lineno": 4,
                    "kind": "reference",
                },
                {
                    "name": "Alpha",
                    "qualified_name": "src.defs.alpha.Alpha",
                    "lineno": 5,
                    "kind": "reference",
                },
            ],
        },
    }

    adjacency = _build_symbol_adjacency(files=files)

    source_id = "src/use.py|1|10|src.use.run"
    alpha_id = "src/defs/alpha.py|1|3|src.defs.alpha.Alpha"
    beta_id = "src/defs/beta.py|1|3|src.defs.beta.Beta"

    assert adjacency[source_id] == [alpha_id, beta_id]


def test_symbol_adjacency_fails_open_for_missing_or_malformed_graph_data() -> None:
    files = {
        "src/broken.py": {
            "module": "src.broken",
            "language": "python",
            "symbols": [
                {
                    "name": "broken",
                    "qualified_name": "src.broken.broken",
                    "kind": "function",
                    "lineno": 0,
                    "end_lineno": 0,
                }
            ],
            "references": [{"name": "Ghost", "qualified_name": "src.ghost.Ghost", "lineno": 1}],
        },
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [
                {
                    "name": "run",
                    "qualified_name": "src.use.run",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 5,
                }
            ],
            "references": [
                {"name": "Ghost", "qualified_name": "src.ghost.Ghost", "lineno": "bad"},
                {"name": "Ghost", "qualified_name": "src.ghost.Ghost", "lineno": 3},
            ],
        },
    }

    assignments = _assign_references_to_enclosing_symbols(files=files)
    adjacency = _build_symbol_adjacency(files=files)

    source_id = "src/use.py|1|5|src.use.run"

    assert assignments == {
        source_id: [
            {
                "path": "src/use.py",
                "lineno": 3,
                "name": "Ghost",
                "qualified_name": "src.ghost.Ghost",
                "kind": "reference",
            }
        ]
    }
    assert adjacency == {source_id: []}


def test_build_stage_precompute_payload_caches_symbol_adjacency() -> None:
    files = {
        "src/defs/foo.py": {
            "module": "src.defs.foo",
            "language": "python",
            "symbols": [
                {
                    "name": "Foo",
                    "qualified_name": "src.defs.foo.Foo",
                    "kind": "class",
                    "lineno": 1,
                    "end_lineno": 4,
                }
            ],
            "references": [],
        },
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [
                {
                    "name": "run",
                    "qualified_name": "src.use.run",
                    "kind": "function",
                    "lineno": 1,
                    "end_lineno": 8,
                }
            ],
            "references": [
                {
                    "name": "Foo",
                    "qualified_name": "src.defs.foo.Foo",
                    "lineno": 3,
                    "kind": "call",
                }
            ],
        },
    }

    payload = build_stage_precompute_payload(
        index_files=files,
        ranking_profile="graph",
    )

    source_id = "src/use.py|1|8|src.use.run"
    target_id = "src/defs/foo.py|1|4|src.defs.foo.Foo"

    assert payload["symbol_adjacency"] == {source_id: [target_id], target_id: []}
