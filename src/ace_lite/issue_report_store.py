from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ace_lite.dev_feedback_store import DevFix
from ace_lite.feedback_issue_linkage import (
    build_issue_report_resolution_from_fix,
    export_issue_report_benchmark_case,
)
from ace_lite.runtime_db import connect_runtime_db

ISSUE_REPORTS_TABLE = "issue_reports"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any, *, max_len: int = 4096) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        return ""
    return normalized[:max_len]


def _normalize_token(value: Any, *, default: str = "", max_len: int = 64) -> str:
    normalized = _normalize_text(value, max_len=max_len).lower().replace(" ", "_")
    return normalized or default


def _normalize_timestamp(value: Any, *, required: bool = False) -> str:
    normalized = _normalize_text(value, max_len=64)
    if not normalized:
        if required:
            return _utc_now_iso()
        return ""
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        normalized = _normalize_text(item)
        if normalized:
            out.append(normalized)
    return out


def _normalize_path(
    value: Any,
    *,
    root_path: Path | None = None,
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if root_path is not None:
            try:
                return resolved.relative_to(root_path).as_posix()
            except ValueError:
                return resolved.as_posix()
        return resolved.as_posix()
    return raw.replace("\\", "/").lstrip("./").lstrip("/")


def _encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _decode_json(value: Any) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def build_issue_report_schema_bootstrap(conn: Any) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ISSUE_REPORTS_TABLE} (
            issue_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            query TEXT NOT NULL,
            repo TEXT NOT NULL,
            root TEXT NOT NULL,
            user_id TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            expected_behavior TEXT NOT NULL,
            actual_behavior TEXT NOT NULL,
            repro_steps_json TEXT NOT NULL,
            plan_payload_ref TEXT NOT NULL,
            selected_path TEXT NOT NULL,
            attachments_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            resolved_at TEXT NOT NULL,
            resolution_note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{ISSUE_REPORTS_TABLE}_repo_status "
        f"ON {ISSUE_REPORTS_TABLE}(repo, status)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{ISSUE_REPORTS_TABLE}_user_profile "
        f"ON {ISSUE_REPORTS_TABLE}(user_id, profile_key)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{ISSUE_REPORTS_TABLE}_occurred_at "
        f"ON {ISSUE_REPORTS_TABLE}(occurred_at)"
    )
    conn.commit()


@dataclass(frozen=True, slots=True)
class IssueReport:
    issue_id: str
    title: str
    category: str
    severity: str
    status: str
    query: str
    repo: str
    root: str
    user_id: str
    profile_key: str
    expected_behavior: str
    actual_behavior: str
    repro_steps: list[str]
    plan_payload_ref: str
    selected_path: str
    attachments: list[str]
    occurred_at: str
    resolved_at: str
    resolution_note: str
    created_at: str
    updated_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "title": self.title,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "query": self.query,
            "repo": self.repo,
            "root": self.root,
            "user_id": self.user_id,
            "profile_key": self.profile_key,
            "expected_behavior": self.expected_behavior,
            "actual_behavior": self.actual_behavior,
            "repro_steps": list(self.repro_steps),
            "plan_payload_ref": self.plan_payload_ref,
            "selected_path": self.selected_path,
            "attachments": list(self.attachments),
            "occurred_at": self.occurred_at,
            "resolved_at": self.resolved_at,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def normalize_issue_report(
    report: IssueReport | dict[str, Any],
    *,
    root_path: str | Path | None = None,
) -> IssueReport:
    payload = report.to_payload() if isinstance(report, IssueReport) else dict(report)
    resolved_root_path = (
        Path(root_path).expanduser().resolve()
        if root_path is not None
        else None
    )
    created_at = _normalize_timestamp(payload.get("created_at"), required=True)
    updated_at = _normalize_timestamp(payload.get("updated_at"), required=True)
    occurred_at = _normalize_timestamp(
        payload.get("occurred_at") or created_at,
        required=True,
    )
    resolved_at = _normalize_timestamp(payload.get("resolved_at"), required=False)
    actual_behavior = _normalize_text(payload.get("actual_behavior"))
    title = _normalize_text(payload.get("title"), max_len=280)
    query = _normalize_text(payload.get("query"), max_len=2048)
    repo = _normalize_text(payload.get("repo"), max_len=255)
    if not title:
        raise ValueError("title cannot be empty")
    if not query:
        raise ValueError("query cannot be empty")
    if not repo:
        raise ValueError("repo cannot be empty")
    if not actual_behavior:
        raise ValueError("actual_behavior cannot be empty")
    root = _normalize_text(payload.get("root"), max_len=1024)
    return IssueReport(
        issue_id=_normalize_text(payload.get("issue_id"), max_len=128) or f"iss_{uuid4().hex[:12]}",
        title=title,
        category=_normalize_token(payload.get("category"), default="general"),
        severity=_normalize_token(payload.get("severity"), default="medium"),
        status=_normalize_token(payload.get("status"), default="open"),
        query=query,
        repo=repo,
        root=root,
        user_id=_normalize_text(payload.get("user_id"), max_len=255),
        profile_key=_normalize_text(payload.get("profile_key"), max_len=255),
        expected_behavior=_normalize_text(payload.get("expected_behavior")),
        actual_behavior=actual_behavior,
        repro_steps=_normalize_string_list(payload.get("repro_steps")),
        plan_payload_ref=_normalize_text(payload.get("plan_payload_ref"), max_len=1024),
        selected_path=_normalize_path(payload.get("selected_path"), root_path=resolved_root_path),
        attachments=_normalize_string_list(payload.get("attachments")),
        occurred_at=occurred_at,
        resolved_at=resolved_at,
        resolution_note=_normalize_text(payload.get("resolution_note")),
        created_at=created_at,
        updated_at=updated_at,
    )


