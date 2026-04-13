from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ace_lite.dev_feedback_taxonomy import (
    describe_dev_feedback_reason,
    normalize_dev_feedback_reason_code,
)
from ace_lite.runtime_db import connect_runtime_db

DEV_ISSUES_TABLE = "dev_issues"
DEV_FIXES_TABLE = "dev_fixes"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any, *, max_len: int = 4096) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        return ""
    return normalized[:max_len]


def _normalize_token(value: Any, *, default: str = "", max_len: int = 64) -> str:
    normalized = normalize_dev_feedback_reason_code(
        _normalize_text(value, max_len=max_len),
        default=default,
    )
    return normalized or default


def _normalize_timestamp(value: Any, *, required: bool = False) -> str:
    normalized = _normalize_text(value, max_len=64)
    if not normalized:
        return _utc_now_iso() if required else ""
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _time_delta_hours(*, start: Any, end: Any) -> float:
    start_normalized = _normalize_timestamp(start, required=False)
    end_normalized = _normalize_timestamp(end, required=False)
    if not start_normalized or not end_normalized:
        return 0.0
    try:
        start_dt = datetime.fromisoformat(start_normalized)
        end_dt = datetime.fromisoformat(end_normalized)
    except ValueError:
        return 0.0
    delta_seconds = (end_dt - start_dt).total_seconds()
    if delta_seconds <= 0.0:
        return 0.0
    return float(delta_seconds) / 3600.0


def _normalize_path(value: Any) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def resolve_dev_feedback_store_path(
    *,
    store_path: str | Path | None = None,
    home_path: str | Path | None = None,
) -> Path:
    if store_path is not None:
        return Path(store_path).expanduser().resolve()
    base = (
        Path(home_path).expanduser()
        if home_path is not None
        else Path(
            os.environ.get("HOME")
            or os.environ.get("USERPROFILE")
            or str(Path.home())
        ).expanduser()
    )
    return (base / ".ace-lite" / "dev_feedback.db").resolve()


def build_dev_feedback_schema_bootstrap(conn: Any) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {DEV_ISSUES_TABLE} (
            issue_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            status TEXT NOT NULL,
            repo TEXT NOT NULL,
            user_id TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            query TEXT NOT NULL,
            selected_path TEXT NOT NULL,
            related_invocation_id TEXT NOT NULL,
            notes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {DEV_FIXES_TABLE} (
            fix_id TEXT PRIMARY KEY,
            issue_id TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            repo TEXT NOT NULL,
            user_id TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            query TEXT NOT NULL,
            selected_path TEXT NOT NULL,
            related_invocation_id TEXT NOT NULL,
            resolution_note TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{DEV_ISSUES_TABLE}_repo_reason "
        f"ON {DEV_ISSUES_TABLE}(repo, reason_code)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{DEV_ISSUES_TABLE}_user_profile "
        f"ON {DEV_ISSUES_TABLE}(user_id, profile_key)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{DEV_FIXES_TABLE}_repo_reason "
        f"ON {DEV_FIXES_TABLE}(repo, reason_code)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{DEV_FIXES_TABLE}_issue "
        f"ON {DEV_FIXES_TABLE}(issue_id)"
    )
    conn.commit()


@dataclass(frozen=True, slots=True)
class DevIssue:
    issue_id: str
    title: str
    reason_code: str
    status: str
    repo: str
    user_id: str
    profile_key: str
    query: str
    selected_path: str
    related_invocation_id: str
    notes: str
    created_at: str
    updated_at: str
    resolved_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "title": self.title,
            "reason_code": self.reason_code,
            "status": self.status,
            "repo": self.repo,
            "user_id": self.user_id,
            "profile_key": self.profile_key,
            "query": self.query,
            "selected_path": self.selected_path,
            "related_invocation_id": self.related_invocation_id,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
        }


