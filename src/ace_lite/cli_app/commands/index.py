from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.progress import echo_progress, echo_done, clear_progress
from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.index_cache import build_or_refresh_index
from ace_lite.indexer import build_index
from ace_lite.indexing_resilience import (
    IndexingResilienceConfig,
    build_index_with_resilience,
)
from ace_lite.parsers.languages import parse_language_csv


@click.command("index", help="Build distilled project index and save as JSON.", epilog=get_help_template("index"))
@click.option(
    "--root",
    required=True,
    type=click.Path(path_type=str),
    help="Repository root path.",
)
@click.option(
    "--progress/--no-progress",
    default=True,
    show_default=True,
    help="Show progress indicators during indexing.",
)
@click.option(
    "--languages",
    default="python,typescript,javascript,go,rust,java,c,cpp,c_sharp,ruby,php,markdown",
    show_default=True,
    help="Comma-separated language profile.",
)
@click.option(
    "--output",
    default="context-map/index.json",
    show_default=True,
    type=click.Path(path_type=str),
    help="Output JSON file for distilled index.",
)
@click.option(
    "--incremental/--no-incremental",
    "incremental",
    default=True,
    show_default=True,
    help="Reuse and incrementally refresh an existing on-disk index when possible.",
)
@click.option(
    "--batch-mode/--no-batch-mode",
    "batch_mode",
    default=False,
    show_default=True,
    help="Enable batch mode with resume-state checkpointing.",
)
@click.option(
    "--batch-size",
    default=200,
    show_default=True,
    type=int,
    help="Files per checkpoint batch when batch mode is enabled.",
)
@click.option(
    "--timeout-per-file",
    default=0.0,
    show_default=True,
    type=float,
    help="Soft per-file timeout seconds (0 disables).",
)
@click.option(
    "--resume/--no-resume",
    "resume",
    default=False,
    show_default=True,
    help="Resume a previous batch-mode indexing run using resume state.",
)
@click.option(
    "--resume-state",
    default="context-map/index.resume.json",
    show_default=True,
    type=click.Path(path_type=str),
    help="Resume state JSON path (relative to --root if not absolute).",
)
@click.option(
    "--retry-timeouts/--no-retry-timeouts",
    "retry_timeouts",
    default=False,
    show_default=True,
    help="Retry timed-out files once with a relaxed timeout multiplier.",
)
@click.option(
    "--subprocess-batch/--no-subprocess-batch",
    "subprocess_batch",
    default=False,
    show_default=True,
    help="Process each batch in a subprocess to reduce peak memory (off by default).",
)
@click.option(
    "--subprocess-batch-timeout",
    default=0.0,
    show_default=True,
    type=float,
    help="Optional hard timeout seconds per batch subprocess (0 disables).",
)
def index_command(
    root: str,
    progress: bool,
    languages: str,
    output: str,
    incremental: bool,
    batch_mode: bool,
    batch_size: int,
    timeout_per_file: float,
    resume: bool,
    resume_state: str,
    retry_timeouts: bool,
    subprocess_batch: bool,
    subprocess_batch_timeout: float,
) -> None:
    progress = bool(progress and sys.stderr.isatty())
    enabled_languages = parse_language_csv(languages)
    effective_batch_mode = bool(
        batch_mode
        or resume
        or retry_timeouts
        or subprocess_batch
        or float(timeout_per_file or 0.0) > 0.0
        or float(subprocess_batch_timeout or 0.0) > 0.0
    )

    if progress:
        click.echo("Building index...", err=True)
        if incremental:
            echo_progress("Checking existing index...")
        else:
            echo_progress("Scanning files...")

    cache_info: dict[str, object] | None = None
    if effective_batch_mode:
        config = IndexingResilienceConfig(
            batch_size=int(batch_size),
            timeout_per_file_seconds=float(timeout_per_file or 0.0) or None,
            resume=bool(resume),
            resume_state_path=Path(resume_state),
            retry_timeouts=bool(retry_timeouts),
            subprocess_batch=bool(subprocess_batch),
            subprocess_batch_timeout_seconds=float(subprocess_batch_timeout or 0.0) or None,
        )
        if progress:
            echo_progress("Indexing with resilience mode...")
        payload = build_index_with_resilience(
            root,
            languages=enabled_languages,
            config=config,
        )
    else:
        output_path = Path(output)
        cache_path = output_path
        if not cache_path.is_absolute():
            cache_path = Path(root) / cache_path
        if progress:
            echo_progress("Building index cache...")
        payload, cache_info = build_or_refresh_index(
            root_dir=root,
            cache_path=str(cache_path),
            languages=enabled_languages,
            incremental=bool(incremental),
        )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if progress:
        clear_progress()
        file_count = int(payload.get("file_count") or 0)
        echo_done(f"Index built ({file_count} files)")

    echo_json(
        {
            "ok": True,
            "output": str(output_path),
            "file_count": int(payload.get("file_count") or 0),
            "indexing_resilience": payload.get("indexing_resilience"),
            "index_cache": cache_info,
        }
    )


__all__ = ["index_command"]
