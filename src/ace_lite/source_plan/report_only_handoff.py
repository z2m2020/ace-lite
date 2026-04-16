from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from ace_lite.report_signals import normalize_signal_paths, normalize_signal_texts

_HANDOFF_NOTE_LOCK = Lock()


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
            [_str(item).strip() for item in _list(review.get("watch_items")) if _str(item).strip()][
                :3
            ]
        )
    if _int(findings.get("blocker_count")) > 0:
        next_actions.append("Resolve blocker-level validation findings before applying changes.")
        risks.append("validation_blockers_present")
    elif _int(findings.get("warn_count")) > 0:
        next_actions.append("Review warning-level validation findings before widening the patch.")
    if validation_tests:
        next_actions.append("Run the suggested validation tests after editing the focus files.")
    if _int(history.get("hit_count")) > 0:
        next_actions.append(
            "Check the recent matching commits before repeating the same change pattern."
        )
    if diagnostics:
        risks.append("augment_diagnostics_present")
    if not next_actions:
        next_actions.append("Open the top focus file and inspect the first prioritized chunk.")

    return {
        "schema_version": "session_end_report_v1",
        "goal": _str(query).strip(),
        "focus_paths": normalize_signal_paths(focused_files, limit=5),
        "validation_tests": normalize_signal_texts(validation_tests, limit=5),
        "next_actions": normalize_signal_texts(next_actions, limit=5),
        "risks": normalize_signal_texts(risks, limit=5),
        "history_context_present": _int(history.get("hit_count")) > 0,
        "validation_status": _str(findings.get("status")).strip() or "skipped",
    }


def build_handoff_payload(
    *,
    query: str,
    candidate_review: dict[str, Any] | None,
    validation_findings: dict[str, Any] | None,
    session_end_report: dict[str, Any] | None,
) -> dict[str, Any]:
    review = _dict(candidate_review)
    findings = _dict(validation_findings)
    session = _dict(session_end_report)

    unresolved: list[str] = []
    unresolved.extend(normalize_signal_texts(_list(findings.get("message_samples"))))
    unresolved.extend(normalize_signal_texts(_list(review.get("watch_items"))))

    return {
        "schema_version": "handoff_payload_v1",
        "goal": _str(query).strip(),
        "assumptions": [],
        "unresolved": normalize_signal_texts(unresolved, limit=5),
        "next_tasks": normalize_signal_texts(_list(session.get("next_actions")), limit=5),
        "risks": normalize_signal_texts(_list(session.get("risks")), limit=5),
        "verify": normalize_signal_texts(_list(session.get("validation_tests")), limit=5),
        "rollback": ["Use session_end_report_v1 as the compatibility fallback."],
        "focus_paths": normalize_signal_paths(_list(session.get("focus_paths")), limit=5),
        "validation_status": _str(session.get("validation_status")).strip() or "skipped",
    }


def render_handoff_payload_markdown(handoff_payload: dict[str, Any] | None) -> str:
    payload = _dict(handoff_payload)
    lines = ["# Handoff Payload", ""]
    lines.append(f"- Goal: {_str(payload.get('goal')).strip() or '(unspecified)'}")
    lines.append(
        f"- Validation status: {_str(payload.get('validation_status')).strip() or 'skipped'}"
    )
    focus_paths = normalize_signal_paths(_list(payload.get("focus_paths")), limit=5)
    next_tasks = normalize_signal_texts(_list(payload.get("next_tasks")), limit=5)
    unresolved = normalize_signal_texts(_list(payload.get("unresolved")), limit=5)
    verify = normalize_signal_texts(_list(payload.get("verify")), limit=5)
    risks = normalize_signal_texts(_list(payload.get("risks")), limit=5)

    def append_section(title: str, rows: list[str]) -> None:
        if not rows:
            return
        lines.extend(["", f"## {title}"])
        lines.extend([f"- {item}" for item in rows])

    append_section("Focus Paths", focus_paths)
    append_section("Next Tasks", next_tasks)
    append_section("Unresolved", unresolved)
    append_section("Verify", verify)
    append_section("Risks", risks)
    lines.extend(
        ["", f"*Schema: {_str(payload.get('schema_version')).strip() or 'handoff_payload_v1'}*"]
    )
    return "\n".join(lines)


def _resolve_repo_output_path(*, root: str, output_path: str | Path) -> Path:
    target = Path(output_path).expanduser()
    if target.is_absolute():
        return target.resolve()
    return (Path(root) / target).resolve()


def write_handoff_payload_artifacts(
    handoff_payload: dict[str, Any] | None,
    output_dir: str | Path,
    *,
    root: str,
) -> dict[str, Any]:
    payload = _dict(handoff_payload)
    base = _resolve_repo_output_path(root=root, output_path=output_dir)
    base.mkdir(parents=True, exist_ok=True)

    json_path = base / "handoff_payload.json"
    markdown_path = base / "handoff_payload.md"

    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    markdown_text = render_handoff_payload_markdown(payload)

    json_path.write_text(json_text, encoding="utf-8")
    markdown_path.write_text(markdown_text, encoding="utf-8")

    return {
        "schema_version": "handoff_payload_artifacts_v1",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "focus_path_count": len(normalize_signal_paths(_list(payload.get("focus_paths")))),
        "next_task_count": len(normalize_signal_texts(_list(payload.get("next_tasks")))),
        "ok": True,
    }


def build_handoff_payload_note(
    *,
    query: str,
    repo: str,
    handoff_payload: dict[str, Any] | None,
    namespace: str | None = None,
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    payload = _dict(handoff_payload)
    goal = _str(payload.get("goal")).strip() or _str(query).strip()
    next_tasks = normalize_signal_texts(_list(payload.get("next_tasks")), limit=5)
    unresolved = normalize_signal_texts(_list(payload.get("unresolved")), limit=5)
    focus_paths = normalize_signal_paths(_list(payload.get("focus_paths")), limit=5)
    verify = normalize_signal_texts(_list(payload.get("verify")), limit=5)
    text_parts = [f"handoff: {goal}"]
    if next_tasks:
        text_parts.append("next: " + "; ".join(next_tasks))
    if focus_paths:
        text_parts.append("focus: " + "; ".join(focus_paths))
    if unresolved:
        text_parts.append("unresolved: " + "; ".join(unresolved))
    if verify:
        text_parts.append("verify: " + "; ".join(verify))
    return {
        "text": " | ".join(text_parts),
        "query": _str(query).strip(),
        "repo": _str(repo).strip(),
        "namespace": _str(namespace).strip() or None,
        "tags": ["handoff", "source_plan", "report_only"],
        "source": "handoff_payload_v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "artifact_refs": normalize_signal_texts(artifact_refs or [], limit=5),
        "handoff_payload": payload,
    }


def append_handoff_payload_note(
    *,
    notes_path: str | Path,
    query: str,
    repo: str,
    handoff_payload: dict[str, Any] | None,
    namespace: str | None = None,
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    path = Path(notes_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    note = build_handoff_payload_note(
        query=query,
        repo=repo,
        handoff_payload=handoff_payload,
        namespace=namespace,
        artifact_refs=artifact_refs,
    )
    with _HANDOFF_NOTE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(note, ensure_ascii=False))
            fh.write("\n")
    return {
        "schema_version": "handoff_payload_note_v1",
        "notes_path": str(path),
        "namespace": note.get("namespace"),
        "ok": True,
    }


__all__ = [
    "append_handoff_payload_note",
    "build_handoff_payload",
    "build_handoff_payload_note",
    "build_session_end_report",
    "render_handoff_payload_markdown",
    "write_handoff_payload_artifacts",
]
