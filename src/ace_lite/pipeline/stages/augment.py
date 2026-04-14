from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path
from typing import Any

from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.vcs_history import collect_git_commit_history
from ace_lite.vcs_worktree import collect_git_worktree_summary

_FRAME_PATTERNS = (
    re.compile(r'File "(?P<path>.+?)", line (?P<line>\d+)', re.IGNORECASE),
    re.compile(r'(?P<path>[\w./\-]+):(?:line\s*)?(?P<line>\d+)', re.IGNORECASE),
)
SBFL_METRIC_CHOICES = ("ochiai", "dstar")


def _empty_tests_payload(*, reason: str = "none") -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": reason,
        "failures": [],
        "stack_frames": [],
        "suspicious_chunks": [],
        "suggested_tests": [],
        "inputs": {
            "junit_xml": None,
            "failed_test_report": None,
            "coverage_json": None,
            "sbfl_json": None,
            "sbfl_metric": "ochiai",
            "report_format": "none",
        },
    }


def _empty_vcs_history_payload(*, reason: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason or "disabled"),
        "commit_count": 0,
        "commits": [],
        "error": "",
    }


def _empty_vcs_worktree_payload(*, reason: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason or "disabled"),
        "changed_count": 0,
        "entries": [],
        "truncated": False,
        "error": "",
    }


def _empty_vcs_worktree_diffstat() -> dict[str, Any]:
    return {
        "file_count": 0,
        "binary_count": 0,
        "additions": 0,
        "deletions": 0,
        "files": [],
        "error": None,
        "timed_out": False,
        "truncated": False,
    }


def _format_fail_open_error(*, exc: BaseException, fallback: str) -> str:
    message = str(exc).strip()
    return message[:240] if message else fallback


def _error_vcs_history_payload(
    *,
    error: str,
    path_count: int,
    limit: int,
) -> dict[str, Any]:
    payload = _empty_vcs_history_payload(reason="error")
    payload["enabled"] = True
    payload["path_count"] = max(0, int(path_count))
    payload["limit"] = max(1, int(limit))
    payload["error"] = str(error)
    payload["elapsed_ms"] = 0.0
    payload["timeout_seconds"] = 0.0
    return payload


def _error_vcs_worktree_payload(*, error: str, max_files: int) -> dict[str, Any]:
    return {
        "enabled": True,
        "reason": "error",
        "changed_count": 0,
        "staged_count": 0,
        "unstaged_count": 0,
        "untracked_count": 0,
        "entries": [],
        "diffstat": {
            "staged": _empty_vcs_worktree_diffstat(),
            "unstaged": _empty_vcs_worktree_diffstat(),
        },
        "error": str(error),
        "elapsed_ms": 0.0,
        "timeout_seconds": 0.0,
        "max_files": max(1, int(max_files)),
        "truncated": False,
    }


