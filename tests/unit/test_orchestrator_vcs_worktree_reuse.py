from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import ace_lite.pipeline.stages.augment as augment_stage
from ace_lite.memory import NullMemoryProvider
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.types import StageContext


def test_orchestrator_reuses_cached_vcs_worktree_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    override = {"enabled": True, "reason": "cached"}

    def unexpected_call(*args: object, **kwargs: object) -> dict[str, Any]:
        raise AssertionError("collect_git_worktree_summary should not be called")

    monkeypatch.setattr(
        augment_stage,
        "collect_git_worktree_summary",
        unexpected_call,
    )

    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        cochange={"enabled": True},
        lsp={"enabled": False},
    )
    orchestrator = AceOrchestrator(
        memory_provider=NullMemoryProvider(),
        config=config,
    )

    ctx = StageContext(
        query="q",
        repo="demo",
        root=str(tmp_path),
        state={
            "index": {
                "candidate_files": [{"path": "src/app.py", "language": "python"}],
            },
            "__vcs_worktree": override,
        },
    )

    payload = orchestrator._run_augment(ctx=ctx)

    assert payload["vcs_worktree"] == override
