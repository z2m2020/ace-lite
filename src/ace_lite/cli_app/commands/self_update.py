from __future__ import annotations

import sys

import click

from ace_lite.cli_app import self_update_support
from ace_lite.cli_app.output import echo_json


@click.command(
    "self-update",
    help="Check or apply the recommended ACE-Lite update flow for the current install mode.",
)
@click.option(
    "--root",
    default=".",
    show_default=True,
    help="Repository root for editable/source-checkout installs.",
)
@click.option(
    "--python-executable",
    default=sys.executable,
    show_default=True,
    help="Python executable used to run update commands.",
)
@click.option(
    "--skip-git-pull",
    is_flag=True,
    help="When using scripts/update.py, skip git pull and only resync the install.",
)
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Print the resolved update plan without executing it.",
)
def self_update_command(
    root: str,
    python_executable: str,
    skip_git_pull: bool,
    check_only: bool,
) -> None:
    payload = self_update_support.run_self_update(
        root=root,
        python_executable=python_executable,
        skip_git_pull=skip_git_pull,
        check=check_only,
    )
    echo_json(payload)
    if not bool(payload.get("ok", False)) and not check_only:
        raise click.exceptions.Exit(1)


__all__ = ["self_update_command"]
