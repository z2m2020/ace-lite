from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from ace_lite.conventions import load_conventions
from ace_lite.exceptions import StageContractError
from ace_lite.memory import (
    MemoryProvider,
)
from ace_lite.memory.local_notes import append_capture_note
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.plan_replay_cache import (
    default_plan_replay_cache_path,
    load_cached_plan,
    load_cached_plan_with_meta,
    normalize_plan_query,
    store_cached_plan,
)
from ace_lite.orchestrator_replay import (
    build_augment_replay_fingerprint,
    build_index_replay_fingerprint,
    build_memory_replay_fingerprint,
    build_orchestrator_plan_replay_key,
    build_repomap_replay_fingerprint,
    build_repo_inputs_replay_fingerprint,
    build_skills_replay_fingerprint,
)
from ace_lite.orchestrator_runtime_support import (
    run_pre_source_plan_stages,
    run_source_plan_stage_with_replay,
)
from ace_lite.pipeline.contracts import validate_stage_output
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.plugin_runtime import PluginRuntime
from ace_lite.pipeline.registry import StageRegistry
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
from ace_lite.profile_store import ProfileStore
from ace_lite.runtime_manager import RuntimeManager
from ace_lite.runtime_state import RuntimeState
from ace_lite.schema import SCHEMA_VERSION, validate_context_plan
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
from ace_lite.tracing import export_stage_trace_jsonl, export_stage_trace_otlp
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.validation.result import build_validation_result_v1

logger = logging.getLogger(__name__)


