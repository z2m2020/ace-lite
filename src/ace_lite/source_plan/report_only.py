"""Report-only source-plan summary helpers for Wave 1 context governance.

These helpers derive additive audit payloads from already-computed stage output.
They must not change candidate ranking, gating, or downstream execution.
"""

from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _str(value: Any) -> str:
    return str(value) if value is not None else ""


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


def _normalize_path(value: Any) -> str:
    return _str(value).strip().replace("\\", "/").lstrip("./")


def build_history_hits(
    *,
    vcs_history: dict[str, Any] | None,
    focused_files: list[str],
    limit: int = 5,
) -> dict[str, Any]:
    payload = _dict(vcs_history)
    commits = [item for item in _list(payload.get("commits")) if isinstance(item, dict)]
    normalized_focus = {
        _normalize_path(item) for item in focused_files if _normalize_path(item)
    }
    hits: list[dict[str, Any]] = []
    for item in commits[: max(1, int(limit))]:
        files = [
            _normalize_path(path)
            for path in _list(item.get("files"))
            if _normalize_path(path)
        ]
        matched_paths = [path for path in files if path in normalized_focus]
        if not matched_paths:
            continue
        hits.append(
            {
                "hash": _str(item.get("hash")).strip(),
                "subject": _str(item.get("subject")).strip(),
                "author": _str(item.get("author")).strip(),
                "committed_at": _str(item.get("committed_at")).strip(),
                "matched_paths": matched_paths,
                "matched_path_count": len(matched_paths),
                "file_count": len(files),
            }
        )

    return {
        "schema_version": "history_hits_v1",
        "enabled": bool(payload.get("enabled", False)),
        "reason": _str(payload.get("reason")).strip() or "disabled",
        "commit_count": _int(payload.get("commit_count"), len(commits)),
        "path_count": _int(payload.get("path_count"), len(normalized_focus)),
        "hit_count": len(hits),
        "hits": hits,
    }


def build_candidate_review(
    *,
    focused_files: list[str],
    candidate_chunks: list[dict[str, Any]],
    evidence_summary: dict[str, Any] | None,
    failure_signal_summary: dict[str, Any] | None,
    validation_tests: list[str],
) -> dict[str, Any]:
    evidence = _dict(evidence_summary)
    failure = _dict(failure_signal_summary)

    direct_ratio = _float(evidence.get("direct_ratio"))
    hint_ratio = _float(evidence.get("hint_only_ratio"))
    neighbor_ratio = _float(evidence.get("neighbor_context_ratio"))
    chunk_count = len([item for item in candidate_chunks if isinstance(item, dict)])
    focus_file_count = len(
        [_normalize_path(item) for item in focused_files if _normalize_path(item)]
    )
    issue_count = _int(failure.get("issue_count"))
    probe_issue_count = _int(failure.get("probe_issue_count"))
    has_failure = bool(failure.get("has_failure", False))

    status = "ok"
    recommendations: list[str] = []
    watch_items: list[str] = []

    if hint_ratio >= 0.5:
        status = "watch"
        watch_items.append("hint_heavy_shortlist")
        recommendations.append("Open the top direct-evidence chunks before following hint-only candidates.")
    if direct_ratio <= 0.25 and chunk_count > 0:
        status = "watch"
        watch_items.append("low_direct_grounding")
        recommendations.append("Prefer files with direct grounding before widening the shortlist.")
    if not validation_tests:
        status = "watch"
        watch_items.append("missing_validation_tests")
        recommendations.append("Add at least one validation test before applying a patch.")
    if has_failure or issue_count > 0 or probe_issue_count > 0:
        status = "watch"
        watch_items.append("validation_feedback_present")
        recommendations.append("Review validation findings before reusing this shortlist.")
    if chunk_count <= 0:
        status = "thin_context"
        watch_items.append("missing_candidate_chunks")
        recommendations.append("Re-run retrieval or inspect entrypoint files before editing.")
    if focus_file_count <= 0:
        status = "thin_context"
        watch_items.append("missing_focus_files")
        recommendations.append("Identify at least one focus path before producing a final patch plan.")
    if not recommendations:
        recommendations.append("Shortlist looks stable enough for manual file review.")

    return {
        "schema_version": "candidate_review_v1",
        "status": status,
        "focus_file_count": focus_file_count,
        "candidate_chunk_count": chunk_count,
        "validation_test_count": len(validation_tests),
        "direct_ratio": direct_ratio,
        "neighbor_context_ratio": neighbor_ratio,
        "hint_only_ratio": hint_ratio,
        "failure_feedback_present": has_failure or issue_count > 0 or probe_issue_count > 0,
        "watch_items": watch_items,
        "recommendations": recommendations,
    }


