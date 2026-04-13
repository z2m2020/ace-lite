"""CLI commands for workspace-level validation and multi-repo planning."""

from __future__ import annotations

import math
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import click

from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.cli_app.output import echo_json
from ace_lite.parsers.languages import parse_language_csv

AGENT_HINTS_START_MARKER = "<!-- AGENT_HINTS_START -->"
AGENT_HINTS_END_MARKER = "<!-- AGENT_HINTS_END -->"
DEFAULT_AGENT_HINTS_SECTION = "\n".join(
    [
        AGENT_HINTS_START_MARKER,
        "## Agent Hints",
        "",
        "- Always read context-map/CONTEXT_REPORT.md first when starting work in this repository",
        "- If context-map/CONTEXT_REPORT.md is missing or stale, regenerate it by running:",
        '  ace-lite plan --context-report-path context-map/CONTEXT_REPORT.md --query "<your query>"',
        "- Follow existing code conventions in this repository",
        "- Use type hints for all function signatures",
        "- Prefer small, focused functions",
        "- Write tests for new functionality",
        AGENT_HINTS_END_MARKER,
    ]
)


def _workspace_module() -> Any:
    try:
        return import_module("ace_lite.workspace")
    except ModuleNotFoundError as exc:
        raise click.ClickException(
            "workspace core module not available: ace_lite.workspace"
        ) from exc


def _workspace_callable(name: str) -> Callable[..., Any]:
    module = _workspace_module()
    value = getattr(module, name, None)
    if callable(value):
        return cast(Callable[..., Any], value)
    raise click.ClickException(f"workspace core function not available: {name}")


def _parse_csv_option(value: str | None, *, option_name: str) -> list[str] | None:
    if value is None:
        return None
    seen: set[str] = set()
    normalized: list[str] = []
    for token in str(value).split(","):
        name = token.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    if not normalized:
        raise click.BadParameter(f"{option_name} cannot be empty", param_hint=option_name)
    return normalized


def _normalize_languages_option(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = parse_language_csv(value)
    if not parsed:
        raise click.BadParameter("--languages cannot be empty", param_hint="--languages")
    return ",".join(parsed)


def _normalize_min_confidence(value: float) -> float:
    threshold = float(value)
    if not math.isfinite(threshold):
        raise click.BadParameter(
            "--min-confidence must be a finite number between 0 and 1",
            param_hint="--min-confidence",
        )
    if threshold < 0.0 or threshold > 1.0:
        raise click.BadParameter(
            "--min-confidence must be between 0 and 1",
            param_hint="--min-confidence",
        )
    return threshold


def _agent_hints_bounds(text: str) -> tuple[int, int] | None:
    start = text.find(AGENT_HINTS_START_MARKER)
    if start < 0:
        return None
    end_marker_start = text.find(AGENT_HINTS_END_MARKER, start + len(AGENT_HINTS_START_MARKER))
    if end_marker_start < 0:
        return None
    end = end_marker_start + len(AGENT_HINTS_END_MARKER)
    if end < len(text) and text[end] == "\r":
        end += 1
    if end < len(text) and text[end] == "\n":
        end += 1
    return start, end


def _has_agent_hints_section(text: str) -> bool:
    return _agent_hints_bounds(text) is not None


def _append_agent_hints_section(text: str) -> str:
    bounds = _agent_hints_bounds(text)
    replacement = f"{DEFAULT_AGENT_HINTS_SECTION}\n"
    if bounds is not None:
        start, end = bounds
        return f"{text[:start]}{replacement}{text[end:]}"
    if not text:
        return replacement
    separator = "\n\n" if not text.endswith("\n") else "\n"
    return f"{text}{separator}{replacement}"


def _remove_agent_hints_section(text: str) -> tuple[str, bool]:
    bounds = _agent_hints_bounds(text)
    if bounds is None:
        return text, False
    start, end = bounds
    return f"{text[:start]}{text[end:]}", True


def _read_agent_hints_target(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"failed to read target {path}: {exc}") from exc
    except UnicodeError as exc:
        raise click.ClickException(f"failed to decode target {path} as UTF-8: {exc}") from exc


def _write_agent_hints_target(path: Path, text: str) -> int:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"failed to write target {path}: {exc}") from exc
    return len(text.encode("utf-8"))


@click.group(
    "workspace",
    help="Workspace-level validation and multi-repo planning.",
    epilog=get_help_template("workspace"),
)
def workspace_group() -> None:
    return None


@workspace_group.command("validate", help="Parse a workspace manifest and print summary JSON.")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(path_type=str),
    help="Path to workspace manifest YAML.",
)
def workspace_validate_command(manifest: str) -> None:
    load_workspace_manifest = _workspace_callable("load_workspace_manifest")
    try:
        manifest_payload = load_workspace_manifest(manifest)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    echo_json(
        {
            "ok": True,
            "workspace": {
                "name": manifest_payload.workspace_name,
                "manifest_path": manifest_payload.manifest_path,
                "repo_count": len(manifest_payload.repos),
            },
            "defaults": dict(manifest_payload.defaults),
            "repos": [
                {
                    "name": repo.name,
                    "root": repo.root,
                    "tags": list(repo.tags),
                    "weight": float(repo.weight),
                }
                for repo in manifest_payload.repos
            ],
        }
    )


