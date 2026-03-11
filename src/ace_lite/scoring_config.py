"""Scoring and ranking configuration constants.

This module centralizes all scoring weights, ranking parameters, and
diversity penalty values used by the ace-lite pipeline stages.

These values were extracted from orchestrator.py as part of the
architecture refactoring plan (Phase 1).

Design Principles:
- All values are pure constants (no runtime computation)
- Values are organized by functional domain
- Each constant has a descriptive docstring

Usage:
    from ace_lite.scoring_config import (
        CHUNK_FILE_PRIOR_WEIGHT,
        BM25_K1,
        HYBRID_BM25_WEIGHT,
    )
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Chunk Scoring Weights
# ---------------------------------------------------------------------------

# Base weight applied to file-level prior scores
CHUNK_FILE_PRIOR_WEIGHT: float = 0.35

# Score boost when chunk path matches query terms exactly
CHUNK_PATH_MATCH: float = 1.0

# Score boost when chunk module matches query terms
CHUNK_MODULE_MATCH: float = 0.8

# Score boost for exact symbol name match
CHUNK_SYMBOL_EXACT: float = 2.5

# Score boost for partial symbol name match
CHUNK_SYMBOL_PARTIAL: float = 1.4

# Score boost when definition signature matches
CHUNK_SIGNATURE_MATCH: float = 0.5

# Weight factor for reference count contribution
CHUNK_REFERENCE_FACTOR: float = 0.3

# Maximum cap for reference-based score contribution
CHUNK_REFERENCE_CAP: float = 2.5

# ---------------------------------------------------------------------------
# Chunk Diversity Penalties
# ---------------------------------------------------------------------------

# Penalty for selecting multiple chunks from the same file path
CHUNK_DIVERSITY_PATH_PENALTY: float = 0.20

# Penalty for selecting chunks from the same symbol family
CHUNK_DIVERSITY_SYMBOL_FAMILY_PENALTY: float = 0.30

# Penalty for selecting chunks of the same kind (class, function, etc.)
CHUNK_DIVERSITY_KIND_PENALTY: float = 0.10

# Penalty for selecting chunks close together in the same file
CHUNK_DIVERSITY_LOCALITY_PENALTY: float = 0.15

# Line window size for locality diversity calculation
CHUNK_DIVERSITY_LOCALITY_WINDOW: int = 24

# ---------------------------------------------------------------------------
# Heuristic Ranker Parameters
# ---------------------------------------------------------------------------

# Score boost for exact path match
HEUR_PATH_EXACT: float = 3.0

# Score boost when path contains query term
HEUR_PATH_CONTAINS: float = 2.0

# Score boost for exact module match
HEUR_MODULE_EXACT: float = 3.0

# Score boost for module tail match (last component)
HEUR_MODULE_TAIL: float = 2.5

# Score boost when module contains query term
HEUR_MODULE_CONTAINS: float = 1.5

# Score boost for exact symbol name match
HEUR_SYMBOL_EXACT: float = 3.0

# Multiplication factor for partial symbol match
HEUR_SYMBOL_PARTIAL_FACTOR: float = 0.75

# Maximum score cap for partial symbol matches
HEUR_SYMBOL_PARTIAL_CAP: float = 2.0

# Weight for import-based scoring
HEUR_IMPORT_FACTOR: float = 0.5

# Maximum cap for import-based score contribution
HEUR_IMPORT_CAP: float = 1.5

# Weight for content symbol matches
HEUR_CONTENT_SYMBOL_FACTOR: float = 0.2

# Weight for content import matches
HEUR_CONTENT_IMPORT_FACTOR: float = 0.1

# Maximum cap for content-based scoring
HEUR_CONTENT_CAP: float = 1.0

# Base value for depth penalty calculation
HEUR_DEPTH_BASE: float = 1.4

# Multiplication factor for path depth penalty
HEUR_DEPTH_FACTOR: float = 0.15

# ---------------------------------------------------------------------------
# BM25 Ranker Parameters
# ---------------------------------------------------------------------------

# BM25 term frequency saturation parameter (k1)
BM25_K1: float = 1.2

# BM25 document length normalization parameter (b)
BM25_B: float = 0.75

# Scaling factor for BM25 scores
BM25_SCORE_SCALE: float = 4.0

# Weight for path prior in BM25 scoring
BM25_PATH_PRIOR_FACTOR: float = 0.1

# Minimum shortlist size before BM25 scoring
BM25_SHORTLIST_MIN: int = 16

# Multiplication factor for shortlist size calculation
BM25_SHORTLIST_FACTOR: int = 6

# ---------------------------------------------------------------------------
# Hybrid RE2 Ranker Parameters
# ---------------------------------------------------------------------------

# Weight for BM25 component in hybrid ranking
HYBRID_BM25_WEIGHT: float = 0.45

# Weight for heuristic component in hybrid ranking
HYBRID_HEURISTIC_WEIGHT: float = 0.45

# Weight for coverage-based scoring
HYBRID_COVERAGE_WEIGHT: float = 0.10

# Scaling factor for combined hybrid scores
HYBRID_COMBINED_SCALE: float = 10.0

# Minimum number of candidates in hybrid shortlist
HYBRID_SHORTLIST_MIN: int = 12

# Multiplication factor for hybrid shortlist size
HYBRID_SHORTLIST_FACTOR: int = 4

# Default k parameter for Reciprocal Rank Fusion
HYBRID_RRF_K_DEFAULT: int = 60

# Supported fusion modes for hybrid ranking
HYBRID_FUSION_MODES: tuple[str, ...] = ("linear", "rrf")

# ---------------------------------------------------------------------------
# SCIP/XRef Boost Parameters
# ---------------------------------------------------------------------------

# Base weight for SCIP-based cross-reference boost
SCIP_BASE_WEIGHT: float = 0.5

# ---------------------------------------------------------------------------
# Term Extraction Parameters
# ---------------------------------------------------------------------------

# Maximum number of terms to extract from query
EXTRACT_TERMS_MAX: int = 16

# ---------------------------------------------------------------------------
# Valid Choice Sets (for validation)
# ---------------------------------------------------------------------------

# Supported candidate ranker strategies
CANDIDATE_RANKER_CHOICES: tuple[str, ...] = (
    "heuristic",
    "bm25_lite",
    "hybrid_re2",
    "rrf_hybrid",
)

# Supported memory disclosure modes
MEMORY_DISCLOSURE_MODES: tuple[str, ...] = ("compact", "full")

# Supported memory retrieval strategies
MEMORY_STRATEGIES: tuple[str, ...] = ("semantic", "hybrid")

# Supported SBFL (Spectrum-Based Fault Localization) metrics
SBFL_METRIC_CHOICES: tuple[str, ...] = ("ochiai", "dstar")


__all__ = [
    "BM25_B",
    "BM25_K1",
    "BM25_PATH_PRIOR_FACTOR",
    "BM25_SCORE_SCALE",
    "BM25_SHORTLIST_FACTOR",
    "BM25_SHORTLIST_MIN",
    "CANDIDATE_RANKER_CHOICES",
    "CHUNK_DIVERSITY_KIND_PENALTY",
    "CHUNK_DIVERSITY_LOCALITY_PENALTY",
    "CHUNK_DIVERSITY_LOCALITY_WINDOW",
    "CHUNK_DIVERSITY_PATH_PENALTY",
    "CHUNK_DIVERSITY_SYMBOL_FAMILY_PENALTY",
    "CHUNK_FILE_PRIOR_WEIGHT",
    "CHUNK_MODULE_MATCH",
    "CHUNK_PATH_MATCH",
    "CHUNK_REFERENCE_CAP",
    "CHUNK_REFERENCE_FACTOR",
    "CHUNK_SIGNATURE_MATCH",
    "CHUNK_SYMBOL_EXACT",
    "CHUNK_SYMBOL_PARTIAL",
    "EXTRACT_TERMS_MAX",
    "HEUR_CONTENT_CAP",
    "HEUR_CONTENT_IMPORT_FACTOR",
    "HEUR_CONTENT_SYMBOL_FACTOR",
    "HEUR_DEPTH_BASE",
    "HEUR_DEPTH_FACTOR",
    "HEUR_IMPORT_CAP",
    "HEUR_IMPORT_FACTOR",
    "HEUR_MODULE_CONTAINS",
    "HEUR_MODULE_EXACT",
    "HEUR_MODULE_TAIL",
    "HEUR_PATH_CONTAINS",
    "HEUR_PATH_EXACT",
    "HEUR_SYMBOL_EXACT",
    "HEUR_SYMBOL_PARTIAL_CAP",
    "HEUR_SYMBOL_PARTIAL_FACTOR",
    "HYBRID_BM25_WEIGHT",
    "HYBRID_COMBINED_SCALE",
    "HYBRID_COVERAGE_WEIGHT",
    "HYBRID_FUSION_MODES",
    "HYBRID_HEURISTIC_WEIGHT",
    "HYBRID_RRF_K_DEFAULT",
    "HYBRID_SHORTLIST_FACTOR",
    "HYBRID_SHORTLIST_MIN",
    "MEMORY_DISCLOSURE_MODES",
    "MEMORY_STRATEGIES",
    "SBFL_METRIC_CHOICES",
    "SCIP_BASE_WEIGHT",
]
