"""Source plan stage for the orchestrator pipeline.

This module builds the final, structured plan payload using upstream stage
outputs: memory, index, repomap, augment, and skills.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ace_lite.explainability import attach_selection_why
from ace_lite.chunking.skeleton import summarize_chunk_contract
from ace_lite.pipeline.types import StageContext
from ace_lite.prompt_rendering.renderer import build_prompt_rendering_boundary
from ace_lite.scip.subgraph import build_subgraph_payload
from ace_lite.source_plan import (
    annotate_source_plan_grounding,
    build_chunk_steps,
    build_source_plan_steps,
    pack_source_plan_chunks,
    rank_source_plan_chunks,
    select_validation_tests,
    summarize_source_plan_grounding,
)


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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
    normalized = normalized.replace("<", "\uFF1C").replace(">", "\uFF1E")
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
    ltm_payload = (
        memory_stage.get("ltm", {}) if isinstance(memory_stage.get("ltm"), dict) else {}
    )
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
    ltm_selected_map: dict[str, dict[str, Any]],
    ltm_attribution_map: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for text in _extract_profile_constraints(profile):
        raw.append({"text": text, "source": "profile"})
    for hit in memory_hits:
        text = hit.get("text") or hit.get("preview")
        if not isinstance(text, str):
            continue
        handle = str(hit.get("handle") or "").strip()
        entry: dict[str, Any] = {
            "text": text,
            "source": "memory",
            "handle": handle,
        }
        if handle and handle in ltm_selected_map:
            entry["source"] = "ltm"
            entry["ltm_selected"] = ltm_selected_map.get(handle, {})
            entry["ltm_attribution"] = ltm_attribution_map.get(handle, {})
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
            selected_payload = (
                item.get("ltm_selected")
                if isinstance(item.get("ltm_selected"), dict)
                else {}
            )
            attribution_payload = (
                item.get("ltm_attribution")
                if isinstance(item.get("ltm_attribution"), dict)
                else {}
            )
            graph_neighborhood = (
                attribution_payload.get("graph_neighborhood")
                if isinstance(attribution_payload.get("graph_neighborhood"), dict)
                else {}
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
                    "graph_neighbor_count": int(
                        graph_neighborhood.get("triple_count", 0) or 0
                    ),
                }
            )
        if len(sanitized) >= 5:
            break

    summary = {
        "selected_count": len(ltm_selected_map),
        "constraint_count": len(selected_ltm_constraints),
        "graph_neighbor_count": sum(
            1
            for item in selected_ltm_constraints
            if int(item.get("graph_neighbor_count", 0) or 0) > 0
        ),
        "handles": [
            str(item.get("handle") or "").strip()
            for item in selected_ltm_constraints
            if str(item.get("handle") or "").strip()
        ],
    }
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
    repomap_stage = ctx.state.get("repomap", {}) if isinstance(ctx.state.get("repomap"), dict) else {}
    skills_stage = ctx.state.get("skills", {}) if isinstance(ctx.state.get("skills"), dict) else {}
    augment_stage = ctx.state.get("augment", {}) if isinstance(ctx.state.get("augment"), dict) else {}
    policy = ctx.state.get("__policy", {}) if isinstance(ctx.state.get("__policy"), dict) else {}

    memory_hits = _extract_memory_hits(memory_stage)
    profile_payload = memory_stage.get("profile", {}) if isinstance(memory_stage.get("profile"), dict) else {}
    ltm_selected_map, ltm_attribution_map = _extract_ltm_maps(memory_stage)
    constraints, ltm_constraints, ltm_constraint_summary = _build_constraints(
        memory_hits=memory_hits,
        profile=profile_payload,
        ltm_selected_map=ltm_selected_map,
        ltm_attribution_map=ltm_attribution_map,
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
    prioritized_chunks, packing = pack_source_plan_chunks(
        prioritized_chunks=ranked_chunks,
        focused_files=focused_files,
        chunk_top_k=max(1, int(chunk_top_k)),
        graph_closure_preference_enabled=bool(
            policy.get("source_plan_graph_closure_pack_enabled", True)
        ),
        return_metadata=True,
    )
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
            item
            for item in index_stage.get("candidate_files", [])
            if isinstance(item, dict)
        ],
        candidate_chunks=grounded_chunks[: max(1, int(chunk_top_k))],
        graph_lookup_payload=(
            index_stage.get("graph_lookup", {})
            if isinstance(index_stage.get("graph_lookup"), dict)
            else {}
        ),
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
    )
    prompt_rendering_boundary = build_prompt_rendering_boundary()
    chunk_contract = summarize_chunk_contract(
        candidate_chunks=grounded_chunks[: max(1, int(chunk_top_k))],
        requested_disclosure=str(chunk_disclosure or "refs"),
    )

    return {
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


__all__ = ["run_source_plan"]
