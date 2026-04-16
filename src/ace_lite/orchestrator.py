from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.memory import (
    MemoryProvider,
)
from ace_lite.memory_long_term import LongTermMemoryCaptureService, LongTermMemoryStore
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.orchestrator_contracts import (
    PlanRequestAdapter,
    PlanResponseAdapter,
    build_plan_request_payload,
    validate_plan_request,
)
from ace_lite.orchestrator_memory_context_service import (
    MemoryContextService,
)
from ace_lite.orchestrator_memory_support import (
    build_orchestrator_memory_runtime,
)
from ace_lite.orchestrator_payload_builder import (
    build_default_validation_payload,
    build_orchestrator_plan_payload,
)
from ace_lite.orchestrator_plugin_support import (
    load_orchestrator_plugins,
)
from ace_lite.orchestrator_runtime_observability_service import (
    RuntimeObservabilityService,
)
from ace_lite.orchestrator_runtime_support import (
    run_orchestrator_finalization,
    run_orchestrator_lifecycle,
    run_orchestrator_preparation,
)
from ace_lite.orchestrator_source_plan_replay_service import (
    SourcePlanReplayService,
)
from ace_lite.orchestrator_source_plan_support import (
    build_orchestrator_source_plan_runtime,
)
from ace_lite.orchestrator_stage_runtime_support import (
    precompute_orchestrator_skills_route,
    run_orchestrator_augment_stage,
    run_orchestrator_index_stage,
    run_orchestrator_repomap_stage,
    run_orchestrator_skills_stage,
    run_orchestrator_validation_stage,
)
from ace_lite.orchestrator_stage_state import apply_post_stage_state_updates
from ace_lite.orchestrator_type_support import (
    _typed_dict,
    _typed_int,
    _typed_list_str,
    _typed_namespace_result,
    _typed_optional_dict,
    _typed_optional_preference_capture_store,
    _typed_path,
    _typed_plugin_load_result,
    _typed_profile_store,
    _typed_replay_load_result,
    _typed_str,
)
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import (
    CORE_PIPELINE_ORDER,
    StageRegistry,
    iter_stage_descriptors,
)
from ace_lite.pipeline.stage_tags import build_stage_tags
from ace_lite.pipeline.stages.context_refine import run_context_refine
from ace_lite.pipeline.stages.history_channel import run_history_channel
from ace_lite.pipeline.stages.memory import run_memory
from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.types import StageContext, StageMetric
from ace_lite.plugins.loader import PluginLoader
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
from ace_lite.profile_store import ProfileStore
from ace_lite.runtime_manager import RuntimeManager
from ace_lite.runtime_state import RuntimeState
from ace_lite.scoring_config import (
    BM25_B,
    BM25_K1,
    CHUNK_FILE_PRIOR_WEIGHT,
    CHUNK_PATH_MATCH,
    CHUNK_SYMBOL_EXACT,
    HEUR_PATH_EXACT,
    HEUR_SYMBOL_EXACT,
    HYBRID_BM25_WEIGHT,
    HYBRID_HEURISTIC_WEIGHT,
    HYBRID_RRF_K_DEFAULT,
)
from ace_lite.token_estimator import (
    estimate_tokens,
)

logger = logging.getLogger(__name__)


