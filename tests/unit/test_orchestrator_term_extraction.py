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
