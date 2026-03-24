from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.memory_long_term.contracts import (
    build_long_term_fact_contract_v1,
    build_long_term_observation_contract_v1,
)
from ace_lite.memory_long_term.store import LongTermMemoryStore
from ace_lite.runtime_settings import RuntimeSettingsManager


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _resolve_repo_relative_path(*, root: str | Path, configured_path: str) -> Path:
    path = Path(str(configured_path or "").strip() or "context-map/long_term_memory.db")
    if path.is_absolute():
        return path.resolve()
    return (Path(root).resolve() / path).resolve()


def _resolve_root(root: str | Path | None) -> str:
    if root is None:
        return ""
    normalized = str(root).strip()
    if not normalized:
        return ""
    return str(Path(normalized).expanduser().resolve())


def _resolve_stage_signal_count(*, stage_name: str, payload: dict[str, Any]) -> int:
    if stage_name == "source_plan":
        return sum(
            (
                int(payload.get("candidate_file_count", 0) or 0) > 0,
                int(payload.get("candidate_chunk_count", 0) or 0) > 0,
                int(payload.get("validation_test_count", 0) or 0) > 0,
                bool(payload.get("patch_artifact_present", False)),
            )
        )
    if stage_name == "validation":
        return sum(
            (
                bool(str(payload.get("reason") or "").strip()),
                int(payload.get("diagnostic_count", 0) or 0) > 0,
                bool(payload.get("patch_artifact_present", False)),
                int(payload.get("selected_test_count", 0) or 0) > 0,
            )
        )
    return sum(1 for value in payload.values() if value not in ("", None, [], {}))


