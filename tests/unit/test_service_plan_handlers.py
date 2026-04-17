from __future__ import annotations

from pathlib import Path

from ace_lite.mcp_server.service_plan_handlers import (
    handle_plan_quick_request,
    handle_plan_request,
)


def test_handle_plan_request_sanitizes_report_only_artifacts_in_full_payload(
    tmp_path: Path,
) -> None:
    result = handle_plan_request(
        query="inspect planner",
        repo="demo",
        root_path=tmp_path,
        default_repo="demo",
        skills_path=tmp_path / "skills",
        config_pack_path=None,
        time_range=None,
        start_date=None,
        end_date=None,
        memory_primary=None,
        memory_secondary=None,
        lsp_enabled=False,
        plugins_enabled=False,
        top_k_files=8,
        min_candidate_score=2,
        retrieval_policy="auto",
        include_full_payload=True,
        timeout_seconds=5.0,
        default_timeout_seconds=25.0,
        run_plan_payload_fn=lambda *args, **kwargs: {
            "observability": {"total_ms": 12.5},
            "context_report": {"schema_version": "context_report_v1"},
            "source_plan": {
                "steps": [{"stage": "source_plan"}],
                "candidate_files": [{"path": "src/app.py"}],
                "retrieval_graph_view": {
                    "schema_version": "retrieval_graph_view_v1"
                },
            },
            "index": {
                "chunk_contract": {"schema_version": "chunk-v1"},
                "subgraph_payload": {
                    "payload_version": "subgraph-v1",
                    "taxonomy_version": "taxonomy-v1",
                },
            },
        },
        plan_quick_fn=lambda **kwargs: {},
    )

    assert result["ok"] is True
    assert result["candidate_files"] == 1
    assert result["repo_identity"]["repo_id"] == "demo"
    assert "context_report" not in result["plan"]
    assert "retrieval_graph_view" not in result["plan"]["source_plan"]


def test_plan_handlers_canonicalize_worktree_repo_identity(tmp_path: Path) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_root = repo_root / "tabiapp-backend_worktree_aeon_v2"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)

    quick = handle_plan_quick_request(
        query="shutdown config controller",
        repo="tabiapp-backend_worktree_aeon_v2",
        root_path=worktree_root,
        default_repo="tabiapp-backend_worktree_aeon_v2",
        language_csv="go",
        top_k_files=8,
        repomap_top_k=8,
        candidate_ranker="rrf_hybrid",
        index_cache_path="context-map/index.json",
        index_incremental=True,
        repomap_expand=False,
        repomap_neighbor_limit=20,
        repomap_neighbor_depth=1,
        budget_tokens=800,
        ranking_profile="graph",
        include_rows=False,
        tokenizer_model="gpt-4o-mini",
        build_plan_quick_fn=lambda **kwargs: {"candidate_files": [], "steps": []},
    )
    assert quick["repo"] == "tabiapp-backend"
    assert quick["repo_identity"]["worktree_name"] == "tabiapp-backend_worktree_aeon_v2"
    assert quick["repo_identity"]["repo_id"] == "tabiapp-backend"

    result = handle_plan_request(
        query="inspect planner",
        repo="tabiapp-backend_worktree_aeon_v2",
        root_path=worktree_root,
        default_repo="tabiapp-backend_worktree_aeon_v2",
        skills_path=worktree_root / "skills",
        config_pack_path=None,
        time_range=None,
        start_date=None,
        end_date=None,
        memory_primary=None,
        memory_secondary=None,
        lsp_enabled=False,
        plugins_enabled=False,
        top_k_files=8,
        min_candidate_score=2,
        retrieval_policy="auto",
        include_full_payload=False,
        timeout_seconds=5.0,
        default_timeout_seconds=25.0,
        run_plan_payload_fn=lambda *args, **kwargs: {
            "observability": {"total_ms": 12.5},
            "source_plan": {"steps": [], "candidate_files": []},
            "index": {"candidate_files": []},
        },
        plan_quick_fn=lambda **kwargs: {},
    )

    assert result["repo"] == "tabiapp-backend"
    assert result["repo_identity"]["repo_id"] == "tabiapp-backend"
    assert result["repo_identity"]["worktree_name"] == "tabiapp-backend_worktree_aeon_v2"
