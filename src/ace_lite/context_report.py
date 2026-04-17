"""Read-only context report builder for ACE-Lite source_plan payloads.

This module produces a human- and agent-readable audit report from an
already-computed plan payload. It does not modify the input payload and
does not call external services, LLM APIs, or write files (except via
the optional :func:`write_context_report_markdown`).

Schema version: ``context_report_v1``
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, cast

from ace_lite.context_report_sections import (
    append_candidate_review_section,
    append_confidence_breakdown_section,
    append_context_refine_section,
    append_core_nodes_section,
    append_handoff_payload_section,
    append_history_channel_section,
    append_history_hits_section,
    append_knowledge_gaps_section,
    append_memory_summary_section,
    append_session_end_report_section,
    append_suggested_questions_section,
    append_surprising_connections_section,
    append_validation_findings_section,
    append_warnings_section,
)
from ace_lite.plan_payload_view import (
    coerce_payload,
    resolve_candidate_chunks,
    resolve_candidate_files,
    resolve_candidate_review,
    resolve_confidence_summary,
    resolve_context_refine,
    resolve_evidence_summary,
    resolve_history_channel,
    resolve_pipeline_stage_names,
    resolve_repomap_payload,
    resolve_report_signals,
    resolve_source_plan_payload,
    resolve_validation_result,
    resolve_validation_tests,
)

__all__ = [
    "append_context_report_note",
    "build_context_report_note",
    "build_context_report_payload",
    "render_context_report_markdown",
    "validate_context_report_payload",
    "write_context_report_artifacts",
    "write_context_report_markdown",
]

SCHEMA_VERSION = "context_report_v1"
_CONTEXT_REPORT_NOTE_LOCK = Lock()

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any, default: bool = False) -> bool:
    return bool(value) if isinstance(value, (bool, type(None))) else default


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _resolve_context_report_json_path(markdown_path: Path) -> Path:
    return markdown_path.parent / "context_report.json"


def build_context_report_note(
    *,
    payload: Mapping[str, Any],
    repo: str | None = None,
    namespace: str | None = None,
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    summary = _dict(payload.get("summary"))
    query = _str(payload.get("query")).strip()
    root = _str(payload.get("root")).strip()
    return {
        "text": " | ".join(
            part
            for part in (
                f"context_report: {query}" if query else "context_report",
                f"candidate_files={_int(summary.get('candidate_file_count', 0))}",
                f"candidate_chunks={_int(summary.get('candidate_chunk_count', 0))}",
                f"warnings={len(_list(payload.get('warnings')))}",
            )
            if part
        ),
        "repo": _str(repo or payload.get("repo")).strip(),
        "namespace": _str(namespace).strip() or None,
        "query": query,
        "root": root,
        "source": SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "artifact_refs": [str(item).strip() for item in (artifact_refs or []) if str(item).strip()],
        "context_report": dict(payload),
    }


def append_context_report_note(
    *,
    payload: Mapping[str, Any],
    notes_path: str | Path,
    repo: str | None = None,
    namespace: str | None = None,
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    path = Path(notes_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    note = build_context_report_note(
        payload=payload,
        repo=repo,
        namespace=namespace,
        artifact_refs=artifact_refs,
    )
    with _CONTEXT_REPORT_NOTE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(note, ensure_ascii=False))
            fh.write("\n")
    return {
        "ok": True,
        "notes_path": str(path),
        "namespace": note.get("namespace"),
    }


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dedup_label(path: str) -> str:
    """Short label from a file path."""
    return path.split("/")[-1].split("\\")[-1] or path


# ----------------------------------------------------------------------
# Confidence breakdown (P0 heuristics -> P1 taxonomy later)
# ----------------------------------------------------------------------


def _infer_confidence_tier(chunk: dict[str, Any]) -> tuple[str, float]:
    """Infer confidence tier from chunk grounding metadata (P0 fallback).

    Returns (tier, score) where tier is EXTRACTED / INFERRED / AMBIGUOUS / UNKNOWN.
    """
    evidence = _dict(chunk.get("evidence"))
    role = str(evidence.get("role") or "").strip().lower()

    if role == "direct":
        # direct retrieval with candidate support
        sources = _list(evidence.get("sources", []))
        if "test_hint" in sources and "direct_candidate" not in sources:
            # hint-only boosted by test signal but not direct retrieval
            return "AMBIGUOUS", 0.35
        return "EXTRACTED", 1.0

    if role == "neighbor_context":
        return "INFERRED", 0.72

    if role == "hint_only":
        return "AMBIGUOUS", 0.28

    # No evidence field -> check score_breakdown for hints
    score_breakdown = _dict(chunk.get("score_breakdown", {}))
    if score_breakdown:
        has_candidate = _float(score_breakdown.get("candidate", 0.0)) > 0
        has_graph_closure = _float(score_breakdown.get("graph_closure_bonus", 0.0)) > 0
        has_test_signal = _float(score_breakdown.get("test_signal", 0.0)) > 0
        if has_candidate:
            return "EXTRACTED", 0.95
        if has_graph_closure or has_test_signal:
            return "INFERRED", 0.68
        return "AMBIGUOUS", 0.22

    return "UNKNOWN", 0.0


def _build_confidence_breakdown_p0(
    chunks: list[dict[str, Any]],
    evidence_summary: dict[str, Any],
) -> dict[str, Any]:
    """Build P0 confidence breakdown from grounding evidence (heuristic)."""
    if not chunks and not evidence_summary:
        return {
            "extracted_count": 0,
            "inferred_count": 0,
            "ambiguous_count": 0,
            "unknown_count": 0,
            "total_count": 0,
        }

    extracted_count = 0
    inferred_count = 0
    ambiguous_count = 0
    unknown_count = 0

    if chunks:
        for chunk in chunks:
            tier, _ = _infer_confidence_tier(chunk)
            if tier == "EXTRACTED":
                extracted_count += 1
            elif tier == "INFERRED":
                inferred_count += 1
            elif tier == "AMBIGUOUS":
                ambiguous_count += 1
            else:
                unknown_count += 1
    else:
        # Fall back to evidence_summary ratios
        total = max(
            1,
            _int(evidence_summary.get("direct_count", 0))
            + _int(evidence_summary.get("neighbor_context_count", 0))
            + _int(evidence_summary.get("hint_only_count", 0)),
        )
        extracted_count = _int(evidence_summary.get("direct_count", 0))
        inferred_count = _int(evidence_summary.get("neighbor_context_count", 0))
        ambiguous_count = _int(evidence_summary.get("hint_only_count", 0))
        unknown_count = max(0, total - extracted_count - inferred_count - ambiguous_count)
        total = extracted_count + inferred_count + ambiguous_count + unknown_count

    return {
        "extracted_count": extracted_count,
        "inferred_count": inferred_count,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "total_count": extracted_count + inferred_count + ambiguous_count + unknown_count,
    }


def _build_confidence_breakdown_p1(
    chunks: list[dict[str, Any]],
    confidence_summary: dict[str, Any],
) -> dict[str, Any]:
    """Build P1+ confidence breakdown from dedicated confidence_summary."""
    if confidence_summary:
        return {
            "extracted_count": _int(confidence_summary.get("extracted_count", 0)),
            "inferred_count": _int(confidence_summary.get("inferred_count", 0)),
            "ambiguous_count": _int(confidence_summary.get("ambiguous_count", 0)),
            "unknown_count": _int(confidence_summary.get("unknown_count", 0)),
            "total_count": _int(confidence_summary.get("total_count", 0)),
        }

    # Chunk-level aggregation
    extracted_count = sum(
        1
        for c in chunks
        if str(_dict(c.get("evidence_confidence", {})).get("confidence", "")).upper()
        in {"EXTRACTED"}
        or str(c.get("evidence_confidence", "")).upper() == "EXTRACTED"
    )
    inferred_count = sum(
        1
        for c in chunks
        if str(_dict(c.get("evidence_confidence", {})).get("confidence", "")).upper()
        in {"INFERRED"}
        or str(c.get("evidence_confidence", "")).upper() == "INFERRED"
    )
    ambiguous_count = sum(
        1
        for c in chunks
        if str(_dict(c.get("evidence_confidence", {})).get("confidence", "")).upper()
        in {"AMBIGUOUS"}
        or str(c.get("evidence_confidence", "")).upper() == "AMBIGUOUS"
    )
    unknown_count = sum(
        1
        for c in chunks
        if str(_dict(c.get("evidence_confidence", {})).get("confidence", "")).upper() in {"UNKNOWN"}
        or str(c.get("evidence_confidence", "")).upper() == "UNKNOWN"
    )
    total_count = len(chunks)

    return {
        "extracted_count": extracted_count,
        "inferred_count": inferred_count,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "total_count": total_count,
    }


# ----------------------------------------------------------------------
# Core nodes
# ----------------------------------------------------------------------


def _build_core_nodes(
    source_plan: dict[str, Any],
    plan_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build core_nodes from candidate_files and candidate_chunks."""
    nodes: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    candidate_files = resolve_candidate_files(plan_payload, source_plan=source_plan)
    for item in candidate_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        score = _float(item.get("score"))
        nodes.append(
            {
                "id": path,
                "label": _dedup_label(path),
                "path": path,
                "kind": "file",
                "source": "source_plan",
                "score": score,
                "reason": "top candidate file",
            }
        )

    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)
    for idx, chunk in enumerate(candidate_chunks):
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        qualified_name = str(chunk.get("qualified_name") or "").strip()
        score = _float(chunk.get("score"))
        chunk_id = f"{path}::{qualified_name}" if qualified_name else path

        evidence_confidence = str(chunk.get("evidence_confidence", "")).upper()
        confidence_reason = str(chunk.get("confidence_reason", "")).strip()

        if path and path not in seen_paths:
            seen_paths.add(path)
            nodes.append(
                {
                    "id": chunk_id,
                    "label": qualified_name or _dedup_label(path),
                    "path": path,
                    "kind": str(chunk.get("kind") or "chunk"),
                    "source": "source_plan",
                    "score": score,
                    "reason": f"top-{idx + 1} chunk" if idx < 5 else f"chunk-{idx + 1}",
                    "evidence_confidence": evidence_confidence or None,
                    "confidence_reason": confidence_reason or None,
                }
            )
        elif chunk_id not in {n["id"] for n in nodes}:
            nodes.append(
                {
                    "id": chunk_id,
                    "label": qualified_name or _dedup_label(path),
                    "path": path,
                    "kind": str(chunk.get("kind") or "chunk"),
                    "source": "source_plan",
                    "score": score,
                    "reason": f"top-{idx + 1} chunk" if idx < 5 else f"chunk-{idx + 1}",
                    "evidence_confidence": evidence_confidence or None,
                    "confidence_reason": confidence_reason or None,
                }
            )

    # Repomap focused_files add "source: repomap"
    repomap = resolve_repomap_payload(plan_payload, source_plan=source_plan)
    repomap_focused = {
        str(p).strip() for p in _list(repomap.get("focused_files", [])) if str(p).strip()
    }
    for node in nodes:
        if node["path"] in repomap_focused and node.get("source") == "source_plan":
            node["source"] = "repomap"

    return nodes


