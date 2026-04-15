from __future__ import annotations

from typing import Any


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


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def append_history_channel_section(lines: list[str], payload: dict[str, Any]) -> None:
    history_channel = _dict(payload.get("history_channel", {}))
    if not history_channel:
        return

    history_summary = _dict(history_channel.get("history_hits", {}))
    lines.append("## History Channel")
    lines.append(
        "- **Status**: {status}; focused_files={focus}; commits={commits}; hits={hits}".format(
            status=_str(history_channel.get("reason", "disabled")) or "disabled",
            focus=len(_list(history_channel.get("focused_files", []))),
            commits=_int(history_channel.get("commit_count", 0)),
            hits=_int(history_channel.get("hit_count", 0)),
        )
    )
    for item in _list(history_summary.get("hits", []))[:5]:
        lines.append(
            "- `{hash}` {subject}".format(
                hash=_str(item.get("hash", ""))[:12],
                subject=_str(item.get("subject", "")),
            )
        )
    for item in _list(history_channel.get("recommendations", []))[:3]:
        lines.append(f"- recommendation: {_str(item)}")
    lines.append("")


def append_history_hits_section(lines: list[str], payload: dict[str, Any]) -> None:
    history_hits = _dict(payload.get("history_hits", {}))
    if not history_hits:
        return

    lines.append("## History Hits")
    hits = _list(history_hits.get("hits", []))
    lines.append(
        "- **Status**: {status}; hits={hits}; commits={commits}".format(
            status=_str(history_hits.get("reason", "disabled")) or "disabled",
            hits=len(hits),
            commits=_int(history_hits.get("commit_count", 0)),
        )
    )
    if hits:
        for item in hits[:5]:
            lines.append(
                "- `{hash}` {subject}".format(
                    hash=_str(item.get("hash", ""))[:12],
                    subject=_str(item.get("subject", "")),
                )
            )
            matched_paths = _list(item.get("matched_paths", []))
            if matched_paths:
                lines.append(
                    "  - matched_paths: {paths}".format(
                        paths=", ".join(_str(path) for path in matched_paths[:3])
                    )
                )
    lines.append("")


def append_context_refine_section(lines: list[str], payload: dict[str, Any]) -> None:
    context_refine = _dict(payload.get("context_refine", {}))
    if not context_refine:
        return

    lines.append("## Context Refine")
    decision_counts = _dict(context_refine.get("decision_counts", {}))
    review = _dict(context_refine.get("candidate_review", {}))
    lines.append(
        "- **Status**: {status}; focused_files={focus}; keep={keep}; downrank={downrank}; drop={drop}; need_more_read={need_more_read}".format(
            status=_str(review.get("status", "")) or "unknown",
            focus=len(_list(context_refine.get("focused_files", []))),
            keep=_int(decision_counts.get("keep", 0)),
            downrank=_int(decision_counts.get("downrank", 0)),
            drop=_int(decision_counts.get("drop", 0)),
            need_more_read=_int(decision_counts.get("need_more_read", 0)),
        )
    )
    for item in _list(review.get("recommendations", []))[:3]:
        lines.append(f"- recommendation: {_str(item)}")
    lines.append("")


def append_core_nodes_section(lines: list[str], payload: dict[str, Any]) -> None:
    core_nodes = _list(payload.get("core_nodes", []))
    if not core_nodes:
        return

    lines.append("## Core Nodes")
    lines.append(f"*Total: {len(core_nodes)}*")
    lines.append("")
    for node in core_nodes[:10]:
        score = _float(node.get("score", 0.0))
        source = _str(node.get("source", ""))
        reason = _str(node.get("reason", ""))
        conf = _str(node.get("evidence_confidence", ""))
        conf_str = f" [`{conf}`]" if conf else ""
        lines.append(
            f"- **{_str(node.get('label', ''))}** "
            f"(score={score:.2f}, source={source}){conf_str}"
        )
        lines.append(f"  - path: `{_str(node.get('path', ''))}`")
        lines.append(f"  - reason: {reason}")
    if len(core_nodes) > 10:
        lines.append(f"  ... *and {len(core_nodes) - 10} more*")
    lines.append("")


def append_candidate_review_section(lines: list[str], payload: dict[str, Any]) -> None:
    candidate_review = _dict(payload.get("candidate_review", {}))
    if not candidate_review:
        return

    lines.append("## Candidate Review")
    lines.append(
        "- **Status**: {status}; focus_files={focus}; chunks={chunks}; validation_tests={tests}".format(
            status=_str(candidate_review.get("status", "")) or "unknown",
            focus=_int(candidate_review.get("focus_file_count", 0)),
            chunks=_int(candidate_review.get("candidate_chunk_count", 0)),
            tests=_int(candidate_review.get("validation_test_count", 0)),
        )
    )
    watch_items = _list(candidate_review.get("watch_items", []))
    if watch_items:
        lines.append(
            "- **Watch items**: {items}".format(
                items=", ".join(_str(item) for item in watch_items)
            )
        )
    for item in _list(candidate_review.get("recommendations", []))[:3]:
        lines.append(f"- recommendation: {_str(item)}")
    lines.append("")


def append_surprising_connections_section(
    lines: list[str], payload: dict[str, Any]
) -> None:
    surprising = _list(payload.get("surprising_connections", []))
    lines.append("## Surprising Connections")
    if surprising:
        lines.append(f"*Total: {len(surprising)}*")
        lines.append("")
        for conn in surprising[:8]:
            boost = ", ".join(_list(conn.get("boost_sources", [])))
            lines.append(
                f"- **{_str(conn.get('label', _str(conn.get('path', ''))))}** "
                f"(boost: {boost or 'cross_directory'})"
            )
            related = _str(conn.get("related_path", ""))
            if related:
                lines.append(f"  - related: `{related}`")
    else:
        lines.append("*No surprising connections detected.*")
    lines.append("")