def _collect_vcs_history_fail_open(
    *,
    root: str,
    candidate_paths: list[str],
    history_limit_files: int,
) -> dict[str, Any]:
    selected_paths = candidate_paths[: max(1, int(history_limit_files))]
    try:
        payload = collect_git_commit_history(
            repo_root=root,
            paths=selected_paths,
            limit=12,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return _error_vcs_history_payload(
            error=_format_fail_open_error(exc=exc, fallback="vcs_history_error"),
            path_count=len(selected_paths),
            limit=12,
        )
    if isinstance(payload, dict):
        return payload
    return _error_vcs_history_payload(
        error="invalid_vcs_history_payload",
        path_count=len(selected_paths),
        limit=12,
    )


def _collect_vcs_worktree_fail_open(*, root: str, max_files: int) -> dict[str, Any]:
    try:
        payload = collect_git_worktree_summary(
            repo_root=root,
            max_files=max_files,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return _error_vcs_worktree_payload(
            error=_format_fail_open_error(exc=exc, fallback="vcs_worktree_error"),
            max_files=max_files,
        )
    if isinstance(payload, dict):
        return payload
    return _error_vcs_worktree_payload(
        error="invalid_vcs_worktree_payload",
        max_files=max_files,
    )


def _normalize_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/")


def _normalize_sbfl_metric(value: str | None) -> str:
    normalized = str(value or "ochiai").strip().lower() or "ochiai"
    if normalized not in SBFL_METRIC_CHOICES:
        return "ochiai"
    return normalized


def _to_non_negative_float(*values: Any) -> float:
    for value in values:
        candidate: float | None
        try:
            candidate = float(value)
        except Exception:
            candidate = None
        if candidate is None:
            continue
        if math.isfinite(candidate) and candidate >= 0.0:
            return candidate
    return 0.0


def _compute_sbfl_score(*, item: dict[str, Any], metric: str) -> float:
    score = _to_non_negative_float(item.get("score"), item.get("suspiciousness"))
    if score > 0.0:
        return score

    ef = _to_non_negative_float(
        item.get("ef"),
        item.get("failed_covered"),
        item.get("failedCovered"),
        item.get("ncf"),
    )
    ep = _to_non_negative_float(
        item.get("ep"),
        item.get("passed_covered"),
        item.get("passedCovered"),
        item.get("ncs"),
    )
    nf = _to_non_negative_float(
        item.get("nf"),
        item.get("failed_not_covered"),
        item.get("failedNotCovered"),
        item.get("nuf"),
    )

    normalized_metric = _normalize_sbfl_metric(metric)
    if normalized_metric == "dstar":
        denominator = ep + nf
        if denominator <= 0.0:
            return ef * ef
        return (ef * ef) / denominator

    denominator = math.sqrt((ef + nf) * (ef + ep))
    if denominator <= 0.0:
        return 0.0
    return ef / denominator


def _parse_junit(path: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path:
        return [], []

    source = Path(path)
    if not source.exists() or not source.is_file():
        return [], []

    try:
        # Trusted local JUnit XML produced by test tooling.
        tree = ET.parse(source)  # nosec B314
    except Exception:
        return [], []

    failures: list[dict[str, Any]] = []
    stack_frames: list[dict[str, Any]] = []

    for testcase in tree.findall(".//testcase"):
        name = str(testcase.attrib.get("name") or "").strip()
        suite = str(testcase.attrib.get("classname") or "").strip()
        file_path = str(testcase.attrib.get("file") or "").strip()
        line_raw = testcase.attrib.get("line")
        line_text = str(line_raw or "").strip()
        line_no = int(line_text) if line_text.isdigit() else None

        issue_node = testcase.find("failure")
        if issue_node is None:
            issue_node = testcase.find("error")
        if issue_node is None:
            continue

        message = str(issue_node.attrib.get("message") or "").strip()
        body = str(issue_node.text or "")
        failure = {
            "suite": suite,
            "name": name,
            "file": _normalize_path(file_path),
            "line": line_no,
            "message": message or body.strip().splitlines()[0] if body.strip() else "",
        }
        failures.append(failure)

        for pattern in _FRAME_PATTERNS:
            for match in pattern.finditer(body):
                frame_path = _normalize_path(match.group("path"))
                line_text = str(match.group("line") or "")
                if not frame_path or not line_text.isdigit():
                    continue
                stack_frames.append(
                    {
                        "path": frame_path,
                        "line": int(line_text),
                        "source": "junit",
                        "test": f"{suite}::{name}" if suite and name else (name or suite),
                    }
                )

    return failures, stack_frames


def _parse_failed_test_report_json(
    path: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path:
        return [], []

    source = Path(path)
    if not source.exists() or not source.is_file():
        return [], []

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return [], []

    records: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        failures_payload = payload.get("failures")
        if isinstance(failures_payload, list):
            records.extend([item for item in failures_payload if isinstance(item, dict)])

        tests = payload.get("tests")
        if isinstance(tests, list):
            for item in tests:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status") or item.get("outcome") or "").strip().lower()
                if status not in {"failed", "failure", "error"}:
                    continue
                records.append(item)
    elif isinstance(payload, list):
        records.extend([item for item in payload if isinstance(item, dict)])

    failures: list[dict[str, Any]] = []
    stack_frames: list[dict[str, Any]] = []

    for item in records:
        suite = str(item.get("suite") or item.get("classname") or item.get("class") or "").strip()
        name = str(item.get("name") or item.get("test") or item.get("case") or "").strip()
        file_path = _normalize_path(str(item.get("file") or item.get("path") or "").strip())

        line_raw = item.get("line", item.get("lineno"))
        try:
            line_no: int | None = int(str(line_raw))
        except Exception:
            line_no = None

        message = str(item.get("message") or item.get("error") or "").strip()
        trace = str(
            item.get("traceback")
            or item.get("stacktrace")
            or item.get("body")
            or item.get("details")
            or ""
        )

        failures.append(
            {
                "suite": suite,
                "name": name,
                "file": file_path,
                "line": line_no,
                "message": message or (trace.strip().splitlines()[0] if trace.strip() else ""),
            }
        )

        if file_path and isinstance(line_no, int) and line_no > 0:
            stack_frames.append(
                {
                    "path": file_path,
                    "line": int(line_no),
                    "source": "json_report",
                    "test": f"{suite}::{name}" if suite and name else (name or suite),
                }
            )

        for pattern in _FRAME_PATTERNS:
            for match in pattern.finditer(trace):
                frame_path = _normalize_path(match.group("path"))
                line_text = str(match.group("line") or "")
                if not frame_path or not line_text.isdigit():
                    continue
                stack_frames.append(
                    {
                        "path": frame_path,
                        "line": int(line_text),
                        "source": "json_report",
                        "test": f"{suite}::{name}" if suite and name else (name or suite),
                    }
                )

    return failures, stack_frames


def _parse_failed_test_report(
    path: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if not path:
        return [], [], "none"

    source = Path(path)
    if not source.exists() or not source.is_file():
        return [], [], "missing"

    suffix = source.suffix.lower()
    if suffix == ".json":
        failures, stack_frames = _parse_failed_test_report_json(path)
        return failures, stack_frames, "json"

    failures, stack_frames = _parse_junit(path)
    if failures or stack_frames:
        return failures, stack_frames, "junit_xml"

    fallback_failures, fallback_frames = _parse_failed_test_report_json(path)
    if fallback_failures or fallback_frames:
        return fallback_failures, fallback_frames, "json"

    return failures, stack_frames, "junit_xml"


def _build_suggested_tests(
    *,
    failures: list[dict[str, Any]],
    sbfl_items: list[dict[str, Any]],
    max_items: int = 20,
) -> list[str]:
    weights: dict[str, float] = {}

    for item in failures:
        if not isinstance(item, dict):
            continue
        suite = str(item.get("suite") or "").strip()
        name = str(item.get("name") or "").strip()
        label = f"{suite}::{name}" if suite and name else (name or suite)
        if not label:
            continue
        weights[label] = float(weights.get(label, 0.0)) + 3.0

    for item in sbfl_items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("test") or "").strip()
        if not label:
            continue
        score = max(0.0, float(item.get("score") or 0.0))
        weights[label] = float(weights.get(label, 0.0)) + 1.0 + min(1.0, score)

    ranked = sorted(weights.items(), key=lambda row: (-float(row[1]), str(row[0])))
    return [label for label, _score in ranked[: max(1, int(max_items))]]


def _parse_coverage(path: str | None) -> dict[str, set[int]]:
    if not path:
        return {}

    source = Path(path)
    if not source.exists() or not source.is_file():
        return {}

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}

    coverage: dict[str, set[int]] = {}

    def absorb(file_path: str, lines: Any) -> None:
        normalized = _normalize_path(file_path)
        if not normalized:
            return
        values: set[int] = set()
        if isinstance(lines, list):
            for item in lines:
                parsed: int | None
                try:
                    parsed = int(item)
                except Exception:
                    parsed = None
                if parsed is None:
                    continue
                values.add(parsed)
        if values:
            coverage.setdefault(normalized, set()).update(values)

    if isinstance(payload, dict):
        files = payload.get("files")
        if isinstance(files, dict):
            for file_path, item in files.items():
                if isinstance(item, dict):
                    absorb(str(file_path), item.get("executed_lines") or item.get("lines") or [])
                elif isinstance(item, list):
                    absorb(str(file_path), item)

        for file_path, item in payload.items():
            if file_path == "files":
                continue
            if isinstance(item, list):
                absorb(str(file_path), item)
            elif isinstance(item, dict):
                absorb(str(file_path), item.get("executed_lines") or item.get("lines") or [])

    return coverage


def _parse_sbfl(path: str | None, *, metric: str = "ochiai") -> list[dict[str, Any]]:
    if not path:
        return []

    source = Path(path)
    if not source.exists() or not source.is_file():
        return []

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            payload = payload["items"]
        elif isinstance(payload.get("suspicious"), list):
            payload = payload["suspicious"]

    items: list[dict[str, Any]] = []
    if not isinstance(payload, list):
        return items

    normalized_metric = _normalize_sbfl_metric(metric)

    for item in payload:
        if not isinstance(item, dict):
            continue

        path_value = _normalize_path(str(item.get("path") or item.get("file") or ""))
        line_value = item.get("lineno", item.get("line"))
        line_text = str(line_value or "").strip()
        if not line_text.isdigit():
            continue
        line_no = int(line_text)

        score = _compute_sbfl_score(item=item, metric=normalized_metric)

        if not path_value or line_no <= 0:
            continue

        items.append(
            {
                "path": path_value,
                "line": line_no,
                "score": score,
                "metric": normalized_metric,
                "test": str(item.get("test") or "").strip(),
            }
        )

    return items


def _select_suspicious_chunks(
    *,
    candidate_chunks: list[dict[str, Any]],
    stack_frames: list[dict[str, Any]],
    sbfl_items: list[dict[str, Any]],
    coverage: dict[str, set[int]],
    top_n: int = 12,
) -> list[dict[str, Any]]:
    if not isinstance(candidate_chunks, list):
        return []

    frame_by_path: dict[str, list[int]] = {}
    for frame in stack_frames:
        if not isinstance(frame, dict):
            continue
        path = _normalize_path(str(frame.get("path") or ""))
        try:
            line_no = int(frame.get("line") or 0)
        except Exception:
            line_no = 0
        if not path or line_no <= 0:
            continue
        frame_by_path.setdefault(path, []).append(line_no)

    sbfl_by_path: dict[str, list[dict[str, Any]]] = {}
    for item in sbfl_items:
        if not isinstance(item, dict):
            continue
        path = _normalize_path(str(item.get("path") or ""))
        if not path:
            continue
        sbfl_by_path.setdefault(path, []).append(item)

    selected: list[dict[str, Any]] = []

    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue

        path = _normalize_path(str(chunk.get("path") or ""))
        if not path:
            continue

        start_value = chunk.get("lineno") or 0
        end_value = chunk.get("end_lineno") or start_value
        try:
            start = int(start_value)
            end = int(end_value)
        except Exception:
            start = None
            end = None
        if start is None or end is None:
            continue

        if start <= 0:
            continue
        if end < start:
            end = start

        sbfl_score = 0.0
        sbfl_hits = 0
        for item in sbfl_by_path.get(path, []):
            line_no = int(item.get("line") or 0)
            if start <= line_no <= end:
                sbfl_hits += 1
                sbfl_score += max(0.0, float(item.get("score") or 0.0))

        frame_hits = sum(1 for line_no in frame_by_path.get(path, []) if start <= int(line_no) <= end)

        coverage_hits = 0
        for line_no in coverage.get(path, set()):
            if start <= int(line_no) <= end:
                coverage_hits += 1

        score = (sbfl_score * 1.5) + float(frame_hits) + min(1.0, coverage_hits * 0.05)
        if score <= 0:
            continue

        selected.append(
            {
                "path": path,
                "qualified_name": str(chunk.get("qualified_name") or ""),
                "kind": str(chunk.get("kind") or ""),
                "lineno": start,
                "end_lineno": end,
                "score": round(score, 6),
                "score_breakdown": {
                    "sbfl": round(sbfl_score, 6),
                    "sbfl_hits": sbfl_hits,
                    "stack_frames": frame_hits,
                    "coverage_hits": coverage_hits,
                },
            }
        )

    selected.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("path") or ""), int(item.get("lineno") or 0)))
    return selected[: max(0, int(top_n))]


