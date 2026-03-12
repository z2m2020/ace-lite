"""Typed orchestrator configuration model.

This module defines the runtime configuration contract for ``AceOrchestrator``.
It is intentionally strict (``extra='forbid'``) to avoid silent typos and to
make configuration changes explicit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, field_validator, model_validator

from ace_lite.chunking.disclosure_policy import CHUNK_DISCLOSURE_CHOICES
from ace_lite.pipeline.plugin_runtime import (
    normalize_remote_slot_allowlist,
    normalize_remote_slot_policy_mode,
)
from ace_lite.pydantic_utils import StrictModel as _StrictModel
from ace_lite.rankers import normalize_fusion_mode
from ace_lite.scip import SCIP_PROVIDERS
from ace_lite.scoring_config import (
    CANDIDATE_RANKER_CHOICES,
    CHUNK_DIVERSITY_KIND_PENALTY,
    CHUNK_DIVERSITY_LOCALITY_PENALTY,
    CHUNK_DIVERSITY_LOCALITY_WINDOW,
    CHUNK_DIVERSITY_PATH_PENALTY,
    CHUNK_DIVERSITY_SYMBOL_FAMILY_PENALTY,
    HYBRID_BM25_WEIGHT,
    HYBRID_COMBINED_SCALE,
    HYBRID_COVERAGE_WEIGHT,
    HYBRID_HEURISTIC_WEIGHT,
    HYBRID_RRF_K_DEFAULT,
    MEMORY_DISCLOSURE_MODES,
    MEMORY_STRATEGIES,
    SBFL_METRIC_CHOICES,
)
from ace_lite.token_estimator import normalize_tokenizer_model
from ace_lite.utils import (
    normalize_choice,
    normalize_lower_str,
    normalize_optional_str,
    to_float,
    to_lower_list,
)


def _normalize_positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except Exception:
        return default


MemoryAutoTagMode = Literal["repo", "user", "global"]
MemoryTimezoneMode = Literal["utc", "local", "explicit"]
MemoryGateMode = Literal["auto", "always", "never"]
AdaptiveRouterMode = Literal["observe", "shadow", "enforce"]
ChunkGuardMode = Literal["off", "report_only", "enforce"]
TopologicalShieldMode = Literal["off", "report_only", "enforce"]


class MemoryNamespaceConfig(_StrictModel):
    container_tag: str | None = None
    auto_tag_mode: MemoryAutoTagMode | None = None

    @field_validator("container_tag", mode="before")
    @classmethod
    def _normalize_container_tag(cls, value: Any) -> str | None:
        return normalize_optional_str(value)

    @field_validator("auto_tag_mode", mode="before")
    @classmethod
    def _normalize_auto_tag_mode(cls, value: Any) -> MemoryAutoTagMode | None:
        normalized = normalize_lower_str(value, default="")
        if not normalized:
            return None
        if normalized not in ("repo", "user", "global"):
            return None
        return cast(MemoryAutoTagMode, normalized)


class MemoryGateConfig(_StrictModel):
    enabled: bool = False
    mode: MemoryGateMode = "auto"

    @field_validator("mode", mode="before")
    @classmethod
    def _normalize_mode(cls, value: Any) -> MemoryGateMode:
        normalized = normalize_lower_str(value, default="auto") or "auto"
        if normalized not in ("auto", "always", "never"):
            normalized = "auto"
        return cast(MemoryGateMode, normalized)


class MemoryPostprocessConfig(_StrictModel):
    enabled: bool = False
    noise_filter_enabled: bool = True
    length_norm_anchor_chars: int = 500
    time_decay_half_life_days: float = 0.0
    hard_min_score: float = 0.0
    diversity_enabled: bool = True
    diversity_similarity_threshold: float = 0.9

    @field_validator("length_norm_anchor_chars", mode="before")
    @classmethod
    def _normalize_anchor(cls, value: Any) -> int:
        return _normalize_positive_int(value, 500)

    @field_validator("time_decay_half_life_days", mode="before")
    @classmethod
    def _normalize_half_life(cls, value: Any) -> float:
        return max(0.0, to_float(value, default=0.0))

    @field_validator("hard_min_score", mode="before")
    @classmethod
    def _normalize_hard_min(cls, value: Any) -> float:
        return max(0.0, to_float(value, default=0.0))

    @field_validator("diversity_similarity_threshold", mode="before")
    @classmethod
    def _normalize_div_thr(cls, value: Any) -> float:
        thr = to_float(value, default=0.9)
        return max(0.0, min(1.0, thr))


class MemoryProfileConfig(_StrictModel):
    enabled: bool = False
    path: str | Path = "~/.ace-lite/profile.json"
    top_n: int = 4
    token_budget: int = 160
    expiry_enabled: bool = True
    ttl_days: int = 90
    max_age_days: int = 365

    @field_validator("path", mode="before")
    @classmethod
    def _normalize_path(cls, value: Any) -> str | Path:
        normalized = str(value or "").strip()
        return normalized or "~/.ace-lite/profile.json"

    @field_validator("top_n", mode="before")
    @classmethod
    def _normalize_top_n(cls, value: Any) -> int:
        return _normalize_positive_int(value, 4)

    @field_validator("token_budget", mode="before")
    @classmethod
    def _normalize_token_budget(cls, value: Any) -> int:
        return _normalize_positive_int(value, 160)

    @field_validator("ttl_days", mode="before")
    @classmethod
    def _normalize_ttl_days(cls, value: Any) -> int:
        return _normalize_positive_int(value, 90)

    @field_validator("max_age_days", mode="before")
    @classmethod
    def _normalize_max_age_days(cls, value: Any) -> int:
        return _normalize_positive_int(value, 365)


class MemoryFeedbackConfig(_StrictModel):
    enabled: bool = False
    path: str | Path = "~/.ace-lite/profile.json"
    max_entries: int = 512
    boost_per_select: float = 0.15
    max_boost: float = 0.6
    decay_days: float = 60.0

    @field_validator("path", mode="before")
    @classmethod
    def _normalize_path(cls, value: Any) -> str | Path:
        normalized = str(value or "").strip()
        return normalized or "~/.ace-lite/profile.json"

    @field_validator("max_entries", mode="before")
    @classmethod
    def _normalize_max_entries(cls, value: Any) -> int:
        try:
            return max(0, int(value))
        except Exception:
            return 512

    @field_validator("boost_per_select", mode="before")
    @classmethod
    def _normalize_boost_per_select(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 0.15

    @field_validator("max_boost", mode="before")
    @classmethod
    def _normalize_max_boost(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 0.6

    @field_validator("decay_days", mode="before")
    @classmethod
    def _normalize_decay_days(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 60.0


class MemoryTemporalConfig(_StrictModel):
    enabled: bool = True
    recency_boost_enabled: bool = False
    recency_boost_max: float = 0.15
    timezone_mode: MemoryTimezoneMode = "utc"

    @field_validator("recency_boost_max", mode="before")
    @classmethod
    def _normalize_recency_boost_max(cls, value: Any) -> float:
        try:
            normalized = float(value)
        except Exception:
            normalized = 0.15
        return max(0.0, min(1.0, normalized))

    @field_validator("timezone_mode", mode="before")
    @classmethod
    def _normalize_timezone_mode(cls, value: Any) -> str:
        return normalize_choice(value, ("utc", "local", "explicit"), default="utc")


class MemoryCaptureConfig(_StrictModel):
    enabled: bool = False
    notes_path: str | Path = "context-map/memory_notes.jsonl"
    min_query_length: int = 24
    keywords: list[str] | tuple[str, ...] | None = None

    @field_validator("notes_path", mode="before")
    @classmethod
    def _normalize_notes_path(cls, value: Any) -> str | Path:
        normalized = str(value or "").strip()
        return normalized or "context-map/memory_notes.jsonl"

    @field_validator("min_query_length", mode="before")
    @classmethod
    def _normalize_min_query_length(cls, value: Any) -> int:
        return _normalize_positive_int(value, 24)

    @field_validator("keywords", mode="before")
    @classmethod
    def _normalize_keywords(cls, value: Any) -> tuple[str, ...] | None:
        normalized = to_lower_list(value)
        if not normalized:
            return None
        deduped: list[str] = []
        for item in normalized:
            if item not in deduped:
                deduped.append(item)
        return tuple(deduped)


MemoryNotesMode = Literal["supplement", "prefer_local", "local_only"]


class MemoryNotesConfig(_StrictModel):
    enabled: bool = False
    path: str | Path = "context-map/memory_notes.jsonl"
    limit: int = 8
    mode: MemoryNotesMode = "supplement"
    expiry_enabled: bool = True
    ttl_days: int = 90
    max_age_days: int = 365

    @field_validator("path", mode="before")
    @classmethod
    def _normalize_path(cls, value: Any) -> str | Path:
        normalized = str(value or "").strip()
        return normalized or "context-map/memory_notes.jsonl"

    @field_validator("limit", mode="before")
    @classmethod
    def _normalize_limit(cls, value: Any) -> int:
        return _normalize_positive_int(value, 8)

    @field_validator("mode", mode="before")
    @classmethod
    def _normalize_mode(cls, value: Any) -> str:
        return normalize_choice(
            value,
            ("supplement", "prefer_local", "local_only"),
            default="supplement",
        )

    @field_validator("ttl_days", mode="before")
    @classmethod
    def _normalize_ttl_days(cls, value: Any) -> int:
        return _normalize_positive_int(value, 90)

    @field_validator("max_age_days", mode="before")
    @classmethod
    def _normalize_max_age_days(cls, value: Any) -> int:
        return _normalize_positive_int(value, 365)


class MemoryConfig(_StrictModel):
    disclosure_mode: str = "compact"
    preview_max_chars: int = 280
    strategy: str = "hybrid"
    timeline_enabled: bool = True
    namespace: MemoryNamespaceConfig = Field(default_factory=MemoryNamespaceConfig)
    gate: MemoryGateConfig = Field(default_factory=MemoryGateConfig)
    profile: MemoryProfileConfig = Field(default_factory=MemoryProfileConfig)
    temporal: MemoryTemporalConfig = Field(default_factory=MemoryTemporalConfig)
    feedback: MemoryFeedbackConfig = Field(default_factory=MemoryFeedbackConfig)
    capture: MemoryCaptureConfig = Field(default_factory=MemoryCaptureConfig)
    notes: MemoryNotesConfig = Field(default_factory=MemoryNotesConfig)
    postprocess: MemoryPostprocessConfig = Field(default_factory=MemoryPostprocessConfig)

    @field_validator("disclosure_mode", mode="before")
    @classmethod
    def _normalize_disclosure_mode(cls, value: Any) -> str:
        normalized = str(value or "compact").strip().lower() or "compact"
        if normalized not in MEMORY_DISCLOSURE_MODES:
            return "compact"
        return normalized

    @field_validator("preview_max_chars", mode="before")
    @classmethod
    def _normalize_preview_max_chars(cls, value: Any) -> int:
        try:
            return max(1, int(value))
        except Exception:
            return 280

    @field_validator("strategy", mode="before")
    @classmethod
    def _normalize_strategy(cls, value: Any) -> str:
        normalized = str(value or "hybrid").strip().lower() or "hybrid"
        if normalized not in MEMORY_STRATEGIES:
            return "hybrid"
        return normalized


class SkillsConfig(_StrictModel):
    dir: str | Path | None = None
    manifest: list[dict[str, Any]] | None = None
    precomputed_routing_enabled: bool = True
    top_n: int = 3
    token_budget: int = 1200

    @field_validator("top_n", mode="before")
    @classmethod
    def _normalize_top_n(cls, value: Any) -> int:
        return _normalize_positive_int(value, 3)

    @field_validator("token_budget", mode="before")
    @classmethod
    def _normalize_token_budget(cls, value: Any) -> int:
        return _normalize_positive_int(value, 1200)


class RetrievalConfig(_StrictModel):
    top_k_files: int = 8
    min_candidate_score: int = 2
    candidate_relative_threshold: float = 0.0
    deterministic_refine_enabled: bool = True
    candidate_ranker: str = "rrf_hybrid"
    hybrid_re2_fusion_mode: str = "linear"
    hybrid_re2_rrf_k: int = HYBRID_RRF_K_DEFAULT
    hybrid_re2_bm25_weight: float = HYBRID_BM25_WEIGHT
    hybrid_re2_heuristic_weight: float = HYBRID_HEURISTIC_WEIGHT
    hybrid_re2_coverage_weight: float = HYBRID_COVERAGE_WEIGHT
    hybrid_re2_combined_scale: float = HYBRID_COMBINED_SCALE
    exact_search_enabled: bool = False
    exact_search_time_budget_ms: int = 40
    exact_search_max_paths: int = 24
    multi_channel_rrf_enabled: bool = False
    multi_channel_rrf_k: int = HYBRID_RRF_K_DEFAULT
    multi_channel_rrf_pool_cap: int = 0
    multi_channel_rrf_code_cap: int = 0
    multi_channel_rrf_docs_cap: int = 0
    multi_channel_rrf_memory_cap: int = 0
    retrieval_policy: str = "auto"
    policy_version: str = "v1"
    adaptive_router_enabled: bool = False
    adaptive_router_mode: AdaptiveRouterMode = "observe"
    adaptive_router_model_path: str | Path = "context-map/router/model.json"
    adaptive_router_state_path: str | Path = "context-map/router/state.json"
    adaptive_router_arm_set: str = "retrieval_policy_v1"
    adaptive_router_online_bandit_enabled: bool = False
    adaptive_router_online_bandit_experiment_enabled: bool = False

    @field_validator("top_k_files", mode="before")
    @classmethod
    def _normalize_top_k_files(cls, value: Any) -> int:
        return _normalize_positive_int(value, 8)

    @field_validator("min_candidate_score", mode="before")
    @classmethod
    def _normalize_min_candidate_score(cls, value: Any) -> int:
        try:
            return max(0, int(value))
        except Exception:
            return 2

    @field_validator("candidate_relative_threshold", mode="before")
    @classmethod
    def _normalize_candidate_relative_threshold(cls, value: Any) -> float:
        try:
            normalized = float(value or 0.0)
        except Exception:
            normalized = 0.0
        return max(0.0, min(1.0, normalized))

    @field_validator("candidate_ranker", mode="before")
    @classmethod
    def _normalize_candidate_ranker(cls, value: Any) -> str:
        normalized = str(value or "heuristic").strip().lower() or "heuristic"
        if normalized not in CANDIDATE_RANKER_CHOICES:
            return "heuristic"
        return normalized

    @field_validator("hybrid_re2_fusion_mode", mode="before")
    @classmethod
    def _normalize_hybrid_re2_fusion_mode(cls, value: Any) -> str:
        return normalize_fusion_mode(str(value or "linear"))

    @field_validator("hybrid_re2_rrf_k", mode="before")
    @classmethod
    def _normalize_hybrid_re2_rrf_k(cls, value: Any) -> int:
        return _normalize_positive_int(value, HYBRID_RRF_K_DEFAULT)

    @field_validator(
        "hybrid_re2_bm25_weight",
        "hybrid_re2_heuristic_weight",
        "hybrid_re2_coverage_weight",
        "hybrid_re2_combined_scale",
        mode="before",
    )
    @classmethod
    def _normalize_hybrid_re2_weight(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 0.0

    @field_validator("exact_search_time_budget_ms", "exact_search_max_paths", mode="before")
    @classmethod
    def _normalize_exact_search_int(cls, value: Any) -> int:
        return _normalize_positive_int(value, 0)

    @field_validator("multi_channel_rrf_k", mode="before")
    @classmethod
    def _normalize_multi_channel_rrf_k(cls, value: Any) -> int:
        return _normalize_positive_int(value, HYBRID_RRF_K_DEFAULT)

    @field_validator(
        "multi_channel_rrf_pool_cap",
        "multi_channel_rrf_code_cap",
        "multi_channel_rrf_docs_cap",
        "multi_channel_rrf_memory_cap",
        mode="before",
    )
    @classmethod
    def _normalize_multi_channel_rrf_caps(cls, value: Any) -> int:
        try:
            return max(0, int(value))
        except Exception:
            return 0

    @field_validator("retrieval_policy", mode="before")
    @classmethod
    def _normalize_retrieval_policy(cls, value: Any) -> str:
        return str(value or "auto").strip().lower() or "auto"

    @field_validator("policy_version", mode="before")
    @classmethod
    def _normalize_policy_version(cls, value: Any) -> str:
        return str(value or "v1").strip() or "v1"

    @field_validator("adaptive_router_mode", mode="before")
    @classmethod
    def _normalize_adaptive_router_mode(cls, value: Any) -> AdaptiveRouterMode:
        normalized = normalize_lower_str(value, default="observe") or "observe"
        if normalized not in ("observe", "shadow", "enforce"):
            normalized = "observe"
        return cast(AdaptiveRouterMode, normalized)

    @field_validator("adaptive_router_model_path", "adaptive_router_state_path", mode="before")
    @classmethod
    def _normalize_adaptive_router_path(cls, value: Any) -> str | Path:
        normalized = str(value or "").strip()
        return normalized

    @field_validator("adaptive_router_arm_set", mode="before")
    @classmethod
    def _normalize_adaptive_router_arm_set(cls, value: Any) -> str:
        return str(value or "retrieval_policy_v1").strip() or "retrieval_policy_v1"


class IndexConfig(_StrictModel):
    languages: list[str] | tuple[str, ...] | None = None
    cache_path: str | Path = "context-map/index.json"
    incremental: bool = True
    conventions_files: list[str] | tuple[str, ...] | None = None


class RepomapConfig(_StrictModel):
    enabled: bool = True
    top_k: int = 8
    neighbor_limit: int = 20
    budget_tokens: int = 800
    ranking_profile: str = "graph"
    signal_weights: dict[str, float] | None = None

    @field_validator("ranking_profile", mode="before")
    @classmethod
    def _normalize_ranking_profile(cls, value: Any) -> str:
        return str(value or "graph").strip().lower() or "graph"

    @field_validator("signal_weights", mode="before")
    @classmethod
    def _normalize_signal_weights(cls, value: Any) -> dict[str, float] | None:
        if not isinstance(value, dict):
            return None
        normalized: dict[str, float] = {}
        for key, raw in value.items():
            normalized_key = str(key).strip().lower()
            if not normalized_key:
                continue
            normalized_value = to_float(raw)
            if normalized_value is None:
                continue
            normalized[normalized_key] = normalized_value
        return normalized or None


class LspConfig(_StrictModel):
    enabled: bool = False
    top_n: int = 5
    commands: dict[str, list[str]] | None = None
    xref_enabled: bool = False
    xref_top_n: int = 3
    time_budget_ms: int = 1500
    xref_commands: dict[str, list[str]] | None = None

    @field_validator("top_n", "xref_top_n", mode="before")
    @classmethod
    def _normalize_non_negative_int(cls, value: Any) -> int:
        try:
            return max(0, int(value))
        except Exception:
            return 0

    @field_validator("time_budget_ms", mode="before")
    @classmethod
    def _normalize_time_budget_ms(cls, value: Any) -> int:
        try:
            return max(1, int(value))
        except Exception:
            return 1500


class PluginsConfig(_StrictModel):
    enabled: bool = True
    remote_slot_allowlist: list[str] | tuple[str, ...] | None = None
    remote_slot_policy_mode: str = "strict"

    @field_validator("remote_slot_allowlist", mode="before")
    @classmethod
    def _normalize_remote_slot_allowlist(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return normalize_remote_slot_allowlist(parts)
        if isinstance(value, (list, tuple, set)):
            return normalize_remote_slot_allowlist([str(item) for item in value])
        return None

    @field_validator("remote_slot_policy_mode", mode="before")
    @classmethod
    def _normalize_remote_slot_policy_mode(cls, value: Any) -> str:
        return normalize_remote_slot_policy_mode(str(value or "strict"))


class ChunkingConfig(_StrictModel):
    class GuardConfig(_StrictModel):
        enabled: bool = False
        mode: ChunkGuardMode = "off"
        lambda_penalty: float = 0.8
        min_pool: int = 4
        max_pool: int = 32
        min_marginal_utility: float = 0.0
        compatibility_min_overlap: float = 0.3

        @field_validator("mode", mode="before")
        @classmethod
        def _normalize_mode(cls, value: Any) -> ChunkGuardMode:
            normalized = normalize_lower_str(value, default="off") or "off"
            if normalized not in ("off", "report_only", "enforce"):
                normalized = "off"
            return cast(ChunkGuardMode, normalized)

        @field_validator("lambda_penalty", "min_marginal_utility", mode="before")
        @classmethod
        def _normalize_non_negative_float(cls, value: Any) -> float:
            try:
                return max(0.0, float(value))
            except Exception:
                return 0.0

        @field_validator("compatibility_min_overlap", mode="before")
        @classmethod
        def _normalize_overlap(cls, value: Any) -> float:
            try:
                normalized = float(value)
            except Exception:
                normalized = 0.3
            return max(0.0, min(1.0, normalized))

        @field_validator("min_pool", "max_pool", mode="before")
        @classmethod
        def _normalize_pool(cls, value: Any) -> int:
            return _normalize_positive_int(value, 1)

        @model_validator(mode="after")
        def _normalize_state(self) -> ChunkingConfig.GuardConfig:
            mode = self.mode
            enabled = bool(self.enabled)
            if enabled and mode == "off":
                mode = "report_only"
            enabled = mode != "off"
            max_pool = max(int(self.min_pool), int(self.max_pool))
            self.enabled = enabled
            self.mode = mode
            self.max_pool = max_pool
            return self

    class TopologicalShieldConfig(_StrictModel):
        enabled: bool = False
        mode: TopologicalShieldMode = "off"
        max_attenuation: float = 0.6
        shared_parent_attenuation: float = 0.2
        adjacency_attenuation: float = 0.5

        @field_validator("mode", mode="before")
        @classmethod
        def _normalize_mode(cls, value: Any) -> TopologicalShieldMode:
            normalized = normalize_lower_str(value, default="off") or "off"
            if normalized not in ("off", "report_only", "enforce"):
                normalized = "off"
            return cast(TopologicalShieldMode, normalized)

        @field_validator(
            "max_attenuation",
            "shared_parent_attenuation",
            "adjacency_attenuation",
            mode="before",
        )
        @classmethod
        def _normalize_weight(cls, value: Any) -> float:
            try:
                normalized = float(value)
            except Exception:
                normalized = 0.0
            return max(0.0, min(1.0, normalized))

        @model_validator(mode="after")
        def _normalize_state(self) -> ChunkingConfig.TopologicalShieldConfig:
            mode = self.mode
            enabled = bool(self.enabled)
            if enabled and mode == "off":
                mode = "report_only"
            enabled = mode != "off"
            max_attenuation = max(0.0, min(1.0, float(self.max_attenuation)))
            shared_parent_attenuation = max(
                0.0, min(max_attenuation, float(self.shared_parent_attenuation))
            )
            adjacency_attenuation = max(
                shared_parent_attenuation,
                min(max_attenuation, float(self.adjacency_attenuation)),
            )
            self.enabled = enabled
            self.mode = mode
            self.max_attenuation = max_attenuation
            self.shared_parent_attenuation = shared_parent_attenuation
            self.adjacency_attenuation = adjacency_attenuation
            return self

    top_k: int = 24
    per_file_limit: int = 3
    disclosure: str = "refs"
    signature: bool = False
    snippet_max_lines: int = 18
    snippet_max_chars: int = 1200
    token_budget: int = 1200
    diversity_enabled: bool = True
    diversity_path_penalty: float = CHUNK_DIVERSITY_PATH_PENALTY
    diversity_symbol_family_penalty: float = CHUNK_DIVERSITY_SYMBOL_FAMILY_PENALTY
    diversity_kind_penalty: float = CHUNK_DIVERSITY_KIND_PENALTY
    diversity_locality_penalty: float = CHUNK_DIVERSITY_LOCALITY_PENALTY
    diversity_locality_window: int = CHUNK_DIVERSITY_LOCALITY_WINDOW
    topological_shield: TopologicalShieldConfig = Field(
        default_factory=TopologicalShieldConfig
    )
    guard: GuardConfig = Field(default_factory=GuardConfig)

    @field_validator("top_k", "per_file_limit", "snippet_max_lines", mode="before")
    @classmethod
    def _normalize_positive_int_fields(cls, value: Any) -> int:
        return _normalize_positive_int(value, 1)

    @field_validator(
        "diversity_path_penalty",
        "diversity_symbol_family_penalty",
        "diversity_kind_penalty",
        "diversity_locality_penalty",
        mode="before",
    )
    @classmethod
    def _normalize_non_negative_float_fields(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 0.0

    @field_validator("snippet_max_chars", mode="before")
    @classmethod
    def _normalize_non_negative_int_field(cls, value: Any) -> int:
        try:
            return max(0, int(value))
        except Exception:
            return 0

    @field_validator("token_budget", mode="before")
    @classmethod
    def _normalize_token_budget(cls, value: Any) -> int:
        return max(128, _normalize_positive_int(value, 1200))

    @field_validator("disclosure", mode="before")
    @classmethod
    def _normalize_disclosure(cls, value: Any) -> str:
        normalized = str(value or "refs").strip().lower() or "refs"
        if normalized not in CHUNK_DISCLOSURE_CHOICES:
            return "refs"
        return normalized

    @model_validator(mode="after")
    def _apply_signature_compatibility(self) -> ChunkingConfig:
        if self.disclosure == "refs" and bool(self.signature):
            self.disclosure = "signature"
        return self


class TokenizerConfig(_StrictModel):
    model: str = "gpt-4o-mini"

    @field_validator("model", mode="before")
    @classmethod
    def _normalize_model(cls, value: Any) -> str:
        return normalize_tokenizer_model(str(value or "gpt-4o-mini"))


class CochangeConfig(_StrictModel):
    enabled: bool = True
    cache_path: str | Path = "context-map/cochange.json"
    lookback_commits: int = 400
    half_life_days: float = 60.0
    top_neighbors: int = 12
    boost_weight: float = 1.5

    @field_validator("lookback_commits", "top_neighbors", mode="before")
    @classmethod
    def _normalize_positive_int_fields(cls, value: Any) -> int:
        return _normalize_positive_int(value, 1)

    @field_validator("half_life_days", mode="before")
    @classmethod
    def _normalize_half_life_days(cls, value: Any) -> float:
        try:
            return max(1.0, float(value))
        except Exception:
            return 60.0

    @field_validator("boost_weight", mode="before")
    @classmethod
    def _normalize_boost_weight(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 1.5


class TestSignalsConfig(_StrictModel):
    junit_xml: str | None = None
    coverage_json: str | None = None
    sbfl_json: str | None = None
    sbfl_metric: str = "ochiai"

    @field_validator("junit_xml", "coverage_json", "sbfl_json", mode="before")
    @classmethod
    def _normalize_optional_path(cls, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("sbfl_metric", mode="before")
    @classmethod
    def _normalize_sbfl_metric(cls, value: Any) -> str:
        normalized = str(value or "ochiai").strip().lower() or "ochiai"
        if normalized not in SBFL_METRIC_CHOICES:
            return "ochiai"
        return normalized


class ScipConfig(_StrictModel):
    enabled: bool = False
    index_path: str | Path = "context-map/scip/index.json"
    provider: str = "auto"
    generate_fallback: bool = True

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: Any) -> str:
        normalized = str(value or "auto").strip().lower() or "auto"
        if normalized not in SCIP_PROVIDERS:
            return "auto"
        return normalized


class EmbeddingsConfig(_StrictModel):
    enabled: bool = False
    provider: str = "hash"
    model: str = "hash-v1"
    dimension: int = 256
    index_path: str | Path = "context-map/embeddings/index.json"
    rerank_pool: int = 24
    lexical_weight: float = 0.7
    semantic_weight: float = 0.3
    min_similarity: float = 0.0
    fail_open: bool = True

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: Any) -> str:
        return str(value or "hash").strip().lower() or "hash"

    @field_validator("model", mode="before")
    @classmethod
    def _normalize_model(cls, value: Any) -> str:
        return str(value or "hash-v1").strip() or "hash-v1"

    @field_validator("dimension", mode="before")
    @classmethod
    def _normalize_dimension(cls, value: Any) -> int:
        try:
            return max(8, int(value))
        except Exception:
            return 256

    @field_validator("rerank_pool", mode="before")
    @classmethod
    def _normalize_rerank_pool(cls, value: Any) -> int:
        return _normalize_positive_int(value, 24)

    @field_validator("lexical_weight", "semantic_weight", mode="before")
    @classmethod
    def _normalize_weight(cls, value: Any) -> float:
        try:
            return max(0.0, float(value))
        except Exception:
            return 0.0

    @field_validator("min_similarity", mode="before")
    @classmethod
    def _normalize_min_similarity(cls, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0


class TraceConfig(_StrictModel):
    export_enabled: bool = False
    export_path: str | Path = "context-map/traces/stage_spans.jsonl"
    otlp_enabled: bool = False
    otlp_endpoint: str = ""
    otlp_timeout_seconds: float = 1.5

    @field_validator("otlp_endpoint", mode="before")
    @classmethod
    def _normalize_otlp_endpoint(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("otlp_timeout_seconds", mode="before")
    @classmethod
    def _normalize_otlp_timeout_seconds(cls, value: Any) -> float:
        try:
            return max(0.1, float(value))
        except Exception:
            return 1.5


class PlanReplayCacheConfig(_StrictModel):
    enabled: bool = False
    cache_path: str | Path = "context-map/plan-replay/cache.json"

    @field_validator("cache_path", mode="before")
    @classmethod
    def _normalize_cache_path(cls, value: Any) -> str | Path:
        normalized = str(value or "").strip()
        return normalized or "context-map/plan-replay/cache.json"


class OrchestratorConfig(_StrictModel):
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    repomap: RepomapConfig = Field(default_factory=RepomapConfig)
    lsp: LspConfig = Field(default_factory=LspConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    tokenizer: TokenizerConfig = Field(default_factory=TokenizerConfig)
    cochange: CochangeConfig = Field(default_factory=CochangeConfig)
    tests: TestSignalsConfig = Field(default_factory=TestSignalsConfig)
    scip: ScipConfig = Field(default_factory=ScipConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    trace: TraceConfig = Field(default_factory=TraceConfig)
    plan_replay_cache: PlanReplayCacheConfig = Field(
        default_factory=PlanReplayCacheConfig
    )


__all__ = ["OrchestratorConfig"]
