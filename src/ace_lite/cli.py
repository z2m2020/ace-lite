"""Backward-compatible CLI entrypoint.

The console script entrypoint remains ``ace_lite.cli:main``. The Click command
tree and most implementation details live in :mod:`ace_lite.cli_app` to keep the
codebase modular and easier to maintain.
"""

from __future__ import annotations

from ace_lite.cli_app.app import cli, main
from ace_lite.cli_app.orchestrator_factory import (
    create_memory_provider,
    create_orchestrator,
    run_plan,
)
from ace_lite.cli_app.params import (
    parse_lsp_command_options,
    parse_lsp_commands_from_config,
)

__all__ = [
    "cli",
    "create_memory_provider",
    "create_orchestrator",
    "main",
    "parse_lsp_command_options",
    "parse_lsp_commands_from_config",
    "run_plan",
]

