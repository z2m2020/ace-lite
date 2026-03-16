from __future__ import annotations

from ace_lite.config_sections import (
    DEFAULT_EMBEDDINGS_INDEX_PATH,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MEMORY_NOTES_PATH,
    DEFAULT_MEMORY_PROFILE_PATH,
    DEFAULT_PLAN_REPLAY_CACHE_PATH,
    DEFAULT_SCIP_INDEX_PATH,
    DEFAULT_TOKENIZER_MODEL,
    DEFAULT_TRACE_EXPORT_PATH,
    normalize_clamped_float,
    normalize_default_path,
    normalize_non_negative_float,
    normalize_non_negative_int,
    normalize_positive_int,
    normalize_string_default,
)
from ace_lite.orchestrator_config import (
    EmbeddingsConfig,
    MemoryCaptureConfig,
    MemoryFeedbackConfig,
    MemoryNotesConfig,
    MemoryProfileConfig,
    PlanReplayCacheConfig,
    ScipConfig,
    TokenizerConfig,
    TraceConfig,
)


def test_runtime_helper_defaults_and_bounds_are_stable() -> None:
    assert (
        normalize_default_path(None, default=DEFAULT_MEMORY_PROFILE_PATH)
        == DEFAULT_MEMORY_PROFILE_PATH
    )
    assert (
        normalize_string_default("", default=DEFAULT_EMBEDDING_MODEL)
        == DEFAULT_EMBEDDING_MODEL
    )
    assert normalize_positive_int("0", default=8, minimum=1) == 1
    assert normalize_positive_int(None, default=8, minimum=1) == 8
    assert normalize_non_negative_int("-3", default=7) == 0
    assert normalize_non_negative_float("-0.2", default=1.5) == 0.0
    assert (
        normalize_clamped_float("9.0", default=0.5, minimum=0.0, maximum=1.0) == 1.0
    )
    assert (
        normalize_clamped_float(
            None,
            default=1.5,
            minimum=0.1,
            maximum=float("inf"),
        )
        == 1.5
    )


def test_orchestrator_shared_sections_use_runtime_helper_defaults() -> None:
    assert MemoryProfileConfig().path == DEFAULT_MEMORY_PROFILE_PATH
    assert MemoryFeedbackConfig().path == DEFAULT_MEMORY_PROFILE_PATH
    assert MemoryCaptureConfig().notes_path == DEFAULT_MEMORY_NOTES_PATH
    assert MemoryNotesConfig().path == DEFAULT_MEMORY_NOTES_PATH
    assert TokenizerConfig().model == DEFAULT_TOKENIZER_MODEL
    assert ScipConfig().index_path == DEFAULT_SCIP_INDEX_PATH
    assert EmbeddingsConfig().model == DEFAULT_EMBEDDING_MODEL
    assert EmbeddingsConfig().index_path == DEFAULT_EMBEDDINGS_INDEX_PATH
    assert TraceConfig().export_path == DEFAULT_TRACE_EXPORT_PATH
    assert PlanReplayCacheConfig().cache_path == DEFAULT_PLAN_REPLAY_CACHE_PATH


def test_orchestrator_shared_sections_fail_open_with_runtime_helpers() -> None:
    embeddings = EmbeddingsConfig(
        model="",
        dimension="2",
        rerank_pool="0",
        lexical_weight="-1",
        semantic_weight="-2",
    )
    assert embeddings.model == DEFAULT_EMBEDDING_MODEL
    assert embeddings.dimension == 8
    assert embeddings.rerank_pool == 1
    assert embeddings.lexical_weight == 0.0
    assert embeddings.semantic_weight == 0.0

    trace = TraceConfig(otlp_timeout_seconds="0")
    assert trace.otlp_timeout_seconds == 0.1

    profile = MemoryProfileConfig(path="", top_n="0", token_budget="0")
    assert profile.path == DEFAULT_MEMORY_PROFILE_PATH
    assert profile.top_n == 1
    assert profile.token_budget == 1
