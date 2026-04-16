from __future__ import annotations

from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.registry import get_stage_descriptor

_LAYER_REPORT_ONLY_FIELDS = {
    "context_report",
    "retrieval_graph_view",
    "skill_catalog",
    "benchmark_report",
    "benchmark_summary",
    "checkpoint_artifacts",
}

_CONTEXT_REFINE_ACTIONS = ("keep", "downrank", "drop", "need_more_read")
_CONTEXT_REFINE_REVIEW_STATUSES = frozenset({"ok", "watch", "thin_context"})


def validate_stage_output(stage_name: str, output: Any) -> None:
    normalized = str(stage_name or "").strip().lower()
    descriptor = get_stage_descriptor(normalized)
    if descriptor is None or not descriptor.contract_enforced:
        return

    if not isinstance(output, dict):
        raise StageContractError(
            "stage output must be a dictionary",
            stage=normalized,
            error_code="stage_contract.invalid_type",
            reason=f"{normalized}.output",
            context={"type": type(output).__name__},
        )

    validator = STAGE_OUTPUT_VALIDATORS.get(normalized)
    if validator is None:
        return
    validator(output)


def _require_key(output: dict[str, Any], key: str, *, stage: str) -> Any:
    if key not in output:
        raise StageContractError(
            f"missing required stage output field: {key}",
            stage=stage,
            error_code="stage_contract.missing_key",
            reason=f"{stage}.{key}",
            context={"missing_key": key},
        )
    return output[key]


def _require_dict(output: dict[str, Any], key: str, *, stage: str) -> dict[str, Any]:
    value = _require_key(output, key, stage=stage)
    if not isinstance(value, dict):
        raise StageContractError(
            f"stage output field must be a dictionary: {key}",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.{key}",
            context={"key": key, "type": type(value).__name__},
        )
    return value


def _require_list(output: dict[str, Any], key: str, *, stage: str) -> list[Any]:
    value = _require_key(output, key, stage=stage)
    if not isinstance(value, list):
        raise StageContractError(
            f"stage output field must be a list: {key}",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.{key}",
            context={"key": key, "type": type(value).__name__},
        )
    return value


def _require_str(output: dict[str, Any], key: str, *, stage: str) -> str:
    value = _require_key(output, key, stage=stage)
    if not isinstance(value, str):
        raise StageContractError(
            f"stage output field must be a string: {key}",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.{key}",
            context={"key": key, "type": type(value).__name__},
        )
    return value


def _require_bool(output: dict[str, Any], key: str, *, stage: str) -> bool:
    value = _require_key(output, key, stage=stage)
    if not isinstance(value, bool):
        raise StageContractError(
            f"stage output field must be a bool: {key}",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.{key}",
            context={"key": key, "type": type(value).__name__},
        )
    return value


def _require_number(output: dict[str, Any], key: str, *, stage: str) -> float:
    value = _require_key(output, key, stage=stage)
    if not isinstance(value, (int, float)):
        raise StageContractError(
            f"stage output field must be numeric: {key}",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.{key}",
            context={"key": key, "type": type(value).__name__},
        )
    return float(value)


def _require_optional_str_list(output: dict[str, Any], key: str, *, stage: str) -> list[str]:
    value = _require_list(output, key, stage=stage)
    for item in value:
        if not isinstance(item, str):
            raise StageContractError(
                f"stage output field must contain only strings: {key}",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{stage}.{key}",
                context={"key": key, "type": type(item).__name__},
            )
    return [str(item) for item in value]


