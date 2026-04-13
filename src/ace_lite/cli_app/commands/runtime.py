"""Long-running runtime commands (hot-reload + scheduler)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click

from ace_lite.cli_app.output import echo_json
from ace_lite.cli_app.runtime_command_support import (
    DEFAULT_RUNTIME_STATS_DB_PATH,
    build_codex_mcp_setup_plan,
    build_runtime_cache_doctor_payload,
    build_runtime_cache_vacuum_payload,
    build_runtime_doctor_payload,
    collect_runtime_mcp_doctor_payload,
    collect_runtime_mcp_self_test_payload,
    collect_runtime_settings_persist_payload,
    collect_runtime_settings_show_payload,
    collect_runtime_status_payload,
    execute_codex_mcp_setup_plan,
    load_runtime_stats_summary,
)
from ace_lite.cli_app.runtime_doctor_support import persist_runtime_doctor_invocation
from ace_lite.cli_app.runtime_mcp_ops import (
    extract_memory_channels as _extract_memory_channels,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    load_mcp_env_snapshot as _load_mcp_env_snapshot,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    mcp_env_snapshot_path as _mcp_env_snapshot_path,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    memory_channels_disabled as _memory_channels_disabled,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    memory_config_recommendations as _memory_config_recommendations,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    resolve_cli_path as _resolve_cli_path,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    run_mcp_self_test as _run_mcp_self_test,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    write_mcp_env_snapshot as _write_mcp_env_snapshot,
)
from ace_lite.config import find_git_root, load_layered_config
from ace_lite.config_models import validate_cli_config
from ace_lite.runtime import ConfigWatcher, TaskScheduler
from ace_lite.runtime_profiles import RUNTIME_PROFILE_NAMES
from ace_lite.runtime_settings_store import (
    DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
)


def _layered_config_paths(*, root: str, config_file: str) -> list[Path]:
    root_path = Path(root).resolve()
    repo_root = find_git_root(root_path) or root_path
    paths = [
        (Path.home() / config_file).resolve(),
        (repo_root / config_file).resolve(),
        (Path.cwd().resolve() / config_file).resolve(),
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _load_and_validate(*, root: str, config_file: str) -> dict[str, Any]:
    raw = load_layered_config(root_dir=root, cwd=Path.cwd(), filename=config_file)
    meta = raw.get("_meta")
    payload = dict(raw)
    payload.pop("_meta", None)
    try:
        validated = validate_cli_config(payload)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if isinstance(meta, dict):
        validated["_meta"] = meta
    return validated


def _runtime_scheduler_section(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    scheduler = runtime.get("scheduler", {})
    return scheduler if isinstance(scheduler, dict) else {}


@click.group("runtime", help="Run service-mode utilities (hot-reload, scheduler).")
def runtime_group() -> None:
    return None


@runtime_group.group("settings", help="Inspect effective runtime settings.")
def runtime_settings_group() -> None:
    return None


@runtime_group.group("cache", help="Inspect and clean stage artifact cache data.")
def runtime_cache_group() -> None:
    return None


@runtime_settings_group.command("show")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--config-file",
    default=".ace-lite.yml",
    show_default=True,
    help="Config filename in layered lookup.",
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
    type=click.Choice(list(RUNTIME_PROFILE_NAMES), case_sensitive=False),
    help="Apply a first-party runtime profile before explicit runtime settings overrides.",
)
@click.option(
    "--use-snapshot/--no-use-snapshot",
    default=True,
    show_default=True,
    help="Load env snapshot from context-map/mcp/<name>.env.json when present.",
)
@click.option(
    "--current-path",
    default=DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    show_default=True,
    help="User-scope persisted runtime settings snapshot path.",
)
@click.option(
    "--last-known-good-path",
    default=DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
    show_default=True,
    help="User-scope last-known-good runtime settings snapshot path.",
)
def runtime_settings_show_command(
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
) -> None:
    echo_json(
        collect_runtime_settings_show_payload(
            root=root,
            config_file=config_file,
            mcp_name=mcp_name,
            runtime_profile=runtime_profile,
            use_snapshot=use_snapshot,
            current_path=current_path,
            last_known_good_path=last_known_good_path,
            snapshot_path_fn=_mcp_env_snapshot_path,
            load_snapshot_fn=_load_mcp_env_snapshot,
        )
    )


@runtime_settings_group.command("persist")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--config-file",
    default=".ace-lite.yml",
    show_default=True,
    help="Config filename in layered lookup.",
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
    type=click.Choice(list(RUNTIME_PROFILE_NAMES), case_sensitive=False),
    help="Apply a first-party runtime profile before explicit runtime settings overrides.",
)
@click.option(
    "--use-snapshot/--no-use-snapshot",
    default=True,
    show_default=True,
    help="Load env snapshot from context-map/mcp/<name>.env.json when present.",
)
@click.option(
    "--current-path",
    default=DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    show_default=True,
    help="User-scope persisted runtime settings snapshot path.",
)
@click.option(
    "--last-known-good-path",
    default=DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
    show_default=True,
    help="User-scope last-known-good runtime settings snapshot path.",
)
@click.option(
    "--update-last-known-good/--no-update-last-known-good",
    default=False,
    show_default=True,
    help="Also promote the resolved runtime settings snapshot to last-known-good.",
)
def runtime_settings_persist_command(
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    update_last_known_good: bool,
) -> None:
    echo_json(
        collect_runtime_settings_persist_payload(
            root=root,
            config_file=config_file,
            mcp_name=mcp_name,
            runtime_profile=runtime_profile,
            use_snapshot=use_snapshot,
            current_path=current_path,
            last_known_good_path=last_known_good_path,
            update_last_known_good=update_last_known_good,
            snapshot_path_fn=_mcp_env_snapshot_path,
            load_snapshot_fn=_load_mcp_env_snapshot,
        )
    )


@runtime_group.command("stats")
@click.option(
    "--repo",
    default="",
    help="Optional repo filter. Defaults to the latest repo in the stats DB.",
)
@click.option(
    "--profile",
    default="",
    help="Optional profile filter.",
)
@click.option(
    "--user-id",
    default="",
    help="Optional user_id filter for preference capture summary.",
)
@click.option(
    "--db-path",
    default=DEFAULT_RUNTIME_STATS_DB_PATH,
    show_default=True,
    help="User-scope durable runtime stats SQLite path.",
)
def runtime_stats_command(repo: str, profile: str, user_id: str, db_path: str) -> None:
    echo_json(
        {
            "ok": True,
            "event": "runtime_stats",
            **load_runtime_stats_summary(
                db_path=db_path,
                repo_key=repo,
                profile_key=profile,
                user_id=user_id,
                home_path=os.environ.get("HOME")
                or os.environ.get("USERPROFILE")
                or Path.home(),
            ),
        }
    )


@runtime_group.command("status")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--config-file",
    default=".ace-lite.yml",
    show_default=True,
    help="Config filename in layered lookup.",
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
    type=click.Choice(list(RUNTIME_PROFILE_NAMES), case_sensitive=False),
    help="Apply a first-party runtime profile before explicit runtime settings overrides.",
)
@click.option(
    "--use-snapshot/--no-use-snapshot",
    default=True,
    show_default=True,
    help="Load env snapshot from context-map/mcp/<name>.env.json when present.",
)
@click.option(
    "--current-path",
    default=DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    show_default=True,
    help="User-scope persisted runtime settings snapshot path.",
)
@click.option(
    "--last-known-good-path",
    default=DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
    show_default=True,
    help="User-scope last-known-good runtime settings snapshot path.",
)
@click.option(
    "--db-path",
    default=DEFAULT_RUNTIME_STATS_DB_PATH,
    show_default=True,
    help="User-scope durable runtime stats SQLite path.",
)
@click.option(
    "--user-id",
    default="",
    help="Optional user_id filter for preference capture summary.",
)
def runtime_status_command(
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    db_path: str,
    user_id: str,
) -> None:
    echo_json(
        collect_runtime_status_payload(
            root=root,
            config_file=config_file,
            mcp_name=mcp_name,
            runtime_profile=runtime_profile,
            use_snapshot=use_snapshot,
            current_path=current_path,
            last_known_good_path=last_known_good_path,
            db_path=db_path,
            user_id=user_id,
            extract_memory_channels_fn=_extract_memory_channels,
            memory_channels_disabled_fn=_memory_channels_disabled,
            memory_config_recommendations_fn=_memory_config_recommendations,
            snapshot_path_fn=_mcp_env_snapshot_path,
            load_snapshot_fn=_load_mcp_env_snapshot,
        )
    )


@runtime_group.command("watch-config")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--config-file",
    default=".ace-lite.yml",
    show_default=True,
    help="Config filename in layered lookup.",
)
@click.option(
    "--poll-interval-seconds",
    default=1.0,
    type=float,
    show_default=True,
    help="Polling interval in seconds.",
)
@click.option(
    "--debounce-ms",
    default=300,
    type=int,
    show_default=True,
    help="Debounce window for file-change events.",
)
@click.option(
    "--max-polls",
    default=0,
    type=int,
    show_default=True,
    help="Max poll iterations (0 means run indefinitely).",
)
@click.option(
    "--fail-on-invalid/--no-fail-on-invalid",
    default=True,
    show_default=True,
    help="Exit non-zero when reloaded config is invalid.",
)
def runtime_watch_config_command(
    root: str,
    config_file: str,
    poll_interval_seconds: float,
    debounce_ms: int,
    max_polls: int,
    fail_on_invalid: bool,
) -> None:
    paths = _layered_config_paths(root=root, config_file=config_file)
    watchers = [
        ConfigWatcher(path=path, debounce_ms=max(0, int(debounce_ms))) for path in paths
    ]
    for watcher in watchers:
        watcher.start()

    total_polls = max(0, int(max_polls))
    poll_index = 0
    emitted_events = 0

    while total_polls <= 0 or poll_index < total_polls:
        poll_index += 1
        changes = [change for watcher in watchers if (change := watcher.poll())]
        if changes:
            try:
                config = _load_and_validate(root=root, config_file=config_file)
                payload = {
                    "ok": True,
                    "event": "config_reloaded",
                    "poll": poll_index,
                    "changes": [
                        {
                            "path": item.path,
                            "exists": item.exists,
                            "mtime_ns": item.mtime_ns,
                            "size_bytes": item.size_bytes,
                            "sha256": item.sha256,
                            "generation": item.generation,
                        }
                        for item in changes
                    ],
                    "loaded_files": list(
                        config.get("_meta", {}).get("loaded_files", [])
                        if isinstance(config.get("_meta"), dict)
                        else []
                    ),
                }
                echo_json(payload)
                emitted_events += 1
            except Exception as exc:
                payload = {
                    "ok": False,
                    "event": "config_reloaded",
                    "poll": poll_index,
                    "error": str(exc),
                }
                echo_json(payload)
                if fail_on_invalid:
                    raise click.ClickException(str(exc)) from exc

        if total_polls > 0 and poll_index >= total_polls:
            break
        time.sleep(max(0.0, float(poll_interval_seconds)))

    echo_json(
        {
            "ok": True,
            "event": "watch_finished",
            "polls": poll_index,
            "reload_events": emitted_events,
        }
    )


@runtime_group.command("run-scheduler")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--config-file",
    default=".ace-lite.yml",
    show_default=True,
    help="Config filename in layered lookup.",
)
@click.option(
    "--max-ticks",
    default=1,
    type=int,
    show_default=True,
    help="Number of scheduler ticks to execute.",
)
@click.option(
    "--tick-interval-seconds",
    default=1.0,
    type=float,
    show_default=True,
    help="Tick interval in seconds.",
)
@click.option(
    "--simulate-clock/--real-clock",
    default=True,
    show_default=True,
    help="Use simulated time advancement between ticks.",
)
@click.option(
    "--start-at",
    default="",
    help="Optional ISO-8601 UTC time for simulated run start.",
)
def runtime_run_scheduler_command(
    root: str,
    config_file: str,
    max_ticks: int,
    tick_interval_seconds: float,
    simulate_clock: bool,
    start_at: str,
) -> None:
    config = _load_and_validate(root=root, config_file=config_file)
    scheduler_cfg = _runtime_scheduler_section(config)
    scheduler_enabled = bool(scheduler_cfg.get("enabled", False))
    heartbeat_cfg = scheduler_cfg.get("heartbeat", {})
    if not isinstance(heartbeat_cfg, dict):
        heartbeat_cfg = {}
    heartbeat_enabled = bool(heartbeat_cfg.get("enabled", False))
    heartbeat_interval = float(heartbeat_cfg.get("interval_seconds", 60.0))
    heartbeat_run_on_start = bool(heartbeat_cfg.get("run_on_start", True))
    cron_items = scheduler_cfg.get("cron", [])
    if not isinstance(cron_items, list):
        cron_items = []

    if not scheduler_enabled:
        echo_json({"ok": True, "event": "scheduler_disabled"})
        return

    scheduler = TaskScheduler()
    emitted_runs: list[dict[str, Any]] = []

    def _emit_action(task_name: str, trigger_at: datetime) -> None:
        emitted_runs.append(
            {
                "task": task_name,
                "trigger_at": trigger_at.isoformat(),
            }
        )

    if heartbeat_enabled:
        scheduler.add_heartbeat_task(
            name="heartbeat",
            interval_seconds=max(0.1, heartbeat_interval),
            action=_emit_action,
            run_on_start=heartbeat_run_on_start,
            enabled=True,
        )

    for item in cron_items:
        if not isinstance(item, dict):
            continue
        enabled = bool(item.get("enabled", True))
        if not enabled:
            continue
        name = str(item.get("name") or "").strip()
        schedule = str(item.get("schedule") or "").strip()
        if not name or not schedule:
            continue
        scheduler.add_cron_task(
            name=name,
            cron=schedule,
            action=_emit_action,
            enabled=True,
        )

    ticks = max(1, int(max_ticks))
    interval = max(0.0, float(tick_interval_seconds))
    now = datetime.now(timezone.utc)
    if start_at:
        try:
            parsed = datetime.fromisoformat(start_at)
            now = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(
                tzinfo=timezone.utc
            )
        except ValueError as exc:
            raise click.BadParameter(f"Invalid --start-at value: {start_at}") from exc

    reports: list[dict[str, Any]] = []
    for _ in range(ticks):
        tick = scheduler.tick(now=now if simulate_clock else None)
        report = {
            "now": tick.now,
            "runs": [
                {
                    "name": run.name,
                    "mode": run.mode,
                    "trigger_at": run.trigger_at,
                    "success": run.success,
                    "error": run.error,
                }
                for run in tick.runs
            ],
        }
        reports.append(report)
        echo_json(report)
        if simulate_clock:
            now = now + timedelta(seconds=interval)
        else:
            time.sleep(interval)

    echo_json(
        {
            "ok": True,
            "event": "scheduler_finished",
            "ticks": ticks,
            "run_count": sum(len(item["runs"]) for item in reports),
            "emitted_runs": emitted_runs,
        }
    )


@runtime_group.command("test-mcp")
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
    help="Timeout for MCP self-test command.",
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
    help="Fail when memory channels are none/none.",
)
def runtime_test_mcp_command(
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
) -> None:
    echo_json(
        collect_runtime_mcp_self_test_payload(
            root=root,
            skills_dir=skills_dir,
            python_executable=python_executable,
            timeout_seconds=timeout_seconds,
            mcp_name=mcp_name,
            use_snapshot=use_snapshot,
            require_memory=require_memory,
            extract_memory_channels_fn=_extract_memory_channels,
            memory_channels_disabled_fn=_memory_channels_disabled,
            memory_config_recommendations_fn=_memory_config_recommendations,
            run_mcp_self_test_fn=_run_mcp_self_test,
            snapshot_path_fn=_mcp_env_snapshot_path,
            load_snapshot_fn=_load_mcp_env_snapshot,
        )
    )


@runtime_group.command("doctor-mcp")
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
def runtime_doctor_mcp_command(
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
) -> None:
    payload = collect_runtime_mcp_doctor_payload(
        root=root,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        require_memory=require_memory,
        probe_endpoints=probe_endpoints,
    )
    echo_json(payload)
    if not bool(payload.get("ok")):
        raise click.ClickException("MCP doctor checks failed")


@runtime_group.command("doctor-cache")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--db-path",
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
def runtime_doctor_cache_command(
    root: str,
    db_path: str,
    payload_root: str,
    temp_root: str,
) -> None:
    payload = build_runtime_cache_doctor_payload(
        root=root,
        db_path=db_path,
        payload_root=payload_root,
        temp_root=temp_root,
    )
    echo_json(payload)
    if not bool(payload.get("ok")):
        raise click.ClickException(
            "Stage artifact cache integrity check found severe corruption"
        )


@runtime_cache_group.command("vacuum")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--db-path",
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
    "--apply/--dry-run",
    default=False,
    show_default=True,
    help="Delete expired rows and orphan payloads instead of only reporting them.",
)
def runtime_cache_vacuum_command(
    root: str,
    db_path: str,
    payload_root: str,
    temp_root: str,
    apply: bool,
) -> None:
    payload = build_runtime_cache_vacuum_payload(
        root=root,
        db_path=db_path,
        payload_root=payload_root,
        temp_root=temp_root,
        apply=apply,
    )
    echo_json(payload)
    if not bool(payload.get("ok", False)):
        raise click.ClickException("Stage artifact cache vacuum failed")


@runtime_group.command("doctor")
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
    type=click.Choice(list(RUNTIME_PROFILE_NAMES), case_sensitive=False),
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
    default=DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    show_default=True,
    help="User-scope persisted runtime settings snapshot path.",
)
@click.option(
    "--last-known-good-path",
    default=DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
    show_default=True,
    help="User-scope last-known-good runtime settings snapshot path.",
)
@click.option(
    "--stats-db-path",
    default=DEFAULT_RUNTIME_STATS_DB_PATH,
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
def runtime_doctor_command(
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
    payload = build_runtime_doctor_payload(
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
    )
    if record_runtime_event:
        payload["runtime_event_recording"] = persist_runtime_doctor_invocation(
            root=root,
            payload=payload,
            stats_db_path=stats_db_path,
            profile_key=runtime_profile,
        )
    echo_json(payload)
    if not bool(payload.get("ok")):
        raise click.exceptions.Exit(1)


@runtime_group.command("setup-codex-mcp")
@click.option(
    "--name",
    default="ace-lite",
    show_default=True,
    help="Codex MCP server name.",
)
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--skills-dir",
    default="skills",
    show_default=True,
    help="Skills directory path.",
)
@click.option(
    "--codex-executable",
    default="codex",
    show_default=True,
    help="Codex CLI executable.",
)
@click.option(
    "--python-executable",
    default=sys.executable,
    show_default=True,
    help="Python executable used by MCP server.",
)
@click.option(
    "--enable-memory/--disable-memory",
    default=False,
    show_default=True,
    help="Enable Mem0/OpenMemory channels in MCP env.",
)
@click.option(
    "--memory-primary",
    type=click.Choice(["mcp", "rest", "none"], case_sensitive=False),
    default="rest",
    show_default=True,
    help="Primary memory channel when memory is enabled.",
)
@click.option(
    "--memory-secondary",
    type=click.Choice(["rest", "mcp", "none"], case_sensitive=False),
    default="none",
    show_default=True,
    help="Secondary memory channel when memory is enabled.",
)
@click.option(
    "--mcp-base-url",
    default="http://localhost:8765",
    show_default=True,
    help="OpenMemory MCP base URL.",
)
@click.option(
    "--rest-base-url",
    default="http://localhost:8765",
    show_default=True,
    help="OpenMemory REST base URL.",
)
@click.option(
    "--user-id",
    default="",
    show_default=True,
    help="Memory user id passed to OpenMemory (defaults to OS username).",
)
@click.option(
    "--app",
    default="ace-lite",
    show_default=True,
    help="Memory app scope passed to OpenMemory.",
)
@click.option(
    "--config-pack",
    default="",
    show_default=True,
    help="Optional config pack path exported as ACE_LITE_CONFIG_PACK.",
)
@click.option(
    "--enable-embeddings/--disable-embeddings",
    default=False,
    show_default=True,
    help="Enable embedding rerank env vars in the MCP registration.",
)
@click.option(
    "--embedding-provider",
    type=click.Choice(
        [
            "ollama",
            "sentence_transformers",
            "bge_m3",
            "bge_reranker",
            "hash",
            "hash_cross",
            "hash_colbert",
        ],
        case_sensitive=False,
    ),
    default="ollama",
    show_default=True,
    help="Embedding provider when embeddings are enabled.",
)
@click.option(
    "--embedding-model",
    default="dengcao/Qwen3-Embedding-4B:Q4_K_M",
    show_default=True,
    help="Embedding model identifier when embeddings are enabled.",
)
@click.option(
    "--embedding-dimension",
    default=2560,
    type=int,
    show_default=True,
    help="Embedding dimension for the configured model.",
)
@click.option(
    "--embedding-index-path",
    default="context-map/embeddings/index.json",
    show_default=True,
    help="Embedding index path exported to the MCP env.",
)
@click.option(
    "--embedding-rerank-pool",
    default=16,
    type=int,
    show_default=True,
    help="Embedding rerank pool size for MCP plans.",
)
@click.option(
    "--embedding-lexical-weight",
    default=0.55,
    type=float,
    show_default=True,
    help="Lexical weight for embedding rerank fusion.",
)
@click.option(
    "--embedding-semantic-weight",
    default=0.45,
    type=float,
    show_default=True,
    help="Semantic weight for embedding rerank fusion.",
)
@click.option(
    "--embedding-min-similarity",
    default=0.05,
    type=float,
    show_default=True,
    help="Minimum similarity threshold for embedding rerank.",
)
@click.option(
    "--embedding-fail-open/--no-embedding-fail-open",
    default=True,
    show_default=True,
    help="Keep planning available when the embedding provider is unavailable.",
)
@click.option(
    "--ollama-base-url",
    default="http://localhost:11434",
    show_default=True,
    help="Ollama base URL for embedding providers that use Ollama.",
)
@click.option(
    "--replace/--no-replace",
    default=True,
    show_default=True,
    help="Remove existing Codex MCP entry with same name first.",
)
@click.option(
    "--apply/--dry-run",
    default=False,
    show_default=True,
    help="Apply commands to Codex config or print planned commands only.",
)
@click.option(
    "--verify/--no-verify",
    default=True,
    show_default=True,
    help="Run `codex mcp get` and self-test validation after apply.",
)
def runtime_setup_codex_mcp_command(
    name: str,
    root: str,
    skills_dir: str,
    codex_executable: str,
    python_executable: str,
    enable_memory: bool,
    memory_primary: str,
    memory_secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    user_id: str,
    app: str,
    config_pack: str,
    enable_embeddings: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_index_path: str,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
    ollama_base_url: str,
    replace: bool,
    apply: bool,
    verify: bool,
) -> None:
    setup_plan = build_codex_mcp_setup_plan(
        name=name,
        root=root,
        skills_dir=skills_dir,
        codex_executable=codex_executable,
        python_executable=python_executable,
        enable_memory=enable_memory,
        memory_primary=memory_primary,
        memory_secondary=memory_secondary,
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        user_id=user_id,
        app=app,
        config_pack=config_pack,
        enable_embeddings=enable_embeddings,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_index_path=embedding_index_path,
        embedding_rerank_pool=embedding_rerank_pool,
        embedding_lexical_weight=embedding_lexical_weight,
        embedding_semantic_weight=embedding_semantic_weight,
        embedding_min_similarity=embedding_min_similarity,
        embedding_fail_open=embedding_fail_open,
        ollama_base_url=ollama_base_url,
        replace=replace,
        apply=apply,
        verify=verify,
        resolve_cli_path_fn=_resolve_cli_path,
        env_get_fn=os.getenv,
    )
    echo_json(
        execute_codex_mcp_setup_plan(
            setup_plan=setup_plan,
            python_executable=python_executable,
            run_subprocess_fn=subprocess.run,
            list2cmdline_fn=subprocess.list2cmdline,
            write_snapshot_fn=_write_mcp_env_snapshot,
            run_mcp_self_test_fn=_run_mcp_self_test,
        )
    )


__all__ = ["runtime_group"]
