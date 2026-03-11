from __future__ import annotations

from ace_lite.chunking.scoring import build_chunk_step_reason
from ace_lite.explainability import attach_selection_why, build_selection_reason


def test_build_selection_reason_normalizes_signal_order() -> None:
    item = {
        "score_breakdown": {
            "scip_pagerank": 0.5,
            "exact_search": 0.2,
            "path_prior": 1.0,
            "content": 2.0,
            "prior_feedback": 0.1,
            "matched_terms": 3,
            "ranker": 1.0,
        },
        "score_embedding": 0.8,
        "score_fused": 0.7,
    }

    assert (
        build_selection_reason(item, default_reason="ranked_file_candidate")
        == "signals:path,lexical,exact,graph,semantic,feedback,fusion"
    )


def test_build_selection_reason_falls_back_to_retrieval_pass() -> None:
    item = {"retrieval_pass": "secondary"}

    assert (
        build_selection_reason(item, default_reason="ranked_file_candidate")
        == "retrieval:secondary"
    )


def test_attach_selection_why_copies_rows_without_mutating_input() -> None:
    rows = [{"path": "src/app.py", "score_breakdown": {"path": 1.0}}]

    annotated = attach_selection_why(rows, default_reason="ranked_file_candidate")

    assert rows[0].get("why") is None
    assert annotated[0]["why"] == "signals:path"


def test_build_chunk_step_reason_ignores_budget_and_policy_metadata() -> None:
    item = {
        "score_breakdown": {
            "file_prior": 0.6,
            "path": 1.0,
            "estimated_tokens": 42,
            "policy_chunk_weight": 1.0,
            "diversity_selected": 1.0,
        }
    }

    assert build_chunk_step_reason(item) == "signals:file,path"
