from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ace_lite.preference_capture_schema import (
    PREFERENCE_CAPTURE_EVENTS_TABLE,
    build_preference_capture_migration_bootstrap,
)
from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_paths import resolve_user_preference_capture_db_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any, *, max_len: int = 255) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        return ""
    return normalized[:max_len]


def _normalize_token(value: Any, *, max_len: int = 64) -> str:
    normalized = _normalize_text(value, max_len=max_len).lower().replace(" ", "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _normalize_target_path(value: Any) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _normalize_weight(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _normalize_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _normalize_preference_kind(value: Any) -> str:
    normalized = _normalize_token(value)
    aliases = {
        "retrieval": "retrieval_preference",
        "packing": "packing_preference",
        "validation": "validation_preference",
        "branch_outcome": "branch_outcome_preference",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized


def _normalize_signal_source(value: Any) -> str:
    normalized = _normalize_token(value)
    aliases = {
        "feedback": "feedback_store",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized


def _encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _decode_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _normalize_text_list(value: Any, *, max_len: int = 255) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _normalize_text(item, max_len=max_len)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _normalize_branch_outcome_capture_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    selected_branch_id = _normalize_text(
        value.get("selected_branch_id") or value.get("winner_branch_id"),
        max_len=128,
    )
    candidate_count = max(0, int(value.get("candidate_count", 0) or 0))
    rejected_count = max(0, int(value.get("rejected_count", 0) or 0))
    if not selected_branch_id or candidate_count <= 1 or rejected_count <= 0:
        return {}
    return {
        "schema_version": _normalize_text(
            value.get("schema_version"), max_len=64
        ) or "branch_outcome_preference_capture_v1",
        "selected_branch_id": selected_branch_id,
        "candidate_count": candidate_count,
        "ranked_branch_ids": _normalize_text_list(
            value.get("ranked_branch_ids"),
            max_len=128,
        ),
        "rejected_count": rejected_count,
        "rejected_reasons": _normalize_text_list(
            value.get("rejected_reasons"),
            max_len=128,
        ),
        "winner_patch_scope_lines": max(
            0,
            int(value.get("winner_patch_scope_lines", 0) or 0),
        ),
        "winner_status": _normalize_text(value.get("winner_status"), max_len=64),
        "winner_artifact_present": bool(value.get("winner_artifact_present", False)),
        "rejected_artifact_count": max(
            0,
            int(value.get("rejected_artifact_count", 0) or 0),
        ),
        "execution_mode": _normalize_text(value.get("execution_mode"), max_len=64),
        "candidate_origin": _normalize_text(
            value.get("candidate_origin"),
            max_len=128,
        ),
        "source": _normalize_text(value.get("source"), max_len=64),
        "target_file_manifest": _normalize_text_list(
            value.get("target_file_manifest"),
            max_len=255,
        ),
        "winner_validation_branch_score": _normalize_payload(
            value.get("winner_validation_branch_score")
        ),
        "rejected": _normalize_mapping_list(value.get("rejected")),
    }


def build_branch_outcome_preference_event(
    *,
    repo_key: str,
    query: str,
    branch_outcome_capture: dict[str, Any],
    user_id: str | None = None,
    profile_key: str | None = None,
    signal_source: str = "runtime",
    signal_key: str | None = None,
    created_at: str | None = None,
) -> PreferenceCaptureEvent | None:
    normalized_repo = _normalize_text(repo_key)
    normalized_query = _normalize_text(query, max_len=2048)
    capture = _normalize_branch_outcome_capture_payload(branch_outcome_capture)
    if not normalized_repo or not normalized_query or not capture:
        return None

    observed_at = _normalize_text(created_at, max_len=64) or _utc_now_iso()
    selected_branch_id = str(capture.get("selected_branch_id") or "").strip()
    target_manifest = capture.get("target_file_manifest")
    target_path = ""
    if isinstance(target_manifest, list) and target_manifest:
        target_path = _normalize_target_path(target_manifest[0])
    if not target_path:
        target_path = "_validation/branch_outcome"
    normalized_signal_key = _normalize_text(
        signal_key,
        max_len=255,
    ) or (
        f"validation.branch_outcome:{selected_branch_id}:{capture.get('candidate_count', 0)}"
    )
    event_seed = "|".join(
        (
            normalized_repo,
            normalized_signal_key,
            selected_branch_id,
            observed_at,
            target_path,
        )
    )
    event_hash = hashlib.sha256(
        event_seed.encode("utf-8", errors="ignore")
    ).hexdigest()[:12]
    event_id = (
        "branch-outcome-preference:"
        + _normalize_token(selected_branch_id, max_len=48)
        + ":"
        + event_hash
    )
    return normalize_preference_capture_event(
        {
            "event_id": event_id,
            "user_id": _normalize_text(user_id),
            "repo_key": normalized_repo,
            "profile_key": _normalize_text(profile_key),
            "preference_kind": "branch_outcome_preference",
            "signal_source": signal_source,
            "signal_key": normalized_signal_key,
            "target_path": target_path,
            "value_text": (
                "selected_branch_id={branch} candidate_count={count} rejected_count={rejected} "
                "winner_status={status}".format(
                    branch=selected_branch_id,
                    count=int(capture.get("candidate_count", 0) or 0),
                    rejected=int(capture.get("rejected_count", 0) or 0),
                    status=str(capture.get("winner_status") or "unknown"),
                )
            ),
            "weight": 1.0,
            "payload": {
                "kind": "branch_outcome_preference",
                "query": normalized_query,
                "summary": capture,
            },
            "created_at": observed_at,
        }
    )


def record_branch_outcome_preference_capture(
    *,
    store: DurablePreferenceCaptureStore,
    repo_key: str,
    query: str,
    branch_outcome_capture: dict[str, Any],
    user_id: str | None = None,
    profile_key: str | None = None,
    signal_source: str = "runtime",
    signal_key: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    event = build_branch_outcome_preference_event(
        repo_key=repo_key,
        query=query,
        branch_outcome_capture=branch_outcome_capture,
        user_id=user_id,
        profile_key=profile_key,
        signal_source=signal_source,
        signal_key=signal_key,
        created_at=created_at,
    )
    if event is None:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_branch_outcome_signal",
            "store_path": str(store.db_path),
        }
    recorded = store.record(event)
    return {
        "ok": True,
        "skipped": False,
        "reason": "",
        "store_path": str(store.db_path),
        "recorded": recorded.to_payload(),
    }


@dataclass(frozen=True, slots=True)
class PreferenceCaptureEvent:
    event_id: str
    user_id: str
    repo_key: str
    profile_key: str
    preference_kind: str
    signal_source: str
    signal_key: str
    target_path: str
    value_text: str
    weight: float
    payload: dict[str, Any]
    created_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "repo_key": self.repo_key,
            "profile_key": self.profile_key,
            "preference_kind": self.preference_kind,
            "signal_source": self.signal_source,
            "signal_key": self.signal_key,
            "target_path": self.target_path,
            "value_text": self.value_text,
            "weight": self.weight,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


def normalize_preference_capture_event(
    event: PreferenceCaptureEvent | dict[str, Any],
) -> PreferenceCaptureEvent:
    payload = event.to_payload() if isinstance(event, PreferenceCaptureEvent) else dict(event)
    return PreferenceCaptureEvent(
        event_id=_normalize_text(payload.get("event_id"), max_len=128) or uuid4().hex,
        user_id=_normalize_text(payload.get("user_id")),
        repo_key=_normalize_text(payload.get("repo_key")),
        profile_key=_normalize_text(payload.get("profile_key")),
        preference_kind=_normalize_preference_kind(payload.get("preference_kind")),
        signal_source=_normalize_signal_source(payload.get("signal_source")),
        signal_key=_normalize_text(payload.get("signal_key")),
        target_path=_normalize_target_path(payload.get("target_path")),
        value_text=_normalize_text(payload.get("value_text"), max_len=2048),
        weight=_normalize_weight(payload.get("weight")),
        payload=_normalize_payload(payload.get("payload")),
        created_at=_normalize_text(payload.get("created_at"), max_len=64) or _utc_now_iso(),
    )


class DurablePreferenceCaptureStore:
    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        home_path: str | Path | None = None,
        configured_path: str | Path | None = None,
    ) -> None:
        resolved_home = (
            Path(home_path).expanduser()
            if home_path is not None
            else Path(
                os.environ.get("HOME")
                or os.environ.get("USERPROFILE")
                or str(Path.home())
            ).expanduser()
        )
        self._db_path = (
            Path(db_path).resolve()
            if db_path is not None
            else Path(
                resolve_user_preference_capture_db_path(
                    home_path=str(resolved_home),
                    configured_path=configured_path,
                )
            )
        )

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> Any:
        return connect_runtime_db(
            db_path=self._db_path,
            row_factory=sqlite3.Row,
            migration_bootstrap=build_preference_capture_migration_bootstrap(),
        )

    def record(
        self,
        event: PreferenceCaptureEvent | dict[str, Any],
    ) -> PreferenceCaptureEvent:
        normalized = normalize_preference_capture_event(event)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                f"INSERT INTO {PREFERENCE_CAPTURE_EVENTS_TABLE}("
                "event_id, user_id, repo_key, profile_key, preference_kind, signal_source, "
                "signal_key, target_path, value_text, weight, payload_json, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(event_id) DO UPDATE SET "
                "user_id = excluded.user_id, "
                "repo_key = excluded.repo_key, "
                "profile_key = excluded.profile_key, "
                "preference_kind = excluded.preference_kind, "
                "signal_source = excluded.signal_source, "
                "signal_key = excluded.signal_key, "
                "target_path = excluded.target_path, "
                "value_text = excluded.value_text, "
                "weight = excluded.weight, "
                "payload_json = excluded.payload_json, "
                "created_at = excluded.created_at",
                (
                    normalized.event_id,
                    normalized.user_id,
                    normalized.repo_key,
                    normalized.profile_key,
                    normalized.preference_kind,
                    normalized.signal_source,
                    normalized.signal_key,
                    normalized.target_path,
                    normalized.value_text,
                    normalized.weight,
                    _encode_payload(normalized.payload),
                    normalized.created_at,
                ),
            )
            conn.execute("COMMIT")
            return normalized
        except Exception:
            with suppress(Exception):
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def list_events(
        self,
        *,
        user_id: str | None = None,
        repo_key: str | None = None,
        profile_key: str | None = None,
        preference_kind: str | None = None,
        signal_source: str | None = None,
        limit: int = 100,
    ) -> list[PreferenceCaptureEvent]:
        predicates: list[str] = []
        params: list[Any] = []
        if _normalize_text(user_id):
            predicates.append("user_id = ?")
            params.append(_normalize_text(user_id))
        if _normalize_text(repo_key):
            predicates.append("repo_key = ?")
            params.append(_normalize_text(repo_key))
        if _normalize_text(profile_key):
            predicates.append("profile_key = ?")
            params.append(_normalize_text(profile_key))
        if _normalize_text(preference_kind):
            predicates.append("preference_kind = ?")
            params.append(_normalize_text(preference_kind))
        if _normalize_text(signal_source):
            predicates.append("signal_source = ?")
            params.append(_normalize_text(signal_source))

        where_sql = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        params.append(max(1, int(limit)))

        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM {PREFERENCE_CAPTURE_EVENTS_TABLE} "
                f"{where_sql} "
                "ORDER BY created_at DESC, event_id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
            return [self._row_to_event(row) for row in rows]
        finally:
            conn.close()

    def summarize(
        self,
        *,
        user_id: str | None = None,
        repo_key: str | None = None,
        profile_key: str | None = None,
        preference_kind: str | None = None,
        signal_source: str | None = None,
    ) -> dict[str, Any]:
        events = self.list_events(
            user_id=user_id,
            repo_key=repo_key,
            profile_key=profile_key,
            preference_kind=preference_kind,
            signal_source=signal_source,
            limit=10000,
        )
        by_kind: dict[str, int] = {}
        by_signal_source: dict[str, int] = {}
        distinct_paths: set[str] = set()
        total_weight = 0.0
        latest_created_at = ""
        for event in events:
            by_kind[event.preference_kind] = by_kind.get(event.preference_kind, 0) + 1
            by_signal_source[event.signal_source] = (
                by_signal_source.get(event.signal_source, 0) + 1
            )
            if event.target_path:
                distinct_paths.add(event.target_path)
            total_weight += event.weight
            if event.created_at > latest_created_at:
                latest_created_at = event.created_at
        return {
            "event_count": len(events),
            "distinct_target_path_count": len(distinct_paths),
            "total_weight": total_weight,
            "latest_created_at": latest_created_at,
            "by_kind": by_kind,
            "by_signal_source": by_signal_source,
        }

    def delete_events(
        self,
        *,
        event_ids: list[str] | None = None,
        user_id: str | None = None,
        repo_key: str | None = None,
        profile_key: str | None = None,
        preference_kind: str | None = None,
        signal_source: str | None = None,
    ) -> int:
        predicates: list[str] = []
        params: list[Any] = []
        normalized_event_ids = [
            _normalize_text(item, max_len=128)
            for item in list(event_ids or [])
            if _normalize_text(item, max_len=128)
        ]
        if normalized_event_ids:
            placeholders = ", ".join("?" for _ in normalized_event_ids)
            predicates.append(f"event_id IN ({placeholders})")
            params.extend(normalized_event_ids)
        if _normalize_text(user_id):
            predicates.append("user_id = ?")
            params.append(_normalize_text(user_id))
        if _normalize_text(repo_key):
            predicates.append("repo_key = ?")
            params.append(_normalize_text(repo_key))
        if _normalize_text(profile_key):
            predicates.append("profile_key = ?")
            params.append(_normalize_text(profile_key))
        if _normalize_text(preference_kind):
            predicates.append("preference_kind = ?")
            params.append(_normalize_text(preference_kind))
        if _normalize_text(signal_source):
            predicates.append("signal_source = ?")
            params.append(_normalize_text(signal_source))

        where_sql = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            before = conn.total_changes
            conn.execute(
                f"DELETE FROM {PREFERENCE_CAPTURE_EVENTS_TABLE} {where_sql}",
                tuple(params),
            )
            deleted = conn.total_changes - before
            conn.execute("COMMIT")
            return max(0, int(deleted))
        except Exception:
            with suppress(Exception):
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def trim_events(
        self,
        *,
        keep_latest: int,
        user_id: str | None = None,
        repo_key: str | None = None,
        profile_key: str | None = None,
        preference_kind: str | None = None,
        signal_source: str | None = None,
    ) -> int:
        normalized_keep = max(0, int(keep_latest))
        predicates: list[str] = []
        params: list[Any] = []
        if _normalize_text(user_id):
            predicates.append("user_id = ?")
            params.append(_normalize_text(user_id))
        if _normalize_text(repo_key):
            predicates.append("repo_key = ?")
            params.append(_normalize_text(repo_key))
        if _normalize_text(profile_key):
            predicates.append("profile_key = ?")
            params.append(_normalize_text(profile_key))
        if _normalize_text(preference_kind):
            predicates.append("preference_kind = ?")
            params.append(_normalize_text(preference_kind))
        if _normalize_text(signal_source):
            predicates.append("signal_source = ?")
            params.append(_normalize_text(signal_source))

        where_sql = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        deletion_sql = (
            f"DELETE FROM {PREFERENCE_CAPTURE_EVENTS_TABLE} "
            "WHERE event_id IN ("
            f"SELECT event_id FROM {PREFERENCE_CAPTURE_EVENTS_TABLE} "
            f"{where_sql} "
            "ORDER BY created_at DESC, event_id DESC "
            "LIMIT -1 OFFSET ?)"
        )
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            before = conn.total_changes
            conn.execute(
                deletion_sql,
                tuple([*params, normalized_keep]),
            )
            deleted = conn.total_changes - before
            conn.execute("COMMIT")
            return max(0, int(deleted))
        except Exception:
            with suppress(Exception):
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _row_to_event(self, row: Any) -> PreferenceCaptureEvent:
        return PreferenceCaptureEvent(
            event_id=str(row["event_id"] or ""),
            user_id=str(row["user_id"] or ""),
            repo_key=str(row["repo_key"] or ""),
            profile_key=str(row["profile_key"] or ""),
            preference_kind=str(row["preference_kind"] or ""),
            signal_source=str(row["signal_source"] or ""),
            signal_key=str(row["signal_key"] or ""),
            target_path=str(row["target_path"] or ""),
            value_text=str(row["value_text"] or ""),
            weight=float(row["weight"] or 0.0),
            payload=_decode_payload(row["payload_json"]),
            created_at=str(row["created_at"] or ""),
        )


__all__ = [
    "DurablePreferenceCaptureStore",
    "PreferenceCaptureEvent",
    "build_branch_outcome_preference_event",
    "normalize_preference_capture_event",
    "record_branch_outcome_preference_capture",
]