@dataclass(frozen=True, slots=True)
class DevFix:
    fix_id: str
    issue_id: str
    reason_code: str
    repo: str
    user_id: str
    profile_key: str
    query: str
    selected_path: str
    related_invocation_id: str
    resolution_note: str
    created_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "fix_id": self.fix_id,
            "issue_id": self.issue_id,
            "reason_code": self.reason_code,
            "repo": self.repo,
            "user_id": self.user_id,
            "profile_key": self.profile_key,
            "query": self.query,
            "selected_path": self.selected_path,
            "related_invocation_id": self.related_invocation_id,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at,
        }


def normalize_dev_issue(issue: DevIssue | dict[str, Any]) -> DevIssue:
    payload = issue.to_payload() if isinstance(issue, DevIssue) else dict(issue)
    title = _normalize_text(payload.get("title"), max_len=280)
    repo = _normalize_text(payload.get("repo"), max_len=255)
    reason_code = _normalize_token(payload.get("reason_code"), default="general")
    if not title:
        raise ValueError("title cannot be empty")
    if not repo:
        raise ValueError("repo cannot be empty")
    return DevIssue(
        issue_id=_normalize_text(payload.get("issue_id"), max_len=128) or f"devi_{uuid4().hex[:12]}",
        title=title,
        reason_code=reason_code,
        status=_normalize_token(payload.get("status"), default="open"),
        repo=repo,
        user_id=_normalize_text(payload.get("user_id"), max_len=255),
        profile_key=_normalize_text(payload.get("profile_key"), max_len=255),
        query=_normalize_text(payload.get("query"), max_len=2048),
        selected_path=_normalize_path(payload.get("selected_path")),
        related_invocation_id=_normalize_text(payload.get("related_invocation_id"), max_len=255),
        notes=_normalize_text(payload.get("notes")),
        created_at=_normalize_timestamp(payload.get("created_at"), required=True),
        updated_at=_normalize_timestamp(payload.get("updated_at"), required=True),
        resolved_at=_normalize_timestamp(payload.get("resolved_at"), required=False),
    )


def normalize_dev_fix(fix: DevFix | dict[str, Any]) -> DevFix:
    payload = fix.to_payload() if isinstance(fix, DevFix) else dict(fix)
    repo = _normalize_text(payload.get("repo"), max_len=255)
    reason_code = _normalize_token(payload.get("reason_code"), default="general")
    resolution_note = _normalize_text(payload.get("resolution_note"))
    if not repo:
        raise ValueError("repo cannot be empty")
    if not resolution_note:
        raise ValueError("resolution_note cannot be empty")
    return DevFix(
        fix_id=_normalize_text(payload.get("fix_id"), max_len=128) or f"devf_{uuid4().hex[:12]}",
        issue_id=_normalize_text(payload.get("issue_id"), max_len=128),
        reason_code=reason_code,
        repo=repo,
        user_id=_normalize_text(payload.get("user_id"), max_len=255),
        profile_key=_normalize_text(payload.get("profile_key"), max_len=255),
        query=_normalize_text(payload.get("query"), max_len=2048),
        selected_path=_normalize_path(payload.get("selected_path")),
        related_invocation_id=_normalize_text(payload.get("related_invocation_id"), max_len=255),
        resolution_note=resolution_note,
        created_at=_normalize_timestamp(payload.get("created_at"), required=True),
    )