class LongTermMemoryCaptureService:
    def __init__(
        self,
        *,
        store: LongTermMemoryStore,
        enabled: bool = False,
    ) -> None:
        self._store = store
        self._enabled = bool(enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def capture_stage_observation(
        self,
        *,
        stage_name: str,
        query: str,
        repo: str,
        root: str,
        profile_key: str | None = None,
        source_run_id: str | None = None,
        stage_payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._enabled:
            return {"ok": True, "skipped": True, "reason": "disabled", "stage": stage_name}

        observed_at = _utc_now_iso()
        payload = self._build_stage_payload(
            stage_name=stage_name,
            stage_payload=stage_payload,
        )
        signal_count = _resolve_stage_signal_count(stage_name=stage_name, payload=payload)
        if signal_count <= 0:
            return {
                "ok": True,
                "skipped": True,
                "reason": "no_capture_signal",
                "stage": stage_name,
                "signal_count": 0,
            }
        observation_id = hashlib.sha256(
            f"{stage_name}|{repo}|{query}|{observed_at}".encode("utf-8")
        ).hexdigest()[:24]
        contract = build_long_term_observation_contract_v1(
            observation_id=observation_id,
            kind=stage_name,
            repo=repo,
            root=root,
            namespace=f"repo/{repo}",
            profile_key=str(profile_key or "").strip(),
            query=query,
            payload=payload,
            observed_at=observed_at,
            as_of=observed_at,
            source_run_id=str(source_run_id or "").strip(),
            severity="info" if stage_name == "source_plan" else self._resolve_validation_severity(stage_payload),
            status=str(payload.get("status") or "captured"),
            metadata={
                "stage": stage_name,
                "capture_gate": "accepted",
                "signal_count": signal_count,
                "attribution_scope": "stage_payload_only",
            },
        )
        entry = self._store.upsert_observation(contract)
        return {
            "ok": True,
            "skipped": False,
            "stage": stage_name,
            "handle": entry.handle,
            "as_of": entry.as_of,
            "status": payload.get("status", "captured"),
            "signal_count": signal_count,
        }

    def capture_selection_feedback(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        selected_path: str,
        position: int | None = None,
        captured_at: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
    ) -> dict[str, Any]:
        if not self._enabled:
            return {
                "ok": True,
                "skipped": True,
                "reason": "disabled",
                "stage": "selection_feedback",
            }

        observed_at = _normalize_text(captured_at) or _utc_now_iso()
        normalized_selected_path = _normalize_text(selected_path)
        normalized_query = _normalize_text(query)
        normalized_repo = _normalize_text(repo)
        if not normalized_repo:
            return {
                "ok": True,
                "skipped": True,
                "reason": "missing_repo",
                "stage": "selection_feedback",
            }
        if not normalized_query:
            return {
                "ok": True,
                "skipped": True,
                "reason": "missing_query",
                "stage": "selection_feedback",
            }
        if not normalized_selected_path:
            return {
                "ok": True,
                "skipped": True,
                "reason": "missing_selected_path",
                "stage": "selection_feedback",
            }
        payload = {
            "status": "selected",
            "selected_path": normalized_selected_path,
            "position": int(position) if isinstance(position, int) and position > 0 else None,
        }
        observation_id = hashlib.sha256(
            f"selection_feedback|{repo}|{query}|{normalized_selected_path}|{observed_at}".encode(
                "utf-8"
            )
        ).hexdigest()[:24]
        contract = build_long_term_observation_contract_v1(
            observation_id=observation_id,
            kind="selection_feedback",
            repo=repo,
            root=root,
            namespace=f"repo/{repo}",
            user_id=str(user_id or "").strip(),
            profile_key=str(profile_key or "").strip(),
            query=query,
            payload=payload,
            observed_at=observed_at,
            as_of=observed_at,
            source_run_id="",
            severity="info",
            status="selected",
            metadata={
                "stage": "selection_feedback",
                "selected_path": normalized_selected_path,
                "capture_gate": "accepted",
                "signal_count": 1,
                "feedback_signal": "helpful",
                "attribution_scope": "explicit_selection_only",
            },
        )
        entry = self._store.upsert_observation(contract)
        return {
            "ok": True,
            "skipped": False,
            "stage": "selection_feedback",
            "handle": entry.handle,
            "as_of": entry.as_of,
            "status": "selected",
            "signal_count": 1,
        }

    def capture_dev_issue(
        self,
        *,
        issue: dict[str, Any],
        root: str | Path | None,
    ) -> dict[str, Any]:
        if not self._enabled:
            return {
                "ok": True,
                "skipped": True,
                "reason": "disabled",
                "stage": "dev_issue",
            }

        normalized_issue = dict(issue) if isinstance(issue, dict) else {}
        repo = _normalize_text(normalized_issue.get("repo"))
        issue_id = _normalize_text(normalized_issue.get("issue_id"))
        observed_at = (
            _normalize_text(normalized_issue.get("updated_at"))
            or _normalize_text(normalized_issue.get("created_at"))
            or _utc_now_iso()
        )
        status = _normalize_text(normalized_issue.get("status")) or "open"
        title = _normalize_text(normalized_issue.get("title"))
        payload = {
            "status": status,
            "issue_id": issue_id,
            "title": title,
            "reason_code": _normalize_text(normalized_issue.get("reason_code")),
            "selected_path": _normalize_text(normalized_issue.get("selected_path")),
            "related_invocation_id": _normalize_text(
                normalized_issue.get("related_invocation_id")
            ),
            "notes": _normalize_text(normalized_issue.get("notes")),
        }
        observation_id = hashlib.sha256(
            f"dev_issue|{repo}|{issue_id}|{observed_at}|{status}".encode("utf-8")
        ).hexdigest()[:24]
        contract = build_long_term_observation_contract_v1(
            observation_id=observation_id,
            kind="dev_issue",
            repo=repo,
            root=_resolve_root(root),
            namespace=f"repo/{repo}",
            user_id=_normalize_text(normalized_issue.get("user_id")),
            profile_key=_normalize_text(normalized_issue.get("profile_key")),
            query=_normalize_text(normalized_issue.get("query")) or title,
            payload=payload,
            observed_at=observed_at,
            as_of=observed_at,
            source_run_id=_normalize_text(normalized_issue.get("related_invocation_id")),
            severity="warning" if status not in {"fixed", "resolved", "rejected"} else "info",
            status=status,
            metadata={
                "stage": "dev_issue",
                "reason_code": payload["reason_code"],
                "issue_id": issue_id,
                "feedback_signal": "harmful",
            },
        )
        entry = self._store.upsert_observation(contract)
        return {
            "ok": True,
            "skipped": False,
            "stage": "dev_issue",
            "handle": entry.handle,
            "as_of": entry.as_of,
            "status": status,
        }

    def capture_dev_fix(
        self,
        *,
        fix: dict[str, Any],
        root: str | Path | None,
    ) -> dict[str, Any]:
        if not self._enabled:
            return {
                "ok": True,
                "skipped": True,
                "reason": "disabled",
                "stage": "dev_fix",
            }

        normalized_fix = dict(fix) if isinstance(fix, dict) else {}
        repo = _normalize_text(normalized_fix.get("repo"))
        fix_id = _normalize_text(normalized_fix.get("fix_id"))
        observed_at = _normalize_text(normalized_fix.get("created_at")) or _utc_now_iso()
        payload = {
            "status": "recorded",
            "fix_id": fix_id,
            "issue_id": _normalize_text(normalized_fix.get("issue_id")),
            "reason_code": _normalize_text(normalized_fix.get("reason_code")),
            "selected_path": _normalize_text(normalized_fix.get("selected_path")),
            "related_invocation_id": _normalize_text(
                normalized_fix.get("related_invocation_id")
            ),
            "resolution_note": _normalize_text(normalized_fix.get("resolution_note")),
        }
        observation_id = hashlib.sha256(
            f"dev_fix|{repo}|{fix_id}|{observed_at}".encode("utf-8")
        ).hexdigest()[:24]
        contract = build_long_term_observation_contract_v1(
            observation_id=observation_id,
            kind="dev_fix",
            repo=repo,
            root=_resolve_root(root),
            namespace=f"repo/{repo}",
            user_id=_normalize_text(normalized_fix.get("user_id")),
            profile_key=_normalize_text(normalized_fix.get("profile_key")),
            query=_normalize_text(normalized_fix.get("query")) or payload["resolution_note"],
            payload=payload,
            observed_at=observed_at,
            as_of=observed_at,
            source_run_id=_normalize_text(normalized_fix.get("related_invocation_id")),
            severity="info",
            status="recorded",
            metadata={
                "stage": "dev_fix",
                "reason_code": payload["reason_code"],
                "fix_id": fix_id,
                "issue_id": payload["issue_id"],
                "feedback_signal": "helpful",
            },
        )
        entry = self._store.upsert_observation(contract)
        return {
            "ok": True,
            "skipped": False,
            "stage": "dev_fix",
            "handle": entry.handle,
            "as_of": entry.as_of,
            "status": "recorded",
        }

    def capture_dev_issue_resolution(
        self,
        *,
        issue: dict[str, Any],
        fix: dict[str, Any],
        root: str | Path | None,
    ) -> dict[str, Any]:
        if not self._enabled:
            return {
                "ok": True,
                "skipped": True,
                "reason": "disabled",
                "stage": "dev_issue_resolution",
            }

        normalized_issue = dict(issue) if isinstance(issue, dict) else {}
        normalized_fix = dict(fix) if isinstance(fix, dict) else {}
        repo = _normalize_text(normalized_issue.get("repo") or normalized_fix.get("repo"))
        issue_id = _normalize_text(normalized_issue.get("issue_id"))
        fix_id = _normalize_text(normalized_fix.get("fix_id"))
        observed_at = (
            _normalize_text(normalized_issue.get("resolved_at"))
            or _normalize_text(normalized_issue.get("updated_at"))
            or _normalize_text(normalized_fix.get("created_at"))
            or _utc_now_iso()
        )
        status = _normalize_text(normalized_issue.get("status")) or "fixed"
        resolution_note = _normalize_text(normalized_fix.get("resolution_note"))
        observation_payload = {
            "status": status,
            "issue_id": issue_id,
            "fix_id": fix_id,
            "reason_code": _normalize_text(
                normalized_issue.get("reason_code") or normalized_fix.get("reason_code")
            ),
            "selected_path": _normalize_text(
                normalized_issue.get("selected_path") or normalized_fix.get("selected_path")
            ),
            "related_invocation_id": _normalize_text(
                normalized_issue.get("related_invocation_id")
                or normalized_fix.get("related_invocation_id")
            ),
            "resolution_note": resolution_note,
        }
        observation_id = hashlib.sha256(
            f"dev_issue_resolution|{repo}|{issue_id}|{fix_id}|{observed_at}".encode("utf-8")
        ).hexdigest()[:24]
        observation_contract = build_long_term_observation_contract_v1(
            observation_id=observation_id,
            kind="dev_issue_resolution",
            repo=repo,
            root=_resolve_root(root),
            namespace=f"repo/{repo}",
            user_id=_normalize_text(
                normalized_issue.get("user_id") or normalized_fix.get("user_id")
            ),
            profile_key=_normalize_text(
                normalized_issue.get("profile_key") or normalized_fix.get("profile_key")
            ),
            query=(
                _normalize_text(normalized_issue.get("query"))
                or _normalize_text(normalized_fix.get("query"))
                or _normalize_text(normalized_issue.get("title"))
                or resolution_note
            ),
            payload=observation_payload,
            observed_at=observed_at,
            as_of=observed_at,
            source_run_id=observation_payload["related_invocation_id"],
            severity="info",
            status=status,
            metadata={
                "stage": "dev_issue_resolution",
                "reason_code": observation_payload["reason_code"],
                "issue_id": issue_id,
                "fix_id": fix_id,
                "feedback_signal": "helpful",
            },
        )
        observation_entry = self._store.upsert_observation(observation_contract)
        fact_contract = build_long_term_fact_contract_v1(
            fact_id=hashlib.sha256(
                f"dev_issue_resolution_fact|{repo}|{issue_id}|{fix_id}|{observed_at}".encode(
                    "utf-8"
                )
            ).hexdigest()[:24],
            fact_type="dev_issue_resolution",
            subject=f"dev_issue:{issue_id}",
            predicate="resolved_by",
            object_value=f"dev_fix:{fix_id}",
            repo=repo,
            root=_resolve_root(root),
            namespace=f"repo/{repo}",
            user_id=_normalize_text(
                normalized_issue.get("user_id") or normalized_fix.get("user_id")
            ),
            profile_key=_normalize_text(
                normalized_issue.get("profile_key") or normalized_fix.get("profile_key")
            ),
            as_of=observed_at,
            confidence=1.0,
            valid_from=observed_at,
            derived_from_observation_id=observation_id,
            metadata={
                "status": status,
                "reason_code": observation_payload["reason_code"],
                "issue_id": issue_id,
                "fix_id": fix_id,
                "resolution_note": resolution_note,
                "feedback_signal": "helpful",
            },
        )
        fact_entry = self._store.upsert_fact(fact_contract)
        return {
            "ok": True,
            "skipped": False,
            "stage": "dev_issue_resolution",
            "handle": observation_entry.handle,
            "fact_handle": fact_entry.handle,
            "as_of": observation_entry.as_of,
            "status": status,
        }

    def _build_stage_payload(
        self,
        *,
        stage_name: str,
        stage_payload: dict[str, Any],
    ) -> dict[str, Any]:
        if stage_name == "source_plan":
            candidate_files = [
                str(item.get("path") or "").strip()
                for item in stage_payload.get("candidate_files", [])
                if isinstance(item, dict) and str(item.get("path") or "").strip()
            ]
            validation_tests = [
                str(item).strip()
                for item in stage_payload.get("validation_tests", [])
                if str(item).strip()
            ]
            return {
                "status": "captured",
                "candidate_file_count": len(candidate_files),
                "candidate_paths": candidate_files[:8],
                "candidate_chunk_count": len(stage_payload.get("candidate_chunks", []) or []),
                "validation_test_count": len(validation_tests),
                "validation_tests": validation_tests[:8],
                "patch_artifact_present": isinstance(stage_payload.get("patch_artifact"), dict),
            }

        result = stage_payload.get("result", {}) if isinstance(stage_payload.get("result"), dict) else {}
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        return {
            "status": _normalize_text(summary.get("status") or stage_payload.get("reason") or "unknown"),
            "reason": _normalize_text(stage_payload.get("reason")),
            "diagnostic_count": int(stage_payload.get("diagnostic_count", 0) or 0),
            "xref_enabled": bool(stage_payload.get("xref_enabled", False)),
            "patch_artifact_present": bool(stage_payload.get("patch_artifact_present", False)),
            "sandboxed": bool(result.get("environment", {}).get("sandboxed", False))
            if isinstance(result.get("environment"), dict)
            else False,
            "selected_test_count": len(
                result.get("tests", {}).get("selected", [])
                if isinstance(result.get("tests"), dict)
                else []
            ),
        }

    @staticmethod
    def _resolve_validation_severity(stage_payload: dict[str, Any]) -> str:
        diagnostic_count = int(stage_payload.get("diagnostic_count", 0) or 0)
        if diagnostic_count > 0:
            return "warning"
        result = stage_payload.get("result", {}) if isinstance(stage_payload.get("result"), dict) else {}
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        status = _normalize_text(summary.get("status"))
        if status in {"failed", "degraded"}:
            return "warning"
        return "info"


def build_long_term_capture_service_from_runtime(
    *,
    root: str | Path,
    config_file: str = ".ace-lite.yml",
    runtime_profile: str | None = None,
    cwd: Path | None = None,
    mcp_env: dict[str, str] | None = None,
    mcp_snapshot_env: dict[str, str] | None = None,
) -> LongTermMemoryCaptureService | None:
    resolved = RuntimeSettingsManager().resolve(
        root=str(Path(root).resolve()),
        cwd=Path.cwd() if cwd is None else cwd,
        config_file=config_file,
        plan_runtime_profile=runtime_profile,
        mcp_env=dict(mcp_env or {}),
        mcp_snapshot_env=dict(mcp_snapshot_env) if isinstance(mcp_snapshot_env, dict) else None,
    )
    plan_settings = resolved.snapshot.get("plan", {})
    memory_settings = plan_settings.get("memory", {}) if isinstance(plan_settings, dict) else {}
    long_term_settings = (
        memory_settings.get("long_term", {})
        if isinstance(memory_settings, dict)
        else {}
    )
    if not isinstance(long_term_settings, dict):
        return None
    enabled = bool(long_term_settings.get("enabled", False))
    write_enabled = bool(long_term_settings.get("write_enabled", False))
    if not (enabled and write_enabled):
        return None
    db_path = _resolve_repo_relative_path(
        root=root,
        configured_path=str(
            long_term_settings.get("path", "context-map/long_term_memory.db")
        ),
    )
    return LongTermMemoryCaptureService(
        store=LongTermMemoryStore(db_path=db_path),
        enabled=True,
    )


__all__ = [
    "LongTermMemoryCaptureService",
    "build_long_term_capture_service_from_runtime",
]
