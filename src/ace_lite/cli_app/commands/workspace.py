"""CLI commands for workspace-level validation and multi-repo planning."""

from __future__ import annotations

from importlib import import_module
import math
from typing import Any, Callable

import click

from ace_lite.cli_app.output import echo_json
from ace_lite.parsers.languages import parse_language_csv


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
        return value
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


@click.group("workspace", help="Workspace-level validation and multi-repo planning.")
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
