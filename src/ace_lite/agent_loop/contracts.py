from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AGENT_LOOP_ACTION_SCHEMA_VERSION = "agent_loop_action_v1"
AGENT_LOOP_ACTION_TYPES = (
    "request_more_context",
    "request_source_plan_retry",
    "request_validation_retry",
)
AGENT_LOOP_RERUN_POLICY_SCHEMA_VERSION = "agent_loop_rerun_policy_v1"
AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION = "agent_loop_branch_batch_v1"
_ACTION_TAXONOMY: dict[str, dict[str, str]] = {
    "request_more_context": {
        "action_category": "retrieval",
        "policy_id": "retrieval_refresh",
        "query_mode": "incremental",
    },
    "request_source_plan_retry": {
        "action_category": "source_plan",
        "policy_id": "source_plan_refresh",
        "query_mode": "reuse",
    },
    "request_validation_retry": {
        "action_category": "validation",
        "policy_id": "validation_retry",
        "query_mode": "reuse",
    },
}


def _normalize_text(value: Any, *, default: str = "") -> str:
    return str(value or default).strip()


def _normalize_text_list(*, value: Any, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{context}[{index}] must be a string")
        text = item.strip().replace("\\", "/")
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class AgentLoopActionV1:
    action_type: str
    reason: str
    query_hint: str
    focus_paths: tuple[str, ...]
    selected_tests: tuple[str, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AGENT_LOOP_ACTION_SCHEMA_VERSION,
            "action_type": self.action_type,
            "reason": self.reason,
            "query_hint": self.query_hint,
            "focus_paths": list(self.focus_paths),
            "selected_tests": list(self.selected_tests),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AgentLoopRerunPolicyV1:
    action_type: str
    action_category: str
    policy_id: str
    query_mode: str
    rerun_stages: tuple[str, ...]
    replay_safe: bool
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AGENT_LOOP_RERUN_POLICY_SCHEMA_VERSION,
            "action_type": self.action_type,
            "action_category": self.action_category,
            "policy_id": self.policy_id,
            "query_mode": self.query_mode,
            "rerun_stages": list(self.rerun_stages),
            "replay_safe": self.replay_safe,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AgentLoopBranchBatchCandidateV1:
    branch_id: str
    patch_scope_lines: int
    artifact_refs: tuple[str, ...]
    validation_branch_score: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "patch_scope_lines": self.patch_scope_lines,
            "artifact_refs": list(self.artifact_refs),
            "validation_branch_score": dict(self.validation_branch_score),
        }


@dataclass(frozen=True, slots=True)
class AgentLoopBranchBatchV1:
    candidates: tuple[AgentLoopBranchBatchCandidateV1, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION,
            "candidate_count": len(self.candidates),
            "candidates": [item.as_dict() for item in self.candidates],
            "metadata": dict(self.metadata),
        }


def build_agent_loop_action_v1(
    *,
    action_type: str,
    reason: str,
    query_hint: str = "",
    focus_paths: list[str] | None = None,
    selected_tests: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentLoopActionV1:
    normalized_action_type = _normalize_text(action_type).lower()
    if normalized_action_type not in AGENT_LOOP_ACTION_TYPES:
        raise ValueError(
            f"action_type must be one of: {', '.join(AGENT_LOOP_ACTION_TYPES)}"
        )
    normalized_reason = _normalize_text(reason)
    if not normalized_reason:
        raise ValueError("reason cannot be empty")

    normalized_query_hint = _normalize_text(query_hint)
    normalized_focus_paths = _normalize_text_list(
        value=focus_paths,
        context="focus_paths",
    )
    normalized_selected_tests = _normalize_text_list(
        value=selected_tests,
        context="selected_tests",
    )
    if normalized_action_type == "request_more_context" and (
        not normalized_query_hint and not normalized_focus_paths
    ):
        raise ValueError(
            "request_more_context requires query_hint or focus_paths"
        )
    return AgentLoopActionV1(
        action_type=normalized_action_type,
        reason=normalized_reason,
        query_hint=normalized_query_hint,
        focus_paths=normalized_focus_paths,
        selected_tests=normalized_selected_tests,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def build_agent_loop_branch_batch_v1(
    *,
    candidates: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> AgentLoopBranchBatchV1:
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a non-empty list")

    normalized_candidates: list[AgentLoopBranchBatchCandidateV1] = []
    seen_branch_ids: set[str] = set()
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise ValueError(f"candidates[{index}] must be a mapping")
        branch_id = _normalize_text(item.get("branch_id"))
        if not branch_id:
            raise ValueError(f"candidates[{index}].branch_id cannot be empty")
        if branch_id in seen_branch_ids:
            raise ValueError(f"candidates[{index}].branch_id must be unique")
        seen_branch_ids.add(branch_id)
        patch_scope_lines = max(0, int(item.get("patch_scope_lines", 0) or 0))
        artifact_refs = _normalize_text_list(
            value=item.get("artifact_refs"),
            context=f"candidates[{index}].artifact_refs",
        )
        validation_branch_score = item.get("validation_branch_score", {})
        if not isinstance(validation_branch_score, dict):
            raise ValueError(
                f"candidates[{index}].validation_branch_score must be a mapping"
            )
        normalized_candidates.append(
            AgentLoopBranchBatchCandidateV1(
                branch_id=branch_id,
                patch_scope_lines=patch_scope_lines,
                artifact_refs=artifact_refs,
                validation_branch_score=dict(validation_branch_score),
            )
        )

    return AgentLoopBranchBatchV1(
        candidates=tuple(normalized_candidates),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def build_agent_loop_rerun_policy_v1(
    *,
    action_type: str,
    rerun_stages: list[str] | tuple[str, ...],
    replay_safe: bool = True,
    metadata: dict[str, Any] | None = None,
) -> AgentLoopRerunPolicyV1:
    normalized_action_type = _normalize_text(action_type).lower()
    if normalized_action_type not in AGENT_LOOP_ACTION_TYPES:
        raise ValueError(
            f"action_type must be one of: {', '.join(AGENT_LOOP_ACTION_TYPES)}"
        )
    normalized_rerun_stages = _normalize_text_list(
        value=list(rerun_stages),
        context="rerun_stages",
    )
    taxonomy = _ACTION_TAXONOMY[normalized_action_type]
    return AgentLoopRerunPolicyV1(
        action_type=normalized_action_type,
        action_category=taxonomy["action_category"],
        policy_id=taxonomy["policy_id"],
        query_mode=taxonomy["query_mode"],
        rerun_stages=normalized_rerun_stages,
        replay_safe=bool(replay_safe),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def validate_agent_loop_action_v1(
    *,
    contract: AgentLoopActionV1 | dict[str, Any],
    strict: bool = True,
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload = contract.as_dict() if isinstance(contract, AgentLoopActionV1) else contract
    if not isinstance(payload, dict):
        raise ValueError("contract must be AgentLoopActionV1 or a mapping payload")

    violation_details: list[dict[str, Any]] = []

    def _add_violation(
        *,
        code: str,
        field: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        violation_details.append(
            {
                "code": code,
                "severity": "error",
                "field": field,
                "message": message,
                "context": dict(context) if isinstance(context, dict) else {},
            }
        )

    if payload.get("schema_version") != AGENT_LOOP_ACTION_SCHEMA_VERSION:
        _add_violation(
            code="agent_loop_action_schema_version_invalid",
            field="schema_version",
            message="schema_version must match agent_loop_action_v1",
        )

    action_type = _normalize_text(payload.get("action_type")).lower()
    if action_type not in AGENT_LOOP_ACTION_TYPES:
        _add_violation(
            code="agent_loop_action_type_invalid",
            field="action_type",
            message=f"action_type must be one of: {', '.join(AGENT_LOOP_ACTION_TYPES)}",
        )

    reason = _normalize_text(payload.get("reason"))
    if not reason:
        _add_violation(
            code="agent_loop_action_reason_invalid",
            field="reason",
            message="reason must be a non-empty string",
        )

    try:
        normalized_focus_paths = _normalize_text_list(
            value=payload.get("focus_paths"),
            context="focus_paths",
        )
    except ValueError as exc:
        normalized_focus_paths = ()
        _add_violation(
            code="agent_loop_action_focus_paths_invalid",
            field="focus_paths",
            message=str(exc),
        )

    try:
        normalized_selected_tests = _normalize_text_list(
            value=payload.get("selected_tests"),
            context="selected_tests",
        )
    except ValueError as exc:
        normalized_selected_tests = ()
        _add_violation(
            code="agent_loop_action_selected_tests_invalid",
            field="selected_tests",
            message=str(exc),
        )

    query_hint = _normalize_text(payload.get("query_hint"))
    if strict and action_type == "request_more_context" and (
        not query_hint and not normalized_focus_paths
    ):
        _add_violation(
            code="agent_loop_action_more_context_missing_signal",
            field="query_hint",
            message="request_more_context requires query_hint or focus_paths",
        )

    if not isinstance(payload.get("metadata", {}), dict):
        _add_violation(
            code="agent_loop_action_metadata_invalid",
            field="metadata",
            message="metadata must be a mapping when present",
        )

    ok = len(violation_details) == 0
    normalized_action = (
        build_agent_loop_action_v1(
            action_type=action_type,
            reason=reason,
            query_hint=query_hint,
            focus_paths=list(normalized_focus_paths),
            selected_tests=list(normalized_selected_tests),
            metadata=payload.get("metadata", {}),
        ).as_dict()
        if ok
        else None
    )
    violations = [item["code"] for item in violation_details]
    return {
        "ok": ok,
        "strict": bool(strict),
        "fail_closed": bool(fail_closed),
        "violations": violations,
        "violation_details": violation_details,
        "action": normalized_action,
    }


def validate_agent_loop_branch_batch_v1(
    *,
    contract: AgentLoopBranchBatchV1 | dict[str, Any],
    strict: bool = True,
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload = contract.as_dict() if isinstance(contract, AgentLoopBranchBatchV1) else contract
    if not isinstance(payload, dict):
        raise ValueError("contract must be AgentLoopBranchBatchV1 or a mapping payload")

    violation_details: list[dict[str, Any]] = []

    def _add_violation(
        *,
        code: str,
        field: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        violation_details.append(
            {
                "code": code,
                "severity": "error",
                "field": field,
                "message": message,
                "context": dict(context) if isinstance(context, dict) else {},
            }
        )

    if payload.get("schema_version") != AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION:
        _add_violation(
            code="agent_loop_branch_batch_schema_version_invalid",
            field="schema_version",
            message="schema_version must match agent_loop_branch_batch_v1",
        )

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        _add_violation(
            code="agent_loop_branch_batch_candidates_invalid",
            field="candidates",
            message="candidates must be a list",
        )
        candidates = []

    seen_branch_ids: set[str] = set()
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            _add_violation(
                code="agent_loop_branch_batch_candidate_entry_invalid",
                field=f"candidates[{index}]",
                message="candidate entry must be a mapping",
            )
            continue
        branch_id = _normalize_text(item.get("branch_id"))
        if not branch_id:
            _add_violation(
                code="agent_loop_branch_batch_branch_id_invalid",
                field=f"candidates[{index}].branch_id",
                message="branch_id must be a non-empty string",
            )
        elif branch_id in seen_branch_ids:
            _add_violation(
                code="agent_loop_branch_batch_branch_id_duplicate",
                field=f"candidates[{index}].branch_id",
                message="branch_id must be unique",
                context={"branch_id": branch_id},
            )
        else:
            seen_branch_ids.add(branch_id)
        if not isinstance(item.get("patch_scope_lines", 0), (int, float)):
            _add_violation(
                code="agent_loop_branch_batch_patch_scope_invalid",
                field=f"candidates[{index}].patch_scope_lines",
                message="patch_scope_lines must be numeric",
            )
        if not isinstance(item.get("artifact_refs", []), list):
            _add_violation(
                code="agent_loop_branch_batch_artifact_refs_invalid",
                field=f"candidates[{index}].artifact_refs",
                message="artifact_refs must be a list",
            )
        if not isinstance(item.get("validation_branch_score", {}), dict):
            _add_violation(
                code="agent_loop_branch_batch_validation_score_invalid",
                field=f"candidates[{index}].validation_branch_score",
                message="validation_branch_score must be a mapping",
            )

    if strict and not candidates:
        _add_violation(
            code="agent_loop_branch_batch_candidates_empty",
            field="candidates",
            message="candidates must be non-empty in strict mode",
        )

    if not isinstance(payload.get("candidate_count"), (int, float)):
        _add_violation(
            code="agent_loop_branch_batch_candidate_count_invalid",
            field="candidate_count",
            message="candidate_count must be numeric",
        )
    if not isinstance(payload.get("metadata", {}), dict):
        _add_violation(
            code="agent_loop_branch_batch_metadata_invalid",
            field="metadata",
            message="metadata must be a mapping when present",
        )

    violations = [item["code"] for item in violation_details]
    normalized_batch = None
    if not violations:
        normalized_batch = build_agent_loop_branch_batch_v1(
            candidates=list(candidates),
            metadata=payload.get("metadata", {}),
        ).as_dict()
    return {
        "ok": not violations,
        "strict": bool(strict),
        "fail_closed": bool(fail_closed),
        "violations": violations,
        "violation_details": violation_details,
        "batch": normalized_batch,
    }


__all__ = [
    "AGENT_LOOP_ACTION_SCHEMA_VERSION",
    "AGENT_LOOP_ACTION_TYPES",
    "AGENT_LOOP_BRANCH_BATCH_SCHEMA_VERSION",
    "AGENT_LOOP_RERUN_POLICY_SCHEMA_VERSION",
    "AgentLoopActionV1",
    "AgentLoopBranchBatchCandidateV1",
    "AgentLoopBranchBatchV1",
    "AgentLoopRerunPolicyV1",
    "build_agent_loop_action_v1",
    "build_agent_loop_branch_batch_v1",
    "build_agent_loop_rerun_policy_v1",
    "validate_agent_loop_action_v1",
    "validate_agent_loop_branch_batch_v1",
]
