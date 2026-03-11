"""CLI commands for recording selection feedback used by reranking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from ace_lite.cli_app.output import echo_json
from ace_lite.feedback_store import FeedbackBoostConfig, SelectionFeedbackStore
from ace_lite.index_stage.terms import extract_terms


@click.group("feedback", help="Record and inspect selection feedback for reranking.")
def feedback_group() -> None:
    return None


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
    help="Path to local profile JSON file (feedback stored under preferences).",
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
def feedback_record_command(
    selected_path: str,
    query: str,
    repo: str,
    position: int | None,
    profile_path: str,
    max_entries: int,
    root: str | None,
) -> None:
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=max(0, int(max_entries)))
    payload = store.record(
        query=query,
        repo=repo,
        selected_path=selected_path,
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
    help="Path to local profile JSON file (feedback stored under preferences).",
)
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
    max_entries: int,
) -> None:
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=max(0, int(max_entries)))
    query_terms: list[str] | None = None
    normalized_query = str(query or "").strip()
    if normalized_query:
        query_terms = extract_terms(query=normalized_query, memory_stage={})
    payload = store.stats(
        repo=repo,
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
    help="Path to local profile JSON file (feedback stored under preferences).",
)
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
    max_entries: int,
) -> None:
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=max(0, int(max_entries)))
    payload = store.export(repo=repo)
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
    help="Path to local profile JSON file (feedback stored under preferences).",
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
    max_entries: int,
) -> None:
    events, input_format = _load_feedback_events(input_path)
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=max(0, int(max_entries)))
    payload = store.replay(
        events=events,
        repo=repo,
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
    help="Path to local profile JSON file (feedback stored under preferences).",
)
def feedback_reset_command(profile_path: str) -> None:
    store = SelectionFeedbackStore(profile_path=profile_path)
    echo_json(store.reset())


__all__ = ["feedback_group"]