def _require_action_name(value: Any, *, stage: str, reason: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _CONTEXT_REFINE_ACTIONS:
        raise StageContractError(
            "context_refine action must be one of keep/downrank/drop/need_more_read",
            stage=stage,
            error_code="stage_contract.invalid_value",
            reason=reason,
            context={"action": value, "allowed_actions": list(_CONTEXT_REFINE_ACTIONS)},
        )
    return normalized


def _validate_context_refine_action_rows(
    rows: list[Any],
    *,
    stage: str,
    reason_prefix: str,
    require_qualified_name: bool,
) -> None:
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            raise StageContractError(
                "context_refine action rows must be dictionaries",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{reason_prefix}.{index}",
                context={"index": index, "type": type(item).__name__},
            )
        path = item.get("path")
        if not isinstance(path, str):
            raise StageContractError(
                "context_refine action row path must be a string",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{reason_prefix}.{index}.path",
                context={"index": index, "type": type(path).__name__},
            )
        if require_qualified_name:
            qualified_name = item.get("qualified_name")
            if not isinstance(qualified_name, str):
                raise StageContractError(
                    "context_refine chunk action row qualified_name must be a string",
                    stage=stage,
                    error_code="stage_contract.invalid_type",
                    reason=f"{reason_prefix}.{index}.qualified_name",
                    context={"index": index, "type": type(qualified_name).__name__},
                )
        score = item.get("score")
        if not isinstance(score, (int, float)):
            raise StageContractError(
                "context_refine action row score must be numeric",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{reason_prefix}.{index}.score",
                context={"index": index, "type": type(score).__name__},
            )
        focused = item.get("focused")
        if not isinstance(focused, bool):
            raise StageContractError(
                "context_refine action row focused must be a bool",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{reason_prefix}.{index}.focused",
                context={"index": index, "type": type(focused).__name__},
            )
        _require_action_name(
            item.get("action"), stage=stage, reason=f"{reason_prefix}.{index}.action"
        )
        reasons = item.get("reasons")
        if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons):
            raise StageContractError(
                "context_refine action row reasons must be a list of strings",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{reason_prefix}.{index}.reasons",
                context={"index": index, "type": type(reasons).__name__},
            )


def _validate_context_refine_decision_counts(
    decision_counts: dict[str, Any],
    *,
    stage: str,
    reason_prefix: str,
) -> None:
    expected: set[str] = set(_CONTEXT_REFINE_ACTIONS)
    actual = set(decision_counts)
    missing = sorted(expected - actual)
    if missing:
        raise StageContractError(
            "context_refine decision_counts missing required actions",
            stage=stage,
            error_code="stage_contract.missing_key",
            reason=reason_prefix,
            context={"missing_keys": missing},
        )
    unexpected = sorted(actual - expected)
    if unexpected:
        raise StageContractError(
            "context_refine decision_counts contains unknown actions",
            stage=stage,
            error_code="stage_contract.invalid_value",
            reason=reason_prefix,
            context={
                "unexpected_keys": unexpected,
                "allowed_actions": list(_CONTEXT_REFINE_ACTIONS),
            },
        )
    for action in _CONTEXT_REFINE_ACTIONS:
        _require_number(decision_counts, action, stage=stage)


def _validate_context_refine_candidate_review(
    candidate_review: dict[str, Any], *, stage: str
) -> None:
    schema_version = _require_str(candidate_review, "schema_version", stage=stage)
    if schema_version != "candidate_review_v2":
        raise StageContractError(
            "context_refine candidate_review must use schema_version candidate_review_v2",
            stage=stage,
            error_code="stage_contract.invalid_value",
            reason=f"{stage}.candidate_review.schema_version",
            context={"schema_version": schema_version},
        )
    status = _require_str(candidate_review, "status", stage=stage)
    if status not in _CONTEXT_REFINE_REVIEW_STATUSES:
        raise StageContractError(
            "context_refine candidate_review status is invalid",
            stage=stage,
            error_code="stage_contract.invalid_value",
            reason=f"{stage}.candidate_review.status",
            context={"status": status, "allowed_statuses": sorted(_CONTEXT_REFINE_REVIEW_STATUSES)},
        )
    _require_number(candidate_review, "focus_file_count", stage=stage)
    _require_number(candidate_review, "candidate_file_count", stage=stage)
    _require_number(candidate_review, "candidate_chunk_count", stage=stage)
    _require_number(candidate_review, "validation_test_count", stage=stage)
    _require_number(candidate_review, "direct_ratio", stage=stage)
    _require_number(candidate_review, "neighbor_context_ratio", stage=stage)
    _require_number(candidate_review, "hint_only_ratio", stage=stage)
    _require_bool(candidate_review, "failure_feedback_present", stage=stage)
    _require_optional_str_list(candidate_review, "watch_items", stage=stage)
    _require_optional_str_list(candidate_review, "recommendations", stage=stage)
    review_decision_counts = _require_dict(candidate_review, "decision_counts", stage=stage)
    _validate_context_refine_decision_counts(
        review_decision_counts,
        stage=stage,
        reason_prefix=f"{stage}.candidate_review.decision_counts",
    )
    review_file_actions = _require_list(candidate_review, "candidate_file_actions", stage=stage)
    _validate_context_refine_action_rows(
        review_file_actions,
        stage=stage,
        reason_prefix=f"{stage}.candidate_review.candidate_file_actions",
        require_qualified_name=False,
    )
    review_chunk_actions = _require_list(candidate_review, "candidate_chunk_actions", stage=stage)
    _validate_context_refine_action_rows(
        review_chunk_actions,
        stage=stage,
        reason_prefix=f"{stage}.candidate_review.candidate_chunk_actions",
        require_qualified_name=True,
    )