class AceOrchestrator:
    PIPELINE_ORDER = CORE_PIPELINE_ORDER
    CANDIDATE_RANKERS = ("heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid")
    REMOTE_SLOT_ALLOWLIST = ("observability.mcp_plugins",)
    PLAN_REPLAY_STAGE = "source_plan"
    PLAN_REPLAY_MODE = "late_exact_source_plan"
    PLAN_REPLAY_GUARDED_BY = (
        "normalized_query",
        "repo_root_fingerprint",
        "temporal_input",
        "plugins_loaded",
        "conventions_hashes",
        "memory_fingerprint",
        "index_fingerprint",
        "index_hash",
        "worktree_state_hash",
        "retrieval_policy",
        "policy_version",
        "candidate_ranker",
        "budget_knobs",
        "upstream_fingerprints",
        "content_version",
    )
    _COCHANGE_NEIGHBOR_CAP = 64
    _COCHANGE_MIN_NEIGHBOR_SCORE = 0.15
    _COCHANGE_MAX_BOOST = 0.8

    def __init__(
        self,
        *,
        memory_provider: MemoryProvider | None = None,
        config: OrchestratorConfig | None = None,
        plugin_loader: PluginLoader | None = None,
        durable_stats_store_factory: Callable[[], Any] | None = None,
        runtime_state: RuntimeState | None = None,
        runtime_manager: RuntimeManager | None = None,
    ) -> None:
        self._runtime_manager = runtime_manager
        if runtime_state is None:
            if self._runtime_manager is None:
                self._runtime_manager = RuntimeManager(
                    config=config,
                    memory_provider=memory_provider,
                    plugin_loader=plugin_loader,
                    durable_stats_store_factory=durable_stats_store_factory,
                )
            runtime_state = self._runtime_manager.startup()

        self._runtime_state = runtime_state
        self._config = runtime_state.config
        self._memory_provider = runtime_state.services.memory_provider
        self._durable_stats_store_factory = runtime_state.services.durable_stats_store_factory
        self._durable_stats_session_id = runtime_state.durable_stats_session_id
        self._conventions_files = (
            list(runtime_state.conventions_files) if runtime_state.conventions_files else None
        )
        self._conventions_hashes = runtime_state.conventions_hashes
        self._plugin_loader = runtime_state.services.plugin_loader
        self._plugin_runtime = runtime_state.services.plugin_runtime
        self._lsp_broker = runtime_state.services.lsp_broker
        self._tokenizer_model = self._config.tokenizer.model
        self._signal_extractor = runtime_state.services.signal_extractor
        self._skill_manifest = runtime_state.services.skill_manifest
        self._source_plan_replay_service = SourcePlanReplayService(
            config=self._config,
            plan_replay_stage=self.PLAN_REPLAY_STAGE,
            plan_replay_mode=self.PLAN_REPLAY_MODE,
            plan_replay_guarded_by=self.PLAN_REPLAY_GUARDED_BY,
            resolve_repo_relative_path_fn=self._resolve_repo_relative_path,
        )
        self._runtime_observability_service = RuntimeObservabilityService(
            config=self._config,
            pipeline_order=tuple(self.PIPELINE_ORDER),
            resolve_repo_relative_path_fn=self._resolve_repo_relative_path,
            durable_stats_store_factory=self._durable_stats_store_factory,
            durable_stats_session_id=self._durable_stats_session_id,
        )
        self._long_term_capture_service = (
            LongTermMemoryCaptureService(
                store=LongTermMemoryStore(db_path=self._config.memory.long_term.path),
                enabled=(
                    bool(self._config.memory.long_term.enabled)
                    and bool(self._config.memory.long_term.write_enabled)
                ),
            )
            if (
                bool(self._config.memory.long_term.enabled)
                and bool(self._config.memory.long_term.write_enabled)
            )
            else None
        )
        self._memory_context_service = MemoryContextService(
            config=self._config,
            long_term_capture_service=self._long_term_capture_service,
            durable_stats_session_id=self._durable_stats_session_id,
        )
        self._last_learning_router_rollout_decision: dict[str, Any] = {}

    @property
    def config(self) -> OrchestratorConfig:
        return self._config

    def shutdown(self) -> dict[str, Any]:
        if self._runtime_manager is None:
            return {
                "started": False,
                "shutdown": False,
                "executed_count": 0,
                "errors": [],
                "results": [],
            }
        return _typed_dict(self._runtime_manager.shutdown())

    def plan(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_payload = build_plan_request_payload(
            query=query,
            repo=repo,
            root=root,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
        )
        validated_request_payload = validate_plan_request(_typed_dict(request_payload))
        request = PlanRequestAdapter(_typed_dict(validated_request_payload))
        query = request.query
        repo = request.repo
        root = request.root
        time_range = request.time_range
        start_date = request.start_date
        end_date = request.end_date
        filters = request.filters
        self._last_learning_router_rollout_decision = {}
        preparation = run_orchestrator_preparation(
            orchestrator=self,
            query=query,
            repo=repo,
            root=root,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
        )
        root_path = preparation.root_path
        conventions = preparation.conventions
        hook_bus = preparation.hook_bus
        plugins_loaded = preparation.plugins_loaded
        registry = preparation.registry
        temporal_input = preparation.temporal_input
        ctx = preparation.ctx

        started = perf_counter()
        started_at = datetime.now(timezone.utc)
        lifecycle_result = run_orchestrator_lifecycle(
            orchestrator=self,
            query=query,
            repo=repo,
            root_path=root_path,
            temporal_input=temporal_input,
            plugins_loaded=plugins_loaded,
            ctx=ctx,
            registry=registry,
            hook_bus=hook_bus,
        )
        stage_metrics = lifecycle_result.stage_metrics
        contract_error = lifecycle_result.contract_error
        replay_cache_info = lifecycle_result.replay_cache_info

        total_ms = (perf_counter() - started) * 1000.0

        finalization_result = run_orchestrator_finalization(
            orchestrator=self,
            query=query,
            repo=repo,
            root_path=root_path,
            conventions=conventions,
            ctx=ctx,
            stage_metrics=stage_metrics,
            plugins_loaded=plugins_loaded,
            started_at=started_at,
            total_ms=total_ms,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
        )
        return _typed_dict(finalization_result.payload)

    def _build_registry(self) -> StageRegistry:
        registry = StageRegistry()
        stage_handlers = {
            "memory": lambda ctx: self._run_memory(ctx=ctx),
            "index": lambda ctx: self._run_index(ctx=ctx),
            "repomap": lambda ctx: self._run_repomap(ctx=ctx),
            "augment": lambda ctx: self._run_augment(ctx=ctx),
            "skills": lambda ctx: self._run_skills(ctx=ctx),
            "history_channel": lambda ctx: self._run_history_channel(ctx=ctx),
            "context_refine": lambda ctx: self._run_context_refine(ctx=ctx),
            "source_plan": lambda ctx: self._run_source_plan(ctx=ctx),
            "validation": lambda ctx: self._run_validation(ctx=ctx),
        }
        for descriptor in iter_stage_descriptors():
            registry.register_descriptor(descriptor.with_handler(stage_handlers[descriptor.name]))
        return registry

    def _execute_stage(
        self,
        *,
        stage_name: str,
        repo: str,
        ctx: StageContext,
        registry: StageRegistry,
        hook_bus: HookBus,
        stage_metrics: list[StageMetric],
    ) -> StageContractError | None:
        logger.debug("stage.start", extra={"stage": stage_name, "repo": repo})
        try:
            stage_payload = self._plugin_runtime.execute_stage(
                stage_name=stage_name,
                registry=registry,
                hook_bus=hook_bus,
                ctx=ctx,
                stage_metrics=stage_metrics,
                tag_builder=build_stage_tags,
            )
        except StageContractError as exc:
            logger.error(
                "stage.contract.error",
                extra={
                    "stage": stage_name,
                    "error_code": exc.error_code,
                    "reason": exc.reason,
                },
            )
            return exc

        self._store_stage_state(
            stage_name=stage_name,
            ctx=ctx,
            stage_payload=stage_payload,
        )
        logger.debug("stage.end", extra={"stage": stage_name, "repo": repo})
        return None

    @staticmethod
    def _context_state(*, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(ctx.state)

    @classmethod
    def _get_stage_state(cls, *, ctx: StageContext, stage_name: str) -> dict[str, Any]:
        value = cls._context_state(ctx=ctx).get(stage_name)
        return dict(value) if isinstance(value, dict) else {}

    def _store_stage_state(
        self,
        *,
        stage_name: str,
        ctx: StageContext,
        stage_payload: dict[str, Any],
    ) -> None:
        ctx_state = self._context_state(ctx=ctx)
        ctx_state[stage_name] = stage_payload
        capture_payload = self._capture_long_term_stage_observation(
            stage_name=stage_name,
            ctx=ctx,
            stage_payload=stage_payload,
        )
        apply_post_stage_state_updates(
            stage_name=stage_name,
            ctx_state=ctx_state,
            stage_payload=stage_payload,
            precomputed_routing_enabled=bool(self._config.skills.precomputed_routing_enabled),
            precompute_skills_route_fn=lambda: self._precompute_skills_route(ctx=ctx),
            capture_payload=capture_payload,
        )

    def _build_plan_payload(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        conventions: dict[str, Any],
        ctx: StageContext,
        stage_metrics: list[StageMetric],
        plugins_loaded: list[str],
        total_ms: float,
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = build_orchestrator_plan_payload(
            query=query,
            repo=repo,
            root=root,
            conventions=conventions,
            ctx=ctx,
            stage_metrics=stage_metrics,
            plugins_loaded=plugins_loaded,
            total_ms=total_ms,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
            pipeline_order=self.PIPELINE_ORDER,
            policy_version=str(self._config.retrieval.policy_version),
            build_plugin_policy_summary_fn=self._plugin_runtime.build_policy_summary,
            extract_source_plan_failure_signal_summary_fn=(
                self._extract_source_plan_failure_signal_summary
            ),
            extract_source_plan_validation_feedback_summary_fn=(
                self._extract_source_plan_validation_feedback_summary
            ),
        )
        payload_view = PlanResponseAdapter(payload)
        self._last_learning_router_rollout_decision = dict(
            payload_view.learning_router_rollout_decision
        )
        return _typed_dict(payload)

    def _default_validation_payload(self) -> dict[str, Any]:
        return _typed_dict(
            build_default_validation_payload(
                policy_version=str(self._config.retrieval.policy_version)
            )
        )

    def _extract_source_plan_validation_feedback_summary(
        self,
        source_plan_stage: Any,
    ) -> dict[str, Any]:
        return _typed_dict(
            self._source_plan_replay_service.extract_source_plan_validation_feedback_summary(
                source_plan_stage
            )
        )

    def _capture_long_term_stage_observation(
        self,
        *,
        stage_name: str,
        ctx: StageContext,
        stage_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        return _typed_optional_dict(
            self._memory_context_service.capture_long_term_stage_observation(
                stage_name=stage_name,
                ctx=ctx,
                stage_payload=stage_payload,
            )
        )

    def _resolve_plan_replay_cache_path(self, *, root: str) -> Path:
        return _typed_path(
            self._source_plan_replay_service.resolve_plan_replay_cache_path(root=root)
        )

    def _extract_source_plan_failure_signal_summary(
        self,
        source_plan_stage: Any,
    ) -> dict[str, Any]:
        return _typed_dict(
            self._source_plan_replay_service.extract_source_plan_failure_signal_summary(
                source_plan_stage
            )
        )

    def _default_plan_replay_cache_info(self, *, root: str) -> dict[str, Any]:
        return _typed_dict(
            self._source_plan_replay_service.default_plan_replay_cache_info(root=root)
        )

    def _load_replayed_source_plan(
        self,
        *,
        root: str,
        replay_cache_path: Path,
        replay_cache_key: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        return _typed_replay_load_result(
            self._source_plan_replay_service.load_replayed_source_plan(
                root=root,
                replay_cache_path=replay_cache_path,
                replay_cache_key=replay_cache_key,
            )
        )

    def _store_source_plan_replay(
        self,
        *,
        query: str,
        repo: str,
        replay_cache_path: Path,
        replay_cache_key: str,
        source_plan_stage: Any,
        replay_cache_info: dict[str, Any],
    ) -> dict[str, Any]:
        return _typed_dict(
            self._source_plan_replay_service.store_source_plan_replay(
                query=query,
                repo=repo,
                replay_cache_path=replay_cache_path,
                replay_cache_key=replay_cache_key,
                source_plan_stage=source_plan_stage,
                replay_cache_info=replay_cache_info,
            )
        )

    def _build_plan_replay_key(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        temporal_input: dict[str, Any],
        plugins_loaded: list[str],
        conventions_hashes: dict[str, str],
        memory_stage: Any,
        index_stage: Any,
        repomap_stage: Any,
        augment_stage: Any,
        skills_stage: Any,
    ) -> str:
        return _typed_str(
            self._source_plan_replay_service.build_plan_replay_key(
                query=query,
                repo=repo,
                root=root,
                temporal_input=temporal_input,
                plugins_loaded=plugins_loaded,
                conventions_hashes=conventions_hashes,
                memory_stage=memory_stage,
                index_stage=index_stage,
                repomap_stage=repomap_stage,
                augment_stage=augment_stage,
                skills_stage=skills_stage,
            )
        )

    @staticmethod
    def _build_memory_replay_fingerprint(*, memory_payload: dict[str, Any]) -> str:
        return _typed_str(
            SourcePlanReplayService.build_memory_replay_fingerprint(memory_payload=memory_payload)
        )

    @staticmethod
    def _build_index_replay_fingerprint(*, index_payload: dict[str, Any]) -> str:
        return _typed_str(
            SourcePlanReplayService.build_index_replay_fingerprint(index_payload=index_payload)
        )

    @staticmethod
    def _build_repomap_replay_fingerprint(*, repomap_payload: dict[str, Any]) -> str:
        return _typed_str(
            SourcePlanReplayService.build_repomap_replay_fingerprint(
                repomap_payload=repomap_payload
            )
        )

    @staticmethod
    def _build_repo_inputs_replay_fingerprint(
        *,
        root: str,
        index_payload: dict[str, Any],
        repomap_payload: dict[str, Any],
    ) -> str:
        return _typed_str(
            SourcePlanReplayService.build_repo_inputs_replay_fingerprint(
                root=root,
                index_payload=index_payload,
                repomap_payload=repomap_payload,
            )
        )

    @staticmethod
    def _build_augment_replay_fingerprint(*, augment_payload: dict[str, Any]) -> str:
        return _typed_str(
            SourcePlanReplayService.build_augment_replay_fingerprint(
                augment_payload=augment_payload
            )
        )

    @staticmethod
    def _build_skills_replay_fingerprint(*, skills_payload: dict[str, Any]) -> str:
        return _typed_str(
            SourcePlanReplayService.build_skills_replay_fingerprint(skills_payload=skills_payload)
        )

    def _load_plugins(self, *, root: str) -> tuple[HookBus, list[str]]:
        return _typed_plugin_load_result(
            load_orchestrator_plugins(
                plugins_enabled=bool(self._config.plugins.enabled),
                plugin_loader=self._plugin_loader,
                root=root,
            )
        )

    @staticmethod
    def _collect_durable_stats_reasons(
        *,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
    ) -> list[str]:
        return _typed_list_str(
            RuntimeObservabilityService.collect_durable_stats_reasons(
                stage_metrics=stage_metrics,
                contract_error=contract_error,
                replay_cache_info=replay_cache_info,
                trace_export=trace_export,
            )
        )

    def _estimate_tokens(self, text: str) -> int:
        return _typed_int(estimate_tokens(text, model=self._tokenizer_model))

    @staticmethod
    def _normalize_namespace_component(*, value: str, fallback: str) -> str:
        return _typed_str(
            MemoryContextService.normalize_namespace_component(
                value=value,
                fallback=fallback,
            )
        )

    def _resolve_memory_namespace(
        self,
        *,
        repo: str,
        root: str,
    ) -> tuple[str | None, str, str]:
        return _typed_namespace_result(
            self._memory_context_service.resolve_memory_namespace(
                repo=repo,
                root=root,
            )
        )

    def _resolve_profile_store(self, *, root: str) -> ProfileStore:
        return _typed_profile_store(self._memory_context_service.resolve_profile_store(root=root))

    def _resolve_capture_notes_path(self, *, root: str) -> Path:
        return _typed_path(self._memory_context_service.resolve_capture_notes_path(root=root))

    def _resolve_validation_preference_capture_store(
        self,
        *,
        root: str,
    ) -> DurablePreferenceCaptureStore | None:
        return _typed_optional_preference_capture_store(
            self._memory_context_service.resolve_validation_preference_capture_store(
                root=root,
            ),
        )

    def _capture_memory_signal(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        namespace: str | None,
        matched_keywords: list[str],
    ) -> dict[str, Any]:
        return _typed_dict(
            self._memory_context_service.capture_memory_signal(
                query=query,
                repo=repo,
                root=root,
                namespace=namespace,
                matched_keywords=matched_keywords,
            )
        )

    def _run_memory(self, *, ctx: StageContext) -> dict[str, Any]:
        query = ctx.query
        repo = ctx.repo
        root = ctx.root
        runtime = build_orchestrator_memory_runtime(
            query=query,
            repo=repo,
            root=root,
            ctx_state=self._context_state(ctx=ctx),
            resolve_memory_namespace_fn=self._resolve_memory_namespace,
            extract_signal_fn=self._signal_extractor.extract,
        )
        payload = run_memory(
            memory_provider=self._memory_provider,
            query=query,
            disclosure_mode=self._config.memory.disclosure_mode,
            strategy=self._config.memory.strategy,
            timeline_enabled=self._config.memory.timeline_enabled,
            preview_max_chars=self._config.memory.preview_max_chars,
            tokenizer_model=self._tokenizer_model,
            container_tag=runtime.container_tag,
            time_range=runtime.time_range,
            start_date=runtime.start_date,
            end_date=runtime.end_date,
            temporal_enabled=bool(self._config.memory.temporal.enabled),
            recency_boost_enabled=bool(self._config.memory.temporal.recency_boost_enabled),
            recency_boost_max=float(self._config.memory.temporal.recency_boost_max),
            timezone_mode=str(self._config.memory.temporal.timezone_mode),
            namespace_mode=runtime.namespace_mode,
            namespace_source=runtime.namespace_source,
            gate_enabled=bool(self._config.memory.gate.enabled),
            gate_mode=str(self._config.memory.gate.mode),
            postprocess_enabled=bool(self._config.memory.postprocess.enabled),
            postprocess_noise_filter_enabled=bool(
                self._config.memory.postprocess.noise_filter_enabled
            ),
            postprocess_length_norm_anchor_chars=int(
                self._config.memory.postprocess.length_norm_anchor_chars
            ),
            postprocess_time_decay_half_life_days=float(
                self._config.memory.postprocess.time_decay_half_life_days
            ),
            postprocess_hard_min_score=float(self._config.memory.postprocess.hard_min_score),
            postprocess_diversity_enabled=bool(self._config.memory.postprocess.diversity_enabled),
            postprocess_diversity_similarity_threshold=float(
                self._config.memory.postprocess.diversity_similarity_threshold
            ),
        )
        return _typed_dict(
            self._memory_context_service.attach_memory_stage_payloads(
                payload=payload,
                query=query,
                repo=repo,
                root=root,
                namespace=runtime.container_tag,
                matched_keywords=list(runtime.extraction.matched_keywords),
                triggered=bool(runtime.extraction.triggered),
                reason=runtime.extraction.reason,
                query_length=runtime.extraction.query_length,
                tokenizer_model=self._tokenizer_model,
            )
        )

    def _run_index(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(
            run_orchestrator_index_stage(
                ctx=ctx,
                config=self._config,
                tokenizer_model=self._tokenizer_model,
                cochange_neighbor_cap=self._COCHANGE_NEIGHBOR_CAP,
                cochange_min_neighbor_score=self._COCHANGE_MIN_NEIGHBOR_SCORE,
                cochange_max_boost=self._COCHANGE_MAX_BOOST,
            )
        )

    def _run_repomap(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(
            run_orchestrator_repomap_stage(
                ctx=ctx,
                config=self._config,
                tokenizer_model=self._tokenizer_model,
            )
        )

    def _run_augment(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(
            run_orchestrator_augment_stage(
                ctx=ctx,
                config=self._config,
                lsp_broker=self._lsp_broker,
            )
        )

    def _run_skills(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(
            run_orchestrator_skills_stage(
                ctx=ctx,
                config=self._config,
                skill_manifest=self._skill_manifest,
            )
        )

    def _precompute_skills_route(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(
            precompute_orchestrator_skills_route(
                ctx=ctx,
                config=self._config,
                skill_manifest=self._skill_manifest,
            )
        )

    def _run_context_refine(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(run_context_refine(ctx=ctx))

    def _run_history_channel(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(run_history_channel(ctx=ctx))

    def _run_source_plan(self, *, ctx: StageContext) -> dict[str, Any]:
        runtime = build_orchestrator_source_plan_runtime(
            config=self._config,
            pipeline_order=tuple(self.PIPELINE_ORDER),
        )
        handoff_namespace: str | None = None
        if self._config.memory.capture.enabled:
            handoff_namespace, _, _ = self._resolve_memory_namespace(
                repo=ctx.repo,
                root=ctx.root,
            )
        return _typed_dict(
            run_source_plan(
                ctx=ctx,
                pipeline_order=runtime.pipeline_order,
                chunk_top_k=runtime.chunk_top_k,
                chunk_per_file_limit=runtime.chunk_per_file_limit,
                chunk_token_budget=runtime.chunk_token_budget,
                chunk_disclosure=runtime.chunk_disclosure,
                policy_version=runtime.policy_version,
                handoff_artifact_dir=runtime.handoff_artifact_dir,
                handoff_notes_path=(
                    runtime.handoff_notes_path if self._config.memory.capture.enabled else None
                ),
                handoff_note_namespace=handoff_namespace,
            )
        )

    def _run_validation(self, *, ctx: StageContext) -> dict[str, Any]:
        return _typed_dict(
            run_orchestrator_validation_stage(
                ctx=ctx,
                config=self._config,
                lsp_broker=self._lsp_broker,
                resolve_validation_preference_capture_store_fn=(
                    self._resolve_validation_preference_capture_store
                ),
            )
        )

    @staticmethod
    def _resolve_repo_relative_path(*, root: str, configured_path: str) -> Path:
        path = Path(str(configured_path or "").strip() or "context-map/index.json")
        if path.is_absolute():
            return path
        return Path(root) / path


__all__ = [
    "BM25_B",
    "BM25_K1",
    "CHUNK_FILE_PRIOR_WEIGHT",
    "CHUNK_PATH_MATCH",
    "CHUNK_SYMBOL_EXACT",
    "HEUR_PATH_EXACT",
    "HEUR_SYMBOL_EXACT",
    "HYBRID_BM25_WEIGHT",
    "HYBRID_HEURISTIC_WEIGHT",
    "HYBRID_RRF_K_DEFAULT",
    "AceOrchestrator",
]
