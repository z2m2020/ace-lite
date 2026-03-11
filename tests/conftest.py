"""Shared pytest fixtures and bootstrap helpers.

The repository uses a `src/` layout, so the test suite adds `src/` to
`sys.path` once (here) instead of duplicating that setup in every test module.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


@pytest.fixture()
def fake_index_files() -> dict[str, dict[str, Any]]:
    """Small, deterministic index payload used by repomap ranking tests."""

    return {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}, {"name": "B"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "Only"}],
            "imports": [],
        },
        "docs/readme.md": {
            "module": "",
            "language": "",
            "symbols": [],
            "imports": [],
        },
    }


@pytest.fixture()
def fake_skill_manifest(tmp_path: Path) -> list[dict[str, Any]]:
    """Builds a small on-disk skills set and returns its manifest."""

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    (skills_dir / "mem.md").write_text(
        textwrap.dedent(
            """
            ---
            name: mem0-codex-playbook
            description: memory ops
            intents: [memory, retrieval]
            modules: [api, mcp]
            error_keywords: [dimension, 405]
            topics: [openmemory, qdrant]
            default_sections: [Workflow]
            priority: 2
            ---
            # Workflow
            Use bridge mode.

            # Troubleshooting
            Fix 405 with mcp-remote.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    (skills_dir / "review.md").write_text(
        textwrap.dedent(
            """
            ---
            name: code-review-router
            intents: [review]
            modules: [repo]
            ---
            # Workflow
            Route reviews.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    from ace_lite.skills import build_skill_manifest

    return build_skill_manifest(skills_dir)


@pytest.fixture()
def tmp_plugin_dir(tmp_path: Path) -> Path:
    """Creates a `plugins/` directory under a temporary repo root."""

    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir(parents=True, exist_ok=True)
    return plugin_root


@pytest.fixture()
def null_orchestrator(tmp_path: Path, fake_skill_manifest: list[dict[str, Any]]):
    """An AceOrchestrator wired with a NullMemoryProvider and isolated cache."""

    from ace_lite.memory import NullMemoryProvider
    from ace_lite.orchestrator import AceOrchestrator
    from ace_lite.orchestrator_config import OrchestratorConfig

    return AceOrchestrator(
        memory_provider=NullMemoryProvider(),
        config=OrchestratorConfig(
            skills={
                "manifest": fake_skill_manifest,
            },
            index={
                "languages": ["python"],
                "cache_path": tmp_path / "context-map" / "index.json",
            },
        ),
    )
