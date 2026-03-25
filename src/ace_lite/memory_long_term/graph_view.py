from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ace_lite.memory_long_term.store import (
    LongTermMemoryEntry,
    LongTermMemoryStore,
    LongTermMemoryTriple,
)

GRAPH_VIEW_SCHEMA_VERSION = "ltm_graph_view_v1"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _normalize_text(raw)
        if not value or value in seen:
            continue
        out.append(value)
        seen.add(value)
    return out


def _entry_to_focus_payload(entry: LongTermMemoryEntry) -> dict[str, Any]:
    payload = entry.payload if isinstance(entry.payload, dict) else {}
    return {
        "handle": entry.handle,
        "memory_kind": entry.entry_kind,
        "fact_type": _normalize_text(payload.get("fact_type")),
        "subject": _normalize_text(payload.get("subject")),
        "predicate": _normalize_text(payload.get("predicate")),
        "object": _normalize_text(payload.get("object")),
        "repo": entry.repo,
        "namespace": entry.namespace,
        "user_id": entry.user_id,
        "profile_key": entry.profile_key,
        "as_of": entry.as_of,
        "valid_from": entry.valid_from,
        "valid_to": entry.valid_to,
        "confidence": float(entry.confidence),
        "derived_from_observation_id": entry.derived_from_observation_id,
    }


def _entry_to_focus_triple(entry: LongTermMemoryEntry) -> LongTermMemoryTriple:
    payload = entry.payload if isinstance(entry.payload, dict) else {}
    return LongTermMemoryTriple(
        fact_handle=entry.handle,
        repo=entry.repo,
        namespace=entry.namespace,
        user_id=entry.user_id,
        profile_key=entry.profile_key,
        as_of=entry.as_of,
        valid_from=entry.valid_from,
        valid_to=entry.valid_to,
        confidence=float(entry.confidence),
        subject=_normalize_text(payload.get("subject")),
        predicate=_normalize_text(payload.get("predicate")),
        object_value=_normalize_text(payload.get("object")),
    )


def _resolve_focus_entry(
    *,
    store: LongTermMemoryStore,
    fact_handle: str,
    as_of: str | None,
) -> LongTermMemoryEntry:
    rows = store.fetch(handles=[fact_handle], as_of=as_of)
    if not rows:
        raise ValueError(f"fact_handle not found: {fact_handle}")
    entry = rows[0]
    if entry.entry_kind != "fact":
        raise ValueError("fact_handle must reference a fact entry")
    return entry


def _build_nodes(
    *,
    triples: Sequence[LongTermMemoryTriple],
    seed_nodes: set[str],
    focus_triple: LongTermMemoryTriple | None,
) -> list[dict[str, Any]]:
    roles_by_node: dict[str, set[str]] = {}
    for triple in triples:
        roles_by_node.setdefault(triple.subject, set())
        roles_by_node.setdefault(triple.object_value, set())
    for seed in seed_nodes:
        roles_by_node.setdefault(seed, set()).add("seed")
    if focus_triple is not None:
        roles_by_node.setdefault(focus_triple.subject, set()).add("focus_subject")
        roles_by_node.setdefault(focus_triple.object_value, set()).add("focus_object")

    nodes: list[dict[str, Any]] = []
    for node_id in sorted(roles_by_node):
        nodes.append(
            {
                "id": node_id,
                "label": node_id,
                "kind": "entity",
                "roles": sorted(roles_by_node[node_id]),
            }
        )
    return nodes


def build_long_term_graph_view(
    *,
    store: LongTermMemoryStore,
    fact_handle: str | None = None,
    seeds: Sequence[str] = (),
    repo: str = "",
    namespace: str = "",
    user_id: str = "",
    profile_key: str = "",
    as_of: str | None = None,
    max_hops: int = 1,
    limit: int = 8,
) -> dict[str, Any]:
    normalized_fact_handle = _normalize_text(fact_handle)
    focus_entry: LongTermMemoryEntry | None = None
    focus_triple: LongTermMemoryTriple | None = None

    if normalized_fact_handle:
        focus_entry = _resolve_focus_entry(
            store=store,
            fact_handle=normalized_fact_handle,
            as_of=as_of,
        )
        focus_triple = _entry_to_focus_triple(focus_entry)

    resolved_repo = _normalize_text(repo or (focus_entry.repo if focus_entry else ""))
    if not resolved_repo:
        raise ValueError("repo is required when fact_handle is not provided")
    resolved_namespace = _normalize_text(
        namespace or (focus_entry.namespace if focus_entry else "")
    )
    resolved_user_id = _normalize_text(
        user_id or (focus_entry.user_id if focus_entry else "")
    )
    resolved_profile_key = _normalize_text(
        profile_key or (focus_entry.profile_key if focus_entry else "")
    )
    resolved_as_of = _normalize_text(as_of or (focus_entry.as_of if focus_entry else ""))

    seed_values = list(seeds)
    if focus_triple is not None:
        seed_values.extend([focus_triple.subject, focus_triple.object_value])
    resolved_seeds = _dedupe_strings(seed_values)
    if not resolved_seeds:
        raise ValueError("at least one seed or fact_handle is required")

    triples = list(
        store.expand_triple_neighborhood(
            seeds=resolved_seeds,
            repo=resolved_repo,
            namespace=resolved_namespace,
            user_id=resolved_user_id,
            profile_key=resolved_profile_key,
            as_of=resolved_as_of or None,
            max_hops=max_hops,
            limit=limit,
        )
    )
    if focus_triple is not None and all(
        item.fact_handle != focus_triple.fact_handle for item in triples
    ):
        triples.insert(0, focus_triple)
    triples = triples[: max(1, int(limit or 8))]

    seed_nodes = set(resolved_seeds)
    nodes = _build_nodes(
        triples=triples,
        seed_nodes=seed_nodes,
        focus_triple=focus_triple,
    )
    triple_payloads: list[dict[str, Any]] = []
    edge_payloads: list[dict[str, Any]] = []
    for triple in triples:
        is_focus = bool(
            focus_triple is not None and triple.fact_handle == focus_triple.fact_handle
        )
        triple_payload = {
            **triple.to_payload(),
            "id": triple.fact_handle,
            "is_focus": is_focus,
        }
        triple_payloads.append(triple_payload)
        edge_payloads.append(
            {
                "id": triple.fact_handle,
                "source": triple.subject,
                "target": triple.object_value,
                "predicate": triple.predicate,
                "fact_handle": triple.fact_handle,
                "confidence": float(triple.confidence),
                "as_of": triple.as_of,
                "is_focus": is_focus,
            }
        )

    return {
        "ok": True,
        "schema_version": GRAPH_VIEW_SCHEMA_VERSION,
        "fact_handle": normalized_fact_handle or None,
        "seeds": resolved_seeds,
        "scope": {
            "repo": resolved_repo,
            "namespace": resolved_namespace or None,
            "user_id": resolved_user_id or None,
            "profile_key": resolved_profile_key or None,
            "as_of": resolved_as_of or None,
        },
        "summary": {
            "triple_count": len(triple_payloads),
            "edge_count": len(edge_payloads),
            "node_count": len(nodes),
            "max_hops": max(1, min(2, int(max_hops or 1))),
            "limit": max(1, int(limit or 8)),
        },
        "focus": _entry_to_focus_payload(focus_entry) if focus_entry is not None else None,
        "nodes": nodes,
        "edges": edge_payloads,
        "triples": triple_payloads,
    }


__all__ = [
    "GRAPH_VIEW_SCHEMA_VERSION",
    "build_long_term_graph_view",
]
