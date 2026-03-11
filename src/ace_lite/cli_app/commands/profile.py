"""CLI commands for managing local ACE-Lite profile data."""

from __future__ import annotations

import click

from ace_lite.cli_app.output import echo_json
from ace_lite.profile_store import ProfileStore


@click.group("profile", help="Manage local user profile facts/preferences.")
def profile_group() -> None:
    return None


@profile_group.command("show")
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Path to local profile JSON file.",
)
def profile_show_command(profile_path: str) -> None:
    store = ProfileStore(path=profile_path)
    payload = store.load()
    payload["path"] = str(store.path)
    echo_json(payload)


@profile_group.command("add-fact")
@click.argument("text")
@click.option(
    "--confidence",
    default=1.0,
    type=float,
    show_default=True,
    help="Confidence score in [0.0, 1.0].",
)
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Path to local profile JSON file.",
)
def profile_add_fact_command(
    text: str,
    confidence: float,
    profile_path: str,
) -> None:
    store = ProfileStore(path=profile_path)
    payload = store.add_fact(text, confidence=confidence, source="manual")
    payload["path"] = str(store.path)
    echo_json(payload)


@profile_group.command("wipe")
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Path to local profile JSON file.",
)
def profile_wipe_command(profile_path: str) -> None:
    store = ProfileStore(path=profile_path)
    store.wipe()
    echo_json({"ok": True, "path": str(store.path)})


@profile_group.command("vacuum")
@click.option(
    "--profile-path",
    default="~/.ace-lite/profile.json",
    show_default=True,
    help="Path to local profile JSON file.",
)
@click.option(
    "--expiry-enabled/--no-expiry-enabled",
    default=True,
    show_default=True,
    help="Enable expiry-based pruning during vacuum.",
)
@click.option(
    "--ttl-days",
    default=90,
    show_default=True,
    type=int,
    help="TTL days for fact/context last-used timestamps.",
)
@click.option(
    "--max-age-days",
    default=365,
    show_default=True,
    type=int,
    help="Hard max age days for profile facts/contexts.",
)
def profile_vacuum_command(
    profile_path: str,
    expiry_enabled: bool,
    ttl_days: int,
    max_age_days: int,
) -> None:
    store = ProfileStore(path=profile_path)
    payload = store.vacuum(
        expiry_enabled=bool(expiry_enabled),
        ttl_days=max(1, int(ttl_days)),
        max_age_days=max(1, int(max_age_days)),
    )
    echo_json(payload)


__all__ = ["profile_group"]
