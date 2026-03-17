"""Pydantic models for validating layered ``.ace-lite.yml`` configuration.

The core config loader returns a raw merged dictionary. These models provide a
strict, type-checked validation layer for CLI usage (unknown keys are rejected)
while keeping the underlying loader lightweight.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import Field, ValidationError, field_validator

from ace_lite.config_choices import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    MEMORY_TIMEZONE_MODE_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
)
from ace_lite.config_sections import (
    ChunkCoreSectionSpec,
    ChunkGuardSectionSpec,
    ChunkTopologicalShieldSectionSpec,
    EmbeddingsSectionSpec,
    MemoryCaptureSectionSpec,
    MemoryCoreSectionSpec,
    MemoryFeedbackSectionSpec,
    MemoryGateSectionSpec,
    MemoryNamespaceSectionSpec,
    MemoryNotesSectionSpec,
    MemoryPostprocessSectionSpec,
    MemoryProfileSectionSpec,
    MemoryTemporalSectionSpec,
    PlanReplayCacheSectionSpec,
    PluginsSectionSpec,
    RepomapSectionSpec,
    ScipSectionSpec,
    TestSignalsSectionSpec,
    TokenizerSectionSpec,
    TraceSectionSpec,
)
from ace_lite.config_model_shared import (
    validate_adaptive_router_mode,
    validate_candidate_ranker,
    validate_chunk_guard_mode,
    validate_chunk_disclosure,
    validate_hybrid_fusion_mode,
    validate_memory_disclosure_mode,
    validate_memory_strategy,
    validate_memory_timezone_mode,
    validate_remote_slot_policy_mode,
    validate_retrieval_policy,
    validate_sbfl_metric,
    validate_topological_shield_mode,
)
from ace_lite.config_value_normalizers import validate_choice_value
from ace_lite.pydantic_utils import StrictModel as _StrictModel
from ace_lite.runtime.scheduler import CronSchedule
from ace_lite.shared_plan_runtime_config import (
    normalize_container_tag,
    resolve_embedding_index_path,
    resolve_embedding_model,
    resolve_embedding_provider,
    resolve_memory_auto_tag_mode,
    resolve_memory_gate_mode,
    resolve_memory_notes_mode,
    resolve_optional_path,
    resolve_plan_replay_cache_path,
    resolve_ranking_profile,
    resolve_scip_index_path,
    resolve_scip_provider,
    resolve_tokenizer_model,
    resolve_trace_export_path,
    resolve_trace_otlp_endpoint,
    resolve_trace_otlp_timeout_seconds,
)

class TokenizerConfig(TokenizerSectionSpec):

    @field_validator("model", mode="before")
    @classmethod
    def _normalize_model(cls, value: Any) -> str:
        return resolve_tokenizer_model(value)


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
        return validate_adaptive_router_mode(
            value,
            field_name="adaptive_router.mode",
        )


class MemoryNamespaceConfig(MemoryNamespaceSectionSpec):

    @field_validator("container_tag", mode="before")
    @classmethod
    def _normalize_container_tag(cls, value: Any) -> str | None:
        return normalize_container_tag(value)

    @field_validator("auto_tag_mode", mode="before")
    @classmethod
    def _validate_auto_tag_mode(cls, value: Any) -> str | None:
        return resolve_memory_auto_tag_mode(
            value,
            field_name="memory.namespace.auto_tag_mode",
        )


class MemoryProfileConfig(MemoryProfileSectionSpec):
    pass


class MemoryTemporalConfig(MemoryTemporalSectionSpec):

    @field_validator("timezone_mode")
    @classmethod
    def _validate_timezone_mode(cls, value: str | None) -> str | None:
        return validate_memory_timezone_mode(
            value,
            field_name="memory.temporal.timezone_mode",
        )


class MemoryFeedbackConfig(MemoryFeedbackSectionSpec):
    pass


class MemoryCaptureConfig(MemoryCaptureSectionSpec):
    keywords: list[str] | None = None


class MemoryNotesConfig(MemoryNotesSectionSpec):
    @field_validator("mode", mode="before")
    @classmethod
    def _validate_mode(cls, value: Any) -> str | None:
        return resolve_memory_notes_mode(
            value,
            field_name="memory.notes.mode",
        )


class MemoryGateConfig(MemoryGateSectionSpec):

    @field_validator("mode", mode="before")
    @classmethod
    def _validate_mode(cls, value: Any) -> str | None:
        return resolve_memory_gate_mode(
            value,
            field_name="memory.gate.mode",
        )


class MemoryPostprocessConfig(MemoryPostprocessSectionSpec):
    pass


class MemoryConfig(MemoryCoreSectionSpec):
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
        return validate_memory_disclosure_mode(
            value,
            field_name="memory.disclosure_mode",
        )

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, value: str | None) -> str | None:
        return validate_memory_strategy(
            value,
            field_name="memory.strategy",
        )


class ChunkSnippetConfig(_StrictModel):
    max_lines: int | None = None
    max_chars: int | None = None


class ChunkGuardConfig(ChunkGuardSectionSpec):

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        return validate_chunk_guard_mode(
            value,
            field_name="chunk.guard.mode",
        )


class ChunkTopologicalShieldConfig(ChunkTopologicalShieldSectionSpec):

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        return validate_topological_shield_mode(
            value,
            field_name="chunk.topological_shield.mode",
        )


class ChunkConfig(ChunkCoreSectionSpec):
    snippet: ChunkSnippetConfig | None = None
    topological_shield: ChunkTopologicalShieldConfig | None = None
    guard: ChunkGuardConfig | None = None

    @field_validator("disclosure")
    @classmethod
    def _validate_disclosure(cls, value: str | None) -> str | None:
        return validate_chunk_disclosure(value, field_name="chunk.disclosure")


class SkillsConfig(_StrictModel):
    precomputed_routing_enabled: bool | None = None


class PluginsConfig(PluginsSectionSpec):
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
        return validate_remote_slot_policy_mode(
            value,
            field_name="plugins.remote_slot_policy_mode",
        )


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
        return validate_sbfl_metric(value, field_name="sbfl.metric")


class TestsCliConfig(TestSignalsSectionSpec):
    sbfl: SbflConfig | None = None

    @field_validator("junit_xml", "coverage_json", "sbfl_json", mode="before")
    @classmethod
    def _normalize_optional_path(cls, value: Any) -> str | None:
        return resolve_optional_path(value)

    @field_validator("sbfl_metric")
    @classmethod
    def _validate_sbfl_metric(cls, value: str | None) -> str | None:
        return validate_sbfl_metric(value, field_name="tests.sbfl_metric")


class TraceConfig(TraceSectionSpec):

    @field_validator("otlp_endpoint", mode="before")
    @classmethod
    def _normalize_otlp_endpoint(cls, value: Any) -> str:
        return resolve_trace_otlp_endpoint(value)

    @field_validator("export_path", mode="before")
    @classmethod
    def _normalize_export_path(cls, value: Any) -> str:
        return resolve_trace_export_path(value)

    @field_validator("otlp_timeout_seconds", mode="before")
    @classmethod
    def _normalize_otlp_timeout_seconds(cls, value: Any) -> float:
        return resolve_trace_otlp_timeout_seconds(value)


class PlanReplayCacheConfig(PlanReplayCacheSectionSpec):

    @field_validator("cache_path", mode="before")
    @classmethod
    def _normalize_cache_path(cls, value: Any) -> str:
        return resolve_plan_replay_cache_path(value)


class ScipCliConfig(ScipSectionSpec):

    @field_validator("index_path", mode="before")
    @classmethod
    def _normalize_index_path(cls, value: Any) -> str:
        return resolve_scip_index_path(value)

    @field_validator("provider", mode="before")
    @classmethod
    def _validate_provider(cls, value: Any) -> str | None:
        return resolve_scip_provider(value, field_name="scip.provider")


class RepomapConfig(RepomapSectionSpec):

    @field_validator("ranking_profile", mode="before")
    @classmethod
    def _validate_ranking_profile(cls, value: Any) -> str | None:
        return resolve_ranking_profile(
            value,
            field_name="repomap.ranking_profile",
        )


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
        return validate_candidate_ranker(
            value,
            field_name="retrieval.candidate_ranker",
        )

    @field_validator("hybrid_re2_fusion_mode")
    @classmethod
    def _validate_hybrid_fusion_mode(cls, value: str | None) -> str | None:
        return validate_hybrid_fusion_mode(
            value,
            field_name="retrieval.hybrid_re2_fusion_mode",
        )

    @field_validator("exact_search_time_budget_ms", "exact_search_max_paths")
    @classmethod
    def _validate_exact_search_int(cls, value: int | None) -> int | None:
        if value is None:
            return value
        resolved = int(value)
        if resolved < 0:
            raise ValueError("retrieval.exact_search_* must be >= 0")
        return resolved


class EmbeddingsConfig(EmbeddingsSectionSpec):

    @field_validator("provider", mode="before")
    @classmethod
    def _validate_provider(cls, value: Any) -> str | None:
        return resolve_embedding_provider(
            value,
            field_name="embeddings.provider",
        )

    @field_validator("model", mode="before")
    @classmethod
    def _normalize_model(cls, value: Any) -> str:
        return resolve_embedding_model(value)

    @field_validator("index_path", mode="before")
    @classmethod
    def _normalize_index_path(cls, value: Any) -> str:
        return resolve_embedding_index_path(value)


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

    agent_loop_enabled: bool | None = None
    agent_loop_max_iterations: int | None = None
    agent_loop_max_focus_paths: int | None = None
    agent_loop_query_hint_max_chars: int | None = None
    agent_loop: dict[str, Any] | None = None

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
        return validate_candidate_ranker(value, field_name="candidate_ranker")

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
        return validate_hybrid_fusion_mode(
            value,
            field_name="hybrid_re2_fusion_mode",
        )

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
        return validate_remote_slot_policy_mode(
            value,
            field_name="remote_slot_policy_mode",
        )

    @field_validator("repomap_ranking_profile", mode="before")
    @classmethod
    def _validate_repomap_ranking_profile(cls, value: Any) -> str | None:
        return resolve_ranking_profile(
            value,
            field_name="repomap_ranking_profile",
        )

    @field_validator("memory_disclosure_mode")
    @classmethod
    def _validate_memory_disclosure_mode(cls, value: str | None) -> str | None:
        return validate_memory_disclosure_mode(
            value,
            field_name="memory_disclosure_mode",
        )

    @field_validator("memory_strategy")
    @classmethod
    def _validate_memory_strategy(cls, value: str | None) -> str | None:
        return validate_memory_strategy(value, field_name="memory_strategy")

    @field_validator("chunk_disclosure")
    @classmethod
    def _validate_chunk_disclosure(cls, value: str | None) -> str | None:
        return validate_chunk_disclosure(value, field_name="chunk_disclosure")

    @field_validator("chunk_guard_mode")
    @classmethod
    def _validate_chunk_guard_mode(cls, value: str | None) -> str | None:
        return validate_chunk_guard_mode(
            value,
            field_name="chunk_guard_mode",
        )

    @field_validator("retrieval_policy")
    @classmethod
    def _validate_retrieval_policy(cls, value: str | None) -> str | None:
        return validate_retrieval_policy(
            value,
            field_name="retrieval_policy",
        )

    @field_validator("adaptive_router_mode")
    @classmethod
    def _validate_adaptive_router_mode(cls, value: str | None) -> str | None:
        return validate_adaptive_router_mode(
            value,
            field_name="adaptive_router_mode",
        )

    @field_validator("sbfl_metric")
    @classmethod
    def _validate_sbfl_metric(cls, value: str | None) -> str | None:
        return validate_sbfl_metric(value, field_name="sbfl_metric")

    @field_validator("scip_provider", mode="before")
    @classmethod
    def _validate_scip_provider(cls, value: Any) -> str | None:
        return resolve_scip_provider(value, field_name="scip_provider")

    @field_validator("scip_index_path", mode="before")
    @classmethod
    def _normalize_scip_index_path(cls, value: Any) -> str:
        return resolve_scip_index_path(value)

    @field_validator("embedding_provider", mode="before")
    @classmethod
    def _validate_embedding_provider(cls, value: Any) -> str | None:
        return resolve_embedding_provider(value, field_name="embedding_provider")

    @field_validator("embedding_model", mode="before")
    @classmethod
    def _normalize_embedding_model(cls, value: Any) -> str:
        return resolve_embedding_model(value)

    @field_validator("embedding_index_path", mode="before")
    @classmethod
    def _normalize_embedding_index_path(cls, value: Any) -> str:
        return resolve_embedding_index_path(value)

    @field_validator("tokenizer_model", mode="before")
    @classmethod
    def _normalize_tokenizer_model(cls, value: Any) -> str:
        return resolve_tokenizer_model(value)

    @field_validator("trace_export_path", mode="before")
    @classmethod
    def _normalize_trace_export_path(cls, value: Any) -> str:
        return resolve_trace_export_path(value)

    @field_validator("trace_otlp_endpoint", mode="before")
    @classmethod
    def _normalize_trace_otlp_endpoint(cls, value: Any) -> str:
        return resolve_trace_otlp_endpoint(value)

    @field_validator("trace_otlp_timeout_seconds", mode="before")
    @classmethod
    def _normalize_trace_otlp_timeout_seconds(cls, value: Any) -> float:
        return resolve_trace_otlp_timeout_seconds(value)

    @field_validator("plan_replay_cache_path", mode="before")
    @classmethod
    def _normalize_plan_replay_cache_path(cls, value: Any) -> str:
        return resolve_plan_replay_cache_path(value)

    @field_validator("junit_xml", "coverage_json", "sbfl_json", mode="before")
    @classmethod
    def _normalize_test_output_paths(cls, value: Any) -> str | None:
        return resolve_optional_path(value)


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

    @field_validator("ranking_profile", mode="before")
    @classmethod
    def _validate_ranking_profile(cls, value: Any) -> str | None:
        return resolve_ranking_profile(
            value,
            field_name="repomap.ranking_profile",
        )


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
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "AceLiteConfig",
    "BenchmarkConfig",
    "CHUNK_GUARD_MODE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_TIMEZONE_MODE_CHOICES",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RepoMapConfig",
    "RETRIEVAL_POLICY_CHOICES",
    "RuntimeConfig",
    "SharedPlanConfig",
    "TeamConfig",
    "TeamSyncConfig",
    "validate_cli_config",
]
