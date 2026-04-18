"""CLI commands for recording selection feedback used by reranking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.runtime_command_support import DEFAULT_RUNTIME_STATS_DB_PATH
from ace_lite.dev_feedback_runtime_linkage import (
    record_dev_issue_from_runtime_invocation,
)
from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import FeedbackBoostConfig, SelectionFeedbackStore
from ace_lite.feedback_observation_summary import build_feedback_observation_overview
from ace_lite.index_stage.terms import extract_terms
from ace_lite.issue_report_store import IssueReportStore
from ace_lite.memory_long_term import build_long_term_capture_service_from_runtime


@click.group(
    "feedback",
    help="Record and inspect selection feedback for reranking.",
    epilog=get_help_template("feedback"),
)
def feedback_group() -> None:
    return None


def _resolve_root_path(root: str | None) -> str:
    return str(Path(root or Path.cwd()).expanduser().resolve())


def _build_long_term_capture_service(*, root: str | None) -> Any:
    try:
        return build_long_term_capture_service_from_runtime(root=_resolve_root_path(root))
    except Exception:
        return None


def _resolve_feedback_profile_path_cli(*, root: str | None, profile_path: str | None) -> Path:
    base_root = Path(_resolve_root_path(root))
    profile = (
        Path(profile_path).expanduser()
        if profile_path
        else Path("~/.ace-lite/profile.json").expanduser()
    )
    if not profile.is_absolute():
        return (base_root / profile).resolve()
    return profile.resolve()


def _capture_long_term_event(
    *,
    service: Any,
    stage_name: str,
    operation: Any,
) -> dict[str, Any] | None:
    if service is None:
        return None
    try:
        payload = operation()
    except Exception as exc:
        return {
            "ok": False,
            "skipped": False,
            "stage": stage_name,
            "reason": f"capture_failed:{exc.__class__.__name__}",
        }
    return dict(payload) if isinstance(payload, dict) else None


def _load_feedback_events(path: Path) -> tuple[list[dict[str, Any]], str]:
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8")
    if suffix in {".jsonl", ".ndjson"}:
        events: list[dict[str, Any]] = []
        for index, line in enumerate(raw.splitlines(), start=1):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise click.ClickException(
                    f"invalid JSONL at line {index} in {path}: {exc.msg}"
                ) from exc
            if not isinstance(payload, dict):
                raise click.ClickException(
                    f"invalid JSONL at line {index} in {path}: expected an object"
                )
            events.append(payload)
        return events, "jsonl"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"invalid JSON in {path}: {exc.msg}") from exc
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise click.ClickException(f"invalid JSON in {path}: expected a list of objects")
        return list(payload), "json"
    if isinstance(payload, dict):
        events = payload.get("events", [])
        if not isinstance(events, list) or not all(isinstance(item, dict) for item in events):
            raise click.ClickException(
                f"invalid JSON in {path}: expected an 'events' list of objects"
            )
        return list(events), "json"
    raise click.ClickException(f"invalid JSON in {path}: expected an object or list")


def _resolve_output_format(*, output_path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    suffix = output_path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        return "jsonl"
    return "json"


def _write_export_payload(
    *,
    output_path: Path,
    output_format: str,
    payload: dict[str, Any],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "jsonl":
        lines = [json.dumps(event, ensure_ascii=False) for event in payload.get("events", [])]
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_cli_issue_report_workflow_hints(*, repo: str, issue_id: str) -> dict[str, Any]:
    return {
        "workflow": "issue_report_feedback_v1",
        "recommended_next_steps": [
            f"ace-lite feedback list-issues --repo {repo} --status open --limit 20",
            (
                "ace-lite feedback report-dev-issue --repo "
                f"{repo} --title <issue-title> --reason-code general"
            ),
            (
                "ace-lite feedback issue-to-benchmark-case --issue-id "
                f"{issue_id} --comparison-lane issue_report_feedback"
            ),
        ],
        "template_fields": [
            "title",
            "query",
            "actual_behavior",
            "expected_behavior",
            "category",
            "severity",
            "repro_steps",
            "attachments",
        ],
    }


def _build_cli_issue_resolution_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    fix_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "issue_report_resolution_v1",
        "recommended_next_steps": [
            f"ace-lite feedback list-issues --repo {repo} --status resolved --limit 20",
            (
                "ace-lite feedback issue-to-benchmark-case --issue-id "
                f"{issue_id} --comparison-lane dev_feedback_resolution"
            ),
            f"ace-lite feedback dev-feedback-summary --repo {repo}",
        ],
        "linked_fix_id": fix_id,
    }


def _build_cli_dev_issue_workflow_hints(*, repo: str, issue_id: str) -> dict[str, Any]:
    return {
        "workflow": "dev_issue_triage_v1",
        "recommended_next_steps": [
            f"ace-lite feedback dev-feedback-summary --repo {repo}",
            (
                "ace-lite feedback report-dev-fix --repo "
                f"{repo} --issue-id {issue_id} --reason-code general --resolution-note <note>"
            ),
            (
                "ace-lite feedback apply-dev-fix --issue-id "
                f"{issue_id} --fix-id <dev-fix-id> --status fixed"
            ),
        ],
    }


def _build_cli_dev_fix_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    fix_id: str,
) -> dict[str, Any]:
    resolved_issue_id = issue_id or "<dev-issue-id>"
    return {
        "workflow": "dev_fix_linking_v1",
        "recommended_next_steps": [
            (
                "ace-lite feedback apply-dev-fix --issue-id "
                f"{resolved_issue_id} --fix-id {fix_id} --status fixed"
            ),
            f"ace-lite feedback dev-feedback-summary --repo {repo}",
        ],
    }


def _build_cli_dev_summary_workflow_hints(
    *,
    repo: str | None,
    summary: dict[str, Any],
    observation_overview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_repo = str(repo or "").strip() or "<repo>"
    issue_count = int(summary.get("issue_count", 0) or 0)
    open_issue_count = int(summary.get("open_issue_count", 0) or 0)
    observation = dict(observation_overview or {})
    issue_reports = dict(observation.get("issue_reports", {}))
    selection_feedback = dict(observation.get("selection_feedback", {}))
    cross_store_gaps = dict(observation.get("cross_store_gaps", {}))
    issue_report_open_count = int(issue_reports.get("open_issue_count", 0) or 0)
    selection_event_count = int(selection_feedback.get("event_count", 0) or 0)
    if issue_count <= 0 and issue_report_open_count > 0:
        return {
            "workflow": "dev_feedback_issue_bridge_v1",
            "recommended_next_steps": [
                f"ace-lite feedback list-issues --repo {normalized_repo} --status open --limit 20",
                (
                    "ace-lite feedback report-dev-issue --repo "
                    f"{normalized_repo} --title <issue-title> --reason-code general"
                ),
            ],
        }
    if issue_count <= 0:
        return {
            "workflow": "dev_feedback_bootstrap_v1",
            "recommended_next_steps": [
                (
                    "ace-lite feedback report-dev-issue --repo "
                    f"{normalized_repo} --title <issue-title> --reason-code general"
                ),
                (
                    "ace-lite feedback report-dev-issue-from-runtime "
                    "--invocation-id <runtime-invocation-id>"
                ),
            ],
        }
    if open_issue_count > 0:
        return {
            "workflow": "dev_feedback_closure_v1",
            "recommended_next_steps": [
                (
                    "ace-lite feedback report-dev-fix --repo "
                    f"{normalized_repo} --issue-id <open-issue-id> "
                    "--reason-code general --resolution-note <note>"
                ),
                (
                    "ace-lite feedback apply-dev-fix --issue-id <open-issue-id> "
                    "--fix-id <dev-fix-id> --status fixed"
                ),
            ],
        }
    if selection_event_count > 0 or int(
        cross_store_gaps.get("issue_report_without_dev_issue_count", 0) or 0
    ) > 0:
        return {
            "workflow": "feedback_observability_v1",
            "recommended_next_steps": [
                f"ace-lite feedback dev-feedback-summary --repo {normalized_repo}",
                f"ace-lite feedback list-issues --repo {normalized_repo} --limit 20",
            ],
        }
    return {
        "workflow": "dev_feedback_maintenance_v1",
        "recommended_next_steps": [
            f"ace-lite feedback dev-feedback-summary --repo {normalized_repo}",
        ],
    }


def _build_cli_runtime_issue_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    invocation_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "runtime_issue_promotion_v1",
        "recommended_next_steps": [
            (
                "ace-lite feedback report-dev-fix --repo "
                f"{repo} --issue-id {issue_id} --related-invocation-id {invocation_id} "
                "--reason-code general --resolution-note <note>"
            ),
            (
                "ace-lite feedback apply-dev-fix --issue-id "
                f"{issue_id} --fix-id <dev-fix-id> --status fixed"
            ),
        ],
    }


def _build_cli_dev_issue_resolution_workflow_hints(
    *,
    repo: str,
    issue_id: str,
    fix_id: str,
) -> dict[str, Any]:
    return {
        "workflow": "dev_issue_resolution_v1",
        "recommended_next_steps": [
            f"ace-lite feedback dev-feedback-summary --repo {repo}",
            (
                "ace-lite feedback resolve-issue-from-dev-fix --issue-id "
                f"{issue_id} --fix-id {fix_id} --status resolved"
            ),
        ],
    }


@feedback_group.command("record", help="Record a selection feedback event.")
@click.argument("selected_path")
@click.option("--query", required=True, help="Query text associated with the selection.")
@click.option("--repo", required=True, help="Repository identifier (feedback partition key).")
@click.option(
    "--position",
    default=None,
    type=int,
    help="Optional 1-based rank position selected (for analysis only).",
)
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Feedback store path. Legacy profile JSON paths are still accepted for compatibility.",
)
@click.option(
    "--max-entries",
    default=512,
    show_default=True,
    type=int,
    help="Maximum stored feedback events (newest kept).",
)
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to convert absolute selected paths into repo-relative paths.",
)
@click.option("--user-id", default=None, help="Optional user scope stored with the feedback event.")
@click.option(
    "--profile-key",
    default=None,
    help="Optional runtime profile scope stored with the feedback event.",
)
@click.option(
    "--candidate-path",
    "candidate_paths",
    multiple=True,
    help="Optional shortlisted candidate path. Repeat to attach the quick shortlist used before selecting the final path.",
)
def feedback_record_command(
    selected_path: str,
    query: str,
    repo: str,
    position: int | None,
    profile_path: str,
    max_entries: int,
    root: str | None,
    user_id: str | None,
    profile_key: str | None,
    candidate_paths: tuple[str, ...],
) -> None:
    long_term_capture_service = _build_long_term_capture_service(root=root)
    store = SelectionFeedbackStore(
        profile_path=_resolve_feedback_profile_path_cli(
            root=root,
            profile_path=profile_path,
        ),
        max_entries=max(0, int(max_entries)),
        long_term_capture_service=long_term_capture_service,
    )
    payload = store.record(
        query=query,
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        selected_path=selected_path,
        candidate_paths=candidate_paths,
        position=position,
        root_path=root,
    )
    echo_json(payload)


@feedback_group.command("stats", help="Summarize stored feedback and computed boosts.")
@click.option(
    "--repo",
    default=None,
    help="Optional repo filter (defaults to all repos in the store).",
)
@click.option(
    "--query",
    default=None,
    help="Optional query to compute term-gated boost stats (mirrors rerank gating).",
)
@click.option(
    "--boost-per-select",
    default=0.15,
    show_default=True,
    type=float,
    help="Boost added per matching selection (before decay/cap).",
)
@click.option(
    "--max-boost",
    default=0.6,
    show_default=True,
    type=float,
    help="Hard cap for total boost per path.",
)
@click.option(
    "--decay-days",
    default=60.0,
    show_default=True,
    type=float,
    help="Half-life days for selection decay.",
)
@click.option(
    "--top-n",
    default=10,
    show_default=True,
    type=int,
    help="Number of paths to return.",
)
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Feedback store path. Legacy profile JSON paths are still accepted for compatibility.",
)
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to resolve relative feedback store paths.",
)
@click.option("--user-id", default=None, help="Optional user filter.")
@click.option("--profile-key", default=None, help="Optional profile filter.")
@click.option(
    "--max-entries",
    default=512,
    show_default=True,
    type=int,
    help="Maximum stored feedback events considered.",
)
def feedback_stats_command(
    repo: str | None,
    query: str | None,
    boost_per_select: float,
    max_boost: float,
    decay_days: float,
    top_n: int,
    profile_path: str,
    root: str | None,
    user_id: str | None,
    profile_key: str | None,
    max_entries: int,
) -> None:
    resolved_profile_path = _resolve_feedback_profile_path_cli(
        root=root,
        profile_path=profile_path,
    )
    store = SelectionFeedbackStore(
        profile_path=resolved_profile_path,
        max_entries=max(0, int(max_entries)),
    )
    query_terms: list[str] | None = None
    normalized_query = str(query or "").strip()
    if normalized_query:
        query_terms = extract_terms(query=normalized_query, memory_stage={})
    payload = store.stats(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        query_terms=query_terms,
        boost=FeedbackBoostConfig(
            boost_per_select=max(0.0, float(boost_per_select)),
            max_boost=max(0.0, float(max_boost)),
            decay_days=max(0.0, float(decay_days)),
        ),
        top_n=max(1, int(top_n)),
    )
    echo_json(payload)


@feedback_group.command("export", help="Export stored feedback events for offline replay.")
@click.option(
    "--repo",
    default=None,
    help="Optional repo filter (defaults to all repos in the store).",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="File to write (`.json` or `.jsonl`).",
)
@click.option(
    "--format",
    "output_format",
    default="auto",
    show_default=True,
    type=click.Choice(["auto", "json", "jsonl"], case_sensitive=False),
    help="Export format. `auto` uses the output file extension.",
)
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Feedback store path. Legacy profile JSON paths are still accepted for compatibility.",
)
@click.option("--user-id", default=None, help="Optional user filter.")
@click.option("--profile-key", default=None, help="Optional profile filter.")
@click.option(
    "--max-entries",
    default=512,
    show_default=True,
    type=int,
    help="Maximum stored feedback events considered.",
)
def feedback_export_command(
    repo: str | None,
    output_path: Path,
    output_format: str,
    profile_path: str,
    user_id: str | None,
    profile_key: str | None,
    max_entries: int,
) -> None:
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=max(0, int(max_entries)))
    payload = store.export(repo=repo, user_id=user_id, profile_key=profile_key)
    resolved_format = _resolve_output_format(
        output_path=output_path,
        requested=str(output_format).lower(),
    )
    _write_export_payload(
        output_path=output_path,
        output_format=resolved_format,
        payload=payload,
    )
    echo_json(
        {
            "ok": True,
            "output_path": str(output_path),
            "output_format": resolved_format,
            "repo_filter": payload.get("repo_filter"),
            "event_count": int(payload.get("event_count", 0) or 0),
        }
    )


@feedback_group.command("replay", help="Replay exported feedback events into a profile.")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Input file produced by `feedback export` (`.json` or `.jsonl`).",
)
@click.option(
    "--repo",
    default=None,
    help="Optional repo override applied when replayed events omit `repo`.",
)
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to convert absolute selected paths into repo-relative paths.",
)
@click.option(
    "--reset/--no-reset",
    default=False,
    show_default=True,
    help="Reset the existing feedback store before replaying the input events.",
)
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Feedback store path. Legacy profile JSON paths are still accepted for compatibility.",
)
@click.option("--user-id", default=None, help="Optional user override for replayed events.")
@click.option(
    "--profile-key",
    default=None,
    help="Optional profile override for replayed events.",
)
@click.option(
    "--max-entries",
    default=512,
    show_default=True,
    type=int,
    help="Maximum stored feedback events retained after replay.",
)
def feedback_replay_command(
    input_path: Path,
    repo: str | None,
    root: str | None,
    reset: bool,
    profile_path: str,
    user_id: str | None,
    profile_key: str | None,
    max_entries: int,
) -> None:
    events, input_format = _load_feedback_events(input_path)
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=max(0, int(max_entries)))
    payload = store.replay(
        events=events,
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        root_path=root,
        reset=reset,
    )
    payload["input_path"] = str(input_path)
    payload["input_format"] = input_format
    echo_json(payload)


@feedback_group.command("reset", help="Remove all stored feedback events.")
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Feedback store path. Legacy profile JSON paths are still accepted for compatibility.",
)
def feedback_reset_command(profile_path: str) -> None:
    store = SelectionFeedbackStore(profile_path=profile_path)
    echo_json(store.reset())


@feedback_group.command("report-issue", help="Record a structured issue report.")
@click.option("--title", required=True, help="Short issue title.")
@click.option("--query", required=True, help="Query associated with the issue.")
@click.option("--repo", required=True, help="Repository identifier.")
@click.option(
    "--actual-behavior",
    required=True,
    help="Observed behavior that should be fixed.",
)
@click.option("--expected-behavior", default=None, help="Optional expected behavior.")
@click.option("--category", default="general", show_default=True, help="Issue category.")
@click.option("--severity", default="medium", show_default=True, help="Issue severity.")
@click.option("--status", default="open", show_default=True, help="Issue status.")
@click.option("--user-id", default=None, help="Optional user scope.")
@click.option("--profile-key", default=None, help="Optional runtime profile scope.")
@click.option("--selected-path", default=None, help="Optional selected file path.")
@click.option("--plan-payload-ref", default=None, help="Optional linked plan/run reference.")
@click.option(
    "--repro-step",
    "repro_steps",
    multiple=True,
    help="Repeatable repro step.",
)
@click.option(
    "--attachment",
    "attachments",
    multiple=True,
    help="Repeatable attachment reference.",
)
@click.option("--occurred-at", default=None, help="Optional ISO-8601 occurrence timestamp.")
@click.option("--resolved-at", default=None, help="Optional ISO-8601 resolution timestamp.")
@click.option("--resolution-note", default=None, help="Optional resolution note.")
@click.option("--issue-id", default=None, help="Optional stable issue identifier.")
@click.option("--root", default=".", show_default=True, help="Repository root.")
@click.option(
    "--store-path",
    default="context-map/issue_reports.db",
    show_default=True,
    help="Issue report SQLite path.",
)
def feedback_report_issue_command(
    title: str,
    query: str,
    repo: str,
    actual_behavior: str,
    expected_behavior: str | None,
    category: str,
    severity: str,
    status: str,
    user_id: str | None,
    profile_key: str | None,
    selected_path: str | None,
    plan_payload_ref: str | None,
    repro_steps: tuple[str, ...],
    attachments: tuple[str, ...],
    occurred_at: str | None,
    resolved_at: str | None,
    resolution_note: str | None,
    issue_id: str | None,
    root: str,
    store_path: str,
) -> None:
    root_path = Path(root).expanduser().resolve()
    target_store_path = Path(store_path).expanduser()
    if not target_store_path.is_absolute():
        target_store_path = (root_path / target_store_path).resolve()
    store = IssueReportStore(db_path=target_store_path)
    report = store.record(
        {
            "issue_id": issue_id,
            "title": title,
            "query": query,
            "repo": repo,
            "root": str(root_path),
            "user_id": user_id,
            "profile_key": profile_key,
            "category": category,
            "severity": severity,
            "status": status,
            "expected_behavior": expected_behavior,
            "actual_behavior": actual_behavior,
            "repro_steps": list(repro_steps),
            "selected_path": selected_path,
            "plan_payload_ref": plan_payload_ref,
            "attachments": list(attachments),
            "occurred_at": occurred_at,
            "resolved_at": resolved_at,
            "resolution_note": resolution_note,
        },
        root_path=root_path,
    )
    report_payload = report.to_payload()
    echo_json(
        {
            "ok": True,
            "root": str(root_path),
            "repo": repo,
            "store_path": str(store.db_path),
            "report": report_payload,
            "workflow_hints": _build_cli_issue_report_workflow_hints(
                repo=repo,
                issue_id=str(report_payload.get("issue_id") or ""),
            ),
        }
    )


@feedback_group.command("list-issues", help="List stored issue reports.")
@click.option("--repo", default=None, help="Optional repo filter.")
@click.option("--user-id", default=None, help="Optional user filter.")
@click.option("--profile-key", default=None, help="Optional profile filter.")
@click.option("--status", default=None, help="Optional status filter.")
@click.option("--category", default=None, help="Optional category filter.")
@click.option("--severity", default=None, help="Optional severity filter.")
@click.option("--root", default=".", show_default=True, help="Repository root.")
@click.option(
    "--store-path",
    default="context-map/issue_reports.db",
    show_default=True,
    help="Issue report SQLite path.",
)
@click.option("--limit", default=20, show_default=True, type=int, help="Maximum rows.")
def feedback_list_issues_command(
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    status: str | None,
    category: str | None,
    severity: str | None,
    root: str,
    store_path: str,
    limit: int,
) -> None:
    root_path = Path(root).expanduser().resolve()
    target_store_path = Path(store_path).expanduser()
    if not target_store_path.is_absolute():
        target_store_path = (root_path / target_store_path).resolve()
    store = IssueReportStore(db_path=target_store_path)
    reports = store.list_reports(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        status=status,
        category=category,
        severity=severity,
        limit=max(1, int(limit)),
    )
    echo_json(
        {
            "ok": True,
            "root": str(root_path),
            "repo": repo,
            "store_path": str(store.db_path),
            "count": len(reports),
            "reports": [item.to_payload() for item in reports],
        }
    )


@feedback_group.command("issue-to-benchmark-case", help="Export an issue report as a benchmark case YAML entry.")
@click.option("--issue-id", required=True, help="Issue report identifier.")
@click.option("--root", default=".", show_default=True, help="Repository root.")
@click.option(
    "--store-path",
    default="context-map/issue_reports.db",
    show_default=True,
    help="Issue report SQLite path.",
)
@click.option(
    "--output",
    "output_path",
    default="benchmark/cases/feedback_issue_reports.yaml",
    show_default=True,
    help="Benchmark case YAML output path.",
)
@click.option("--case-id", default=None, help="Optional explicit benchmark case id.")
@click.option(
    "--comparison-lane",
    default="issue_report_feedback",
    show_default=True,
    help="Benchmark comparison lane name.",
)
@click.option("--top-k", default=8, show_default=True, type=int, help="Benchmark top-k.")
@click.option(
    "--min-validation-tests",
    default=1,
    show_default=True,
    type=int,
    help="Minimum validation tests for task_success.",
)
@click.option("--append/--replace", default=True, show_default=True, help="Append into existing YAML or replace it.")
def feedback_issue_to_benchmark_case_command(
    issue_id: str,
    root: str,
    store_path: str,
    output_path: str,
    case_id: str | None,
    comparison_lane: str,
    top_k: int,
    min_validation_tests: int,
    append: bool,
) -> None:
    root_path = Path(root).expanduser().resolve()
    target_store_path = Path(store_path).expanduser()
    if not target_store_path.is_absolute():
        target_store_path = (root_path / target_store_path).resolve()
    target_output_path = Path(output_path).expanduser()
    if not target_output_path.is_absolute():
        target_output_path = (root_path / target_output_path).resolve()
    store = IssueReportStore(db_path=target_store_path)
    payload = store.export_case(
        issue_id=issue_id,
        output_path=target_output_path,
        case_id=case_id,
        comparison_lane=comparison_lane,
        top_k=top_k,
        min_validation_tests=min_validation_tests,
        append=append,
    )
    echo_json({"ok": True, "root": str(root_path), "store_path": str(store.db_path), **payload})


@feedback_group.command("resolve-issue-from-dev-fix", help="Apply a stored dev fix to an issue report resolution.")
@click.option("--issue-id", required=True, help="Issue report identifier.")
@click.option("--fix-id", required=True, help="Developer fix identifier.")
@click.option("--root", default=".", show_default=True, help="Repository root.")
@click.option(
    "--issue-store-path",
    default="context-map/issue_reports.db",
    show_default=True,
    help="Issue report SQLite path.",
)
@click.option(
    "--dev-feedback-path",
    default="~/.ace-lite/dev_feedback.db",
    show_default=True,
    help="Developer feedback SQLite path.",
)
@click.option("--status", default="resolved", show_default=True, help="Resolved issue status.")
@click.option("--resolved-at", default=None, help="Optional ISO-8601 resolution timestamp.")
def feedback_resolve_issue_from_dev_fix_command(
    issue_id: str,
    fix_id: str,
    root: str,
    issue_store_path: str,
    dev_feedback_path: str,
    status: str,
    resolved_at: str | None,
) -> None:
    root_path = Path(root).expanduser().resolve()
    target_issue_store_path = Path(issue_store_path).expanduser()
    if not target_issue_store_path.is_absolute():
        target_issue_store_path = (root_path / target_issue_store_path).resolve()
    issue_store = IssueReportStore(db_path=target_issue_store_path)
    dev_store = DevFeedbackStore(db_path=dev_feedback_path)
    fix = dev_store.get_fix(fix_id)
    if fix is None:
        raise click.ClickException(f"Developer fix not found: {fix_id}")
    report = issue_store.resolve_with_fix(
        issue_id=issue_id,
        fix=fix,
        resolved_at=resolved_at,
        status=status,
    )
    report_payload = report.to_payload()
    fix_payload = fix.to_payload()
    echo_json(
        {
            "ok": True,
            "root": str(root_path),
            "issue_store_path": str(issue_store.db_path),
            "dev_feedback_path": str(dev_store.db_path),
            "report": report_payload,
            "fix": fix_payload,
            "workflow_hints": _build_cli_issue_resolution_workflow_hints(
                repo=str(report_payload.get("repo") or ""),
                issue_id=str(report_payload.get("issue_id") or issue_id),
                fix_id=str(fix_payload.get("fix_id") or fix_id),
            ),
        }
    )


@feedback_group.command("report-dev-issue", help="Record a developer-side issue for runtime triage.")
@click.option("--title", required=True, help="Short developer issue title.")
@click.option("--reason-code", required=True, help="Normalized pain / fallback reason code.")
@click.option("--repo", required=True, help="Repository identifier.")
@click.option("--status", default="open", show_default=True, help="Issue status.")
@click.option("--user-id", default=None, help="Optional user scope.")
@click.option("--profile-key", default=None, help="Optional runtime profile scope.")
@click.option("--query", default=None, help="Optional query associated with the issue.")
@click.option("--selected-path", default=None, help="Optional selected path.")
@click.option("--related-invocation-id", default=None, help="Optional linked invocation id.")
@click.option("--notes", default=None, help="Optional free-form issue notes.")
@click.option("--created-at", default=None, help="Optional ISO-8601 creation timestamp.")
@click.option("--updated-at", default=None, help="Optional ISO-8601 update timestamp.")
@click.option("--resolved-at", default=None, help="Optional ISO-8601 resolution timestamp.")
@click.option("--issue-id", default=None, help="Optional stable issue id.")
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to resolve runtime config for long-term capture.",
)
@click.option(
    "--store-path",
    default="~/.ace-lite/dev_feedback.db",
    show_default=True,
    help="Developer feedback SQLite path.",
)
def feedback_report_dev_issue_command(
    title: str,
    reason_code: str,
    repo: str,
    status: str,
    user_id: str | None,
    profile_key: str | None,
    query: str | None,
    selected_path: str | None,
    related_invocation_id: str | None,
    notes: str | None,
    created_at: str | None,
    updated_at: str | None,
    resolved_at: str | None,
    issue_id: str | None,
    root: str | None,
    store_path: str,
) -> None:
    store = DevFeedbackStore(db_path=store_path)
    issue = store.record_issue(
        {
            "issue_id": issue_id,
            "title": title,
            "reason_code": reason_code,
            "status": status,
            "repo": repo,
            "user_id": user_id,
            "profile_key": profile_key,
            "query": query,
            "selected_path": selected_path,
            "related_invocation_id": related_invocation_id,
            "notes": notes,
            "created_at": created_at,
            "updated_at": updated_at,
            "resolved_at": resolved_at,
        }
    )
    issue_payload = issue.to_payload()
    long_term_capture_service = _build_long_term_capture_service(root=root)
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_issue",
        operation=lambda: long_term_capture_service.capture_dev_issue(
            issue=issue_payload,
            root=_resolve_root_path(root),
        ),
    )
    echo_json(
        {
            "ok": True,
            "store_path": str(store.db_path),
            "issue": issue_payload,
            "long_term_capture": long_term_capture,
            "workflow_hints": _build_cli_dev_issue_workflow_hints(
                repo=str(issue_payload.get("repo") or repo),
                issue_id=str(issue_payload.get("issue_id") or ""),
            ),
        }
    )


@feedback_group.command("report-dev-fix", help="Record a developer-side fix or mitigation.")
@click.option("--reason-code", required=True, help="Normalized pain / fallback reason code.")
@click.option("--repo", required=True, help="Repository identifier.")
@click.option("--resolution-note", required=True, help="Fix or mitigation summary.")
@click.option("--user-id", default=None, help="Optional user scope.")
@click.option("--profile-key", default=None, help="Optional runtime profile scope.")
@click.option("--issue-id", default=None, help="Optional linked dev issue id.")
@click.option("--query", default=None, help="Optional query associated with the fix.")
@click.option("--selected-path", default=None, help="Optional selected path.")
@click.option("--related-invocation-id", default=None, help="Optional linked invocation id.")
@click.option("--created-at", default=None, help="Optional ISO-8601 creation timestamp.")
@click.option("--fix-id", default=None, help="Optional stable fix id.")
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to resolve runtime config for long-term capture.",
)
@click.option(
    "--store-path",
    default="~/.ace-lite/dev_feedback.db",
    show_default=True,
    help="Developer feedback SQLite path.",
)
def feedback_report_dev_fix_command(
    reason_code: str,
    repo: str,
    resolution_note: str,
    user_id: str | None,
    profile_key: str | None,
    issue_id: str | None,
    query: str | None,
    selected_path: str | None,
    related_invocation_id: str | None,
    created_at: str | None,
    fix_id: str | None,
    root: str | None,
    store_path: str,
) -> None:
    store = DevFeedbackStore(db_path=store_path)
    fix = store.record_fix(
        {
            "fix_id": fix_id,
            "issue_id": issue_id,
            "reason_code": reason_code,
            "repo": repo,
            "user_id": user_id,
            "profile_key": profile_key,
            "query": query,
            "selected_path": selected_path,
            "related_invocation_id": related_invocation_id,
            "resolution_note": resolution_note,
            "created_at": created_at,
        }
    )
    fix_payload = fix.to_payload()
    long_term_capture_service = _build_long_term_capture_service(root=root)
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_fix",
        operation=lambda: long_term_capture_service.capture_dev_fix(
            fix=fix_payload,
            root=_resolve_root_path(root),
        ),
    )
    echo_json(
        {
            "ok": True,
            "store_path": str(store.db_path),
            "fix": fix_payload,
            "long_term_capture": long_term_capture,
            "workflow_hints": _build_cli_dev_fix_workflow_hints(
                repo=str(fix_payload.get("repo") or repo),
                issue_id=str(fix_payload.get("issue_id") or ""),
                fix_id=str(fix_payload.get("fix_id") or ""),
            ),
        }
    )


@feedback_group.command(
    "apply-dev-fix",
    help="Apply a stored developer fix to a developer-side issue resolution.",
)
@click.option("--issue-id", required=True, help="Developer issue identifier.")
@click.option("--fix-id", required=True, help="Developer fix identifier.")
@click.option(
    "--store-path",
    default="~/.ace-lite/dev_feedback.db",
    show_default=True,
    help="Developer feedback SQLite path.",
)
@click.option("--status", default="fixed", show_default=True, help="Resolved issue status.")
@click.option("--resolved-at", default=None, help="Optional ISO-8601 resolution timestamp.")
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to resolve runtime config for long-term capture.",
)
def feedback_apply_dev_fix_command(
    issue_id: str,
    fix_id: str,
    store_path: str,
    status: str,
    resolved_at: str | None,
    root: str | None,
) -> None:
    store = DevFeedbackStore(db_path=store_path)
    issue = store.apply_fix(
        issue_id=issue_id,
        fix_id=fix_id,
        status=status,
        resolved_at=resolved_at,
    )
    fix = store.get_fix(fix_id)
    if fix is None:
        raise click.ClickException(f"Developer fix not found: {fix_id}")
    issue_payload = issue.to_payload()
    fix_payload = fix.to_payload()
    long_term_capture_service = _build_long_term_capture_service(root=root)
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_issue_resolution",
        operation=lambda: long_term_capture_service.capture_dev_issue_resolution(
            issue=issue_payload,
            fix=fix_payload,
            root=_resolve_root_path(root),
        ),
    )
    echo_json(
        {
            "ok": True,
            "store_path": str(store.db_path),
            "issue": issue_payload,
            "fix": fix_payload,
            "long_term_capture": long_term_capture,
            "workflow_hints": _build_cli_dev_issue_resolution_workflow_hints(
                repo=str(issue_payload.get("repo") or ""),
                issue_id=str(issue_payload.get("issue_id") or issue_id),
                fix_id=str(fix_payload.get("fix_id") or fix_id),
            ),
        }
    )


@feedback_group.command("dev-feedback-summary", help="Summarize stored developer issues and fixes.")
@click.option("--repo", default=None, help="Optional repo filter.")
@click.option("--user-id", default=None, help="Optional user filter.")
@click.option("--profile-key", default=None, help="Optional profile filter.")
@click.option(
    "--root",
    default=".",
    show_default=True,
    help="Repo root used to resolve issue report store.",
)
@click.option(
    "--issue-store-path",
    default=None,
    help="Optional issue report SQLite path override.",
)
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Selection feedback store path used for unified observation summary.",
)
@click.option(
    "--store-path",
    default="~/.ace-lite/dev_feedback.db",
    show_default=True,
    help="Developer feedback SQLite path.",
)
def feedback_dev_feedback_summary_command(
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    root: str,
    issue_store_path: str | None,
    profile_path: str,
    store_path: str,
) -> None:
    store = DevFeedbackStore(db_path=store_path)
    summary_payload = store.summarize(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
    )
    observation_overview = build_feedback_observation_overview(
        repo=repo,
        user_id=user_id,
        profile_key=profile_key,
        root=root,
        dev_feedback_store_path=store_path,
        issue_store_path=issue_store_path,
        profile_path=profile_path,
    )
    echo_json(
        {
            "ok": True,
            "store_path": str(store.db_path),
            "summary": summary_payload,
            "observation_overview": observation_overview,
            "workflow_hints": _build_cli_dev_summary_workflow_hints(
                repo=repo,
                summary=summary_payload,
                observation_overview=observation_overview,
            ),
        }
    )


@feedback_group.command(
    "report-dev-issue-from-runtime",
    help="Promote an auto-captured runtime event into a developer-side issue.",
)
@click.option("--invocation-id", required=True, help="Runtime invocation id to promote.")
@click.option("--reason-code", default=None, help="Optional degraded reason override.")
@click.option("--title", default=None, help="Optional developer issue title override.")
@click.option("--notes", default=None, help="Optional extra notes appended to auto notes.")
@click.option("--status", default="open", show_default=True, help="Issue status.")
@click.option("--user-id", default=None, help="Optional user scope.")
@click.option("--profile-key", default=None, help="Optional profile scope override.")
@click.option("--issue-id", default=None, help="Optional stable issue id.")
@click.option(
    "--root",
    default=None,
    help="Optional repo root used to resolve runtime config for long-term capture.",
)
@click.option(
    "--stats-db-path",
    default=DEFAULT_RUNTIME_STATS_DB_PATH,
    show_default=True,
    help="Runtime stats SQLite path used for auto-captured invocation lookup.",
)
@click.option(
    "--store-path",
    default="~/.ace-lite/dev_feedback.db",
    show_default=True,
    help="Developer feedback SQLite path.",
)
def feedback_report_dev_issue_from_runtime_command(
    invocation_id: str,
    reason_code: str | None,
    title: str | None,
    notes: str | None,
    status: str,
    user_id: str | None,
    profile_key: str | None,
    issue_id: str | None,
    root: str | None,
    stats_db_path: str,
    store_path: str,
) -> None:
    issue, invocation, resolved_store_path, resolved_stats_db_path = (
        record_dev_issue_from_runtime_invocation(
            invocation_id=invocation_id,
            stats_db_path=stats_db_path,
            store_path=store_path,
            reason_code=reason_code,
            title=title,
            notes=notes,
            status=status,
            user_id=user_id,
            profile_key=profile_key,
            issue_id=issue_id,
        )
    )
    issue_payload = issue.to_payload()
    invocation_payload = invocation.to_payload()
    long_term_capture_service = _build_long_term_capture_service(root=root)
    long_term_capture = _capture_long_term_event(
        service=long_term_capture_service,
        stage_name="dev_issue",
        operation=lambda: long_term_capture_service.capture_dev_issue(
            issue=issue_payload,
            root=_resolve_root_path(root),
        ),
    )
    echo_json(
        {
            "ok": True,
            "store_path": resolved_store_path,
            "stats_db_path": resolved_stats_db_path,
            "issue": issue_payload,
            "invocation": invocation_payload,
            "long_term_capture": long_term_capture,
            "workflow_hints": _build_cli_runtime_issue_workflow_hints(
                repo=str(issue_payload.get("repo") or ""),
                issue_id=str(issue_payload.get("issue_id") or ""),
                invocation_id=str(invocation_payload.get("invocation_id") or invocation_id),
            ),
        }
    )


__all__ = ["feedback_group"]