@workspace_group.command(
    "install-agent-hints",
    help="Install, preview, or remove an AGENTS.md agent hints section.",
)
@click.option(
    "--target",
    required=True,
    type=click.Path(path_type=str),
    help="Path to the target AGENTS.md file.",
)
@click.option(
    "--mode",
    default="dry-run",
    show_default=True,
    type=click.Choice(["dry-run", "append", "remove"]),
    help="Operation mode for the agent hints section.",
)
def workspace_install_agent_hints_command(target: str, mode: str) -> None:
    target_path = Path(target).expanduser().resolve()
    if not target_path.exists():
        if mode == "dry-run":
            changes_preview = "append mode would create and append the agent hints section"
            echo_json(
                {
                    "ok": True,
                    "mode": "dry-run",
                    "target": str(target_path),
                    "has_existing_section": False,
                    "would_append": True,
                    "would_remove": False,
                    "changes_preview": changes_preview,
                    "file_exists": False,
                }
            )
            return
        if mode == "append":
            next_text = _append_agent_hints_section("")
            bytes_written = _write_agent_hints_target(target_path, next_text)
            echo_json(
                {
                    "ok": True,
                    "mode": "append",
                    "target": str(target_path),
                    "file_updated": True,
                    "bytes_written": bytes_written,
                    "file_created": True,
                }
            )
            return
        echo_json(
            {
                "ok": True,
                "mode": "remove",
                "target": str(target_path),
                "file_exists": False,
                "file_updated": False,
                "bytes_written": 0,
            }
        )
        return

    current_text = _read_agent_hints_target(target_path)
    has_existing_section = _has_agent_hints_section(current_text)

    if mode == "dry-run":
        changes_preview = (
            "append mode would replace the existing agent hints section"
            if has_existing_section
            else "append mode would append the default agent hints section"
        )
        echo_json(
            {
                "ok": True,
                "mode": "dry-run",
                "target": str(target_path),
                "has_existing_section": has_existing_section,
                "would_append": True,
                "would_remove": has_existing_section,
                "changes_preview": changes_preview,
            }
        )
        return

    if mode == "append":
        next_text = _append_agent_hints_section(current_text)
        bytes_written = _write_agent_hints_target(target_path, next_text)
        echo_json(
            {
                "ok": True,
                "mode": "append",
                "target": str(target_path),
                "file_updated": True,
                "bytes_written": bytes_written,
            }
        )
        return

    next_text, file_updated = _remove_agent_hints_section(current_text)
    bytes_written = _write_agent_hints_target(target_path, next_text) if file_updated else 0
    echo_json(
        {
            "ok": True,
            "mode": "remove",
            "target": str(target_path),
            "file_updated": file_updated,
            "bytes_written": bytes_written,
        }
    )


