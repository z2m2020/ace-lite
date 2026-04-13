"""Compact source-plan card builders for replay and explainability."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

CARD_SCHEMA_VERSION = "y7503-card-v1"


def build_validation_feedback_summary(
    validation_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(validation_result, dict) or not validation_result:
        return {}

    raw_summary = validation_result.get("summary")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    raw_probes = validation_result.get("probes")
    probes = raw_probes if isinstance(raw_probes, dict) else {}
    raw_tests = validation_result.get("tests")
    tests = raw_tests if isinstance(raw_tests, dict) else {}
    selected_tests = tests.get("selected", [])
    executed_tests = tests.get("executed", [])

    return {
        "status": str(summary.get("status") or "").strip() or "skipped",
        "issue_count": int(summary.get("issue_count", 0) or 0),
        "probe_status": str(probes.get("status") or "").strip() or "disabled",
        "probe_issue_count": int(probes.get("issue_count", 0) or 0),
        "probe_executed_count": int(probes.get("executed_count", 0) or 0),
        "selected_test_count": len(selected_tests) if isinstance(selected_tests, list) else 0,
        "executed_test_count": len(executed_tests) if isinstance(executed_tests, list) else 0,
    }


def _chunk_card_id(chunk: dict[str, Any]) -> str:
    path = str(chunk.get("path") or "").strip() or "(unknown)"
    qualified_name = str(chunk.get("qualified_name") or "").strip() or "(unknown)"
    lineno = int(chunk.get("lineno", 0) or 0)
    end_lineno = int(chunk.get("end_lineno", lineno) or lineno)
    return f"{path}:{qualified_name}:{lineno}-{end_lineno}"


def build_chunk_cards(
    *, prioritized_chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for item in prioritized_chunks:
        if not isinstance(item, dict):
            continue
        raw_evidence = item.get("evidence")
        evidence = raw_evidence if isinstance(raw_evidence, dict) else {}
        raw_granularity = evidence.get("granularity")
        granularity = raw_granularity if isinstance(raw_granularity, list) else []
        raw_sources = evidence.get("sources")
        sources = raw_sources if isinstance(raw_sources, list) else []
        cards.append(
            {
                "schema_version": CARD_SCHEMA_VERSION,
                "card_id": _chunk_card_id(item),
                "path": str(item.get("path") or ""),
                "qualified_name": str(item.get("qualified_name") or ""),
                "kind": str(item.get("kind") or ""),
                "lineno": int(item.get("lineno", 0) or 0),
                "end_lineno": int(item.get("end_lineno", item.get("lineno", 0)) or 0),
                "score": round(float(item.get("score", 0.0) or 0.0), 6),
                "evidence_role": str(evidence.get("role") or "unknown"),
                "granularity": [
                    str(value).strip()
                    for value in granularity
                    if str(value).strip()
                ]
                if isinstance(granularity, list)
                else [],
                "sources": [
                    str(value).strip() for value in sources if str(value).strip()
                ]
                if isinstance(sources, list)
                else [],
                "disclosure": str(item.get("disclosure") or "refs"),
                "skeleton_available": isinstance(item.get("skeleton"), dict),
            }
        )
    return cards


def build_file_cards(*, chunk_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in chunk_cards:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        bucket = grouped.setdefault(
            path,
            {
                "schema_version": CARD_SCHEMA_VERSION,
                "card_id": f"file:{path}",
                "path": path,
                "chunk_count": 0,
                "max_score": 0.0,
                "evidence_roles": [],
                "qualified_names": [],
                "chunk_card_ids": [],
            },
        )
        bucket["chunk_count"] = int(bucket.get("chunk_count", 0) or 0) + 1
        bucket["max_score"] = max(
            float(bucket.get("max_score", 0.0) or 0.0),
            float(item.get("score", 0.0) or 0.0),
        )
        role = str(item.get("evidence_role") or "").strip()
        if role and role not in bucket["evidence_roles"]:
            bucket["evidence_roles"].append(role)
        qualified_name = str(item.get("qualified_name") or "").strip()
        if qualified_name and qualified_name not in bucket["qualified_names"]:
            bucket["qualified_names"].append(qualified_name)
        card_id = str(item.get("card_id") or "").strip()
        if card_id and card_id not in bucket["chunk_card_ids"]:
            bucket["chunk_card_ids"].append(card_id)

    return list(grouped.values())


def build_evidence_cards(
    *,
    evidence_summary: dict[str, float],
    file_cards: list[dict[str, Any]],
    chunk_cards: list[dict[str, Any]],
    validation_feedback_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    file_paths = [
        str(item.get("path") or "")
        for item in file_cards
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]
    chunk_card_ids = [
        str(item.get("card_id") or "")
        for item in chunk_cards
        if isinstance(item, dict) and str(item.get("card_id") or "").strip()
    ][:12]
    retrieval_card = {
        "schema_version": CARD_SCHEMA_VERSION,
        "card_id": "evidence:retrieval_grounding",
        "card_type": "evidence",
        "topic": "retrieval_grounding",
        "title": "Retrieval Grounding",
        "summary": (
            "direct={direct}; neighbor={neighbor}; hint_only={hint} across {count} chunks"
        ).format(
            direct=int(evidence_summary.get("direct_count", 0.0) or 0.0),
            neighbor=int(evidence_summary.get("neighbor_context_count", 0.0) or 0.0),
            hint=int(evidence_summary.get("hint_only_count", 0.0) or 0.0),
            count=len(chunk_cards),
        ),
        "metrics": {
            "direct_count": round(float(evidence_summary.get("direct_count", 0.0) or 0.0), 6),
            "neighbor_context_count": round(
                float(evidence_summary.get("neighbor_context_count", 0.0) or 0.0), 6
            ),
            "hint_only_count": round(
                float(evidence_summary.get("hint_only_count", 0.0) or 0.0), 6
            ),
            "file_card_count": float(len(file_cards)),
            "chunk_card_count": float(len(chunk_cards)),
        },
        "file_paths": file_paths,
        "chunk_card_ids": chunk_card_ids,
    }
    cards = [retrieval_card]

    if validation_feedback_summary:
        cards.append(
            {
                "schema_version": CARD_SCHEMA_VERSION,
                "card_id": "evidence:validation_feedback",
                "card_type": "evidence",
                "topic": "validation_feedback",
                "title": "Validation Feedback",
                "summary": (
                    "status={status}; issues={issues}; probe={probe}; executed_tests={tests}"
                ).format(
                    status=str(validation_feedback_summary.get("status") or "skipped"),
                    issues=int(validation_feedback_summary.get("issue_count", 0) or 0),
                    probe=str(validation_feedback_summary.get("probe_status") or "disabled"),
                    tests=int(
                        validation_feedback_summary.get("executed_test_count", 0) or 0
                    ),
                ),
                "metrics": {
                    key: (
                        round(float(value or 0.0), 6)
                        if isinstance(value, (int, float))
                        else value
                    )
                    for key, value in validation_feedback_summary.items()
                },
                "file_paths": [],
                "chunk_card_ids": [],
            }
        )
    return cards


def build_source_plan_cards(
    *,
    prioritized_chunks: list[dict[str, Any]],
    evidence_summary: dict[str, float],
    validation_result: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    validation_feedback_summary = build_validation_feedback_summary(validation_result)
    chunk_cards = build_chunk_cards(prioritized_chunks=prioritized_chunks)
    file_cards = build_file_cards(chunk_cards=chunk_cards)
    evidence_cards = build_evidence_cards(
        evidence_summary=evidence_summary,
        file_cards=file_cards,
        chunk_cards=chunk_cards,
        validation_feedback_summary=validation_feedback_summary,
    )
    card_summary = {
        "schema_version": CARD_SCHEMA_VERSION,
        "evidence_card_count": len(evidence_cards),
        "file_card_count": len(file_cards),
        "chunk_card_count": len(chunk_cards),
        "validation_card_present": bool(validation_feedback_summary),
    }
    return evidence_cards, file_cards, chunk_cards, card_summary


__all__ = [
    "CARD_SCHEMA_VERSION",
    "build_chunk_cards",
    "build_evidence_cards",
    "build_file_cards",
    "build_source_plan_cards",
    "build_validation_feedback_summary",
]
