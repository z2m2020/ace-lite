"""CLI commands for local-first memory notes operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from ace_lite.cli_app.output import echo_json
from ace_lite.memory import prune_memory_notes_rows
from ace_lite.memory_long_term.graph_view import build_long_term_graph_view
from ace_lite.memory_long_term.store import LongTermMemoryStore
from ace_lite.memory_search_guardrails import build_memory_search_guardrails


def _parse_tags(values: tuple[str, ...]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in values:
        raw = str(item or "").strip()
        if not raw or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            tags[key] = value
    return tags


def _load_notes(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _save_notes(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text((content + "\n") if content else "", encoding="utf-8")


@click.group("memory", help="Manage local memory notes (local-first).")
def memory_group() -> None:
    return None


@memory_group.command("search")
@click.argument("query")
@click.option("--limit", default=5, type=int, show_default=True, help="Max results.")
@click.option("--namespace", default="", help="Optional namespace filter.")
@click.option(
    "--notes-path",
    default="context-map/memory_notes.jsonl",
    show_default=True,
    help="Local notes JSONL path.",
)
def memory_search_command(
    query: str,
    limit: int,
    namespace: str,
    notes_path: str,
) -> None:
    notes = _load_notes(Path(notes_path).expanduser())
    namespace_filter = str(namespace or "").strip()
    tokens = [token for token in str(query or "").lower().split() if token]

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
            score = hits / max(1, len(tokens))
        scored.append((score, row))

    scored.sort(
        key=lambda item: (
            -float(item[0]),
            str(item[1].get("captured_at") or item[1].get("created_at") or ""),
        ),
        reverse=False,
    )
    limit_value = max(1, int(limit))
    items = [row for _, row in scored[:limit_value]]
    payload = {
        "query": query,
        "namespace": namespace_filter or None,
        "count": len(items),
        "items": items,
        "notes_path": str(Path(notes_path).expanduser()),
    }
    payload.update(
        build_memory_search_guardrails(
            query=query,
            items=items,
        )
    )
    echo_json(payload)


@memory_group.command("store")
@click.argument("text")
@click.option("--namespace", default="", help="Optional namespace tag for this note.")
@click.option("--tag", "tags", multiple=True, help="Add metadata tag in k=v format.")
@click.option("--req", default="", help="Optional requirement ID such as EXPL-01.")
@click.option("--contract", default="", help="Optional contract or schema identifier.")
@click.option("--area", default="", help="Optional area or module label.")
@click.option("--decision-type", default="", help="Optional decision type such as constraint.")
@click.option("--task-id", default="", help="Optional task identifier.")
@click.option(
    "--notes-path",
    default="context-map/memory_notes.jsonl",
    show_default=True,
    help="Local notes JSONL path.",
)
def memory_store_command(
    text: str,
    namespace: str,
    tags: tuple[str, ...],
    notes_path: str,
    req: str,
    contract: str,
    area: str,
    decision_type: str,
    task_id: str,
) -> None:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        raise click.ClickException("text cannot be empty")

    path = Path(notes_path).expanduser()
    rows = _load_notes(path)
    merged_tags = _parse_tags(tags)
    if str(req).strip():
        merged_tags["req"] = str(req).strip()
    if str(contract).strip():
        merged_tags["contract"] = str(contract).strip()
    if str(area).strip():
        merged_tags["area"] = str(area).strip()
    if str(decision_type).strip():
        merged_tags["decision_type"] = str(decision_type).strip()
    if str(task_id).strip():
        merged_tags["task_id"] = str(task_id).strip()
    payload = {
        "text": normalized_text,
        "namespace": str(namespace or "").strip() or None,
        "tags": merged_tags,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "cli.store",
    }
    if str(req).strip():
        payload["req"] = str(req).strip()
    if str(contract).strip():
        payload["contract"] = str(contract).strip()
    if str(area).strip():
        payload["area"] = str(area).strip()
    if str(decision_type).strip():
        payload["decision_type"] = str(decision_type).strip()
    if str(task_id).strip():
        payload["task_id"] = str(task_id).strip()
    rows.append(payload)
    _save_notes(path, rows)
    echo_json({"ok": True, "stored": payload, "notes_path": str(path)})


@memory_group.command("wipe")
@click.option("--namespace", default="", help="Optional namespace filter.")
@click.option(
    "--notes-path",
    default="context-map/memory_notes.jsonl",
    show_default=True,
    help="Local notes JSONL path.",
)
def memory_wipe_command(namespace: str, notes_path: str) -> None:
    path = Path(notes_path).expanduser()
    rows = _load_notes(path)
    namespace_filter = str(namespace or "").strip()
    if namespace_filter:
        remaining = [
            row
            for row in rows
            if str(row.get("namespace", "")).strip() != namespace_filter
        ]
    else:
        remaining = []
    removed_count = max(0, len(rows) - len(remaining))
    _save_notes(path, remaining)
    echo_json(
        {
            "ok": True,
            "namespace": namespace_filter or None,
            "removed_count": removed_count,
            "remaining_count": len(remaining),
            "notes_path": str(path),
        }
    )


@memory_group.command("vacuum")
@click.option("--namespace", default="", help="Optional namespace filter.")
@click.option(
    "--notes-path",
    default="context-map/memory_notes.jsonl",
    show_default=True,
    help="Local notes JSONL path.",
)
@click.option(
    "--expiry-enabled/--no-expiry-enabled",
    default=True,
    show_default=True,
    help="Enable expiry-based pruning during vacuum.",
)
@click.option(
    "--ttl-days",
    default=90,
    show_default=True,
    type=int,
    help="TTL days for note last-seen timestamps.",
)
@click.option(
    "--max-age-days",
    default=365,
    show_default=True,
    type=int,
    help="Hard max age days for note timestamps.",
)
def memory_vacuum_command(
    namespace: str,
    notes_path: str,
    expiry_enabled: bool,
    ttl_days: int,
    max_age_days: int,
) -> None:
    path = Path(notes_path).expanduser()
    rows = _load_notes(path)
    namespace_filter = str(namespace or "").strip()
    if namespace_filter:
        target_rows = [
            row
            for row in rows
            if str(row.get("namespace", "")).strip() == namespace_filter
        ]
        kept_target_rows, removed_count = prune_memory_notes_rows(
            target_rows,
            expiry_enabled=bool(expiry_enabled),
            ttl_days=max(1, int(ttl_days)),
            max_age_days=max(1, int(max_age_days)),
        )
        target_cursor = iter(kept_target_rows)
        remaining: list[dict[str, Any]] = []
        for row in rows:
            row_namespace = str(row.get("namespace", "")).strip()
            if row_namespace != namespace_filter:
                remaining.append(row)
                continue
            try:
                remaining.append(next(target_cursor))
            except StopIteration:
                continue
    else:
        remaining, removed_count = prune_memory_notes_rows(
            rows,
            expiry_enabled=bool(expiry_enabled),
            ttl_days=max(1, int(ttl_days)),
            max_age_days=max(1, int(max_age_days)),
        )
    _save_notes(path, remaining)
    echo_json(
        {
            "ok": True,
            "namespace": namespace_filter or None,
            "expiry_enabled": bool(expiry_enabled),
            "ttl_days": max(1, int(ttl_days)),
            "max_age_days": max(1, int(max_age_days)),
            "removed_count": int(removed_count),
            "remaining_count": len(remaining),
            "notes_path": str(path),
        }
    )


@memory_group.command("graph")
@click.option(
    "--db-path",
    default="context-map/long_term_memory.db",
    show_default=True,
    help="Long-term memory SQLite path.",
)
@click.option("--fact-handle", default="", help="Optional fact handle to center the graph view.")
@click.option("--seed", "seeds", multiple=True, help="Seed subject/object value for neighborhood expansion.")
@click.option("--repo", default="", help="Repository scope. Required when --fact-handle is not set.")
@click.option("--namespace", default="", help="Optional namespace scope.")
@click.option("--user-id", default="", help="Optional user scope.")
@click.option("--profile-key", default="", help="Optional profile scope.")
@click.option("--as-of", default="", help="Optional ISO-8601 time boundary.")
@click.option("--max-hops", default=1, show_default=True, type=int, help="Neighborhood hops (1-2).")
@click.option("--limit", default=8, show_default=True, type=int, help="Maximum triples returned.")
def memory_graph_command(
    db_path: str,
    fact_handle: str,
    seeds: tuple[str, ...],
    repo: str,
    namespace: str,
    user_id: str,
    profile_key: str,
    as_of: str,
    max_hops: int,
    limit: int,
) -> None:
    payload = build_long_term_graph_view(
        store=LongTermMemoryStore(db_path=Path(db_path).expanduser()),
        fact_handle=fact_handle or None,
        seeds=seeds,
        repo=repo,
        namespace=namespace,
        user_id=user_id,
        profile_key=profile_key,
        as_of=as_of or None,
        max_hops=max_hops,
        limit=limit,
    )
    echo_json(payload)


__all__ = ["memory_group"]
