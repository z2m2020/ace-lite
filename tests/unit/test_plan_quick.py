from __future__ import annotations

from pathlib import Path

from ace_lite.indexer import build_index
from ace_lite.plan_quick import (
    PlanQuickScoredRow,
    _build_plan_quick_risk_hints,
    build_plan_quick,
    build_plan_quick_policy_observability,
    score_plan_quick_rows,
)
from ace_lite.repomap.ranking import rank_index_files
from ace_lite.retrieval_shared import CandidateSelectionResult


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_score_plan_quick_rows_rescores_and_sorts() -> None:
    rows = [
        {"path": "src/auth/token.py", "module": "auth.token", "language": "python", "score": 1.0},
        {
            "path": "src/auth/session.py",
            "module": "auth.session",
            "language": "python",
            "score": 3.0,
        },
        {"path": "src/other.py", "module": "misc", "language": "python", "score": 10.0},
    ]

    scored = score_plan_quick_rows(query="auth token", rows=rows, lexical_boost_per_hit=5.0)

    assert [row.path for row in scored] == [
        "src/auth/token.py",  # 1.0 + 2 hits * 5.0 = 11.0
        "src/other.py",  # 10.0 + 0 = 10.0
        "src/auth/session.py",  # 3.0 + 1 * 5.0 = 8.0
    ]
    assert scored[0].lexical_hits == 2
    assert scored[0].fused_score == 11.0


def test_score_plan_quick_rows_tiebreaks_by_path() -> None:
    rows = [
        {"path": "b.py", "module": "", "language": "python", "score": 1.0},
        {"path": "a.py", "module": "", "language": "python", "score": 1.0},
    ]

    scored = score_plan_quick_rows(query="missing", rows=rows, lexical_boost_per_hit=5.0)

    assert [row.path for row in scored] == ["a.py", "b.py"]


def test_score_plan_quick_rows_demotes_ace_lite_feedback_docs_for_repo_queries() -> None:
    rows = [
        {
            "path": "docs/ace_lite_repo_validation_feedback_2026-04-16.md",
            "module": "docs.feedback",
            "language": "markdown",
            "score": 9.0,
        },
        {
            "path": "internal/app/api/shutdown/allowlist.py",
            "module": "internal.app.api.shutdown.allowlist",
            "language": "python",
            "score": 7.5,
        },
        {
            "path": "internal/app/api/shutdown/controller.py",
            "module": "internal.app.api.shutdown.controller",
            "language": "python",
            "score": 7.0,
        },
    ]

    scored = score_plan_quick_rows(
        query="airdrop settings preview claim linked wallet shutdown D15 allowlist",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored[:2]] == [
        "internal/app/api/shutdown/allowlist.py",
        "internal/app/api/shutdown/controller.py",
    ]
    assert scored[-1].path == "docs/ace_lite_repo_validation_feedback_2026-04-16.md"


def test_score_plan_quick_rows_demotes_tmp_feedback_docs_for_code_intent_query() -> None:
    rows = [
        {
            "path": ".tmp/ace_lite_developer_feedback_2026-04-17.md",
            "module": ".tmp.feedback",
            "language": "markdown",
            "score": 9.0,
        },
        {
            "path": "src/ace_lite/validation/report_support.py",
            "module": "src.ace_lite.validation.report_support",
            "language": "python",
            "score": 7.0,
        },
    ]

    scored = score_plan_quick_rows(
        query="validation report_support.py selected_path root cause",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "src/ace_lite/validation/report_support.py",
        ".tmp/ace_lite_developer_feedback_2026-04-17.md",
    ]


def test_score_plan_quick_rows_demotes_task_docs_for_code_intent_query() -> None:
    rows = [
        {
            "path": ".codex/tasks/ace-lite/main/10_fix_feedback_observability_and_doc_pollution.md",
            "module": ".codex.tasks.feedback",
            "language": "markdown",
            "score": 8.5,
        },
        {
            "path": "src/ace_lite/cli_app/commands/feedback.py",
            "module": "src.ace_lite.cli_app.commands.feedback",
            "language": "python",
            "score": 7.0,
        },
    ]

    scored = score_plan_quick_rows(
        query="feedback.py command summary root option",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "src/ace_lite/cli_app/commands/feedback.py",
        ".codex/tasks/ace-lite/main/10_fix_feedback_observability_and_doc_pollution.md",
    ]


def test_score_plan_quick_rows_demotes_generic_docs_for_code_intent_query() -> None:
    rows = [
        {
            "path": "docs/config_test_comparison_report.md",
            "module": "docs.config_test_comparison_report",
            "language": "markdown",
            "score": 8.4,
        },
        {
            "path": "internal/app/api/shutdown/config.go",
            "module": "internal.app.api.shutdown.config",
            "language": "go",
            "score": 8.2,
        },
    ]

    scored = score_plan_quick_rows(
        query="shutdown config redis yaml auto phase fallback refresh status controller",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "internal/app/api/shutdown/config.go",
        "docs/config_test_comparison_report.md",
    ]
    assert scored[-1].intent_boost < 0.0


def test_score_plan_quick_rows_demotes_public_contract_docs_without_query_marker(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "ace_lite.plan_quick._query_flags",
        lambda _query: {
            "doc_sync": False,
            "code_intent": True,
            "latest_sensitive": False,
            "onboarding": False,
            "has_req_id": False,
            "req_ids": [],
        },
    )
    rows = [
        {
            "path": "docs/reference/ARCHITECTURE_OVERVIEW.md",
            "module": "docs.reference.architecture_overview",
            "language": "markdown",
            "score": 8.9,
        },
        {
            "path": "src/ace_lite/mcp_server/service_health.py",
            "module": "src.ace_lite.mcp_server.service_health",
            "language": "python",
            "score": 8.2,
        },
    ]

    scored = score_plan_quick_rows(
        query="health runtime source_root fingerprint mismatch",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "src/ace_lite/mcp_server/service_health.py",
        "docs/reference/ARCHITECTURE_OVERVIEW.md",
    ]
    assert scored[-1].intent_boost < 0.0


