from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.memory_long_term.contracts import build_long_term_observation_contract_v1
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
            metadata={"stage": stage_name},
        )
        entry = self._store.upsert_observation(contract)
        return {
            "ok": True,
            "skipped": False,
            "stage": stage_name,
            "handle": entry.handle,
            "as_of": entry.as_of,
            "status": payload.get("status", "captured"),
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
