from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.memory_long_term.graph_view import build_long_term_graph_view
from ace_lite.memory_long_term.store import LongTermMemoryStore
from ace_lite.memory_search_guardrails import build_memory_search_guardrails

_ABSTRACT_QUERY_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "onboarding": ("onboarding", "familiarize", "overview", "entrypoint", "codebase"),
    "familiarization": ("onboarding", "familiarize", "overview", "entrypoint", "codebase"),
    "familiarize": ("onboarding", "familiarize", "overview", "entrypoint", "codebase"),
    "feedback": ("feedback", "selection", "preference", "capture"),
    "optimization": ("optimization", "optimize", "improve", "tuning"),
    "memory": ("memory", "notes", "knowledge", "recall"),
    "repo": ("repo", "repository", "codebase", "project"),
    "repository": ("repo", "repository", "codebase", "project"),
    "熟悉": ("熟悉", "上手", "入口", "导览"),
    "反馈": ("反馈", "偏好", "选择", "闭环"),
    "优化": ("优化", "改进", "调优"),
}


def _normalize_tokens(value: str) -> list[str]:
    return [token for token in str(value or "").lower().split() if token]


def _expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        for candidate in (token, *_ABSTRACT_QUERY_EXPANSIONS.get(token, ())):
            normalized = str(candidate or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            expanded.append(normalized)
    return expanded


def _row_search_blob(row: dict[str, Any]) -> str:
    tag_values: list[str] = []
    tags = row.get("tags")
    if isinstance(tags, dict):
        tag_values.extend(str(value) for value in tags.values() if value)
    elif isinstance(tags, list):
        tag_values.extend(str(value) for value in tags if value)
    # Include task-level slot values in search blob for better matching
    for slot_key in ("req", "contract", "area", "decision_type", "task_id"):
        slot_value = row.get(slot_key) or (tags.get(slot_key) if isinstance(tags, dict) else None)
        if slot_value:
            tag_values.append(str(slot_value))
    return " ".join(
        [
            str(row.get("text", "")),
            str(row.get("query", "")),
            " ".join(str(item) for item in row.get("matched_keywords", []) if item),
            " ".join(tag_values),
        ]
    ).lower()


def _classify_note_type(row: dict[str, Any]) -> str:
    """Classify memory note into task-level categories.

    Returns one of:
    - project_reminder: General project-level information
    - task_constraint: Specific task-level constraints
    - req_match: Requirement-specific note
    - weak_hint: Low-confidence or generic hint
    """
    tags = row.get("tags")
    tags_dict: dict[str, Any] = tags if isinstance(tags, dict) else {}

    # Check for requirement-specific markers
    if row.get("req") or row.get("requirement_id") or tags_dict.get("req") or tags_dict.get("requirement_id"):
        return "req_match"

    # Check for contract markers
    if row.get("contract") or row.get("contract_id") or tags_dict.get("contract") or tags_dict.get("contract_id"):
        return "task_constraint"

    # Check for area/decision type markers
    if (
        row.get("area")
        or row.get("decision_type")
        or row.get("task_id")
        or tags_dict.get("area")
        or tags_dict.get("decision_type")
        or tags_dict.get("task_id")
    ):
        return "task_constraint"

    # Check if note has high specificity (long text with concrete details)
    text = str(row.get("text", ""))
    if len(text) > 200 and any(
        marker in text.lower()
        for marker in ("must", "should", "need to", "required", "constraint", "limitation")
    ):
        return "task_constraint"

    # Check for generic project-level markers
    if tags_dict.get("type") == "project" or tags_dict.get("category") == "overview":
        return "project_reminder"

    # Default to weak_hint for short or generic notes
    if len(text) < 100:
        return "weak_hint"

    return "project_reminder"


def _calculate_task_level_score(
    row: dict[str, Any],
    query: str,
    base_score: float,
) -> float:
    """Boost score for task-level notes when query contains matching req/contract IDs."""
    tags = row.get("tags")
    tags_dict: dict[str, Any] = tags if isinstance(tags, dict) else {}
    query_lower = str(query or "").lower()

    boost = 0.0

    # Extract req IDs from query (e.g., EXPL-01, REQ-01)
    import re
    req_ids = re.findall(r"\b([A-Z]{2,})-(\d+)\b", query, re.IGNORECASE)
    req_id_strs = [f"{str(prefix).upper()}-{num}" for prefix, num in req_ids]

    # Boost if note has matching req ID
    note_req = row.get("req") or row.get("requirement_id") or tags_dict.get("req") or tags_dict.get("requirement_id")
    if note_req and str(note_req).upper() in req_id_strs:
        boost += 0.5  # Significant boost for req match

    # Boost if note has matching contract
    note_contract = row.get("contract") or row.get("contract_id") or tags_dict.get("contract") or tags_dict.get("contract_id")
    if note_contract and str(note_contract).lower() in query_lower:
        boost += 0.4

    # Boost if note has matching area
    note_area = row.get("area") or tags_dict.get("area")
    if note_area and str(note_area).lower() in query_lower:
        boost += 0.3

    # Penalize generic project reminders when query has specific IDs
    if req_id_strs and not (note_req or note_contract or note_area):
        note_type = _classify_note_type(row)
        if note_type == "project_reminder":
            boost -= 0.2  # Slight penalty for generic reminders

    return base_score + boost


def handle_memory_search(
    *,
    query: str,
    limit: int,
    namespace: str | None,
    path: Path,
    notes: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    namespace_filter = str(namespace or "").strip()
    tokens = _normalize_tokens(normalized_query)
    expanded_tokens = _expand_query_tokens(tokens)
    namespace_rows = [
        row
        for row in notes
        if not namespace_filter or str(row.get("namespace", "")).strip() == namespace_filter
    ]

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in namespace_rows:
        search_blob = _row_search_blob(row)
        if not search_blob.strip():
            continue
        if not tokens:
            base_score = 1.0
        else:
            hits = sum(1 for token in tokens if token in search_blob)
            expanded_hits = sum(
                1 for token in expanded_tokens if token in search_blob
            )
            if hits <= 0 and expanded_hits <= 0:
                continue
            base_score = (
                float(hits) / float(max(1, len(tokens)))
                if hits > 0
                else (float(expanded_hits) / float(max(1, len(expanded_tokens)))) * 0.6
            )
        # Apply task-level scoring boost
        final_score = _calculate_task_level_score(row, normalized_query, base_score)
        scored.append((final_score, row))

    scored.sort(
        key=lambda item: (
            -float(item[0]),
            str(item[1].get("captured_at") or item[1].get("created_at") or ""),
        ),
        reverse=False,
    )

    # Add note_type classification to each item
    items: list[dict[str, Any]] = []
    for score, row in scored[: max(1, int(limit))]:
        item = dict(row)
        item["_note_type"] = _classify_note_type(row)
        item["_score"] = round(score, 6)
        items.append(item)

    payload = {
        "ok": True,
        "query": normalized_query,
        "namespace": namespace_filter or None,
        "count": len(items),
        "items": items,
        "notes_path": str(path),
        "cold_start": bool(namespace_filter and not namespace_rows and not items),
        "recommended_next_step": (
            "ace_plan_quick" if namespace_filter and not namespace_rows and not items else None
        ),
    }
    payload.update(
        build_memory_search_guardrails(
            query=normalized_query,
            items=items,
            namespace=namespace_filter or None,
            namespace_note_count=len(namespace_rows),
        )
    )
    return payload


def handle_memory_store(
    *,
    text: str,
    namespace: str | None,
    tags: dict[str, str] | None,
    path: Path,
    rows: list[dict[str, Any]],
    save_notes_fn: Any,
    # Task-level slots (ASF-8911)
    req: str | None = None,
    contract: str | None = None,
    area: str | None = None,
    decision_type: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        raise ValueError("text cannot be empty")

    # Merge explicit slots into tags
    merged_tags = dict(tags or {})
    if req:
        merged_tags["req"] = req
    if contract:
        merged_tags["contract"] = contract
    if area:
        merged_tags["area"] = area
    if decision_type:
        merged_tags["decision_type"] = decision_type
    if task_id:
        merged_tags["task_id"] = task_id

    payload = {
        "text": normalized_text,
        "namespace": str(namespace or "").strip() or None,
        "tags": merged_tags,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "mcp.store",
    }
    # Also store slots at top level for easy access
    if req:
        payload["req"] = req
    if contract:
        payload["contract"] = contract
    if area:
        payload["area"] = area
    if decision_type:
        payload["decision_type"] = decision_type
    if task_id:
        payload["task_id"] = task_id

    rows.append(payload)
    save_notes_fn(path, rows)
    return {
        "ok": True,
        "stored": payload,
        "notes_path": str(path),
    }


def handle_memory_wipe(
    *,
    namespace: str | None,
    path: Path,
    rows: list[dict[str, Any]],
    save_notes_fn: Any,
) -> dict[str, Any]:
    namespace_filter = str(namespace or "").strip()
    if namespace_filter:
        remaining = [
            row
            for row in rows
            if str(row.get("namespace", "")).strip() != namespace_filter
        ]
    else:
        remaining = []
    removed = len(rows) - len(remaining)
    save_notes_fn(path, remaining)
    return {
        "ok": True,
        "namespace": namespace_filter or None,
        "removed_count": max(0, int(removed)),
        "remaining_count": len(remaining),
        "notes_path": str(path),
    }


def handle_memory_graph_view(
    *,
    db_path: Path,
    fact_handle: str | None,
    seeds: list[str] | tuple[str, ...],
    repo: str | None,
    namespace: str | None,
    user_id: str | None,
    profile_key: str | None,
    as_of: str | None,
    max_hops: int,
    limit: int,
) -> dict[str, Any]:
    return build_long_term_graph_view(
        store=LongTermMemoryStore(db_path=db_path),
        fact_handle=fact_handle,
        seeds=tuple(seeds),
        repo=str(repo or ""),
        namespace=str(namespace or ""),
        user_id=str(user_id or ""),
        profile_key=str(profile_key or ""),
        as_of=as_of,
        max_hops=max_hops,
        limit=limit,
    )


__all__ = [
    "handle_memory_graph_view",
    "handle_memory_search",
    "handle_memory_store",
    "handle_memory_wipe",
]
