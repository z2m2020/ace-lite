"""Documentation links for CLI commands.

Centralized documentation URLs for help text and examples.

PRD-91: Unified doc entrypoint for help text.
"""

from __future__ import annotations

DOCS_BASE = "docs/guides"
DOCS_ROOT = "docs"

GUIDES = {
    "getting_started": f"{DOCS_BASE}/GETTING_STARTED.md",
    "configuration": f"{DOCS_BASE}/CONFIGURATION.md",
    "troubleshooting": f"{DOCS_BASE}/TROUBLESHOOTING.md",
}

COMMAND_GUIDES = {
    "plan": f"{DOCS_BASE}/PLAN_GUIDE.md",
    "index": f"{DOCS_BASE}/INDEXING.md",
    "repomap": f"{DOCS_BASE}/REPOMAP.md",
    "doctor": f"{DOCS_BASE}/DIAGNOSTICS.md",
    "benchmark": f"{DOCS_BASE}/BENCHMARK.md",
    "memory": f"{DOCS_BASE}/MEMORY.md",
    "feedback": f"{DOCS_BASE}/FEEDBACK.md",
    "profile": f"{DOCS_BASE}/PROFILE.md",
    "workspace": f"{DOCS_BASE}/WORKSPACE.md",
    "demo": f"{DOCS_BASE}/DEMO.md",
    "runtime": f"{DOCS_BASE}/RUNTIME.md",
    "skills": f"{DOCS_BASE}/SKILLS.md",
}

QUICK_REFERENCE = {
    "examples": f"{DOCS_BASE}/EXAMPLES.md",
    "cheatsheet": f"{DOCS_BASE}/CHEATSHEET.md",
}


def get_command_guide(command: str) -> str | None:
    """Get the guide link for a command."""
    return COMMAND_GUIDES.get(command.lower())


def get_guide(name: str) -> str | None:
    """Get a general guide link."""
    return GUIDES.get(name.lower())


HELP_TEMPLATES = {
    "getting_started": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/CHEATSHEET.md         Command cheatsheet
""",
    "benchmark": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/BENCHMARK.md          Benchmark guide
""",
    "demo": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/DEMO.md               Demo guide
""",
    "feedback": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/FEEDBACK.md           Feedback guide
""",
    "memory": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/MEMORY.md             Memory guide
""",
    "plan": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/PLAN_GUIDE.md         Plan command guide
  docs/guides/RETRIEVAL_PROFILES.md Retrieval profiles guide
""",
    "plan-quick": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/PLAN_QUICK.md         Plan quick guide
""",
    "profile": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/PROFILE.md            Profile guide
""",
    "index": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/INDEXING.md           Indexing guide
""",
    "doctor": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/DIAGNOSTICS.md        Diagnostics guide
""",
    "repomap": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/REPOMAP.md            RepoMap guide
""",
    "workspace": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/WORKSPACE.md          Workspace guide
""",
    "runtime": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/RUNTIME.md            Runtime guide
""",
    "skills": """
See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/SKILLS.md             Skills guide
""",
}


def get_help_template(command: str) -> str:
    """Get the help 'See also' template for a command."""
    return HELP_TEMPLATES.get(
        command.lower(),
        HELP_TEMPLATES.get("getting_started", ""),
    )


__all__ = [
    "COMMAND_GUIDES",
    "DOCS_BASE",
    "DOCS_ROOT",
    "GUIDES",
    "HELP_TEMPLATES",
    "QUICK_REFERENCE",
    "get_command_guide",
    "get_guide",
    "get_help_template",
]
