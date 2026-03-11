from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    tokens = [token for token in normalized_query.lower().split() if token]

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in notes:
        row_namespace = str(row.get("namespace", "")).strip()
        if namespace_filter and row_namespace != namespace_filter:
            continue
        search_blob = " ".join(
            [
                str(row.get("text", "")),
                str(row.get("query", "")),
                " ".join(str(item) for item in row.get("matched_keywords", []) if item),
            ]
        ).lower()
        if not search_blob.strip():
            continue
        if not tokens:
            score = 1.0
        else:
            hits = sum(1 for token in tokens if token in search_blob)
            if hits <= 0:
                continue
            score = float(hits) / float(max(1, len(tokens)))
        scored.append((score, row))

    scored.sort(
        key=lambda item: (
            -float(item[0]),
            str(item[1].get("captured_at") or item[1].get("created_at") or ""),
        ),
        reverse=False,
    )
    items = [row for _, row in scored[: max(1, int(limit))]]
    return {
        "ok": True,
        "query": normalized_query,
        "namespace": namespace_filter or None,
        "count": len(items),
        "items": items,
        "notes_path": str(path),
    }


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


__all__ = [
    "handle_memory_search",
    "handle_memory_store",
    "handle_memory_wipe",
]
