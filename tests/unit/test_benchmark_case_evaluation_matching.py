from __future__ import annotations

from ace_lite.benchmark.case_evaluation_matching import (
    collect_candidate_match_details,
    collect_chunk_match_details,
    tokenize,
)


def test_collect_candidate_match_details_reports_relevant_and_noise_paths() -> None:
    details = collect_candidate_match_details(
        top_candidates=[
            {"path": "src/validation.py", "module": "ace.validation.result"},
            {"path": "src/schema.py", "module": "ace.schema"},
        ],
        expected=["validation result"],
        top_k=4,
    )

    assert details["expected_hits"] == ["validation result"]
    assert details["recall_hit"] == 1.0
    assert details["relevant_candidate_paths"] == ["src/validation.py"]
    assert details["noise_candidate_paths"] == ["src/schema.py"]
    assert details["hit_at_1"] == 1.0
    assert details["reciprocal_rank"] == 1.0


def test_collect_chunk_match_details_detects_expected_chunk_hit() -> None:
    details = collect_chunk_match_details(
        top_chunks=[
            {
                "path": "src/validation.py",
                "qualified_name": "build_validation_result",
                "signature": "def build_validation_result() -> dict",
            }
        ],
        expected=["validation result"],
    )

    assert details == {
        "chunk_hits": ["validation result"],
        "chunk_hit_at_k": 1.0,
    }


def test_tokenize_splits_path_and_module_boundaries() -> None:
    assert tokenize("src/ace.validation.py") == {"src", "ace", "validation", "py"}
