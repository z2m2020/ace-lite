from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.entrypoint_runtime import (
    EmbeddingRuntimeKwargs,
    MemoryGatePostprocessRuntimeKwargs,
    RetrievalPolicyRuntimeKwargs,
)
from ace_lite.mcp_server.config import AceLiteMcpConfig


class PlanRequestRunPlanKwargs(
    EmbeddingRuntimeKwargs,
    MemoryGatePostprocessRuntimeKwargs,
    RetrievalPolicyRuntimeKwargs,
):
    memory_auto_tag_mode: str | None
    top_k_files: int
    min_candidate_score: int
    candidate_relative_threshold: float
    candidate_ranker: str
    deterministic_refine_enabled: bool
    hybrid_re2_fusion_mode: str
    hybrid_re2_rrf_k: int
    repomap_signal_weights: dict[str, float] | None
    lsp_enabled: bool
    plugins_enabled: bool


PLAN_REQUEST_RUN_PLAN_KWARGS_KEYS = frozenset(
    PlanRequestRunPlanKwargs.__annotations__.keys()
)


@dataclass(frozen=True, slots=True)
class PlanRequestOptions:
    top_k_files: int
    min_candidate_score: int
    retrieval_policy: str
    lsp_enabled: bool
    plugins_enabled: bool
    candidate_relative_threshold: float
    candidate_ranker: str
    deterministic_refine_enabled: bool
    hybrid_re2_fusion_mode: str
    hybrid_re2_rrf_k: int
    repomap_signal_weights: dict[str, float] | None
    policy_version: str
    embedding_enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_index_path: str
    embedding_rerank_pool: int
    embedding_lexical_weight: float
    embedding_semantic_weight: float
    embedding_min_similarity: float
    embedding_fail_open: bool
    memory_notes_enabled: bool
    memory_auto_tag_mode: str | None
    memory_gate_enabled: bool
    memory_gate_mode: str
    memory_postprocess_enabled: bool
    memory_postprocess_noise_filter_enabled: bool
    memory_postprocess_length_norm_anchor_chars: int
    memory_postprocess_time_decay_half_life_days: float
    memory_postprocess_hard_min_score: float
    memory_postprocess_diversity_enabled: bool
    memory_postprocess_diversity_similarity_threshold: float

    def to_run_plan_kwargs(self) -> PlanRequestRunPlanKwargs:
        return {
            "top_k_files": int(self.top_k_files),
            "min_candidate_score": int(self.min_candidate_score),
            "candidate_relative_threshold": float(self.candidate_relative_threshold),
            "candidate_ranker": str(self.candidate_ranker),
            "deterministic_refine_enabled": bool(self.deterministic_refine_enabled),
            "hybrid_re2_fusion_mode": str(self.hybrid_re2_fusion_mode),
            "hybrid_re2_rrf_k": int(self.hybrid_re2_rrf_k),
            "embedding_enabled": bool(self.embedding_enabled),
            "embedding_provider": str(self.embedding_provider),
            "embedding_model": str(self.embedding_model),
            "embedding_dimension": int(self.embedding_dimension),
            "embedding_index_path": str(self.embedding_index_path),
            "embedding_rerank_pool": int(self.embedding_rerank_pool),
            "embedding_lexical_weight": float(self.embedding_lexical_weight),
            "embedding_semantic_weight": float(self.embedding_semantic_weight),
            "embedding_min_similarity": float(self.embedding_min_similarity),
            "embedding_fail_open": bool(self.embedding_fail_open),
            "repomap_signal_weights": self.repomap_signal_weights,
            "retrieval_policy": str(self.retrieval_policy),
            "policy_version": str(self.policy_version),
            "lsp_enabled": bool(self.lsp_enabled),
            "plugins_enabled": bool(self.plugins_enabled),
            "memory_gate_enabled": bool(self.memory_gate_enabled),
            "memory_auto_tag_mode": (
                str(self.memory_auto_tag_mode).strip().lower()
                if self.memory_auto_tag_mode is not None
                else None
            ),
            "memory_gate_mode": str(self.memory_gate_mode),
            "memory_postprocess_enabled": bool(self.memory_postprocess_enabled),
            "memory_postprocess_noise_filter_enabled": bool(
                self.memory_postprocess_noise_filter_enabled
            ),
            "memory_postprocess_length_norm_anchor_chars": int(
                self.memory_postprocess_length_norm_anchor_chars
            ),
            "memory_postprocess_time_decay_half_life_days": float(
                self.memory_postprocess_time_decay_half_life_days
            ),
            "memory_postprocess_hard_min_score": float(
                self.memory_postprocess_hard_min_score
            ),
            "memory_postprocess_diversity_enabled": bool(
                self.memory_postprocess_diversity_enabled
            ),
            "memory_postprocess_diversity_similarity_threshold": float(
                self.memory_postprocess_diversity_similarity_threshold
            ),
        }


