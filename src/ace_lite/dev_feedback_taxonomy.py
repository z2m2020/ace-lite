from __future__ import annotations

from typing import Any


_REASON_ALIASES = {
    "docs_timeout": "parallel_docs_timeout",
    "document_timeout": "parallel_docs_timeout",
    "worktree_timeout": "parallel_worktree_timeout",
    "sandbox_timeout": "validation_timeout",
    "validation_timed_out": "validation_timeout",
    "manual_selection_override": "manual_override",
    "selection_override": "manual_override",
    "manual_path_override": "manual_override",
    "repeated_retries": "repeated_retry",
    "retry_loop": "repeated_retry",
    "retry_exhausted": "repeated_retry",
    "patch_apply_failed": "validation_apply_failed",
    "apply_failed": "validation_apply_failed",
    "budget_exceeded": "latency_budget_exceeded",
    "time_budget_exceeded": "latency_budget_exceeded",
    "slo_downgrade": "latency_budget_exceeded",
    "low_support_chunk": "evidence_insufficient",
    "missing_validation": "evidence_insufficient",
    "no_candidate": "evidence_insufficient",
    "cache_corruption": "stage_artifact_cache_corrupt",
    "stage_artifact_cache_error": "stage_artifact_cache_corrupt",
    "editable_install_drift": "install_drift",
}

_REASON_METADATA = {
    "memory_fallback": {"reason_family": "memory", "capture_class": "fallback"},
    "memory_namespace_fallback": {
        "reason_family": "memory",
        "capture_class": "fallback",
    },
    "candidate_ranker_fallback": {
        "reason_family": "retrieval",
        "capture_class": "fallback",
    },
    "plan_replay_invalid_cached_payload": {
        "reason_family": "plan_replay",
        "capture_class": "cache_integrity",
    },
    "plan_replay_store_failed": {
        "reason_family": "plan_replay",
        "capture_class": "cache_write_failure",
    },
    "embedding_time_budget_exceeded": {
        "reason_family": "embeddings",
        "capture_class": "budget",
    },
    "embedding_fallback": {
        "reason_family": "embeddings",
        "capture_class": "fallback",
    },
    "chunk_semantic_time_budget_exceeded": {
        "reason_family": "chunking",
        "capture_class": "budget",
    },
    "chunk_semantic_fallback": {
        "reason_family": "chunking",
        "capture_class": "fallback",
    },
    "chunk_guard_fallback": {
        "reason_family": "chunking",
        "capture_class": "fallback",
    },
    "parallel_docs_timeout": {
        "reason_family": "parallelism",
        "capture_class": "timeout",
    },
    "parallel_worktree_timeout": {
        "reason_family": "parallelism",
        "capture_class": "timeout",
    },
    "xref_budget_exhausted": {
        "reason_family": "xref",
        "capture_class": "budget",
    },
    "skills_budget_exhausted": {
        "reason_family": "skills",
        "capture_class": "budget",
    },
    "router_fallback_applied": {
        "reason_family": "router",
        "capture_class": "fallback",
    },
    "plugin_policy_blocked": {
        "reason_family": "plugin_policy",
        "capture_class": "policy",
    },
    "plugin_policy_warn": {
        "reason_family": "plugin_policy",
        "capture_class": "policy",
    },
    "validation_timeout": {
        "reason_family": "validation",
        "capture_class": "timeout",
    },
    "validation_apply_failed": {
        "reason_family": "validation",
        "capture_class": "apply_failure",
    },
    "contract_error": {
        "reason_family": "contract",
        "capture_class": "contract_error",
    },
    "trace_export_failed": {
        "reason_family": "trace_export",
        "capture_class": "export_failure",
    },
    "stage_artifact_cache_corrupt": {
        "reason_family": "cache",
        "capture_class": "cache_integrity",
    },
    "git_unavailable": {
        "reason_family": "runtime_environment",
        "capture_class": "environment",
    },
    "install_drift": {
        "reason_family": "runtime_environment",
        "capture_class": "configuration_drift",
    },
    "evidence_insufficient": {
        "reason_family": "evidence",
        "capture_class": "insufficient_evidence",
    },
    "noisy_hit": {
        "reason_family": "evidence",
        "capture_class": "noisy_hit",
    },
    "manual_override": {
        "reason_family": "manual_action",
        "capture_class": "manual_override",
    },
    "repeated_retry": {
        "reason_family": "runtime",
        "capture_class": "retry",
    },
    "latency_budget_exceeded": {
        "reason_family": "runtime",
        "capture_class": "budget",
    },
}


def _normalize_reason_token(value: Any) -> str:
    normalized = " ".join(str(value or "").strip().split()).lower().replace(" ", "_")
    return normalized


def normalize_dev_feedback_reason_code(
    value: Any,
    *,
    default: str = "general",
) -> str:
    normalized = _normalize_reason_token(value)
    if not normalized:
        return default
    return _REASON_ALIASES.get(normalized, normalized)


def describe_dev_feedback_reason(reason_code: Any) -> dict[str, str]:
    canonical = normalize_dev_feedback_reason_code(reason_code, default="general")
    metadata = _REASON_METADATA.get(
        canonical,
        {"reason_family": "runtime", "capture_class": "general"},
    )
    return {
        "reason_code": canonical,
        "reason_family": str(metadata["reason_family"]),
        "capture_class": str(metadata["capture_class"]),
    }


def get_dev_feedback_reason_family(reason_code: Any) -> str:
    return describe_dev_feedback_reason(reason_code)["reason_family"]


def get_dev_feedback_capture_class(reason_code: Any) -> str:
    return describe_dev_feedback_reason(reason_code)["capture_class"]


KNOWN_DEV_FEEDBACK_REASON_CODES = tuple(sorted(_REASON_METADATA))


__all__ = [
    "KNOWN_DEV_FEEDBACK_REASON_CODES",
    "describe_dev_feedback_reason",
    "get_dev_feedback_capture_class",
    "get_dev_feedback_reason_family",
    "normalize_dev_feedback_reason_code",
]
