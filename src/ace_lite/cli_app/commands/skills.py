from __future__ import annotations

from pathlib import Path

import click

from ace_lite.cli_app.docs_links import get_help_template
from ace_lite.skills import build_skill_catalog, build_skill_manifest


def _resolve_skills_path(*, root: str, skills_dir: str) -> Path:
    root_path = Path(root).expanduser().resolve()
    candidate = Path(skills_dir).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_path / candidate).resolve()


@click.group(
    "skills",
    help="Inspect skill manifests and discovery surfaces.",
    epilog=get_help_template("skills"),
)
def skills_group() -> None:
    return None


@skills_group.command("catalog", help="Render available skills as a read-only markdown catalog.")
@click.option("--root", default=".", show_default=True, help="Repository root path.")
@click.option(
    "--skills-dir",
    default="skills",
    show_default=True,
    help="Skills directory relative to --root, or absolute path.",
)
def skills_catalog_command(root: str, skills_dir: str) -> None:
    manifest = build_skill_manifest(_resolve_skills_path(root=root, skills_dir=skills_dir))
    click.echo(build_skill_catalog(manifest))


__all__ = ["skills_catalog_command", "skills_group"]
