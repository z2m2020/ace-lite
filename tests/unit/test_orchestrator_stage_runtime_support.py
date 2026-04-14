from __future__ import annotations

from types import SimpleNamespace

from ace_lite.orchestrator_stage_runtime_support import (
    precompute_orchestrator_skills_route,
    run_orchestrator_augment_stage,
    run_orchestrator_index_stage,
    run_orchestrator_repomap_stage,
    run_orchestrator_skills_stage,
    run_orchestrator_validation_stage,
)
from ace_lite.pipeline.types import StageContext


def test_run_orchestrator_index_stage_builds_index_config_and_executes(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_from_orchestrator_config(**kwargs):  # type: ignore[no-untyped-def]
        captured["config_kwargs"] = kwargs
        return "index-config"

    def fake_run_index(**kwargs):  # type: ignore[no-untyped-def]
        captured["run_index_kwargs"] = kwargs
        return {"stage": "index"}

    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.IndexStageConfig.from_orchestrator_config",
        fake_from_orchestrator_config,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.run_index",
        fake_run_index,
    )

    config = SimpleNamespace(name="cfg")
    ctx = StageContext(query="q", repo="repo", root="root", state={})

    result = run_orchestrator_index_stage(
        ctx=ctx,
        config=config,
        tokenizer_model="tok-model",
        cochange_neighbor_cap=8,
        cochange_min_neighbor_score=0.2,
        cochange_max_boost=0.9,
    )

    assert result == {"stage": "index"}
    assert captured["config_kwargs"] == {
        "config": config,
        "tokenizer_model": "tok-model",
        "cochange_neighbor_cap": 8,
        "cochange_min_neighbor_score": 0.2,
        "cochange_max_boost": 0.9,
    }
    assert captured["run_index_kwargs"] == {
        "ctx": ctx,
        "config": "index-config",
    }