class AceOrchestrator:
    PIPELINE_ORDER = ("memory", "index", "repomap", "augment", "skills", "source_plan", "validation")
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
    ) -> dict[str, Any]:
        root_path = str(Path(root).resolve())
        conventions = load_conventions(
            root_dir=root_path,
            files=self._conventions_files,
            previous_hashes=self._conventions_hashes,
        )
        self._runtime_state.update_conventions_hashes(
            conventions.get("file_hashes", {})
        )
        hook_bus, plugins_loaded = self._load_plugins(root=root_path)

        registry = self._build_registry()
        temporal_input = {
            "time_range": str(time_range or "").strip() or None,
            "start_date": str(start_date or "").strip() or None,
            "end_date": str(end_date or "").strip() or None,
        }
        ctx = StageContext(
            query=query,
            repo=repo,
            root=root_path,
            state={
                "conventions": conventions,
                "temporal": temporal_input,
            },
        )

        started = perf_counter()
        started_at = datetime.now(timezone.utc)
        stage_metrics, contract_error = run_pre_source_plan_stages(
            orchestrator=self,
            repo=repo,
            ctx=ctx,
            registry=registry,
            hook_bus=hook_bus,
        )
        contract_error, replay_cache_info = run_source_plan_stage_with_replay(
            orchestrator=self,
            query=query,
            repo=repo,
            root_path=root_path,
            temporal_input=temporal_input,
            plugins_loaded=plugins_loaded,
            ctx=ctx,
            registry=registry,
            hook_bus=hook_bus,
            stage_metrics=stage_metrics,
            contract_error=contract_error,
        )
        if contract_error is None:
            contract_error = self._execute_stage(
                stage_name="validation",
                repo=repo,
                ctx=ctx,
                registry=registry,
                hook_bus=hook_bus,
                stage_metrics=stage_metrics,
            )

        total_ms = (perf_counter() - started) * 1000.0

        payload = self._build_plan_payload(
            query=query,
            repo=repo,
            root=root_path,
            conventions=conventions,
            ctx=ctx,
            stage_metrics=stage_metrics,
            plugins_loaded=plugins_loaded,
            total_ms=total_ms,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
        )

        if contract_error is not None:
            payload["observability"]["error"] = {
                "type": "stage_contract_error",
                "stage": contract_error.stage or "",
                "error_code": contract_error.error_code,
                "reason": contract_error.reason,
                "message": contract_error.message,
                "context": contract_error.context,
            }
            payload["observability"]["contract_errors"] = ctx.state.get(
                "_contract_errors", []
            )

        validate_context_plan(payload)

        trace_export = self._export_stage_trace(
            query=query,
            repo=repo,
            root=root_path,
            started_at=started_at,
            total_ms=total_ms,
            stage_metrics=stage_metrics,
            plugin_policy_summary=payload["observability"].get("plugin_policy_summary", {}),
        )
        if trace_export.get("enabled"):
            payload["observability"]["trace_export"] = trace_export

        payload["observability"]["durable_stats"] = self._record_durable_stats(
            query=query,
            repo=repo,
            root=root_path,
            started_at=started_at,
            total_ms=total_ms,
            stage_metrics=stage_metrics,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
            trace_export=trace_export,
        )
        self._runtime_state.note_plan_root(root_path)
        self._runtime_state.note_durable_stats(
            payload["observability"]["durable_stats"]
        )
        if self._runtime_manager is not None:
            self._runtime_manager.ensure_shutdown_hooks()

        return payload

    def _build_registry(self) -> StageRegistry:
        registry = StageRegistry()
        registry.register("memory", lambda ctx: self._run_memory(ctx=ctx))
        registry.register("index", lambda ctx: self._run_index(ctx=ctx))
        registry.register("repomap", lambda ctx: self._run_repomap(ctx=ctx))
        registry.register("augment", lambda ctx: self._run_augment(ctx=ctx))
        registry.register("skills", lambda ctx: self._run_skills(ctx=ctx))
        registry.register("source_plan", lambda ctx: self._run_source_plan(ctx=ctx))
        registry.register("validation", lambda ctx: self._run_validation(ctx=ctx))
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
        if stage_name == "augment":
            if self._config.skills.precomputed_routing_enabled:
                ctx.state["_skills_route"] = self._precompute_skills_route(ctx=ctx)
            else:
                ctx.state.pop("_skills_route", None)
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
        observability: dict[str, Any] = {
            "total_ms": total_ms,
            "stage_metrics": [
                {
                    "stage": metric.stage,
                    "elapsed_ms": metric.elapsed_ms,
                    "plugins": metric.plugins,
                    "tags": metric.tags,
                }
                for metric in stage_metrics
            ],
            "plugins_loaded": plugins_loaded,
            "plugin_action_log": ctx.state.get("_plugin_action_log", []),
            "plugin_conflicts": ctx.state.get("_plugin_conflicts", []),
            "plugin_policy_summary": self._plugin_runtime.build_policy_summary(
                stage_summary=ctx.state.get("_plugin_policy_stage", {}),
                pipeline_order=self.PIPELINE_ORDER,
            ),
        }
        if isinstance(replay_cache_info, dict):
            observability["plan_replay_cache"] = dict(replay_cache_info)

        payload = {
            "schema_version": SCHEMA_VERSION,
            "query": query,
            "repo": repo,
            "root": root,
            "pipeline_order": list(self.PIPELINE_ORDER),
            "conventions": {
                "count": conventions.get("count", 0),
                "rules_count": conventions.get("rules_count", 0),
                "loaded_files": [
                    {
                        "path": item.get("path"),
                        "sha256": item.get("sha256"),
                    }
                    for item in conventions.get("loaded_files", [])
                    if isinstance(item, dict)
                ],
                "rules": [
                    {
                        "name": item.get("name"),
                        "path": item.get("path"),
                        "priority": item.get("priority", 0),
                        "always_load": bool(item.get("always_load", False)),
                        "globs": item.get("globs", []),
                    }
                    for item in conventions.get("rules", [])
                    if isinstance(item, dict)
                ],
                "cache_hit": conventions.get("cache_hit", False),
            },
            "memory": ctx.state.get("memory", {}),
            "index": ctx.state.get("index", {}),
            "repomap": ctx.state.get("repomap", {}),
            "augment": ctx.state.get("augment", {}),
            "skills": ctx.state.get("skills", {}),
            "source_plan": ctx.state.get("source_plan", {}),
            "validation": (
                ctx.state.get("validation", {})
                if isinstance(ctx.state.get("validation"), dict)
                and ctx.state.get("validation")
                else self._default_validation_payload()
            ),
            "observability": observability,
        }

        if contract_error is not None:
            payload["observability"]["error"] = {
                "type": "stage_contract_error",
                "stage": contract_error.stage or "",
                "error_code": contract_error.error_code,
                "reason": contract_error.reason,
                "message": contract_error.message,
                "context": contract_error.context,
            }
            payload["observability"]["contract_errors"] = ctx.state.get(
                "_contract_errors", []
            )

        return payload

    def _default_validation_payload(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "reason": "disabled",
            "sandbox": {
                "enabled": False,
                "sandbox_root": "",
                "patch_applied": False,
                "cleanup_ok": False,
                "restore_ok": False,
                "apply_result": {},
            },
            "diagnostics": [],
            "diagnostic_count": 0,
            "xref_enabled": False,
            "xref": {
                "count": 0,
                "results": [],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 0.0,
                "time_budget_ms": 0,
            },
            "result": build_validation_result_v1(
                selected_tests=[],
                sandboxed=False,
                runner="disabled",
                replay_key="",
                status="skipped",
            ).as_dict(),
            "patch_artifact_present": False,
            "policy_name": "general",
            "policy_version": str(self._config.retrieval.policy_version),
        }

    def _resolve_plan_replay_cache_path(self, *, root: str) -> Path:
        configured = str(self._config.plan_replay_cache.cache_path or "").strip()
        if not configured:
            return default_plan_replay_cache_path(root=root)
        return self._resolve_repo_relative_path(root=root, configured_path=configured)

    def _default_plan_replay_cache_info(self, *, root: str) -> dict[str, Any]:
        enabled = bool(self._config.plan_replay_cache.enabled)
        return {
            "enabled": enabled,
            "stage": self.PLAN_REPLAY_STAGE,
            "mode": self.PLAN_REPLAY_MODE,
            "cache_path": str(self._resolve_plan_replay_cache_path(root=root)),
            "hit": False,
            "safe_hit": False,
            "stale_hit_safe": enabled,
            "stored": False,
            "reused_stages": [],
            "guarded_by": list(self.PLAN_REPLAY_GUARDED_BY),
            "origin": "none",
            "age_seconds": None,
            "trust_class": "",
            "policy_name": self.PLAN_REPLAY_STAGE,
            "reason": "disabled" if not enabled else "not_reached",
        }

    def _load_replayed_source_plan(
        self,
        *,
        root: str,
        replay_cache_path: Path,
        replay_cache_key: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        replay_cache_info = self._default_plan_replay_cache_info(root=root)
        replay_cache_info["cache_path"] = str(replay_cache_path)
        replay_cache_info["key"] = replay_cache_key
        replay_cache_info["reason"] = "miss"

        lookup_started = perf_counter()
        cached_payload, cache_metadata = load_cached_plan_with_meta(
            cache_path=replay_cache_path,
            key=replay_cache_key,
        )
        replay_cache_info["lookup_ms"] = round(
            (perf_counter() - lookup_started) * 1000.0,
            3,
        )
        if not isinstance(cached_payload, dict):
            return None, replay_cache_info

        cached_source_plan = cached_payload.get("source_plan", {})
        if not isinstance(cached_source_plan, dict):
            replay_cache_info["reason"] = "invalid_cached_payload"
            return None, replay_cache_info

        try:
            validate_stage_output(self.PLAN_REPLAY_STAGE, cached_source_plan)
        except Exception as exc:
            replay_cache_info["reason"] = "invalid_cached_payload"
            replay_cache_info["load_error"] = str(exc)
            return None, replay_cache_info

        replay_cache_info["hit"] = True
        replay_cache_info["safe_hit"] = True
        replay_cache_info["reused_stages"] = [self.PLAN_REPLAY_STAGE]
        replay_cache_info["origin"] = str(cache_metadata.get("origin") or "unknown")
        replay_cache_info["age_seconds"] = cache_metadata.get("age_seconds")
        replay_cache_info["trust_class"] = str(cache_metadata.get("trust_class") or "")
        replay_cache_info["policy_name"] = str(
            cache_metadata.get("policy_name") or self.PLAN_REPLAY_STAGE
        )
        replay_cache_info["reason"] = "hit"
        return cached_source_plan, replay_cache_info

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
        updated_info = dict(replay_cache_info)
        source_plan_payload = (
            dict(source_plan_stage) if isinstance(source_plan_stage, dict) else {}
        )
        store_started = perf_counter()
        stored = store_cached_plan(
            cache_path=replay_cache_path,
            key=replay_cache_key,
            payload={"source_plan": source_plan_payload},
            meta={
                "query": normalize_plan_query(query),
                "repo": repo,
                "stage": self.PLAN_REPLAY_STAGE,
            },
        )
        updated_info["store_ms"] = round(
            (perf_counter() - store_started) * 1000.0,
            3,
        )
        updated_info["stored"] = bool(stored)
        updated_info["origin"] = "stage_artifact_cache"
        updated_info["trust_class"] = "exact"
        updated_info["policy_name"] = self.PLAN_REPLAY_STAGE
        if not bool(stored):
            updated_info["reason"] = "store_failed"
        return updated_info

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
        memory_payload = memory_stage if isinstance(memory_stage, dict) else {}
        index_payload = index_stage if isinstance(index_stage, dict) else {}
        repomap_payload = repomap_stage if isinstance(repomap_stage, dict) else {}
        augment_payload = augment_stage if isinstance(augment_stage, dict) else {}
        skills_payload = skills_stage if isinstance(skills_stage, dict) else {}
        return build_orchestrator_plan_replay_key(
            query=query,
            repo=repo,
            root=root,
            temporal_input=temporal_input,
            plugins_loaded=plugins_loaded,
            conventions_hashes=conventions_hashes,
            memory_payload=memory_payload,
            index_payload=index_payload,
            repomap_payload=repomap_payload,
            augment_payload=augment_payload,
            skills_payload=skills_payload,
            retrieval_policy_version=str(self._config.retrieval.policy_version),
            candidate_ranker_default=str(self._config.retrieval.candidate_ranker),
            chunk_disclosure=str(self._config.chunking.disclosure),
            budget_knobs={
                "top_k_files": int(self._config.retrieval.top_k_files),
                "repomap_top_k": int(self._config.repomap.top_k),
                "repomap_neighbor_limit": int(self._config.repomap.neighbor_limit),
                "repomap_budget_tokens": int(self._config.repomap.budget_tokens),
                "skills_top_n": int(self._config.skills.top_n),
                "skills_token_budget": int(self._config.skills.token_budget),
                "precomputed_skills_routing_enabled": bool(
                    self._config.skills.precomputed_routing_enabled
                ),
                "chunk_top_k": int(self._config.chunking.top_k),
                "chunk_per_file_limit": int(self._config.chunking.per_file_limit),
                "chunk_token_budget": int(self._config.chunking.token_budget),
                "lsp_top_n": int(self._config.lsp.top_n),
                "lsp_xref_top_n": int(self._config.lsp.xref_top_n),
            },
        )

    @staticmethod
    def _build_memory_replay_fingerprint(*, memory_payload: dict[str, Any]) -> str:
        return build_memory_replay_fingerprint(memory_payload=memory_payload)

    @staticmethod
    def _build_index_replay_fingerprint(*, index_payload: dict[str, Any]) -> str:
        return build_index_replay_fingerprint(index_payload=index_payload)

    @staticmethod
    def _build_repomap_replay_fingerprint(*, repomap_payload: dict[str, Any]) -> str:
        return build_repomap_replay_fingerprint(repomap_payload=repomap_payload)

    @staticmethod
    def _build_repo_inputs_replay_fingerprint(
        *,
        root: str,
        index_payload: dict[str, Any],
        repomap_payload: dict[str, Any],
    ) -> str:
        return build_repo_inputs_replay_fingerprint(
            root=root,
            index_payload=index_payload,
            repomap_payload=repomap_payload,
        )

    @staticmethod
    def _build_augment_replay_fingerprint(*, augment_payload: dict[str, Any]) -> str:
        return build_augment_replay_fingerprint(augment_payload=augment_payload)

    @staticmethod
    def _build_skills_replay_fingerprint(*, skills_payload: dict[str, Any]) -> str:
        return build_skills_replay_fingerprint(skills_payload=skills_payload)

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
        if not self._config.trace.export_enabled and not self._config.trace.otlp_enabled:
            return {"enabled": False}

        result: dict[str, Any] = {"enabled": True}

        if self._config.trace.export_enabled:
            output_path = self._resolve_repo_relative_path(
                root=root,
                configured_path=str(self._config.trace.export_path),
            )
            try:
                result.update(
                    export_stage_trace_jsonl(
                        output_path=output_path,
                        query=query,
                        repo=repo,
                        root=root,
                        started_at=started_at,
                        total_ms=total_ms,
                        stage_metrics=stage_metrics,
                        pipeline_order=list(self.PIPELINE_ORDER),
                        plugin_policy_summary=plugin_policy_summary,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "trace.export.error",
                    extra={
                        "path": str(output_path),
                        "error": str(exc),
                    },
                )
                result.update(
                    {
                        "exported": False,
                        "path": str(output_path),
                        "error": str(exc),
                    }
                )

        if self._config.trace.otlp_enabled:
            endpoint = str(self._config.trace.otlp_endpoint)
            resolved_endpoint = endpoint
            if endpoint.startswith("file://"):
                raw_path = endpoint.replace("file://", "", 1)
                candidate = Path(raw_path)
                if not candidate.is_absolute():
                    resolved = self._resolve_repo_relative_path(
                        root=root,
                        configured_path=raw_path,
                    )
                    resolved_endpoint = f"file://{resolved}"
            elif endpoint and not endpoint.startswith(("http://", "https://")):
                resolved_endpoint = str(
                    self._resolve_repo_relative_path(root=root, configured_path=endpoint)
                )

            try:
                otlp_result = export_stage_trace_otlp(
                    endpoint=resolved_endpoint,
                    query=query,
                    repo=repo,
                    root=root,
                    started_at=started_at,
                    total_ms=total_ms,
                    stage_metrics=stage_metrics,
                    pipeline_order=list(self.PIPELINE_ORDER),
                    plugin_policy_summary=plugin_policy_summary,
                    timeout_seconds=self._config.trace.otlp_timeout_seconds,
                )
                result["otlp"] = otlp_result
                if not self._config.trace.export_enabled:
                    result["exported"] = bool(otlp_result.get("exported", False))
                    result["trace_id"] = otlp_result.get("trace_id", "")
                    result["otel_trace_id"] = otlp_result.get("otel_trace_id", "")
                    result["span_count"] = int(otlp_result.get("span_count", 0) or 0)
                    result["format"] = "otlp"
            except Exception as exc:
                logger.warning(
                    "trace.otlp.export.error",
                    extra={
                        "endpoint": str(resolved_endpoint),
                        "error": str(exc),
                    },
                )
                result["otlp"] = {
                    "enabled": True,
                    "exported": False,
                    "endpoint": str(resolved_endpoint),
                    "error": str(exc),
                }

        return result

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
        invocation_seed = "|".join(
            (
                repo,
                root,
                query,
                started_at.astimezone(timezone.utc).isoformat(),
            )
        )
        invocation_id = hashlib.sha256(invocation_seed.encode("utf-8")).hexdigest()[:24]
        degraded_reason_codes = self._collect_durable_stats_reasons(
            stage_metrics=stage_metrics,
            contract_error=contract_error,
            replay_cache_info=replay_cache_info,
            trace_export=trace_export,
        )
        status = "succeeded"
        if contract_error is not None:
            status = "failed"
        elif degraded_reason_codes:
            status = "degraded"
        try:
            store = self._durable_stats_store_factory()
            store.record_invocation(
                RuntimeInvocationStats(
                    invocation_id=invocation_id,
                    session_id=self._durable_stats_session_id,
                    repo_key=repo,
                    status=status,
                    total_latency_ms=round(float(total_ms), 6),
                    started_at=started_at.astimezone(timezone.utc).isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    contract_error_code=contract_error.error_code
                    if contract_error is not None
                    else "",
                    degraded_reason_codes=tuple(degraded_reason_codes),
                    stage_latencies=tuple(
                        {"stage_name": item.stage, "elapsed_ms": item.elapsed_ms}
                        for item in stage_metrics
                    )
                    + (
                        {"stage_name": "total", "elapsed_ms": round(float(total_ms), 6)},
                    ),
                    plan_replay_hit=bool((replay_cache_info or {}).get("hit", False)),
                    plan_replay_safe_hit=bool(
                        (replay_cache_info or {}).get("safe_hit", False)
                    ),
                    plan_replay_store_written=bool(
                        (replay_cache_info or {}).get("stored", False)
                    ),
                    trace_exported=bool(trace_export.get("exported", False)),
                    trace_export_failed=bool(
                        trace_export.get("enabled", False)
                        and not trace_export.get("exported", False)
                    ),
                )
            )
            return {
                "enabled": True,
                "recorded": True,
                "session_id": self._durable_stats_session_id,
                "invocation_id": invocation_id,
                "status": status,
                "db_path": str(getattr(store, "db_path", "")),
            }
        except Exception as exc:
            logger.warning(
                "durable.stats.record.error",
                extra={"repo": repo, "error": str(exc)},
            )
            return {
                "enabled": True,
                "recorded": False,
                "session_id": self._durable_stats_session_id,
                "invocation_id": invocation_id,
                "status": status,
                "error": str(exc),
            }

    @staticmethod
    def _collect_durable_stats_reasons(
        *,
        stage_metrics: list[StageMetric],
        contract_error: StageContractError | None,
        replay_cache_info: dict[str, Any] | None,
        trace_export: dict[str, Any],
    ) -> list[str]:
        reasons: set[str] = set()
        if contract_error is not None:
            reasons.add("contract_error")
        replay_reason = str((replay_cache_info or {}).get("reason") or "").strip().lower()
        if replay_reason == "invalid_cached_payload":
            reasons.add("plan_replay_invalid_cached_payload")
        if replay_reason == "store_failed":
            reasons.add("plan_replay_store_failed")
        if trace_export.get("enabled", False) and not trace_export.get("exported", False):
            reasons.add("trace_export_failed")
        for metric in stage_metrics:
            tags = metric.tags if isinstance(metric.tags, dict) else {}
            if metric.stage == "memory":
                if bool(tags.get("fallback", False)):
                    reasons.add("memory_fallback")
                if bool(tags.get("memory_namespace_fallback", False)):
                    reasons.add("memory_namespace_fallback")
            if metric.stage == "index":
                if bool(tags.get("candidate_ranker_fallback", False)):
                    reasons.add("candidate_ranker_fallback")
                if bool(tags.get("embedding_time_budget_exceeded", False)):
                    reasons.add("embedding_time_budget_exceeded")
                if bool(tags.get("embedding_fallback", False)):
                    reasons.add("embedding_fallback")
                if bool(tags.get("chunk_semantic_time_budget_exceeded", False)):
                    reasons.add("chunk_semantic_time_budget_exceeded")
                if bool(tags.get("chunk_semantic_fallback", False)):
                    reasons.add("chunk_semantic_fallback")
                if bool(tags.get("parallel_docs_timed_out", False)):
                    reasons.add("parallel_docs_timeout")
                if bool(tags.get("parallel_worktree_timed_out", False)):
                    reasons.add("parallel_worktree_timeout")
                if bool(tags.get("router_fallback_applied", False)):
                    reasons.add("router_fallback_applied")
            if metric.stage == "augment" and bool(tags.get("xref_budget_exhausted", False)):
                reasons.add("xref_budget_exhausted")
            if int(tags.get("slot_policy_blocked", 0) or 0) > 0:
                reasons.add("plugin_policy_blocked")
            if int(tags.get("slot_policy_warn", 0) or 0) > 0:
                reasons.add("plugin_policy_warn")
        return sorted(reasons)

    def _estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text, model=self._tokenizer_model)

    @staticmethod
    def _normalize_namespace_component(*, value: str, fallback: str) -> str:
        normalized = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower())
        normalized = normalized.strip("-")
        return normalized or fallback

    def _resolve_memory_namespace(
        self,
        *,
        repo: str,
        root: str,
    ) -> tuple[str | None, str, str]:
        explicit_tag = self._config.memory.namespace.container_tag
        if explicit_tag:
            return explicit_tag, "explicit", "explicit"

        mode = self._config.memory.namespace.auto_tag_mode
        if mode == "repo":
            repo_name = str(repo or "").strip() or Path(root or ".").name
            return (
                f"repo:{self._normalize_namespace_component(value=repo_name, fallback='repo')}",
                "repo",
                "auto",
            )
        if mode == "user":
            import getpass

            try:
                user_name = getpass.getuser()
            except Exception:
                user_name = ""
            return (
                f"user:{self._normalize_namespace_component(value=user_name, fallback='local')}",
                "user",
                "auto",
            )
        if mode == "global":
            return "global", "global", "auto"
        return None, "disabled", "disabled"

    def _resolve_profile_store(self, *, root: str) -> ProfileStore:
        configured = str(self._config.memory.profile.path or "").strip()
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path(root) / path
        return ProfileStore(
            path=path,
            expiry_enabled=self._config.memory.profile.expiry_enabled,
            ttl_days=self._config.memory.profile.ttl_days,
            max_age_days=self._config.memory.profile.max_age_days,
        )

    def _resolve_capture_notes_path(self, *, root: str) -> Path:
        configured = str(self._config.memory.capture.notes_path or "").strip()
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path(root) / path
        return path

    def _capture_memory_signal(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        namespace: str | None,
        matched_keywords: list[str],
    ) -> dict[str, Any]:
        captured_items = 0
        warnings: list[str] = []
        notes_pruned_expired_count = 0

        try:
            store = self._resolve_profile_store(root=root)
            store.add_recent_context(query=query, repo=repo)
            captured_items += 1
        except Exception as exc:
            warnings.append(f"profile_recent_context_error:{exc.__class__.__name__}")

        try:
            notes_path = self._resolve_capture_notes_path(root=root)
            notes_captured_items, notes_pruned_expired_count = append_capture_note(
                notes_path=notes_path,
                query=query,
                repo=repo,
                namespace=namespace,
                matched_keywords=matched_keywords,
                expiry_enabled=self._config.memory.notes.expiry_enabled,
                ttl_days=self._config.memory.notes.ttl_days,
                max_age_days=self._config.memory.notes.max_age_days,
            )
            captured_items += notes_captured_items
        except Exception as exc:
            warnings.append(f"notes_append_error:{exc.__class__.__name__}")

        return {
            "enabled": True,
            "triggered": bool(matched_keywords),
            "matched_keywords": matched_keywords,
            "captured_items": captured_items,
            "notes_pruned_expired_count": notes_pruned_expired_count,
            "warning": ";".join(warnings) if warnings else None,
        }

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
            try:
                store = self._resolve_profile_store(root=root)
                profile_payload = store.build_injection(
                    top_n=self._config.memory.profile.top_n,
                    token_budget=self._config.memory.profile.token_budget,
                    tokenizer_model=self._tokenizer_model,
                )
                payload["profile"] = profile_payload
            except Exception as exc:
                logger.warning(
                    "memory.profile.inject.error",
                    extra={"error": str(exc)},
                )
                payload["profile"] = {
                    "enabled": True,
                    "error": str(exc),
                    "facts": [],
                    "selected_count": 0,
                    "selected_est_tokens_total": 0,
                }

        extraction = self._signal_extractor.extract(query)
        capture_enabled = bool(self._config.memory.capture.enabled)
        capture_payload: dict[str, Any] = {
            "enabled": capture_enabled,
            "triggered": False,
            "namespace": container_tag,
            "matched_keywords": [],
            "captured_items": 0,
            "reason": extraction.reason,
            "query_length": extraction.query_length,
            "warning": None,
        }
        if capture_enabled and extraction.triggered:
            capture_payload = {
                **capture_payload,
                **self._capture_memory_signal(
                    query=query,
                    repo=repo,
                    root=root,
                    namespace=container_tag,
                    matched_keywords=list(extraction.matched_keywords),
                ),
                "reason": extraction.reason,
                "query_length": extraction.query_length,
            }
        elif capture_enabled:
            capture_payload["matched_keywords"] = list(extraction.matched_keywords)
        payload["capture"] = capture_payload
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
