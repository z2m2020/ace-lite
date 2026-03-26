from __future__ import annotations

from ace_lite.index_stage import extract_terms


def test_extract_terms_adds_bigrams_for_compound_tokens() -> None:
    terms = extract_terms(
        query="where does the tree sitter indexer parse symbols",
        memory_stage={},
    )

    assert "tree" in terms
    assert "sitter" in terms
    assert "treesitter" in terms
    assert "tree_sitter" in terms


def test_extract_terms_can_disable_compound_expansion() -> None:
    terms = extract_terms(
        query="where does the tree sitter indexer parse symbols",
        memory_stage={},
        query_expansion_enabled=False,
    )

    assert "tree" in terms
    assert "sitter" in terms
    assert "treesitter" not in terms
    assert "tree_sitter" not in terms


def test_extract_terms_adds_release_freeze_variants() -> None:
    terms = extract_terms(
        query="how release freeze validates tabiv3 latency and repomap latency gates",
        memory_stage={},
    )

    assert "run_release_freeze_regression.py" in terms


def test_extract_terms_adds_freeze_automation_variants() -> None:
    terms = extract_terms(
        query="how freeze automation enforces tabiv3 and concept gate thresholds",
        memory_stage={},
    )

    assert "run_release_freeze_regression.py" in terms
    assert "test_matrix_freeze_scripts" in terms
    assert "test_matrix_freeze_scripts.py" in terms


def test_extract_terms_adds_graph_signal_variants() -> None:
    terms = extract_terms(
        query="how scip and xref graph signals rerank candidate files",
        memory_stage={},
    )

    assert "graph_lookup" in terms
    assert "graph_lookup_rerank" in terms
    assert "scip/" in terms
    assert "scip/loader.py" in terms


def test_extract_terms_adds_repomap_file_hints() -> None:
    terms = extract_terms(
        query="why repomap cache keys include index hash and worktree state",
        memory_stage={},
    )

    assert "test_repomap_stage_cache" not in terms
    assert "repomap/" in terms
    assert "repomap.py" in terms
    assert "src/ace_lite/pipeline/stages/repomap.py" in terms


def test_extract_terms_adds_docs_channel_variants() -> None:
    terms = extract_terms(
        query="why docs evidence and code hints are fed back into index ranking",
        memory_stage={},
    )

    assert "docs_channel" in terms
    assert "docs_channel.py" in terms


def test_extract_terms_adds_term_expansion_variants() -> None:
    terms = extract_terms(
        query="how do docs channel hits feed back into deterministic retrieval terms for explain queries",
        memory_stage={},
    )

    assert "extract_terms" in terms
    assert "terms.py" in terms
    assert "src/ace_lite/index_stage/terms.py" in terms


def test_extract_terms_adds_section_cache_variants() -> None:
    terms = extract_terms(
        query="how docs channel stores and reloads section cache on disk",
        memory_stage={},
    )

    assert "docs_sections_cache.json" in terms
    assert "repomap/cache.py" in terms


def test_extract_terms_adds_concept_benchmark_gate_variants() -> None:
    terms = extract_terms(
        query="where concept benchmark gate is configured and evaluated in freeze automation",
        memory_stage={},
    )

    assert "run_release_freeze_regression.py" in terms
    assert "benchmark/runner.py" in terms


def test_extract_terms_adds_worktree_guard_variants() -> None:
    terms = extract_terms(
        query="why worktree query guard filters unrelated changed files before ranking",
        memory_stage={},
    )

    assert "worktree_query_guard" in terms
    assert "priors.py" in terms


def test_extract_terms_adds_worktree_prior_test_variants() -> None:
    terms = extract_terms(
        query="how worktree changed files are boosted and injected into candidate selection",
        memory_stage={},
    )

    assert "test_orchestrator_cochange_gating" in terms


def test_extract_terms_adds_rerank_budget_variants() -> None:
    terms = extract_terms(
        query="why cross encoder rerank uses strict time budget with fail open fallback",
        memory_stage={},
    )

    assert "embeddings" in terms
    assert "embeddings.py" in terms
    assert "semantic_rerank_time_budget_ms" in terms
    assert "embedding_fail_open" in terms


def test_extract_terms_adds_chinese_docs_channel_variants() -> None:
    terms = extract_terms(
        query="为什么文档通道的文档证据会回灌到索引排序",
        memory_stage={},
    )

    assert "docs_channel" in terms
    assert "docs_channel.py" in terms


def test_extract_terms_adds_chinese_worktree_variants() -> None:
    terms = extract_terms(
        query="工作区改动文件如何影响候选文件选择",
        memory_stage={},
    )

    assert "worktree_prior" in terms
    assert "index_cache" in terms


def test_extract_terms_adds_chinese_freeze_variants() -> None:
    terms = extract_terms(
        query="冻结门控如何验证 tabiv3 和概念门控阈值",
        memory_stage={},
    )

    assert "run_release_freeze_regression.py" in terms
    assert "p1_concepts.yaml" in terms


def test_extract_terms_adds_chinese_architecture_intent_variants() -> None:
    terms = extract_terms(
        query="解释一下重试机制和整体架构如何工作",
        memory_stage={},
    )

    assert "retry" in terms
    assert "architecture" in terms
    assert "mechanism" in terms


