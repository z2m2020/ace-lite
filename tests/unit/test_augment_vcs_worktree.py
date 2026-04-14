from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import ace_lite.pipeline.stages.augment as augment_stage
from ace_lite.pipeline.stages.augment import run_diagnostics_augment


def test_run_diagnostics_augment_includes_vcs_worktree_payload(tmp_path: Path) -> None:
    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="q",
        index_stage={"candidate_files": [{"path": "src/app.py", "language": "python"}]},
        enabled=False,
        top_n=3,
        broker=None,
        xref_enabled=False,
        xref_top_n=1,
        xref_time_budget_ms=100,
    )

    assert payload["enabled"] is False
    assert "vcs_worktree" in payload
    assert payload["vcs_worktree"]["enabled"] is False
    assert payload["vcs_worktree"]["reason"] == "disabled"


def test_run_diagnostics_augment_uses_vcs_worktree_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    override = {"enabled": True, "reason": "cached"}

    def unexpected_call(*args: object, **kwargs: object) -> dict[str, Any]:
        raise AssertionError("collect_git_worktree_summary should not be called")

    monkeypatch.setattr(
        augment_stage,
        "collect_git_worktree_summary",
        unexpected_call,
    )

    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="q",
        index_stage={"candidate_files": [{"path": "src/app.py", "language": "python"}]},
        enabled=True,
        top_n=3,
        broker=None,
        xref_enabled=False,
        xref_top_n=1,
        xref_time_budget_ms=100,
        vcs_worktree_override=override,
    )

    assert payload["vcs_worktree"] == override


def test_run_diagnostics_augment_fail_opens_vcs_worktree_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def raise_worktree(*args: object, **kwargs: object) -> dict[str, Any]:
        raise RuntimeError("worktree unavailable")

    monkeypatch.setattr(
        augment_stage,
        "collect_git_worktree_summary",
        raise_worktree,
    )

    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="q",
        index_stage={"candidate_files": [{"path": "src/app.py", "language": "python"}]},
        enabled=True,
        top_n=3,
        broker=None,
        xref_enabled=False,
        xref_top_n=1,
        xref_time_budget_ms=100,
    )

    assert payload["reason"] == "broker_unavailable"
    assert payload["vcs_worktree"]["enabled"] is True
    assert payload["vcs_worktree"]["reason"] == "error"
    assert payload["vcs_worktree"]["changed_count"] == 0
    assert payload["vcs_worktree"]["error"] == "worktree unavailable"