# ----------------------------------------------------------------------
# Surprising connections
# ----------------------------------------------------------------------


def _build_surprising_connections(
    source_plan: dict[str, Any],
    plan_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Infer surprising connections from graph-boosted chunks.

    Returns (connections, warnings).
    """
    connections: list[dict[str, Any]] = []
    warnings: list[str] = []

    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)
    if not candidate_chunks:
        warnings.append("surprising_connections_unavailable: no candidate_chunks")
        return connections, warnings

    score_breakdown: dict[str, Any] = {}
    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        breakdown = _dict(chunk.get("score_breakdown", {}))
        sb = _dict(breakdown) if isinstance(breakdown, dict) else {}
        score_breakdown[str(chunk.get("path") or "")] = sb

    # Chunks boosted by cochange, graph_closure, graph_lookup, SCIP, xref, coverage
    boosted_paths: dict[str, list[str]] = {}
    graph_boost_keys = {
        "cochange_boost",
        "graph_closure_bonus",
        "graph_lookup_boost",
        "scip_reference_boost",
        "xref_boost",
        "coverage_boost",
    }

    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        if not path:
            continue
        breakdown = _dict(chunk.get("score_breakdown", {}))
        boosts = [key for key in graph_boost_keys if _float(breakdown.get(key, 0.0)) > 0]
        if boosts:
            if path not in boosted_paths:
                boosted_paths[path] = []
            for boost in boosts:
                label = boost.replace("_boost", "").replace("_bonus", "")
                if label not in boosted_paths[path]:
                    boosted_paths[path].append(label)

    for path, sources in boosted_paths.items():
        chunk = next(
            (c for c in candidate_chunks if str(c.get("path") or "") == path),
            None,
        )
        if not chunk:
            continue
        connections.append(
            {
                "path": path,
                "label": _dedup_label(path),
                "boost_sources": sources,
                "score": _float(chunk.get("score")),
                "reason": f"boosted by {'/'.join(sources)}",
            }
        )

    # Cross-directory associations (production <-> test, code <-> docs)
    paths = [str(c.get("path") or "") for c in candidate_chunks if isinstance(c, dict)]
    test_code_pairs: list[tuple[str, str]] = []
    for p in paths:
        if "/test" in p.replace("\\", "/") or p.startswith("tests/"):
            continue
        for other in paths:
            if other == p:
                continue
            test_marker = "/test" in other.replace("\\", "/") or other.startswith("tests/")
            code_marker = "/test" not in other.replace("\\", "/") and not other.startswith("tests/")
            if (
                (test_marker or code_marker)
                and ("src/" in p.replace("\\", "/") or "src\\" in p.replace("/", "\\"))
                and ("test" in other.replace("\\", "/"))
            ):
                # Simple proxy: production src vs test
                test_code_pairs.append((p, other))

    seen_pairs: set[tuple[str, str]] = set()
    for src, test in test_code_pairs:
        pair_key = cast(tuple[str, str], tuple(sorted([src, test])))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        connections.append(
            {
                "path": src,
                "related_path": test,
                "label": _dedup_label(src),
                "related_label": _dedup_label(test),
                "boost_sources": ["cross_directory"],
                "score": 0.0,
                "reason": "production-test cross-reference",
            }
        )

    if not connections:
        warnings.append("surprising_connections_unavailable: no stable graph-boost signal")

    return connections, warnings


# ----------------------------------------------------------------------
# Knowledge gaps
# ----------------------------------------------------------------------


def _collect_degraded_reasons(plan_payload: dict[str, Any]) -> list[str]:
    """Collect degraded reasons from observability and validation payloads."""
    degraded_reasons: list[str] = []

    observability = _dict(plan_payload.get("observability", {}))
    stage_metrics_value = observability.get("stage_metrics", [])
    if isinstance(stage_metrics_value, dict):
        stage_metrics_list = [stage_metrics_value]
    else:
        stage_metrics_list = _list(stage_metrics_value)
    for sm in stage_metrics_list:
        if isinstance(sm, dict):
            tags = _dict(sm.get("tags", {}))
            for reason in _list(tags.get("degraded_reasons", [])):
                degraded_reasons.append(str(reason))
            for reason in _list(sm.get("degraded_reasons", [])):
                degraded_reasons.append(str(reason))

    validation = _dict(plan_payload.get("validation", {}))
    probes = _list(validation.get("probes", []))
    for probe in probes:
        if isinstance(probe, dict):
            for reason in _list(probe.get("degraded_reasons", [])):
                degraded_reasons.append(str(reason))

    return degraded_reasons


def _build_memory_summary(plan_payload: dict[str, Any]) -> dict[str, Any]:
    memory_payload = _dict(plan_payload.get("memory", {}))
    ltm = _dict(memory_payload.get("ltm", {}))
    selected = _list(ltm.get("selected", []))
    if not memory_payload and not selected:
        return {}

    abstraction_counts = {level: 0 for level in ("abstract", "overview", "detail")}
    feedback_signal_counts = {
        key: _int(value, 0)
        for key, value in _dict(ltm.get("feedback_signal_counts", {})).items()
    }
    observation_hit_count = 0
    fact_hit_count = 0
    stale_warning_count = 0

    for item in selected:
        if not isinstance(item, dict):
            continue
        memory_kind = str(item.get("memory_kind") or "").strip().lower()
        if memory_kind == "observation":
            observation_hit_count += 1
        elif memory_kind == "fact":
            fact_hit_count += 1
        abstraction_level = str(item.get("abstraction_level") or "").strip().lower()
        if abstraction_level in abstraction_counts:
            abstraction_counts[abstraction_level] += 1
        if str(item.get("freshness_state") or "").strip().lower() == "stale":
            stale_warning_count += 1

    hit_count = len([item for item in selected if isinstance(item, dict)])
    return {
        "count": _int(memory_payload.get("count", 0)),
        "ltm_selected_count": _int(ltm.get("selected_count", hit_count)),
        "hit_count": hit_count,
        "abstract_hit_count": abstraction_counts["abstract"] + abstraction_counts["overview"],
        "observation_hit_count": observation_hit_count,
        "fact_hit_count": fact_hit_count,
        "stale_warning_count": stale_warning_count,
        "feedback_signal_counts": feedback_signal_counts,
        "abstraction_counts": abstraction_counts,
    }


def _build_knowledge_gaps(
    plan_payload: dict[str, Any],
    source_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Identify knowledge gaps from plan payload signals."""
    gaps: list[dict[str, Any]] = []

    validation_tests = resolve_validation_tests(plan_payload, source_plan=source_plan)
    if not validation_tests:
        gaps.append(
            {
                "code": "missing_validation_tests",
                "severity": "medium",
                "message": "source_plan.validation_tests is empty",
            }
        )

    evidence_summary = resolve_evidence_summary(plan_payload, source_plan=source_plan)
    hint_ratio = _float(evidence_summary.get("hint_only_ratio", 0.0))
    if hint_ratio > 0.5:
        gaps.append(
            {
                "code": "hint_heavy_evidence",
                "severity": "high",
                "message": f"source_plan.evidence_summary.hint_only_ratio={hint_ratio:.2f} > 0.5",
            }
        )

    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)
    if not candidate_chunks:
        gaps.append(
            {
                "code": "missing_candidate_chunks",
                "severity": "high",
                "message": "source_plan.candidate_chunks is empty",
            }
        )

    # Check observability stage_metrics and validation probes for degraded reasons.
    degraded_reasons = _collect_degraded_reasons(plan_payload)
    degraded_keys = {
        "memory_fallback",
        "candidate_ranker_fallback",
        "embedding_fallback",
        "trace_export_failed",
    }
    for reason in degraded_reasons:
        reason_str = str(reason).lower()
        for key in degraded_keys:
            if key in reason_str:
                gaps.append(
                    {
                        "code": key,
                        "severity": "medium",
                        "message": f"observability stage_metrics degraded: {reason}",
                    }
                )

    # Plan timeout fallback
    if plan_payload.get("_plan_timeout_fallback"):
        gaps.append(
            {
                "code": "plan_timeout_fallback",
                "severity": "medium",
                "message": "plan execution timed out and fell back to plan_quick",
            }
        )

    memory_summary = _build_memory_summary(plan_payload)
    if _int(memory_summary.get("stale_warning_count", 0)) > 0:
        gaps.append(
            {
                "code": "stale_memory_signal",
                "severity": "medium",
                "message": "memory.ltm contains stale long-term memory hits that should be re-validated",
            }
        )
    if (
        _int(memory_summary.get("hit_count", 0)) > 0
        and _int(memory_summary.get("abstract_hit_count", 0)) == 0
    ):
        gaps.append(
            {
                "code": "missing_abstract_memory",
                "severity": "low",
                "message": "memory.ltm hits exist, but none are exposed at abstract/overview level",
            }
        )

    return gaps