def _collect_test_signals(
    *,
    candidate_chunks: list[dict[str, Any]],
    junit_xml_path: str | None,
    coverage_json_path: str | None,
    sbfl_json_path: str | None,
    sbfl_metric: str = "ochiai",
) -> dict[str, Any]:
    normalized_metric = _normalize_sbfl_metric(sbfl_metric)
    failures, stack_frames, report_format = _parse_failed_test_report(junit_xml_path)
    coverage = _parse_coverage(coverage_json_path)
    sbfl_items = _parse_sbfl(sbfl_json_path, metric=normalized_metric)
    suspicious_chunks = _select_suspicious_chunks(
        candidate_chunks=candidate_chunks,
        stack_frames=stack_frames,
        sbfl_items=sbfl_items,
        coverage=coverage,
    )

    suggested_tests = _build_suggested_tests(
        failures=failures,
        sbfl_items=sbfl_items,
        max_items=20,
    )

    enabled = bool(junit_xml_path or coverage_json_path or sbfl_json_path)
    return {
        "enabled": enabled,
        "reason": "provided" if enabled else "not_provided",
        "failures": failures,
        "stack_frames": stack_frames,
        "suspicious_chunks": suspicious_chunks,
        "suggested_tests": suggested_tests,
        "sbfl_metric": normalized_metric,
        "sbfl_item_count": len(sbfl_items),
        "inputs": {
            "junit_xml": junit_xml_path,
            "failed_test_report": junit_xml_path,
            "coverage_json": coverage_json_path,
            "sbfl_json": sbfl_json_path,
            "sbfl_metric": normalized_metric,
            "report_format": report_format,
        },
    }


