from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ace_lite.dev_feedback_taxonomy import normalize_dev_feedback_reason_code
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DEFAULT_EVENT_CLASS,
    RUNTIME_STATS_DOCTOR_EVENT_CLASS,
    RUNTIME_STATS_EVENT_CLASS_VALUES,
    RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_DECISION_VALUES,
    RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_PHASE_VALUES,
    RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_REASON_CODES,
    RUNTIME_STATS_STAGE_NAMES,
    RUNTIME_STATS_STATUS_VALUES,
)

BRANCH_VALIDATION_ARCHIVE_SCHEMA_VERSION = "branch_validation_archive_v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any, *, max_len: int = 255) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return " ".join(raw.split())[:max_len]


def _normalize_latency(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        return 0.0
    if parsed < 0.0:
        return 0.0
    return round(parsed, 6)


def _normalize_count(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        return 0
    return max(0, parsed)


@dataclass(frozen=True, slots=True)
class RuntimeStageLatency:
    stage_name: str
    elapsed_ms: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True, slots=True)
class RuntimeInvocationStats:
    invocation_id: str
    session_id: str
    repo_key: str
    profile_key: str = ""
    event_class: str = RUNTIME_STATS_DEFAULT_EVENT_CLASS
    settings_fingerprint: str = ""
    status: str = "succeeded"
    total_latency_ms: float = 0.0
    started_at: str = ""
    finished_at: str = ""
    contract_error_code: str = ""
    degraded_reason_codes: tuple[str, ...] = ()
    stage_latencies: tuple[RuntimeStageLatency, ...] = ()
    learning_router_rollout_decision: dict[str, Any] = field(default_factory=dict)
    plan_replay_hit: bool = False
    plan_replay_safe_hit: bool = False
    plan_replay_store_written: bool = False
    trace_exported: bool = False
    trace_export_failed: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "session_id": self.session_id,
            "repo_key": self.repo_key,
            "profile_key": self.profile_key,
            "event_class": self.event_class,
            "settings_fingerprint": self.settings_fingerprint,
            "status": self.status,
            "total_latency_ms": self.total_latency_ms,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "contract_error_code": self.contract_error_code,
            "degraded_reason_codes": list(self.degraded_reason_codes),
            "stage_latencies": [item.to_payload() for item in self.stage_latencies],
            "learning_router_rollout_decision": dict(
                self.learning_router_rollout_decision
            ),
            "plan_replay_hit": self.plan_replay_hit,
            "plan_replay_safe_hit": self.plan_replay_safe_hit,
            "plan_replay_store_written": self.plan_replay_store_written,
            "trace_exported": self.trace_exported,
            "trace_export_failed": self.trace_export_failed,
        }

    def to_storage_payload(self) -> dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "session_id": self.session_id,
            "repo_key": self.repo_key,
            "profile_key": self.profile_key,
            "event_class": self.event_class,
            "settings_fingerprint": self.settings_fingerprint,
            "status": self.status,
            "total_latency_ms": self.total_latency_ms,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "contract_error_code": self.contract_error_code,
            "degraded_reason_codes": json.dumps(
                list(self.degraded_reason_codes),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "stage_latency_json": json.dumps(
                [item.to_payload() for item in self.stage_latencies],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "learning_router_rollout_json": json.dumps(
                dict(self.learning_router_rollout_decision),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "plan_replay_hit": 1 if self.plan_replay_hit else 0,
            "plan_replay_safe_hit": 1 if self.plan_replay_safe_hit else 0,
            "plan_replay_store_written": 1 if self.plan_replay_store_written else 0,
            "trace_exported": 1 if self.trace_exported else 0,
            "trace_export_failed": 1 if self.trace_export_failed else 0,
        }


@dataclass(frozen=True, slots=True)
class RuntimeScopeRollup:
    scope_kind: str
    scope_key: str
    repo_key: str
    profile_key: str
    counters: dict[str, int]
    latency: dict[str, float]
    updated_at: str
    stage_latencies: tuple[dict[str, Any], ...]
    degraded_states: tuple[dict[str, Any], ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "scope_kind": self.scope_kind,
            "scope_key": self.scope_key,
            "repo_key": self.repo_key,
            "profile_key": self.profile_key,
            "counters": dict(self.counters),
            "latency": dict(self.latency),
            "updated_at": self.updated_at,
            "stage_latencies": [dict(item) for item in self.stage_latencies],
            "degraded_states": [dict(item) for item in self.degraded_states],
        }


@dataclass(frozen=True, slots=True)
class RuntimeStatsSnapshot:
    scopes: tuple[RuntimeScopeRollup, ...]

    def to_payload(self) -> dict[str, Any]:
        return {"scopes": [item.to_payload() for item in self.scopes]}


def normalize_runtime_stage_latencies(value: Any) -> tuple[RuntimeStageLatency, ...]:
    rows = value if isinstance(value, (list, tuple)) else ()
    normalized: dict[str, RuntimeStageLatency] = {}
    stage_order = {name: index for index, name in enumerate(RUNTIME_STATS_STAGE_NAMES)}
    for item in rows:
        if isinstance(item, RuntimeStageLatency):
            stage_name = _normalize_text(item.stage_name, max_len=64)
            elapsed_ms = _normalize_latency(item.elapsed_ms)
        elif isinstance(item, dict):
            stage_name = _normalize_text(item.get("stage_name"), max_len=64)
            if not stage_name:
                stage_name = _normalize_text(item.get("stage"), max_len=64)
            elapsed_ms = _normalize_latency(item.get("elapsed_ms"))
        else:
            continue
        if not stage_name:
            continue
        normalized[stage_name] = RuntimeStageLatency(
            stage_name=stage_name,
            elapsed_ms=elapsed_ms,
        )
    ordered = sorted(
        normalized.values(),
        key=lambda item: (stage_order.get(item.stage_name, 999), item.stage_name),
    )
    return tuple(ordered)


def normalize_runtime_degraded_reason_codes(value: Any) -> tuple[str, ...]:
    rows = value if isinstance(value, (list, tuple, set)) else ()
    normalized: set[str] = set()
    for item in rows:
        reason = normalize_dev_feedback_reason_code(
            _normalize_text(item, max_len=128).lower(),
            default="",
        )
        if not reason:
            continue
        normalized.add(reason)
    return tuple(sorted(normalized))


def normalize_runtime_learning_router_rollout_decision(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    normalized: dict[str, Any] = {}
    for key, raw_value in payload.items():
        normalized_key = _normalize_text(key, max_len=128)
        if not normalized_key:
            continue
        if isinstance(raw_value, bool):
            normalized[normalized_key] = raw_value
        elif isinstance(raw_value, int):
            normalized[normalized_key] = _normalize_count(raw_value)
        elif isinstance(raw_value, float):
            normalized[normalized_key] = _normalize_latency(raw_value)
        elif isinstance(raw_value, str):
            normalized[normalized_key] = _normalize_text(raw_value, max_len=255)
        elif isinstance(raw_value, (list, tuple)):
            normalized[normalized_key] = [
                item
                for item in (
                    _normalize_text(candidate, max_len=255) for candidate in raw_value
                )
                if item
            ]
    return normalized


def normalize_runtime_invocation_stats(
    stats: RuntimeInvocationStats | dict[str, Any],
) -> RuntimeInvocationStats:
    raw = stats if isinstance(stats, dict) else asdict(stats)
    invocation_id = _normalize_text(raw.get("invocation_id"), max_len=128)
    session_id = _normalize_text(raw.get("session_id"), max_len=128)
    repo_key = _normalize_text(raw.get("repo_key"), max_len=255)
    if not invocation_id:
        raise ValueError("invocation_id must be non-empty")
    if not session_id:
        raise ValueError("session_id must be non-empty")
    if not repo_key:
        raise ValueError("repo_key must be non-empty")
    raw_event_class = _normalize_text(raw.get("event_class"), max_len=64).lower()
    if session_id.startswith("runtime-doctor::") and raw_event_class in {
        "",
        RUNTIME_STATS_DEFAULT_EVENT_CLASS,
    }:
        event_class = RUNTIME_STATS_DOCTOR_EVENT_CLASS
    else:
        event_class = raw_event_class or RUNTIME_STATS_DEFAULT_EVENT_CLASS
    if event_class not in RUNTIME_STATS_EVENT_CLASS_VALUES:
        raise ValueError(f"unsupported runtime stats event_class: {event_class}")

    status = _normalize_text(raw.get("status"), max_len=32).lower() or "succeeded"
    if status not in RUNTIME_STATS_STATUS_VALUES:
        raise ValueError(f"unsupported runtime stats status: {status}")

    started_at = _normalize_text(raw.get("started_at"), max_len=64) or utc_now_iso()
    finished_at = _normalize_text(raw.get("finished_at"), max_len=64) or started_at
    return RuntimeInvocationStats(
        invocation_id=invocation_id,
        session_id=session_id,
        repo_key=repo_key,
        profile_key=_normalize_text(raw.get("profile_key"), max_len=128),
        event_class=event_class,
        settings_fingerprint=_normalize_text(
            raw.get("settings_fingerprint"),
            max_len=128,
        ),
        status=status,
        total_latency_ms=_normalize_latency(raw.get("total_latency_ms")),
        started_at=started_at,
        finished_at=finished_at,
        contract_error_code=_normalize_text(
            raw.get("contract_error_code"),
            max_len=128,
        ),
        degraded_reason_codes=normalize_runtime_degraded_reason_codes(
            raw.get("degraded_reason_codes")
        ),
        stage_latencies=normalize_runtime_stage_latencies(raw.get("stage_latencies")),
        learning_router_rollout_decision=normalize_runtime_learning_router_rollout_decision(
            raw.get("learning_router_rollout_decision")
        ),
        plan_replay_hit=bool(raw.get("plan_replay_hit")),
        plan_replay_safe_hit=bool(raw.get("plan_replay_safe_hit")),
        plan_replay_store_written=bool(raw.get("plan_replay_store_written")),
        trace_exported=bool(raw.get("trace_exported")),
        trace_export_failed=bool(raw.get("trace_export_failed")),
    )


def build_learning_router_rollout_decision_payload(
    *,
    adaptive_router: dict[str, Any] | None,
    card_summary: dict[str, Any] | None,
    validation_feedback_summary: dict[str, Any] | None,
    failure_signal_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    router = adaptive_router if isinstance(adaptive_router, dict) else {}
    cards = card_summary if isinstance(card_summary, dict) else {}
    validation_feedback = (
        validation_feedback_summary
        if isinstance(validation_feedback_summary, dict)
        else {}
    )
    failure_signal = (
        failure_signal_summary if isinstance(failure_signal_summary, dict) else {}
    )
    online_bandit = (
        router.get("online_bandit")
        if isinstance(router.get("online_bandit"), dict)
        else {}
    )
    online_bandit_payload = online_bandit if isinstance(online_bandit, dict) else {}

    phase = "report_only"
    if phase not in RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_PHASE_VALUES:
        phase = RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_PHASE_VALUES[0]

    decision = "stay_report_only"
    if decision not in RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_DECISION_VALUES:
        decision = RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_DECISION_VALUES[0]

    router_enabled = bool(router.get("enabled", False))
    router_mode = _normalize_text(router.get("mode"), max_len=32).lower() or "disabled"
    router_arm_id = _normalize_text(router.get("arm_id"), max_len=128)
    router_source = _normalize_text(router.get("source"), max_len=64)
    shadow_arm_id = _normalize_text(router.get("shadow_arm_id"), max_len=128)
    shadow_source = _normalize_text(router.get("shadow_source"), max_len=64)
    evidence_card_count = _normalize_count(cards.get("evidence_card_count"))
    validation_card_present = bool(cards.get("validation_card_present", False))
    validation_feedback_present = bool(validation_feedback) or validation_card_present
    failure_signal_status = (
        _normalize_text(failure_signal.get("status"), max_len=32).lower() or "skipped"
    )
    failure_signal_has_failure = bool(
        failure_signal.get("has_failure", False)
        or failure_signal_status in {"failed", "degraded", "timeout"}
        or _normalize_count(failure_signal.get("issue_count")) > 0
        or _normalize_count(failure_signal.get("probe_issue_count")) > 0
    )
    eligible_for_guarded_rollout = False
    reason = "adaptive_router_disabled"
    if router_enabled:
        if router_mode != "shadow":
            reason = "adaptive_router_not_shadow"
        elif not shadow_arm_id:
            reason = "shadow_arm_missing"
        elif evidence_card_count <= 0:
            reason = "missing_source_plan_cards"
        elif failure_signal_has_failure:
            reason = "failure_signal_present"
        else:
            reason = "eligible_pending_guarded_rollout"
            eligible_for_guarded_rollout = True
    if reason not in RUNTIME_STATS_LEARNING_ROUTER_ROLLOUT_REASON_CODES:
        reason = "adaptive_router_disabled"

    return {
        "phase": phase,
        "decision": decision,
        "reason": reason,
        "eligible_for_guarded_rollout": eligible_for_guarded_rollout,
        "router_enabled": router_enabled,
        "router_mode": router_mode,
        "router_arm_id": router_arm_id,
        "router_source": router_source,
        "shadow_arm_id": shadow_arm_id,
        "shadow_source": shadow_source,
        "online_bandit_requested": bool(online_bandit_payload.get("requested", False)),
        "online_bandit_eligible": bool(online_bandit_payload.get("eligible", False)),
        "online_bandit_active": bool(online_bandit_payload.get("active", False)),
        "evidence_card_count": evidence_card_count,
        "validation_card_present": validation_card_present,
        "validation_feedback_present": validation_feedback_present,
        "validation_selected_test_count": _normalize_count(
            validation_feedback.get("selected_test_count")
        ),
        "validation_executed_test_count": _normalize_count(
            validation_feedback.get("executed_test_count")
        ),
        "failure_signal_status": failure_signal_status,
        "failure_signal_has_failure": failure_signal_has_failure,
        "failure_signal_issue_count": _normalize_count(
            failure_signal.get("issue_count")
        ),
        "failure_signal_probe_issue_count": _normalize_count(
            failure_signal.get("probe_issue_count")
        ),
        "failure_signal_source": _normalize_text(
            failure_signal.get("source"),
            max_len=64,
        ),
    }


def build_branch_validation_archive_payload(
    *,
    branch_batch: dict[str, Any] | None,
    branch_selection: dict[str, Any] | None,
) -> dict[str, Any]:
    batch = branch_batch if isinstance(branch_batch, dict) else {}
    selection = branch_selection if isinstance(branch_selection, dict) else {}
    winner_branch_id = _normalize_text(selection.get("winner_branch_id"), max_len=128)
    candidates = (
        batch.get("candidates", [])
        if isinstance(batch.get("candidates"), list)
        else []
    )
    winner_artifact_refs: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        branch_id = _normalize_text(item.get("branch_id"), max_len=128)
        if branch_id != winner_branch_id:
            continue
        artifact_rows = item.get("artifact_refs", [])
        if not isinstance(artifact_rows, list):
            continue
        winner_artifact_refs = [
            ref
            for ref in (
                _normalize_text(candidate, max_len=255) for candidate in artifact_rows
            )
            if ref
        ]
        break

    rejected_rows = (
        selection.get("rejected", [])
        if isinstance(selection.get("rejected"), list)
        else []
    )
    rejected: list[dict[str, Any]] = []
    for item in rejected_rows:
        if not isinstance(item, dict):
            continue
        branch_id = _normalize_text(item.get("branch_id"), max_len=128)
        rejected_reason = _normalize_text(item.get("rejected_reason"), max_len=128)
        if not branch_id:
            continue
        rejected.append(
            {
                "branch_id": branch_id,
                "rejected_reason": rejected_reason,
            }
        )

    return {
        "schema_version": BRANCH_VALIDATION_ARCHIVE_SCHEMA_VERSION,
        "winner_branch_id": winner_branch_id,
        "winner_artifact_refs": winner_artifact_refs,
        "rejected": rejected,
        "candidate_count": _normalize_count(batch.get("candidate_count")),
    }


__all__ = [
    "BRANCH_VALIDATION_ARCHIVE_SCHEMA_VERSION",
    "RuntimeInvocationStats",
    "RuntimeScopeRollup",
    "RuntimeStageLatency",
    "RuntimeStatsSnapshot",
    "build_branch_validation_archive_payload",
    "build_learning_router_rollout_decision_payload",
    "normalize_runtime_degraded_reason_codes",
    "normalize_runtime_invocation_stats",
    "normalize_runtime_learning_router_rollout_decision",
    "normalize_runtime_stage_latencies",
    "utc_now_iso",
]
