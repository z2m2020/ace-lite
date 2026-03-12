from __future__ import annotations

from ace_lite.scip.subgraph import (
    SUBGRAPH_EDGE_TAXONOMY_VERSION,
    SUBGRAPH_PAYLOAD_VERSION,
    build_subgraph_payload,
)


def test_build_subgraph_payload_is_fail_open_without_graph_signals() -> None:
    payload = build_subgraph_payload(
        candidate_files=[{"path": "src/auth.py"}],
        candidate_chunks=[{"path": "src/auth.py", "qualified_name": "validate"}],
        graph_lookup_payload={},
    )

    assert payload == {
        "payload_version": SUBGRAPH_PAYLOAD_VERSION,
        "taxonomy_version": SUBGRAPH_EDGE_TAXONOMY_VERSION,
        "enabled": False,
        "reason": "disabled",
        "seed_paths": [],
        "edge_counts": {},
    }


def test_build_subgraph_payload_deduplicates_paths_across_file_and_chunk_rows() -> None:
    payload = build_subgraph_payload(
        candidate_files=[
            {"path": "src/auth.py", "score_breakdown": {"graph_lookup": 0.3}},
            {"path": "src/session.py", "score_breakdown": {"graph_lookup": 0.2}},
        ],
        candidate_chunks=[
            {
                "path": "src/auth.py",
                "qualified_name": "validate_token",
                "score_breakdown": {
                    "graph_lookup": 0.25,
                    "graph_prior": 0.15,
                    "graph_closure_bonus": 0.1,
                },
            }
        ],
        graph_lookup_payload={
            "enabled": True,
            "reason": "ok",
            "boosted_count": 3,
            "query_hit_paths": 2,
        },
    )

    assert payload["enabled"] is True
    assert payload["reason"] == "ok"
    assert payload["seed_paths"] == ["src/auth.py", "src/session.py"]
    assert payload["edge_counts"] == {
        "graph_lookup": 2,
        "graph_prior": 1,
        "graph_closure_bonus": 1,
    }