def test_extract_terms_adds_summary_index_variants() -> None:
    terms = extract_terms(
        query="how does workspace summary index return summary tokens for a repo",
        memory_stage={},
    )

    assert "summary_index" in terms
    assert "summary_tokens_for_repo" in terms
    assert "workspace/planner.py" in terms


def test_extract_terms_adds_reference_sidecar_variants() -> None:
    terms = extract_terms(
        query="how does reference sidecar include caller callee context in chunk rerank",
        memory_stage={},
    )

    assert "references" in terms
    assert "treesitter_engine.py" in terms
    assert "chunking/builder.py" in terms


def test_extract_terms_adds_cli_flag_variants() -> None:
    terms = extract_terms(
        query="which code handles --trace-export-path and --memory-primary options",
        memory_stage={},
    )

    assert "trace_export_path" in terms
    assert "memory_primary" in terms


def test_extract_terms_adds_benchmark_flag_impl_hints() -> None:
    query = "".join(
        (
            "where are embedding ",
            "provider and rerank ",
            "pool benchmark options wired ",
            "for academic optimization experiments",
        )
    )
    terms = extract_terms(
        query=query,
        memory_stage={},
    )

    assert "embedding_provider" in terms
    assert "embedding_rerank_pool" in terms
    assert "".join(("--embedding-", "provider")) in terms
    assert "".join(("--embedding-", "rerank-pool")) in terms
    assert "".join(("embedding_provider_", "choices")) in terms
    assert "".join(("shared_embedding_option_", "descriptors")) in terms
    assert "".join(("_build_benchmark_", "command")) in terms
    assert "".join(("query_expansion_", "experiment")) in terms
    assert "".join(("resolve_benchmark_run_", "settings")) in terms
    assert "".join(("_resolve_shared_plan_", "config")) in terms
    assert "".join(("ace_lite_query_expansion_", "enabled")) in terms


def test_extract_terms_can_disable_benchmark_flag_impl_hints() -> None:
    query = "".join(
        (
            "where are embedding ",
            "provider and rerank ",
            "pool benchmark options wired ",
            "for academic optimization experiments",
        )
    )
    terms = extract_terms(
        query=query,
        memory_stage={},
        query_expansion_enabled=False,
    )

    assert "embedding" in terms
    assert "provider" in terms
    assert "rerank" in terms
    assert "pool" in terms
    assert "embedding_provider" not in terms
    assert "embedding_rerank_pool" not in terms
    assert "".join(("--embedding-", "provider")) not in terms
    assert "".join(("embedding_provider_", "choices")) not in terms
    assert "".join(("shared_embedding_option_", "descriptors")) not in terms
    assert "".join(("_build_benchmark_", "command")) not in terms
    assert "".join(("resolve_benchmark_run_", "settings")) not in terms


def test_extract_terms_adds_stage_contract_impl_hints() -> None:
    query = "".join(
        (
            "where does ",
            "StageContractError format error ",
            "code and reason for pipeline ",
            "contract failures",
        )
    )
    terms = extract_terms(
        query=query,
        memory_stage={},
    )

    assert "stagecontracterror" in terms
    assert "error_code" in terms
    assert "".join(("stage_contract_", "error")) in terms
    assert "".join(("pipeline/", "contracts.py")) in terms
    assert "".join(("src/ace_lite/pipeline/", "contracts.py")) in terms
    assert "".join(("validate_stage_", "output")) in terms
    assert "".join(("stage_contract.invalid_", "type")) in terms
    assert "".join(("stage_contract.missing_", "key")) in terms


def test_extract_terms_adds_timeout_fallback_impl_hints() -> None:
    query = "".join(
        (
            "how runtime error and ",
            "traceback are handled when ",
            "plan fallback times out",
        )
    )
    terms = extract_terms(
        query=query,
        memory_stage={},
    )

    assert "runtimeerror" in terms
    assert "traceback" in terms
    assert "".join(("_capture_thread_", "stack")) in terms
    assert "".join(("execute_with_", "timeout")) in terms
    assert "".join(("build_plan_timeout_fallback_", "payload")) in terms
    assert "".join(("plan", "timeoutoutcome")) in terms


def test_extract_terms_can_disable_timeout_fallback_impl_hints() -> None:
    query = "".join(
        (
            "how runtime error and ",
            "traceback are handled when ",
            "plan fallback times out",
        )
    )
    terms = extract_terms(
        query=query,
        memory_stage={},
        query_expansion_enabled=False,
    )

    assert "runtime" in terms
    assert "error" in terms
    assert "traceback" in terms
    assert "runtimeerror" not in terms
    assert "plan_timeout.py" not in terms
    assert "exceptions.py" not in terms
    assert "".join(("_capture_thread_", "stack")) not in terms
    assert "".join(("execute_with_", "timeout")) not in terms
    assert "".join(("build_plan_timeout_fallback_", "payload")) not in terms


def test_extract_terms_adds_camel_case_exception_variants() -> None:
    terms = extract_terms(
        query="where is ValueError raised when validation result parsing fails",
        memory_stage={},
    )

    assert "valueerror" in terms
    assert "value_error" in terms
    assert "exceptions.py" in terms