def append_confidence_breakdown_section(lines: list[str], payload: dict[str, Any]) -> None:
    breakdown = _dict(payload.get("confidence_breakdown", {}))
    if not breakdown:
        return

    lines.append("## Confidence Breakdown")
    total = _int(breakdown.get("total_count", 0))
    extracted = _int(breakdown.get("extracted_count", 0))
    inferred = _int(breakdown.get("inferred_count", 0))
    ambiguous = _int(breakdown.get("ambiguous_count", 0))
    unknown = _int(breakdown.get("unknown_count", 0))
    lines.append(f"- **EXTRACTED** (direct evidence): {extracted}/{total}")
    lines.append(f"- **INFERRED** (neighbor/hint): {inferred}/{total}")
    lines.append(f"- **AMBIGUOUS** (weak evidence): {ambiguous}/{total}")
    lines.append(f"- **UNKNOWN**: {unknown}/{total}")
    lines.append("")


def append_validation_findings_section(
    lines: list[str], payload: dict[str, Any]
) -> None:
    validation_findings = _dict(payload.get("validation_findings", {}))
    if not validation_findings:
        return

    lines.append("## Validation Findings")
    lines.append(
        "- **Status**: {status}; info={info}; warn={warn}; blocker={blocker}".format(
            status=_str(validation_findings.get("status", "")) or "unknown",
            info=_int(validation_findings.get("info_count", 0)),
            warn=_int(validation_findings.get("warn_count", 0)),
            blocker=_int(validation_findings.get("blocker_count", 0)),
        )
    )
    for item in _list(validation_findings.get("findings", []))[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- `{severity}` {code}: {message}".format(
                severity=_str(item.get("severity", "")).upper() or "INFO",
                code=_str(item.get("code", "")),
                message=_str(item.get("message", "")),
            )
        )
    lines.append("")


def append_knowledge_gaps_section(lines: list[str], payload: dict[str, Any]) -> None:
    gaps = _list(payload.get("knowledge_gaps", []))
    lines.append("## Knowledge Gaps")
    if gaps:
        for gap in gaps:
            severity = _str(gap.get("severity", "medium"))
            code = _str(gap.get("code", ""))
            message = _str(gap.get("message", ""))
            lines.append(f"- `[{severity.upper()}]` **{code}**: {message}")
    else:
        lines.append("*No knowledge gaps identified.*")
    lines.append("")


def append_suggested_questions_section(
    lines: list[str], payload: dict[str, Any]
) -> None:
    questions = _list(payload.get("suggested_questions", []))
    lines.append("## Suggested Questions")
    if questions:
        for q in questions:
            qtype = _str(q.get("type", ""))
            question = _str(q.get("question", ""))
            why = _str(q.get("why", ""))
            lines.append(f"- **{qtype}**: {question}")
            if why:
                lines.append(f"  - *{why}*")
    else:
        lines.append("*No questions generated.*")
    lines.append("")


def append_warnings_section(lines: list[str], payload: dict[str, Any]) -> None:
    warnings = _list(payload.get("warnings", []))
    if not warnings:
        return

    lines.append("## Warnings")
    for item in warnings:
        lines.append(f"- warning: {item}")
    lines.append("")


def append_session_end_report_section(
    lines: list[str], payload: dict[str, Any]
) -> None:
    session_end_report = _dict(payload.get("session_end_report", {}))
    if not session_end_report:
        return

    lines.append("## Session End Report")
    goal = _str(session_end_report.get("goal", ""))
    if goal:
        lines.append(f"- **Goal**: {goal}")
    focus_paths = _list(session_end_report.get("focus_paths", []))
    if focus_paths:
        lines.append(
            "- **Focus paths**: {paths}".format(
                paths=", ".join(_str(item) for item in focus_paths[:5])
            )
        )
    validation_tests = _list(session_end_report.get("validation_tests", []))
    if validation_tests:
        lines.append(
            "- **Validation tests**: {tests}".format(
                tests=", ".join(_str(item) for item in validation_tests[:3])
            )
        )
    for item in _list(session_end_report.get("next_actions", []))[:5]:
        lines.append(f"- next_action: {_str(item)}")
    risks = _list(session_end_report.get("risks", []))
    if risks:
        lines.append(
            "- **Risks**: {risks}".format(
                risks=", ".join(_str(item) for item in risks[:5])
            )
        )
    lines.append("")


def append_handoff_payload_section(lines: list[str], payload: dict[str, Any]) -> None:
    handoff_payload = _dict(payload.get("handoff_payload", {}))
    if not handoff_payload:
        return

    lines.append("## Handoff Payload")
    goal = _str(handoff_payload.get("goal", ""))
    if goal:
        lines.append(f"- **Goal**: {goal}")
    focus_paths = _list(handoff_payload.get("focus_paths", []))
    if focus_paths:
        lines.append(
            "- **Focus paths**: {paths}".format(
                paths=", ".join(_str(item) for item in focus_paths[:5])
            )
        )
    for item in _list(handoff_payload.get("next_tasks", []))[:5]:
        lines.append(f"- next_task: {_str(item)}")
    unresolved = _list(handoff_payload.get("unresolved", []))
    if unresolved:
        lines.append(
            "- **Unresolved**: {items}".format(
                items=", ".join(_str(item) for item in unresolved[:5])
            )
        )
    lines.append("")
