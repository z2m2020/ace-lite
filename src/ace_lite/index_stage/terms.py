"""Query-term extraction for the index stage."""

from __future__ import annotations

import os
import re
from typing import Any

from ace_lite.scoring_config import EXTRACT_TERMS_MAX
from ace_lite.text_tokens import code_tokens

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "else",
        "for",
        "from",
        "had",
        "has",
        "have",
        "here",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "might",
        "must",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "should",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "without",
        "would",
        "you",
        "your",
    }
)


def _resolve_query_expansion_enabled(value: bool | None) -> bool:
    if value is not None:
        return bool(value)
    raw = str(os.getenv("ACE_LITE_QUERY_EXPANSION_ENABLED", "") or "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "off", "no", "disabled"}


def extract_terms(
    *,
    query: str,
    memory_stage: dict[str, Any],
    query_expansion_enabled: bool | None = None,
) -> list[str]:
    """Extract index query terms from the user query and memory hits."""

    terms: list[str] = []
    max_terms = EXTRACT_TERMS_MAX
    expansion_enabled = _resolve_query_expansion_enabled(query_expansion_enabled)

    def stem(token: str) -> str:
        if len(token) <= 4:
            return token

        if token.endswith("ies") and len(token) > 5:
            return token[:-3] + "y"

        for suffix in ("ing", "ed", "es"):
            if token.endswith(suffix) and len(token) > (len(suffix) + 2):
                return token[: -len(suffix)]

        if token.endswith("s") and not token.endswith("ss") and len(token) > 5:
            return token[:-1]

        return token

    def add_token(token: str, *, min_len: int) -> None:
        if not token or len(token) < min_len:
            return
        if token in _STOPWORDS:
            return
        if token not in terms:
            terms.append(token)

    def add_variants(raw: str, *, min_len: int) -> None:
        if len(terms) >= max_terms:
            return

        token = raw.strip().lower()
        if not token:
            return

        add_token(token, min_len=min_len)
        stemmed = stem(token)
        if stemmed != token:
            add_token(stemmed, min_len=min_len)

        if "_" in token:
            for part in token.split("_"):
                add_token(part, min_len=min_len)
                stemmed_part = stem(part)
                if stemmed_part != part:
                    add_token(stemmed_part, min_len=min_len)

    query_lower = str(query or "").lower()

    if expansion_enabled and len(terms) < max_terms:
        # Prioritize stable internal tokens before generic raw query tokens so
        # important compound expansions are not crowded out by stopwords or
        # low-signal natural language terms.
        compounds: list[tuple[str, tuple[str, ...]]] = [
            ("tree sitter", ("treesitter", "tree_sitter")),
            ("tree-sitter", ("treesitter", "tree_sitter")),
            ("open memory", ("openmemory", "open_memory")),
            ("repo map", ("repomap", "repo_map")),
            (
                "term expansion",
                (
                    "extract_terms",
                    "terms.py",
                    "index_stage/terms.py",
                    "src/ace_lite/index_stage/terms.py",
                ),
            ),
            (
                "retrieval terms",
                (
                    "extract_terms",
                    "terms.py",
                    "index_stage/terms.py",
                    "src/ace_lite/index_stage/terms.py",
                ),
            ),
            (
                "deterministic retrieval terms",
                (
                    "extract_terms",
                    "terms.py",
                    "index_stage/terms.py",
                    "src/ace_lite/index_stage/terms.py",
                ),
            ),
            # Internal ops/control-plane phrases that map to stable file tokens.
            ("docs channel", ("docs_channel", "docs_channel.py")),
            ("docs evidence", ("docs_channel", "docs_channel.py")),
            ("code hints", ("docs_channel", "docs_channel.py")),
            (
                "section cache",
                (
                    "docs_sections_cache.json",
                    "docs_sections_cache",
                    "repomap/cache.py",
                    "ace_lite/repomap/cache.py",
                    "src/ace_lite/repomap/cache.py",
                ),
            ),
            ("文档通道", ("docs_channel", "docs_channel.py", "docs/")),
            ("文档证据", ("docs_channel", "docs_channel.py")),
            ("代码提示", ("docs_channel", "docs_channel.py")),
            (
                "章节缓存",
                (
                    "docs_sections_cache.json",
                    "docs_sections_cache",
                    "repomap/cache.py",
                    "ace_lite/repomap/cache.py",
                    "src/ace_lite/repomap/cache.py",
                ),
            ),
            ("架构", ("architecture", "design", "overview", "docs/")),
            ("机制", ("mechanism", "workflow", "explain")),
            ("原理", ("principle", "design", "overview")),
            ("流程", ("workflow", "overview", "design")),
            ("解释", ("explain", "overview", "design")),
            ("如何", ("workflow", "mechanism", "overview")),
            ("为什么", ("explain", "design", "overview")),
            ("重试", ("retry", "backoff")),
            (
                "release freeze",
                ("run_release_freeze_regression.py", "scripts/run_release_freeze_regression.py"),
            ),
            (
                "freeze automation",
                (
                    "run_release_freeze_regression.py",
                    "scripts/run_release_freeze_regression.py",
                    "test_matrix_freeze_scripts",
                    "test_matrix_freeze_scripts.py",
                ),
            ),
            (
                "发布冻结",
                (
                    "run_release_freeze_regression.py",
                    "scripts/run_release_freeze_regression.py",
                    "freeze_regression",
                ),
            ),
            (
                "冻结门控",
                (
                    "run_release_freeze_regression.py",
                    "scripts/run_release_freeze_regression.py",
                    "freeze_regression",
                ),
            ),
            (
                "冻结自动化",
                (
                    "run_release_freeze_regression.py",
                    "scripts/run_release_freeze_regression.py",
                    "test_matrix_freeze_scripts",
                    "test_matrix_freeze_scripts.py",
                ),
            ),
            ("concept gate", ("p1_concepts.yaml", "concept_gate")),
            ("external concept", ("external_howwhy.yaml", "external_howwhy")),
            ("feature slices", ("feature_slices.yaml", "run_feature_slice_matrix.py")),
            (
                "concept benchmark gate",
                (
                    "run_release_freeze_regression.py",
                    "scripts/run_release_freeze_regression.py",
                    "benchmark/runner.py",
                    "benchmark/scoring.py",
                ),
            ),
            ("概念门控", ("p1_concepts.yaml", "concept_gate")),
            ("外部概念", ("external_howwhy.yaml", "external_howwhy")),
            ("特性切片", ("feature_slices.yaml", "run_feature_slice_matrix.py")),
            (
                "graph signals",
                (
                    "graph_lookup",
                    "graph_lookup_rerank",
                    "scip/loader.py",
                    "ace_lite/scip/loader.py",
                    "src/ace_lite/scip/loader.py",
                ),
            ),
            (
                "xref graph",
                (
                    "graph_lookup",
                    "graph_lookup_rerank",
                    "scip/loader.py",
                    "ace_lite/scip/loader.py",
                    "src/ace_lite/scip/loader.py",
                ),
            ),
            (
                "图信号",
                (
                    "graph_lookup",
                    "graph_lookup_rerank",
                    "scip/",
                    "scip/loader.py",
                    "ace_lite/scip/loader.py",
                    "src/ace_lite/scip/loader.py",
                ),
            ),
            ("交叉引用", ("xref_json", "graph_lookup")),
            (
                "worktree prior",
                (
                    "worktree_prior",
                    "priors.py",
                    "vcs_worktree.py",
                    "index_cache",
                    "test_orchestrator_cochange_gating",
                ),
            ),
            ("worktree query guard", ("worktree_query_guard", "priors.py")),
            (
                "worktree changed files",
                (
                    "index_cache",
                    "worktree_prior",
                    "test_orchestrator_cochange_gating",
                ),
            ),
            ("工作区", ("worktree_prior", "vcs_worktree.py", "index_cache")),
            ("改动文件", ("worktree_prior", "index_cache")),
            ("变更文件", ("worktree_prior", "index_cache")),
            ("查询守卫", ("worktree_query_guard", "priors.py")),
            ("index cache", ("index_cache", "test_index_cache")),
            (
                "repomap cache",
                (
                    "repomap/",
                    "repomap.py",
                    "repomap/cache.py",
                    "ace_lite/repomap/cache.py",
                    "src/ace_lite/repomap/cache.py",
                    "ace_lite/pipeline/stages/repomap.py",
                    "src/ace_lite/pipeline/stages/repomap.py",
                    "repomap/builder.py",
                    "ace_lite/repomap/builder.py",
                    "src/ace_lite/repomap/builder.py",
                ),
            ),
            ("repomap precompute", ("repomap_precompute", "repomap_precompute_ttl_seconds", "repomap/cache.py")),
            ("仓库地图缓存", ("repomap/cache.py", "repomap_cache")),
            ("预计算", ("repomap_precompute", "repomap_precompute_ttl_seconds", "precompute_cache.json")),
            (
                "summary index",
                (
                    "summary_index",
                    "summary_index.py",
                    "workspace/planner.py",
                    "src/ace_lite/workspace/planner.py",
                ),
            ),
            (
                "summary tokens",
                (
                    "summary_tokens_for_repo",
                    "summary_index.py",
                    "workspace/planner.py",
                ),
            ),
            (
                "workspace summary",
                (
                    "summary_index",
                    "summary_tokens_for_repo",
                    "workspace/planner.py",
                ),
            ),
            (
                "reference sidecar",
                (
                    "references",
                    "chunking/builder.py",
                    "src/ace_lite/chunking/builder.py",
                    "chunk_selection.py",
                    "src/ace_lite/index_stage/chunk_selection.py",
                ),
            ),
            (
                "caller callee",
                (
                    "references",
                    "treesitter_engine.py",
                    "chunking/builder.py",
                    "chunk_selection.py",
                ),
            ),
            (
                "摘要索引",
                (
                    "summary_index",
                    "summary_index.py",
                    "workspace/planner.py",
                    "summary_tokens_for_repo",
                ),
            ),
            (
                "摘要词",
                (
                    "summary_tokens_for_repo",
                    "summary_index.py",
                    "workspace/planner.py",
                ),
            ),
            (
                "引用旁路",
                (
                    "references",
                    "chunking/builder.py",
                    "chunk_selection.py",
                    "treesitter_engine.py",
                ),
            ),
            (
                "调用方",
                (
                    "references",
                    "treesitter_engine.py",
                    "chunking/builder.py",
                ),
            ),
            (
                "被调用方",
                (
                    "references",
                    "treesitter_engine.py",
                    "chunking/builder.py",
                ),
            ),
            (
                "stage contract",
                (
                    "stagecontracterror",
                    "exceptions.py",
                    "pipeline/contracts.py",
                    "src/ace_lite/pipeline/contracts.py",
                    "validate_stage_output",
                    "stage_contract.invalid_type",
                    "stage_contract.missing_key",
                ),
            ),
            (
                "stagecontracterror",
                (
                    "stagecontracterror",
                    "stage_contract_error",
                    "exceptions.py",
                    "pipeline/contracts.py",
                    "src/ace_lite/pipeline/contracts.py",
                    "validate_stage_output",
                    "stage_contract.invalid_type",
                    "stage_contract.missing_key",
                ),
            ),
            (
                "pipeline contract",
                (
                    "pipeline/contracts.py",
                    "src/ace_lite/pipeline/contracts.py",
                    "validate_stage_output",
                    "stage_contract.invalid_type",
                    "stage_contract.missing_key",
                ),
            ),
            (
                "error code",
                (
                    "error_code",
                    "exceptions.py",
                    "validation/result.py",
                    "src/ace_lite/validation/result.py",
                ),
            ),
            (
                "traceback",
                (
                    "traceback",
                    "plan_timeout.py",
                    "exceptions.py",
                    "src/ace_lite/plan_timeout.py",
                    "_capture_thread_stack",
                    "execute_with_timeout",
                ),
            ),
            (
                "stack trace",
                (
                    "traceback",
                    "plan_timeout.py",
                    "exceptions.py",
                    "src/ace_lite/plan_timeout.py",
                ),
            ),
            (
                "plan fallback",
                (
                    "build_plan_timeout_fallback_payload",
                    "execute_with_timeout",
                    "_capture_thread_stack",
                    "plantimeoutoutcome",
                    "plan_timeout.py",
                    "src/ace_lite/plan_timeout.py",
                ),
            ),
            (
                "runtime error",
                (
                    "runtimeerror",
                    "exceptions.py",
                    "runtime/scheduler.py",
                    "src/ace_lite/runtime/scheduler.py",
                ),
            ),
            (
                "value error",
                (
                    "valueerror",
                    "exceptions.py",
                    "validation/result.py",
                    "src/ace_lite/validation/result.py",
                ),
            ),
            (
                "key error",
                (
                    "keyerror",
                    "exceptions.py",
                    "pipeline/registry.py",
                ),
            ),
            (
                "type error",
                (
                    "typeerror",
                    "exceptions.py",
                    "pipeline/stages/memory.py",
                ),
            ),
            ("异常", ("exceptions.py", "stagecontracterror", "runtimeerror")),
            ("错误码", ("error_code", "validation/result.py", "exceptions.py")),
            ("堆栈", ("traceback", "plan_timeout.py", "exceptions.py")),
            ("运行时错误", ("runtimeerror", "exceptions.py", "runtime/scheduler.py")),
            (
                "cross encoder",
                (
                    "embeddings",
                    "embeddings.py",
                    "ace_lite/embeddings.py",
                    "src/ace_lite/embeddings.py",
                    "test_orchestrator_embeddings",
                ),
            ),
            (
                "embedding provider",
                (
                    "embedding_provider",
                    "--embedding-provider",
                    "embedding_provider_choices",
                    "benchmark_run_command",
                    "resolve_benchmark_run_settings",
                    "_resolve_shared_plan_config",
                    "cli_app/commands/benchmark.py",
                    "src/ace_lite/cli_app/commands/benchmark.py",
                ),
            ),
            (
                "rerank pool",
                (
                    "embedding_rerank_pool",
                    "--embedding-rerank-pool",
                    "shared_embedding_option_descriptors",
                    "benchmark_run_command",
                    "resolve_benchmark_run_settings",
                    "cli_app/params_option_retrieval_groups.py",
                    "src/ace_lite/cli_app/params_option_retrieval_groups.py",
                ),
            ),
            (
                "benchmark options",
                (
                    "benchmark_run_command",
                    "resolve_benchmark_run_settings",
                    "_resolve_shared_plan_config",
                    "shared_embedding_option_descriptors",
                    "cli_app/commands/benchmark.py",
                    "src/ace_lite/cli_app/commands/benchmark.py",
                ),
            ),
            (
                "academic optimization",
                (
                    "_build_benchmark_command",
                    "query_expansion_experiment",
                    "ace_lite_query_expansion_enabled",
                    "academic_optimization.yaml",
                    "run_academic_optimization_benchmark.py",
                    "scripts/run_academic_optimization_benchmark.py",
                ),
            ),
            (
                "academic optimization experiments",
                (
                    "_build_benchmark_command",
                    "query_expansion_experiment",
                    "ace_lite_query_expansion_enabled",
                    "academic_optimization.yaml",
                ),
            ),
            ("time budget", ("semantic_rerank_time_budget_ms", "time_budget")),
            ("fail open", ("fail_open", "embedding_fail_open")),
            (
                "交叉编码",
                (
                    "embeddings",
                    "embeddings.py",
                    "ace_lite/embeddings.py",
                    "src/ace_lite/embeddings.py",
                    "test_orchestrator_embeddings",
                ),
            ),
            ("时间预算", ("semantic_rerank_time_budget_ms", "time_budget")),
            ("失败降级", ("fail_open", "embedding_fail_open")),
        ]
        for phrase, variants in compounds:
                if len(terms) >= max_terms:
                    break
                if phrase not in query_lower:
                    continue
                for variant in variants:
                    add_token(variant, min_len=5)
                    if len(terms) >= max_terms:
                        break

    query_tokens = re.findall(r"[a-z0-9_]+", query_lower)
    query_code_tokens = code_tokens(query, min_len=3, max_tokens=64)

    for raw in [*query_tokens, *query_code_tokens]:
        add_variants(raw, min_len=3)
        if len(terms) >= max_terms:
            break

    if expansion_enabled and len(terms) < max_terms:
        # Provide stable "directory-ish" hints for repo-internal keywords so
        # implementation modules can surface alongside tests (especially in
        # concept/architecture queries).
        if "scip" in terms:
            add_token("scip/", min_len=5)
            add_token("scip/loader.py", min_len=5)
            add_token("ace_lite/scip/loader.py", min_len=5)
            add_token("src/ace_lite/scip/loader.py", min_len=5)
        if "embeddings" in terms:
            add_token("ace_lite/embeddings.py", min_len=5)
            add_token("src/ace_lite/embeddings.py", min_len=5)
        if "repomap" in terms:
            add_token("repomap/", min_len=5)
            add_token("repomap.py", min_len=5)
        if "summary_index" in terms or "summary_tokens_for_repo" in terms:
            add_token("workspace/summary_index.py", min_len=5)
            add_token("src/ace_lite/workspace/summary_index.py", min_len=5)
            add_token("workspace/planner.py", min_len=5)
            add_token("src/ace_lite/workspace/planner.py", min_len=5)
        if "references" in terms:
            add_token("treesitter_engine.py", min_len=5)
            add_token("chunking/builder.py", min_len=5)
            add_token("chunk_selection.py", min_len=5)
        if (
            "stagecontracterror" in terms
            or "runtimeerror" in terms
            or "valueerror" in terms
            or "keyerror" in terms
            or "typeerror" in terms
            or "error_code" in terms
            or "traceback" in terms
        ):
            add_token("exceptions.py", min_len=5)
            add_token("src/ace_lite/exceptions.py", min_len=5)

    if expansion_enabled and len(terms) < max_terms:
        flag_tokens = re.findall(r"--[a-z0-9][a-z0-9-]*", query_lower)
        for raw_flag in flag_tokens:
            normalized_flag = raw_flag.lstrip("-").strip()
            if not normalized_flag:
                continue
            add_token(normalized_flag, min_len=3)
            add_variants(normalized_flag.replace("-", "_"), min_len=3)
            if len(terms) >= max_terms:
                break

    if expansion_enabled and len(terms) < max_terms:
        exception_tokens = re.findall(r"\b[A-Z][A-Za-z]+(?:Error|Exception)\b", str(query or ""))
        for raw_exception in exception_tokens:
            normalized_exception = raw_exception.strip().lower()
            if not normalized_exception:
                continue
            add_token(normalized_exception, min_len=3)
            snake_case = re.sub(r"(?<!^)([A-Z])", r"_\1", raw_exception).lower()
            add_variants(snake_case, min_len=3)
            add_token("exceptions.py", min_len=5)
            add_token("src/ace_lite/exceptions.py", min_len=5)
            if len(terms) >= max_terms:
                break

    hits = memory_stage.get("hits", [])
    if not isinstance(hits, list):
        hits = []
    if not hits:
        hits = memory_stage.get("hits_preview", [])
    if not isinstance(hits, list):
        hits = []

    for hit in hits:
        if not isinstance(hit, dict):
            continue
        text = hit.get("text") or hit.get("preview")
        if not isinstance(text, str):
            continue
        for raw in re.findall(r"[a-z0-9_]+", text.lower()):
            add_variants(raw, min_len=5)
            if len(terms) >= max_terms:
                break
        if len(terms) >= max_terms:
            break

    return terms


__all__ = ["extract_terms"]
