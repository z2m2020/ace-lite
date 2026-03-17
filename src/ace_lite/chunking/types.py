"""Types for chunking modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChunkCandidate:
    """Represents a candidate code chunk for selection."""

    path: str
    qualified_name: str
    kind: str
    lineno: int
    end_lineno: int
    score: float = 0.0
    signature: str = ""
    snippet: str = ""
    score_breakdown: dict[str, Any] = field(default_factory=dict)

    def to_dict(
        self, *, include_signature: bool = True, include_snippet: bool = False
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
        }

        if include_signature:
            payload["signature"] = self.signature
        if include_snippet and self.snippet:
            payload["snippet"] = self.snippet

        return payload


@dataclass(slots=True)
class ChunkMetrics:
    """Metrics for chunk selection process."""

    candidate_chunk_count: int = 0
    candidate_chunks_total: int = 0
    candidate_chunks_selected: int = 0
    chunks_per_file_mean: float = 0.0
    chunk_budget_used: int = 0
    dedup_ratio: float = 0.0
    unique_files_in_chunks: int = 0
    unique_symbol_families_in_chunks: int = 0
    retrieval_context_chunk_count: int = 0
    retrieval_context_coverage_ratio: float = 0.0
    retrieval_context_char_count_mean: float = 0.0
    robust_signature_count: int = 0
    robust_signature_coverage_ratio: float = 0.0
    graph_prior_chunk_count: int = 0
    graph_prior_coverage_ratio: float = 0.0
    graph_prior_total: float = 0.0
    graph_seeded_chunk_count: int = 0
    graph_transfer_count: int = 0
    graph_hub_suppressed_chunk_count: int = 0
    graph_hub_penalty_total: float = 0.0
    graph_closure_enabled: bool = False
    graph_closure_boosted_chunk_count: int = 0
    graph_closure_coverage_ratio: float = 0.0
    graph_closure_anchor_count: int = 0
    graph_closure_support_edge_count: int = 0
    graph_closure_total: float = 0.0
    diversity_enabled: bool = False
    topological_shield_enabled: bool = False
    topological_shield_report_only: bool = False
    topological_shield_attenuated_chunk_count: int = 0
    topological_shield_coverage_ratio: float = 0.0
    topological_shield_adjacency_evidence_count: int = 0
    topological_shield_shared_parent_evidence_count: int = 0
    topological_shield_graph_attested_chunk_count: int = 0
    topological_shield_attenuation_total: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "candidate_chunk_count": float(self.candidate_chunk_count),
            "candidate_chunks_total": float(self.candidate_chunks_total),
            "candidate_chunks_selected": float(self.candidate_chunks_selected),
            "chunks_per_file_mean": self.chunks_per_file_mean,
            "chunk_budget_used": float(self.chunk_budget_used),
            "dedup_ratio": self.dedup_ratio,
            "unique_files_in_chunks": float(self.unique_files_in_chunks),
            "unique_symbol_families_in_chunks": float(self.unique_symbol_families_in_chunks),
            "retrieval_context_chunk_count": float(self.retrieval_context_chunk_count),
            "retrieval_context_coverage_ratio": self.retrieval_context_coverage_ratio,
            "retrieval_context_char_count_mean": self.retrieval_context_char_count_mean,
            "robust_signature_count": float(self.robust_signature_count),
            "robust_signature_coverage_ratio": self.robust_signature_coverage_ratio,
            "graph_prior_chunk_count": float(self.graph_prior_chunk_count),
            "graph_prior_coverage_ratio": self.graph_prior_coverage_ratio,
            "graph_prior_total": self.graph_prior_total,
            "graph_seeded_chunk_count": float(self.graph_seeded_chunk_count),
            "graph_transfer_count": float(self.graph_transfer_count),
            "graph_hub_suppressed_chunk_count": float(
                self.graph_hub_suppressed_chunk_count
            ),
            "graph_hub_penalty_total": self.graph_hub_penalty_total,
            "graph_closure_enabled": 1.0 if self.graph_closure_enabled else 0.0,
            "graph_closure_boosted_chunk_count": float(
                self.graph_closure_boosted_chunk_count
            ),
            "graph_closure_coverage_ratio": self.graph_closure_coverage_ratio,
            "graph_closure_anchor_count": float(self.graph_closure_anchor_count),
            "graph_closure_support_edge_count": float(
                self.graph_closure_support_edge_count
            ),
            "graph_closure_total": self.graph_closure_total,
            "diversity_enabled": 1.0 if self.diversity_enabled else 0.0,
            "topological_shield_enabled": (
                1.0 if self.topological_shield_enabled else 0.0
            ),
            "topological_shield_report_only": (
                1.0 if self.topological_shield_report_only else 0.0
            ),
            "topological_shield_attenuated_chunk_count": float(
                self.topological_shield_attenuated_chunk_count
            ),
            "topological_shield_coverage_ratio": self.topological_shield_coverage_ratio,
            "topological_shield_adjacency_evidence_count": float(
                self.topological_shield_adjacency_evidence_count
            ),
            "topological_shield_shared_parent_evidence_count": float(
                self.topological_shield_shared_parent_evidence_count
            ),
            "topological_shield_graph_attested_chunk_count": float(
                self.topological_shield_graph_attested_chunk_count
            ),
            "topological_shield_attenuation_total": (
                self.topological_shield_attenuation_total
            ),
        }


__all__ = ["ChunkCandidate", "ChunkMetrics"]