def run_diagnostics_augment(
    *,
    root: str,
    query: str,
    index_stage: dict[str, Any],
    enabled: bool,
    top_n: int,
    broker: LspDiagnosticsBroker | None,
    xref_enabled: bool,
    xref_top_n: int,
    xref_time_budget_ms: int,
    candidate_chunks: list[dict[str, Any]] | None = None,
    junit_xml_path: str | None = None,
    coverage_json_path: str | None = None,
    sbfl_json_path: str | None = None,
    sbfl_metric: str = "ochiai",
    vcs_enabled: bool = True,
    vcs_worktree_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chunk_candidates = candidate_chunks if isinstance(candidate_chunks, list) else []
    tests_payload = _collect_test_signals(
        candidate_chunks=chunk_candidates,
        junit_xml_path=junit_xml_path,
        coverage_json_path=coverage_json_path,
        sbfl_json_path=sbfl_json_path,
        sbfl_metric=sbfl_metric,
    )

    if not enabled:
        vcs_worktree = (
            dict(vcs_worktree_override)
            if isinstance(vcs_worktree_override, dict) and vcs_worktree_override
            else _empty_vcs_worktree_payload(reason="disabled")
        )
        return {
            "enabled": False,
            "count": 0,
            "diagnostics": [],
            "errors": [],
            "reason": "disabled",
            "vcs_history": _empty_vcs_history_payload(reason="disabled"),
            "vcs_worktree": vcs_worktree,
            "xref_enabled": bool(xref_enabled),
            "xref": {
                "count": 0,
                "results": [],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 0.0,
                "time_budget_ms": max(1, int(xref_time_budget_ms)),
            },
            "tests": tests_payload,
        }

    candidates = index_stage.get("candidate_files", [])
    if not isinstance(candidates, list):
        candidates = []

    candidate_paths: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in candidate_paths:
            continue
        candidate_paths.append(path)

    if vcs_enabled:
        history_limit_files = max(1, min(8, int(top_n)))
        vcs_history = _collect_vcs_history_fail_open(
            root=root,
            candidate_paths=candidate_paths,
            history_limit_files=history_limit_files,
        )
        if isinstance(vcs_worktree_override, dict) and vcs_worktree_override:
            vcs_worktree = vcs_worktree_override
        else:
            vcs_worktree = _collect_vcs_worktree_fail_open(
                root=root,
                max_files=48,
            )
    else:
        vcs_history = _empty_vcs_history_payload(reason="disabled")
        vcs_worktree = _empty_vcs_worktree_payload(reason="disabled")

    if broker is None:
        return {
            "enabled": False,
            "count": 0,
            "diagnostics": [],
            "errors": [],
            "reason": "broker_unavailable",
            "vcs_history": vcs_history,
            "vcs_worktree": vcs_worktree,
            "xref_enabled": bool(xref_enabled),
            "xref": {
                "count": 0,
                "results": [],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 0.0,
                "time_budget_ms": max(1, int(xref_time_budget_ms)),
            },
            "tests": tests_payload,
        }

    result = broker.collect(root=root, candidate_files=candidates, top_n=top_n)
    if xref_enabled:
        result["xref"] = broker.collect_xref(
            root=root,
            query=query,
            candidate_files=candidates,
            top_n=xref_top_n,
            time_budget_ms=xref_time_budget_ms,
        )
    else:
        result["xref"] = {
            "count": 0,
            "results": [],
            "errors": [],
            "budget_exhausted": False,
            "elapsed_ms": 0.0,
            "time_budget_ms": max(1, int(xref_time_budget_ms)),
        }
    result["xref_enabled"] = bool(xref_enabled)
    result["enabled"] = True
    result["tests"] = tests_payload
    result["vcs_history"] = vcs_history
    result["vcs_worktree"] = vcs_worktree
    return result


__all__ = ["SBFL_METRIC_CHOICES", "run_diagnostics_augment"]


