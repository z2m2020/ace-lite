from __future__ import annotations

import json
from pathlib import Path

import click

from ace_lite.cli_app.orchestrator_factory import run_plan
from ace_lite.cli_app.output import echo_json
from ace_lite.demo_repo import seed_demo_repo


def _resolve_skills_dir(*, configured: str | None) -> str:
    if configured:
        return str(Path(configured).expanduser().resolve())

    cwd_candidate = Path.cwd() / "skills"
    if cwd_candidate.is_dir():
        return str(cwd_candidate.resolve())

    # Best-effort: if running from a source checkout, locate repo-root/skills.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "skills"
        if candidate.is_dir():
            return str(candidate.resolve())

    return "skills"


@click.command("demo", help="One-command demo: seed a tiny repo and run a plan.")
@click.option(
    "--output",
    "output_dir",
    default="artifacts/demo/repo",
    show_default=True,
    type=click.Path(path_type=str),
    help="Directory to write the seeded demo repo.",
)
@click.option(
    "--clone-url",
    default=None,
    type=str,
    help="Optional git clone URL to use as the repo root instead of seeding a demo repo.",
)
@click.option(
    "--query",
    default="shutdown middleware allowlist blocklist withdraw phase",
    show_default=True,
    help="Query to run in the demo plan.",
)
@click.option(
    "--repo",
    default="ace-lite-demo",
    show_default=True,
    help="Repo identifier passed to the planner.",
)
@click.option(
    "--skills-dir",
    default=None,
    type=str,
    help="Skills directory (defaults to ./skills when available).",
)
@click.option(
    "--languages",
    default="python",
    show_default=True,
    help="Comma-separated languages for indexing.",
)
def demo_command(
    output_dir: str,
    clone_url: str | None,
    query: str,
    repo: str,
    skills_dir: str | None,
    languages: str,
) -> None:
    output_path = Path(output_dir).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    root_path: Path
    if clone_url:
        from ace_lite.subprocess_utils import run_capture_output

        if output_path.exists() and any(output_path.iterdir()):
            raise click.ClickException(
                f"--output directory is not empty: {output_path}"
            )
        output_path.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "clone", "--depth", "1", str(clone_url), str(output_path)]
        returncode, stdout, stderr, timed_out = run_capture_output(
            cmd,
            cwd=output_path.parent,
            timeout_seconds=60.0,
            env_overrides={"GIT_TERMINAL_PROMPT": "0"},
        )
        if timed_out or returncode != 0:
            raise click.ClickException(
                "git clone failed: "
                f"returncode={returncode} timed_out={timed_out} stderr={str(stderr or '')[:240]}"
            )
        root_path = output_path
    else:
        root_path = seed_demo_repo(root=output_path)

    resolved_skills_dir = _resolve_skills_dir(configured=skills_dir)

    payload = run_plan(
        query=str(query),
        repo=str(repo),
        root=str(root_path),
        skills_dir=str(resolved_skills_dir),
        memory_disclosure_mode="compact",
        memory_strategy="hybrid",
        memory_provider=None,
        memory_client=None,
        memory_notes_enabled=False,
        memory_capture_enabled=False,
        memory_feedback_enabled=False,
        memory_profile_enabled=False,
        top_k_files=8,
        min_candidate_score=1,
        candidate_ranker="rrf_hybrid",
        index_languages=[token.strip().lower() for token in str(languages).split(",") if token.strip()],
        index_cache_path=str(root_path / "context-map" / "index.json"),
        index_incremental=True,
        repomap_config={"enabled": False},
        plugins_config={"enabled": True},
    )

    echo_json(
        {
            "demo_root": str(root_path),
            "skills_dir": str(resolved_skills_dir),
            "query": str(query),
            "repo": str(repo),
            "plan": payload,
        }
    )


__all__ = ["demo_command"]