def _validate_history_hits_payload(history_hits: dict[str, Any], *, stage: str) -> None:
    schema_version = _require_str(history_hits, "schema_version", stage=stage)
    if schema_version != "history_hits_v1":
        raise StageContractError(
            "history_channel history_hits must use schema_version history_hits_v1",
            stage=stage,
            error_code="stage_contract.invalid_value",
            reason=f"{stage}.history_hits.schema_version",
            context={"schema_version": schema_version},
        )
    _require_bool(history_hits, "enabled", stage=stage)
    _require_str(history_hits, "reason", stage=stage)
    _require_number(history_hits, "commit_count", stage=stage)
    _require_number(history_hits, "path_count", stage=stage)
    _require_number(history_hits, "hit_count", stage=stage)
    hits = _require_list(history_hits, "hits", stage=stage)
    for index, item in enumerate(hits):
        if not isinstance(item, dict):
            raise StageContractError(
                "history_channel history_hits rows must be dictionaries",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{stage}.history_hits.hits.{index}",
                context={"index": index, "type": type(item).__name__},
            )
        for key in ("hash", "subject", "author", "committed_at"):
            value = item.get(key)
            if not isinstance(value, str):
                raise StageContractError(
                    f"history_channel history_hits row field must be a string: {key}",
                    stage=stage,
                    error_code="stage_contract.invalid_type",
                    reason=f"{stage}.history_hits.hits.{index}.{key}",
                    context={"index": index, "key": key, "type": type(value).__name__},
                )
        matched_paths = item.get("matched_paths")
        if not isinstance(matched_paths, list) or any(
            not isinstance(path, str) for path in matched_paths
        ):
            raise StageContractError(
                "history_channel history_hits row matched_paths must be a list of strings",
                stage=stage,
                error_code="stage_contract.invalid_type",
                reason=f"{stage}.history_hits.hits.{index}.matched_paths",
                context={"index": index, "type": type(matched_paths).__name__},
            )
        for key in ("matched_path_count", "file_count"):
            value = item.get(key)
            if not isinstance(value, (int, float)):
                raise StageContractError(
                    f"history_channel history_hits row field must be numeric: {key}",
                    stage=stage,
                    error_code="stage_contract.invalid_type",
                    reason=f"{stage}.history_hits.hits.{index}.{key}",
                    context={"index": index, "key": key, "type": type(value).__name__},
                )


def _reject_report_only_fields(
    output: dict[str, Any],
    *,
    stage: str,
    forbidden_fields: set[str] | frozenset[str],
) -> None:
    for field in sorted(forbidden_fields):
        if field not in output:
            continue
        raise StageContractError(
            f"report-only field must not appear in stage output: {field}",
            stage=stage,
            error_code="stage_contract.forbidden_field",
            reason=f"{stage}.{field}",
            context={"field": field},
        )


def _validate_memory(output: dict[str, Any]) -> None:
    stage = "memory"
    _require_str(output, "query", stage=stage)
    _require_number(output, "count", stage=stage)
    _require_list(output, "hits_preview", stage=stage)
    _require_str(output, "channel_used", stage=stage)
    _require_str(output, "strategy", stage=stage)
    _require_dict(output, "namespace", stage=stage)
    _require_dict(output, "timeline", stage=stage)
    _require_dict(output, "cache", stage=stage)
    _require_dict(output, "notes", stage=stage)
    _require_dict(output, "disclosure", stage=stage)
    _require_dict(output, "cost", stage=stage)
    _require_dict(output, "profile", stage=stage)
    _require_dict(output, "capture", stage=stage)


