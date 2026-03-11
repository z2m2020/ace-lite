from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig


def _seed_feedback_repo(root: Path) -> None:
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)

    payload = textwrap.dedent(
        """
        def validate_token(raw: str) -> bool:
            return bool(raw)
        """
    ).strip()
    (root / "src" / "app" / "alpha.py").write_text(payload + "\n", encoding="utf-8")
    (root / "src" / "app" / "beta.py").write_text(payload + "\n", encoding="utf-8")


def test_orchestrator_feedback_disabled_baseline(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_feedback_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        retrieval={
            "candidate_ranker": "heuristic",
            "min_candidate_score": 0,
            "top_k_files": 2,
        },
        memory={
            "feedback": {
                "enabled": False,
            }
        },
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(query="validate token", repo="demo", root=str(tmp_path))

    candidates = payload["index"]["candidate_files"]
    assert [item["path"] for item in candidates[:2]] == [
        "src/app/alpha.py",
        "src/app/beta.py",
    ]
    assert payload["index"]["feedback"]["enabled"] is False
    assert payload["index"]["feedback"]["reason"] == "disabled"
    assert "prior_feedback" not in candidates[0]["score_breakdown"]


def test_orchestrator_feedback_enabled_without_events_is_noop(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_feedback_repo(tmp_path)
    profile_path = tmp_path / "profile.json"
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        retrieval={
            "candidate_ranker": "heuristic",
            "min_candidate_score": 0,
            "top_k_files": 2,
        },
        memory={
            "feedback": {
                "enabled": True,
                "path": str(profile_path),
                "max_entries": 16,
            }
        },
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(query="validate token", repo="demo", root=str(tmp_path))

    candidates = payload["index"]["candidate_files"]
    assert [item["path"] for item in candidates[:2]] == [
        "src/app/alpha.py",
        "src/app/beta.py",
    ]
    assert payload["index"]["feedback"]["enabled"] is True
    assert payload["index"]["feedback"]["reason"] == "no_events"
    assert "prior_feedback" not in candidates[0]["score_breakdown"]


def test_orchestrator_feedback_boosts_selected_path(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_feedback_repo(tmp_path)
    profile_path = tmp_path / "profile.json"
    SelectionFeedbackStore(profile_path=profile_path, max_entries=16).record(
        query="validate token",
        repo="demo",
        selected_path="src/app/beta.py",
        position=2,
        captured_at="2026-02-14T00:00:00+00:00",
    )

    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        retrieval={
            "candidate_ranker": "heuristic",
            "min_candidate_score": 0,
            "top_k_files": 2,
        },
        memory={
            "feedback": {
                "enabled": True,
                "path": str(profile_path),
                "max_entries": 16,
                "boost_per_select": 0.6,
                "max_boost": 0.6,
                "decay_days": 60.0,
            }
        },
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(query="validate token", repo="demo", root=str(tmp_path))

    candidates = payload["index"]["candidate_files"]
    assert [item["path"] for item in candidates[:2]] == [
        "src/app/beta.py",
        "src/app/alpha.py",
    ]
    assert payload["index"]["feedback"]["enabled"] is True
    assert payload["index"]["feedback"]["reason"] == "ok"
    assert int(payload["index"]["feedback"]["boosted_candidate_count"]) >= 1
    assert float(candidates[0]["score_breakdown"]["prior_feedback"]) > 0.0
