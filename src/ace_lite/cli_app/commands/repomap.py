from __future__ import annotations

import click

from ace_lite.cli_app.config_resolve import _load_command_config, _resolve_from_config
from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.params import _to_csv_languages, _to_int
from ace_lite.indexer import build_index
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.repomap.builder import write_repo_map
from ace_lite.repomap.ranking import RANKING_PROFILES


@click.group(
    "repomap",
    help="Build prompt-friendly repository map outputs.",
    epilog=get_help_template("repomap"),
)
def repomap_group() -> None:
    pass


@repomap_group.command("build", help="Generate RepoMap JSON and Markdown from current index.")
@click.option(
    "--root",
    required=True,
    type=click.Path(path_type=str),
    help="Repository root path.",
)
@click.option(
    "--languages",
    default="python,typescript,javascript,go",
    show_default=True,
    help="Comma-separated language profile.",
)
@click.option(
    "--output-json",
    default="context-map/repo_map.json",
    show_default=True,
    type=click.Path(path_type=str),
    help="RepoMap JSON output path.",
)
@click.option(
    "--output-md",
    default="context-map/repo_map.md",
    show_default=True,
    type=click.Path(path_type=str),
    help="RepoMap Markdown output path.",
)
@click.option(
    "--budget-tokens",
    default=800,
    show_default=True,
    type=int,
    help="Token budget for RepoMap Markdown output.",
)
@click.option(
    "--top-k",
    default=40,
    show_default=True,
    type=int,
    help="Top-ranked files to consider before budget cutoff.",
)
@click.option(
    "--ranking-profile",
    default="heuristic",
    show_default=True,
    type=click.Choice(list(RANKING_PROFILES), case_sensitive=False),
    help="RepoMap ranking profile.",
)
@click.pass_context
def repomap_build_command(
    ctx: click.Context,
    root: str,
    languages: str,
    output_json: str,
    output_md: str,
    budget_tokens: int,
    top_k: int,
    ranking_profile: str,
) -> None:
    config = _load_command_config(root)
    tokenizer_model = str(config.get("tokenizer", {}).get("model", "")).strip()

    languages = _resolve_from_config(
        ctx=ctx,
        param_name="languages",
        current=languages,
        config=config,
        paths=[("repomap", "languages"), ("languages",)],
        transform=_to_csv_languages,
    )
    output_json = _resolve_from_config(
        ctx=ctx,
        param_name="output_json",
        current=output_json,
        config=config,
        paths=[("repomap", "output_json")],
        transform=str,
    )
    output_md = _resolve_from_config(
        ctx=ctx,
        param_name="output_md",
        current=output_md,
        config=config,
        paths=[("repomap", "output_md")],
        transform=str,
    )
    budget_tokens = _resolve_from_config(
        ctx=ctx,
        param_name="budget_tokens",
        current=budget_tokens,
        config=config,
        paths=[("repomap", "budget_tokens")],
        transform=_to_int,
    )
    top_k = _resolve_from_config(
        ctx=ctx,
        param_name="top_k",
        current=top_k,
        config=config,
        paths=[("repomap", "top_k")],
        transform=_to_int,
    )
    ranking_profile = _resolve_from_config(
        ctx=ctx,
        param_name="ranking_profile",
        current=ranking_profile,
        config=config,
        paths=[("repomap", "ranking_profile")],
        transform=lambda value: str(value).strip().lower(),
    )

    index_payload = build_index(root, languages=parse_language_csv(languages))
    outputs = write_repo_map(
        index_payload=index_payload,
        output_json=output_json,
        output_md=output_md,
        budget_tokens=max(1, int(budget_tokens)),
        top_k=max(0, int(top_k)),
        ranking_profile=ranking_profile,
        tokenizer_model=tokenizer_model or None,
    )
    echo_json(outputs)


__all__ = ["repomap_group"]