def _validate_index(output: dict[str, Any]) -> None:
    stage = "index"
    _require_str(output, "repo", stage=stage)
    _require_str(output, "root", stage=stage)
    _require_list(output, "terms", stage=stage)
    _require_list(output, "targets", stage=stage)
    _require_str(output, "module_hint", stage=stage)
    _require_str(output, "index_hash", stage=stage)
    _require_number(output, "file_count", stage=stage)
    _require_dict(output, "cache", stage=stage)
    _require_list(output, "candidate_files", stage=stage)
    _require_list(output, "candidate_chunks", stage=stage)
    _require_dict(output, "chunk_metrics", stage=stage)
    _require_dict(output, "docs", stage=stage)
    _require_dict(output, "worktree_prior", stage=stage)
    _require_dict(output, "cochange", stage=stage)
    _require_dict(output, "embeddings", stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)


def _validate_repomap(output: dict[str, Any]) -> None:
    stage = "repomap"
    _require_bool(output, "enabled", stage=stage)
    _require_list(output, "focused_files", stage=stage)
    _require_list(output, "seed_paths", stage=stage)
    _require_list(output, "neighbor_paths", stage=stage)
    _require_dict(output, "dependency_recall", stage=stage)
    _require_str(output, "markdown", stage=stage)
    _require_str(output, "ranking_profile", stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)
    _require_number(output, "neighbor_limit", stage=stage)
    _require_number(output, "neighbor_depth", stage=stage)
    _require_number(output, "budget_tokens", stage=stage)
    _require_bool(output, "repomap_enabled_effective", stage=stage)
    _require_dict(output, "cache", stage=stage)
    _require_dict(output, "precompute", stage=stage)


def _validate_augment(output: dict[str, Any]) -> None:
    stage = "augment"
    _require_bool(output, "enabled", stage=stage)
    _require_number(output, "count", stage=stage)
    _require_list(output, "diagnostics", stage=stage)
    _require_list(output, "errors", stage=stage)
    _require_dict(output, "vcs_history", stage=stage)
    _require_dict(output, "vcs_worktree", stage=stage)
    _require_bool(output, "xref_enabled", stage=stage)
    _require_dict(output, "xref", stage=stage)
    _require_dict(output, "tests", stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)


def _validate_skills(output: dict[str, Any]) -> None:
    stage = "skills"
    _require_dict(output, "query_ctx", stage=stage)
    _require_number(output, "available_count", stage=stage)
    _require_list(output, "selected", stage=stage)


def _validate_context_refine(output: dict[str, Any]) -> None:
    stage = "context_refine"
    _require_bool(output, "enabled", stage=stage)
    _require_str(output, "reason", stage=stage)
    _require_list(output, "focused_files", stage=stage)
    candidate_file_actions = _require_list(output, "candidate_file_actions", stage=stage)
    _validate_context_refine_action_rows(
        candidate_file_actions,
        stage=stage,
        reason_prefix=f"{stage}.candidate_file_actions",
        require_qualified_name=False,
    )
    candidate_chunk_actions = _require_list(output, "candidate_chunk_actions", stage=stage)
    _validate_context_refine_action_rows(
        candidate_chunk_actions,
        stage=stage,
        reason_prefix=f"{stage}.candidate_chunk_actions",
        require_qualified_name=True,
    )
    decision_counts = _require_dict(output, "decision_counts", stage=stage)
    _validate_context_refine_decision_counts(
        decision_counts,
        stage=stage,
        reason_prefix=f"{stage}.decision_counts",
    )
    candidate_review = _require_dict(output, "candidate_review", stage=stage)
    _validate_context_refine_candidate_review(candidate_review, stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)


def _validate_history_channel(output: dict[str, Any]) -> None:
    stage = "history_channel"
    _require_str(output, "schema_version", stage=stage)
    _require_bool(output, "enabled", stage=stage)
    _require_str(output, "reason", stage=stage)
    _require_list(output, "focused_files", stage=stage)
    _require_number(output, "commit_count", stage=stage)
    _require_number(output, "path_count", stage=stage)
    _require_number(output, "hit_count", stage=stage)
    history_hits = _require_dict(output, "history_hits", stage=stage)
    _validate_history_hits_payload(history_hits, stage=stage)
    _require_list(output, "recommendations", stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)


