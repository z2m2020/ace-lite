"""Source plan stage for the orchestrator pipeline.

This module builds the final, structured plan payload using upstream stage
outputs: memory, index, repomap, augment, and skills.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ace_lite.chunking.skeleton import summarize_chunk_contract
from ace_lite.explainability import attach_selection_why
from ace_lite.pipeline.types import StageContext
from ace_lite.prompt_rendering.renderer import build_prompt_rendering_boundary
from ace_lite.scip.subgraph import build_subgraph_payload
from ace_lite.source_plan import (
    annotate_source_plan_grounding,
    build_chunk_steps,
    build_source_plan_cards,
    build_source_plan_steps,
    build_validation_feedback_summary,
    pack_source_plan_chunks,
    rank_source_plan_chunks,
    select_validation_tests,
    summarize_source_plan_grounding,
)
from ace_lite.source_plan.evidence_confidence import (
    annotate_chunk_confidence,
    build_confidence_summary,
)
from ace_lite.source_plan.report_only import (
    build_candidate_review,
    build_history_hits,
    build_session_end_report,
    build_validation_findings,
)
from ace_lite.validation.patch_artifact import validate_patch_artifact_contract_v1


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_memory_hits(memory_stage: dict[str, Any]) -> list[dict[str, Any]]:
    hits = _coerce_list(memory_stage.get("hits", []))
    if not hits:
        hits = _coerce_list(memory_stage.get("hits_preview", []))
    return [item for item in hits if isinstance(item, dict)]


def _extract_constraints(memory_hits: list[dict[str, Any]]) -> list[str]:
    constraints: list[str] = []
    for hit in memory_hits:
        text = hit.get("text") or hit.get("preview")
        if isinstance(text, str):
            constraints.append(text)
        if len(constraints) >= 5:
            break
    return constraints


def _sanitize_constraint(text: str, *, max_chars: int = 220) -> str:
    normalized = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    if not normalized:
        return ""
    # Strip basic tag-like patterns and escape angle brackets to reduce prompt-injection surface.
    normalized = normalized.replace("<", "\uff1c").replace(">", "\uff1e")
    normalized = " ".join(normalized.split())
    if len(normalized) > max(32, int(max_chars)):
        normalized = normalized[: max(32, int(max_chars))].rstrip() + "..."
    return normalized


def _extract_profile_constraints(profile_payload: dict[str, Any]) -> list[str]:
    facts = profile_payload.get("facts", [])
    if not isinstance(facts, list):
        return []
    constraints: list[str] = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            constraints.append(text.strip())
        if len(constraints) >= 5:
            break
    return constraints


def _extract_ltm_maps(
    memory_stage: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    ltm_payload = memory_stage.get("ltm", {}) if isinstance(memory_stage.get("ltm"), dict) else {}
    selected_map: dict[str, dict[str, Any]] = {}
    attribution_map: dict[str, dict[str, Any]] = {}

    for item in _coerce_list(ltm_payload.get("selected")):
        if not isinstance(item, dict):
            continue
        handle = str(item.get("handle") or "").strip()
        if handle:
            selected_map[handle] = item
    for item in _coerce_list(ltm_payload.get("attribution")):
        if not isinstance(item, dict):
            continue
        handle = str(item.get("handle") or "").strip()
        if handle:
            attribution_map[handle] = item
    return selected_map, attribution_map


def _build_constraints(
    *,
    memory_hits: list[dict[str, Any]],
    profile: dict[str, Any],
    ltm_selected_map: dict[str, dict[str, Any]] | None = None,
    ltm_attribution_map: dict[str, dict[str, Any]] | None = None,
    return_details: bool = False,
) -> list[str] | tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    resolved_ltm_selected_map = ltm_selected_map if isinstance(ltm_selected_map, dict) else {}
    resolved_ltm_attribution_map = (
        ltm_attribution_map if isinstance(ltm_attribution_map, dict) else {}
    )
    raw: list[dict[str, Any]] = []
    for text in _extract_profile_constraints(profile):
        raw.append({"text": text, "source": "profile"})
    for hit in memory_hits:
        text_raw = hit.get("text") or hit.get("preview")
        if not isinstance(text_raw, str):
            continue
        handle = str(hit.get("handle") or "").strip()
        entry: dict[str, Any] = {
            "text": text_raw,
            "source": "memory",
            "handle": handle,
        }
        if handle and handle in resolved_ltm_selected_map:
            entry["source"] = "ltm"
            entry["ltm_selected"] = resolved_ltm_selected_map.get(handle, {})
            entry["ltm_attribution"] = resolved_ltm_attribution_map.get(handle, {})
        raw.append(entry)

    sanitized: list[str] = []
    selected_ltm_constraints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        candidate = _sanitize_constraint(str(item.get("text") or ""))
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        sanitized.append(candidate)

        if item.get("source") == "ltm":
            selected_payload = _coerce_mapping(item.get("ltm_selected"))
            attribution_payload = _coerce_mapping(item.get("ltm_attribution"))
            graph_neighborhood = _coerce_mapping(
                attribution_payload.get("graph_neighborhood")
            )
            selected_ltm_constraints.append(
                {
                    "handle": str(item.get("handle") or "").strip(),
                    "constraint": candidate,
                    "memory_kind": str(selected_payload.get("memory_kind") or "").strip(),
                    "fact_type": str(selected_payload.get("fact_type") or "").strip(),
                    "as_of": str(selected_payload.get("as_of") or "").strip(),
                    "derived_from_observation_id": str(
                        selected_payload.get("derived_from_observation_id") or ""
                    ).strip(),
                    "graph_neighbor_count": _coerce_int(
                        graph_neighborhood.get("triple_count", 0)
                    ),
                }
            )
        if len(sanitized) >= 5:
            break

    summary = {
        "selected_count": len(resolved_ltm_selected_map),
        "constraint_count": len(selected_ltm_constraints),
        "graph_neighbor_count": sum(
            1
            for item in selected_ltm_constraints
            if _coerce_int(item.get("graph_neighbor_count", 0)) > 0
        ),
        "handles": [
            str(item.get("handle") or "").strip()
            for item in selected_ltm_constraints
            if str(item.get("handle") or "").strip()
        ],
    }
    if not return_details:
        return sanitized
    return sanitized, selected_ltm_constraints, summary


def _resolve_focused_files(
    *,
    repomap_stage: dict[str, Any],
    index_stage: dict[str, Any],
) -> list[str]:
    focused = repomap_stage.get("focused_files", [])
    if isinstance(focused, list) and focused:
        return [str(item) for item in focused if str(item).strip()]

    candidates = index_stage.get("candidate_files", [])
    if not isinstance(candidates, list):
        return []
    return [
        str(item.get("path"))
        for item in candidates
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]


def _extract_patch_artifacts(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw_candidates: list[dict[str, Any]] = []
    single = state.get("_validation_patch_artifact")
    if isinstance(single, dict):
        raw_candidates.append(single)
    multi = state.get("_validation_patch_artifacts")
    if isinstance(multi, list):
        raw_candidates.extend(item for item in multi if isinstance(item, dict))

    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], tuple[tuple[str, str], ...], str]] = set()
    for item in raw_candidates:
        validation = validate_patch_artifact_contract_v1(
            contract=item,
            strict=True,
            fail_closed=True,
        )
        if not validation.get("ok", False):
            continue
        manifest = tuple(
            str(path).strip().replace("\\", "/")
            for path in item.get("target_file_manifest", [])
            if isinstance(path, str) and str(path).strip()
        )
        operations = tuple(
            (
                str(entry.get("op") or "").strip(),
                str(entry.get("path") or "").strip().replace("\\", "/"),
            )
            for entry in item.get("operations", [])
            if isinstance(entry, dict)
        )
        identity = (
            str(item.get("schema_version") or "").strip(),
            manifest,
            operations,
            str(item.get("patch_text") or ""),
        )
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(dict(item))
    return selected


def run_source_plan(
    *,
    ctx: StageContext,
    pipeline_order: Iterable[str],
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_disclosure: str = "refs",
    policy_version: str,
) -> dict[str, Any]:
    """Run the source_plan stage.

    Args:
        ctx: Stage context with query and state.
        pipeline_order: Ordered stage list used for output metadata.
        chunk_top_k: Maximum number of prioritized chunks to emit.
        chunk_per_file_limit: Per-file chunk cap (used to size validation tests).
        chunk_token_budget: Token budget used for reporting (index stage enforces budget).
        policy_version: Policy version string for metadata.

    Returns:
        Source plan payload dict.
    """
    memory_stage = ctx.state.get("memory", {}) if isinstance(ctx.state.get("memory"), dict) else {}
    index_stage = ctx.state.get("index", {}) if isinstance(ctx.state.get("index"), dict) else {}
    repomap_stage = (
        ctx.state.get("repomap", {}) if isinstance(ctx.state.get("repomap"), dict) else {}
    )
    skills_stage = ctx.state.get("skills", {}) if isinstance(ctx.state.get("skills"), dict) else {}
    augment_stage = (
        ctx.state.get("augment", {}) if isinstance(ctx.state.get("augment"), dict) else {}
    )
    validation_stage = (
        ctx.state.get("validation", {}) if isinstance(ctx.state.get("validation"), dict) else {}
    )
    policy = ctx.state.get("__policy", {}) if isinstance(ctx.state.get("__policy"), dict) else {}
    vcs_history = (
        augment_stage.get("vcs_history", {})
        if isinstance(augment_stage.get("vcs_history"), dict)
        else {}
    )

    memory_hits = _extract_memory_hits(memory_stage)
    profile_payload = (
        memory_stage.get("profile", {}) if isinstance(memory_stage.get("profile"), dict) else {}
    )
    ltm_selected_map, ltm_attribution_map = _extract_ltm_maps(memory_stage)
    constraints, ltm_constraints, ltm_constraint_summary = _build_constraints(
        memory_hits=memory_hits,
        profile=profile_payload,
        ltm_selected_map=ltm_selected_map,
        ltm_attribution_map=ltm_attribution_map,
        return_details=True,
    )

    diagnostics = _coerce_list(augment_stage.get("diagnostics", []))
    xref = augment_stage.get("xref", {}) if isinstance(augment_stage.get("xref"), dict) else {}
    tests = augment_stage.get("tests", {}) if isinstance(augment_stage.get("tests"), dict) else {}

    focused_files = _resolve_focused_files(repomap_stage=repomap_stage, index_stage=index_stage)

    candidate_chunks = index_stage.get("candidate_chunks", [])
    if not isinstance(candidate_chunks, list):
        candidate_chunks = []

    chunk_metrics = index_stage.get("chunk_metrics", {})
    if not isinstance(chunk_metrics, dict):
        chunk_metrics = {}

    suspicious_chunks = tests.get("suspicious_chunks", []) if isinstance(tests, dict) else []
    if not isinstance(suspicious_chunks, list):
        suspicious_chunks = []

    test_signal_weight = max(0.0, float(policy.get("test_signal_weight", 1.0) or 1.0))
    ranked_chunks = rank_source_plan_chunks(
        suspicious_chunks=[item for item in suspicious_chunks if isinstance(item, dict)],
        candidate_chunks=[item for item in candidate_chunks if isinstance(item, dict)],
        test_signal_weight=test_signal_weight,
    )
    packed_chunks = pack_source_plan_chunks(
        prioritized_chunks=ranked_chunks,
        focused_files=focused_files,
        chunk_top_k=max(1, int(chunk_top_k)),
        graph_closure_preference_enabled=bool(
            policy.get("source_plan_graph_closure_pack_enabled", True)
        ),
        return_metadata=True,
    )
    if isinstance(packed_chunks, tuple):
        prioritized_chunks, packing = packed_chunks
    else:
        prioritized_chunks = packed_chunks
        packing = {}
    prioritized_chunks_with_why = attach_selection_why(
        prioritized_chunks,
        default_reason="ranked_chunk_candidate",
    )
    direct_candidate_files = [
        str(item.get("path") or "")
        for item in index_stage.get("candidate_files", [])
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]
    grounded_chunks = annotate_source_plan_grounding(
        prioritized_chunks=prioritized_chunks_with_why,
        direct_candidate_files=direct_candidate_files,
        direct_candidate_chunks=[item for item in candidate_chunks if isinstance(item, dict)],
        focused_files=focused_files,
    )
    evidence_summary = summarize_source_plan_grounding(grounded_chunks)
    # P1: annotate confidence taxonomy on grounded chunks (additive, report-only)
    grounded_chunks = annotate_chunk_confidence(grounded_chunks)
    confidence_summary = build_confidence_summary(grounded_chunks)

    validation_tests = select_validation_tests(
        tests=tests,
        limit=max(1, min(12, int(chunk_per_file_limit) * 2)),
    )

    chunk_steps = build_chunk_steps(
        prioritized_chunks=grounded_chunks,
        chunk_top_k=max(1, int(chunk_top_k)),
    )
    subgraph_payload = build_subgraph_payload(
        candidate_files=[
            item for item in index_stage.get("candidate_files", []) if isinstance(item, dict)
        ],
        candidate_chunks=grounded_chunks[: max(1, int(chunk_top_k))],
        graph_lookup_payload=(
            index_stage.get("graph_lookup", {})
            if isinstance(index_stage.get("graph_lookup"), dict)
            else {}
        ),
    )
    validation_result = (
        validation_stage.get("result") if isinstance(validation_stage.get("result"), dict) else {}
    )
    validation_feedback_summary = build_validation_feedback_summary(validation_result)
    failure_signal_summary = dict(validation_feedback_summary)
    if not failure_signal_summary:
        failure_signal_summary = {
            "status": "skipped",
            "issue_count": 0,
            "probe_status": "disabled",
            "probe_issue_count": 0,
            "probe_executed_count": 0,
            "selected_test_count": 0,
            "executed_test_count": 0,
        }
    failure_signal_summary["has_failure"] = bool(
        str(failure_signal_summary.get("status") or "").strip().lower()
        in {"failed", "degraded", "timeout"}
        or str(failure_signal_summary.get("probe_status") or "").strip().lower()
        in {"failed", "degraded", "timeout"}
        or int(failure_signal_summary.get("issue_count", 0) or 0) > 0
        or int(failure_signal_summary.get("probe_issue_count", 0) or 0) > 0
    )
    failure_signal_summary["source"] = "source_plan.validate_step"
    history_hits = build_history_hits(
        vcs_history=vcs_history,
        focused_files=focused_files,
    )
    candidate_review = build_candidate_review(
        focused_files=focused_files,
        candidate_chunks=grounded_chunks[: max(1, int(chunk_top_k))],
        evidence_summary=evidence_summary,
        failure_signal_summary=failure_signal_summary,
        validation_tests=validation_tests,
    )
    validation_findings = build_validation_findings(validation_result=validation_result)
    session_end_report = build_session_end_report(
        query=ctx.query,
        focused_files=focused_files,
        validation_tests=validation_tests,
        diagnostics=diagnostics,
        candidate_review=candidate_review,
        validation_findings=validation_findings,
        history_hits=history_hits,
    )

    steps = build_source_plan_steps(
        index_stage=index_stage,
        repomap_stage=repomap_stage,
        augment_stage=augment_stage,
        skills_stage=skills_stage,
        focused_files=focused_files,
        prioritized_chunks=grounded_chunks,
        candidate_chunk_count=len(candidate_chunks),
        suspicious_chunk_count=len([item for item in suspicious_chunks if isinstance(item, dict)]),
        diagnostics=diagnostics,
        xref=xref,
        tests=tests,
        validation_tests=validation_tests,
        subgraph_payload=subgraph_payload,
        validation_result=validation_result,
    )
    prompt_rendering_boundary = build_prompt_rendering_boundary()
    chunk_contract = summarize_chunk_contract(
        candidate_chunks=grounded_chunks[: max(1, int(chunk_top_k))],
        requested_disclosure=str(chunk_disclosure or "refs"),
    )
    evidence_cards, file_cards, chunk_cards, card_summary = build_source_plan_cards(
        prioritized_chunks=grounded_chunks[: max(1, int(chunk_top_k))],
        evidence_summary=evidence_summary,
        validation_result=validation_result,
    )
    payload = {
        "repo": ctx.repo,
        "root": ctx.root,
        "query": ctx.query,
        "stages": list(pipeline_order),
        "constraints": constraints,
        "ltm_constraints": ltm_constraints,
        "ltm_constraint_summary": ltm_constraint_summary,
        "diagnostics": diagnostics,
        "xref": xref,
        "tests": tests,
        "validation_tests": validation_tests,
        "candidate_chunks": grounded_chunks[: max(1, int(chunk_top_k))],
        "chunk_steps": chunk_steps,
        "chunk_budget_used": float(chunk_metrics.get("chunk_budget_used", 0.0) or 0.0),
        "chunk_budget_limit": int(chunk_token_budget),
        "chunk_disclosure": str(chunk_disclosure or "refs"),
        "chunk_contract": chunk_contract,
        "subgraph_payload": subgraph_payload,
        "prompt_rendering_boundary": prompt_rendering_boundary,
        "packing": packing,
        "evidence_summary": evidence_summary,
        "confidence_summary": confidence_summary,
        "evidence_cards": evidence_cards,
        "file_cards": file_cards,
        "chunk_cards": chunk_cards,
        "card_summary": card_summary,
        "history_hits": history_hits,
        "candidate_review": candidate_review,
        "validation_findings": validation_findings,
        "session_end_report": session_end_report,
        "failure_signal_summary": failure_signal_summary,
        "policy_name": str(policy.get("name", "general")),
        "policy_version": str(policy.get("version", policy_version)),
        "steps": steps,
        "writeback_template": {
            "title": "",
            "decision": "",
            "result": "",
            "caveat": "",
            "metadata": {
                "repo": ctx.repo,
                "branch": "",
                "path": "",
                "topic": "",
                "module": "",
                "updated_at": "",
                "app": "codex",
            },
        },
    }
    patch_artifacts = _extract_patch_artifacts(ctx.state)
    if patch_artifacts:
        payload["patch_artifact"] = dict(patch_artifacts[0])
        payload["patch_artifacts"] = [dict(item) for item in patch_artifacts]
    if isinstance(validation_result, dict) and validation_result:
        payload["validation_result"] = dict(validation_result)
    return payload


__all__ = ["run_source_plan"]