def build_validation_findings(
    *,
    validation_result: dict[str, Any] | None,
) -> dict[str, Any]:
    result = _dict(validation_result)
    summary = _dict(result.get("summary"))
    probes = _dict(result.get("probes"))
    tests = _dict(result.get("tests"))

    findings: list[dict[str, Any]] = []

    status = _str(summary.get("status")).strip() or "skipped"
    issue_count = _int(summary.get("issue_count"))
    probe_status = _str(probes.get("status")).strip() or "disabled"
    probe_issue_count = _int(probes.get("issue_count"))
    selected_tests = _list(tests.get("selected"))
    executed_tests = _list(tests.get("executed"))

    if status in {"passed", "ok"} and issue_count <= 0:
        findings.append(
            {
                "severity": "info",
                "code": "validation_clean",
                "message": "Validation completed without reported issues.",
            }
        )
    elif issue_count > 0:
        severity = "blocker" if status in {"failed", "timeout"} else "warn"
        findings.append(
            {
                "severity": severity,
                "code": f"validation_{status or 'issues'}",
                "message": f"Validation reported {issue_count} issue(s).",
            }
        )
    elif status and status not in {"skipped", "disabled"}:
        findings.append(
            {
                "severity": "info",
                "code": f"validation_{status}",
                "message": f"Validation status is {status}.",
            }
        )

    if probe_issue_count > 0 or probe_status in {"failed", "timeout", "degraded"}:
        severity = "blocker" if probe_status in {"failed", "timeout"} else "warn"
        findings.append(
            {
                "severity": severity,
                "code": f"probe_{probe_status or 'issue'}",
                "message": f"Validation probes reported {probe_issue_count} issue(s).",
            }
        )

    if selected_tests and not executed_tests:
        findings.append(
            {
                "severity": "warn",
                "code": "selected_tests_not_executed",
                "message": "Validation selected tests but did not execute any of them.",
            }
        )
    elif not selected_tests:
        findings.append(
            {
                "severity": "warn",
                "code": "validation_test_selection_empty",
                "message": "No validation tests were selected for this source plan.",
            }
        )

    severity_counts = {"info": 0, "warn": 0, "blocker": 0}
    for item in findings:
        severity = _str(item.get("severity")).strip().lower()
        if severity in severity_counts:
            severity_counts[severity] += 1

    return {
        "schema_version": "validation_findings_v1",
        "status": status,
        "probe_status": probe_status,
        "selected_test_count": len(selected_tests),
        "executed_test_count": len(executed_tests),
        "info_count": severity_counts["info"],
        "warn_count": severity_counts["warn"],
        "blocker_count": severity_counts["blocker"],
        "findings": findings,
    }


def build_session_end_report(
    *,
    query: str,
    focused_files: list[str],
    validation_tests: list[str],
    diagnostics: list[Any],
    candidate_review: dict[str, Any] | None,
    validation_findings: dict[str, Any] | None,
    history_hits: dict[str, Any] | None,
) -> dict[str, Any]:
    review = _dict(candidate_review)
    findings = _dict(validation_findings)
    history = _dict(history_hits)

    next_actions: list[str] = []
    risks: list[str] = []

    if review:
        next_actions.extend(
            [
                _str(item).strip()
                for item in _list(review.get("recommendations"))
                if _str(item).strip()
            ][:3]
        )
        risks.extend(
            [_str(item).strip() for item in _list(review.get("watch_items")) if _str(item).strip()][:3]
        )
    if _int(findings.get("blocker_count")) > 0:
        next_actions.append("Resolve blocker-level validation findings before applying changes.")
        risks.append("validation_blockers_present")
    elif _int(findings.get("warn_count")) > 0:
        next_actions.append("Review warning-level validation findings before widening the patch.")
    if validation_tests:
        next_actions.append("Run the suggested validation tests after editing the focus files.")
    if _int(history.get("hit_count")) > 0:
        next_actions.append("Check the recent matching commits before repeating the same change pattern.")
    if diagnostics:
        risks.append("augment_diagnostics_present")
    if not next_actions:
        next_actions.append("Open the top focus file and inspect the first prioritized chunk.")

    deduped_next_actions: list[str] = []
    seen_actions: set[str] = set()
    for item in next_actions:
        normalized = _str(item).strip()
        if not normalized or normalized in seen_actions:
            continue
        seen_actions.add(normalized)
        deduped_next_actions.append(normalized)

    deduped_risks: list[str] = []
    seen_risks: set[str] = set()
    for item in risks:
        normalized = _str(item).strip()
        if not normalized or normalized in seen_risks:
            continue
        seen_risks.add(normalized)
        deduped_risks.append(normalized)

    return {
        "schema_version": "session_end_report_v1",
        "goal": _str(query).strip(),
        "focus_paths": [
            _normalize_path(item) for item in focused_files if _normalize_path(item)
        ][:5],
        "validation_tests": [
            _str(item).strip() for item in validation_tests if _str(item).strip()
        ][:5],
        "next_actions": deduped_next_actions[:5],
        "risks": deduped_risks[:5],
        "history_context_present": _int(history.get("hit_count")) > 0,
        "validation_status": _str(findings.get("status")).strip() or "skipped",
    }


__all__ = [
    "build_candidate_review",
    "build_history_hits",
    "build_session_end_report",
    "build_validation_findings",
]
