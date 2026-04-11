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
    return " ".join(
        [
            str(row.get("text", "")),
            str(row.get("query", "")),
            " ".join(str(item) for item in row.get("matched_keywords", []) if item),
            " ".join(tag_values),
        ]
    ).lower()


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
            score = 1.0
        else:
            hits = sum(1 for token in tokens if token in search_blob)
            expanded_hits = sum(
                1 for token in expanded_tokens if token in search_blob
            )
            if hits <= 0 and expanded_hits <= 0:
                continue
            score = (
                float(hits) / float(max(1, len(tokens)))
                if hits > 0
                else (float(expanded_hits) / float(max(1, len(expanded_tokens)))) * 0.6
            )
        scored.append((score, row))

    scored.sort(
        key=lambda item: (
            -float(item[0]),
            str(item[1].get("captured_at") or item[1].get("created_at") or ""),
        ),
        reverse=False,
    )
    items = [row for _, row in scored[: max(1, int(limit))]]
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
) -> dict[str, Any]:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        raise ValueError("text cannot be empty")

    payload = {
        "text": normalized_text,
        "namespace": str(namespace or "").strip() or None,
        "tags": dict(tags or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "mcp.store",
    }
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
