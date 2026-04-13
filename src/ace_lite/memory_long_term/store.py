from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.memory_long_term.contracts import (
    LONG_TERM_FACT_SCHEMA_VERSION,
    LONG_TERM_OBSERVATION_SCHEMA_VERSION,
    LongTermFactContractV1,
    LongTermObservationContractV1,
    validate_long_term_fact_contract_v1,
    validate_long_term_observation_contract_v1,
)
from ace_lite.runtime_db import connect_runtime_db

LONG_TERM_MEMORY_ENTRIES_TABLE = "long_term_memory_entries"
LONG_TERM_MEMORY_FTS_TABLE = "long_term_memory_fts"
LONG_TERM_MEMORY_TRIPLES_TABLE = "long_term_memory_triples"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_iso_timestamp(value: Any) -> str:
    return str(value or "").strip()


def _normalize_json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _render_observation_text(payload: dict[str, Any]) -> str:
    kind = _normalize_text(payload.get("kind"))
    query = _normalize_text(payload.get("query"))
    metadata = _normalize_json_mapping(payload.get("metadata"))
    details = _normalize_json_mapping(payload.get("payload"))
    detail_parts: list[str] = []
    for key in ("reason", "category", "summary", "status", "selected_path"):
        value = _normalize_text(details.get(key) or metadata.get(key))
        if value:
            detail_parts.append(f"{key}:{value}")
    prefix = f"[observation:{kind}]" if kind else "[observation]"
    parts = [prefix]
    if query:
        parts.append(query)
    if detail_parts:
        parts.append(" ".join(detail_parts[:4]))
    return _normalize_text(" ".join(parts))


def _render_fact_text(payload: dict[str, Any]) -> str:
    fact_type = _normalize_text(payload.get("fact_type"))
    subject = _normalize_text(payload.get("subject"))
    predicate = _normalize_text(payload.get("predicate"))
    object_value = _normalize_text(payload.get("object"))
    prefix = f"[fact:{fact_type}]" if fact_type else "[fact]"
    return _normalize_text(f"{prefix} {subject} {predicate} {object_value}")


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_json_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        raw = json.loads(value)
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _normalize_query_for_match(query: str) -> str:
    tokens = [token for token in "".join(ch if ch.isalnum() else " " for ch in query).split() if token]
    return " ".join(tokens)


def _normalize_relation_value(value: Any) -> str:
    return _normalize_text(value)


