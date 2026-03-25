from __future__ import annotations

from ace_lite.pydantic_utils import StrictModel as _StrictModel


class RepomapSectionSpec(_StrictModel):
    enabled: bool | None = None
    top_k: int | None = None
    neighbor_limit: int | None = None
    budget_tokens: int | None = None
    ranking_profile: str | None = None
    signal_weights: dict[str, float] | None = None


class ScipSectionSpec(_StrictModel):
    enabled: bool | None = None
    index_path: str | None = None
    provider: str | None = None
    generate_fallback: bool | None = None
    base_weight: float | None = None


class EmbeddingsSectionSpec(_StrictModel):
    enabled: bool | None = None
    provider: str | None = None
    model: str | None = None
    dimension: int | None = None
    index_path: str | None = None
    rerank_pool: int | None = None
    lexical_weight: float | None = None
    semantic_weight: float | None = None
    min_similarity: float | None = None
    fail_open: bool | None = None


class TraceSectionSpec(_StrictModel):
    export_enabled: bool | None = None
    export_path: str | None = None
    otlp_enabled: bool | None = None
    otlp_endpoint: str | None = None
    otlp_timeout_seconds: float | None = None


class PlanReplayCacheSectionSpec(_StrictModel):
    enabled: bool | None = None
    cache_path: str | None = None


class TokenizerSectionSpec(_StrictModel):
    model: str | None = None


class TestSignalsSectionSpec(_StrictModel):
    junit_xml: str | None = None
    coverage_json: str | None = None
    sbfl_json: str | None = None
    sbfl_metric: str | None = None


__all__ = [
    "EmbeddingsSectionSpec",
    "PlanReplayCacheSectionSpec",
    "RepomapSectionSpec",
    "ScipSectionSpec",
    "TestSignalsSectionSpec",
    "TokenizerSectionSpec",
    "TraceSectionSpec",
]