# ----------------------------------------------------------------------
# Suggested questions
# ----------------------------------------------------------------------


def _build_suggested_questions(
    plan_payload: dict[str, Any],
    source_plan: dict[str, Any],
    knowledge_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate suggested questions from plan payload and gaps."""
    questions: list[dict[str, Any]] = []

    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)
    candidate_files = resolve_candidate_files(plan_payload, source_plan=source_plan)

    # Entrypoint question from top candidate file
    if candidate_chunks:
        top_chunk = next(
            (c for c in candidate_chunks if isinstance(c, dict)),
            None,
        )
        if top_chunk:
            path = str(top_chunk.get("path") or "").strip()
            questions.append(
                {
                    "type": "entrypoint",
                    "question": "Which top candidate file should be inspected first?",
                    "why": "Top source_plan candidate controls the likely edit boundary.",
                    "path": path,
                }
            )
    elif candidate_files:
        top_file = next(
            (f for f in candidate_files if isinstance(f, dict)),
            None,
        )
        if top_file:
            path = str(top_file.get("path") or "").strip()
            questions.append(
                {
                    "type": "entrypoint",
                    "question": "Which top candidate file should be inspected first?",
                    "why": "No chunks but candidate files are available.",
                    "path": path,
                }
            )

    # Validation questions from gaps
    gap_codes = {g.get("code") for g in knowledge_gaps}
    if "missing_validation_tests" in gap_codes:
        questions.append(
            {
                "type": "validation",
                "question": "How to add validation tests for the top candidate?",
                "why": "validation_tests is empty; without tests the plan cannot self-verify.",
            }
        )
    if "hint_heavy_evidence" in gap_codes:
        questions.append(
            {
                "type": "validation",
                "question": "Are there direct symbol or import hits for this query?",
                "why": "hint_only_ratio > 0.5 means most evidence is indirect.",
            }
        )
    if "missing_candidate_chunks" in gap_codes:
        questions.append(
            {
                "type": "validation",
                "question": "Should the retrieval index be rebuilt or the query refined?",
                "why": "candidate_chunks is empty; retrieval may have failed.",
            }
        )
    if "plan_timeout_fallback" in gap_codes:
        questions.append(
            {
                "type": "validation",
                "question": "Did the full plan produce better candidates than plan_quick?",
                "why": "Plan timed out and fell back to quick mode.",
            }
        )
    if "stale_memory_signal" in gap_codes:
        questions.append(
            {
                "type": "memory",
                "question": "Which stale long-term memory hits need reconfirmation before trusting them?",
                "why": "Stale memory hits can distort the handoff summary without being current facts.",
            }
        )
    if "missing_abstract_memory" in gap_codes:
        questions.append(
            {
                "type": "memory",
                "question": "Should any long-term memory hits be promoted to abstract or overview level?",
                "why": "Only detail-level memory is available, so summary-first inspection is weakened.",
            }
        )

    # Ambiguous evidence questions
    evidence_summary = resolve_evidence_summary(plan_payload, source_plan=source_plan)
    neighbor_count = _int(evidence_summary.get("neighbor_context_count", 0))
    if neighbor_count > 0:
        questions.append(
            {
                "type": "clarification",
                "question": "Do the neighbor-context files belong in the edit boundary?",
                "why": f"{neighbor_count} chunk(s) were included via focused-file neighbor context.",
            }
        )

    if not questions:
        questions.append(
            {
                "type": "no_signal",
                "question": "Not enough context to generate targeted questions.",
                "why": "Plan payload lacks sufficient signals for question generation.",
            }
        )

    return questions


# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------


def _build_summary(
    plan_payload: dict[str, Any],
    source_plan: dict[str, Any],
) -> dict[str, Any]:
    """Build summary section from plan payload."""
    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)
    candidate_files_in_index = resolve_candidate_files(plan_payload, source_plan=source_plan)
    validation_tests = resolve_validation_tests(plan_payload, source_plan=source_plan)
    stages = resolve_pipeline_stage_names(plan_payload, source_plan=source_plan)
    history_channel = resolve_history_channel(plan_payload)
    context_refine = resolve_context_refine(plan_payload)
    report_signals = resolve_report_signals(plan_payload, source_plan=source_plan)
    history_hits = _dict(report_signals.get("history_hits", {}))
    validation_findings = _dict(report_signals.get("validation_findings", {}))
    session_end_report = _dict(report_signals.get("session_end_report", {}))
    handoff_payload = _dict(report_signals.get("handoff_payload", {}))
    memory_summary = _build_memory_summary(plan_payload)

    # Count degraded reasons from observability
    degraded_reasons = _collect_degraded_reasons(plan_payload)
    degraded_reason_count = len(degraded_reasons)

    # Also check top-level indicators
    if plan_payload.get("_plan_timeout_fallback"):
        degraded_reason_count += 1

    # unique candidate file count
    unique_files: set[str] = set()
    for chunk in candidate_chunks:
        if isinstance(chunk, dict):
            p = str(chunk.get("path") or "").strip()
            if p:
                unique_files.add(p)
    for f in candidate_files_in_index:
        if isinstance(f, dict):
            p = str(f.get("path") or "").strip()
            if p:
                unique_files.add(p)

    has_validation_payload = bool(resolve_validation_result(plan_payload, source_plan=source_plan))

    return {
        "candidate_file_count": len(unique_files),
        "candidate_chunk_count": len(candidate_chunks),
        "validation_test_count": len(validation_tests),
        "stage_count": len(stages),
        "degraded_reason_count": degraded_reason_count,
        "has_validation_payload": has_validation_payload,
        "history_channel_hit_count": len(
            _list(_dict(history_channel.get("history_hits", {})).get("hits", []))
        ),
        "history_hit_count": len(_list(history_hits.get("hits", []))),
        "context_refine_decision_count": sum(
            _int(_dict(context_refine.get("decision_counts", {})).get(key, 0))
            for key in ("keep", "downrank", "drop", "need_more_read")
        ),
        "validation_finding_count": len(_list(validation_findings.get("findings", []))),
        "next_action_count": len(_list(session_end_report.get("next_actions", []))),
        "handoff_next_task_count": len(_list(handoff_payload.get("next_tasks", []))),
        "memory_hit_count": _int(memory_summary.get("hit_count", 0)),
        "memory_abstract_hit_count": _int(memory_summary.get("abstract_hit_count", 0)),
        "memory_observation_hit_count": _int(memory_summary.get("observation_hit_count", 0)),
        "memory_fact_hit_count": _int(memory_summary.get("fact_hit_count", 0)),
        "memory_stale_warning_count": _int(memory_summary.get("stale_warning_count", 0)),
    }


# ----------------------------------------------------------------------
# Main builder
# ----------------------------------------------------------------------


def build_context_report_payload(plan_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a context_report_v1 payload from a plan payload.

    Args:
        plan_payload: A source_plan output dict (or any mapping with similar fields).

    Returns:
        A dict conforming to the ``context_report_v1`` schema.
        Always returns a valid report even for empty/None inputs (``ok=false``).
    """
    payload = coerce_payload(plan_payload)
    sp: dict[str, Any] = resolve_source_plan_payload(payload)

    warnings: list[str] = []
    inputs: dict[str, bool] = {
        "has_source_plan": bool(payload),
        "has_observability": bool(_dict(payload.get("observability", {}))),
        "has_validation": bool(resolve_validation_result(payload, source_plan=sp)),
    }

    # Graceful empty handling
    has_chunks = bool(resolve_candidate_chunks(payload, source_plan=sp))
    has_files = bool(resolve_candidate_files(payload, source_plan=sp))
    has_query = bool(payload.get("query") or sp.get("query"))

    if not payload or (not has_chunks and not has_files and not has_query):
        return {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "query": _str(payload.get("query", "")),
            "repo": _str(payload.get("repo", "")),
            "root": _str(payload.get("root", "")),
            "summary": {
                "candidate_file_count": 0,
                "candidate_chunk_count": 0,
                "validation_test_count": 0,
                "stage_count": len(resolve_pipeline_stage_names(payload, source_plan=sp)),
                "degraded_reason_count": 0,
                "has_validation_payload": False,
                "history_channel_hit_count": 0,
                "history_hit_count": 0,
                "context_refine_decision_count": 0,
                "validation_finding_count": 0,
                "next_action_count": 0,
                "handoff_next_task_count": 0,
                "memory_hit_count": 0,
                "memory_abstract_hit_count": 0,
                "memory_observation_hit_count": 0,
                "memory_fact_hit_count": 0,
                "memory_stale_warning_count": 0,
            },
            "core_nodes": [],
            "surprising_connections": [],
            "confidence_breakdown": {
                "extracted_count": 0,
                "inferred_count": 0,
                "ambiguous_count": 0,
                "unknown_count": 0,
                "total_count": 0,
            },
            "knowledge_gaps": [],
            "suggested_questions": [
                {
                    "type": "no_signal",
                    "question": "Not enough context to generate targeted questions.",
                    "why": "Plan payload is empty or minimal.",
                }
            ],
            "history_channel": {},
            "history_hits": {},
            "context_refine": {},
            "candidate_review": {},
            "validation_findings": {},
            "session_end_report": {},
            "handoff_payload": {},
            "memory_summary": {},
            "inputs": inputs,
            "warnings": ["empty_payload"],
        }

    # P1: try confidence_summary first, fall back to P0 heuristics
    sp_chunks = resolve_candidate_chunks(payload, source_plan=sp)
    confidence_summary = resolve_confidence_summary(payload, source_plan=sp)
    evidence_summary = resolve_evidence_summary(payload, source_plan=sp)
    history_channel = resolve_history_channel(payload)
    context_refine = resolve_context_refine(payload)
    report_signals = resolve_report_signals(payload, source_plan=sp)
    history_hits = _dict(report_signals.get("history_hits", {}))
    candidate_review = resolve_candidate_review(payload, source_plan=sp)
    validation_findings = _dict(report_signals.get("validation_findings", {}))
    session_end_report = _dict(report_signals.get("session_end_report", {}))
    handoff_payload = _dict(report_signals.get("handoff_payload", {}))
    memory_summary = _build_memory_summary(payload)

    if confidence_summary:
        confidence_breakdown = _build_confidence_breakdown_p1(sp_chunks, confidence_summary)
    else:
        confidence_breakdown = _build_confidence_breakdown_p0(sp_chunks, evidence_summary)

    core_nodes = _build_core_nodes(sp, payload)
    surprising_connections, sc_warnings = _build_surprising_connections(sp, payload)
    warnings.extend(sc_warnings)
    knowledge_gaps = _build_knowledge_gaps(payload, sp)
    suggested_questions = _build_suggested_questions(payload, sp, knowledge_gaps)
    summary = _build_summary(payload, sp)

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "query": _str(payload.get("query", "")),
        "repo": _str(payload.get("repo", "")),
        "root": _str(payload.get("root", "")),
        "summary": summary,
        "core_nodes": core_nodes,
        "surprising_connections": surprising_connections,
        "confidence_breakdown": confidence_breakdown,
        "history_channel": history_channel,
        "history_hits": history_hits,
        "context_refine": context_refine,
        "candidate_review": candidate_review,
        "validation_findings": validation_findings,
        "session_end_report": session_end_report,
        "handoff_payload": handoff_payload,
        "memory_summary": memory_summary,
        "knowledge_gaps": knowledge_gaps,
        "suggested_questions": suggested_questions,
        "inputs": inputs,
        "warnings": warnings,
    }


