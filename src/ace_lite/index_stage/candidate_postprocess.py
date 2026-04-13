"""Candidate postprocess helpers for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

RankCandidatesFn = Callable[..., list[dict[str, Any]]]
MergeCandidateListsFn = Callable[..., list[dict[str, Any]]]


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(slots=True)
class CandidatePostprocessResult:
    candidates: list[dict[str, Any]]
    second_pass_payload: dict[str, Any]
    refine_pass_payload: dict[str, Any]
    retrieval_refinement_payload: dict[str, Any]


def _normalize_focus_paths(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        path = str(item or "").strip().replace("\\", "/")
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def _apply_retrieval_refinement(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, Any],
    retrieval_refinement: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload: dict[str, Any] = {
        "enabled": bool(isinstance(retrieval_refinement, dict) and retrieval_refinement),
        "applied": False,
        "reason": "disabled",
        "schema_version": "",
        "iteration_index": 0,
        "action_type": "",
        "query_hint": "",
        "focus_paths": [],
        "boosted_paths": [],
        "injected_paths": [],
        "candidate_count_before": len(candidates),
        "candidate_count_after": len(candidates),
    }
    processed = [dict(item) for item in candidates]
    if not isinstance(retrieval_refinement, dict) or not retrieval_refinement:
        return processed, payload

    focus_paths = _normalize_focus_paths(retrieval_refinement.get("focus_paths"))
    payload.update(
        {
            "schema_version": str(
                retrieval_refinement.get("schema_version") or ""
            ).strip(),
            "iteration_index": max(
                0, int(retrieval_refinement.get("iteration_index", 0) or 0)
            ),
            "action_type": str(retrieval_refinement.get("action_type") or "").strip(),
            "query_hint": str(retrieval_refinement.get("query_hint") or "").strip(),
            "focus_paths": list(focus_paths),
        }
    )
    if not focus_paths:
        payload["reason"] = "no_focus_paths"
        return processed, payload

    focus_order = {path: index for index, path in enumerate(focus_paths)}
    focus_set = set(focus_order)
    existing_paths = {
        str(item.get("path") or "").strip().replace("\\", "/")
        for item in processed
        if isinstance(item, dict)
    }
    max_score = max(
        (float(item.get("score") or 0.0) for item in processed if isinstance(item, dict)),
        default=1.0,
    )
    injected_paths: list[str] = []
    for path in focus_paths:
        if path in existing_paths or path not in files_map:
            continue
        entry = files_map.get(path, {})
        injected_candidate = {
            "path": path,
            "module": str(entry.get("module") or "").strip(),
            "language": str(entry.get("language") or "").strip(),
            "score": float(max_score + 1.0 - (focus_order.get(path, 0) * 0.001)),
            "retrieval_pass": "agent_loop_focus",
            "score_breakdown": {
                "agent_loop_focus": float(
                    round(max_score + 1.0 - (focus_order.get(path, 0) * 0.001), 6)
                )
            },
            "selection_reason": "agent_loop_retrieval_refinement",
        }
        processed.append(injected_candidate)
        existing_paths.add(path)
        injected_paths.append(path)

    boosted_paths: list[str] = []
    for item in processed:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if path not in focus_set:
            continue
        boosted_paths.append(path)
        item["agent_loop_focus"] = True
        item["agent_loop_focus_rank"] = int(focus_order.get(path, 0))
        breakdown = _coerce_mapping(item.get("score_breakdown"))
        breakdown["agent_loop_focus"] = float(
            round(max_score + 1.0 - (focus_order.get(path, 0) * 0.001), 6)
        )
        item["score_breakdown"] = breakdown

    if not boosted_paths:
        payload["reason"] = "no_matching_focus_paths"
        return processed, payload

    processed.sort(
        key=lambda item: (
            0
            if str(item.get("path") or "").strip().replace("\\", "/") in focus_set
            else 1,
            int(
                focus_order.get(
                    str(item.get("path") or "").strip().replace("\\", "/"),
                    9999,
                )
            ),
            -float(item.get("score") or 0.0),
            str(item.get("path") or "").strip().replace("\\", "/"),
        )
    )
    payload.update(
        {
            "applied": True,
            "reason": "ok",
            "boosted_paths": list(dict.fromkeys(boosted_paths)),
            "injected_paths": list(injected_paths),
            "candidate_count_after": len(processed),
        }
    )
    return processed, payload


def merge_candidate_lists(
    *,
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    merged_by_path: dict[str, dict[str, Any]] = {}
    for source_name, rows in (("primary", primary), ("secondary", secondary)):
        for row in rows:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "").strip()
            if not path:
                continue
            score = float(row.get("score") or 0.0)
            existing = merged_by_path.get(path)
            if existing is None or float(existing.get("score") or 0.0) < score:
                payload = dict(row)
                payload["retrieval_pass"] = source_name
                merged_by_path[path] = payload

    merged = list(merged_by_path.values())
    merged.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
        )
    )
    return merged[:limit]


def postprocess_candidates(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, Any],
    selected_ranker: str,
    top_k_files: int,
    candidate_relative_threshold: float,
    refine_enabled: bool,
    retrieval_refinement: dict[str, Any] | None = None,
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

    processed_candidates, retrieval_refinement_payload = _apply_retrieval_refinement(
        candidates=processed_candidates,
        files_map=files_map,
        retrieval_refinement=retrieval_refinement,
    )

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
        retrieval_refinement_payload=retrieval_refinement_payload,
    )

__all__ = [
    "CandidatePostprocessResult",
    "merge_candidate_lists",
    "postprocess_candidates",
]
