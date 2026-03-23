from __future__ import annotations

from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.registry import get_stage_descriptor


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


def _validate_source_plan(output: dict[str, Any]) -> None:
    stage = "source_plan"
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


def _validate_validation(output: dict[str, Any]) -> None:
    stage = "validation"
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
    "source_plan": _validate_source_plan,
    "validation": _validate_validation,
}


__all__ = ["STAGE_OUTPUT_VALIDATORS", "validate_stage_output"]
