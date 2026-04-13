from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ace_lite.orchestrator_source_plan_replay_service import SourcePlanReplayService


def _build_config(
    *,
    cache_path: str = "",
    cache_enabled: bool = True,
    candidate_ranker: str = "rrf_hybrid",
    skills_token_budget: int = 1200,
) -> SimpleNamespace:
    return SimpleNamespace(
        plan_replay_cache=SimpleNamespace(enabled=cache_enabled, cache_path=cache_path),
        retrieval=SimpleNamespace(policy_version="v1", candidate_ranker=candidate_ranker, top_k_files=8),
        chunking=SimpleNamespace(disclosure="compact", top_k=12, per_file_limit=4, token_budget=900),
        repomap=SimpleNamespace(top_k=8, neighbor_limit=20, budget_tokens=800),
        skills=SimpleNamespace(top_n=3, token_budget=skills_token_budget, precomputed_routing_enabled=True),
        lsp=SimpleNamespace(top_n=5, xref_top_n=3),
    )


def _build_service(
    *,
    root: Path,
    cache_path: str = "",
    cache_enabled: bool = True,
    candidate_ranker: str = "rrf_hybrid",
    skills_token_budget: int = 1200,
) -> SourcePlanReplayService:
    return SourcePlanReplayService(
        config=_build_config(
            cache_path=cache_path,
            cache_enabled=cache_enabled,
            candidate_ranker=candidate_ranker,
            skills_token_budget=skills_token_budget,
        ),
        plan_replay_stage="source_plan",
        plan_replay_mode="late_exact_source_plan",
        plan_replay_guarded_by=("normalized_query", "budget_knobs"),
        resolve_repo_relative_path_fn=lambda *, root, configured_path: Path(root) / configured_path,
    )


def _build_valid_source_plan_payload() -> dict[str, object]:
    return {
        "repo": "ace-lite",
        "root": "/tmp/repo",
        "query": "fix source plan replay",
        "stages": [],
        "constraints": [],
        "diagnostics": [],
        "xref": {},
        "tests": {},
        "validation_tests": [],
        "candidate_chunks": [],
        "chunk_steps": [],
        "chunk_budget_used": 0,
        "chunk_budget_limit": 0,
        "chunk_disclosure": "compact",
        "policy_name": "source_plan",
        "policy_version": "v1",
        "steps": [],
        "writeback_template": {},
    }


def test_resolve_plan_replay_cache_path_defaults_when_config_empty(tmp_path: Path) -> None:
    service = _build_service(root=tmp_path)

    resolved = service.resolve_plan_replay_cache_path(root=str(tmp_path))

    assert resolved == tmp_path / "context-map" / "plan-replay" / "cache.json"


def test_default_plan_replay_cache_info_uses_service_contract(tmp_path: Path) -> None:
    service = _build_service(root=tmp_path, cache_enabled=False)

    payload = service.default_plan_replay_cache_info(root=str(tmp_path))

    assert payload["enabled"] is False
    assert payload["stage"] == "source_plan"
    assert payload["mode"] == "late_exact_source_plan"
    assert payload["reason"] == "disabled"
    assert payload["failure_signal_summary"]["source"] == "source_plan"


def test_extract_source_plan_validation_feedback_summary_reads_validate_step_payload(
    tmp_path: Path,
) -> None:
    service = _build_service(root=tmp_path)

    summary = service.extract_source_plan_validation_feedback_summary(
        {
            "steps": [
                {"stage": "index", "validation_feedback_summary": {"retry_count": 9}},
                {
                    "stage": "validate",
                    "validation_feedback_summary": {
                        "status": "failed",
                        "issue_count": 2,
                        "probe_status": "failed",
                    },
                },
            ]
        }
    )

    assert summary == {
        "status": "failed",
        "issue_count": 2,
        "probe_status": "failed",
    }


def test_extract_source_plan_failure_signal_summary_falls_back_to_validation_feedback_summary(
    tmp_path: Path,
) -> None:
    service = _build_service(root=tmp_path)

    summary = service.extract_source_plan_failure_signal_summary(
        {
            "steps": [
                {
                    "stage": "validate",
                    "validation_feedback_summary": {
                        "status": "failed",
                        "issue_count": 2,
                        "probe_status": "failed",
                        "probe_issue_count": 1,
                    },
                }
            ]
        }
    )

    assert summary["status"] == "failed"
    assert summary["issue_count"] == 2
    assert summary["probe_status"] == "failed"
    assert summary["probe_issue_count"] == 1
    assert summary["has_failure"] is True
    assert summary["source"] == "source_plan"


def test_store_and_load_replayed_source_plan_round_trip(tmp_path: Path) -> None:
    cache_path = tmp_path / "context-map" / "custom-plan-replay.json"
    service = _build_service(
        root=tmp_path,
        cache_path="context-map/custom-plan-replay.json",
    )
    source_plan_payload = _build_valid_source_plan_payload()

    stored_info = service.store_source_plan_replay(
        query="fix source plan replay",
        repo="ace-lite",
        replay_cache_path=cache_path,
        replay_cache_key="k1",
        source_plan_stage=source_plan_payload,
        replay_cache_info={"reason": "miss", "hit": False},
    )
    loaded_payload, loaded_info = service.load_replayed_source_plan(
        root=str(tmp_path),
        replay_cache_path=cache_path,
        replay_cache_key="k1",
    )

    assert stored_info["stored"] is True
    assert loaded_payload == source_plan_payload
    assert loaded_info["hit"] is True
    assert loaded_info["reason"] == "hit"
    assert loaded_info["policy_name"] == "source_plan"


def test_build_plan_replay_key_changes_when_budget_knob_changes(tmp_path: Path) -> None:
    base = _build_service(root=tmp_path, skills_token_budget=1200)
    changed = _build_service(root=tmp_path, skills_token_budget=2400)

    kwargs = {
        "query": "sync docs update",
        "repo": "ace-lite",
        "root": str(tmp_path),
        "temporal_input": {"time_range": "last_30_days"},
        "plugins_loaded": ["plugin-a"],
        "conventions_hashes": {"AGENTS.md": "abc"},
        "memory_stage": {"hits_preview": []},
        "index_stage": {"candidate_files": []},
        "repomap_stage": {"focused_files": []},
        "augment_stage": {"selected_files": []},
        "skills_stage": {"matched_skills": []},
    }

    first = base.build_plan_replay_key(**kwargs)
    second = changed.build_plan_replay_key(**kwargs)

    assert first != second
