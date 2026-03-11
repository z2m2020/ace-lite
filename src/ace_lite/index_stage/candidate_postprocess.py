"""Candidate postprocess helpers for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

RankCandidatesFn = Callable[..., list[dict[str, Any]]]
MergeCandidateListsFn = Callable[..., list[dict[str, Any]]]


@dataclass(slots=True)
class CandidatePostprocessResult:
    candidates: list[dict[str, Any]]
    second_pass_payload: dict[str, Any]
    refine_pass_payload: dict[str, Any]


def postprocess_candidates(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, Any],
    selected_ranker: str,
    top_k_files: int,
    candidate_relative_threshold: float,
    refine_enabled: bool,
    rank_candidates: RankCandidatesFn,
    merge_candidate_lists: MergeCandidateListsFn,
) -> CandidatePostprocessResult:
    """Apply threshold filtering and low-candidate second-pass expansion."""

    processed_candidates = [dict(item) for item in candidates]
    second_pass_payload: dict[str, Any] = {
        "triggered": False,
        "applied": False,
        "reason": "",
        "retry_ranker": "",
        "candidate_count_before": 0,
        "candidate_count_after": 0,
    }
    refine_pass_payload: dict[str, Any] = {
        "enabled": bool(refine_enabled),
        "trigger_condition_met": False,
        "triggered": False,
        "applied": False,
        "reason": "",
        "retry_ranker": "",
        "candidate_count_before": 0,
        "candidate_count_after": 0,
        "max_passes": 1,
    }

    relative_threshold = float(candidate_relative_threshold)
    if processed_candidates and relative_threshold > 0.0:
        max_score = float(processed_candidates[0].get("score") or 0.0)
        cutoff = max_score * relative_threshold
        if cutoff > 0:
            kept = [
                item
                for item in processed_candidates
                if float(item.get("score") or 0.0) >= cutoff
            ]
            if kept:
                processed_candidates = kept

    desired_count = max(2, min(6, int(top_k_files)))
    if files_map and len(processed_candidates) < desired_count:
        retry_ranker = "hybrid_re2" if selected_ranker != "hybrid_re2" else "heuristic"
        before_count = len(processed_candidates)
        refine_pass_payload = {
            "enabled": bool(refine_enabled),
            "trigger_condition_met": True,
            "triggered": bool(refine_enabled),
            "applied": False,
            "reason": "low_candidate_count" if refine_enabled else "disabled",
            "retry_ranker": retry_ranker,
            "candidate_count_before": before_count,
            "candidate_count_after": before_count,
            "max_passes": 1,
        }
        if refine_enabled:
            retry_candidates = rank_candidates(min_score=0, candidate_ranker=retry_ranker)
            merged = merge_candidate_lists(
                primary=processed_candidates,
                secondary=retry_candidates,
                limit=max(int(top_k_files) * 4, int(top_k_files) + 8),
            )
            refine_pass_payload["applied"] = len(merged) > before_count
            refine_pass_payload["candidate_count_after"] = len(merged)
            second_pass_payload = {
                "triggered": True,
                "applied": len(merged) > before_count,
                "reason": "low_candidate_count",
                "retry_ranker": retry_ranker,
                "candidate_count_before": before_count,
                "candidate_count_after": len(merged),
            }
            if len(merged) > before_count:
                processed_candidates = merged

    return CandidatePostprocessResult(
        candidates=processed_candidates,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
    )


__all__ = ["CandidatePostprocessResult", "postprocess_candidates"]
