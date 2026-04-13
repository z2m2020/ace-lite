"""Plan Quick CLI Command for ACE-Lite

This module provides a direct CLI entry point for plan_quick functionality,
allowing users to invoke quick planning without needing MCP server access.

PRD-91 P0-5: Direct plan quick CLI entry
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import click

from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.cli_app.output import echo_json
from ace_lite.plan_quick import build_plan_quick

# Help examples for plan quick
PLAN_QUICK_EXAMPLES = """
Examples:
  # Quick planning for a query
  ace-lite plan-quick --query="implement login" --root=.

  # With custom top-k
  ace-lite plan-quick --query="fix auth" --root=. --top-k=5

  # Output as JSON
  ace-lite plan-quick --query="..." --root=. --output-json=quick_plan.json

  # Or use as plan --quick
  ace-lite plan --quick --query="..." --root=.

See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/PLAN_QUICK.md        Plan quick guide
"""


@click.command(
    "plan-quick",
    help="Build a quick source plan using index-based retrieval (no memory/skill stages).",
    epilog=get_help_template("plan-quick"),
)
@click.option(
    "--query",
    required=True,
    help="User query for planning.",
)
@click.option(
    "--root",
    default=".",
    show_default=True,
    help="Repository root path.",
)
@click.option(
    "--top-k",
    default=8,
    type=int,
    show_default=True,
    help="Number of top candidate files to retrieve.",
)
@click.option(
    "--output-json",
    default=None,
    type=str,
    help="Optional path to write the plan payload JSON (UTF-8).",
)
@click.option(
    "--languages",
    default="python,typescript,javascript,go",
    show_default=True,
    help="Comma-separated list of programming languages to index.",
)
@click.option(
    "--tokenizer-model",
    default="gpt-4o-mini",
    show_default=True,
    help="Tokenizer model for token estimation.",
)
@click.option(
    "--verbose/--quiet",
    default=False,
    show_default=True,
    help="Enable verbose output.",
)
def plan_quick_command(
    query: str,
    root: str,
    top_k: int,
    output_json: str | None,
    languages: str,
    tokenizer_model: str,
    verbose: bool,
) -> None:
    """Build a quick source plan using index-based retrieval.

    This command provides a fast path for generating source plans without
    the full pipeline overhead. It's ideal for quick lookups or when
    memory/skill stages are not needed.

    Unlike 'ace-lite plan', this command:
    - Skips memory retrieval stage
    - Skips skills routing stage
    - Uses only index-based candidate retrieval
    - Returns results faster (typically < 5 seconds)

    For full pipeline planning, use 'ace-lite plan' instead.
    """
    # Set up logging
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate parameters
    if top_k < 1 or top_k > 100:
        raise click.BadParameter(
            f"--top-k must be between 1 and 100, got {top_k}",
            param="top-k",
            param_hint="Valid range: 1 to 100",
        )

    # Resolve root path
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise click.BadParameter(
            f"Directory does not exist: {root}",
            param="root",
            param_hint="Provide a valid repository root path",
        )

    # Build plan quick payload
    if verbose:
        click.echo(f"Building quick plan for query: {query}", err=True)
        click.echo(f"Root: {root_path}", err=True)
        click.echo(f"Top-K: {top_k}", err=True)

    try:
        payload = build_plan_quick(
            query=query,
            root=str(root_path),
            top_k_files=top_k,
            languages=languages,
            tokenizer_model=tokenizer_model,
        )
    except Exception as e:
        if verbose:
            raise
        raise click.ClickException(
            f"Failed to build quick plan: {e}\n\n"
            "Hint: Ensure the index exists by running 'ace-lite index --root=.' first"
        ) from e

    # Add metadata
    payload["_plan_quick"] = True
    payload["_cli_invoked"] = True

    # Write output file if specified
    if output_json:
        output_path = Path(output_json).expanduser()
        if not output_path.is_absolute():
            output_path = root_path / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if verbose:
            click.echo(f"Plan written to: {output_path}", err=True)

    # Output payload
    echo_json(payload)


# Also expose as a function for use by plan --quick
def run_plan_quick(
    query: str,
    root: str,
    top_k: int = 8,
    languages: str = "python,typescript,javascript,go",
    tokenizer_model: str = "gpt-4o-mini",
) -> dict:
    """Programmatic entry point for plan_quick.

    This function can be called by other commands (e.g., plan --quick)
    to reuse the plan_quick logic.

    Args:
        query: User query for planning
        root: Repository root path
        top_k: Number of top candidates
        languages: Comma-separated language list
        tokenizer_model: Tokenizer model name

    Returns:
        Plan quick payload dict
    """
    return cast(
        dict[str, Any],
        build_plan_quick(
            query=query,
            root=root,
            top_k_files=top_k,
            languages=languages,
            tokenizer_model=tokenizer_model,
        ),
    )


__all__ = ["plan_quick_command", "run_plan_quick"]
