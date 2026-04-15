"""Report-only context_refine stage.

This stage formalizes Wave 1 candidate-review heuristics into a dedicated
pipeline step that sits between ``skills`` and ``source_plan``. The output is
additive and observational only: downstream stages may read it, but it must
not directly change candidate ranking or gating decisions.
"""

from __future__ import annotations

from typing import Any

from ace_lite.pipeline.types import StageContext


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: Any) -> str:
    return str(value) if value is not None else ""


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_path(value: Any) -> str:
    return _str(value).strip().replace("\\", "/").lstrip("./")


def _resolve_focused_files(*, repomap_stage: dict[str, Any], index_stage: dict[str, Any]) -> list[str]:
    focused = repomap_stage.get("focused_files")
    if isinstance(focused, list) and focused:
        return [_normalize_path(item) for item in focused if _normalize_path(item)]

    candidates = index_stage.get("candidate_files")
    if not isinstance(candidates, list):
        return []
    return [
        _normalize_path(item.get("path"))
        for item in candidates
        if isinstance(item, dict) and _normalize_path(item.get("path"))
    ]


def _positive_signal_names(
    breakdown: dict[str, Any],
    *,
    names: tuple[str, ...],
) -> list[str]:
    signals: list[str] = []
    for name in names:
        if _float(breakdown.get(name, 0.0), 0.0) > 0.0:
            signals.append(name)
    return signals


