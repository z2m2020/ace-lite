from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from ace_lite.cli import cli
from ace_lite.index_stage import extract_terms
from ace_lite.memory import OpenMemoryMemoryProvider
from ace_lite.memory_long_term import (
    LongTermMemoryProvider,
    LongTermMemoryStore,
    build_long_term_fact_contract_v1,
)
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.rankers.bm25 import rank_candidates_bm25_two_stage
from ace_lite.runtime_manager import RuntimeManager
from ace_lite.stage_artifact_cache import StageArtifactCache
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.schema import SCHEMA_VERSION
from ace_lite.validation.result import build_validation_result_v1


class FakeOpenMemoryClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def search(
        self,
        *,
        query: str,
        user_id: str | None = None,
        app: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "query": query,
                "user_id": user_id,
                "app": app,
                "limit": limit,
            }
        )
        return {
            "results": [
                {
                    "memory": "Keep owner-file scope only.",
                    "score": 0.99,
                    "metadata": {"path": "docs/design/ORCHESTRATOR_DESIGN.md"},
                }
            ]
        }



def test_bm25_two_stage_shortlists_before_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    import ace_lite.rankers.bm25 as bm25_ranker

    files_map = {
        f"src/f{idx:02d}.py": {
            "module": f"src.f{idx:02d}",
            "language": "python",
            "symbols": [],
            "imports": [],
        }
        for idx in range(30)
    }

    calls: list[int] = []

    def fake_heuristic(files_map: Any, terms: list[str], *, min_score: int = 1) -> list[dict[str, Any]]:
        paths = sorted(str(path) for path in files_map)
        return [
            {"path": path, "score": float(len(paths) - offset)}
            for offset, path in enumerate(paths)
        ]

    def fake_bm25(files_map: Any, terms: list[str], *, min_score: int = 1) -> list[dict[str, Any]]:
        calls.append(len(files_map) if isinstance(files_map, dict) else 0)
        return []

    monkeypatch.setattr(bm25_ranker, "rank_candidates_bm25", fake_bm25)
    rank_candidates_bm25_two_stage(
        files_map,
        ["token"],
        min_score=0,
        top_k_files=2,
        heuristic_ranker=fake_heuristic,
    )

    assert calls
    assert calls[0] == 16


def test_bm25_two_stage_falls_back_to_full_corpus_when_shortlist_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ace_lite.rankers.bm25 as bm25_ranker

    files_map = {
        f"src/f{idx:02d}.py": {
            "module": f"src.f{idx:02d}",
            "language": "python",
            "symbols": [],
            "imports": [],
        }
        for idx in range(20)
    }

    calls: list[int] = []

    def fake_heuristic(files_map: Any, terms: list[str], *, min_score: int = 1) -> list[dict[str, Any]]:
        paths = sorted(str(path) for path in files_map)
        return [
            {"path": path, "score": float(len(paths) - offset)}
            for offset, path in enumerate(paths)
        ]

    def fake_bm25(files_map: Any, terms: list[str], *, min_score: int = 1) -> list[dict[str, Any]]:
        corpus_size = len(files_map) if isinstance(files_map, dict) else 0
        calls.append(corpus_size)
        if len(calls) == 1:
            return []
        first_path = sorted(files_map.keys())[0]
        return [{"path": first_path, "score": 1.0}]

    monkeypatch.setattr(bm25_ranker, "rank_candidates_bm25", fake_bm25)
    ranked = rank_candidates_bm25_two_stage(
        files_map,
        ["token"],
        min_score=0,
        top_k_files=2,
        heuristic_ranker=fake_heuristic,
    )

    assert calls == [16, 20]
    assert ranked

