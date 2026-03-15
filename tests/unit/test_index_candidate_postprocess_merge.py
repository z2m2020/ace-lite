from __future__ import annotations

from ace_lite.index_stage.candidate_postprocess import merge_candidate_lists


def test_merge_candidate_lists_prefers_higher_score_and_marks_retrieval_pass() -> None:
    merged = merge_candidate_lists(
        primary=[
            {"path": "src/high.py", "score": 9.0},
            {"path": "src/shared.py", "score": 3.0},
        ],
        secondary=[
            {"path": "src/shared.py", "score": 7.0},
            {"path": "src/new.py", "score": 4.0},
        ],
        limit=5,
    )

    assert merged == [
        {"path": "src/high.py", "score": 9.0, "retrieval_pass": "primary"},
        {"path": "src/shared.py", "score": 7.0, "retrieval_pass": "secondary"},
        {"path": "src/new.py", "score": 4.0, "retrieval_pass": "secondary"},
    ]
