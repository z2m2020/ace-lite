"""Chunk selection and scoring modules.

This package provides modular chunk selection algorithms:

- `types`: ChunkCandidate and ChunkMetrics dataclasses
- `scoring`: Chunk scoring based on term matching and references
- `diversity`: Diversity penalties for varied chunk selection

Usage:
    from ace_lite.chunking import (
        ChunkCandidate,
        ChunkMetrics,
        score_chunk_candidate,
        calculate_diversity_penalty,
    )
"""

from __future__ import annotations

from ace_lite.chunking.diversity import (
    calculate_diversity_penalty,
    chunk_symbol_family,
)
from ace_lite.chunking.scoring import build_chunk_step_reason, score_chunk_candidate
from ace_lite.chunking.types import ChunkCandidate, ChunkMetrics

__all__ = [
    "ChunkCandidate",
    "ChunkMetrics",
    "build_chunk_step_reason",
    "calculate_diversity_penalty",
    "chunk_symbol_family",
    "score_chunk_candidate",
]
