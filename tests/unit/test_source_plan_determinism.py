from __future__ import annotations

from itertools import permutations

from ace_lite.source_plan.chunk_ranking import (
    pack_source_plan_chunks,
    rank_source_plan_chunks,
)


def _pack_signature(items: list[dict[str, object]]) -> list[tuple[str, str, float]]:
    return [
        (
            str(item.get("path") or ""),
            str(item.get("qualified_name") or ""),
            float(item.get("score") or 0.0),
        )
        for item in items
    ]


def test_source_plan_packing_is_deterministic_across_repeated_rank_inputs() -> None:
    candidate_chunks = [
        {
            "path": "src/alpha.py",
            "qualified_name": "anchor_alpha",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 18,
            "score": 1.2,
            "score_breakdown": {"candidate": 1.2},
        },
        {
            "path": "src/alpha.py",
            "qualified_name": "support_alpha",
            "kind": "function",
            "lineno": 30,
            "end_lineno": 38,
            "score": 0.8,
            "score_breakdown": {
                "candidate": 0.8,
                "graph_closure_bonus": 0.3,
            },
        },
        {
            "path": "src/beta.py",
            "qualified_name": "anchor_beta",
            "kind": "function",
            "lineno": 20,
            "end_lineno": 28,
            "score": 1.4,
            "score_breakdown": {"candidate": 1.4},
        },
    ]
    suspicious_chunks = [
        {
            "path": "src/beta.py",
            "qualified_name": "anchor_beta",
            "kind": "function",
            "lineno": 20,
            "end_lineno": 28,
            "score": 0.4,
        },
        {
            "path": "src/alpha.py",
            "qualified_name": "support_alpha",
            "kind": "function",
            "lineno": 30,
            "end_lineno": 38,
            "score": 0.2,
        },
    ]

    expected_signature: list[tuple[str, str, float]] | None = None
    expected_metadata: dict[str, object] | None = None

    for candidate_order in permutations(candidate_chunks):
        for suspicious_order in permutations(suspicious_chunks):
            ranked = rank_source_plan_chunks(
                suspicious_chunks=[dict(item) for item in suspicious_order],
                candidate_chunks=[dict(item) for item in candidate_order],
                test_signal_weight=1.0,
            )
            packed, metadata = pack_source_plan_chunks(
                prioritized_chunks=ranked,
                focused_files=["src/alpha.py", "src/beta.py"],
                chunk_top_k=3,
                graph_closure_preference_enabled=True,
                return_metadata=True,
            )
            signature = _pack_signature(packed)
            if expected_signature is None:
                expected_signature = signature
                expected_metadata = metadata
                continue
            assert signature == expected_signature
            assert metadata == expected_metadata

    assert expected_signature == [
        ("src/alpha.py", "anchor_alpha", 1.2),
        ("src/alpha.py", "support_alpha", 1.0),
        ("src/beta.py", "anchor_beta", 1.8),
    ]
    assert expected_metadata is not None
    assert expected_metadata["graph_closure_preference_enabled"] is True
    assert expected_metadata["graph_closure_bonus_candidate_count"] == 1
    assert expected_metadata["graph_closure_preferred_count"] == 1
    assert expected_metadata["focused_file_promoted_count"] == 2
    assert expected_metadata["packed_path_count"] == 2
    assert str(expected_metadata.get("reason") or "").strip()
