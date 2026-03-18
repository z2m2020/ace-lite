"""Shared choice tuples and retrieval presets for CLI option groups."""

from __future__ import annotations

from typing import Any

from ace_lite.chunking.disclosure_policy import CHUNK_DISCLOSURE_CHOICES
from ace_lite.config_choices import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
)
from ace_lite.scip import SCIP_PROVIDERS

CANDIDATE_RANKER_CHOICES = ("heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid")
HYBRID_FUSION_CHOICES = ("linear", "rrf")
MEMORY_STRATEGY_CHOICES = ("semantic", "hybrid")
SBFL_METRIC_CHOICES = ("ochiai", "dstar")
SCIP_PROVIDER_CHOICES = tuple(SCIP_PROVIDERS)

RETRIEVAL_PRESETS: dict[str, dict[str, Any]] = {
    "balanced-v1": {
        "top_k_files": 6,
        "min_candidate_score": 2,
        "candidate_relative_threshold": 0.35,
        "candidate_ranker": "hybrid_re2",
        "repomap_signal_weights": {"base": 0.7, "graph": 0.25, "import_depth": 0.05},
    },
    "precision-v1": {
        "top_k_files": 4,
        "min_candidate_score": 2,
        "candidate_relative_threshold": 0.55,
        "candidate_ranker": "heuristic",
        "repomap_signal_weights": {"base": 0.75, "graph": 0.2, "import_depth": 0.05},
    },
    "recall-v1": {
        "top_k_files": 8,
        "min_candidate_score": 1,
        "candidate_relative_threshold": 0.0,
        "candidate_ranker": "hybrid_re2",
        "repomap_signal_weights": {"base": 0.6, "graph": 0.3, "import_depth": 0.1},
    },
}

RETRIEVAL_PRESET_CHOICES = ("none", *tuple(RETRIEVAL_PRESETS.keys()))

__all__ = [
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "CANDIDATE_RANKER_CHOICES",
    "CHUNK_DISCLOSURE_CHOICES",
    "CHUNK_GUARD_MODE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "HYBRID_FUSION_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_STRATEGY_CHOICES",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RETRIEVAL_POLICY_CHOICES",
    "RETRIEVAL_PRESETS",
    "RETRIEVAL_PRESET_CHOICES",
    "SBFL_METRIC_CHOICES",
    "SCIP_PROVIDER_CHOICES",
]
