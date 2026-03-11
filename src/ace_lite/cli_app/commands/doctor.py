from __future__ import annotations

import sys

import click

from ace_lite.cli_app.commands import runtime as runtime_module


@click.command("doctor", help="Environment and MCP self-test checks (alias for `runtime doctor-mcp`).")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--skills-dir",
    default="",
    help="Optional skills directory passed to MCP self-test.",
)
@click.option(
    "--python-executable",
    default=sys.executable,
    show_default=True,
    help="Python executable used to launch MCP self-test.",
)
@click.option(
    "--timeout-seconds",
    default=15.0,
    type=float,
    show_default=True,
    help="Timeout for MCP self-test and endpoint probes.",
)
@click.option(
    "--mcp-name",
    default="ace-lite",
    show_default=True,
    help="MCP server name for loading saved env snapshot.",
)
@click.option(
    "--use-snapshot/--no-use-snapshot",
    default=True,
    show_default=True,
    help="Load env snapshot from context-map/mcp/<name>.env.json when present.",
)
@click.option(
    "--require-memory/--allow-no-memory",
    default=False,
    show_default=True,
    help="Fail when memory is not configured or all configured endpoints fail.",
)
@click.option(
    "--probe-endpoints/--no-probe-endpoints",
    default=True,
    show_default=True,
    help="Probe configured MCP/REST memory endpoints.",
)
def doctor_command(
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
) -> None:
    runtime_module.runtime_doctor_mcp_command.callback(
        root=root,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        require_memory=require_memory,
        probe_endpoints=probe_endpoints,
    )


__all__ = ["doctor_command"]
