from __future__ import annotations

import sys

import click

from ace_lite.cli_app.commands import runtime as runtime_module


@click.command("doctor", help="Grouped runtime diagnostics (alias for `runtime doctor`).")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--config-file",
    default=".ace-lite.yml",
    show_default=True,
    help="Config filename in layered lookup.",
)
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
    "--runtime-profile",
    default=None,
    type=click.Choice(list(runtime_module.RUNTIME_PROFILE_NAMES), case_sensitive=False),
    help="Apply a first-party runtime profile before explicit runtime settings overrides.",
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
@click.option(
    "--current-path",
    default=runtime_module.DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    show_default=True,
    help="User-scope persisted runtime settings snapshot path.",
)
@click.option(
    "--last-known-good-path",
    default=runtime_module.DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
    show_default=True,
    help="User-scope last-known-good runtime settings snapshot path.",
)
@click.option(
    "--stats-db-path",
    default=runtime_module.DEFAULT_RUNTIME_STATS_DB_PATH,
    show_default=True,
    help="User-scope durable runtime stats SQLite path.",
)
@click.option(
    "--user-id",
    default="",
    help="Optional user_id filter for preference capture summary.",
)
@click.option(
    "--cache-db-path",
    default="",
    help="Optional stage artifact cache SQLite override path.",
)
@click.option(
    "--payload-root",
    default="",
    help="Optional stage artifact payload root override path.",
)
@click.option(
    "--temp-root",
    default="",
    help="Optional stage artifact temp payload root override path.",
)
@click.option(
    "--record-runtime-event/--no-record-runtime-event",
    default=False,
    show_default=True,
    help="Persist doctor degraded reasons as a synthetic runtime invocation in durable stats.",
)
def doctor_command(
    root: str,
    config_file: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
    current_path: str,
    last_known_good_path: str,
    stats_db_path: str,
    user_id: str,
    cache_db_path: str,
    payload_root: str,
    temp_root: str,
    record_runtime_event: bool,
) -> None:
    runtime_module.runtime_doctor_command.callback(
        root=root,
        config_file=config_file,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        require_memory=require_memory,
        probe_endpoints=probe_endpoints,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
        stats_db_path=stats_db_path,
        user_id=user_id,
        cache_db_path=cache_db_path,
        payload_root=payload_root,
        temp_root=temp_root,
        record_runtime_event=record_runtime_event,
    )


__all__ = ["doctor_command"]
