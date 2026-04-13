from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, cast

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
from ace_lite.orchestrator_payload_builder import (
    build_default_validation_payload,
    build_orchestrator_plan_payload,
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
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import (
    CORE_PIPELINE_ORDER,
    StageRegistry,
    iter_stage_descriptors,
)
from ace_lite.pipeline.stage_tags import build_stage_tags
from ace_lite.pipeline.stages.augment import run_diagnostics_augment
from ace_lite.pipeline.stages.index import IndexStageConfig, run_index
from ace_lite.pipeline.stages.memory import run_memory
from ace_lite.pipeline.stages.repomap import run_repomap
from ace_lite.pipeline.stages.skills import route_skills, run_skills
from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.stages.validation import run_validation_stage
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
        self._durable_stats_store_factory = (
            runtime_state.services.durable_stats_store_factory
        )
        self._durable_stats_session_id = runtime_state.durable_stats_session_id
        self._conventions_files = (
            list(runtime_state.conventions_files)
            if runtime_state.conventions_files
            else None
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
        return self._runtime_manager.shutdown()

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
        validated_request_payload = validate_plan_request(
            cast(dict[str, Any], request_payload)
        )
        request = PlanRequestAdapter(
            cast(dict[str, Any], validated_request_payload)
        )
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
        payload = finalization_result.payload
        return payload

    def _build_registry(self) -> StageRegistry:
        registry = StageRegistry()
        stage_handlers = {
            "memory": lambda ctx: self._run_memory(ctx=ctx),
            "index": lambda ctx: self._run_index(ctx=ctx),
            "repomap": lambda ctx: self._run_repomap(ctx=ctx),
            "augment": lambda ctx: self._run_augment(ctx=ctx),
            "skills": lambda ctx: self._run_skills(ctx=ctx),
            "source_plan": lambda ctx: self._run_source_plan(ctx=ctx),
            "validation": lambda ctx: self._run_validation(ctx=ctx),
        }
        for descriptor in iter_stage_descriptors():
            registry.register_descriptor(
                descriptor.with_handler(stage_handlers[descriptor.name])
            )
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

        ctx.state[stage_name] = stage_payload
        if stage_name == "validation":
            selected_patch_artifact = (
                stage_payload.get("patch_artifact", {})
                if isinstance(stage_payload, dict)
                else {}
            )
            if isinstance(selected_patch_artifact, dict) and selected_patch_artifact:
                ctx.state["_validation_patch_artifact"] = dict(selected_patch_artifact)
            else:
                ctx.state.pop("_validation_patch_artifact", None)

            selected_patch_artifacts = (
                stage_payload.get("patch_artifacts", [])
                if isinstance(stage_payload, dict)
                else []
            )
            if isinstance(selected_patch_artifacts, list) and selected_patch_artifacts:
                ctx.state["_validation_patch_artifacts"] = [
                    dict(item) for item in selected_patch_artifacts if isinstance(item, dict)
                ]
            else:
                ctx.state.pop("_validation_patch_artifacts", None)
        if stage_name == "augment":
            if self._config.skills.precomputed_routing_enabled:
                ctx.state["_skills_route"] = self._precompute_skills_route(ctx=ctx)
            else:
                ctx.state.pop("_skills_route", None)
        capture_payload = self._capture_long_term_stage_observation(
            stage_name=stage_name,
            ctx=ctx,
            stage_payload=stage_payload,
        )
        if capture_payload is not None:
            ctx.state.setdefault("_long_term_capture", []).append(capture_payload)
        logger.debug("stage.end", extra={"stage": stage_name, "repo": repo})
        return None

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
        return payload

    def _default_validation_payload(self) -> dict[str, Any]:
        return build_default_validation_payload(
            policy_version=str(self._config.retrieval.policy_version)
        )

    @staticmethod
    def _extract_source_plan_validation_feedback_summary(
        source_plan_stage: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_plan_stage, dict):
            return {}
        steps_value = source_plan_stage.get("steps")
        steps: list[Any] = list(steps_value) if isinstance(steps_value, list) else []
        validate_step = next(
            (
                item
                for item in steps
                if isinstance(item, dict)
                and str(item.get("stage") or "").strip() == "validate"
            ),
            {},
        )
        validation_feedback_summary = (
            validate_step.get("validation_feedback_summary")
            if isinstance(validate_step, dict)
            else None
        )
        return (
            dict(validation_feedback_summary)
            if isinstance(validation_feedback_summary, dict)
            else {}
        )

    def _capture_long_term_stage_observation(
        self,
        *,
        stage_name: str,
        ctx: StageContext,
        stage_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self._memory_context_service.capture_long_term_stage_observation(
            stage_name=stage_name,
            ctx=ctx,
            stage_payload=stage_payload,
        )

    def _resolve_plan_replay_cache_path(self, *, root: str) -> Path:
        return self._source_plan_replay_service.resolve_plan_replay_cache_path(
            root=root
        )

    def _extract_source_plan_failure_signal_summary(
        self,
        source_plan_stage: Any,
    ) -> dict[str, Any]:
        return self._source_plan_replay_service.extract_source_plan_failure_signal_summary(
            source_plan_stage
        )

    def _default_plan_replay_cache_info(self, *, root: str) -> dict[str, Any]:
        return self._source_plan_replay_service.default_plan_replay_cache_info(root=root)

    def _load_replayed_source_plan(
        self,
        *,
        root: str,
        replay_cache_path: Path,
        replay_cache_key: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        return self._source_plan_replay_service.load_replayed_source_plan(
            root=root,
            replay_cache_path=replay_cache_path,
            replay_cache_key=replay_cache_key,
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
        return self._source_plan_replay_service.store_source_plan_replay(
            query=query,
            repo=repo,
            replay_cache_path=replay_cache_path,
            replay_cache_key=replay_cache_key,
            source_plan_stage=source_plan_stage,
            replay_cache_info=replay_cache_info,
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
        return self._source_plan_replay_service.build_plan_replay_key(
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

    @staticmethod
    def _build_memory_replay_fingerprint(*, memory_payload: dict[str, Any]) -> str:
        return SourcePlanReplayService.build_memory_replay_fingerprint(
            memory_payload=memory_payload
        )

    @staticmethod
    def _build_index_replay_fingerprint(*, index_payload: dict[str, Any]) -> str:
        return SourcePlanReplayService.build_index_replay_fingerprint(
            index_payload=index_payload
        )

    @staticmethod
    def _build_repomap_replay_fingerprint(*, repomap_payload: dict[str, Any]) -> str:
        return SourcePlanReplayService.build_repomap_replay_fingerprint(
            repomap_payload=repomap_payload
        )

    @staticmethod
    def _build_repo_inputs_replay_fingerprint(
        *,
        root: str,
        index_payload: dict[str, Any],
        repomap_payload: dict[str, Any],
    ) -> str:
        return SourcePlanReplayService.build_repo_inputs_replay_fingerprint(
            root=root,
            index_payload=index_payload,
            repomap_payload=repomap_payload,
        )

    @staticmethod
    def _build_augment_replay_fingerprint(*, augment_payload: dict[str, Any]) -> str:
        return SourcePlanReplayService.build_augment_replay_fingerprint(
            augment_payload=augment_payload
        )

    @staticmethod
    def _build_skills_replay_fingerprint(*, skills_payload: dict[str, Any]) -> str:
        return SourcePlanReplayService.build_skills_replay_fingerprint(
            skills_payload=skills_payload
        )

    def _export_stage_trace(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
        total_ms: float,
        stage_metrics: list[StageMetric],
        plugin_policy_summary: dict[str, Any],
    ) -> dict[str, Any]:
        return self._runtime_observability_service.export_stage_trace(
            query=query,
            repo=repo,
            root=root,
            started_at=started_at,
            total_ms=total_ms,
            stage_metrics=stage_metrics,
            plugin_policy_summary=plugin_policy_summary,
        )

    def _load_plugins(self, *, root: str) -> tuple[HookBus, list[str]]:
        if not self._config.plugins.enabled:
            return HookBus(), []
        return self._plugin_loader.load_hooks(repo_root=root)

    def _record_durable_stats(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        started_at: datetime,
        total_ms: float,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
    ) -> dict[str, Any]:
        return self._runtime_observability_service.record_durable_stats(
            query=query,
            repo=repo,
            root=root,
            started_at=started_at,
            total_ms=total_ms,
            stage_metrics=stage_metrics,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
            trace_export=trace_export,
            learning_router_rollout_decision=self._last_learning_router_rollout_decision,
        )

    @staticmethod
    def _collect_durable_stats_reasons(
        *,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
    ) -> list[str]:
        return RuntimeObservabilityService.collect_durable_stats_reasons(
            stage_metrics=stage_metrics,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
            trace_export=trace_export,
        )

    def _estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text, model=self._tokenizer_model)

    @staticmethod
    def _normalize_namespace_component(*, value: str, fallback: str) -> str:
        return MemoryContextService.normalize_namespace_component(
            value=value,
            fallback=fallback,
        )

    def _resolve_memory_namespace(
        self,
        *,
        repo: str,
        root: str,
    ) -> tuple[str | None, str, str]:
        return self._memory_context_service.resolve_memory_namespace(
            repo=repo,
            root=root,
        )

    def _resolve_profile_store(self, *, root: str) -> ProfileStore:
        return self._memory_context_service.resolve_profile_store(
            root=root,
        )

    def _resolve_capture_notes_path(self, *, root: str) -> Path:
        return self._memory_context_service.resolve_capture_notes_path(root=root)

    def _resolve_validation_preference_capture_store(
        self,
        *,
        root: str,
    ) -> DurablePreferenceCaptureStore | None:
        return self._memory_context_service.resolve_validation_preference_capture_store(
            root=root,
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
        return self._memory_context_service.capture_memory_signal(
            query=query,
            repo=repo,
            root=root,
            namespace=namespace,
            matched_keywords=matched_keywords,
        )

    def _run_memory(self, *, ctx: StageContext) -> dict[str, Any]:
        query = ctx.query
        repo = ctx.repo
        root = ctx.root

        def normalize_temporal_input(value: Any) -> str | None:
            if value is None:
                return None
            normalized = str(value).strip()
            return normalized or None

        container_tag, namespace_mode, namespace_source = self._resolve_memory_namespace(
            repo=repo,
            root=root,
        )
        temporal_input = (
            ctx.state.get("temporal", {}) if isinstance(ctx.state.get("temporal"), dict) else {}
        )
        time_range = temporal_input.get("time_range")
        start_date = temporal_input.get("start_date")
        end_date = temporal_input.get("end_date")
        payload = run_memory(
            memory_provider=self._memory_provider,
            query=query,
            disclosure_mode=self._config.memory.disclosure_mode,
            strategy=self._config.memory.strategy,
            timeline_enabled=self._config.memory.timeline_enabled,
            preview_max_chars=self._config.memory.preview_max_chars,
            tokenizer_model=self._tokenizer_model,
            container_tag=container_tag,
            time_range=normalize_temporal_input(time_range),
            start_date=normalize_temporal_input(start_date),
            end_date=normalize_temporal_input(end_date),
            temporal_enabled=bool(self._config.memory.temporal.enabled),
            recency_boost_enabled=bool(
                self._config.memory.temporal.recency_boost_enabled
            ),
            recency_boost_max=float(self._config.memory.temporal.recency_boost_max),
            timezone_mode=str(self._config.memory.temporal.timezone_mode),
            namespace_mode=namespace_mode,
            namespace_source=namespace_source,
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
            postprocess_diversity_enabled=bool(
                self._config.memory.postprocess.diversity_enabled
            ),
            postprocess_diversity_similarity_threshold=float(
                self._config.memory.postprocess.diversity_similarity_threshold
            ),
        )
        if not self._config.memory.profile.enabled:
            payload["profile"] = {"enabled": False, "facts": [], "selected_count": 0}
        else:
            payload["profile"] = self._memory_context_service.build_profile_payload(
                root=root,
                tokenizer_model=self._tokenizer_model,
            )

        extraction = self._signal_extractor.extract(query)
        payload["capture"] = self._memory_context_service.build_capture_payload(
            query=query,
            repo=repo,
            root=root,
            namespace=container_tag,
            matched_keywords=list(extraction.matched_keywords),
            triggered=bool(extraction.triggered),
            reason=extraction.reason,
            query_length=extraction.query_length,
        )
        return payload

    def _run_index(self, *, ctx: StageContext) -> dict[str, Any]:
        return run_index(
            ctx=ctx,
            config=IndexStageConfig.from_orchestrator_config(
                config=self._config,
                tokenizer_model=self._tokenizer_model,
                cochange_neighbor_cap=self._COCHANGE_NEIGHBOR_CAP,
                cochange_min_neighbor_score=self._COCHANGE_MIN_NEIGHBOR_SCORE,
                cochange_max_boost=self._COCHANGE_MAX_BOOST,
            ),
        )

    def _run_repomap(self, *, ctx: StageContext) -> dict[str, Any]:
        cfg = self._config
        return run_repomap(
            ctx=ctx,
            repomap_enabled=cfg.repomap.enabled,
            repomap_neighbor_limit=cfg.repomap.neighbor_limit,
            repomap_budget_tokens=cfg.repomap.budget_tokens,
            repomap_top_k=cfg.repomap.top_k,
            repomap_ranking_profile=cfg.repomap.ranking_profile,
            repomap_signal_weights=cfg.repomap.signal_weights,
            tokenizer_model=self._tokenizer_model,
            policy_version=cfg.retrieval.policy_version,
        )

    def _run_augment(self, *, ctx: StageContext) -> dict[str, Any]:
        cfg = self._config
        index_stage = ctx.state.get("index", {})
        repomap_stage = ctx.state.get("repomap", {})
        index_files = ctx.state.get("__index_files", {})
        vcs_worktree_override = ctx.state.get("__vcs_worktree")
        if not isinstance(vcs_worktree_override, dict):
            vcs_worktree_override = None
        policy = (
            ctx.state.get("__policy", {})
            if isinstance(ctx.state.get("__policy"), dict)
            else {}
        )
        candidates = self._resolve_augment_candidates(
            index_stage=index_stage,
            repomap_stage=repomap_stage,
            index_files=index_files,
        )
        payload = run_diagnostics_augment(
            root=ctx.root,
            query=ctx.query,
            index_stage={"candidate_files": candidates},
            enabled=cfg.lsp.enabled,
            top_n=cfg.lsp.top_n,
            broker=self._lsp_broker,
            xref_enabled=cfg.lsp.xref_enabled,
            xref_top_n=cfg.lsp.xref_top_n,
            xref_time_budget_ms=cfg.lsp.time_budget_ms,
            candidate_chunks=index_stage.get("candidate_chunks", [])
            if isinstance(index_stage, dict)
            else [],
            junit_xml_path=cfg.tests.junit_xml,
            coverage_json_path=cfg.tests.coverage_json,
            sbfl_json_path=cfg.tests.sbfl_json,
            sbfl_metric=cfg.tests.sbfl_metric,
            vcs_enabled=cfg.cochange.enabled,
            vcs_worktree_override=vcs_worktree_override,
        )
        payload["policy_name"] = str(policy.get("name", "general"))
        payload["policy_version"] = str(
            policy.get("version", cfg.retrieval.policy_version)
        )
        return payload

    def _run_skills(self, *, ctx: StageContext) -> dict[str, Any]:
        return run_skills(
            ctx=ctx,
            skill_manifest=self._skill_manifest,
            top_n=self._config.skills.top_n,
            token_budget=self._config.skills.token_budget,
            routed_payload=(
                ctx.state.get("_skills_route")
                if self._config.skills.precomputed_routing_enabled
                and isinstance(ctx.state.get("_skills_route"), dict)
                else None
            ),
        )

    def _precompute_skills_route(self, *, ctx: StageContext) -> dict[str, Any]:
        index_stage = ctx.state.get("index", {})
        module_hint = (
            str(index_stage.get("module_hint", "") or "")
            if isinstance(index_stage, dict)
            else ""
        )
        return route_skills(
            query=ctx.query,
            module_hint=module_hint,
            skill_manifest=self._skill_manifest,
            top_n=self._config.skills.top_n,
        )

    def _run_source_plan(self, *, ctx: StageContext) -> dict[str, Any]:
        cfg = self._config
        return run_source_plan(
            ctx=ctx,
            pipeline_order=self.PIPELINE_ORDER,
            chunk_top_k=cfg.chunking.top_k,
            chunk_per_file_limit=cfg.chunking.per_file_limit,
            chunk_token_budget=cfg.chunking.token_budget,
            chunk_disclosure=cfg.chunking.disclosure,
            policy_version=cfg.retrieval.policy_version,
        )

    def _run_validation(self, *, ctx: StageContext) -> dict[str, Any]:
        cfg = self._config
        policy = (
            ctx.state.get("__policy", {})
            if isinstance(ctx.state.get("__policy"), dict)
            else {}
        )
        preference_capture_store = self._resolve_validation_preference_capture_store(
            root=ctx.root,
        )
        return run_validation_stage(
            root=ctx.root,
            query=ctx.query,
            source_plan_stage=(
                ctx.state.get("source_plan", {})
                if isinstance(ctx.state.get("source_plan"), dict)
                else {}
            ),
            index_stage=(
                ctx.state.get("index", {})
                if isinstance(ctx.state.get("index"), dict)
                else {}
            ),
            enabled=cfg.validation.enabled,
            include_xref=cfg.validation.include_xref,
            top_n=cfg.validation.top_n,
            xref_top_n=cfg.validation.xref_top_n,
            sandbox_timeout_seconds=cfg.validation.sandbox_timeout_seconds,
            broker=self._lsp_broker,
            patch_artifact=(
                ctx.state.get("_validation_patch_artifact")
                if isinstance(ctx.state.get("_validation_patch_artifact"), dict)
                else None
            ),
            policy_name=str(policy.get("name", "general")),
            policy_version=str(policy.get("version", cfg.retrieval.policy_version)),
            preference_capture_store=preference_capture_store,
            preference_capture_repo_key=ctx.repo,
        )

    @staticmethod
    def _resolve_repo_relative_path(*, root: str, configured_path: str) -> Path:
        path = Path(str(configured_path or "").strip() or "context-map/index.json")
        if path.is_absolute():
            return path
        return Path(root) / path

    @staticmethod
    def _resolve_augment_candidates(
        *,
        index_stage: dict[str, Any],
        repomap_stage: dict[str, Any],
        index_files: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        base_candidates = (
            index_stage.get("candidate_files", [])
            if isinstance(index_stage, dict)
            else []
        )
        if not isinstance(base_candidates, list):
            base_candidates = []

        focused = (
            repomap_stage.get("focused_files", [])
            if isinstance(repomap_stage, dict)
            else []
        )
        if not isinstance(focused, list):
            focused = []
        if not focused:
            return [item for item in base_candidates if isinstance(item, dict)]

        by_path = {
            str(item.get("path", "")): item
            for item in base_candidates
            if isinstance(item, dict) and str(item.get("path", "")).strip()
        }

        resolved: list[dict[str, Any]] = []
        for path in focused:
            relative_path = str(path).strip()
            if not relative_path:
                continue
            if relative_path in by_path:
                resolved.append(by_path[relative_path])
                continue

            entry = (
                index_files.get(relative_path, {})
                if isinstance(index_files, dict)
                else {}
            )
            if not isinstance(entry, dict):
                continue
            resolved.append(
                {
                    "path": relative_path,
                    "module": entry.get("module", ""),
                    "language": entry.get("language", ""),
                    "score": 0,
                    "symbol_count": len(entry.get("symbols", []))
                    if isinstance(entry.get("symbols", []), list)
                    else 0,
                    "import_count": len(entry.get("imports", []))
                    if isinstance(entry.get("imports", []), list)
                    else 0,
                }
            )
        return resolved

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