class IssueReportStore:
    def __init__(self, *, db_path: str | Path = "context-map/issue_reports.db") -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    def _connect(self) -> Any:
        return connect_runtime_db(
            db_path=self.db_path,
            row_factory=sqlite3.Row,
            schema_bootstrap=build_issue_report_schema_bootstrap,
        )

    def _bootstrap(self) -> None:
        conn = self._connect()
        conn.close()

    def record(
        self,
        report: IssueReport | dict[str, Any],
        *,
        root_path: str | Path | None = None,
    ) -> IssueReport:
        normalized = normalize_issue_report(report, root_path=root_path)
        conn = self._connect()
        try:
            conn.execute(
                f"""
                INSERT INTO {ISSUE_REPORTS_TABLE} (
                    issue_id, title, category, severity, status, query, repo, root,
                    user_id, profile_key, expected_behavior, actual_behavior,
                    repro_steps_json, plan_payload_ref, selected_path, attachments_json,
                    occurred_at, resolved_at, resolution_note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_id) DO UPDATE SET
                    title=excluded.title,
                    category=excluded.category,
                    severity=excluded.severity,
                    status=excluded.status,
                    query=excluded.query,
                    repo=excluded.repo,
                    root=excluded.root,
                    user_id=excluded.user_id,
                    profile_key=excluded.profile_key,
                    expected_behavior=excluded.expected_behavior,
                    actual_behavior=excluded.actual_behavior,
                    repro_steps_json=excluded.repro_steps_json,
                    plan_payload_ref=excluded.plan_payload_ref,
                    selected_path=excluded.selected_path,
                    attachments_json=excluded.attachments_json,
                    occurred_at=excluded.occurred_at,
                    resolved_at=excluded.resolved_at,
                    resolution_note=excluded.resolution_note,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at
                """,
                (
                    normalized.issue_id,
                    normalized.title,
                    normalized.category,
                    normalized.severity,
                    normalized.status,
                    normalized.query,
                    normalized.repo,
                    normalized.root,
                    normalized.user_id,
                    normalized.profile_key,
                    normalized.expected_behavior,
                    normalized.actual_behavior,
                    _encode_json(normalized.repro_steps),
                    normalized.plan_payload_ref,
                    normalized.selected_path,
                    _encode_json(normalized.attachments),
                    normalized.occurred_at,
                    normalized.resolved_at,
                    normalized.resolution_note,
                    normalized.created_at,
                    normalized.updated_at,
                ),
            )
            conn.commit()
            return normalized
        finally:
            conn.close()

    def get_report(self, issue_id: str) -> IssueReport | None:
        normalized_issue_id = _normalize_text(issue_id, max_len=128)
        if not normalized_issue_id:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {ISSUE_REPORTS_TABLE} WHERE issue_id = ?",
                (normalized_issue_id,),
            ).fetchone()
            return self._row_to_report(row) if row is not None else None
        finally:
            conn.close()

    def resolve_with_fix(
        self,
        *,
        issue_id: str,
        fix: DevFix,
        resolved_at: str | None = None,
        status: str = "resolved",
    ) -> IssueReport:
        current = self.get_report(issue_id)
        if current is None:
            raise KeyError(f"issue report not found: {issue_id}")
        payload = build_issue_report_resolution_from_fix(
            report=current,
            fix=fix,
            resolved_at=resolved_at,
            status=status,
        )
        return self.record(payload)

    def export_case(
        self,
        *,
        issue_id: str,
        output_path: str | Path,
        case_id: str | None = None,
        comparison_lane: str = "issue_report_feedback",
        top_k: int = 8,
        min_validation_tests: int = 1,
        append: bool = True,
    ) -> dict[str, Any]:
        report = self.get_report(issue_id)
        if report is None:
            raise KeyError(f"issue report not found: {issue_id}")
        payload = export_issue_report_benchmark_case(
            report=report,
            output_path=output_path,
            case_id=case_id,
            comparison_lane=comparison_lane,
            top_k=top_k,
            min_validation_tests=min_validation_tests,
            append=append,
        )
        return {"report": report.to_payload(), **payload}

    def list_reports(
        self,
        *,
        repo: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[IssueReport]:
        predicates: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("repo", _normalize_text(repo, max_len=255)),
            ("status", _normalize_token(status)),
            ("user_id", _normalize_text(user_id, max_len=255)),
            ("profile_key", _normalize_text(profile_key, max_len=255)),
            ("category", _normalize_token(category)),
            ("severity", _normalize_token(severity)),
        ):
            if value:
                predicates.append(f"{field_name} = ?")
                params.append(value)
        where_sql = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        params.append(max(1, int(limit)))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM {ISSUE_REPORTS_TABLE} "
                f"{where_sql} "
                "ORDER BY occurred_at DESC, issue_id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
            return [self._row_to_report(row) for row in rows]
        finally:
            conn.close()

    def summarize(
        self,
        *,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
    ) -> dict[str, Any]:
        predicates: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("repo", _normalize_text(repo, max_len=255)),
            ("user_id", _normalize_text(user_id, max_len=255)),
            ("profile_key", _normalize_text(profile_key, max_len=255)),
        ):
            if value:
                predicates.append(f"{field_name} = ?")
                params.append(value)
        where_sql = f"WHERE {' AND '.join(predicates)}" if predicates else ""

        conn = self._connect()
        try:
            status_rows = conn.execute(
                f"""
                SELECT status, COUNT(*) AS report_count, MAX(occurred_at) AS last_seen_at
                FROM {ISSUE_REPORTS_TABLE}
                {where_sql}
                GROUP BY status
                """,
                tuple(params),
            ).fetchall()
            category_rows = conn.execute(
                f"""
                SELECT category, COUNT(*) AS report_count
                FROM {ISSUE_REPORTS_TABLE}
                {where_sql}
                GROUP BY category
                ORDER BY report_count DESC, category ASC
                """,
                tuple(params),
            ).fetchall()
        finally:
            conn.close()

        by_status: list[dict[str, Any]] = []
        open_issue_count = 0
        resolved_issue_count = 0
        report_count = 0
        latest_occurred_at = ""
        for row in status_rows:
            status = str(row["status"] or "")
            count = int(row["report_count"] or 0)
            last_seen_at = str(row["last_seen_at"] or "")
            report_count += count
            if status in {"resolved", "fixed", "closed"}:
                resolved_issue_count += count
            else:
                open_issue_count += count
            latest_occurred_at = max(latest_occurred_at, last_seen_at)
            by_status.append(
                {
                    "status": status,
                    "report_count": count,
                    "last_seen_at": last_seen_at,
                }
            )
        by_status.sort(key=lambda item: (-int(item["report_count"]), str(item["status"])))

        by_category = [
            {
                "category": str(row["category"] or ""),
                "report_count": int(row["report_count"] or 0),
            }
            for row in category_rows
        ]

        return {
            "repo": _normalize_text(repo, max_len=255),
            "user_id": _normalize_text(user_id, max_len=255),
            "profile_key": _normalize_text(profile_key, max_len=255),
            "report_count": report_count,
            "open_issue_count": open_issue_count,
            "resolved_issue_count": resolved_issue_count,
            "latest_occurred_at": latest_occurred_at,
            "by_status": by_status,
            "by_category": by_category,
        }

    @staticmethod
    def _row_to_report(row: Any) -> IssueReport:
        return IssueReport(
            issue_id=str(row["issue_id"] or ""),
            title=str(row["title"] or ""),
            category=str(row["category"] or ""),
            severity=str(row["severity"] or ""),
            status=str(row["status"] or ""),
            query=str(row["query"] or ""),
            repo=str(row["repo"] or ""),
            root=str(row["root"] or ""),
            user_id=str(row["user_id"] or ""),
            profile_key=str(row["profile_key"] or ""),
            expected_behavior=str(row["expected_behavior"] or ""),
            actual_behavior=str(row["actual_behavior"] or ""),
            repro_steps=_decode_json(row["repro_steps_json"]),
            plan_payload_ref=str(row["plan_payload_ref"] or ""),
            selected_path=str(row["selected_path"] or ""),
            attachments=_decode_json(row["attachments_json"]),
            occurred_at=str(row["occurred_at"] or ""),
            resolved_at=str(row["resolved_at"] or ""),
            resolution_note=str(row["resolution_note"] or ""),
            created_at=str(row["created_at"] or ""),
            updated_at=str(row["updated_at"] or ""),
        )


__all__ = [
    "ISSUE_REPORTS_TABLE",
    "IssueReport",
    "IssueReportStore",
    "build_issue_report_schema_bootstrap",
    "normalize_issue_report",
]