def _seed_repo(root: Path) -> None:
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "auth.py").write_text(
        textwrap.dedent(
            """
            def validate_token(raw: str) -> bool:
                return bool(raw)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_orchestrator_pipeline_and_injected_client(tmp_path: Path, fake_skill_manifest: list[dict[str, Any]]) -> None:
    _seed_repo(tmp_path)
    client = FakeOpenMemoryClient()
    provider = OpenMemoryMemoryProvider(client, user_id="u-test", app="ace-lite", limit=4, channel_name="mcp")
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(memory_provider=provider, config=config)

    payload = orchestrator.plan(
        query="fix 405 memory pipeline for auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["pipeline_order"] == [
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
        "source_plan",
        "validation",
    ]
    assert payload["memory"]["count"] == 1
    assert payload["memory"]["channel_used"] == "mcp"
    assert "docs/design/ORCHESTRATOR_DESIGN.md" in payload["index"]["targets"]
    assert payload["index"]["languages_covered"] == ["python"]
    assert payload["repomap"]["enabled"] is False
    assert isinstance(payload["repomap"].get("focused_files", []), list)
    assert payload["augment"]["enabled"] is False
    assert payload["augment"]["reason"] == "disabled"
    assert payload["skills"]["available_count"] == len(fake_skill_manifest)
    assert payload["skills"]["routing_source"] == "precomputed"
    assert payload["skills"]["metadata_only_routing"] is True
    assert payload["skills"]["route_latency_ms"] >= 0.0
    assert payload["skills"]["selected"][0]["name"] == "mem0-codex-playbook"
    assert payload["validation"]["enabled"] is False
    assert payload["validation"]["reason"] == "disabled"
    assert isinstance(payload["observability"]["stage_metrics"], list)
    assert len(payload["observability"]["stage_metrics"]) == 7
    first_stage = payload["observability"]["stage_metrics"][0]
    assert "tags" in first_stage
    assert isinstance(first_stage["tags"], dict)
    assert "conventions" in payload
    assert "rules_count" in payload["conventions"]

    assert client.calls == [
        {
            "query": "fix 405 memory pipeline for auth",
            "user_id": "u-test",
            "app": "ace-lite",
            "limit": 4,
        }
    ]


def test_orchestrator_plan_records_durable_runtime_stats(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    db_path = tmp_path / "user-runtime" / "runtime-stats.db"
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(
        config=config,
        durable_stats_store_factory=lambda: DurableStatsStore(db_path=db_path),
    )

    payload = orchestrator.plan(
        query="record durable runtime stats for auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    durable_stats = payload["observability"]["durable_stats"]
    assert durable_stats["enabled"] is True
    assert durable_stats["recorded"] is True

    store = DurableStatsStore(db_path=db_path)
    all_time = store.read_scope(scope_kind="all_time", scope_key="all")
    session = store.read_scope(
        scope_kind="session",
        scope_key=str(durable_stats["session_id"]),
    )

    assert all_time is not None
    assert session is not None
    assert all_time.to_payload()["counters"]["invocation_count"] == 1
    assert session.to_payload()["counters"]["invocation_count"] == 1
    assert "total" in [item["stage_name"] for item in session.to_payload()["stage_latencies"]]


def test_orchestrator_plan_captures_long_term_stage_observations(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    db_path = tmp_path / "context-map" / "long_term_memory.db"
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        memory={
            "long_term": {
                "enabled": True,
                "path": db_path,
                "write_enabled": True,
            }
        },
        validation={"enabled": False},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="capture source plan and validation observations",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    store = LongTermMemoryStore(db_path=db_path)
    rows = store.search(query="capture", limit=10)

    assert "long_term_capture" in payload["observability"]
    assert len(payload["observability"]["long_term_capture"]) == 2
    assert {row.payload["kind"] for row in rows} == {"source_plan", "validation"}


def test_orchestrator_plan_emits_ltm_constraints_for_source_plan(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    store = LongTermMemoryStore(db_path=tmp_path / "context-map" / "long_term_memory.db")
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="ace-lite-engine",
            namespace="repo:ace-lite-engine",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    provider = LongTermMemoryProvider(
        store,
        limit=4,
        container_tag="repo:ace-lite-engine",
        neighborhood_hops=1,
        neighborhood_limit=4,
    )
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        memory={
            "namespace": {"container_tag": "repo:ace-lite-engine"},
            "disclosure_mode": "full",
        },
        validation={"enabled": False},
    )
    orchestrator = AceOrchestrator(memory_provider=provider, config=config)

    payload = orchestrator.plan(
        query="fallback",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert payload["memory"]["ltm"]["selected_count"] == 1
    assert payload["source_plan"]["ltm_constraint_summary"] == {
        "selected_count": 1,
        "constraint_count": 1,
        "graph_neighbor_count": 0,
        "handles": ["fact-1"],
    }
    assert payload["source_plan"]["ltm_constraints"][0]["handle"] == "fact-1"
    assert payload["source_plan"]["ltm_constraints"][0]["memory_kind"] == "fact"


def test_orchestrator_can_reuse_runtime_manager_shared_services(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    client = FakeOpenMemoryClient()
    provider = OpenMemoryMemoryProvider(
        client,
        user_id="u-runtime",
        app="ace-lite",
        limit=3,
        channel_name="mcp",
    )
    db_path = tmp_path / "user-runtime" / "runtime-stats.db"
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
    )
    manager = RuntimeManager(
        config=config,
        memory_provider=provider,
        durable_stats_store_factory=lambda: DurableStatsStore(db_path=db_path),
    )
    first = AceOrchestrator(runtime_manager=manager)
    second = AceOrchestrator(runtime_manager=manager)

    first_payload = first.plan(
        query="first runtime-managed plan for auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )
    second_payload = second.plan(
        query="second runtime-managed plan for auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    runtime_state = manager.startup()
    assert first._runtime_state is runtime_state
    assert second._runtime_state is runtime_state
    assert first_payload["memory"]["channel_used"] == "mcp"
    assert second_payload["memory"]["channel_used"] == "mcp"
    assert (
        first_payload["observability"]["durable_stats"]["session_id"]
        == runtime_state.durable_stats_session_id
    )
    assert (
        second_payload["observability"]["durable_stats"]["session_id"]
        == runtime_state.durable_stats_session_id
    )

    store = DurableStatsStore(db_path=db_path)
    session = store.read_scope(
        scope_kind="session",
        scope_key=runtime_state.durable_stats_session_id,
    )
    assert session is not None
    assert session.to_payload()["counters"]["invocation_count"] == 2


def test_orchestrator_shutdown_runs_inline_gc_and_final_stats_flush(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    db_path = tmp_path / "user-runtime" / "runtime-stats.db"
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        plan_replay_cache={"enabled": True},
    )
    manager = RuntimeManager(
        config=config,
        durable_stats_store_factory=lambda: DurableStatsStore(db_path=db_path),
    )
    orchestrator = AceOrchestrator(runtime_manager=manager)
    orchestrator.plan(
        query="shutdown lifecycle for auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    cache = StageArtifactCache(repo_root=tmp_path)
    orphan = cache.temp_root / "source_plan" / "ab" / "abcdef.worker.json.tmp"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text('{"orphan": true}\n', encoding="utf-8")

    shutdown_payload = orchestrator.shutdown()

    assert shutdown_payload["shutdown"] is True
    assert orphan.exists() is False
    flush_result = next(
        item
        for item in shutdown_payload["results"]
        if item["hook"] == "_flush_runtime_stats_hook"
    )
    gc_result = next(
        item
        for item in shutdown_payload["results"]
        if item["hook"] == "_cleanup_stage_artifact_temps_hook"
    )
    assert flush_result["ok"] is True
    assert flush_result["result"]["skipped"] is False
    assert flush_result["result"]["invocation_count"] == 1
    assert gc_result["result"]["mode"] == "bounded_opportunistic"
    assert gc_result["result"]["budget_ms"] == 50.0
    assert gc_result["result"]["deleted_temp_payloads"] >= 1
    assert gc_result["ok"] is True
    assert gc_result["result"]["deleted_temp_payloads"] >= 1


def test_orchestrator_plan_replay_cache_hits_on_second_run(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        plan_replay_cache={
            "enabled": True,
            "cache_path": tmp_path / "context-map" / "plan-replay" / "cache.json",
        },
    )
    orchestrator = AceOrchestrator(memory_provider=None, config=config)

    first = orchestrator.plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )
    second = orchestrator.plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    first_cache = first["observability"]["plan_replay_cache"]
    second_cache = second["observability"]["plan_replay_cache"]

    assert first_cache["enabled"] is True
    assert first_cache["stage"] == "source_plan"
    assert first_cache["hit"] is False
    assert first_cache["stored"] is True
    assert first_cache["stale_hit_safe"] is True
    assert first_cache["reused_stages"] == []
    assert first_cache["origin"] == "stage_artifact_cache"
    assert first_cache["trust_class"] == "exact"
    assert first_cache["policy_name"] == "source_plan"

    assert second_cache["enabled"] is True
    assert second_cache["stage"] == "source_plan"
    assert second_cache["hit"] is True
    assert second_cache["safe_hit"] is True
    assert second_cache["stale_hit_safe"] is True
    assert second_cache["reused_stages"] == ["source_plan"]
    assert second_cache["origin"] == "stage_artifact_cache"
    assert second_cache["trust_class"] == "exact"
    assert second_cache["policy_name"] == "source_plan"
    assert float(second_cache["age_seconds"]) >= 0.0
    assert Path(second_cache["cache_path"]).exists()
    assert first["source_plan"] == second["source_plan"]
    assert first["repomap"] == second["repomap"]
    assert first["skills"]["selected"] == second["skills"]["selected"]
    assert first["skills"]["routing_source"] == second["skills"]["routing_source"]
    assert len(second["observability"]["stage_metrics"]) == 7
    assert second["observability"]["stage_metrics"][-1]["stage"] == "validation"


def test_orchestrator_plan_replay_cache_invalidates_when_budget_changes(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    cache_path = tmp_path / "context-map" / "plan-replay" / "cache.json"
    base_kwargs = {
        "skills": {"manifest": fake_skill_manifest},
        "index": {
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        "repomap": {"enabled": False},
        "plan_replay_cache": {
            "enabled": True,
            "cache_path": cache_path,
        },
    }

    first = AceOrchestrator(
        memory_provider=None,
        config=OrchestratorConfig(**base_kwargs),
    ).plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )
    second = AceOrchestrator(
        memory_provider=None,
        config=OrchestratorConfig(
            **base_kwargs,
            chunking={"top_k": 8},
        ),
    ).plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert first["observability"]["plan_replay_cache"]["stored"] is True
    assert second["observability"]["plan_replay_cache"]["hit"] is False
    assert second["observability"]["plan_replay_cache"]["reason"] == "miss"


def test_orchestrator_plan_replay_cache_invalidates_when_worktree_changes(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        plan_replay_cache={
            "enabled": True,
            "cache_path": tmp_path / "context-map" / "plan-replay" / "cache.json",
        },
    )
    orchestrator = AceOrchestrator(memory_provider=None, config=config)

    first = orchestrator.plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )
    (tmp_path / "src" / "app" / "auth.py").write_text(
        textwrap.dedent(
            """
            def validate_token(raw: str) -> bool:
                return bool(raw.strip())
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    second = orchestrator.plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert first["observability"]["plan_replay_cache"]["stored"] is True
    assert second["observability"]["plan_replay_cache"]["hit"] is False
    assert second["observability"]["plan_replay_cache"]["reason"] == "miss"


def test_orchestrator_augment_replay_fingerprint_ignores_runtime_elapsed_fields() -> None:
    payload = {
        "enabled": True,
        "reason": "ok",
        "diagnostics": [],
        "xref": {
            "count": 0,
            "results": [],
            "errors": [],
            "budget_exhausted": False,
            "elapsed_ms": 12.5,
        },
        "tests": {
            "enabled": False,
            "reason": "none",
            "failures": [],
            "stack_frames": [],
            "suspicious_chunks": [],
            "suggested_tests": [],
            "inputs": {
                "junit_xml": None,
                "failed_test_report": None,
                "coverage_json": None,
                "sbfl_json": None,
                "sbfl_metric": "ochiai",
                "report_format": "none",
            },
        },
        "vcs_history": {
            "enabled": True,
            "reason": "ok",
            "path_count": 1,
            "commit_count": 1,
            "commits": [
                {
                    "hash": "abc123",
                    "committed_at": "2026-03-10T00:00:00+00:00",
                    "author": "test-user",
                    "subject": "docs: update tracing guide",
                    "files": ["docs/maintainers/TRACING_EXPORT.md"],
                }
            ],
            "error": None,
            "elapsed_ms": 111.0,
            "timeout_seconds": 0.35,
            "limit": 12,
        },
        "vcs_worktree": {
            "enabled": True,
            "reason": "ok",
            "changed_count": 0,
            "staged_count": 0,
            "unstaged_count": 0,
            "untracked_count": 0,
            "entries": [],
            "diffstat": {
                "staged": {
                    "file_count": 0,
                    "binary_count": 0,
                    "additions": 0,
                    "deletions": 0,
                    "files": [],
                    "error": None,
                    "timed_out": False,
                    "truncated": False,
                },
                "unstaged": {
                    "file_count": 0,
                    "binary_count": 0,
                    "additions": 0,
                    "deletions": 0,
                    "files": [],
                    "error": None,
                    "timed_out": False,
                    "truncated": False,
                },
            },
            "error": None,
            "elapsed_ms": 222.0,
            "timeout_seconds": 0.35,
            "max_files": 48,
            "truncated": False,
        },
    }
    changed = json.loads(json.dumps(payload))
    changed["xref"]["elapsed_ms"] = 98.4
    changed["vcs_history"]["elapsed_ms"] = 7.2
    changed["vcs_worktree"]["elapsed_ms"] = 0.9

    first = AceOrchestrator._build_augment_replay_fingerprint(augment_payload=payload)
    second = AceOrchestrator._build_augment_replay_fingerprint(augment_payload=changed)

    assert first == second


def test_orchestrator_augment_replay_fingerprint_ignores_disabled_vcs_payload_shape_drift() -> None:
    payload = {
        "enabled": False,
        "reason": "disabled",
        "diagnostics": [],
        "xref": {
            "count": 0,
            "results": [],
            "errors": [],
            "budget_exhausted": False,
            "elapsed_ms": 0.0,
            "time_budget_ms": 1500,
        },
        "tests": {
            "enabled": False,
            "reason": "not_provided",
            "failures": [],
            "stack_frames": [],
            "suspicious_chunks": [],
            "suggested_tests": [],
            "inputs": {
                "junit_xml": None,
                "failed_test_report": None,
                "coverage_json": None,
                "sbfl_json": None,
                "sbfl_metric": "ochiai",
                "report_format": "none",
            },
        },
        "vcs_history": {
            "enabled": False,
            "reason": "disabled",
            "commit_count": 0,
            "commits": [],
            "error": "",
        },
        "vcs_worktree": {
            "enabled": False,
            "reason": "not_git_repo",
            "changed_count": 0,
            "staged_count": 0,
            "unstaged_count": 0,
            "untracked_count": 0,
            "entries": [],
            "diffstat": {
                "staged": {
                    "file_count": 0,
                    "binary_count": 0,
                    "additions": 0,
                    "deletions": 0,
                    "files": [],
                    "error": None,
                    "timed_out": False,
                    "truncated": False,
                },
                "unstaged": {
                    "file_count": 0,
                    "binary_count": 0,
                    "additions": 0,
                    "deletions": 0,
                    "files": [],
                    "error": None,
                    "timed_out": False,
                    "truncated": False,
                },
            },
        },
    }
    changed = json.loads(json.dumps(payload))
    changed["vcs_history"] = {
        "enabled": False,
        "reason": "disabled",
        "commit_count": 0,
        "commits": [],
        "error": "",
    }
    changed["vcs_worktree"] = {
        "enabled": False,
        "reason": "disabled",
        "changed_count": 0,
        "entries": [],
        "truncated": False,
        "error": "",
    }

    first = AceOrchestrator._build_augment_replay_fingerprint(augment_payload=payload)
    second = AceOrchestrator._build_augment_replay_fingerprint(augment_payload=changed)

    assert first == second


def test_orchestrator_agent_loop_reruns_incremental_retrieval_after_validation_signal(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        agent_loop={"enabled": True, "max_iterations": 1},
    )
    orchestrator = AceOrchestrator(memory_provider=None, config=config)

    index_queries: list[str] = []
    original_run_index = orchestrator._run_index

    def wrapped_run_index(*, ctx):
        index_queries.append(ctx.query)
        return original_run_index(ctx=ctx)

    def fake_run_validation(*, ctx):
        return {
            "enabled": True,
            "reason": "ok",
            "sandbox": {
                "enabled": True,
                "sandbox_root": str(tmp_path / "sandbox"),
                "patch_applied": True,
                "cleanup_ok": True,
                "restore_ok": False,
                "apply_result": {"ok": True, "reason": "ok"},
            },
            "diagnostics": [
                {
                    "path": "src/app/auth.py",
                    "language": "python",
                    "severity": "error",
                    "message": "invalid syntax",
                    "line": 1,
                    "column": 1,
                }
            ],
            "diagnostic_count": 1,
            "xref_enabled": False,
            "xref": {
                "count": 0,
                "results": [],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 0.0,
                "time_budget_ms": 0,
            },
            "result": build_validation_result_v1(
                syntax_issues=[
                    {
                        "code": "lsp.diagnostic",
                        "message": "invalid syntax",
                        "path": "src/app/auth.py",
                        "severity": "error",
                        "line": 1,
                        "column": 1,
                    }
                ],
                replay_key="",
                status="failed",
            ).as_dict(),
            "patch_artifact_present": True,
            "policy_name": "general",
            "policy_version": "v1",
        }

    monkeypatch.setattr(orchestrator, "_run_index", wrapped_run_index)
    monkeypatch.setattr(orchestrator, "_run_validation", fake_run_validation)

    payload = orchestrator.plan(
        query="draft auth plan",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    loop_summary = payload["observability"]["agent_loop"]
    assert loop_summary["enabled"] is True
    assert loop_summary["iteration_count"] == 1
    assert loop_summary["actions_executed"] == 1
    assert loop_summary["stop_reason"] == "max_iterations"
    assert len(index_queries) == 2
    assert index_queries[0] == "draft auth plan"
    assert "Focus refinement" in index_queries[1]

    rerun_index_metrics = [
        item
        for item in payload["observability"]["stage_metrics"]
        if item["stage"] == "index" and item["tags"].get("agent_loop_iteration") == 1
    ]
    assert len(rerun_index_metrics) == 1
    assert rerun_index_metrics[0]["tags"]["agent_loop_action"] == "request_more_context"


def test_multi_channel_rrf_fusion_promotes_memory_paths(
    tmp_path: Path, fake_skill_manifest: list[dict[str, Any]]
) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "main.py").write_text(
        textwrap.dedent(
            """
            def validate_token(raw: str) -> bool:
                return bool(raw)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "secondary.py").write_text(
        textwrap.dedent(
            """
            def token_only(raw: str) -> bool:
                return bool(raw)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    class MemoryPathClient:
        def search(
            self,
            *,
            query: str,
            user_id: str | None = None,
            app: str | None = None,
            limit: int = 5,
        ) -> dict[str, object]:
            _ = (query, user_id, app, limit)
            return {
                "results": [
                    {
                        "memory": "Secondary file is relevant to token flows.",
                        "score": 0.95,
                        "metadata": {
                            "path": str(tmp_path / "src" / "secondary.py"),
                        },
                    }
                ]
            }

    provider = OpenMemoryMemoryProvider(
        MemoryPathClient(),
        user_id="u-test",
        app="ace-lite",
        limit=3,
        channel_name="mcp",
    )
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": "heuristic",
            "min_candidate_score": 0,
            "top_k_files": 2,
            "multi_channel_rrf_enabled": True,
            "multi_channel_rrf_pool_cap": 16,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(memory_provider=provider, config=config)

    payload = orchestrator.plan(
        query="validate token",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    candidates = payload["index"]["candidate_files"]
    assert [row["path"] for row in candidates[:2]] == [
        "src/secondary.py",
        "src/main.py",
    ]
    assert payload["index"]["candidate_ranking"]["multi_channel_rrf_enabled"] is True
    assert payload["index"]["candidate_ranking"]["multi_channel_rrf_applied"] is True
    fusion = payload["index"]["multi_channel_fusion"]
    assert fusion["enabled"] is True
    assert fusion["applied"] is True
    assert fusion["channels"]["memory"]["count"] == 1


def test_cli_plan_outputs_json(tmp_path: Path, fake_skill_manifest: list[dict[str, Any]]) -> None:
    _seed_repo(tmp_path)
    skills_dir = Path(fake_skill_manifest[0]["path"]).parent
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "draft auth plan",
            "--repo",
            "ace-lite-engine",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--no-repomap",
        ],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["query"] == "draft auth plan"
    assert payload["repo"] == "ace-lite-engine"
    assert payload["pipeline_order"] == [
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
        "source_plan",
        "validation",
    ]
    assert payload["memory"]["channel_used"] == "none"
    assert payload["augment"]["enabled"] is False
    assert "source_plan" in payload


def _seed_ranker_repo(root: Path) -> None:
    (root / "src" / "core").mkdir(parents=True, exist_ok=True)

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
    (root / "src" / "core" / "session.py").write_text(
        textwrap.dedent(
            """
            from src.core.auth import validate_token

            def ensure_session(token: str) -> bool:
                return validate_token(token)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "core" / "cache.py").write_text(
        textwrap.dedent(
            """
            def put_cache(key: str, value: str) -> tuple[str, str]:
                return key, value
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "core" / "router.py").write_text(
        textwrap.dedent(
            """
            from src.core.session import ensure_session

            def route_request(token: str) -> bool:
                return ensure_session(token)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_extract_terms_plural_stemming() -> None:
    terms = extract_terms(query="rank files for query", memory_stage={})
    assert "files" in terms
    assert "fil" in terms

@pytest.mark.parametrize("candidate_ranker", ["heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid"])
def test_index_candidate_ranker_modes(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
    candidate_ranker: str,
) -> None:
    _seed_ranker_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": candidate_ranker,
            "min_candidate_score": 0,
            "top_k_files": 4,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(memory_provider=None, config=config)

    payload = orchestrator.plan(
        query="validate token session refresh auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    ranking = payload["index"]["candidate_ranking"]
    assert ranking["requested"] == candidate_ranker
    assert ranking["selected"] == candidate_ranker
    if candidate_ranker == "rrf_hybrid":
        assert ranking["fusion_mode"] == "rrf"
    elif candidate_ranker == "hybrid_re2":
        assert ranking["fusion_mode"] in {"linear", "rrf"}
    else:
        assert ranking["fusion_mode"] == "linear"
    assert payload["index"]["metadata"]["candidate_ranker"] == candidate_ranker
    assert isinstance(payload["index"]["candidate_files"], list)
    assert payload["index"]["candidate_files"]


def test_index_selection_fingerprint_is_stable_for_same_inputs(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_ranker_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": "rrf_hybrid",
            "min_candidate_score": 0,
            "top_k_files": 4,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(memory_provider=None, config=config)

    payload1 = orchestrator.plan(
        query="validate token session refresh auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )
    payload2 = orchestrator.plan(
        query="validate token session refresh auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    fp1 = payload1["index"]["metadata"].get("selection_fingerprint")
    fp2 = payload2["index"]["metadata"].get("selection_fingerprint")
    assert isinstance(fp1, str)
    assert fp1
    assert fp1 == fp2
    assert isinstance(payload1["index"].get("context_budget"), dict)


def test_index_candidate_ranker_tiny_corpus_fallback(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": "hybrid_re2",
            "min_candidate_score": 0,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="validate token",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    ranking = payload["index"]["candidate_ranking"]
    assert ranking["requested"] == "hybrid_re2"
    assert ranking["selected"] == "heuristic"
    assert "tiny_corpus" in ranking["fallbacks"]


def test_index_candidate_ranker_empty_retrieval_fallback(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_ranker_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": "bm25_lite",
            "min_candidate_score": 9,
            "top_k_files": 4,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="qzzzz_notfoundtoken_zzzz",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    ranking = payload["index"]["candidate_ranking"]
    assert ranking["requested"] == "bm25_lite"
    assert ranking["selected"] == "heuristic"
    assert "empty_retrieval" in ranking["fallbacks"]
    assert payload["index"]["candidate_files"]


def test_index_second_pass_retrieval_expands_low_recall(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_ranker_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": "heuristic",
            "min_candidate_score": 1,
            "candidate_relative_threshold": 0.95,
            "top_k_files": 4,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="validate token session refresh auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    ranking = payload["index"]["candidate_ranking"]
    second_pass = ranking["second_pass"]
    refine_pass = ranking["refine_pass"]
    assert second_pass["triggered"] is True
    assert second_pass["applied"] is True
    assert second_pass["reason"] == "low_candidate_count"
    assert second_pass["retry_ranker"] in {"hybrid_re2", "heuristic"}
    assert int(second_pass["candidate_count_after"]) > int(
        second_pass["candidate_count_before"]
    )
    assert refine_pass["enabled"] is True
    assert refine_pass["trigger_condition_met"] is True
    assert refine_pass["triggered"] is True
    assert refine_pass["reason"] == "low_candidate_count"


def test_index_can_disable_deterministic_refine_retry(
    tmp_path: Path,
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    _seed_ranker_repo(tmp_path)
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        retrieval={
            "candidate_ranker": "heuristic",
            "min_candidate_score": 1,
            "candidate_relative_threshold": 0.95,
            "top_k_files": 4,
            "deterministic_refine_enabled": False,
        },
        repomap={"enabled": False},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="validate token session refresh auth",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    ranking = payload["index"]["candidate_ranking"]
    second_pass = ranking["second_pass"]
    refine_pass = ranking["refine_pass"]
    assert second_pass["triggered"] is False
    assert refine_pass["enabled"] is False
    assert refine_pass["trigger_condition_met"] is True
    assert refine_pass["triggered"] is False
    assert refine_pass["reason"] == "disabled"
    assert len(payload["index"]["candidate_files"]) == 1