def _classify_action(
    *,
    score: float,
    focused: bool,
    strong_signals: list[str],
    support_signals: list[str],
    is_test_path: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if focused:
        reasons.append("focused_file")
    reasons.extend(strong_signals)
    reasons.extend(support_signals)

    if focused and (strong_signals or score >= 0.6):
        return "keep", reasons or ["focused_file"]
    if strong_signals and score >= 0.25:
        return "need_more_read", reasons or ["strong_signal"]
    if focused and (support_signals or score >= 0.15):
        return "need_more_read", reasons or ["focused_file"]
    if is_test_path and not focused and not strong_signals:
        return "drop", reasons or ["test_only_noise"]
    if support_signals or score >= 0.1:
        return "downrank", reasons or ["weak_signal"]
    return "drop", reasons or ["no_grounding_signal"]


def _build_file_actions(
    *,
    candidate_files: list[dict[str, Any]],
    focused_files: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    focused_set = {_normalize_path(item) for item in focused_files if _normalize_path(item)}
    actions: list[dict[str, Any]] = []
    for item in candidate_files[: max(1, int(limit))]:
        if not isinstance(item, dict):
            continue
        path = _normalize_path(item.get("path"))
        if not path:
            continue
        score = _float(item.get("score", 0.0), 0.0)
        breakdown = _dict(item.get("score_breakdown"))
        strong_signals = _positive_signal_names(
            breakdown,
            names=("candidate", "path_exact", "symbol_exact", "exact_search"),
        )
        support_signals = _positive_signal_names(
            breakdown,
            names=("file_prior", "cochange", "docs_hint", "worktree_prior"),
        )
        action, reasons = _classify_action(
            score=score,
            focused=(path in focused_set),
            strong_signals=strong_signals,
            support_signals=support_signals,
            is_test_path=("/tests/" in f"/{path}" or path.startswith("tests/")),
        )
        actions.append(
            {
                "path": path,
                "score": score,
                "action": action,
                "focused": path in focused_set,
                "reasons": reasons,
            }
        )
    return actions


def _build_chunk_actions(
    *,
    candidate_chunks: list[dict[str, Any]],
    focused_files: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    focused_set = {_normalize_path(item) for item in focused_files if _normalize_path(item)}
    actions: list[dict[str, Any]] = []
    for item in candidate_chunks[: max(1, int(limit))]:
        if not isinstance(item, dict):
            continue
        path = _normalize_path(item.get("path"))
        if not path:
            continue
        qualified_name = _str(item.get("qualified_name")).strip()
        score = _float(item.get("score", 0.0), 0.0)
        breakdown = _dict(item.get("score_breakdown"))
        strong_signals = _positive_signal_names(
            breakdown,
            names=(
                "candidate",
                "path_exact",
                "symbol_exact",
                "chunk_path_match",
                "chunk_symbol_exact",
                "exact_search",
                "test_signal",
            ),
        )
        support_signals = _positive_signal_names(
            breakdown,
            names=("file_prior", "cochange", "graph_closure_bonus", "docs_hint"),
        )
        action, reasons = _classify_action(
            score=score,
            focused=(path in focused_set),
            strong_signals=strong_signals,
            support_signals=support_signals,
            is_test_path=("/tests/" in f"/{path}" or path.startswith("tests/")),
        )
        actions.append(
            {
                "path": path,
                "qualified_name": qualified_name,
                "score": score,
                "action": action,
                "focused": path in focused_set,
                "reasons": reasons,
            }
        )
    return actions


def _build_decision_counts(
    *,
    file_actions: list[dict[str, Any]],
    chunk_actions: list[dict[str, Any]],
) -> dict[str, int]:
    counts = {"keep": 0, "downrank": 0, "drop": 0, "need_more_read": 0}
    for item in [*file_actions, *chunk_actions]:
        action = _str(_dict(item).get("action")).strip().lower()
        if action in counts:
            counts[action] += 1
    return counts


def _build_candidate_review(
    *,
    focused_files: list[str],
    file_actions: list[dict[str, Any]],
    chunk_actions: list[dict[str, Any]],
    diagnostics: list[Any],
    suspicious_chunks: list[Any],
) -> dict[str, Any]:
    decision_counts = _build_decision_counts(
        file_actions=file_actions,
        chunk_actions=chunk_actions,
    )
    watch_items: list[str] = []
    recommendations: list[str] = []

    status = "ok"
    if not focused_files or not chunk_actions:
        status = "thin_context"
        watch_items.append("missing_focus_or_chunks")
        recommendations.append("Inspect entrypoint files before trusting the shortlist.")
    if decision_counts["drop"] > 0:
        status = "watch"
        watch_items.append("drop_candidates_present")
        recommendations.append("Ignore low-signal candidates unless direct evidence appears.")
    if decision_counts["downrank"] > 0:
        status = "watch"
        watch_items.append("downrank_candidates_present")
        recommendations.append("Review downranked items only after keep candidates are exhausted.")
    if decision_counts["need_more_read"] > 0:
        watch_items.append("need_more_read_candidates_present")
        recommendations.append("Open need-more-read candidates before editing to confirm intent.")
    if suspicious_chunks:
        status = "watch"
        watch_items.append("augment_suspicious_chunks_present")
        recommendations.append("Cross-check suspicious test-linked chunks before widening the patch.")
    if diagnostics:
        watch_items.append("augment_diagnostics_present")
    if not recommendations:
        recommendations.append("Shortlist looks stable enough for manual review.")

    deduped_watch_items: list[str] = []
    seen_watch_items: set[str] = set()
    for item in watch_items:
        normalized = _str(item).strip()
        if not normalized or normalized in seen_watch_items:
            continue
        seen_watch_items.add(normalized)
        deduped_watch_items.append(normalized)

    deduped_recommendations: list[str] = []
    seen_recommendations: set[str] = set()
    for item in recommendations:
        normalized = _str(item).strip()
        if not normalized or normalized in seen_recommendations:
            continue
        seen_recommendations.add(normalized)
        deduped_recommendations.append(normalized)

    return {
        "schema_version": "candidate_review_v2",
        "status": status,
        "focus_file_count": len(focused_files),
        "candidate_file_count": len(file_actions),
        "candidate_chunk_count": len(chunk_actions),
        "validation_test_count": 0,
        "direct_ratio": 0.0,
        "neighbor_context_ratio": 0.0,
        "hint_only_ratio": 0.0,
        "failure_feedback_present": False,
        "watch_items": deduped_watch_items[:6],
        "recommendations": deduped_recommendations[:6],
        "decision_counts": dict(decision_counts),
        "candidate_file_actions": [dict(item) for item in file_actions[:8]],
        "candidate_chunk_actions": [dict(item) for item in chunk_actions[:12]],
    }


def run_context_refine(*, ctx: StageContext) -> dict[str, Any]:
    index_stage = _dict(ctx.state.get("index"))
    repomap_stage = _dict(ctx.state.get("repomap"))
    augment_stage = _dict(ctx.state.get("augment"))

    focused_files = _resolve_focused_files(
        repomap_stage=repomap_stage,
        index_stage=index_stage,
    )
    candidate_files = [
        item for item in _list(index_stage.get("candidate_files")) if isinstance(item, dict)
    ]
    candidate_chunks = [
        item for item in _list(index_stage.get("candidate_chunks")) if isinstance(item, dict)
    ]
    diagnostics = _list(augment_stage.get("diagnostics"))
    tests = _dict(augment_stage.get("tests"))
    suspicious_chunks = _list(tests.get("suspicious_chunks"))
    policy_name = _str(index_stage.get("policy_name")).strip() or "general"
    policy_version = _str(index_stage.get("policy_version")).strip() or "1"

    file_actions = _build_file_actions(
        candidate_files=candidate_files,
        focused_files=focused_files,
        limit=8,
    )
    chunk_actions = _build_chunk_actions(
        candidate_chunks=candidate_chunks,
        focused_files=focused_files,
        limit=12,
    )
    decision_counts = _build_decision_counts(
        file_actions=file_actions,
        chunk_actions=chunk_actions,
    )
    candidate_review = _build_candidate_review(
        focused_files=focused_files,
        file_actions=file_actions,
        chunk_actions=chunk_actions,
        diagnostics=diagnostics,
        suspicious_chunks=suspicious_chunks,
    )

    return {
        "enabled": True,
        "reason": "report_only",
        "focused_files": list(focused_files),
        "candidate_file_actions": [dict(item) for item in file_actions],
        "candidate_chunk_actions": [dict(item) for item in chunk_actions],
        "decision_counts": dict(decision_counts),
        "candidate_review": candidate_review,
        "policy_name": policy_name,
        "policy_version": policy_version,
    }


__all__ = ["run_context_refine"]
