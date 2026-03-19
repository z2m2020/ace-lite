from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ace_lite.dev_feedback_store import DevFix

if TYPE_CHECKING:
    from ace_lite.issue_report_store import IssueReport


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(str(value or ""))]


def _unique_non_empty(items: list[str], *, limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        normalized = str(item or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if limit is not None and len(out) >= limit:
            break
    return out


def build_issue_report_case_id(*, report: IssueReport) -> str:
    suffix = str(report.issue_id or "issue").strip().lower().replace("_", "-")
    suffix = re.sub(r"[^a-z0-9-]+", "-", suffix).strip("-")
    return f"issue-report-{suffix or 'unknown'}"


def derive_issue_report_expected_keys(
    *,
    report: IssueReport,
    limit: int = 8,
) -> list[str]:
    candidate_tokens: list[str] = []
    selected_path = str(report.selected_path or "").strip()
    if selected_path:
        path = Path(selected_path)
        candidate_tokens.extend(_tokenize(path.stem))
        candidate_tokens.extend(_tokenize(path.parent.as_posix()))
    candidate_tokens.extend(_tokenize(report.title))
    candidate_tokens.extend(_tokenize(report.query))
    candidate_tokens.extend(_tokenize(report.category))
    candidate_tokens.extend(_tokenize(report.severity))
    filtered = [token for token in candidate_tokens if len(token) >= 3]
    return _unique_non_empty(filtered, limit=limit)


def build_issue_report_benchmark_case(
    *,
    report: IssueReport,
    case_id: str | None = None,
    comparison_lane: str = "issue_report_feedback",
    top_k: int = 8,
    min_validation_tests: int = 1,
) -> dict[str, Any]:
    expected_keys = derive_issue_report_expected_keys(report=report)
    if not expected_keys and report.selected_path:
        expected_keys = [Path(report.selected_path).stem.lower()]
    filters: dict[str, Any] = {}
    if report.selected_path:
        filters["include_paths"] = [str(report.selected_path)]
    return {
        "case_id": str(case_id or build_issue_report_case_id(report=report)),
        "query": str(report.query),
        "expected_keys": expected_keys,
        "top_k": max(1, int(top_k)),
        "comparison_lane": str(comparison_lane or "issue_report_feedback"),
        "task_success": {
            "mode": "positive",
            "min_validation_tests": max(1, int(min_validation_tests)),
        },
        "filters": filters,
        "issue_report": {
            "issue_id": str(report.issue_id),
            "repo": str(report.repo),
            "category": str(report.category),
            "severity": str(report.severity),
            "status": str(report.status),
            "selected_path": str(report.selected_path),
            "plan_payload_ref": str(report.plan_payload_ref),
        },
    }


def export_issue_report_benchmark_case(
    *,
    report: IssueReport,
    output_path: str | Path,
    case_id: str | None = None,
    comparison_lane: str = "issue_report_feedback",
    top_k: int = 8,
    min_validation_tests: int = 1,
    append: bool = True,
) -> dict[str, Any]:
    target = Path(output_path).expanduser().resolve()
    case_payload = build_issue_report_benchmark_case(
        report=report,
        case_id=case_id,
        comparison_lane=comparison_lane,
        top_k=top_k,
        min_validation_tests=min_validation_tests,
    )
    payload: dict[str, Any] = {"cases": []}
    if append and target.exists():
        loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("cases"), list):
            payload = {"cases": list(loaded.get("cases", []))}
    existing_cases = payload["cases"]
    if not isinstance(existing_cases, list):
        existing_cases = []
    deduped_cases = [
        item
        for item in existing_cases
        if not (
            isinstance(item, dict)
            and str(item.get("case_id") or "").strip()
            == str(case_payload["case_id"])
        )
    ]
    deduped_cases.append(case_payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump({"cases": deduped_cases}, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return {
        "output_path": str(target),
        "case": case_payload,
        "case_count": len(deduped_cases),
    }


def build_issue_report_resolution_from_fix(
    *,
    report: IssueReport,
    fix: DevFix,
    resolved_at: str | None = None,
    status: str = "resolved",
) -> dict[str, Any]:
    attachments = list(report.attachments)
    fix_ref = f"dev-fix://{fix.fix_id}"
    if fix_ref not in attachments:
        attachments.append(fix_ref)
    return {
        **report.to_payload(),
        "status": status,
        "resolved_at": resolved_at or fix.created_at,
        "resolution_note": fix.resolution_note,
        "attachments": attachments,
        "updated_at": resolved_at or fix.created_at,
    }


__all__ = [
    "build_issue_report_benchmark_case",
    "build_issue_report_case_id",
    "build_issue_report_resolution_from_fix",
    "derive_issue_report_expected_keys",
    "export_issue_report_benchmark_case",
]
