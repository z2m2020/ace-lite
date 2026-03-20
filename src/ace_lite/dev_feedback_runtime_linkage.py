from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.dev_feedback_store import DevFeedbackStore, DevIssue
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_store import DurableStatsStore


def resolve_runtime_stats_store_path(
    *,
    stats_db_path: str | Path | None,
) -> str | None:
    return str(Path(stats_db_path).expanduser().resolve()) if stats_db_path else None


def resolve_reason_code_for_invocation(
    *,
    invocation: RuntimeInvocationStats,
    reason_code: str | None,
) -> str:
    normalized = " ".join(str(reason_code or "").strip().split()).lower().replace(" ", "_")
    if normalized:
        return normalized
    candidates = [
        str(item).strip() for item in invocation.degraded_reason_codes if str(item).strip()
    ]
    if not candidates and str(invocation.contract_error_code or "").strip():
        return "contract_error"
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError(
            "reason_code is required when the runtime invocation has multiple degraded reasons"
        )
    raise ValueError("runtime invocation does not expose a promotable degraded reason")


def build_dev_issue_payload_from_runtime_invocation(
    *,
    invocation: RuntimeInvocationStats,
    reason_code: str | None,
    title: str | None,
    notes: str | None,
    status: str | None,
    user_id: str | None,
    profile_key: str | None,
    issue_id: str | None,
) -> dict[str, Any]:
    resolved_reason = resolve_reason_code_for_invocation(
        invocation=invocation,
        reason_code=reason_code,
    )
    normalized_title = " ".join(str(title or "").strip().split())
    note_lines = [
        "auto_captured_from=runtime_stats",
        f"runtime_status={invocation.status}",
        f"reason_code={resolved_reason}",
        f"total_latency_ms={invocation.total_latency_ms:.6f}",
        f"started_at={invocation.started_at}",
        f"finished_at={invocation.finished_at}",
        f"settings_fingerprint={invocation.settings_fingerprint}",
        f"plan_replay_hit={bool(invocation.plan_replay_hit)}",
        f"plan_replay_safe_hit={bool(invocation.plan_replay_safe_hit)}",
        f"plan_replay_store_written={bool(invocation.plan_replay_store_written)}",
        f"trace_exported={bool(invocation.trace_exported)}",
        f"trace_export_failed={bool(invocation.trace_export_failed)}",
    ]
    if invocation.degraded_reason_codes:
        note_lines.append(
            "degraded_reason_codes=" + ",".join(invocation.degraded_reason_codes)
        )
    if str(invocation.contract_error_code or "").strip():
        note_lines.append(f"contract_error_code={invocation.contract_error_code}")
    if str(notes or "").strip():
        note_lines.append("user_notes=" + " ".join(str(notes).strip().split()))

    occurred_at = str(invocation.finished_at or invocation.started_at).strip()
    return {
        "issue_id": issue_id,
        "title": normalized_title or f"Auto-captured runtime event: {resolved_reason}",
        "reason_code": resolved_reason,
        "status": status or "open",
        "repo": invocation.repo_key,
        "user_id": user_id,
        "profile_key": " ".join(str(profile_key or "").strip().split()) or invocation.profile_key,
        "query": "",
        "selected_path": "",
        "related_invocation_id": invocation.invocation_id,
        "notes": "\n".join(line for line in note_lines if line),
        "created_at": occurred_at,
        "updated_at": occurred_at,
        "resolved_at": "",
    }


def record_dev_issue_from_runtime_invocation(
    *,
    invocation_id: str,
    stats_db_path: str | Path | None,
    store_path: str | Path | None,
    reason_code: str | None,
    title: str | None,
    notes: str | None,
    status: str | None,
    user_id: str | None,
    profile_key: str | None,
    issue_id: str | None,
) -> tuple[DevIssue, RuntimeInvocationStats, str, str]:
    runtime_store = DurableStatsStore(
        db_path=resolve_runtime_stats_store_path(stats_db_path=stats_db_path)
    )
    invocation = runtime_store.read_invocation(invocation_id=invocation_id)
    if invocation is None:
        raise ValueError(f"runtime invocation not found: {invocation_id}")

    store = DevFeedbackStore(db_path=store_path)
    issue = store.record_issue(
        build_dev_issue_payload_from_runtime_invocation(
            invocation=invocation,
            reason_code=reason_code,
            title=title,
            notes=notes,
            status=status,
            user_id=user_id,
            profile_key=profile_key,
            issue_id=issue_id,
        )
    )
    return issue, invocation, str(store.db_path), str(runtime_store.db_path)


__all__ = [
    "build_dev_issue_payload_from_runtime_invocation",
    "record_dev_issue_from_runtime_invocation",
    "resolve_reason_code_for_invocation",
    "resolve_runtime_stats_store_path",
]