def _validate_source_plan(output: dict[str, Any]) -> None:
    stage = "source_plan"
    _reject_report_only_fields(
        output,
        stage=stage,
        forbidden_fields=_LAYER_REPORT_ONLY_FIELDS,
    )
    _require_str(output, "repo", stage=stage)
    _require_str(output, "root", stage=stage)
    _require_str(output, "query", stage=stage)
    _require_list(output, "stages", stage=stage)
    _require_list(output, "constraints", stage=stage)
    _require_list(output, "diagnostics", stage=stage)
    _require_dict(output, "xref", stage=stage)
    _require_dict(output, "tests", stage=stage)
    _require_list(output, "validation_tests", stage=stage)
    _require_list(output, "candidate_chunks", stage=stage)
    _require_list(output, "chunk_steps", stage=stage)
    _require_number(output, "chunk_budget_used", stage=stage)
    _require_number(output, "chunk_budget_limit", stage=stage)
    _require_str(output, "chunk_disclosure", stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)
    _require_list(output, "steps", stage=stage)
    _require_dict(output, "writeback_template", stage=stage)
    if "evidence_cards" in output and not isinstance(output.get("evidence_cards"), list):
        raise StageContractError(
            "stage output field must be a list: evidence_cards",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.evidence_cards",
            context={"key": "evidence_cards", "type": type(output.get("evidence_cards")).__name__},
        )
    if "file_cards" in output and not isinstance(output.get("file_cards"), list):
        raise StageContractError(
            "stage output field must be a list: file_cards",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.file_cards",
            context={"key": "file_cards", "type": type(output.get("file_cards")).__name__},
        )
    if "chunk_cards" in output and not isinstance(output.get("chunk_cards"), list):
        raise StageContractError(
            "stage output field must be a list: chunk_cards",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.chunk_cards",
            context={"key": "chunk_cards", "type": type(output.get("chunk_cards")).__name__},
        )
    if "card_summary" in output and not isinstance(output.get("card_summary"), dict):
        raise StageContractError(
            "stage output field must be a dictionary: card_summary",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.card_summary",
            context={"key": "card_summary", "type": type(output.get("card_summary")).__name__},
        )
    if "patch_artifact" in output and not isinstance(output.get("patch_artifact"), dict):
        raise StageContractError(
            "stage output field must be a dictionary: patch_artifact",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.patch_artifact",
            context={"key": "patch_artifact", "type": type(output.get("patch_artifact")).__name__},
        )
    if "patch_artifacts" in output and not isinstance(output.get("patch_artifacts"), list):
        raise StageContractError(
            "stage output field must be a list: patch_artifacts",
            stage=stage,
            error_code="stage_contract.invalid_type",
            reason=f"{stage}.patch_artifacts",
            context={
                "key": "patch_artifacts",
                "type": type(output.get("patch_artifacts")).__name__,
            },
        )


def _validate_validation(output: dict[str, Any]) -> None:
    stage = "validation"
    _reject_report_only_fields(
        output,
        stage=stage,
        forbidden_fields=_LAYER_REPORT_ONLY_FIELDS,
    )
    _require_bool(output, "enabled", stage=stage)
    _require_str(output, "reason", stage=stage)
    _require_dict(output, "sandbox", stage=stage)
    _require_list(output, "diagnostics", stage=stage)
    _require_number(output, "diagnostic_count", stage=stage)
    _require_bool(output, "xref_enabled", stage=stage)
    _require_dict(output, "xref", stage=stage)
    _require_dict(output, "result", stage=stage)
    _require_bool(output, "patch_artifact_present", stage=stage)
    _require_str(output, "policy_name", stage=stage)
    _require_str(output, "policy_version", stage=stage)


STAGE_OUTPUT_VALIDATORS = {
    "memory": _validate_memory,
    "index": _validate_index,
    "repomap": _validate_repomap,
    "augment": _validate_augment,
    "skills": _validate_skills,
    "history_channel": _validate_history_channel,
    "context_refine": _validate_context_refine,
    "source_plan": _validate_source_plan,
    "validation": _validate_validation,
}


__all__ = ["STAGE_OUTPUT_VALIDATORS", "validate_stage_output"]