def test_score_plan_quick_rows_keeps_matching_schema_docs_for_explicit_contract_query(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "ace_lite.plan_quick._query_flags",
        lambda _query: {
            "doc_sync": False,
            "code_intent": True,
            "latest_sensitive": False,
            "onboarding": False,
            "has_req_id": False,
            "req_ids": [],
        },
    )
    rows = [
        {
            "path": "docs/reference/OPENAPI_SCHEMA.md",
            "module": "docs.reference.openapi_schema",
            "language": "markdown",
            "score": 8.4,
        },
        {
            "path": "src/ace_lite/plan_quick.py",
            "module": "src.ace_lite.plan_quick",
            "language": "python",
            "score": 8.2,
        },
    ]

    scored = score_plan_quick_rows(
        query="openapi schema parser contract mapping",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "docs/reference/OPENAPI_SCHEMA.md",
        "src/ace_lite/plan_quick.py",
    ]
    assert scored[0].intent_boost >= 0.0


def test_score_plan_quick_rows_uses_strategy_registries(monkeypatch) -> None:
    calls: dict[str, int] = {"intent": 0, "domain": 0, "doc_boost": 0, "latest_boost": 0}

    class FakeIntentRegistry:
        def detect_intent(self, query: str):
            calls["intent"] += 1
            assert query == "latest docs status"

            class Flags:
                doc_sync = True
                code_intent = False
                latest_sensitive = True
                onboarding = False
                has_req_id = False
                req_ids = ()

            return Flags()

    class FakeBoostRegistry:
        def calculate_doc_sync_boost(self, **kwargs):
            calls["doc_boost"] += 1
            assert kwargs["path"] == "docs/status.md"
            return 2.5

        def calculate_latest_doc_boost(self, **kwargs):
            calls["latest_boost"] += 1
            assert kwargs["context"]["newest_dated_doc"] is None
            return 1.25

    monkeypatch.setattr(
        "ace_lite.plan_quick.IntentStrategyRegistry.get_instance",
        lambda: FakeIntentRegistry(),
    )
    monkeypatch.setattr(
        "ace_lite.plan_quick.DomainStrategyRegistry.classify",
        lambda path: calls.__setitem__("domain", calls["domain"] + 1) or "docs",
    )
    monkeypatch.setattr(
        "ace_lite.plan_quick.BoostStrategyRegistry.get_instance",
        lambda: FakeBoostRegistry(),
    )

    scored = score_plan_quick_rows(
        query="latest docs status",
        rows=[
            {
                "path": "docs/status.md",
                "module": "docs.status",
                "language": "markdown",
                "score": 3.0,
            }
        ],
        lexical_boost_per_hit=0.0,
    )

    assert len(scored) == 1
    assert scored[0].semantic_domain == "docs"
    assert scored[0].intent_boost == 2.5
    assert scored[0].recency_boost == 1.25
    assert calls == {"intent": 1, "domain": 2, "doc_boost": 1, "latest_boost": 1}


def test_score_plan_quick_rows_biases_doc_sync_queries_toward_markdown_status_files() -> None:
    rows = [
        {
            "path": "src/runtime/indexer.py",
            "module": "src.runtime.indexer",
            "language": "python",
            "score": 7.0,
        },
        {
            "path": "docs/planning/repo-progress.md",
            "module": "docs.planning.repo_progress",
            "language": "markdown",
            "score": 5.5,
        },
        {
            "path": "research/notes.md",
            "module": "research.notes",
            "language": "markdown",
            "score": 6.5,
        },
    ]

    scored = score_plan_quick_rows(
        query="sync docs update latest progress",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "docs/planning/repo-progress.md",
        "src/runtime/indexer.py",
        "research/notes.md",
    ]
    assert scored[0].intent_boost > 0.0
    assert scored[-1].intent_boost < 0.0


def test_score_plan_quick_rows_boosts_newer_status_docs_for_latest_sensitive_query() -> None:
    rows = [
        {
            "path": "docs/planning/2026-03-25_status.md",
            "module": "docs.planning.current_status",
            "language": "markdown",
            "score": 5.0,
        },
        {
            "path": "docs/planning/2026-02-01_status.md",
            "module": "docs.planning.old_status",
            "language": "markdown",
            "score": 5.0,
        },
    ]

    scored = score_plan_quick_rows(
        query="latest status update",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "docs/planning/2026-03-25_status.md",
        "docs/planning/2026-02-01_status.md",
    ]
    assert scored[0].recency_boost > scored[1].recency_boost


