from __future__ import annotations

from ace_lite.pydantic_utils import StrictModel as _StrictModel


class MemoryCoreSectionSpec(_StrictModel):
    disclosure_mode: str | None = None
    preview_max_chars: int | None = None
    strategy: str | None = None


class MemoryNamespaceSectionSpec(_StrictModel):
    container_tag: str | None = None
    auto_tag_mode: str | None = None


class MemoryProfileSectionSpec(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    top_n: int | None = None
    token_budget: int | None = None
    expiry_enabled: bool | None = None
    ttl_days: int | None = None
    max_age_days: int | None = None


class MemoryTemporalSectionSpec(_StrictModel):
    enabled: bool | None = None
    recency_boost_enabled: bool | None = None
    recency_boost_max: float | None = None
    timezone_mode: str | None = None


class MemoryFeedbackSectionSpec(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    max_entries: int | None = None
    boost_per_select: float | None = None
    max_boost: float | None = None
    decay_days: float | None = None


class MemoryCaptureSectionSpec(_StrictModel):
    enabled: bool | None = None
    notes_path: str | None = None
    min_query_length: int | None = None
    keywords: list[str] | tuple[str, ...] | None = None


class MemoryNotesSectionSpec(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    limit: int | None = None
    mode: str | None = None
    expiry_enabled: bool | None = None
    ttl_days: int | None = None
    max_age_days: int | None = None


class MemoryGateSectionSpec(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None


class MemoryPostprocessSectionSpec(_StrictModel):
    enabled: bool | None = None
    noise_filter_enabled: bool | None = None
    length_norm_anchor_chars: int | None = None
    time_decay_half_life_days: float | None = None
    hard_min_score: float | None = None
    diversity_enabled: bool | None = None
    diversity_similarity_threshold: float | None = None


__all__ = [
    "MemoryCaptureSectionSpec",
    "MemoryCoreSectionSpec",
    "MemoryFeedbackSectionSpec",
    "MemoryGateSectionSpec",
    "MemoryNamespaceSectionSpec",
    "MemoryNotesSectionSpec",
    "MemoryPostprocessSectionSpec",
    "MemoryProfileSectionSpec",
    "MemoryTemporalSectionSpec",
]