def build_long_term_memory_schema_bootstrap(conn: Any) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {LONG_TERM_MEMORY_ENTRIES_TABLE} (
            handle TEXT PRIMARY KEY,
            entry_kind TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            repo TEXT NOT NULL,
            root TEXT NOT NULL,
            namespace TEXT NOT NULL,
            user_id TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            as_of TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_to TEXT NOT NULL,
            confidence REAL NOT NULL,
            derived_from_observation_id TEXT NOT NULL,
            text TEXT NOT NULL,
            preview TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {LONG_TERM_MEMORY_FTS_TABLE}
        USING fts5(
            handle UNINDEXED,
            text,
            repo,
            namespace,
            profile_key,
            user_id
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {LONG_TERM_MEMORY_TRIPLES_TABLE} (
            fact_handle TEXT PRIMARY KEY,
            repo TEXT NOT NULL,
            namespace TEXT NOT NULL,
            user_id TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            as_of TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_to TEXT NOT NULL,
            confidence REAL NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object_value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{LONG_TERM_MEMORY_TRIPLES_TABLE}_scope "
        f"ON {LONG_TERM_MEMORY_TRIPLES_TABLE}(repo, namespace, user_id, profile_key, as_of)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{LONG_TERM_MEMORY_TRIPLES_TABLE}_subject "
        f"ON {LONG_TERM_MEMORY_TRIPLES_TABLE}(subject)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{LONG_TERM_MEMORY_TRIPLES_TABLE}_object "
        f"ON {LONG_TERM_MEMORY_TRIPLES_TABLE}(object_value)"
    )
    conn.commit()


@dataclass(frozen=True, slots=True)
class LongTermMemoryEntry:
    handle: str
    entry_kind: str
    schema_version: str
    repo: str
    root: str
    namespace: str
    user_id: str
    profile_key: str
    as_of: str
    observed_at: str
    valid_from: str
    valid_to: str
    confidence: float
    derived_from_observation_id: str
    text: str
    preview: str
    metadata: dict[str, Any]
    payload: dict[str, Any]

    def to_record_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload.update(
            {
                "memory_kind": self.entry_kind,
                "schema_version": self.schema_version,
                "repo": self.repo,
                "root": self.root,
                "namespace": self.namespace,
                "user_id": self.user_id,
                "profile_key": self.profile_key,
                "as_of": self.as_of,
                "confidence": self.confidence,
                "derived_from_observation_id": self.derived_from_observation_id,
            }
        )
        if self.observed_at:
            payload.setdefault("observed_at", self.observed_at)
            payload.setdefault("captured_at", self.observed_at)
            payload.setdefault("created_at", self.observed_at)
        if self.valid_from:
            payload.setdefault("valid_from", self.valid_from)
            payload.setdefault("created_at", self.valid_from)
        if self.valid_to:
            payload.setdefault("valid_to", self.valid_to)
        if self.entry_kind == "fact":
            payload.setdefault("fact_type", self.payload.get("fact_type", ""))
            payload.setdefault("subject", self.payload.get("subject", ""))
            payload.setdefault("predicate", self.payload.get("predicate", ""))
            payload.setdefault("object", self.payload.get("object", ""))
        else:
            payload.setdefault("kind", self.payload.get("kind", ""))
            payload.setdefault("query", self.payload.get("query", ""))
            payload.setdefault("status", self.payload.get("status", ""))
        return payload


@dataclass(frozen=True, slots=True)
class LongTermMemoryTriple:
    fact_handle: str
    repo: str
    namespace: str
    user_id: str
    profile_key: str
    as_of: str
    valid_from: str
    valid_to: str
    confidence: float
    subject: str
    predicate: str
    object_value: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "fact_handle": self.fact_handle,
            "repo": self.repo,
            "namespace": self.namespace,
            "user_id": self.user_id,
            "profile_key": self.profile_key,
            "as_of": self.as_of,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "confidence": self.confidence,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object_value,
        }


class LongTermMemoryStore:
    def __init__(self, *, db_path: str | Path = "context-map/long_term_memory.db") -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    def _connect(self) -> Any:
        return connect_runtime_db(
            db_path=self.db_path,
            row_factory=sqlite3.Row,
            schema_bootstrap=build_long_term_memory_schema_bootstrap,
        )

    def _bootstrap(self) -> None:
        conn = self._connect()
        conn.close()

    def upsert_observation(
        self,
        contract: LongTermObservationContractV1 | dict[str, Any],
    ) -> LongTermMemoryEntry:
        validation = validate_long_term_observation_contract_v1(contract=contract)
        if not validation["ok"]:
            raise ValueError(validation["violation_details"][0]["message"])
        payload = dict(validation["normalized_contract"] or {})
        entry = LongTermMemoryEntry(
            handle=str(payload.get("id") or "").strip(),
            entry_kind="observation",
            schema_version=LONG_TERM_OBSERVATION_SCHEMA_VERSION,
            repo=_normalize_text(payload.get("repo")),
            root=_normalize_text(payload.get("root")),
            namespace=_normalize_text(payload.get("namespace")),
            user_id=_normalize_text(payload.get("user_id")),
            profile_key=_normalize_text(payload.get("profile_key")),
            as_of=_normalize_iso_timestamp(payload.get("as_of")),
            observed_at=_normalize_iso_timestamp(payload.get("observed_at")),
            valid_from="",
            valid_to="",
            confidence=1.0,
            derived_from_observation_id="",
            text=_render_observation_text(payload),
            preview=_render_observation_text(payload)[:280],
            metadata=_normalize_json_mapping(payload.get("metadata")),
            payload=payload,
        )
        self._upsert_entry(entry)
        return entry

    def upsert_fact(
        self,
        contract: LongTermFactContractV1 | dict[str, Any],
    ) -> LongTermMemoryEntry:
        validation = validate_long_term_fact_contract_v1(contract=contract)
        if not validation["ok"]:
            raise ValueError(validation["violation_details"][0]["message"])
        payload = dict(validation["normalized_contract"] or {})
        valid_from = _normalize_iso_timestamp(payload.get("valid_from")) or _normalize_iso_timestamp(payload.get("as_of"))
        entry = LongTermMemoryEntry(
            handle=str(payload.get("id") or "").strip(),
            entry_kind="fact",
            schema_version=LONG_TERM_FACT_SCHEMA_VERSION,
            repo=_normalize_text(payload.get("repo")),
            root=_normalize_text(payload.get("root")),
            namespace=_normalize_text(payload.get("namespace")),
            user_id=_normalize_text(payload.get("user_id")),
            profile_key=_normalize_text(payload.get("profile_key")),
            as_of=_normalize_iso_timestamp(payload.get("as_of")),
            observed_at="",
            valid_from=valid_from,
            valid_to=_normalize_iso_timestamp(payload.get("valid_to")),
            confidence=float(payload.get("confidence") or 0.0),
            derived_from_observation_id=_normalize_text(
                payload.get("derived_from_observation_id")
            ),
            text=_render_fact_text(payload),
            preview=_render_fact_text(payload)[:280],
            metadata=_normalize_json_mapping(payload.get("metadata")),
            payload=payload,
        )
        self._upsert_entry(entry)
        self._upsert_triple_from_entry(entry)
        return entry

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        container_tag: str | None = None,
        as_of: str | None = None,
    ) -> list[LongTermMemoryEntry]:
        resolved_limit = max(1, int(limit))
        normalized_container_tag = _normalize_text(container_tag)
        normalized_as_of = _normalize_iso_timestamp(as_of)
        normalized_match = _normalize_query_for_match(query)
        params: list[Any] = []
        clauses: list[str] = []
        if normalized_container_tag:
            clauses.append("e.namespace = ?")
            params.append(normalized_container_tag)
        if normalized_as_of:
            clauses.append("e.as_of <= ?")
            params.append(normalized_as_of)
            clauses.append("(e.valid_to = '' OR e.valid_to >= ?)")
            params.append(normalized_as_of)

        where_sql = ""
        if clauses:
            where_sql = " AND " + " AND ".join(clauses)

        conn = self._connect()
        try:
            if normalized_match:
                sql = (
                    f"SELECT e.* FROM {LONG_TERM_MEMORY_FTS_TABLE} f "
                    f"JOIN {LONG_TERM_MEMORY_ENTRIES_TABLE} e ON e.handle = f.handle "
                    f"WHERE f.text MATCH ?{where_sql} "
                    f"ORDER BY bm25({LONG_TERM_MEMORY_FTS_TABLE}), e.as_of DESC, e.handle ASC "
                    f"LIMIT ?"
                )
                rows = conn.execute(sql, (normalized_match, *params, resolved_limit)).fetchall()
            else:
                like_pattern = f"%{_normalize_text(query)}%"
                sql = (
                    f"SELECT e.* FROM {LONG_TERM_MEMORY_ENTRIES_TABLE} e "
                    f"WHERE e.text LIKE ?{where_sql} "
                    f"ORDER BY e.as_of DESC, e.handle ASC LIMIT ?"
                )
                rows = conn.execute(sql, (like_pattern, *params, resolved_limit)).fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            conn.close()

    def fetch(
        self,
        *,
        handles: Sequence[str],
        as_of: str | None = None,
    ) -> list[LongTermMemoryEntry]:
        normalized_handles = [str(handle).strip() for handle in handles if str(handle).strip()]
        if not normalized_handles:
            return []
        normalized_as_of = _normalize_iso_timestamp(as_of)
        placeholders = ",".join("?" for _ in normalized_handles)
        sql = f"SELECT * FROM {LONG_TERM_MEMORY_ENTRIES_TABLE} WHERE handle IN ({placeholders})"
        params: list[Any] = list(normalized_handles)
        if normalized_as_of:
            sql += " AND as_of <= ? AND (valid_to = '' OR valid_to >= ?)"
            params.extend([normalized_as_of, normalized_as_of])
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()
        by_handle = {str(row["handle"]): self._row_to_entry(row) for row in rows}
        return [by_handle[handle] for handle in normalized_handles if handle in by_handle]

    def expand_triple_neighborhood(
        self,
        *,
        seeds: Sequence[str],
        repo: str,
        namespace: str = "",
        user_id: str = "",
        profile_key: str = "",
        as_of: str | None = None,
        max_hops: int = 1,
        limit: int = 8,
    ) -> list[LongTermMemoryTriple]:
        frontier = {
            _normalize_relation_value(seed)
            for seed in seeds
            if _normalize_relation_value(seed)
        }
        if not frontier:
            return []

        resolved_repo = _normalize_text(repo)
        resolved_namespace = _normalize_text(namespace)
        resolved_user_id = _normalize_text(user_id)
        resolved_profile_key = _normalize_text(profile_key)
        resolved_as_of = _normalize_iso_timestamp(as_of)
        resolved_hops = max(1, min(2, int(max_hops or 1)))
        resolved_limit = max(1, int(limit or 8))

        triples_by_handle: dict[str, LongTermMemoryTriple] = {}
        seen_handles: set[str] = set()
        current_frontier = set(frontier)

        for _ in range(resolved_hops):
            hop_rows = self._fetch_triples_for_nodes(
                nodes=current_frontier,
                repo=resolved_repo,
                namespace=resolved_namespace,
                user_id=resolved_user_id,
                profile_key=resolved_profile_key,
                as_of=resolved_as_of,
                limit=resolved_limit * 4,
            )
            if not hop_rows:
                break

            next_frontier: set[str] = set()
            for triple in hop_rows:
                if triple.fact_handle in seen_handles:
                    continue
                triples_by_handle[triple.fact_handle] = triple
                seen_handles.add(triple.fact_handle)
                if len(triples_by_handle) >= resolved_limit:
                    break
                if triple.subject in current_frontier and triple.object_value:
                    next_frontier.add(triple.object_value)
                if triple.object_value in current_frontier and triple.subject:
                    next_frontier.add(triple.subject)
            if len(triples_by_handle) >= resolved_limit:
                break
            current_frontier = {
                node for node in next_frontier if node and node not in frontier
            }
            frontier.update(current_frontier)
            if not current_frontier:
                break

        return list(triples_by_handle.values())[:resolved_limit]

    def _upsert_entry(self, entry: LongTermMemoryEntry) -> None:
        conn = self._connect()
        try:
            conn.execute(
                f"""
                INSERT INTO {LONG_TERM_MEMORY_ENTRIES_TABLE} (
                    handle, entry_kind, schema_version, repo, root, namespace,
                    user_id, profile_key, as_of, observed_at, valid_from, valid_to,
                    confidence, derived_from_observation_id, text, preview,
                    metadata_json, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(handle) DO UPDATE SET
                    entry_kind=excluded.entry_kind,
                    schema_version=excluded.schema_version,
                    repo=excluded.repo,
                    root=excluded.root,
                    namespace=excluded.namespace,
                    user_id=excluded.user_id,
                    profile_key=excluded.profile_key,
                    as_of=excluded.as_of,
                    observed_at=excluded.observed_at,
                    valid_from=excluded.valid_from,
                    valid_to=excluded.valid_to,
                    confidence=excluded.confidence,
                    derived_from_observation_id=excluded.derived_from_observation_id,
                    text=excluded.text,
                    preview=excluded.preview,
                    metadata_json=excluded.metadata_json,
                    payload_json=excluded.payload_json
                """,
                (
                    entry.handle,
                    entry.entry_kind,
                    entry.schema_version,
                    entry.repo,
                    entry.root,
                    entry.namespace,
                    entry.user_id,
                    entry.profile_key,
                    entry.as_of,
                    entry.observed_at,
                    entry.valid_from,
                    entry.valid_to,
                    entry.confidence,
                    entry.derived_from_observation_id,
                    entry.text,
                    entry.preview,
                    _serialize_json(entry.metadata),
                    _serialize_json(entry.payload),
                ),
            )
            conn.execute(
                f"DELETE FROM {LONG_TERM_MEMORY_FTS_TABLE} WHERE handle = ?",
                (entry.handle,),
            )
            conn.execute(
                f"""
                INSERT INTO {LONG_TERM_MEMORY_FTS_TABLE} (
                    handle, text, repo, namespace, profile_key, user_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.handle,
                    entry.text,
                    entry.repo,
                    entry.namespace,
                    entry.profile_key,
                    entry.user_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _upsert_triple_from_entry(self, entry: LongTermMemoryEntry) -> None:
        if entry.entry_kind != "fact":
            return
        payload = entry.payload
        subject = _normalize_relation_value(payload.get("subject"))
        predicate = _normalize_relation_value(payload.get("predicate"))
        object_value = _normalize_relation_value(payload.get("object"))
        if not subject or not predicate or not object_value:
            return

        conn = self._connect()
        try:
            conn.execute(
                f"""
                INSERT INTO {LONG_TERM_MEMORY_TRIPLES_TABLE} (
                    fact_handle, repo, namespace, user_id, profile_key, as_of,
                    valid_from, valid_to, confidence, subject, predicate, object_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_handle) DO UPDATE SET
                    repo=excluded.repo,
                    namespace=excluded.namespace,
                    user_id=excluded.user_id,
                    profile_key=excluded.profile_key,
                    as_of=excluded.as_of,
                    valid_from=excluded.valid_from,
                    valid_to=excluded.valid_to,
                    confidence=excluded.confidence,
                    subject=excluded.subject,
                    predicate=excluded.predicate,
                    object_value=excluded.object_value
                """,
                (
                    entry.handle,
                    entry.repo,
                    entry.namespace,
                    entry.user_id,
                    entry.profile_key,
                    entry.as_of,
                    entry.valid_from,
                    entry.valid_to,
                    entry.confidence,
                    subject,
                    predicate,
                    object_value,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _fetch_triples_for_nodes(
        self,
        *,
        nodes: set[str],
        repo: str,
        namespace: str,
        user_id: str,
        profile_key: str,
        as_of: str,
        limit: int,
    ) -> list[LongTermMemoryTriple]:
        if not nodes:
            return []
        params: list[Any] = [repo]
        clauses = ["repo = ?"]
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if profile_key:
            clauses.append("profile_key = ?")
            params.append(profile_key)
        if as_of:
            clauses.append("as_of <= ?")
            params.append(as_of)
            clauses.append("(valid_to = '' OR valid_to >= ?)")
            params.append(as_of)

        node_list = sorted(nodes)
        placeholders = ",".join("?" for _ in node_list)
        params.extend(node_list)
        params.extend(node_list)
        params.append(max(1, int(limit)))

        sql = (
            f"SELECT * FROM {LONG_TERM_MEMORY_TRIPLES_TABLE} "
            f"WHERE {' AND '.join(clauses)} "
            f"AND (subject IN ({placeholders}) OR object_value IN ({placeholders})) "
            f"ORDER BY confidence DESC, as_of DESC, fact_handle ASC LIMIT ?"
        )
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [self._row_to_triple(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_entry(row: Any) -> LongTermMemoryEntry:
        return LongTermMemoryEntry(
            handle=str(row["handle"]),
            entry_kind=str(row["entry_kind"]),
            schema_version=str(row["schema_version"]),
            repo=str(row["repo"]),
            root=str(row["root"]),
            namespace=str(row["namespace"]),
            user_id=str(row["user_id"]),
            profile_key=str(row["profile_key"]),
            as_of=str(row["as_of"]),
            observed_at=str(row["observed_at"]),
            valid_from=str(row["valid_from"]),
            valid_to=str(row["valid_to"]),
            confidence=float(row["confidence"] or 0.0),
            derived_from_observation_id=str(row["derived_from_observation_id"]),
            text=str(row["text"]),
            preview=str(row["preview"]),
            metadata=_parse_json_mapping(row["metadata_json"]),
            payload=_parse_json_mapping(row["payload_json"]),
        )

    @staticmethod
    def _row_to_triple(row: Any) -> LongTermMemoryTriple:
        return LongTermMemoryTriple(
            fact_handle=str(row["fact_handle"]),
            repo=str(row["repo"]),
            namespace=str(row["namespace"]),
            user_id=str(row["user_id"]),
            profile_key=str(row["profile_key"]),
            as_of=str(row["as_of"]),
            valid_from=str(row["valid_from"]),
            valid_to=str(row["valid_to"]),
            confidence=float(row["confidence"] or 0.0),
            subject=str(row["subject"]),
            predicate=str(row["predicate"]),
            object_value=str(row["object_value"]),
        )


__all__ = [
    "LONG_TERM_MEMORY_ENTRIES_TABLE",
    "LONG_TERM_MEMORY_FTS_TABLE",
    "LONG_TERM_MEMORY_TRIPLES_TABLE",
    "LongTermMemoryEntry",
    "LongTermMemoryStore",
    "LongTermMemoryTriple",
    "build_long_term_memory_schema_bootstrap",
]
