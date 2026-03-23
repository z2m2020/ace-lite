from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from ace_lite.chunking.robust_signature import chunk_identity_key
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig


def _seed_repo(root: Path) -> None:
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


def test_chunk_guard_report_only_vs_enforce_changes_chunk_outputs(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    def _force_conflict_sidecar(
        *,
        candidate_chunks: list[dict[str, Any]],
        files_map: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        _ = files_map
        sidecar: dict[str, dict[str, Any]] = {}
        for chunk in candidate_chunks:
            key = chunk_identity_key(chunk=chunk)
            qualified_name = str(chunk.get("qualified_name") or "").strip()
            if not key or qualified_name not in {
                "validate_token",
                "refresh_session",
            }:
                continue
            sidecar[key] = {
                "available": True,
                "compatibility_domain": "auth-flow",
                "shape_hash": "shape-a"
                if qualified_name == "validate_token"
                else "shape-b",
                "entity_vocab": ("auth", "token", "session"),
            }
        return sidecar

    monkeypatch.setattr(
        "ace_lite.index_stage.chunk_selection.build_chunk_robust_signature_sidecar",
        _force_conflict_sidecar,
    )

    common_chunking = {
        "top_k": 8,
        "per_file_limit": 4,
        "token_budget": 256,
        "guard": {
            "enabled": True,
            "min_pool": 1,
            "lambda_penalty": 8.0,
            "min_marginal_utility": 0.5,
        },
    }

    report_only = AceOrchestrator(
        config=_base_config(
            tmp_path=tmp_path,
            fake_skill_manifest=fake_skill_manifest,
            repomap={"enabled": False},
            cochange={"enabled": False},
            scip={"enabled": False},
            chunking={
                **common_chunking,
                "guard": {
                    **common_chunking["guard"],
                    "mode": "report_only",
                },
            },
        )
    ).plan(query="validate token auth flow", repo="ace-lite-engine", root=str(tmp_path))

    enforce = AceOrchestrator(
        config=_base_config(
            tmp_path=tmp_path,
            fake_skill_manifest=fake_skill_manifest,
            repomap={"enabled": False},
            cochange={"enabled": False},
            scip={"enabled": False},
            chunking={
                **common_chunking,
                "guard": {
                    **common_chunking["guard"],
                    "mode": "enforce",
                },
            },
        )
    ).plan(query="validate token auth flow", repo="ace-lite-engine", root=str(tmp_path))

    report_index_chunks = [
        item.get("qualified_name")
        for item in report_only["index"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    enforce_index_chunks = [
        item.get("qualified_name")
        for item in enforce["index"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    report_source_chunks = [
        item.get("qualified_name")
        for item in report_only["source_plan"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    enforce_source_chunks = [
        item.get("qualified_name")
        for item in enforce["source_plan"]["candidate_chunks"]
        if isinstance(item, dict)
    ]

    assert report_only["index"]["chunk_guard"]["mode"] == "report_only"
    assert report_only["index"]["chunk_guard"]["filtered_count"] == 1
    assert report_only["index"]["chunk_guard"]["filtered_refs"] == ["refresh_session"]
    assert report_only["index"]["chunk_guard"]["fallback"] is False
    assert report_index_chunks == ["validate_token", "refresh_session"]
    assert "refresh_session" in report_index_chunks
    assert "refresh_session" in report_source_chunks

    assert enforce["index"]["chunk_guard"]["mode"] == "enforce"
    assert enforce["index"]["chunk_guard"]["reason"] == "enforce_applied"
    assert enforce["index"]["chunk_guard"]["filtered_count"] == 1
    assert enforce["index"]["chunk_guard"]["filtered_refs"] == ["refresh_session"]
    assert enforce["index"]["chunk_guard"]["fallback"] is False
    assert enforce_index_chunks == ["validate_token"]
    assert enforce_source_chunks == ["validate_token"]


def test_chunk_guard_enforce_fail_open_matches_report_only_outputs(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    common_chunking = {
        "top_k": 8,
        "per_file_limit": 4,
        "token_budget": 256,
        "guard": {
            "enabled": True,
            "min_pool": 99,
            "lambda_penalty": 4.0,
            "min_marginal_utility": 0.5,
        },
    }

    report_only = AceOrchestrator(
        config=_base_config(
            tmp_path=tmp_path,
            fake_skill_manifest=fake_skill_manifest,
            repomap={"enabled": False},
            cochange={"enabled": False},
            scip={"enabled": False},
            chunking={
                **common_chunking,
                "guard": {
                    **common_chunking["guard"],
                    "mode": "report_only",
                },
            },
        )
    ).plan(query="validate token auth flow", repo="ace-lite-engine", root=str(tmp_path))

    enforce = AceOrchestrator(
        config=_base_config(
            tmp_path=tmp_path,
            fake_skill_manifest=fake_skill_manifest,
            repomap={"enabled": False},
            cochange={"enabled": False},
            scip={"enabled": False},
            chunking={
                **common_chunking,
                "guard": {
                    **common_chunking["guard"],
                    "mode": "enforce",
                },
            },
        )
    ).plan(query="validate token auth flow", repo="ace-lite-engine", root=str(tmp_path))

    report_index_chunks = [
        item.get("qualified_name")
        for item in report_only["index"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    enforce_index_chunks = [
        item.get("qualified_name")
        for item in enforce["index"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    report_source_chunks = [
        item.get("qualified_name")
        for item in report_only["source_plan"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    enforce_source_chunks = [
        item.get("qualified_name")
        for item in enforce["source_plan"]["candidate_chunks"]
        if isinstance(item, dict)
    ]

    assert report_only["index"]["chunk_guard"]["reason"] == "pool_below_min"
    assert report_only["index"]["chunk_guard"]["fallback"] is False
    assert enforce["index"]["chunk_guard"]["reason"] == "pool_below_min"
    assert enforce["index"]["chunk_guard"]["fallback"] is True
    assert enforce_index_chunks == report_index_chunks
    assert enforce_source_chunks == report_source_chunks


def test_plan_emits_candidate_chunks_and_policy_tags(tmp_path: Path, fake_skill_manifest) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": True},
        cochange={"enabled": False},
        scip={"enabled": False},
        retrieval={"retrieval_policy": "bugfix_test"},
        chunking={
            "top_k": 8,
            "per_file_limit": 2,
            "token_budget": 256,
        },
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="pytest failure validate token flow",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    index_payload = payload["index"]
    source_plan = payload["source_plan"]
    repomap_payload = payload["repomap"]

    assert index_payload["policy_name"] == "bugfix_test"
    assert index_payload["candidate_files"]
    assert index_payload["candidate_files"][0]["why"].startswith("signals:")
    assert index_payload["candidate_chunks"]
    assert index_payload["candidate_chunks"][0]["why"].startswith("signals:")
    assert index_payload["chunk_metrics"]["candidate_chunk_count"] > 0

    assert source_plan["candidate_chunks"]
    assert source_plan["candidate_chunks"][0]["why"].startswith("signals:")
    assert source_plan["candidate_chunks"][0]["evidence"]["role"] == "direct"
    assert source_plan["candidate_chunks"][0]["evidence"]["direct_retrieval"] is True
    assert source_plan["evidence_summary"]["direct_count"] >= 1.0
    assert source_plan["evidence_summary"]["hint_only_count"] >= 0.0
    assert source_plan["chunk_steps"]
    first_step = source_plan["chunk_steps"][0]
    assert first_step["action"] == "Inspect chunk before opening full file"
    assert first_step["chunk_ref"]["path"]
    assert first_step["chunk_ref"]["evidence"]["role"] == source_plan["candidate_chunks"][0]["evidence"]["role"]
    assert first_step["reason"] == source_plan["candidate_chunks"][0]["why"]
    assert source_plan["chunk_budget_used"] >= 0.0
    assert source_plan["chunk_budget_limit"] == 256
    assert isinstance(source_plan["validation_tests"], list)
    assert source_plan["policy_name"] == "bugfix_test"

    assert repomap_payload["enabled"] is False
    assert repomap_payload["reason"] == "policy_disabled"
    assert repomap_payload["repomap_enabled_effective"] is False
    assert repomap_payload["neighbor_limit"] == 15
    assert repomap_payload["budget_tokens"] == 560

    stage_metrics = payload["observability"]["stage_metrics"]
    index_metric = next(item for item in stage_metrics if item["stage"] == "index")
    source_metric = next(item for item in stage_metrics if item["stage"] == "source_plan")

    assert index_metric["tags"]["policy_name"] == "bugfix_test"
    assert index_metric["tags"]["candidate_chunk_count"] >= 1
    assert source_metric["tags"]["candidate_chunk_count"] >= 1
    assert source_metric["tags"]["chunk_step_count"] >= 1
    assert source_metric["tags"]["chunk_budget_used"] >= 0.0
    assert source_metric["tags"]["validation_test_count"] == 0
    repomap_metric = next(item for item in stage_metrics if item["stage"] == "repomap")
    assert repomap_metric["tags"]["repomap_enabled_effective"] is False
    assert repomap_metric["tags"]["budget_tokens"] == 560
    assert repomap_metric["tags"]["ranking_profile"] == "graph"


def test_auto_policy_disables_cochange_in_index(tmp_path: Path, fake_skill_manifest) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": True},
        retrieval={"retrieval_policy": "auto"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="validate token behavior",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    cochange = payload["index"]["cochange"]
    assert payload["index"]["policy_name"] == "general"
    assert cochange["enabled"] is False
    assert cochange["cache_mode"] == "policy_disabled"


def test_explicit_feature_policy_keeps_cochange_enabled(tmp_path: Path, fake_skill_manifest) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": True},
        retrieval={"retrieval_policy": "feature"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="add association endpoint",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert payload["index"]["policy_name"] == "feature"
    assert payload["index"]["cochange"]["cache_mode"] in {"cache", "rebuilt", "memory", "git_unavailable"}



def test_auto_policy_enables_cochange_for_feature_intent(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": True},
        retrieval={"retrieval_policy": "auto"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="add association endpoint",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert payload["index"]["policy_name"] == "feature"
    assert payload["index"]["cochange"]["cache_mode"] != "policy_disabled"


def test_source_plan_validation_tests_from_failed_report(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    junit_path = reports / "junit.xml"
    junit_path.write_text(
        """
<testsuite tests="1" failures="1">
  <testcase classname="tests.test_auth" name="test_token_failure" file="src/core/auth.py" line="3">
    <failure message="assert false">Traceback\nFile "src/core/auth.py", line 4</failure>
  </testcase>
</testsuite>
""".strip(),
        encoding="utf-8",
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": False},
        cochange={"enabled": False},
        scip={"enabled": False},
        retrieval={"retrieval_policy": "bugfix_test"},
        chunking={
            "top_k": 8,
            "per_file_limit": 2,
            "token_budget": 256,
        },
        tests={
            "junit_xml": str(junit_path),
        },
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="pytest failure validate token flow",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    source_plan = payload["source_plan"]
    assert source_plan["validation_tests"]
    assert source_plan["validation_tests"][0] == "tests.test_auth::test_token_failure"


def test_auto_policy_definition_lookup_with_exception_prefers_general(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": True},
        cochange={"enabled": True},
        retrieval={"retrieval_policy": "auto"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="where RequestException class is defined in requests",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert payload["index"]["policy_name"] == "general"
    repomap = payload["repomap"]
    assert repomap["repomap_enabled_effective"] is True
    assert repomap["enabled"] is True
    assert repomap["ranking_profile"] == "graph_seeded"


def test_repomap_seed_observability_survives_orchestrator_cache_reuse(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": True},
        cochange={"enabled": False},
        scip={"enabled": False},
        retrieval={"retrieval_policy": "auto"},
    )
    orchestrator = AceOrchestrator(config=config)

    first = orchestrator.plan(
        query="where RequestException class is defined in requests",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )
    second = orchestrator.plan(
        query="where RequestException class is defined in requests",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    first_repomap = first["repomap"]
    second_repomap = second["repomap"]

    assert first_repomap["enabled"] is True
    assert first_repomap["ranking_profile"] == "graph_seeded"
    assert first_repomap["worktree_seed_count"] == 0
    assert first_repomap["subgraph_seed_count"] == 1
    assert first_repomap["seed_candidates_count"] == 1
    assert first_repomap["cache"]["hit"] is False
    assert first_repomap["precompute"]["hit"] is False

    assert second_repomap["enabled"] is True
    assert second_repomap["seed_paths"] == first_repomap["seed_paths"]
    assert second_repomap["worktree_seed_count"] == first_repomap["worktree_seed_count"]
    assert second_repomap["subgraph_seed_count"] == first_repomap["subgraph_seed_count"]
    assert second_repomap["seed_candidates_count"] == first_repomap["seed_candidates_count"]
    assert second_repomap["cache"]["hit"] is True
    assert second_repomap["precompute"]["hit"] is True

    first_repromap_metric = next(
        item for item in first["observability"]["stage_metrics"] if item["stage"] == "repomap"
    )
    second_repromap_metric = next(
        item for item in second["observability"]["stage_metrics"] if item["stage"] == "repomap"
    )

    assert first_repromap_metric["tags"]["worktree_seed_count"] == 0
    assert first_repromap_metric["tags"]["subgraph_seed_count"] == 1
    assert first_repromap_metric["tags"]["seed_candidates_count"] == 1
    assert first_repromap_metric["tags"]["cache_hit"] is False
    assert second_repromap_metric["tags"]["worktree_seed_count"] == 0
    assert second_repromap_metric["tags"]["subgraph_seed_count"] == 1
    assert second_repromap_metric["tags"]["seed_candidates_count"] == 1
    assert second_repromap_metric["tags"]["cache_hit"] is True


def test_repomap_profile_explicit_override_kept_under_auto_policy(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={
            "enabled": True,
            "ranking_profile": "heuristic",
        },
        cochange={"enabled": True},
        retrieval={"retrieval_policy": "auto"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="add association endpoint",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    repomap = payload["repomap"]
    assert payload["index"]["policy_name"] == "feature"
    assert repomap["enabled"] is True
    assert repomap["ranking_profile"] == "heuristic"


def test_auto_policy_doc_intent_emits_docs_signals(tmp_path: Path, fake_skill_manifest) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        """
# Auth Architecture
See `src/core/auth.py` for the main auth flow and retry behavior.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        repomap={"enabled": True},
        cochange={"enabled": True},
        retrieval={"retrieval_policy": "auto"},
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="how does auth architecture work and why retry matters",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    assert payload["index"]["policy_name"] == "doc_intent"
    docs_payload = payload["index"]["docs"]
    assert docs_payload["enabled"] is True
    assert docs_payload["section_count"] >= 1
    assert "src/core/auth.py" in docs_payload["hints"]["paths"]

