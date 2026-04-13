"""Types for chunking modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RETRIEVAL_CONTEXT_SIDECAR_KEY = "_retrieval_context"
CONTEXTUAL_CHUNKING_SIDECAR_KEY = "_contextual_chunking_sidecar"
ROBUST_SIGNATURE_SIDECAR_KEY = "_robust_signature_lite"
TOPOLOGICAL_SHIELD_SIDECAR_KEY = "_topological_shield"
INTERNAL_CHUNK_SIDECAR_KEYS = frozenset(
    {
        RETRIEVAL_CONTEXT_SIDECAR_KEY,
        CONTEXTUAL_CHUNKING_SIDECAR_KEY,
        ROBUST_SIGNATURE_SIDECAR_KEY,
        TOPOLOGICAL_SHIELD_SIDECAR_KEY,
    }
)


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
    retrieval_context: str = ""
    score_breakdown: dict[str, Any] = field(default_factory=dict)

    def to_dict(
        self,
        *,
        include_signature: bool = True,
        include_snippet: bool = False,
        include_internal_sidecars: bool = False,
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
        if include_internal_sidecars and self.retrieval_context:
            payload[RETRIEVAL_CONTEXT_SIDECAR_KEY] = self.retrieval_context

        return payload


def strip_internal_chunk_sidecars(
    candidate_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in candidate_chunks:
        if not isinstance(item, dict):
            continue
        payload = {
            key: value
            for key, value in item.items()
            if str(key) not in INTERNAL_CHUNK_SIDECAR_KEYS
            and not str(key).startswith("_")
        }
        sanitized.append(payload)
    return sanitized


def render_retrieval_context_from_sidecar(*, sidecar: dict[str, Any]) -> str:
    if not isinstance(sidecar, dict):
        return ""

    context_parts: list[str] = []
    for field in ("module", "language", "kind", "path", "symbol", "signature"):
        value = str(sidecar.get(field) or "").strip()
        if value:
            context_parts.append(f"{field}={value}")

    parent_symbol = str(sidecar.get("parent_symbol") or "").strip()
    if parent_symbol:
        context_parts.append(f"parent_symbol={parent_symbol}")

    parent_signature = str(sidecar.get("parent_signature") or "").strip()
    if parent_signature:
        context_parts.append(f"parent={parent_signature}")

    imports = sidecar.get("imports", [])
    if isinstance(imports, list):
        import_values = [str(item).strip() for item in imports if str(item).strip()]
        if import_values:
            joined = ", ".join(import_values)
            if bool(sidecar.get("imports_truncated", False)):
                joined += ", ..."
            context_parts.append(f"imports={joined}")

    references = sidecar.get("references", [])
    if isinstance(references, list):
        reference_values = [str(item).strip() for item in references if str(item).strip()]
        if reference_values:
            joined = ", ".join(reference_values)
            if bool(sidecar.get("references_truncated", False)):
                joined += ", ..."
            context_parts.append(f"references={joined}")

    callees = sidecar.get("callees", [])
    if isinstance(callees, list):
        callee_values = [str(item).strip() for item in callees if str(item).strip()]
        if callee_values:
            joined = ", ".join(callee_values)
            if bool(sidecar.get("callees_truncated", False)):
                joined += ", ..."
            context_parts.append(f"callees={joined}")

    callers = sidecar.get("callers", [])
    if isinstance(callers, list):
        caller_values = [str(item).strip() for item in callers if str(item).strip()]
        if caller_values:
            joined = ", ".join(caller_values)
            if bool(sidecar.get("callers_truncated", False)):
                joined += ", ..."
            context_parts.append(f"callers={joined}")

    reference_scope = str(sidecar.get("references_scope") or "").strip()
    if reference_scope:
        context_parts.append(f"references_scope={reference_scope}")

    return "\n".join(context_parts).strip()


def resolve_retrieval_context_text(candidate_chunk: dict[str, Any]) -> str:
    if not isinstance(candidate_chunk, dict):
        return ""

    retrieval_context = str(candidate_chunk.get(RETRIEVAL_CONTEXT_SIDECAR_KEY) or "").strip()
    if retrieval_context:
        return retrieval_context

    sidecar = candidate_chunk.get(CONTEXTUAL_CHUNKING_SIDECAR_KEY)
    if isinstance(sidecar, dict):
        return render_retrieval_context_from_sidecar(sidecar=sidecar)

    return ""


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
    contextual_sidecar_parent_symbol_chunk_count: int = 0
    contextual_sidecar_parent_symbol_coverage_ratio: float = 0.0
    contextual_sidecar_reference_hint_chunk_count: int = 0
    contextual_sidecar_reference_hint_coverage_ratio: float = 0.0
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
    graph_source_provider_loaded: bool = False
    graph_source_projection_fallback: bool = False
    graph_source_edge_count: int = 0
    graph_source_inbound_signal_chunk_count: int = 0
    graph_source_inbound_signal_coverage_ratio: float = 0.0
    graph_source_centrality_signal_chunk_count: int = 0
    graph_source_centrality_signal_coverage_ratio: float = 0.0
    graph_source_pagerank_signal_chunk_count: int = 0
    graph_source_pagerank_signal_coverage_ratio: float = 0.0

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
            "contextual_sidecar_parent_symbol_chunk_count": float(
                self.contextual_sidecar_parent_symbol_chunk_count
            ),
            "contextual_sidecar_parent_symbol_coverage_ratio": (
                self.contextual_sidecar_parent_symbol_coverage_ratio
            ),
            "contextual_sidecar_reference_hint_chunk_count": float(
                self.contextual_sidecar_reference_hint_chunk_count
            ),
            "contextual_sidecar_reference_hint_coverage_ratio": (
                self.contextual_sidecar_reference_hint_coverage_ratio
            ),
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
            "graph_source_provider_loaded": (
                1.0 if self.graph_source_provider_loaded else 0.0
            ),
            "graph_source_projection_fallback": (
                1.0 if self.graph_source_projection_fallback else 0.0
            ),
            "graph_source_edge_count": float(self.graph_source_edge_count),
            "graph_source_inbound_signal_chunk_count": float(
                self.graph_source_inbound_signal_chunk_count
            ),
            "graph_source_inbound_signal_coverage_ratio": (
                self.graph_source_inbound_signal_coverage_ratio
            ),
            "graph_source_centrality_signal_chunk_count": float(
                self.graph_source_centrality_signal_chunk_count
            ),
            "graph_source_centrality_signal_coverage_ratio": (
                self.graph_source_centrality_signal_coverage_ratio
            ),
            "graph_source_pagerank_signal_chunk_count": float(
                self.graph_source_pagerank_signal_chunk_count
            ),
            "graph_source_pagerank_signal_coverage_ratio": (
                self.graph_source_pagerank_signal_coverage_ratio
            ),
        }


__all__ = [
    "CONTEXTUAL_CHUNKING_SIDECAR_KEY",
    "INTERNAL_CHUNK_SIDECAR_KEYS",
    "RETRIEVAL_CONTEXT_SIDECAR_KEY",
    "ROBUST_SIGNATURE_SIDECAR_KEY",
    "TOPOLOGICAL_SHIELD_SIDECAR_KEY",
    "ChunkCandidate",
    "ChunkMetrics",
    "render_retrieval_context_from_sidecar",
    "resolve_retrieval_context_text",
    "strip_internal_chunk_sidecars",
]