@workspace_group.command(
    "summarize",
    help="Build workspace summary index and emit summary artifact metadata.",
)
@click.option(
    "--manifest",
    required=True,
    type=click.Path(path_type=str),
    help="Path to workspace manifest YAML.",
)
@click.option(
    "--repo-scope",
    default=None,
    help="Comma-separated repo names to scope workspace summary.",
)
@click.option(
    "--languages",
    default=None,
    help="Comma-separated language profile override.",
)
@click.option(
    "--index-cache-path",
    default=None,
    type=click.Path(path_type=str),
    help="Optional per-repo index cache path override.",
)
@click.option(
    "--index-incremental/--no-index-incremental",
    "index_incremental",
    default=None,
    help="Optional incremental index refresh override.",
)
def workspace_summarize_command(
    manifest: str,
    repo_scope: str | None,
    languages: str | None,
    index_cache_path: str | None,
    index_incremental: bool | None,
) -> None:
    summarize_workspace = _workspace_callable("summarize_workspace")
    normalized_languages = _normalize_languages_option(languages)
    normalized_repo_scope = _parse_csv_option(repo_scope, option_name="--repo-scope")

    try:
        payload = summarize_workspace(
            manifest=manifest,
            repo_scope=normalized_repo_scope,
            languages=normalized_languages,
            index_cache_path=index_cache_path,
            index_incremental=index_incremental,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    echo_json(payload)


@workspace_group.command(
    "plan",
    help="Build a workspace plan by routing repos and running per-repo quick plans.",
)
@click.option(
    "--manifest",
    required=True,
    type=click.Path(path_type=str),
    help="Path to workspace manifest YAML.",
)
@click.option("--query", required=True, help="User query for workspace planning.")
@click.option(
    "--top-k-repos",
    default=3,
    show_default=True,
    type=int,
    help="Number of repos selected for planning.",
)
@click.option(
    "--top-k-files",
    default=None,
    type=int,
    help="Override candidate file count per selected repo.",
)
@click.option(
    "--languages",
    default=None,
    help="Comma-separated language profile override.",
)
@click.option(
    "--repo-scope",
    default=None,
    help="Comma-separated repo names to scope workspace routing.",
)
@click.option(
    "--index-cache-path",
    default=None,
    type=click.Path(path_type=str),
    help="Optional plan_quick index cache path override.",
)
@click.option(
    "--index-incremental/--no-index-incremental",
    "index_incremental",
    default=None,
    help="Optional plan_quick index incremental override.",
)
@click.option(
    "--summary-routing/--no-summary-routing",
    "summary_routing",
    default=False,
    show_default=True,
    help="Enable summary-token contribution during repo routing.",
)
@click.option(
    "--evidence-strict/--no-evidence-strict",
    "evidence_strict",
    default=False,
    show_default=True,
    help="Enable strict evidence validation for workspace plan output.",
)
@click.option(
    "--min-confidence",
    default=0.85,
    show_default=True,
    type=float,
    help="Minimum evidence confidence threshold for strict validation.",
)
@click.option(
    "--fail-closed/--no-fail-closed",
    "fail_closed",
    default=False,
    show_default=True,
    help="Fail command when evidence validation does not pass.",
)
def workspace_plan_command(
    manifest: str,
    query: str,
    top_k_repos: int,
    top_k_files: int | None,
    languages: str | None,
    repo_scope: str | None,
    index_cache_path: str | None,
    index_incremental: bool | None,
    summary_routing: bool,
    evidence_strict: bool,
    min_confidence: float,
    fail_closed: bool,
) -> None:
    build_workspace_plan = _workspace_callable("build_workspace_plan")
    normalized_languages = _normalize_languages_option(languages)
    normalized_repo_scope = _parse_csv_option(repo_scope, option_name="--repo-scope")
    normalized_min_confidence = _normalize_min_confidence(min_confidence)

    try:
        payload = build_workspace_plan(
            query=query,
            manifest=manifest,
            top_k_repos=max(1, int(top_k_repos)),
            top_k_files=max(1, int(top_k_files)) if top_k_files is not None else None,
            languages=normalized_languages,
            repo_scope=normalized_repo_scope,
            index_cache_path=index_cache_path,
            index_incremental=index_incremental,
            summary_score_enabled=bool(summary_routing),
            evidence_strict=bool(evidence_strict),
            min_confidence=float(normalized_min_confidence),
            fail_closed=bool(fail_closed),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    echo_json(payload)


@workspace_group.command(
    "benchmark",
    help="Benchmark workspace repo routing against expected repo labels.",
)
@click.option(
    "--manifest",
    required=True,
    type=click.Path(path_type=str),
    help="Path to workspace manifest YAML.",
)
@click.option(
    "--cases-json",
    required=True,
    type=click.Path(path_type=str),
    help="Path to benchmark cases JSON list.",
)
@click.option(
    "--baseline-json",
    default=None,
    type=click.Path(path_type=str),
    help="Optional baseline benchmark JSON used for threshold checks.",
)
@click.option(
    "--top-k-repos",
    default=3,
    show_default=True,
    type=int,
    help="Number of repos selected for each benchmark case.",
)
@click.option(
    "--repo-scope",
    default=None,
    help="Comma-separated repo names to scope benchmark routing.",
)
@click.option(
    "--summary-routing/--no-summary-routing",
    "summary_routing",
    default=False,
    show_default=True,
    help="Enable summary-token contribution during repo routing.",
)
@click.option(
    "--full-plan/--no-full-plan",
    "full_plan",
    default=False,
    show_default=True,
    help="Run full workspace plan per case and report evidence completeness.",
)
@click.option(
    "--fail-on-baseline/--no-fail-on-baseline",
    "fail_on_baseline",
    default=False,
    show_default=True,
    help="Exit with non-zero code when baseline checks fail.",
)
def workspace_benchmark_command(
    manifest: str,
    cases_json: str,
    baseline_json: str | None,
    top_k_repos: int,
    repo_scope: str | None,
    summary_routing: bool,
    full_plan: bool,
    fail_on_baseline: bool,
) -> None:
    run_workspace_benchmark = _workspace_callable("run_workspace_benchmark")
    normalized_repo_scope = _parse_csv_option(repo_scope, option_name="--repo-scope")
    if fail_on_baseline and baseline_json is None:
        raise click.BadParameter(
            "--fail-on-baseline requires --baseline-json",
            param_hint="--fail-on-baseline",
        )

    try:
        payload = run_workspace_benchmark(
            manifest=manifest,
            cases_json=cases_json,
            baseline_json=baseline_json,
            fail_on_baseline=bool(fail_on_baseline),
            top_k_repos=max(1, int(top_k_repos)),
            repo_scope=normalized_repo_scope,
            summary_score_enabled=bool(summary_routing),
            full_plan=bool(full_plan),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    echo_json(payload)


__all__ = ["workspace_group"]