def resolve_plan_request_options(
    *,
    config: AceLiteMcpConfig,
    top_k_files: int,
    min_candidate_score: int,
    retrieval_policy: str,
    lsp_enabled: bool,
    plugins_enabled: bool,
    config_pack_overrides: dict[str, Any] | None,
) -> PlanRequestOptions:
    effective_top_k_files = max(1, int(top_k_files))
    effective_min_candidate_score = max(0, int(min_candidate_score))
    effective_retrieval_policy = (
        str(retrieval_policy or "auto").strip().lower() or "auto"
    )
    effective_lsp_enabled = bool(lsp_enabled)
    effective_plugins_enabled = bool(plugins_enabled)

    candidate_relative_threshold = 0.0
    candidate_ranker = "rrf_hybrid"
    deterministic_refine_enabled = True
    hybrid_re2_fusion_mode = "linear"
    hybrid_re2_rrf_k = 60
    repomap_signal_weights: dict[str, float] | None = None
    policy_version = "v1"
    embedding_enabled = bool(config.embedding_enabled)
    embedding_provider = str(config.embedding_provider or "hash").strip().lower() or "hash"
    embedding_model = str(config.embedding_model or "hash-v1").strip() or "hash-v1"
    embedding_dimension = max(8, int(config.embedding_dimension))
    embedding_index_path = (
        str(config.embedding_index_path or "context-map/embeddings/index.json").strip()
        or "context-map/embeddings/index.json"
    )
    embedding_rerank_pool = max(1, int(config.embedding_rerank_pool))
    embedding_lexical_weight = float(config.embedding_lexical_weight)
    embedding_semantic_weight = float(config.embedding_semantic_weight)
    embedding_min_similarity = float(config.embedding_min_similarity)
    embedding_fail_open = bool(config.embedding_fail_open)
    memory_notes_enabled = True
    memory_auto_tag_mode: str | None = "repo"
    memory_gate_enabled = False
    memory_gate_mode = "auto"
    memory_postprocess_enabled = False
    memory_postprocess_noise_filter_enabled = True
    memory_postprocess_length_norm_anchor_chars = 500
    memory_postprocess_time_decay_half_life_days = 0.0
    memory_postprocess_hard_min_score = 0.0
    memory_postprocess_diversity_enabled = True
    memory_postprocess_diversity_similarity_threshold = 0.9

    overrides = (
        config_pack_overrides
        if isinstance(config_pack_overrides, dict)
        else {}
    )
    if overrides:
        if effective_top_k_files == 8 and "top_k_files" in overrides:
            effective_top_k_files = max(
                1,
                _coerce_int(overrides.get("top_k_files"), effective_top_k_files),
            )
        if effective_min_candidate_score == 2 and "min_candidate_score" in overrides:
            effective_min_candidate_score = max(
                0,
                _coerce_int(
                    overrides.get("min_candidate_score"),
                    effective_min_candidate_score,
                ),
            )
        if effective_retrieval_policy == "auto" and "retrieval_policy" in overrides:
            effective_retrieval_policy = (
                str(overrides.get("retrieval_policy") or effective_retrieval_policy)
                .strip()
                .lower()
                or effective_retrieval_policy
            )
        if not effective_lsp_enabled and "lsp_enabled" in overrides:
            effective_lsp_enabled = _coerce_bool(
                overrides.get("lsp_enabled"),
                effective_lsp_enabled,
            )
        if not effective_plugins_enabled and "plugins_enabled" in overrides:
            effective_plugins_enabled = _coerce_bool(
                overrides.get("plugins_enabled"),
                effective_plugins_enabled,
            )

        if "candidate_relative_threshold" in overrides:
            candidate_relative_threshold = max(
                0.0,
                min(
                    1.0,
                    _coerce_float(
                        overrides.get("candidate_relative_threshold"),
                        candidate_relative_threshold,
                    ),
                ),
            )
        if "candidate_ranker" in overrides:
            candidate_ranker = (
                str(overrides.get("candidate_ranker") or candidate_ranker).strip().lower()
                or candidate_ranker
            )
        if "deterministic_refine_enabled" in overrides:
            deterministic_refine_enabled = _coerce_bool(
                overrides.get("deterministic_refine_enabled"),
                deterministic_refine_enabled,
            )
        if "hybrid_re2_fusion_mode" in overrides:
            hybrid_re2_fusion_mode = (
                str(overrides.get("hybrid_re2_fusion_mode") or hybrid_re2_fusion_mode)
                .strip()
                .lower()
                or hybrid_re2_fusion_mode
            )
        if "hybrid_re2_rrf_k" in overrides:
            hybrid_re2_rrf_k = max(
                1,
                _coerce_int(overrides.get("hybrid_re2_rrf_k"), hybrid_re2_rrf_k),
            )
        if "repomap_signal_weights" in overrides:
            repomap_signal_weights = _coerce_float_dict(
                overrides.get("repomap_signal_weights")
            )
        if "policy_version" in overrides:
            policy_version = (
                str(overrides.get("policy_version") or policy_version).strip()
                or policy_version
            )
        if "embedding_enabled" in overrides:
            embedding_enabled = _coerce_bool(
                overrides.get("embedding_enabled"),
                embedding_enabled,
            )
        if "embedding_provider" in overrides:
            embedding_provider = (
                str(overrides.get("embedding_provider") or embedding_provider)
                .strip()
                .lower()
                or embedding_provider
            )
        if "embedding_model" in overrides:
            embedding_model = (
                str(overrides.get("embedding_model") or embedding_model).strip()
                or embedding_model
            )
        if "embedding_dimension" in overrides:
            embedding_dimension = max(
                8,
                _coerce_int(overrides.get("embedding_dimension"), embedding_dimension),
            )
        if "embedding_index_path" in overrides:
            embedding_index_path = (
                str(overrides.get("embedding_index_path") or embedding_index_path).strip()
                or embedding_index_path
            )
        if "embedding_rerank_pool" in overrides:
            embedding_rerank_pool = max(
                1,
                _coerce_int(overrides.get("embedding_rerank_pool"), embedding_rerank_pool),
            )
        if "embedding_lexical_weight" in overrides:
            embedding_lexical_weight = max(
                0.0,
                _coerce_float(
                    overrides.get("embedding_lexical_weight"),
                    embedding_lexical_weight,
                ),
            )
        if "embedding_semantic_weight" in overrides:
            embedding_semantic_weight = max(
                0.0,
                _coerce_float(
                    overrides.get("embedding_semantic_weight"),
                    embedding_semantic_weight,
                ),
            )
        if "embedding_min_similarity" in overrides:
            embedding_min_similarity = _coerce_float(
                overrides.get("embedding_min_similarity"),
                embedding_min_similarity,
            )
        if "embedding_fail_open" in overrides:
            embedding_fail_open = _coerce_bool(
                overrides.get("embedding_fail_open"),
                embedding_fail_open,
            )
        if "memory_notes_enabled" in overrides:
            memory_notes_enabled = _coerce_bool(
                overrides.get("memory_notes_enabled"),
                memory_notes_enabled,
            )
        if "memory_auto_tag_mode" in overrides:
            raw_memory_auto_tag_mode = str(
                overrides.get("memory_auto_tag_mode") or ""
            ).strip().lower()
            memory_auto_tag_mode = raw_memory_auto_tag_mode or None
        if "memory_gate_enabled" in overrides:
            memory_gate_enabled = _coerce_bool(
                overrides.get("memory_gate_enabled"),
                memory_gate_enabled,
            )
        if "memory_gate_mode" in overrides:
            memory_gate_mode = (
                str(overrides.get("memory_gate_mode") or memory_gate_mode).strip().lower()
                or memory_gate_mode
            )
        if "memory_postprocess_enabled" in overrides:
            memory_postprocess_enabled = _coerce_bool(
                overrides.get("memory_postprocess_enabled"),
                memory_postprocess_enabled,
            )
        if "memory_postprocess_noise_filter_enabled" in overrides:
            memory_postprocess_noise_filter_enabled = _coerce_bool(
                overrides.get("memory_postprocess_noise_filter_enabled"),
                memory_postprocess_noise_filter_enabled,
            )
        if "memory_postprocess_length_norm_anchor_chars" in overrides:
            memory_postprocess_length_norm_anchor_chars = max(
                1,
                _coerce_int(
                    overrides.get("memory_postprocess_length_norm_anchor_chars"),
                    memory_postprocess_length_norm_anchor_chars,
                ),
            )
        if "memory_postprocess_time_decay_half_life_days" in overrides:
            memory_postprocess_time_decay_half_life_days = max(
                0.0,
                _coerce_float(
                    overrides.get("memory_postprocess_time_decay_half_life_days"),
                    memory_postprocess_time_decay_half_life_days,
                ),
            )
        if "memory_postprocess_hard_min_score" in overrides:
            memory_postprocess_hard_min_score = max(
                0.0,
                _coerce_float(
                    overrides.get("memory_postprocess_hard_min_score"),
                    memory_postprocess_hard_min_score,
                ),
            )
        if "memory_postprocess_diversity_enabled" in overrides:
            memory_postprocess_diversity_enabled = _coerce_bool(
                overrides.get("memory_postprocess_diversity_enabled"),
                memory_postprocess_diversity_enabled,
            )
        if "memory_postprocess_diversity_similarity_threshold" in overrides:
            memory_postprocess_diversity_similarity_threshold = max(
                0.0,
                min(
                    1.0,
                    _coerce_float(
                        overrides.get("memory_postprocess_diversity_similarity_threshold"),
                        memory_postprocess_diversity_similarity_threshold,
                    ),
                ),
            )

    return PlanRequestOptions(
        top_k_files=effective_top_k_files,
        min_candidate_score=effective_min_candidate_score,
        retrieval_policy=effective_retrieval_policy,
        lsp_enabled=effective_lsp_enabled,
        plugins_enabled=effective_plugins_enabled,
        candidate_relative_threshold=candidate_relative_threshold,
        candidate_ranker=candidate_ranker,
        deterministic_refine_enabled=deterministic_refine_enabled,
        hybrid_re2_fusion_mode=hybrid_re2_fusion_mode,
        hybrid_re2_rrf_k=hybrid_re2_rrf_k,
        repomap_signal_weights=repomap_signal_weights,
        policy_version=policy_version,
        embedding_enabled=embedding_enabled,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_index_path=embedding_index_path,
        embedding_rerank_pool=embedding_rerank_pool,
        embedding_lexical_weight=embedding_lexical_weight,
        embedding_semantic_weight=embedding_semantic_weight,
        embedding_min_similarity=embedding_min_similarity,
        embedding_fail_open=embedding_fail_open,
        memory_notes_enabled=memory_notes_enabled,
        memory_auto_tag_mode=memory_auto_tag_mode,
        memory_gate_enabled=memory_gate_enabled,
        memory_gate_mode=memory_gate_mode,
        memory_postprocess_enabled=memory_postprocess_enabled,
        memory_postprocess_noise_filter_enabled=memory_postprocess_noise_filter_enabled,
        memory_postprocess_length_norm_anchor_chars=memory_postprocess_length_norm_anchor_chars,
        memory_postprocess_time_decay_half_life_days=memory_postprocess_time_decay_half_life_days,
        memory_postprocess_hard_min_score=memory_postprocess_hard_min_score,
        memory_postprocess_diversity_enabled=memory_postprocess_diversity_enabled,
        memory_postprocess_diversity_similarity_threshold=memory_postprocess_diversity_similarity_threshold,
    )


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(fallback)


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(fallback)


def _coerce_float_dict(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    output: dict[str, float] = {}
    for key, raw in value.items():
        name = str(key or "").strip().lower()
        if not name:
            continue
        output[name] = float(_coerce_float(raw, 0.0))
    return output or None


__all__ = [
    "PLAN_REQUEST_RUN_PLAN_KWARGS_KEYS",
    "PlanRequestOptions",
    "PlanRequestRunPlanKwargs",
    "resolve_plan_request_options",
]
