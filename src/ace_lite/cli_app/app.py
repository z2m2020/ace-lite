"""CLI application entrypoint.

The public package entrypoint remains ``ace_lite.cli:main``; this module
contains the actual Click command tree implementation.
"""

from __future__ import annotations

import logging

import click

from ace_lite.cli_app.commands.benchmark import benchmark_group
from ace_lite.cli_app.commands.demo import demo_command
from ace_lite.cli_app.commands.doctor import doctor_command
from ace_lite.cli_app.commands.feedback import feedback_group
from ace_lite.cli_app.commands.index import index_command
from ace_lite.cli_app.commands.memory import memory_group
from ace_lite.cli_app.commands.plan import plan_command
from ace_lite.cli_app.commands.profile import profile_group
from ace_lite.cli_app.commands.repomap import repomap_group
from ace_lite.cli_app.commands.runtime import runtime_group
from ace_lite.cli_app.commands.workspace import workspace_group
from ace_lite.version import get_version


@click.group(help="ACE-Lite command line interface.")
@click.version_option(version=get_version(), prog_name="ace-lite")
def cli() -> None:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s %(message)s"
    )


cli.add_command(plan_command)
cli.add_command(index_command)
cli.add_command(repomap_group)
cli.add_command(benchmark_group)
cli.add_command(demo_command)
cli.add_command(feedback_group)
cli.add_command(profile_group)
cli.add_command(memory_group)
cli.add_command(runtime_group)
cli.add_command(doctor_command)
cli.add_command(workspace_group)


def main() -> None:
    cli(prog_name="ace-lite")


__all__ = ["cli", "main"]