def test_score_plan_quick_rows_skips_recency_boost_without_latest_marker() -> None:
    rows = [
        {
            "path": "docs/planning/2026-03-25_status.md",
            "module": "docs.planning.current_status",
            "language": "markdown",
            "score": 5.0,
        },
        {
            "path": "docs/planning/2026-02-01_status.md",
            "module": "docs.planning.old_status",
            "language": "markdown",
            "score": 5.0,
        },
    ]

    scored = score_plan_quick_rows(
        query="docs status",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert all(row.recency_boost == 0.0 for row in scored)


def test_score_plan_quick_rows_demotes_weekly_and_research_docs_for_docs_sync_latest_query() -> (
    None
):
    rows = [
        {
            "path": "docs/planning/2026-03-26_ERC-mandated-execution-sync-status.md",
            "module": "docs.planning.current_status",
            "language": "markdown",
            "score": 7.2,
        },
        {
            "path": "docs/planning/2026-03-23_repo-progress-sync.md",
            "module": "docs.planning.repo_progress",
            "language": "markdown",
            "score": 7.0,
        },
        {
            "path": "reports/2026-03-02_Weekly.md",
            "module": "reports.weekly",
            "language": "markdown",
            "score": 8.6,
        },
        {
            "path": "docs/research/2026-03-24_Report_Full-Lifecycle-ERC-Matrix.md",
            "module": "docs.research.erc_matrix",
            "language": "markdown",
            "score": 8.8,
        },
    ]

    scored = score_plan_quick_rows(
        query="contract repo sync docs update ERC mandated execution",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    ranked_paths = [row.path for row in scored]
    assert ranked_paths.index(
        "docs/planning/2026-03-26_ERC-mandated-execution-sync-status.md"
    ) < ranked_paths.index("reports/2026-03-02_Weekly.md")
    assert ranked_paths.index(
        "docs/planning/2026-03-23_repo-progress-sync.md"
    ) < ranked_paths.index("docs/research/2026-03-24_Report_Full-Lifecycle-ERC-Matrix.md")


def test_score_plan_quick_rows_prefers_docs_entrypoint_over_weekly_status_report() -> None:
    rows = [
        {
            "path": "docs/planning/README.md",
            "module": "docs.planning.readme",
            "language": "markdown",
            "score": 8.0,
        },
        {
            "path": "reports/2026-03-26_weekly_status_update.md",
            "module": "reports.weekly",
            "language": "markdown",
            "score": 8.0,
        },
    ]

    scored = score_plan_quick_rows(
        query="contract repo sync docs update latest status",
        rows=rows,
        lexical_boost_per_hit=0.0,
    )

    assert [row.path for row in scored] == [
        "docs/planning/README.md",
        "reports/2026-03-26_weekly_status_update.md",
    ]
    assert scored[0].intent_boost > scored[1].intent_boost
    assert scored[0].recency_boost > 0.0


def test_score_plan_quick_rows_applies_weekly_and_matrix_penalties_to_boosts() -> None:
    rows = [
        {
            "path": "docs/planning/2026-03-26_sync-update.md",
            "module": "docs.planning.sync_update",
            "language": "markdown",
            "score": 5.0,
        },
        {
            "path": "docs/planning/2026-03-26_weekly_sync-update.md",
            "module": "docs.planning.weekly_sync_update",
            "language": "markdown",
            "score": 5.0,
        },
        {
            "path": "docs/planning/2026-03-26_matrix_sync-update.md",
            "module": "docs.planning.matrix_sync_update",
            "language": "markdown",
            "score": 5.0,
        },
    ]

    scored = {
        row.path: row
        for row in score_plan_quick_rows(
            query="contract repo sync docs update latest status",
            rows=rows,
            lexical_boost_per_hit=0.0,
        )
    }

    baseline = scored["docs/planning/2026-03-26_sync-update.md"]
    weekly = scored["docs/planning/2026-03-26_weekly_sync-update.md"]
    matrix = scored["docs/planning/2026-03-26_matrix_sync-update.md"]

    assert weekly.intent_boost < baseline.intent_boost
    assert weekly.recency_boost < baseline.recency_boost
    assert matrix.intent_boost < baseline.intent_boost
    assert matrix.recency_boost < baseline.recency_boost


def test_score_plan_quick_rows_marks_docs_research_as_research_without_recency_boost() -> None:
    rows = [
        {
            "path": "docs/research/2026-03-24_Report_Full-Lifecycle-ERC-Matrix.md",
            "module": "docs.research.erc_matrix",
            "language": "markdown",
            "score": 6.5,
        },
        {
            "path": "docs/planning/2026-03-24_current-status.md",
            "module": "docs.planning.current_status",
            "language": "markdown",
            "score": 6.5,
        },
    ]

    scored = {
        row.path: row
        for row in score_plan_quick_rows(
            query="latest docs sync update status",
            rows=rows,
            lexical_boost_per_hit=0.0,
        )
    }

    research = scored["docs/research/2026-03-24_Report_Full-Lifecycle-ERC-Matrix.md"]
    planning = scored["docs/planning/2026-03-24_current-status.md"]

    assert research.semantic_domain == "research"
    assert research.recency_boost == 0.0
    assert planning.semantic_domain == "planning"
    assert planning.recency_boost > 0.0


def test_score_plan_quick_rows_treats_docs_reference_as_reference_with_recency_boost() -> None:
    rows = [
        {
            "path": "docs/reference/2026-03-24_upgrade-notes.md",
            "module": "docs.reference.upgrade_notes",
            "language": "markdown",
            "score": 6.5,
        },
        {
            "path": "docs/research/2026-03-24_upgrade-notes.md",
            "module": "docs.research.upgrade_notes",
            "language": "markdown",
            "score": 6.5,
        },
    ]

    scored = {
        row.path: row
        for row in score_plan_quick_rows(
            query="latest docs update notes",
            rows=rows,
            lexical_boost_per_hit=0.0,
        )
    }

    reference = scored["docs/reference/2026-03-24_upgrade-notes.md"]
    research = scored["docs/research/2026-03-24_upgrade-notes.md"]

    assert reference.semantic_domain == "reference"
    assert reference.recency_boost > 0.0
    assert research.semantic_domain == "research"
    assert research.recency_boost == 0.0
    assert reference.fused_score > research.fused_score


def test_score_plan_quick_rows_attaches_candidate_roles_and_labels() -> None:
    rows = [
        {
            "path": "src/demo/cli.py",
            "module": "demo.cli",
            "language": "python",
            "score": 4.0,
        },
        {
            "path": "docs/reference/EVAL_REPORT_SCHEMA.md",
            "module": "docs.reference.eval_report_schema",
            "language": "markdown",
            "score": 4.0,
        },
        {
            "path": "src/demo/sqlite_store.py",
            "module": "demo.sqlite_store",
            "language": "python",
            "score": 4.0,
        },
        {
            "path": "tests/test_cli.py",
            "module": "tests.test_cli",
            "language": "python",
            "score": 4.0,
        },
    ]

    scored = {
        row.path: row
        for row in score_plan_quick_rows(
            query="onboarding codebase where to start",
            rows=rows,
            lexical_boost_per_hit=0.0,
        )
    }

    assert scored["src/demo/cli.py"].role == "entrypoint"
    assert "entrypoint" in scored["src/demo/cli.py"].labels
    assert scored["docs/reference/EVAL_REPORT_SCHEMA.md"].role == "public_contract"
    assert "public_contract" in scored["docs/reference/EVAL_REPORT_SCHEMA.md"].labels
    assert scored["src/demo/sqlite_store.py"].role == "persistence_layer"
    assert "persistence_layer" in scored["src/demo/sqlite_store.py"].labels
    assert scored["tests/test_cli.py"].role == "test_entry"
    assert "test_entry" in scored["tests/test_cli.py"].labels


def test_build_index_marks_generated_files(tmp_path: Path) -> None:
    _write_file(
        tmp_path / "pkg/contract/erc20_generated.py",
        "\n".join(
            [
                "# Code generated by abigen. DO NOT EDIT.",
                "",
                "def erc20_transfer():",
                "    return 1",
                "",
            ]
        ),
    )
    _write_file(
        tmp_path / "internal/app/api/shutdown/allowlist.py",
        "\n".join(
            [
                "def allowlist_enabled():",
                "    return True",
                "",
            ]
        ),
    )

    payload = build_index(tmp_path, languages=["python"])
    files = payload.get("files", {})
    assert isinstance(files, dict)
    assert files["pkg/contract/erc20_generated.py"]["generated"] is True
    assert files["internal/app/api/shutdown/allowlist.py"]["generated"] is False


def test_build_plan_quick_prefers_business_logic_over_generated(tmp_path: Path) -> None:
    business_symbols = "\n".join(
        [
            "def shutdown_middleware():\n    return True\n",
            "def allowlist_route():\n    return True\n",
            "def blocklist_route():\n    return True\n",
        ]
    )
    _write_file(
        tmp_path / "internal/app/api/shutdown/allowlist.py",
        business_symbols,
    )

    generated_symbols = "\n".join([f"def generated_fn_{i}():\n    return {i}\n" for i in range(40)])
    _write_file(
        tmp_path / "pkg/contract/erc20_generated.py",
        "\n".join(["# Code generated by tool. DO NOT EDIT.", "", generated_symbols]),
    )

    result = build_plan_quick(
        query="shutdown allowlist middleware",
        root=tmp_path,
        languages="python",
        top_k_files=5,
        repomap_top_k=24,
    )
    assert result["ranking_source"] == "ranker"
    assert result["candidate_ranker"] == "rrf_hybrid"
    assert isinstance(result.get("index_cache"), dict)
    assert result["candidate_files"]
    assert result["candidate_files"][0].endswith("internal/app/api/shutdown/allowlist.py")

    contract_query = build_plan_quick(
        query="erc20 contract binding",
        root=tmp_path,
        languages="python",
        top_k_files=5,
        repomap_top_k=24,
    )
    assert contract_query["candidate_files"]
    assert contract_query["candidate_files"][0].startswith("pkg/contract/")

    assert isinstance(contract_query.get("index_cache"), dict)
    assert contract_query["index_cache"].get("cache_hit") is True
    assert contract_query["index_cache"].get("mode") == "cache_only"

    assert result["candidate_files"] != contract_query["candidate_files"]


def test_build_plan_quick_repomap_expand_includes_stage_payload(tmp_path: Path) -> None:
    _write_file(tmp_path / "src/app.py", "def shutdown_middleware():\n    return True\n")
    _write_file(tmp_path / "src/other.py", "def helper():\n    return 1\n")

    result = build_plan_quick(
        query="shutdown middleware",
        root=tmp_path,
        languages="python",
        top_k_files=3,
        repomap_top_k=8,
        repomap_expand=True,
        repomap_neighbor_limit=10,
        repomap_neighbor_depth=1,
    )
    assert result["ranking_source"] in {"ranker", "repomap"}
    assert isinstance(result.get("repomap_stage"), (dict, type(None)))
    # In tiny repos neighbor_paths may be empty, but stage payload should exist.
    assert isinstance(result.get("repomap_stage"), dict)
    assert isinstance(result["repomap_stage"].get("seed_paths"), list)
    assert isinstance(result["repomap_stage"].get("neighbor_paths"), list)


def test_build_plan_quick_candidate_ranker_option(tmp_path: Path) -> None:
    _write_file(tmp_path / "src/auth/token.py", "def token_auth():\n    return True\n")
    _write_file(tmp_path / "src/auth/session.py", "def session_auth():\n    return True\n")
    _write_file(tmp_path / "src/misc.py", "def other():\n    return 1\n")

    bm25 = build_plan_quick(
        query="auth token",
        root=tmp_path,
        languages="python",
        top_k_files=3,
        repomap_top_k=12,
        candidate_ranker="bm25_lite",
    )
    assert bm25["ranking_source"] == "ranker"
    assert bm25["candidate_ranker"] == "bm25_lite"
    assert bm25["candidate_files"]


def test_build_plan_quick_policy_observability_uses_shared_policy_resolution(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_retrieval_policy(**kwargs):
        captured.update(kwargs)
        return {
            "name": "doc_intent",
            "source": "auto",
            "version": "v1",
            "embedding_enabled": True,
            "docs_enabled": True,
            "repomap_enabled": True,
            "graph_lookup_enabled": False,
            "chunk_semantic_rerank_enabled": True,
            "semantic_rerank_time_budget_ms": 120,
        }

    monkeypatch.setattr(
        "ace_lite.plan_quick.resolve_retrieval_policy",
        fake_resolve_retrieval_policy,
    )

    profile, payload = build_plan_quick_policy_observability(
        query="how architecture works",
    )

    assert profile == "doc_intent"
    assert payload == {
        "requested": "auto",
        "selected": "doc_intent",
        "source": "auto",
        "version": "v1",
        "embedding_enabled": True,
        "docs_enabled": True,
        "repomap_enabled": True,
        "graph_lookup_enabled": False,
        "chunk_semantic_rerank_enabled": True,
        "semantic_rerank_time_budget_ms": 120,
    }
    assert captured == {
        "query": "how architecture works",
        "retrieval_policy": "auto",
        "policy_version": "v1",
        "cochange_enabled": True,
        "embedding_enabled": True,
    }


def test_build_plan_quick_uses_shared_candidate_selection(monkeypatch, tmp_path: Path) -> None:
    _write_file(tmp_path / "src/app.py", "def auth_token():\n    return True\n")
    captured: dict[str, object] = {}

    class FakeRuntimeProfile:
        top_k_files = 8

        def selection_kwargs(self, *, corpus_size: int) -> dict[str, object]:
            captured["corpus_size"] = corpus_size
            return {
                "candidate_ranker": "rrf_hybrid",
                "min_candidate_score": 1,
                "top_k_files": 8,
                "corpus_size": corpus_size,
                "hybrid_fusion_mode": "linear",
                "hybrid_rrf_k": 60,
                "hybrid_weights": {},
                "index_hash": None,
                "allow_empty_terms_fail_open": False,
            }

    def fake_build_retrieval_runtime_profile(**kwargs):
        captured["profile_kwargs"] = kwargs
        return FakeRuntimeProfile()

    monkeypatch.setattr(
        "ace_lite.plan_quick.build_retrieval_runtime_profile",
        fake_build_retrieval_runtime_profile,
    )

    def fake_select_initial_candidates(**kwargs):
        assert kwargs["candidate_ranker"] == "rrf_hybrid"
        assert kwargs["allow_empty_terms_fail_open"] is False
        return CandidateSelectionResult(
            requested_ranker="rrf_hybrid",
            selected_ranker="heuristic",
            min_score_used=1,
            fallback_reasons=["tiny_corpus"],
            candidates=[
                {
                    "path": "src/app.py",
                    "module": "src.app",
                    "language": "python",
                    "score": 3.0,
                }
            ],
        )

    monkeypatch.setattr(
        "ace_lite.plan_quick.select_initial_candidates", fake_select_initial_candidates
    )

    result = build_plan_quick(
        query="auth token",
        root=tmp_path,
        languages="python",
        top_k_files=3,
        repomap_top_k=8,
        candidate_ranker="rrf_hybrid",
    )

    assert result["ranking_source"] == "ranker"
    assert result["candidate_ranker"] == "rrf_hybrid"
    assert result["candidate_ranker_selected"] == "heuristic"
    assert result["candidate_ranker_fallbacks"] == ["tiny_corpus"]
    assert result["candidate_min_score_used"] == 1
    assert result["candidate_files"] == ["src/app.py"]
    assert captured["profile_kwargs"] == {
        "candidate_ranker": "rrf_hybrid",
        "min_candidate_score": 1,
        "top_k_files": 8,
        "hybrid_fusion_mode": "linear",
        "hybrid_rrf_k": 60,
        "hybrid_weights": {},
        "index_hash": None,
        "allow_empty_terms_fail_open": False,
    }
    assert captured["corpus_size"] == 1


def test_build_plan_quick_includes_retrieval_policy_observability(tmp_path: Path) -> None:
    _write_file(tmp_path / "docs/architecture.md", "System architecture overview\n")

    result = build_plan_quick(
        query="how architecture works",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=3,
        repomap_top_k=8,
    )

    assert result["retrieval_policy_profile"] == "doc_intent"
    assert result["retrieval_policy_observability"] == {
        "requested": "auto",
        "selected": "doc_intent",
        "source": "auto",
        "version": "v1",
        "embedding_enabled": True,
        "docs_enabled": True,
        "repomap_enabled": True,
        "graph_lookup_enabled": False,
        "chunk_semantic_rerank_enabled": True,
        "semantic_rerank_time_budget_ms": 120,
    }


def test_build_plan_quick_adds_query_profile_risk_hints_and_full_build_reason(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path / "docs/planning/current-status.md", "Current rollout status\n")
    _write_file(tmp_path / "src/runtime/indexer.py", "def refresh_index():\n    return True\n")
    _write_file(tmp_path / "research/notes.md", "historic note\n")

    result = build_plan_quick(
        query="sync docs update latest status",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=5,
        repomap_top_k=8,
    )

    assert result["query_profile"]["doc_sync"] is True
    assert result["query_profile"]["latest_sensitive"] is True
    assert result["query_profile"]["onboarding"] is False
    assert "has_req_id" in result["query_profile"]
    assert "req_ids" in result["query_profile"]
    assert result["candidate_domain_summary"]["primary_domain"] == "planning"
    assert result["candidate_details"][0]["role"] == "public_contract"
    assert "public_contract" in result["candidate_details"][0]["labels"]
    assert result["upgrade_recommended"] is False
    assert result["expected_incremental_value"] == "low"
    assert isinstance(result["expected_cost_ms_band"]["min"], int)
    assert result["why_not_plan_yet"]
    assert isinstance(result["candidate_domain_summary"]["cross_domain_mix"], bool)
    assert result["candidate_domain_summary"]["domain_counts"]["planning"] >= 1
    assert len(result["suggested_query_refinements"]) >= 1
    assert result["suggested_query_refinements"][0]["reason_code"] == "docs_status_focus"
    assert "docs" in result["suggested_query_refinements"][0]["target_domains"]
    assert "planning" in result["suggested_query_refinements"][0]["query"]
    assert isinstance(result["risk_hints"], list)
    assert any(item["code"] == "index_cold_start" for item in result["risk_hints"])
    assert result["index_cache"]["full_build_reason"] == "cache_missing"


def test_build_plan_quick_keeps_code_queries_out_of_doc_intent_and_feedback_docs(
    tmp_path: Path,
) -> None:
    _write_file(
        tmp_path / "internal/app/api/shutdown/config.go",
        "package shutdown\n\nfunc LoadConfig() bool {\n\treturn true\n}\n",
    )
    _write_file(
        tmp_path / "internal/app/api/shutdown/controller.go",
        "package shutdown\n\nfunc HandleShutdown() bool {\n\treturn true\n}\n",
    )
    _write_file(
        tmp_path / "internal/app/api/shutdown/phase.go",
        'package shutdown\n\nfunc AutoPhase() string {\n\treturn "refresh"\n}\n',
    )
    _write_file(
        tmp_path / "docs/ace_lite_repo_validation_feedback_2026-04-16.md",
        "# Repo validation feedback\nshutdown config controller phase refresh\n",
    )

    result = build_plan_quick(
        query="shutdown config.go controller.go phase.go auto_phase refresh",
        root=tmp_path,
        languages="go,markdown",
        top_k_files=5,
        repomap_top_k=16,
    )

    assert result["retrieval_policy_profile"] == "general"
    assert result["query_profile"]["code_intent"] is True
    assert result["query_profile"]["doc_sync"] is False
    assert result["suggested_query_refinements"] == []
    assert all(path.endswith(".go") for path in result["candidate_files"][:3])
    assert (
        "docs/ace_lite_repo_validation_feedback_2026-04-16.md" not in result["candidate_files"][:3]
    )


def test_build_plan_quick_emits_onboarding_view_candidate_details_and_upgrade_guidance(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path / "src/hypergraph_memory_lab/cli.py", "def main():\n    return 0\n")
    _write_file(
        tmp_path / "docs/reference/HYPEREDGE_SCHEMA.md",
        "# Hyperedge schema\n",
    )
    _write_file(
        tmp_path / "src/hypergraph_memory_lab/sqlite_store.py",
        "class SQLiteStore:\n    pass\n",
    )
    _write_file(tmp_path / "tests/test_cli.py", "def test_main():\n    assert True\n")

    result = build_plan_quick(
        query="repository onboarding where to start understanding the codebase",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=4,
        repomap_top_k=8,
    )

    assert result["query_profile"]["onboarding"] is True
    assert result["onboarding_view"]["recommended"] is True
    assert result["onboarding_view"]["mode"] == "repository_onboarding"
    assert "src/hypergraph_memory_lab/cli.py" in result["onboarding_view"]["entrypoints"]
    assert "docs/reference/HYPEREDGE_SCHEMA.md" in result["onboarding_view"]["public_contracts"]
    assert "src/hypergraph_memory_lab/sqlite_store.py" in result["onboarding_view"]["runtime_core"]
    assert "tests/test_cli.py" in result["onboarding_view"]["tests"]
    assert result["upgrade_recommended"] is False
    assert result["expected_incremental_value"] == "low"
    assert result["why_not_plan_yet"]

    details = {item["path"]: item for item in result["candidate_details"]}
    assert "entrypoint" in details["src/hypergraph_memory_lab/cli.py"]["labels"]
    assert "public_contract" in details["docs/reference/HYPEREDGE_SCHEMA.md"]["labels"]
    assert "persistence_layer" in details["src/hypergraph_memory_lab/sqlite_store.py"]["labels"]
    assert "test_entry" in details["tests/test_cli.py"]["labels"]
    assert result["onboarding_view"]["recommended_read_order"]


def test_build_plan_quick_emits_history_summary_and_candidate_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_file(tmp_path / "src/ace_lite/cli.py", "def main():\n    return 0\n")
    _write_file(tmp_path / "src/ace_lite/orchestrator.py", "class Orchestrator:\n    pass\n")

    monkeypatch.setattr(
        "ace_lite.plan_quick_ranking.collect_git_commit_history",
        lambda **kwargs: {
            "enabled": True,
            "reason": "ok",
            "commit_count": 2,
            "commits": [
                {
                    "hash": "abc123",
                    "committed_at": "2026-04-15T12:00:00+00:00",
                    "subject": "touch cli and orchestrator",
                    "files": [
                        "src/ace_lite/cli.py",
                        "src/ace_lite/orchestrator.py",
                    ],
                },
                {
                    "hash": "def456",
                    "committed_at": "2026-04-14T12:00:00+00:00",
                    "subject": "touch orchestrator",
                    "files": ["src/ace_lite/orchestrator.py"],
                },
            ],
            "error": None,
        },
    )

    result = build_plan_quick(
        query="orchestrator cli routing",
        root=tmp_path,
        languages="python",
        top_k_files=2,
        repomap_top_k=6,
    )

    assert result["history_summary"]["enabled"] is True
    assert result["history_summary"]["reason"] == "ok"
    assert result["history_summary"]["commit_count"] == 2
    assert result["history_summary"]["top_paths"][0]["path"] == "src/ace_lite/orchestrator.py"
    details = {item["path"]: item for item in result["candidate_details"]}
    assert details["src/ace_lite/orchestrator.py"]["history"]["commit_count"] == 2
    assert details["src/ace_lite/cli.py"]["history"]["commit_count"] == 1


def test_build_plan_quick_adds_secondary_doc_mix_risk_hint_for_docs_sync_query(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path / "docs/planning/2026-03-26_sync-status.md", "Current sync status\n")
    _write_file(tmp_path / "docs/planning/2026-03-20_repo-progress.md", "Repo progress snapshot\n")
    _write_file(tmp_path / "reports/2026-03-02_Weekly.md", "Weekly status note\n")
    _write_file(
        tmp_path / "docs/research/2026-03-24_Report_Full-Lifecycle-ERC-Matrix.md",
        "Deep research note\n",
    )

    result = build_plan_quick(
        query="contract repo sync docs update ERC mandated execution",
        root=tmp_path,
        languages="markdown",
        top_k_files=4,
        repomap_top_k=8,
    )

    assert isinstance(result["risk_hints"], list)
    assert any(item["code"] == "secondary_doc_mix" for item in result["risk_hints"])


def test_build_plan_quick_risk_hints_flags_secondary_doc_mix_within_visible_rows() -> None:
    rows = [
        PlanQuickScoredRow(
            path=f"docs/planning/2026-03-{day:02d}_sync-status.md",
            module=f"docs.planning.sync_{day}",
            language="markdown",
            score=10.0 - (day * 0.1),
            lexical_hits=0,
            lexical_boost=0.0,
            intent_boost=8.0,
            recency_boost=4.0,
            semantic_domain="planning",
            fused_score=22.0 - (day * 0.1),
            labels=("public_contract", "planning"),
            role="public_contract",
        )
        for day in range(1, 8)
    ]
    rows.append(
        PlanQuickScoredRow(
            path="reports/2026-03-02_Weekly.md",
            module="reports.weekly",
            language="markdown",
            score=6.0,
            lexical_hits=0,
            lexical_boost=0.0,
            intent_boost=1.0,
            recency_boost=0.0,
            semantic_domain="reports",
            fused_score=7.0,
            labels=("reports",),
            role="reports",
        )
    )

    hints = _build_plan_quick_risk_hints(
        query="contract repo sync docs update ERC mandated execution",
        rows=rows,
        retrieval_policy_profile="doc_intent",
        index_cache={},
    )

    assert any(item["code"] == "secondary_doc_mix" for item in hints)


def test_build_plan_quick_risk_hints_skips_secondary_doc_mix_for_non_doc_sync_query() -> None:
    rows = [
        PlanQuickScoredRow(
            path="docs/planning/2026-03-26_sync-status.md",
            module="docs.planning.sync_status",
            language="markdown",
            score=10.0,
            lexical_hits=0,
            lexical_boost=0.0,
            intent_boost=8.0,
            recency_boost=4.0,
            semantic_domain="planning",
            fused_score=22.0,
            labels=("public_contract", "planning"),
            role="public_contract",
        ),
        PlanQuickScoredRow(
            path="reports/2026-03-02_Weekly.md",
            module="reports.weekly",
            language="markdown",
            score=6.0,
            lexical_hits=0,
            lexical_boost=0.0,
            intent_boost=1.0,
            recency_boost=0.0,
            semantic_domain="reports",
            fused_score=7.0,
            labels=("reports",),
            role="reports",
        ),
    ]

    hints = _build_plan_quick_risk_hints(
        query="why build failed in pipeline",
        rows=rows,
        retrieval_policy_profile="doc_intent",
        index_cache={},
    )

    assert all(item["code"] != "secondary_doc_mix" for item in hints)


def test_build_plan_quick_risk_hints_skips_secondary_doc_mix_outside_visible_rows() -> None:
    rows = [
        PlanQuickScoredRow(
            path=f"docs/planning/2026-03-{day:02d}_sync-status.md",
            module=f"docs.planning.sync_{day}",
            language="markdown",
            score=10.0 - (day * 0.1),
            lexical_hits=0,
            lexical_boost=0.0,
            intent_boost=8.0,
            recency_boost=4.0,
            semantic_domain="planning",
            fused_score=22.0 - (day * 0.1),
            labels=("public_contract", "planning"),
            role="public_contract",
        )
        for day in range(1, 9)
    ]
    rows.append(
        PlanQuickScoredRow(
            path="reports/2026-03-02_Weekly.md",
            module="reports.weekly",
            language="markdown",
            score=6.0,
            lexical_hits=0,
            lexical_boost=0.0,
            intent_boost=1.0,
            recency_boost=0.0,
            semantic_domain="reports",
            fused_score=7.0,
            labels=("reports",),
            role="reports",
        )
    )

    hints = _build_plan_quick_risk_hints(
        query="contract repo sync docs update ERC mandated execution",
        rows=rows,
        retrieval_policy_profile="doc_intent",
        index_cache={},
    )

    assert all(item["code"] != "secondary_doc_mix" for item in hints)


def test_build_plan_quick_preserves_repomap_fallback_when_selection_is_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_file(tmp_path / "src/fallback.py", "def fallback_target():\n    return True\n")

    monkeypatch.setattr(
        "ace_lite.plan_quick.select_initial_candidates",
        lambda **kwargs: CandidateSelectionResult(
            requested_ranker="heuristic",
            selected_ranker="heuristic",
            min_score_used=1,
            fallback_reasons=[],
            candidates=[],
        ),
    )

    monkeypatch.setattr(
        "ace_lite.plan_quick.build_repo_map",
        lambda **kwargs: {
            "files": [
                {
                    "path": "src/fallback.py",
                    "module": "src.fallback",
                    "language": "python",
                    "score": 1.0,
                }
            ],
            "used_tokens": 17,
            "budget_tokens": 128,
            "ranking_profile": "graph",
        },
    )

    result = build_plan_quick(
        query="missing target",
        root=tmp_path,
        languages="python",
        top_k_files=3,
        repomap_top_k=8,
        budget_tokens=128,
    )

    assert result["ranking_source"] == "repomap"
    assert result["candidate_files"] == ["src/fallback.py"]


def test_build_plan_quick_emits_onboarding_view_and_grouped_read_order(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path / "src/ace_lite/cli.py", "def main():\n    return 0\n")
    _write_file(
        tmp_path / "docs/reference/ARCHITECTURE_OVERVIEW.md",
        "Architecture overview\n",
    )
    _write_file(
        tmp_path / "src/ace_lite/orchestrator.py",
        "class Orchestrator:\n    pass\n",
    )
    _write_file(tmp_path / "tests/test_cli.py", "def test_cli():\n    assert True\n")

    result = build_plan_quick(
        query="familiarize this codebase and tell me where to start",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=4,
        repomap_top_k=8,
    )

    assert result["query_profile"]["onboarding"] is True
    assert result["onboarding_view"]["recommended"] is True
    assert result["onboarding_view"]["mode"] == "repository_onboarding"
    assert "src/ace_lite/cli.py" in result["onboarding_view"]["entrypoints"]
    assert (
        "docs/reference/ARCHITECTURE_OVERVIEW.md" in result["onboarding_view"]["public_contracts"]
    )
    assert result["onboarding_view"]["recommended_read_order"][0]["role"] in {
        "entrypoint",
        "public_contract",
    }


def test_build_plan_quick_marks_repomap_neighbors_and_requests_full_plan_when_mixed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_file(tmp_path / "src/app.py", "def run():\n    return True\n")
    _write_file(tmp_path / "docs/guide.md", "Guide\n")
    _write_file(tmp_path / "research/notes.md", "Notes\n")

    monkeypatch.setattr(
        "ace_lite.plan_quick.build_stage_repo_map",
        lambda **kwargs: {
            "enabled": True,
            "seed_paths": ["src/app.py"],
            "neighbor_paths": ["docs/guide.md"],
            "focused_files": ["src/app.py", "docs/guide.md"],
            "used_tokens": 17,
            "budget_tokens": 128,
        },
    )
    monkeypatch.setattr(
        "ace_lite.plan_quick.build_repo_map",
        lambda **kwargs: {
            "files": [
                {
                    "path": "src/app.py",
                    "module": "app",
                    "language": "python",
                    "score": 9.0,
                },
                {
                    "path": "docs/guide.md",
                    "module": "docs.guide",
                    "language": "markdown",
                    "score": 8.5,
                },
                {
                    "path": "research/notes.md",
                    "module": "research.notes",
                    "language": "markdown",
                    "score": 8.0,
                },
            ],
            "used_tokens": 17,
            "budget_tokens": 128,
            "ranking_profile": "graph",
        },
    )

    result = build_plan_quick(
        query="where to start understand the architecture and dependencies",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=3,
        repomap_top_k=8,
        repomap_expand=True,
    )

    assert isinstance(result["candidate_details"], list)
    details = {item["path"]: item for item in result["candidate_details"]}
    assert "repomap_neighbor" in details["docs/guide.md"]["labels"]
    assert result["expected_incremental_value"] in {"medium", "high", "low"}
    if result["upgrade_recommended"]:
        assert result["why_upgrade_now"]
    assert result["repomap_stage"]["used_tokens"] == 17
    assert result["repomap_stage"]["budget_tokens"] == 128


def test_repomap_base_scoring_penalizes_generated_files(tmp_path: Path) -> None:
    business_symbols = "\n".join([f"def allow_{i}():\n    return {i}\n" for i in range(12)])
    _write_file(tmp_path / "internal/app/api/shutdown/allowlist.py", business_symbols)

    generated_symbols = "\n".join([f"def generated_{i}():\n    return {i}\n" for i in range(30)])
    _write_file(
        tmp_path / "pkg/contract/erc20_generated.py",
        "\n".join(["# Code generated by tool. DO NOT EDIT.", "", generated_symbols]),
    )

    index_payload = build_index(tmp_path, languages=["python"])
    ranked = rank_index_files(files=index_payload["files"], profile="heuristic")
    assert ranked
    assert ranked[0]["path"] == "internal/app/api/shutdown/allowlist.py"


def test_build_plan_quick_emits_outcome_label_and_upgrade_outcome_hint(
    tmp_path: Path,
) -> None:
    """ALH1-0202.T1: plan_quick payload includes outcome_label and upgrade_outcome_hint (report-only)."""
    _write_file(tmp_path / "src/main.py", "def main():\n    pass\n")

    result = build_plan_quick(
        query="where is the entrypoint",
        root=tmp_path,
        languages="python",
        top_k_files=3,
        repomap_top_k=8,
    )

    # outcome_label must be present and valid
    assert "outcome_label" in result
    assert result["outcome_label"] in (
        "plan_quick_success",
        "plan_quick_timeout_fallback",
        "plan_quick_error",
    )

    # upgrade_outcome_hint must be present with expected structure
    assert "upgrade_outcome_hint" in result
    hint = result["upgrade_outcome_hint"]
    assert isinstance(hint, dict)
    assert "expected_incremental_value" in hint
    assert "expected_cost_ms_band" in hint
    assert "upgrade_recommended" in hint
    assert hint["expected_incremental_value"] in {"low", "medium", "high"}
    assert isinstance(hint["upgrade_recommended"], bool)
    assert isinstance(hint["expected_cost_ms_band"], dict)
    assert "min" in hint["expected_cost_ms_band"]
    assert "max" in hint["expected_cost_ms_band"]

    # upgrade_outcome_hint values must match the top-level upgrade guidance
    assert hint["expected_incremental_value"] == result["expected_incremental_value"]
    assert hint["upgrade_recommended"] == result["upgrade_recommended"]


def test_classify_path_domain_recognizes_hidden_planning_dirs() -> None:
    """ASF-8902: .planning/, .plans/, milestones/, phases/, state/ are recognized as planning domain."""
    from ace_lite.plan_quick import _classify_path_domain

    assert _classify_path_domain(".planning/REQUIREMENTS.md") == "planning"
    assert _classify_path_domain(".plans/roadmap.md") == "planning"
    assert _classify_path_domain("milestones/phase-1.md") == "planning"
    assert _classify_path_domain("phases/current.md") == "planning"
    assert _classify_path_domain("state/status.md") == "planning"
    assert _classify_path_domain("src/.planning/state.md") == "planning"
    assert _classify_path_domain("docs/.milestones/goal.md") == "planning"


def test_query_flags_extracts_req_ids() -> None:
    """ASF-8901: Query flags extract requirement IDs like EXPL-01, REQ-01."""
    from ace_lite.plan_quick import _query_flags

    flags = _query_flags("What is the status of EXPL-01 and REQ-02?")
    assert flags["has_req_id"] is True
    assert "EXPL-01" in flags["req_ids"]
    assert "REQ-02" in flags["req_ids"]

    flags_no_req = _query_flags("What is the status of planning?")
    assert flags_no_req["has_req_id"] is False
    assert flags_no_req["req_ids"] == []


def test_query_flags_extracts_req_ids_case_insensitively() -> None:
    """ASF-8901: Requirement IDs are normalized even when query casing varies."""
    from ace_lite.plan_quick import _query_flags

    flags = _query_flags("what is the status of expl-01 and Req-02?")
    assert flags["has_req_id"] is True
    assert "EXPL-01" in flags["req_ids"]
    assert "REQ-02" in flags["req_ids"]


def test_candidate_details_includes_picked_because(tmp_path: Path) -> None:
    """ASF-8904: Candidate details include picked_because with concise explanation."""
    _write_file(tmp_path / ".planning/REQUIREMENTS.md", "# Requirements\n")
    _write_file(tmp_path / "src/main.py", "def main():\n    pass\n")

    result = build_plan_quick(
        query="EXPL-01 requirements",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=3,
        repomap_top_k=8,
    )

    assert "candidate_details" in result
    for detail in result["candidate_details"]:
        assert "picked_because" in detail
        assert isinstance(detail["picked_because"], str)
        assert len(detail["picked_because"]) > 0


def test_suggested_refinements_includes_domain_mixed_for_req_ids(tmp_path: Path) -> None:
    """ASF-8903: Query with requirement IDs gets domain_mixed refinement suggestion."""
    _write_file(tmp_path / ".planning/REQUIREMENTS.md", "# Requirements\n")
    _write_file(tmp_path / "src/main.py", "def main():\n    pass\n")

    result = build_plan_quick(
        query="EXPL-01 requirements",
        root=tmp_path,
        languages="python,markdown",
        top_k_files=3,
        repomap_top_k=8,
    )

    refinements = result.get("suggested_query_refinements", [])
    codes = [r["code"] for r in refinements]
    assert "domain_mixed" in codes