def test_run_orchestrator_augment_stage_builds_payload_and_applies_policy(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_runtime(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {"ctx_state": {"augment": True}}
        return SimpleNamespace(
            index_stage={"candidate_files": [{"path": "src/a.py"}]},
            repomap_stage={"candidate_files": [{"path": "src/b.py"}]},
            index_files=[{"path": "src/a.py"}],
            candidate_chunks=[{"chunk": 1}],
            vcs_worktree_override="worktree",
            policy_name="strict",
            policy_version="",
        )

    def fake_resolve_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured["resolve_candidates_kwargs"] = kwargs
        return [{"path": "src/final.py"}]

    def fake_run_diagnostics_augment(**kwargs):  # type: ignore[no-untyped-def]
        captured["augment_kwargs"] = kwargs
        return {"stage": "augment"}

    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.build_orchestrator_augment_runtime",
        fake_build_runtime,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.resolve_augment_candidates",
        fake_resolve_candidates,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.run_diagnostics_augment",
        fake_run_diagnostics_augment,
    )

    config = SimpleNamespace(
        lsp=SimpleNamespace(
            enabled=True,
            top_n=5,
            xref_enabled=True,
            xref_top_n=3,
            time_budget_ms=125.0,
        ),
        tests=SimpleNamespace(
            junit_xml="junit.xml",
            coverage_json="coverage.json",
            sbfl_json="sbfl.json",
            sbfl_metric="ochiai",
        ),
        cochange=SimpleNamespace(enabled=True),
        retrieval=SimpleNamespace(policy_version="fallback-v3"),
    )
    ctx = StageContext(
        query="bug query",
        repo="demo-repo",
        root="demo-root",
        state={"augment": True},
    )

    result = run_orchestrator_augment_stage(
        ctx=ctx,
        config=config,
        lsp_broker="broker",
    )

    assert result == {
        "stage": "augment",
        "policy_name": "strict",
        "policy_version": "fallback-v3",
    }
    assert captured["resolve_candidates_kwargs"] == {
        "index_stage": {"candidate_files": [{"path": "src/a.py"}]},
        "repomap_stage": {"candidate_files": [{"path": "src/b.py"}]},
        "index_files": [{"path": "src/a.py"}],
    }
    assert captured["augment_kwargs"] == {
        "root": "demo-root",
        "query": "bug query",
        "index_stage": {"candidate_files": [{"path": "src/final.py"}]},
        "enabled": True,
        "top_n": 5,
        "broker": "broker",
        "xref_enabled": True,
        "xref_top_n": 3,
        "xref_time_budget_ms": 125.0,
        "candidate_chunks": [{"chunk": 1}],
        "junit_xml_path": "junit.xml",
        "coverage_json_path": "coverage.json",
        "sbfl_json_path": "sbfl.json",
        "sbfl_metric": "ochiai",
        "vcs_enabled": True,
        "vcs_worktree_override": "worktree",
    }


def test_run_orchestrator_skills_stage_builds_runtime_and_forwards_payload(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_runtime(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {
            "ctx_state": {"index": {"module_hint": "pkg.core"}},
            "precomputed_routing_enabled": True,
        }
        return SimpleNamespace(routed_payload={"route": True})

    def fake_run_skills(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"stage": "skills"}

    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.build_orchestrator_skills_runtime",
        fake_build_runtime,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.run_skills",
        fake_run_skills,
    )

    config = SimpleNamespace(
        skills=SimpleNamespace(
            precomputed_routing_enabled=True,
            top_n=6,
            token_budget=1200,
        )
    )
    ctx = StageContext(
        query="query",
        repo="repo",
        root="root",
        state={"index": {"module_hint": "pkg.core"}},
    )

    result = run_orchestrator_skills_stage(
        ctx=ctx,
        config=config,
        skill_manifest={"manifest": True},
    )

    assert result == {"stage": "skills"}
    assert captured == {
        "ctx": ctx,
        "skill_manifest": {"manifest": True},
        "top_n": 6,
        "token_budget": 1200,
        "routed_payload": {"route": True},
    }


def test_precompute_orchestrator_skills_route_builds_runtime_and_routes(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_runtime(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {
            "ctx_state": {"index": {"module_hint": "pkg.api"}},
            "precomputed_routing_enabled": False,
        }
        return SimpleNamespace(module_hint="pkg.api")

    def fake_route_skills(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"route": "done"}

    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.build_orchestrator_skills_runtime",
        fake_build_runtime,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.route_skills",
        fake_route_skills,
    )

    config = SimpleNamespace(
        skills=SimpleNamespace(
            precomputed_routing_enabled=False,
            top_n=4,
        )
    )
    ctx = StageContext(
        query="search query",
        repo="repo",
        root="root",
        state={"index": {"module_hint": "pkg.api"}},
    )

    result = precompute_orchestrator_skills_route(
        ctx=ctx,
        config=config,
        skill_manifest={"manifest": True},
    )

    assert result == {"route": "done"}
    assert captured == {
        "query": "search query",
        "module_hint": "pkg.api",
        "skill_manifest": {"manifest": True},
        "top_n": 4,
    }


def test_run_orchestrator_repomap_stage_forwards_runtime_config(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_repomap(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"stage": "repomap"}

    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.run_repomap",
        fake_run_repomap,
    )

    config = SimpleNamespace(
        repomap=SimpleNamespace(
            enabled=True,
            neighbor_limit=17,
            budget_tokens=2048,
            top_k=9,
            ranking_profile="balanced",
            signal_weights={"xref": 0.5},
        ),
        retrieval=SimpleNamespace(policy_version="v9"),
    )
    ctx = StageContext(query="q", repo="repo", root="root", state={})

    result = run_orchestrator_repomap_stage(
        ctx=ctx,
        config=config,
        tokenizer_model="tok-model",
    )

    assert result == {"stage": "repomap"}
    assert captured == {
        "ctx": ctx,
        "repomap_enabled": True,
        "repomap_neighbor_limit": 17,
        "repomap_budget_tokens": 2048,
        "repomap_top_k": 9,
        "repomap_ranking_profile": "balanced",
        "repomap_signal_weights": {"xref": 0.5},
        "tokenizer_model": "tok-model",
        "policy_version": "v9",
    }


def test_run_orchestrator_validation_stage_builds_runtime_and_forwards_store(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_runtime(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {"ctx_state": {"__policy": {"version": "ctx-v1"}}}
        return SimpleNamespace(
            source_plan_stage={"ok": True},
            index_stage={"index": True},
            policy_name="strict",
            policy_version="",
            patch_artifact={"patch": True},
        )

    def fake_run_validation_stage(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"stage": "validation"}

    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.build_orchestrator_validation_runtime",
        fake_build_runtime,
    )
    monkeypatch.setattr(
        "ace_lite.orchestrator_stage_runtime_support.run_validation_stage",
        fake_run_validation_stage,
    )

    config = SimpleNamespace(
        validation=SimpleNamespace(
            enabled=True,
            include_xref=False,
            top_n=4,
            xref_top_n=2,
            sandbox_timeout_seconds=30,
        ),
        retrieval=SimpleNamespace(policy_version="fallback-v2"),
    )
    ctx = StageContext(
        query="query",
        repo="demo-repo",
        root="demo-root",
        state={"__policy": {"version": "ctx-v1"}},
    )

    def resolve_store(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {"root": "demo-root"}
        return {"store": True}

    result = run_orchestrator_validation_stage(
        ctx=ctx,
        config=config,
        lsp_broker="broker",
        resolve_validation_preference_capture_store_fn=resolve_store,
    )

    assert result == {"stage": "validation"}
    assert captured == {
        "root": "demo-root",
        "query": "query",
        "source_plan_stage": {"ok": True},
        "index_stage": {"index": True},
        "enabled": True,
        "include_xref": False,
        "top_n": 4,
        "xref_top_n": 2,
        "sandbox_timeout_seconds": 30,
        "broker": "broker",
        "patch_artifact": {"patch": True},
        "policy_name": "strict",
        "policy_version": "fallback-v2",
        "preference_capture_store": {"store": True},
        "preference_capture_repo_key": "demo-repo",
    }
