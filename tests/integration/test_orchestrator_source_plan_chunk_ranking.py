from __future__ import annotations

from ace_lite.source_plan import rank_source_plan_chunks


def test_rank_source_plan_chunks_merges_candidate_and_test_scores() -> None:
    ranked = rank_source_plan_chunks(
        candidate_chunks=[
            {
                "path": "src/core/auth.py",
                "qualified_name": "validate_token",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 12,
                "score": 4.0,
            }
        ],
        suspicious_chunks=[
            {
                "path": "src/core/auth.py",
                "qualified_name": "validate_token",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 12,
                "score": 1.5,
            }
        ],
        test_signal_weight=2.0,
    )

    assert len(ranked) == 1
    item = ranked[0]
    assert item["path"] == "src/core/auth.py"
    assert item["score"] == 7.0
    assert item["score_breakdown"]["candidate"] == 4.0
    assert item["score_breakdown"]["test_signal"] == 3.0


def test_rank_source_plan_chunks_test_weight_changes_ordering() -> None:
    candidate_chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "alpha",
            "kind": "function",
            "lineno": 5,
            "end_lineno": 9,
            "score": 3.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "beta",
            "kind": "function",
            "lineno": 20,
            "end_lineno": 24,
            "score": 2.0,
        },
    ]
    suspicious_chunks = [
        {
            "path": "src/b.py",
            "qualified_name": "beta",
            "kind": "function",
            "lineno": 20,
            "end_lineno": 24,
            "score": 1.0,
        }
    ]

    low_weight = rank_source_plan_chunks(
        candidate_chunks=candidate_chunks,
        suspicious_chunks=suspicious_chunks,
        test_signal_weight=0.5,
    )
    assert low_weight[0]["path"] == "src/a.py"

    high_weight = rank_source_plan_chunks(
        candidate_chunks=candidate_chunks,
        suspicious_chunks=suspicious_chunks,
        test_signal_weight=2.0,
    )
    assert high_weight[0]["path"] == "src/b.py"
