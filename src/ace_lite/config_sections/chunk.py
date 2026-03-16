from __future__ import annotations

from ace_lite.pydantic_utils import StrictModel as _StrictModel


class ChunkCoreSectionSpec(_StrictModel):
    top_k: int | None = None
    per_file_limit: int | None = None
    disclosure: str | None = None
    signature: bool | None = None
    token_budget: int | None = None


class ChunkGuardSectionSpec(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    lambda_penalty: float | None = None
    min_pool: int | None = None
    max_pool: int | None = None
    min_marginal_utility: float | None = None
    compatibility_min_overlap: float | None = None


class ChunkTopologicalShieldSectionSpec(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    max_attenuation: float | None = None
    shared_parent_attenuation: float | None = None
    adjacency_attenuation: float | None = None


__all__ = [
    "ChunkCoreSectionSpec",
    "ChunkGuardSectionSpec",
    "ChunkTopologicalShieldSectionSpec",
]