class DevFeedbackStore:
    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        home_path: str | Path | None = None,
    ) -> None:
        self._db_path = resolve_dev_feedback_store_path(
            store_path=db_path,
            home_path=home_path,
        )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> Any:
        return connect_runtime_db(
            db_path=self._db_path,
            row_factory=sqlite3.Row,
            schema_bootstrap=build_dev_feedback_schema_bootstrap,
        )

    def _bootstrap(self) -> None:
        conn = self._connect()
        conn.close()

    def record_issue(self, issue: DevIssue | dict[str, Any]) -> DevIssue:
        normalized = normalize_dev_issue(issue)
        conn = self._connect()
        try:
            conn.execute(
                f"""
                INSERT INTO {DEV_ISSUES_TABLE} (
                    issue_id, title, reason_code, status, repo, user_id, profile_key,
                    query, selected_path, related_invocation_id, notes,
                    created_at, updated_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_id) DO UPDATE SET
                    title=excluded.title,
                    reason_code=excluded.reason_code,
                    status=excluded.status,
                    repo=excluded.repo,
                    user_id=excluded.user_id,
                    profile_key=excluded.profile_key,
                    query=excluded.query,
                    selected_path=excluded.selected_path,
                    related_invocation_id=excluded.related_invocation_id,
                    notes=excluded.notes,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    resolved_at=excluded.resolved_at
                """,
                (
                    normalized.issue_id,
                    normalized.title,
                    normalized.reason_code,
                    normalized.status,
                    normalized.repo,
                    normalized.user_id,
                    normalized.profile_key,
                    normalized.query,
                    normalized.selected_path,
                    normalized.related_invocation_id,
                    normalized.notes,
                    normalized.created_at,
                    normalized.updated_at,
                    normalized.resolved_at,
                ),
            )
            conn.commit()
            return normalized
        finally:
            conn.close()

    def record_fix(self, fix: DevFix | dict[str, Any]) -> DevFix:
        normalized = normalize_dev_fix(fix)
        conn = self._connect()
        try:
            conn.execute(
                f"""
                INSERT INTO {DEV_FIXES_TABLE} (
                    fix_id, issue_id, reason_code, repo, user_id, profile_key,
                    query, selected_path, related_invocation_id, resolution_note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fix_id) DO UPDATE SET
                    issue_id=excluded.issue_id,
                    reason_code=excluded.reason_code,
                    repo=excluded.repo,
                    user_id=excluded.user_id,
                    profile_key=excluded.profile_key,
                    query=excluded.query,
                    selected_path=excluded.selected_path,
                    related_invocation_id=excluded.related_invocation_id,
                    resolution_note=excluded.resolution_note,
                    created_at=excluded.created_at
                """,
                (
                    normalized.fix_id,
                    normalized.issue_id,
                    normalized.reason_code,
                    normalized.repo,
                    normalized.user_id,
                    normalized.profile_key,
                    normalized.query,
                    normalized.selected_path,
                    normalized.related_invocation_id,
                    normalized.resolution_note,
                    normalized.created_at,
                ),
            )
            conn.commit()
            return normalized
        finally:
            conn.close()

    def get_issue(self, issue_id: str) -> DevIssue | None:
        normalized_issue_id = _normalize_text(issue_id, max_len=128)
        if not normalized_issue_id:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {DEV_ISSUES_TABLE} WHERE issue_id = ?",
                (normalized_issue_id,),
            ).fetchone()
            return self._row_to_issue(row) if row is not None else None
        finally:
            conn.close()

    def get_fix(self, fix_id: str) -> DevFix | None:
        normalized_fix_id = _normalize_text(fix_id, max_len=128)
        if not normalized_fix_id:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {DEV_FIXES_TABLE} WHERE fix_id = ?",
                (normalized_fix_id,),
            ).fetchone()
            return self._row_to_fix(row) if row is not None else None
        finally:
            conn.close()

    def resolve_with_fix(
        self,
        *,
        issue_id: str,
        fix: DevFix,
        resolved_at: str | None = None,
        status: str = "fixed",
    ) -> DevIssue:
        current = self.get_issue(issue_id)
        if current is None:
            raise KeyError(f"developer issue not found: {issue_id}")
        if fix.issue_id and fix.issue_id != current.issue_id:
            raise ValueError("developer fix issue_id does not match target issue")
        if fix.repo != current.repo:
            raise ValueError("developer fix repo does not match target issue")
        if fix.reason_code and current.reason_code and fix.reason_code != current.reason_code:
            raise ValueError("developer fix reason_code does not match target issue")

        resolved_timestamp = _normalize_timestamp(
            resolved_at or fix.created_at,
            required=True,
        )
        note_lines = (
            [str(current.notes or "").strip()]
            if str(current.notes or "").strip()
            else []
        )
        note_lines.append(f"resolved_by_fix={fix.fix_id}")
        note_lines.append(f"resolution_note={fix.resolution_note}")
        return self.record_issue(
            {
                **current.to_payload(),
                "status": status,
                "related_invocation_id": current.related_invocation_id
                or fix.related_invocation_id,
                "notes": "\n".join(note_lines),
                "updated_at": resolved_timestamp,
                "resolved_at": resolved_timestamp,
            }
        )

    def apply_fix(
        self,
        *,
        issue_id: str,
        fix_id: str,
        resolved_at: str | None = None,
        status: str = "fixed",
    ) -> DevIssue:
        fix = self.get_fix(fix_id)
        if fix is None:
            raise KeyError(f"developer fix not found: {fix_id}")
        return self.resolve_with_fix(
            issue_id=issue_id,
            fix=fix,
            resolved_at=resolved_at,
            status=status,
        )

    def summarize(
        self,
        *,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_repo = _normalize_text(repo, max_len=255)
        normalized_user_id = _normalize_text(user_id, max_len=255)
        normalized_profile = _normalize_text(profile_key, max_len=255)
        issue_predicates: list[str] = []
        issue_params: list[Any] = []
        for field_name, value in (
            ("repo", normalized_repo),
            ("user_id", normalized_user_id),
            ("profile_key", normalized_profile),
        ):
            if value:
                issue_predicates.append(f"{field_name} = ?")
                issue_params.append(value)
        issue_where_sql = (
            f"WHERE {' AND '.join(issue_predicates)}" if issue_predicates else ""
        )
        fix_where_sql = issue_where_sql
        fix_params = list(issue_params)

        conn = self._connect()
        try:
            issue_rows = conn.execute(
                f"""
                SELECT reason_code, status, COUNT(*) AS event_count, MAX(updated_at) AS last_seen_at
                FROM {DEV_ISSUES_TABLE}
                {issue_where_sql}
                GROUP BY reason_code, status
                """,
                tuple(issue_params),
            ).fetchall()
            fix_rows = conn.execute(
                f"""
                SELECT reason_code, COUNT(*) AS event_count, MAX(created_at) AS last_seen_at
                FROM {DEV_FIXES_TABLE}
                {fix_where_sql}
                GROUP BY reason_code
                """,
                tuple(fix_params),
            ).fetchall()
            issue_detail_rows = conn.execute(
                f"""
                SELECT issue_id, reason_code, status, created_at, updated_at, resolved_at
                FROM {DEV_ISSUES_TABLE}
                {issue_where_sql}
                """,
                tuple(issue_params),
            ).fetchall()
            fix_detail_rows = conn.execute(
                f"""
                SELECT issue_id, reason_code, created_at
                FROM {DEV_FIXES_TABLE}
                {fix_where_sql}
                """,
                tuple(fix_params),
            ).fetchall()
        finally:
            conn.close()

        by_reason_code: dict[str, dict[str, Any]] = {}
        open_issue_count = 0
        issue_count = 0
        resolved_issue_count = 0
        latest_issue_at = ""
        for row in issue_rows:
            reason_code = str(row["reason_code"] or "")
            status = str(row["status"] or "")
            event_count = int(row["event_count"] or 0)
            last_seen_at = str(row["last_seen_at"] or "")
            issue_count += event_count
            if status not in {"fixed", "rejected"}:
                open_issue_count += event_count
            latest_issue_at = max(latest_issue_at, last_seen_at)
            bucket = by_reason_code.setdefault(
                reason_code,
                {
                    "reason_code": reason_code,
                    **describe_dev_feedback_reason(reason_code),
                    "issue_count": 0,
                    "open_issue_count": 0,
                    "fix_count": 0,
                    "resolved_issue_count": 0,
                    "linked_fix_issue_count": 0,
                    "dev_issue_to_fix_rate": 0.0,
                    "issue_time_to_fix_case_count": 0,
                    "issue_time_to_fix_hours_mean": 0.0,
                    "last_seen_at": "",
                },
            )
            bucket["issue_count"] += event_count
            if status not in {"fixed", "rejected"}:
                bucket["open_issue_count"] += event_count
            bucket["last_seen_at"] = max(str(bucket["last_seen_at"]), last_seen_at)

        fix_count = 0
        latest_fix_at = ""
        for row in fix_rows:
            reason_code = str(row["reason_code"] or "")
            event_count = int(row["event_count"] or 0)
            last_seen_at = str(row["last_seen_at"] or "")
            fix_count += event_count
            latest_fix_at = max(latest_fix_at, last_seen_at)
            bucket = by_reason_code.setdefault(
                reason_code,
                {
                    "reason_code": reason_code,
                    **describe_dev_feedback_reason(reason_code),
                    "issue_count": 0,
                    "open_issue_count": 0,
                    "fix_count": 0,
                    "resolved_issue_count": 0,
                    "linked_fix_issue_count": 0,
                    "dev_issue_to_fix_rate": 0.0,
                    "issue_time_to_fix_case_count": 0,
                    "issue_time_to_fix_hours_mean": 0.0,
                    "last_seen_at": "",
                },
            )
            bucket["fix_count"] += event_count
            bucket["last_seen_at"] = max(str(bucket["last_seen_at"]), last_seen_at)

        linked_fix_issue_ids: set[str] = set()
        linked_fix_issue_ids_by_reason: dict[str, set[str]] = {}
        for row in fix_detail_rows:
            issue_id = str(row["issue_id"] or "").strip()
            reason_code = str(row["reason_code"] or "")
            if not issue_id:
                continue
            linked_fix_issue_ids.add(issue_id)
            linked_fix_issue_ids_by_reason.setdefault(reason_code, set()).add(issue_id)

        issue_time_to_fix_hours_values: list[float] = []
        issue_time_to_fix_hours_by_reason: dict[str, list[float]] = {}
        for row in issue_detail_rows:
            issue_id = str(row["issue_id"] or "").strip()
            reason_code = str(row["reason_code"] or "")
            status = str(row["status"] or "").strip().lower()
            resolved_at = str(row["resolved_at"] or "").strip()
            if status in {"fixed", "rejected"} or resolved_at:
                resolved_issue_count += 1
                bucket = by_reason_code.setdefault(
                    reason_code,
                    {
                        "reason_code": reason_code,
                        **describe_dev_feedback_reason(reason_code),
                        "issue_count": 0,
                        "open_issue_count": 0,
                        "fix_count": 0,
                        "resolved_issue_count": 0,
                        "linked_fix_issue_count": 0,
                        "dev_issue_to_fix_rate": 0.0,
                        "issue_time_to_fix_case_count": 0,
                        "issue_time_to_fix_hours_mean": 0.0,
                        "last_seen_at": "",
                    },
                )
                bucket["resolved_issue_count"] += 1
            if issue_id and issue_id in linked_fix_issue_ids:
                bucket = by_reason_code.setdefault(
                    reason_code,
                    {
                        "reason_code": reason_code,
                        **describe_dev_feedback_reason(reason_code),
                        "issue_count": 0,
                        "open_issue_count": 0,
                        "fix_count": 0,
                        "resolved_issue_count": 0,
                        "linked_fix_issue_count": 0,
                        "dev_issue_to_fix_rate": 0.0,
                        "issue_time_to_fix_case_count": 0,
                        "issue_time_to_fix_hours_mean": 0.0,
                        "last_seen_at": "",
                    },
                )
                bucket["linked_fix_issue_count"] += 1
            time_to_fix_hours = _time_delta_hours(
                start=row["created_at"],
                end=row["resolved_at"],
            )
            if time_to_fix_hours > 0.0:
                issue_time_to_fix_hours_values.append(time_to_fix_hours)
                issue_time_to_fix_hours_by_reason.setdefault(reason_code, []).append(
                    time_to_fix_hours
                )

        total_linked_fix_issue_count = 0
        for reason_code, bucket in by_reason_code.items():
            reason_issue_count = int(bucket["issue_count"] or 0)
            linked_count = int(bucket["linked_fix_issue_count"] or 0)
            if linked_count <= 0:
                linked_count = min(
                    reason_issue_count,
                    int(bucket["fix_count"] or 0),
                )
                bucket["linked_fix_issue_count"] = linked_count
            bucket["dev_issue_to_fix_rate"] = (
                float(linked_count) / float(reason_issue_count)
                if reason_issue_count > 0
                else 0.0
            )
            reason_time_to_fix_hours = issue_time_to_fix_hours_by_reason.get(reason_code, [])
            bucket["issue_time_to_fix_case_count"] = len(reason_time_to_fix_hours)
            bucket["issue_time_to_fix_hours_mean"] = (
                float(sum(reason_time_to_fix_hours)) / float(len(reason_time_to_fix_hours))
                if reason_time_to_fix_hours
                else 0.0
            )
            total_linked_fix_issue_count += linked_count

        top_reasons = sorted(
            by_reason_code.values(),
            key=lambda item: (
                -(int(item["open_issue_count"]) + int(item["issue_count"])),
                -int(item["fix_count"]),
                str(item["reason_code"]),
            ),
        )
        return {
            "store_path": str(self.db_path),
            "repo": normalized_repo or None,
            "user_id": normalized_user_id or None,
            "profile_key": normalized_profile or None,
            "issue_count": issue_count,
            "open_issue_count": open_issue_count,
            "resolved_issue_count": resolved_issue_count,
            "fix_count": fix_count,
            "linked_fix_issue_count": total_linked_fix_issue_count,
            "dev_issue_to_fix_rate": (
                float(total_linked_fix_issue_count) / float(issue_count)
                if issue_count > 0
                else 0.0
            ),
            "issue_time_to_fix_case_count": len(issue_time_to_fix_hours_values),
            "issue_time_to_fix_hours_mean": (
                float(sum(issue_time_to_fix_hours_values))
                / float(len(issue_time_to_fix_hours_values))
                if issue_time_to_fix_hours_values
                else 0.0
            ),
            "latest_issue_at": latest_issue_at,
            "latest_fix_at": latest_fix_at,
            "by_reason_code": top_reasons,
        }

    @staticmethod
    def _row_to_fix(row: Any) -> DevFix:
        return DevFix(
            fix_id=str(row["fix_id"] or ""),
            issue_id=str(row["issue_id"] or ""),
            reason_code=str(row["reason_code"] or ""),
            repo=str(row["repo"] or ""),
            user_id=str(row["user_id"] or ""),
            profile_key=str(row["profile_key"] or ""),
            query=str(row["query"] or ""),
            selected_path=str(row["selected_path"] or ""),
            related_invocation_id=str(row["related_invocation_id"] or ""),
            resolution_note=str(row["resolution_note"] or ""),
            created_at=str(row["created_at"] or ""),
        )

    @staticmethod
    def _row_to_issue(row: Any) -> DevIssue:
        return DevIssue(
            issue_id=str(row["issue_id"] or ""),
            title=str(row["title"] or ""),
            reason_code=str(row["reason_code"] or ""),
            status=str(row["status"] or ""),
            repo=str(row["repo"] or ""),
            user_id=str(row["user_id"] or ""),
            profile_key=str(row["profile_key"] or ""),
            query=str(row["query"] or ""),
            selected_path=str(row["selected_path"] or ""),
            related_invocation_id=str(row["related_invocation_id"] or ""),
            notes=str(row["notes"] or ""),
            created_at=str(row["created_at"] or ""),
            updated_at=str(row["updated_at"] or ""),
            resolved_at=str(row["resolved_at"] or ""),
        )


__all__ = [
    "DEV_FIXES_TABLE",
    "DEV_ISSUES_TABLE",
    "DevFeedbackStore",
    "DevFix",
    "DevIssue",
    "build_dev_feedback_schema_bootstrap",
    "normalize_dev_fix",
    "normalize_dev_issue",
    "resolve_dev_feedback_store_path",
]