# ----------------------------------------------------------------------
# Schema guard
# ----------------------------------------------------------------------


def validate_context_report_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a context_report_v1 payload against required keys and types.

    Args:
        payload: A dict conforming (or claimed to conform) to context_report_v1.

    Returns:
        The validated payload as a dict.

    Raises:
        ValueError: if a required key is missing or has an invalid type.
    """
    if not isinstance(payload, dict):
        raise ValueError("context_report payload must be a dictionary")

    _required_str_fields = ("schema_version", "query", "repo", "root")
    for field in _required_str_fields:
        value = payload.get(field)
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string; got {type(value).__name__}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be '{SCHEMA_VERSION}'; got {payload.get('schema_version')!r}"
        )

    if not isinstance(payload.get("summary"), dict):
        raise ValueError("summary must be a dict")
    if not isinstance(payload.get("core_nodes"), list):
        raise ValueError("core_nodes must be a list")
    if not isinstance(payload.get("warnings"), list):
        raise ValueError("warnings must be a list")

    return dict(payload)


# ----------------------------------------------------------------------
# Markdown renderer
# ----------------------------------------------------------------------


def render_context_report_markdown(payload: Mapping[str, Any]) -> str:
    """Render a context_report_v1 payload as a human-readable Markdown string.

    Args:
        payload: A ``context_report_v1`` dict as returned by
                 :func:`build_context_report_payload`.

    Returns:
        A Markdown-formatted report string.
    """
    p = _dict(payload) if hasattr(payload, "__getitem__") else {}

    lines: list[str] = []

    # Header
    lines.append("# Context Report")
    schema_ver = _str(p.get("schema_version", "unknown"))
    ok_status = "ok" if _bool(p.get("ok")) else "degraded"
    lines.append(f"*schema: {schema_ver} | status: {ok_status}*")
    lines.append("")

    # Inputs
    inputs = _dict(p.get("inputs", {}))
    if inputs:
        input_parts = [
            f"{k}={'yes' if v else 'no'}"
            for k, v in inputs.items()
            if k in ("has_source_plan", "has_observability", "has_validation")
        ]
        if input_parts:
            lines.append(f"**Inputs**: {', '.join(input_parts)}")
            lines.append("")

    # Summary
    summary = _dict(p.get("summary", {}))
    if summary:
        lines.append("## Summary")
        for key in (
            "candidate_file_count",
            "candidate_chunk_count",
            "validation_test_count",
            "stage_count",
            "degraded_reason_count",
            "memory_hit_count",
            "memory_abstract_hit_count",
            "memory_observation_hit_count",
            "memory_fact_hit_count",
            "memory_stale_warning_count",
            "history_channel_hit_count",
            "history_hit_count",
            "context_refine_decision_count",
            "validation_finding_count",
            "next_action_count",
        ):
            val = summary.get(key)
            if val is not None:
                label = key.replace("_", " ").capitalize()
                lines.append(f"- **{label}**: {val}")
        has_val = summary.get("has_validation_payload")
        lines.append(f"- **Has validation payload**: {'yes' if has_val else 'no'}")
        lines.append("")

    append_history_channel_section(lines, p)
    append_history_hits_section(lines, p)
    append_context_refine_section(lines, p)
    append_core_nodes_section(lines, p)
    append_candidate_review_section(lines, p)
    append_surprising_connections_section(lines, p)
    append_confidence_breakdown_section(lines, p)
    append_memory_summary_section(lines, p)
    append_validation_findings_section(lines, p)
    append_knowledge_gaps_section(lines, p)
    append_suggested_questions_section(lines, p)
    append_warnings_section(lines, p)
    append_session_end_report_section(lines, p)
    append_handoff_payload_section(lines, p)

    # Footer
    query = _str(p.get("query", ""))
    if query:
        lines.append(f"*Query: {query}*")
    repo = _str(p.get("repo", ""))
    root = _str(p.get("root", ""))
    if repo:
        lines.append(f"*Repo: {repo} | Root: {root}*")
    lines.append(f"*Schema: {schema_ver}*")

    return "\n".join(lines)


# ----------------------------------------------------------------------
# File writer
# ----------------------------------------------------------------------


def write_context_report_artifacts(
    plan_payload: Mapping[str, Any],
    output_path: str | Path,
    *,
    notes_path: str | Path | None = None,
    repo: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Build the report and write synchronized markdown/json artifacts.

    Returns a dict including markdown/json paths and optional memory-note sync info.
    """

    payload = build_context_report_payload(plan_payload)
    markdown = render_context_report_markdown(payload)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")

    json_path = _resolve_context_report_json_path(target)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    artifact_refs = [str(target), str(json_path)]
    note_sync: dict[str, Any] | None = None
    if notes_path is not None and str(notes_path).strip():
        note_sync = append_context_report_note(
            payload=payload,
            notes_path=notes_path,
            repo=repo,
            namespace=namespace,
            artifact_refs=artifact_refs,
        )

    return {
        "path": str(target),
        "markdown_path": str(target),
        "json_path": str(json_path),
        "byte_count": len(markdown.encode("utf-8")),
        "ok": True,
        "note_sync": note_sync,
    }


def write_context_report_markdown(
    plan_payload: Mapping[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    """Compatibility wrapper for writing the Markdown context report.

    Also writes the synchronized ``context_report.json`` artifact beside the markdown file.
    """

    return write_context_report_artifacts(plan_payload, output_path)
