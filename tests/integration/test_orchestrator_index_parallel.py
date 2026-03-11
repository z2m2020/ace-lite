from __future__ import annotations

import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig


def _seed_repo(root: Path) -> None:
    (root / "src" / "core").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)

    (root / "src" / "core" / "auth.py").write_text(
        textwrap.dedent(
            """
            def validate_token(raw: str) -> bool:
                return bool(raw)

            def refresh_session(token: str) -> str:
                return token.strip()
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    (root / "docs" / "ARCHITECTURE.md").write_text(
        textwrap.dedent(
            """
            # Architecture

            The engine uses a deterministic multi-stage pipeline.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _base_config(
    *,
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
    **overrides: Any,
) -> OrchestratorConfig:
    return OrchestratorConfig(
        skills={
            "manifest": fake_skill_manifest,
        },
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        **overrides,
    )


def test_orchestrator_index_parallel_enabled_under_policy_v2(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)
    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": False},
        scip={"enabled": False},
        retrieval={"retrieval_policy": "doc_intent", "policy_version": "v2"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="how does the architecture work",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    index_payload = payload["index"]
    parallel = index_payload["parallel"]
    assert parallel["requested"] is True
    assert parallel["enabled"] is True
    assert parallel["docs"]["started"] is True
    assert parallel["docs"]["timed_out"] is False

    stage_metrics = payload["observability"]["stage_metrics"]
    index_metric = next(item for item in stage_metrics if item["stage"] == "index")
    assert index_metric["tags"]["parallel_enabled"] is True
    assert index_metric["tags"]["parallel_docs_timed_out"] is False


def test_orchestrator_index_parallel_docs_timeout_fail_open(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    import ace_lite.pipeline.stages.index as index_stage

    original_collect_docs_signals = index_stage.collect_docs_signals

    def _slow_collect_docs_signals(*args: Any, **kwargs: Any) -> dict[str, Any]:
        time.sleep(0.05)
        return original_collect_docs_signals(*args, **kwargs)

    monkeypatch.setattr(index_stage, "collect_docs_signals", _slow_collect_docs_signals)

    original_resolve_retrieval_policy = index_stage.resolve_retrieval_policy

    def _resolve_retrieval_policy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = original_resolve_retrieval_policy(*args, **kwargs)
        payload["index_parallel_enabled"] = True
        payload["index_parallel_time_budget_ms"] = 1
        payload["docs_enabled"] = True
        return payload

    monkeypatch.setattr(index_stage, "resolve_retrieval_policy", _resolve_retrieval_policy)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": False},
        scip={"enabled": False},
        retrieval={"retrieval_policy": "doc_intent", "policy_version": "v2"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="how does the architecture work",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    index_payload = payload["index"]
    assert index_payload["parallel"]["enabled"] is True
    assert index_payload["parallel"]["docs"]["timed_out"] is True
    assert index_payload["docs"]["enabled"] is False
    assert index_payload["docs"]["reason"] == "timeout"

    stage_metrics = payload["observability"]["stage_metrics"]
    index_metric = next(item for item in stage_metrics if item["stage"] == "index")
    assert index_metric["tags"]["parallel_enabled"] is True
    assert index_metric["tags"]["parallel_docs_timed_out"] is True


def test_orchestrator_index_parallel_starts_worktree_future_under_policy_v2(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    import ace_lite.pipeline.stages.index as index_stage

    def _stub_collect_worktree_prior(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return index_stage._disabled_worktree_prior(reason="stub")

    monkeypatch.setattr(index_stage, "collect_worktree_prior", _stub_collect_worktree_prior)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": True},
        scip={"enabled": False},
        retrieval={"retrieval_policy": "general", "policy_version": "v2"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="validate token behavior",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    index_payload = payload["index"]
    parallel = index_payload["parallel"]
    assert parallel["requested"] is True
    assert parallel["enabled"] is True
    assert parallel["docs"]["started"] is False
    assert parallel["worktree"]["started"] is True
