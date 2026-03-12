"""Pydantic models for validating layered ``.ace-lite.yml`` configuration.

The core config loader returns a raw merged dictionary. These models provide a
strict, type-checked validation layer for CLI usage (unknown keys are rejected)
while keeping the underlying loader lightweight.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import Field, ValidationError, field_validator

from ace_lite.chunking.disclosure_policy import CHUNK_DISCLOSURE_CHOICES
from ace_lite.pydantic_utils import StrictModel as _StrictModel
from ace_lite.repomap.ranking import RANKING_PROFILES
from ace_lite.runtime.scheduler import CronSchedule
from ace_lite.scip import SCIP_PROVIDERS
from ace_lite.scoring_config import (
    CANDIDATE_RANKER_CHOICES,
    HYBRID_FUSION_MODES,
    MEMORY_DISCLOSURE_MODES,
    MEMORY_STRATEGIES,
    SBFL_METRIC_CHOICES,
)

REMOTE_SLOT_POLICY_CHOICES: tuple[str, ...] = ("strict", "warn", "off")
RETRIEVAL_POLICY_CHOICES: tuple[str, ...] = (
    "auto",
    "bugfix_test",
    "doc_intent",
    "feature",
    "refactor",
    "general",
)
ADAPTIVE_ROUTER_MODE_CHOICES: tuple[str, ...] = ("observe", "shadow", "enforce")
CHUNK_GUARD_MODE_CHOICES: tuple[str, ...] = ("off", "report_only", "enforce")
TOPOLOGICAL_SHIELD_MODE_CHOICES: tuple[str, ...] = (
    "off",
    "report_only",
    "enforce",
)
MEMORY_AUTO_TAG_MODE_CHOICES: tuple[str, ...] = ("repo", "user", "global")
MEMORY_NOTES_MODE_CHOICES: tuple[str, ...] = ("supplement", "prefer_local", "local_only")
MEMORY_TIMEZONE_MODE_CHOICES: tuple[str, ...] = ("utc", "local", "explicit")
MEMORY_GATE_MODE_CHOICES: tuple[str, ...] = ("auto", "always", "never")
EMBEDDING_PROVIDER_CHOICES: tuple[str, ...] = (
    "hash",
    "hash_cross",
    "hash_colbert",
    "bge_m3",
    "bge_reranker",
    "sentence_transformers",
    "ollama",
)


class TokenizerConfig(_StrictModel):
    model: str | None = None


class MemoryCacheConfig(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    ttl_seconds: int | None = None
    max_entries: int | None = None


class MemoryTimelineConfig(_StrictModel):
    enabled: bool | None = None


class MemoryHybridConfig(_StrictModel):
    limit: int | None = None


class AdaptiveRouterOnlineBanditConfig(_StrictModel):
    enabled: bool | None = None
    experiment_enabled: bool | None = None


class AdaptiveRouterConfig(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    model_path: str | None = None
    state_path: str | None = None
    arm_set: str | None = None
    online_bandit: AdaptiveRouterOnlineBanditConfig | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in ADAPTIVE_ROUTER_MODE_CHOICES:
            choices = ", ".join(ADAPTIVE_ROUTER_MODE_CHOICES)
            raise ValueError(
                "Unsupported adaptive_router.mode: "
                f"{normalized}. Expected one of: {choices}"
            )
        return normalized


class MemoryNamespaceConfig(_StrictModel):
    container_tag: str | None = None
    auto_tag_mode: str | None = None

    @field_validator("container_tag")
    @classmethod
    def _normalize_container_tag(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip()
        return normalized or None

    @field_validator("auto_tag_mode")
    @classmethod
    def _validate_auto_tag_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_AUTO_TAG_MODE_CHOICES:
            choices = ", ".join(MEMORY_AUTO_TAG_MODE_CHOICES)
            raise ValueError(
                "Unsupported memory.namespace.auto_tag_mode: "
                f"{normalized}. Expected one of: {choices}"
            )
        return normalized


class MemoryProfileConfig(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    top_n: int | None = None
    token_budget: int | None = None
    expiry_enabled: bool | None = None
    ttl_days: int | None = None
    max_age_days: int | None = None


class MemoryTemporalConfig(_StrictModel):
    enabled: bool | None = None
    recency_boost_enabled: bool | None = None
    recency_boost_max: float | None = None
    timezone_mode: str | None = None

    @field_validator("timezone_mode")
    @classmethod
    def _validate_timezone_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_TIMEZONE_MODE_CHOICES:
            choices = ", ".join(MEMORY_TIMEZONE_MODE_CHOICES)
            raise ValueError(
                f"Unsupported memory.temporal.timezone_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized


class MemoryFeedbackConfig(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    max_entries: int | None = None
    boost_per_select: float | None = None
    max_boost: float | None = None
    decay_days: float | None = None


class MemoryCaptureConfig(_StrictModel):
    enabled: bool | None = None
    notes_path: str | None = None
    min_query_length: int | None = None
    keywords: list[str] | None = None


class MemoryNotesConfig(_StrictModel):
    enabled: bool | None = None
    path: str | None = None
    limit: int | None = None
    mode: str | None = None
    expiry_enabled: bool | None = None
    ttl_days: int | None = None
    max_age_days: int | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_NOTES_MODE_CHOICES:
            choices = ", ".join(MEMORY_NOTES_MODE_CHOICES)
            raise ValueError(
                f"Unsupported memory.notes.mode: {normalized}. Expected one of: {choices}"
            )
        return normalized


class MemoryGateConfig(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_GATE_MODE_CHOICES:
            choices = ", ".join(MEMORY_GATE_MODE_CHOICES)
            raise ValueError(
                f"Unsupported memory.gate.mode: {normalized}. Expected one of: {choices}"
            )
        return normalized


class MemoryPostprocessConfig(_StrictModel):
    enabled: bool | None = None
    noise_filter_enabled: bool | None = None
    length_norm_anchor_chars: int | None = None
    time_decay_half_life_days: float | None = None
    hard_min_score: float | None = None
    diversity_enabled: bool | None = None
    diversity_similarity_threshold: float | None = None


class MemoryConfig(_StrictModel):
    disclosure_mode: str | None = None
    preview_max_chars: int | None = None
    strategy: str | None = None
    cache: MemoryCacheConfig | None = None
    timeline: MemoryTimelineConfig | None = None
    hybrid: MemoryHybridConfig | None = None
    namespace: MemoryNamespaceConfig | None = None
    gate: MemoryGateConfig | None = None
    profile: MemoryProfileConfig | None = None
    temporal: MemoryTemporalConfig | None = None
    feedback: MemoryFeedbackConfig | None = None
    capture: MemoryCaptureConfig | None = None
    notes: MemoryNotesConfig | None = None
    postprocess: MemoryPostprocessConfig | None = None

    @field_validator("disclosure_mode")
    @classmethod
    def _validate_disclosure_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_DISCLOSURE_MODES:
            choices = ", ".join(MEMORY_DISCLOSURE_MODES)
            raise ValueError(
                f"Unsupported memory.disclosure_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_STRATEGIES:
            choices = ", ".join(MEMORY_STRATEGIES)
            raise ValueError(
                f"Unsupported memory.strategy: {normalized}. Expected one of: {choices}"
            )
        return normalized


class ChunkSnippetConfig(_StrictModel):
    max_lines: int | None = None
    max_chars: int | None = None


class ChunkGuardConfig(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    lambda_penalty: float | None = None
    min_pool: int | None = None
    max_pool: int | None = None
    min_marginal_utility: float | None = None
    compatibility_min_overlap: float | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in CHUNK_GUARD_MODE_CHOICES:
            choices = ", ".join(CHUNK_GUARD_MODE_CHOICES)
            raise ValueError(
                "Unsupported chunk.guard.mode: "
                f"{normalized}. Expected one of: {choices}"
            )
        return normalized


class ChunkTopologicalShieldConfig(_StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    max_attenuation: float | None = None
    shared_parent_attenuation: float | None = None
    adjacency_attenuation: float | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in TOPOLOGICAL_SHIELD_MODE_CHOICES:
            choices = ", ".join(TOPOLOGICAL_SHIELD_MODE_CHOICES)
            raise ValueError(
                "Unsupported chunk.topological_shield.mode: "
                f"{normalized}. Expected one of: {choices}"
            )
        return normalized


class ChunkConfig(_StrictModel):
    top_k: int | None = None
    per_file_limit: int | None = None
    disclosure: str | None = None
    signature: bool | None = None
    snippet: ChunkSnippetConfig | None = None
    token_budget: int | None = None
    topological_shield: ChunkTopologicalShieldConfig | None = None
    guard: ChunkGuardConfig | None = None

    @field_validator("disclosure")
    @classmethod
    def _validate_disclosure(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in CHUNK_DISCLOSURE_CHOICES:
            choices = ", ".join(CHUNK_DISCLOSURE_CHOICES)
            raise ValueError(
                f"Unsupported chunk.disclosure: {normalized}. Expected one of: {choices}"
            )
        return normalized


class SkillsConfig(_StrictModel):
    precomputed_routing_enabled: bool | None = None


class PluginsConfig(_StrictModel):
    enabled: bool | None = None
    remote_slot_policy_mode: str | None = None
    remote_slot_allowlist: list[str] | str | None = None

    @field_validator("remote_slot_policy_mode", mode="before")
    @classmethod
    def _coerce_remote_slot_policy_mode(cls, value: Any) -> Any:
        if isinstance(value, bool):
            return "strict" if value else "off"
        return value

    @field_validator("remote_slot_policy_mode")
    @classmethod
    def _validate_remote_slot_policy_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in REMOTE_SLOT_POLICY_CHOICES:
            choices = ", ".join(REMOTE_SLOT_POLICY_CHOICES)
            raise ValueError(
                f"Unsupported plugins.remote_slot_policy_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized


class IndexCliConfig(_StrictModel):
    languages: list[str] | str | None = None
    cache_path: str | None = None
    incremental: bool | None = None
    conventions_files: list[str] | str | None = None


class CochangeCliConfig(_StrictModel):
    enabled: bool | None = None
    cache_path: str | None = None
    lookback_commits: int | None = None
    half_life_days: float | None = None
    top_neighbors: int | None = None
    boost_weight: float | None = None


class SbflConfig(_StrictModel):
    metric: str | None = None
    json_path: str | None = None
    json_: str | None = Field(default=None, alias="json")

    @field_validator("metric")
    @classmethod
    def _validate_metric(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in SBFL_METRIC_CHOICES:
            choices = ", ".join(SBFL_METRIC_CHOICES)
            raise ValueError(f"Unsupported sbfl.metric: {normalized}. Expected one of: {choices}")
        return normalized


class TestsCliConfig(_StrictModel):
    junit_xml: str | None = None
    coverage_json: str | None = None
    sbfl_json: str | None = None
    sbfl_metric: str | None = None
    sbfl: SbflConfig | None = None

    @field_validator("sbfl_metric")
    @classmethod
    def _validate_sbfl_metric(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in SBFL_METRIC_CHOICES:
            choices = ", ".join(SBFL_METRIC_CHOICES)
            raise ValueError(
                f"Unsupported tests.sbfl_metric: {normalized}. Expected one of: {choices}"
            )
        return normalized


class TraceConfig(_StrictModel):
    export_enabled: bool | None = None
    export_path: str | None = None
    otlp_enabled: bool | None = None
    otlp_endpoint: str | None = None
    otlp_timeout_seconds: float | None = None


class PlanReplayCacheConfig(_StrictModel):
    enabled: bool | None = None
    cache_path: str | None = None


class ScipCliConfig(_StrictModel):
    enabled: bool | None = None
    index_path: str | None = None
    provider: str | None = None
    generate_fallback: bool | None = None

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in SCIP_PROVIDERS:
            choices = ", ".join(sorted(SCIP_PROVIDERS))
            raise ValueError(
                f"Unsupported scip.provider: {normalized}. Expected one of: {choices}"
            )
        return normalized


class RepomapConfig(_StrictModel):
    enabled: bool | None = None
    top_k: int | None = None
    neighbor_limit: int | None = None
    budget_tokens: int | None = None
    ranking_profile: str | None = None
    signal_weights: dict[str, float] | None = None

    @field_validator("ranking_profile")
    @classmethod
    def _validate_ranking_profile(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in RANKING_PROFILES:
            choices = ", ".join(sorted(RANKING_PROFILES))
            raise ValueError(
                f"Unsupported repomap.ranking_profile: {normalized}. Expected one of: {choices}"
            )
        return normalized


class LspConfig(_StrictModel):
    enabled: bool | None = None
    top_n: int | None = None
    commands: dict[str, Any] | list[Any] | str | None = None
    xref_enabled: bool | None = None
    xref_top_n: int | None = None
    time_budget_ms: int | None = None
    xref_commands: dict[str, Any] | list[Any] | str | None = None


class RetrievalGroupConfig(_StrictModel):
    top_k_files: int | None = None
    min_candidate_score: int | None = None
    candidate_relative_threshold: float | None = None
    deterministic_refine_enabled: bool | None = None
    candidate_ranker: str | None = None
    hybrid_re2_fusion_mode: str | None = None
    hybrid_re2_rrf_k: int | None = None
    hybrid_re2_bm25_weight: float | None = None
    hybrid_re2_heuristic_weight: float | None = None
    hybrid_re2_coverage_weight: float | None = None
    hybrid_re2_combined_scale: float | None = None
    exact_search_enabled: bool | None = None
    exact_search_time_budget_ms: int | None = None
    exact_search_max_paths: int | None = None

    @field_validator("candidate_ranker")
    @classmethod
    def _validate_candidate_ranker(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in CANDIDATE_RANKER_CHOICES:
            choices = ", ".join(CANDIDATE_RANKER_CHOICES)
            raise ValueError(
                f"Unsupported retrieval.candidate_ranker: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("hybrid_re2_fusion_mode")
    @classmethod
    def _validate_hybrid_fusion_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in HYBRID_FUSION_MODES:
            choices = ", ".join(HYBRID_FUSION_MODES)
            raise ValueError(
                "Unsupported retrieval.hybrid_re2_fusion_mode: "
                f"{normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("exact_search_time_budget_ms", "exact_search_max_paths")
    @classmethod
    def _validate_exact_search_int(cls, value: int | None) -> int | None:
        if value is None:
            return value
        resolved = int(value)
        if resolved < 0:
            raise ValueError("retrieval.exact_search_* must be >= 0")
        return resolved


class EmbeddingsConfig(_StrictModel):
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

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in EMBEDDING_PROVIDER_CHOICES:
            choices = ", ".join(EMBEDDING_PROVIDER_CHOICES)
            raise ValueError(
                f"Unsupported embeddings.provider: {normalized}. Expected one of: {choices}"
            )
        return normalized


class TeamSyncConfig(_StrictModel):
    enabled: bool | None = None
    backend: str | None = None
    endpoint: str | None = None
    namespace_scope: str | None = None


class TeamConfig(_StrictModel):
    sync: TeamSyncConfig | None = None


class RuntimeHotReloadConfig(_StrictModel):
    enabled: bool | None = None
    config_file: str | None = None
    poll_interval_seconds: float | None = None
    debounce_ms: int | None = None

    @field_validator("poll_interval_seconds")
    @classmethod
    def _validate_poll_interval_seconds(cls, value: float | None) -> float | None:
        if value is None:
            return value
        resolved = float(value)
        if resolved <= 0:
            raise ValueError("runtime.hot_reload.poll_interval_seconds must be > 0")
        return resolved

    @field_validator("debounce_ms")
    @classmethod
    def _validate_debounce_ms(cls, value: int | None) -> int | None:
        if value is None:
            return value
        resolved = int(value)
        if resolved < 0:
            raise ValueError("runtime.hot_reload.debounce_ms must be >= 0")
        return resolved


class RuntimeHeartbeatConfig(_StrictModel):
    enabled: bool | None = None
    interval_seconds: float | None = None
    run_on_start: bool | None = None

    @field_validator("interval_seconds")
    @classmethod
    def _validate_interval_seconds(cls, value: float | None) -> float | None:
        if value is None:
            return value
        resolved = float(value)
        if resolved <= 0:
            raise ValueError("runtime.scheduler.heartbeat.interval_seconds must be > 0")
        return resolved


class RuntimeCronTaskConfig(_StrictModel):
    name: str
    schedule: str
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("runtime.scheduler.cron[].name cannot be empty")
        return normalized

    @field_validator("schedule")
    @classmethod
    def _validate_schedule(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("runtime.scheduler.cron[].schedule cannot be empty")
        CronSchedule.parse(normalized)
        return normalized


class RuntimeSchedulerConfig(_StrictModel):
    enabled: bool | None = None
    heartbeat: RuntimeHeartbeatConfig | None = None
    cron: list[RuntimeCronTaskConfig] | None = None


class RuntimeConfig(_StrictModel):
    hot_reload: RuntimeHotReloadConfig | None = None
    scheduler: RuntimeSchedulerConfig | None = None


class SharedPlanConfig(_StrictModel):
    runtime_profile: str | None = None
    retrieval_preset: str | None = None
    precomputed_skills_routing_enabled: bool | None = None
    retrieval: RetrievalGroupConfig | None = None
    adaptive_router: AdaptiveRouterConfig | None = None
    adaptive_router_enabled: bool | None = None
    adaptive_router_mode: str | None = None
    adaptive_router_model_path: str | None = None
    adaptive_router_state_path: str | None = None
    adaptive_router_arm_set: str | None = None
    plan_replay_cache_enabled: bool | None = None
    plan_replay_cache_path: str | None = None

    top_k_files: int | None = None
    min_candidate_score: int | None = None
    candidate_relative_threshold: float | None = None
    deterministic_refine_enabled: bool | None = None
    candidate_ranker: str | None = None
    hybrid_re2_fusion_mode: str | None = None
    hybrid_re2_rrf_k: int | None = None
    hybrid_re2_bm25_weight: float | None = None
    hybrid_re2_heuristic_weight: float | None = None
    hybrid_re2_coverage_weight: float | None = None
    hybrid_re2_combined_scale: float | None = None
    exact_search_enabled: bool | None = None
    exact_search_time_budget_ms: int | None = None
    exact_search_max_paths: int | None = None

    languages: list[str] | str | None = None
    index_cache_path: str | None = None
    index_incremental: bool | None = None
    conventions_files: list[str] | str | None = None
    index: IndexCliConfig | None = None

    plugins_enabled: bool | None = None
    remote_slot_policy_mode: str | None = None
    remote_slot_allowlist: list[str] | str | None = None
    plugins: PluginsConfig | None = None

    repomap_enabled: bool | None = None
    repomap_top_k: int | None = None
    repomap_neighbor_limit: int | None = None
    repomap_budget_tokens: int | None = None
    repomap_ranking_profile: str | None = None
    repomap_signal_weights: dict[str, float] | None = None
    repomap: RepomapConfig | None = None

    lsp_enabled: bool | None = None
    lsp_top_n: int | None = None
    lsp_commands: dict[str, Any] | list[Any] | str | None = None
    lsp_xref_enabled: bool | None = None
    lsp_xref_top_n: int | None = None
    lsp_time_budget_ms: int | None = None
    lsp_xref_commands: dict[str, Any] | list[Any] | str | None = None
    lsp: LspConfig | None = None

    validation_enabled: bool | None = None
    validation_include_xref: bool | None = None
    validation_top_n: int | None = None
    validation_xref_top_n: int | None = None
    validation_sandbox_timeout_seconds: float | None = None
    validation: dict[str, Any] | None = None

    memory_disclosure_mode: str | None = None
    memory_preview_max_chars: int | None = None
    memory_strategy: str | None = None
    memory_cache_enabled: bool | None = None
    memory_cache_path: str | None = None
    memory_cache_ttl_seconds: int | None = None
    memory_cache_max_entries: int | None = None
    memory_timeline_enabled: bool | None = None
    memory_hybrid_limit: int | None = None
    memory: MemoryConfig | None = None
    skills: SkillsConfig | None = None

    tokenizer_model: str | None = None
    tokenizer: TokenizerConfig | None = None

    chunk_top_k: int | None = None
    chunk_per_file_limit: int | None = None
    chunk_disclosure: str | None = None
    chunk_signature: bool | None = None
    chunk_snippet_max_lines: int | None = None
    chunk_snippet_max_chars: int | None = None
    chunk_token_budget: int | None = None
    chunk_guard_enabled: bool | None = None
    chunk_guard_mode: str | None = None
    chunk_guard_lambda_penalty: float | None = None
    chunk_guard_min_pool: int | None = None
    chunk_guard_max_pool: int | None = None
    chunk_guard_min_marginal_utility: float | None = None
    chunk_guard_compatibility_min_overlap: float | None = None
    chunk_diversity_enabled: bool | None = None
    chunk_diversity_path_penalty: float | None = None
    chunk_diversity_symbol_family_penalty: float | None = None
    chunk_diversity_kind_penalty: float | None = None
    chunk_diversity_locality_penalty: float | None = None
    chunk_diversity_locality_window: int | None = None
    chunk: ChunkConfig | None = None

    cochange_enabled: bool | None = None
    cochange_cache_path: str | None = None
    cochange_lookback_commits: int | None = None
    cochange_half_life_days: float | None = None
    cochange_top_neighbors: int | None = None
    cochange_boost_weight: float | None = None
    cochange: CochangeCliConfig | None = None

    embedding_enabled: bool | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    embedding_index_path: str | None = None
    embedding_rerank_pool: int | None = None
    embedding_lexical_weight: float | None = None
    embedding_semantic_weight: float | None = None
    embedding_min_similarity: float | None = None
    embedding_fail_open: bool | None = None
    embeddings: EmbeddingsConfig | None = None

    retrieval_policy: str | None = None
    policy_version: str | None = None

    failed_test_report: str | None = None
    junit_xml: str | None = None
    coverage_json: str | None = None
    sbfl_json: str | None = None
    sbfl_metric: str | None = None
    sbfl: SbflConfig | None = None
    tests: TestsCliConfig | None = None

    scip_enabled: bool | None = None
    scip_index_path: str | None = None
    scip_provider: str | None = None
    scip_generate_fallback: bool | None = None
    scip: ScipCliConfig | None = None

    trace_export_enabled: bool | None = None
    trace_export_path: str | None = None
    trace_otlp_enabled: bool | None = None
    trace_otlp_endpoint: str | None = None
    trace_otlp_timeout_seconds: float | None = None
    trace: TraceConfig | None = None
    plan_replay_cache: PlanReplayCacheConfig | None = None

    @field_validator("candidate_ranker")
    @classmethod
    def _validate_candidate_ranker(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in CANDIDATE_RANKER_CHOICES:
            choices = ", ".join(CANDIDATE_RANKER_CHOICES)
            raise ValueError(
                f"Unsupported candidate_ranker: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("runtime_profile")
    @classmethod
    def _normalize_runtime_profile(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        return normalized or None

    @field_validator("hybrid_re2_fusion_mode")
    @classmethod
    def _validate_hybrid_fusion_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in HYBRID_FUSION_MODES:
            choices = ", ".join(HYBRID_FUSION_MODES)
            raise ValueError(
                f"Unsupported hybrid_re2_fusion_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("exact_search_time_budget_ms", "exact_search_max_paths")
    @classmethod
    def _validate_exact_search_int(cls, value: int | None) -> int | None:
        if value is None:
            return value
        resolved = int(value)
        if resolved < 0:
            raise ValueError("exact_search_* must be >= 0")
        return resolved

    @field_validator("remote_slot_policy_mode", mode="before")
    @classmethod
    def _coerce_remote_slot_policy_mode(cls, value: Any) -> Any:
        if isinstance(value, bool):
            return "strict" if value else "off"
        return value

    @field_validator("remote_slot_policy_mode")
    @classmethod
    def _validate_remote_slot_policy_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in REMOTE_SLOT_POLICY_CHOICES:
            choices = ", ".join(REMOTE_SLOT_POLICY_CHOICES)
            raise ValueError(
                f"Unsupported remote_slot_policy_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("repomap_ranking_profile")
    @classmethod
    def _validate_repomap_ranking_profile(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in RANKING_PROFILES:
            choices = ", ".join(sorted(RANKING_PROFILES))
            raise ValueError(
                f"Unsupported repomap_ranking_profile: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("memory_disclosure_mode")
    @classmethod
    def _validate_memory_disclosure_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_DISCLOSURE_MODES:
            choices = ", ".join(MEMORY_DISCLOSURE_MODES)
            raise ValueError(
                f"Unsupported memory_disclosure_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("memory_strategy")
    @classmethod
    def _validate_memory_strategy(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in MEMORY_STRATEGIES:
            choices = ", ".join(MEMORY_STRATEGIES)
            raise ValueError(
                f"Unsupported memory_strategy: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("chunk_disclosure")
    @classmethod
    def _validate_chunk_disclosure(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in CHUNK_DISCLOSURE_CHOICES:
            choices = ", ".join(CHUNK_DISCLOSURE_CHOICES)
            raise ValueError(
                f"Unsupported chunk_disclosure: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("chunk_guard_mode")
    @classmethod
    def _validate_chunk_guard_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in CHUNK_GUARD_MODE_CHOICES:
            choices = ", ".join(CHUNK_GUARD_MODE_CHOICES)
            raise ValueError(
                f"Unsupported chunk_guard_mode: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("retrieval_policy")
    @classmethod
    def _validate_retrieval_policy(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in RETRIEVAL_POLICY_CHOICES:
            choices = ", ".join(RETRIEVAL_POLICY_CHOICES)
            raise ValueError(
                f"Unsupported retrieval_policy: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("adaptive_router_mode")
    @classmethod
    def _validate_adaptive_router_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in ADAPTIVE_ROUTER_MODE_CHOICES:
            choices = ", ".join(ADAPTIVE_ROUTER_MODE_CHOICES)
            raise ValueError(
                "Unsupported adaptive_router_mode: "
                f"{normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("sbfl_metric")
    @classmethod
    def _validate_sbfl_metric(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in SBFL_METRIC_CHOICES:
            choices = ", ".join(SBFL_METRIC_CHOICES)
            raise ValueError(f"Unsupported sbfl_metric: {normalized}. Expected one of: {choices}")
        return normalized

    @field_validator("scip_provider")
    @classmethod
    def _validate_scip_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in SCIP_PROVIDERS:
            choices = ", ".join(sorted(SCIP_PROVIDERS))
            raise ValueError(
                f"Unsupported scip_provider: {normalized}. Expected one of: {choices}"
            )
        return normalized

    @field_validator("embedding_provider")
    @classmethod
    def _validate_embedding_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in EMBEDDING_PROVIDER_CHOICES:
            choices = ", ".join(EMBEDDING_PROVIDER_CHOICES)
            raise ValueError(
                f"Unsupported embedding_provider: {normalized}. Expected one of: {choices}"
            )
        return normalized


class BenchmarkThresholdsConfig(_StrictModel):
    precision_tolerance: float | None = None
    noise_tolerance: float | None = None
    latency_growth_factor: float | None = None
    dependency_recall_floor: float | None = None
    chunk_hit_tolerance: float | None = None
    chunk_budget_growth_factor: float | None = None
    validation_test_growth_factor: float | None = None
    embedding_similarity_tolerance: float | None = None
    embedding_rerank_ratio_tolerance: float | None = None
    embedding_cache_hit_tolerance: float | None = None
    embedding_fallback_tolerance: float | None = None


class RewardLogConfig(_StrictModel):
    enabled: bool | None = None
    path: str | None = None


class BenchmarkConfig(SharedPlanConfig):
    threshold_profile: str | None = None
    thresholds: BenchmarkThresholdsConfig | None = None
    warmup_runs: int | None = None
    include_plans: bool | None = None
    include_case_details: bool | None = None
    reward_log: RewardLogConfig | None = None
    reward_log_enabled: bool | None = None
    reward_log_path: str | None = None


class RepoMapConfig(_StrictModel):
    languages: list[str] | str | None = None
    output_json: str | None = None
    output_md: str | None = None
    budget_tokens: int | None = None
    top_k: int | None = None
    ranking_profile: str | None = None

    @field_validator("ranking_profile")
    @classmethod
    def _validate_ranking_profile(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in RANKING_PROFILES:
            choices = ", ".join(sorted(RANKING_PROFILES))
            raise ValueError(
                f"Unsupported repomap.ranking_profile: {normalized}. Expected one of: {choices}"
            )
        return normalized


class AceLiteConfig(SharedPlanConfig):
    plan: SharedPlanConfig | None = None
    benchmark: BenchmarkConfig | None = None
    repomap: RepoMapConfig | None = None
    team: TeamConfig | None = None
    runtime: RuntimeConfig | None = None


def validate_cli_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate merged config data for CLI usage.

    Returns a normalized dictionary (unknown keys rejected). Raises ``ValueError``
    with a human-friendly summary for CLI consumption.
    """

    try:
        model = AceLiteConfig.model_validate(config)
    except ValidationError as exc:
        lines = ["Invalid .ace-lite.yml configuration:"]
        for error in exc.errors():
            location = ".".join(str(item) for item in error.get("loc", ()))
            message = str(error.get("msg", "Invalid value"))
            lines.append(f"- {location}: {message}")
        raise ValueError("\n".join(lines)) from exc

    return cast(dict[str, Any], model.model_dump(exclude_none=True, by_alias=True))


__all__ = [
    "AceLiteConfig",
    "BenchmarkConfig",
    "RepoMapConfig",
    "RuntimeConfig",
    "SharedPlanConfig",
    "TeamConfig",
    "TeamSyncConfig",
    "validate_cli_config",
]
