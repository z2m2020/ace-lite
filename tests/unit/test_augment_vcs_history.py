from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import ace_lite.pipeline.stages.augment as augment_stage
from ace_lite.pipeline.stages.augment import run_diagnostics_augment


def test_run_diagnostics_augment_includes_vcs_history_payload(tmp_path: Path) -> None:
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
    assert "vcs_history" in payload
    assert payload["vcs_history"]["enabled"] is False
    assert payload["vcs_history"]["reason"] == "disabled"


def test_run_diagnostics_augment_fail_opens_vcs_history_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def raise_history(*args: object, **kwargs: object) -> dict[str, Any]:
        raise RuntimeError("history unavailable")

    monkeypatch.setattr(augment_stage, "collect_git_commit_history", raise_history)

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
    assert payload["vcs_history"]["enabled"] is True
    assert payload["vcs_history"]["reason"] == "error"
    assert payload["vcs_history"]["commit_count"] == 0
    assert payload["vcs_history"]["error"] == "history unavailable"
