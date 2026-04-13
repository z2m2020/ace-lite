from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, cast

from ace_lite.validation.patch_artifact import validate_patch_artifact_contract_v1
from ace_lite.workspace.common import ensure_non_empty_str as _ensure_non_empty_str

_SYMBOL_TOKEN_PATTERN = re.compile(r"[^A-Za-z0-9]+")

_PATH_NOISE_TOKENS = {
    "src",
    "lib",
    "tests",
    "test",
    "app",
    "apps",
    "service",
    "services",
    "pkg",
    "package",
    "python",
}

_GENERIC_FILE_STEMS = {"__init__", "index", "main", "app", "mod", "module"}

def _extract_repo_name(*, payload: dict[str, Any], context: str) -> str:
    for key in ("name", "repo", "repo_name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"{context} must include a repo name")


def _normalize_candidate_files(*, selected_repo_payload: dict[str, Any]) -> tuple[str, ...]:
    quick_plan = selected_repo_payload.get("quick_plan", {})
    if not isinstance(quick_plan, dict):
        return ()

    raw_files = quick_plan.get("candidate_files", [])
    if not isinstance(raw_files, list):
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, str):
            continue
        path = item.strip().replace("\\", "/")
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return tuple(normalized)


def _normalize_path_list(*, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        path = item.strip().replace("\\", "/")
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return tuple(normalized)


def _extract_quick_plan(*, selected_repo_payload: dict[str, Any]) -> dict[str, Any] | None:
    quick_plan = selected_repo_payload.get("quick_plan")
    return quick_plan if isinstance(quick_plan, dict) else None


def _extract_patch_artifacts(*, selected_repo_payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    patch_artifacts = selected_repo_payload.get("patch_artifacts")
    if not isinstance(patch_artifacts, list):
        patch_artifact = selected_repo_payload.get("patch_artifact")
        if isinstance(patch_artifact, dict):
            patch_artifacts = [patch_artifact]
    if not isinstance(patch_artifacts, list):
        quick_plan = _extract_quick_plan(selected_repo_payload=selected_repo_payload)
        patch_artifacts = quick_plan.get("patch_artifacts") if isinstance(quick_plan, dict) else []
    if not isinstance(patch_artifacts, list):
        return ()

    normalized: list[dict[str, Any]] = []
    for item in patch_artifacts:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return tuple(normalized)


def _symbol_from_path(*, path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return ""

    without_ext = normalized.rsplit(".", 1)[0]
    parts = [part for part in without_ext.split("/") if part]
    if not parts:
        return ""

    stem = parts[-1].strip().lower()
    if stem in _GENERIC_FILE_STEMS and len(parts) >= 2:
        candidate_blob = "/".join(parts[-2:])
    else:
        candidate_blob = "/".join(parts[-3:])

    tokens = [
        token.lower()
        for token in _SYMBOL_TOKEN_PATTERN.split(candidate_blob)
        if token and token.lower() not in _PATH_NOISE_TOKENS
    ]
    if not tokens:
        tokens = [token.lower() for token in _SYMBOL_TOKEN_PATTERN.split(stem) if token]
    if not tokens:
        return ""
    return ".".join(tokens[-3:])


def _build_impacted_symbols(
    *,
    repo_name: str,
    quick_plan: dict[str, Any] | None,
    candidate_files: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    symbols: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    rows = quick_plan.get("rows", []) if isinstance(quick_plan, dict) else []
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, dict):
                continue
            module = str(item.get("module", "") or "").strip()
            path = str(item.get("path", "") or "").strip().replace("\\", "/")
            if not module:
                continue
            dedupe_key = (repo_name, module, path)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            symbols.append(
                {
                    "repo": repo_name,
                    "symbol": module,
                    "kind": "module",
                    "path": path,
                    "evidence": "quick_plan.rows.module",
                }
            )

    for path in candidate_files:
        symbol = _symbol_from_path(path=path)
        if not symbol:
            continue
        dedupe_key = (repo_name, symbol, path)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        symbols.append(
            {
                "repo": repo_name,
                "symbol": symbol,
                "kind": "path_heuristic",
                "path": path,
                "evidence": "quick_plan.candidate_files",
            }
        )

    return tuple(symbols)


def _build_dependency_entry(
    *,
    repo_name: str,
    position: int,
    depends_on_repo: str | None,
    quick_plan: dict[str, Any] | None,
    candidate_files: tuple[str, ...],
    missing_flags: list[str],
) -> tuple[dict[str, Any], bool]:
    repomap_stage = quick_plan.get("repomap_stage") if isinstance(quick_plan, dict) else None
    if not isinstance(repomap_stage, dict):
        missing_flags.append(f"missing_repomap_stage:{repo_name}")
        repomap_stage = None

    seed_paths = _normalize_path_list(
        value=repomap_stage.get("seed_paths") if repomap_stage is not None else None
    )
    neighbor_paths = _normalize_path_list(
        value=repomap_stage.get("neighbor_paths") if repomap_stage is not None else None
    )
    focused_files = _normalize_path_list(
        value=repomap_stage.get("focused_files") if repomap_stage is not None else None
    )

    if not seed_paths:
        missing_flags.append(f"missing_seed_paths:{repo_name}")
    if not neighbor_paths:
        missing_flags.append(f"missing_neighbor_paths:{repo_name}")
    if not focused_files and candidate_files:
        focused_files = candidate_files
    if not focused_files:
        missing_flags.append(f"missing_focused_files:{repo_name}")

    source = "repomap_stage" if repomap_stage is not None else "selected_repo_order"
    has_dependency_paths = bool(seed_paths or neighbor_paths or focused_files)

    return (
        {
            "repo": repo_name,
            "position": int(position),
            "depends_on_repo": depends_on_repo,
            "source": source,
            "seed_paths": list(seed_paths),
            "neighbor_paths": list(neighbor_paths),
            "focused_files": list(focused_files),
        },
        has_dependency_paths,
    )


def _build_rollback_entry(
    *,
    repo_name: str,
    candidate_files: tuple[str, ...],
    dependency_entry: dict[str, Any],
    missing_flags: list[str],
) -> tuple[dict[str, Any], bool]:
    focused_files = _normalize_path_list(value=dependency_entry.get("focused_files"))
    seed_paths = _normalize_path_list(value=dependency_entry.get("seed_paths"))
    rollback_paths = tuple(dict.fromkeys([*candidate_files, *focused_files, *seed_paths]))
    if not rollback_paths:
        missing_flags.append(f"missing_rollback_paths:{repo_name}")

    return (
        {
            "repo": repo_name,
            "strategy": "file_level_revert" if rollback_paths else "repo_level_revert",
            "paths": list(rollback_paths),
            "anchor_count": len(rollback_paths),
        },
        bool(rollback_paths),
    )


def _normalize_repo_names(*, entries: list[dict[str, Any]], context: str) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"{context}[{index}] must be a mapping")
        name = _extract_repo_name(payload=item, context=f"{context}[{index}]")
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return tuple(names)


def _extract_repo_names_from_contract(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        name: str | None = None
        if isinstance(item, str) and item.strip():
            name = item.strip()
        elif isinstance(item, dict):
            try:
                name = _extract_repo_name(payload=item, context=f"{context}[{index}]")
            except ValueError:
                name = None
        if name is None or not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return tuple(names)


@dataclass(frozen=True, slots=True)
class WorkspaceEvidenceContractV1:
    decision_target: str
    candidate_repos: tuple[str, ...]
    selected_repos: tuple[str, ...]
    impacted_files_by_repo: dict[str, tuple[str, ...]]
    impacted_symbols: tuple[dict[str, Any], ...]
    dependency_chain: tuple[dict[str, Any], ...]
    rollback_points: tuple[dict[str, Any], ...]
    patch_artifacts: tuple[dict[str, Any], ...]
    risks: tuple[str, ...]
    confidence: float
    missing_evidence_flags: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        impacted_repos = list(self.selected_repos or self.candidate_repos)
        impacted_files = [
            path
            for name in impacted_repos
            for path in self.impacted_files_by_repo.get(name, ())
        ]
        return {
            "decision_target": self.decision_target,
            "candidate_repos": list(self.candidate_repos),
            "selected_repos": list(self.selected_repos),
            "impacted_files_by_repo": {
                name: list(paths) for name, paths in self.impacted_files_by_repo.items()
            },
            "risks": list(self.risks),
            "confidence": float(self.confidence),
            "missing_evidence_flags": list(self.missing_evidence_flags),
            "impacted_repos": impacted_repos,
            "impacted_files": impacted_files,
            "impacted_symbols": [dict(item) for item in self.impacted_symbols],
            "dependency_chain": [dict(item) for item in self.dependency_chain],
            "rollback_points": [dict(item) for item in self.rollback_points],
            "patch_artifacts": [dict(item) for item in self.patch_artifacts],
        }


def build_workspace_evidence_contract_v1(
    *,
    decision_target: str,
    candidate_repos: list[dict[str, Any]],
    selected_repos: list[dict[str, Any]],
) -> WorkspaceEvidenceContractV1:
    target = _ensure_non_empty_str(value=decision_target, context="decision_target")
    candidate_names = _normalize_repo_names(entries=candidate_repos, context="candidate_repos")
    selected_names = _normalize_repo_names(entries=selected_repos, context="selected_repos")

    impacted_files_by_repo: dict[str, tuple[str, ...]] = {}
    impacted_symbols: list[dict[str, Any]] = []
    dependency_chain: list[dict[str, Any]] = []
    rollback_points: list[dict[str, Any]] = []
    patch_artifacts: list[dict[str, Any]] = []
    repos_with_candidate_files = 0
    repos_with_term_overlap = 0
    repos_with_symbols = 0
    repos_with_dependency_paths = 0
    repos_with_rollback_paths = 0
    missing_flags: list[str] = []
    risks: list[str] = []

    if not candidate_names:
        missing_flags.append("no_candidate_repos")
        risks.append("routing_empty")

    if not selected_names:
        missing_flags.append("no_selected_repos")
        risks.append("selection_empty")

    selected_payload_by_name: dict[str, dict[str, Any]] = {}
    for item in selected_repos:
        name = _extract_repo_name(payload=item, context="selected_repos[]")
        if name in selected_payload_by_name:
            continue
        selected_payload_by_name[name] = item

    for index, name in enumerate(selected_names):
        item = selected_payload_by_name.get(name, {})
        candidate_files = _normalize_candidate_files(selected_repo_payload=item)
        impacted_files_by_repo[name] = candidate_files
        if candidate_files:
            repos_with_candidate_files += 1
        else:
            missing_flags.append(f"missing_candidate_files:{name}")
            risks.append(f"insufficient_file_evidence:{name}")

        quick_plan = _extract_quick_plan(selected_repo_payload=item)
        if quick_plan is None:
            missing_flags.append(f"missing_quick_plan:{name}")
            risks.append(f"insufficient_plan_evidence:{name}")

        symbols = _build_impacted_symbols(
            repo_name=name,
            quick_plan=quick_plan,
            candidate_files=candidate_files,
        )
        if symbols:
            repos_with_symbols += 1
            impacted_symbols.extend(symbols)
        else:
            missing_flags.append(f"missing_impacted_symbols:{name}")
            risks.append(f"weak_symbol_evidence:{name}")

        dependency_entry, has_dependency_paths = _build_dependency_entry(
            repo_name=name,
            position=index + 1,
            depends_on_repo=selected_names[index - 1] if index > 0 else None,
            quick_plan=quick_plan,
            candidate_files=candidate_files,
            missing_flags=missing_flags,
        )
        dependency_chain.append(dependency_entry)
        if has_dependency_paths:
            repos_with_dependency_paths += 1
        else:
            risks.append(f"weak_dependency_chain:{name}")

        rollback_entry, has_rollback_paths = _build_rollback_entry(
            repo_name=name,
            candidate_files=candidate_files,
            dependency_entry=dependency_entry,
            missing_flags=missing_flags,
        )
        rollback_points.append(rollback_entry)
        if has_rollback_paths:
            repos_with_rollback_paths += 1
        else:
            risks.append(f"weak_rollback_evidence:{name}")

        patch_artifacts.extend(_extract_patch_artifacts(selected_repo_payload=item))

        matched_terms = item.get("matched_terms", [])
        term_overlap = (
            isinstance(matched_terms, list)
            and any(isinstance(term, str) and term.strip() for term in matched_terms)
        )
        if term_overlap:
            repos_with_term_overlap += 1
        else:
            missing_flags.append(f"missing_query_alignment:{name}")
            risks.append(f"weak_query_alignment:{name}")

    if candidate_names and selected_names and len(selected_names) < len(candidate_names):
        risks.append("partial_repo_selection")

    selected_count = len(selected_names)
    candidate_count = len(candidate_names)
    if selected_count <= 0 or candidate_count <= 0:
        confidence = 0.0
    else:
        selection_coverage = min(1.0, float(selected_count) / float(candidate_count))
        file_coverage = float(repos_with_candidate_files) / float(selected_count)
        alignment_coverage = float(repos_with_term_overlap) / float(selected_count)
        symbol_coverage = float(repos_with_symbols) / float(selected_count)
        dependency_coverage = float(repos_with_dependency_paths) / float(selected_count)
        rollback_coverage = float(repos_with_rollback_paths) / float(selected_count)
        confidence = (
            0.10
            + (0.20 * selection_coverage)
            + (0.25 * file_coverage)
            + (0.15 * alignment_coverage)
            + (0.10 * symbol_coverage)
            + (0.10 * dependency_coverage)
            + (0.10 * rollback_coverage)
        )
        confidence -= min(0.35, 0.02 * float(len(missing_flags)))
        confidence = max(0.0, min(1.0, confidence))

    if selected_names and not dependency_chain:
        missing_flags.append("missing_dependency_chain")
    if selected_names and not impacted_symbols:
        missing_flags.append("missing_impacted_symbols_global")
    if selected_names and not rollback_points:
        missing_flags.append("missing_rollback_points")

    unique_missing_flags = tuple(dict.fromkeys(missing_flags))
    unique_risks = tuple(dict.fromkeys(risks))

    return WorkspaceEvidenceContractV1(
        decision_target=target,
        candidate_repos=candidate_names,
        selected_repos=selected_names,
        impacted_files_by_repo=impacted_files_by_repo,
        impacted_symbols=tuple(impacted_symbols),
        dependency_chain=tuple(dependency_chain),
        rollback_points=tuple(rollback_points),
        patch_artifacts=tuple(patch_artifacts),
        risks=unique_risks,
        confidence=round(float(confidence), 3),
        missing_evidence_flags=unique_missing_flags,
    )


def validate_workspace_evidence_contract_v1(
    *,
    contract: WorkspaceEvidenceContractV1 | dict[str, Any],
    strict: bool = True,
    min_confidence: float = 0.85,
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any]
    if isinstance(contract, WorkspaceEvidenceContractV1):
        payload = contract.as_dict()
    elif isinstance(contract, dict):
        payload = contract
    else:
        raise ValueError("contract must be WorkspaceEvidenceContractV1 or a mapping payload")

    if isinstance(min_confidence, bool) or not isinstance(min_confidence, (int, float)):
        raise ValueError("min_confidence must be a number")
    min_confidence_normalized = float(min_confidence)
    if not math.isfinite(min_confidence_normalized):
        raise ValueError("min_confidence must be a finite number")
    if min_confidence_normalized < 0.0 or min_confidence_normalized > 1.0:
        raise ValueError("min_confidence must be within [0, 1]")

    violation_details: list[dict[str, Any]] = []

    def _add_violation(
        *,
        code: str,
        field: str,
        message: str,
        context: dict[str, Any] | None = None,
        severity: str = "error",
    ) -> None:
        detail: dict[str, Any] = {
            "code": code,
            "severity": severity,
            "field": field,
            "message": message,
            "context": dict(context) if isinstance(context, dict) else {},
        }
        violation_details.append(detail)

    decision_target_raw = payload.get("decision_target")
    if not isinstance(decision_target_raw, str) or not decision_target_raw.strip():
        _add_violation(
            code="decision_target_empty",
            field="decision_target",
            message="decision_target must be a non-empty string",
        )

    candidate_names = _extract_repo_names_from_contract(
        payload.get("candidate_repos"),
        context="candidate_repos",
    )
    if not candidate_names:
        _add_violation(
            code="candidate_repos_empty",
            field="candidate_repos",
            message="candidate_repos must contain at least one repo",
        )

    selected_names = _extract_repo_names_from_contract(
        payload.get("selected_repos"),
        context="selected_repos",
    )
    if not selected_names:
        _add_violation(
            code="selected_repos_empty",
            field="selected_repos",
            message="selected_repos must contain at least one repo",
        )

    impacted_files_by_repo_raw = payload.get("impacted_files_by_repo")
    if not isinstance(impacted_files_by_repo_raw, dict):
        _add_violation(
            code="impacted_files_by_repo_invalid",
            field="impacted_files_by_repo",
            message="impacted_files_by_repo must be a mapping",
        )
        impacted_files_by_repo_raw = {}

    if selected_names:
        for repo_name in selected_names:
            if repo_name not in impacted_files_by_repo_raw:
                _add_violation(
                    code="impacted_files_missing_repo",
                    field="impacted_files_by_repo",
                    message="missing impacted files entry for selected repo",
                    context={"repo": repo_name},
                )

    impacted_symbols = payload.get("impacted_symbols")
    dependency_chain = payload.get("dependency_chain")
    rollback_points = payload.get("rollback_points")
    patch_artifacts = payload.get("patch_artifacts")
    if strict:
        if not isinstance(impacted_symbols, list) or not impacted_symbols:
            _add_violation(
                code="impacted_symbols_empty",
                field="impacted_symbols",
                message="impacted_symbols must be a non-empty list in strict mode",
            )
        if not isinstance(dependency_chain, list) or not dependency_chain:
            _add_violation(
                code="dependency_chain_empty",
                field="dependency_chain",
                message="dependency_chain must be a non-empty list in strict mode",
            )
        if not isinstance(rollback_points, list) or not rollback_points:
            _add_violation(
                code="rollback_points_empty",
                field="rollback_points",
                message="rollback_points must be a non-empty list in strict mode",
            )

    if patch_artifacts is not None and not isinstance(patch_artifacts, list):
        _add_violation(
            code="patch_artifacts_invalid",
            field="patch_artifacts",
            message="patch_artifacts must be a list when present",
        )
        patch_artifacts = []
    if isinstance(patch_artifacts, list):
        for index, item in enumerate(patch_artifacts):
            if not isinstance(item, dict):
                _add_violation(
                    code="patch_artifact_entry_invalid",
                    field="patch_artifacts",
                    message="patch_artifacts entries must be mappings",
                    context={"index": index},
                )
                continue
            validation = validate_patch_artifact_contract_v1(
                contract=item,
                strict=False,
                fail_closed=False,
            )
            if not validation.get("ok", False):
                codes = validation.get("violations", [])
                _add_violation(
                    code="patch_artifact_invalid",
                    field="patch_artifacts",
                    message="patch_artifact payload failed validation",
                    context={
                        "index": index,
                        "violations": list(codes) if isinstance(codes, list) else [],
                    },
                )

    confidence_raw = payload.get("confidence")
    confidence: float = 0.0
    confidence_is_valid = (
        not isinstance(confidence_raw, bool)
        and isinstance(confidence_raw, (int, float))
    )
    if not confidence_is_valid:
        _add_violation(
            code="confidence_not_numeric",
            field="confidence",
            message="confidence must be numeric",
        )
    else:
        confidence = float(cast(int | float, confidence_raw))
        if not math.isfinite(confidence):
            _add_violation(
                code="confidence_not_finite",
                field="confidence",
                message="confidence must be a finite number",
            )
        else:
            if confidence < 0.0 or confidence > 1.0:
                _add_violation(
                    code="confidence_out_of_range",
                    field="confidence",
                    message="confidence must be within [0, 1]",
                )
            if confidence < min_confidence_normalized:
                _add_violation(
                    code="confidence_below_min_confidence",
                    field="confidence",
                    message="confidence is below minimum threshold",
                    context={"min_confidence": float(min_confidence_normalized)},
                )

    violations = list(dict.fromkeys(detail["code"] for detail in violation_details))

    ok = not violations
    return {
        "ok": bool(ok),
        "confidence": float(confidence),
        "min_confidence": float(min_confidence_normalized),
        "fail_closed": bool(fail_closed),
        "strict": bool(strict),
        "violations": list(violations),
        "violation_details": [dict(item) for item in violation_details],
    }


__all__ = [
    "WorkspaceEvidenceContractV1",
    "build_workspace_evidence_contract_v1",
    "validate_workspace_evidence_contract_v1",
]
