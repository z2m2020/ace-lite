from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.orchestrator_replay import (
    build_augment_replay_fingerprint,
    build_index_replay_fingerprint,
    build_memory_replay_fingerprint,
    build_orchestrator_plan_replay_key,
    build_repo_inputs_replay_fingerprint,
    build_repomap_replay_fingerprint,
    build_skills_replay_fingerprint,
)
from ace_lite.pipeline.contracts import validate_stage_output
from ace_lite.plan_replay_cache import (
    default_plan_replay_cache_path,
    load_cached_plan_with_meta,
    normalize_plan_query,
    store_cached_plan,
)


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class SourcePlanReplayService:
    config: Any
    plan_replay_stage: str
    plan_replay_mode: str
    plan_replay_guarded_by: tuple[str, ...]
    resolve_repo_relative_path_fn: Callable[..., Path]

    def resolve_plan_replay_cache_path(self, *, root: str) -> Path:
        configured = str(self.config.plan_replay_cache.cache_path or "").strip()
        if not configured:
            return Path(default_plan_replay_cache_path(root=root))
        return Path(
            self.resolve_repo_relative_path_fn(
                root=root,
                configured_path=configured,
            )
        )

    def extract_source_plan_failure_signal_summary(
        self,
        source_plan_stage: Any,
    ) -> dict[str, Any]:
        default_summary = {
            "status": "skipped",
            "issue_count": 0,
            "probe_status": "disabled",
            "probe_issue_count": 0,
            "probe_executed_count": 0,
            "selected_test_count": 0,
            "executed_test_count": 0,
            "has_failure": False,
            "source": "source_plan",
        }
        if not isinstance(source_plan_stage, dict):
            return dict(default_summary)

        summary = _coerce_mapping(source_plan_stage.get("failure_signal_summary"))
        if not summary:
            steps = _coerce_list(source_plan_stage.get("steps"))
            validate_step = next(
                (
                    item
                    for item in steps
                    if isinstance(item, dict)
                    and str(item.get("stage") or "").strip() == "validate"
                ),
                {},
            )
            validate_step_payload = _coerce_mapping(validate_step)
            feedback_summary = _coerce_mapping(
                validate_step_payload.get("validation_feedback_summary")
            )
            summary = dict(feedback_summary) if feedback_summary else {}

        normalized = dict(default_summary)
        normalized.update(summary)
        normalized["has_failure"] = bool(
            str(normalized.get("status") or "").strip().lower()
            in {"failed", "degraded", "timeout"}
            or str(normalized.get("probe_status") or "").strip().lower()
            in {"failed", "degraded", "timeout"}
            or _coerce_int(normalized.get("issue_count", 0)) > 0
            or _coerce_int(normalized.get("probe_issue_count", 0)) > 0
        )
        normalized["source"] = str(normalized.get("source") or "source_plan")
        return normalized

    def default_plan_replay_cache_info(self, *, root: str) -> dict[str, Any]:
        enabled = bool(self.config.plan_replay_cache.enabled)
        return {
            "enabled": enabled,
            "stage": self.plan_replay_stage,
            "mode": self.plan_replay_mode,
            "cache_path": str(self.resolve_plan_replay_cache_path(root=root)),
            "hit": False,
            "safe_hit": False,
            "stale_hit_safe": enabled,
            "stored": False,
            "reused_stages": [],
            "guarded_by": list(self.plan_replay_guarded_by),
            "origin": "none",
            "age_seconds": None,
            "trust_class": "",
            "policy_name": self.plan_replay_stage,
            "failure_signal_summary": self.extract_source_plan_failure_signal_summary(
                {}
            ),
            "reason": "disabled" if not enabled else "not_reached",
        }

    def load_replayed_source_plan(
        self,
        *,
        root: str,
        replay_cache_path: Path,
        replay_cache_key: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        replay_cache_info = self.default_plan_replay_cache_info(root=root)
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
            validate_stage_output(self.plan_replay_stage, cached_source_plan)
        except Exception as exc:
            replay_cache_info["reason"] = "invalid_cached_payload"
            replay_cache_info["load_error"] = str(exc)
            return None, replay_cache_info

        replay_cache_info["hit"] = True
        replay_cache_info["safe_hit"] = True
        replay_cache_info["reused_stages"] = [self.plan_replay_stage]
        replay_cache_info["origin"] = str(cache_metadata.get("origin") or "unknown")
        replay_cache_info["age_seconds"] = cache_metadata.get("age_seconds")
        replay_cache_info["trust_class"] = str(cache_metadata.get("trust_class") or "")
        replay_cache_info["policy_name"] = str(
            cache_metadata.get("policy_name") or self.plan_replay_stage
        )
        replay_cache_info["reason"] = "hit"
        replay_cache_info["failure_signal_summary"] = (
            self.extract_source_plan_failure_signal_summary(cached_source_plan)
        )
        return cached_source_plan, replay_cache_info

    def store_source_plan_replay(
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
                "stage": self.plan_replay_stage,
            },
        )
        updated_info["store_ms"] = round(
            (perf_counter() - store_started) * 1000.0,
            3,
        )
        updated_info["stored"] = bool(stored)
        updated_info["origin"] = "stage_artifact_cache"
        updated_info["trust_class"] = "exact"
        updated_info["policy_name"] = self.plan_replay_stage
        updated_info["failure_signal_summary"] = (
            self.extract_source_plan_failure_signal_summary(source_plan_payload)
        )
        if not bool(stored):
            updated_info["reason"] = "store_failed"
        return updated_info

    def build_plan_replay_key(
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
        return str(
            build_orchestrator_plan_replay_key(
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
            retrieval_policy_version=str(self.config.retrieval.policy_version),
            candidate_ranker_default=str(self.config.retrieval.candidate_ranker),
            chunk_disclosure=str(self.config.chunking.disclosure),
            budget_knobs={
                "top_k_files": int(self.config.retrieval.top_k_files),
                "repomap_top_k": int(self.config.repomap.top_k),
                "repomap_neighbor_limit": int(self.config.repomap.neighbor_limit),
                "repomap_budget_tokens": int(self.config.repomap.budget_tokens),
                "skills_top_n": int(self.config.skills.top_n),
                "skills_token_budget": int(self.config.skills.token_budget),
                "precomputed_skills_routing_enabled": bool(
                    self.config.skills.precomputed_routing_enabled
                ),
                "chunk_top_k": int(self.config.chunking.top_k),
                "chunk_per_file_limit": int(self.config.chunking.per_file_limit),
                "chunk_token_budget": int(self.config.chunking.token_budget),
                "lsp_top_n": int(self.config.lsp.top_n),
                "lsp_xref_top_n": int(self.config.lsp.xref_top_n),
            },
            )
        )

    @staticmethod
    def build_memory_replay_fingerprint(*, memory_payload: dict[str, Any]) -> str:
        return str(build_memory_replay_fingerprint(memory_payload=memory_payload))

    @staticmethod
    def build_index_replay_fingerprint(*, index_payload: dict[str, Any]) -> str:
        return str(build_index_replay_fingerprint(index_payload=index_payload))

    @staticmethod
    def build_repomap_replay_fingerprint(*, repomap_payload: dict[str, Any]) -> str:
        return str(build_repomap_replay_fingerprint(repomap_payload=repomap_payload))

    @staticmethod
    def build_repo_inputs_replay_fingerprint(
        *,
        root: str,
        index_payload: dict[str, Any],
        repomap_payload: dict[str, Any],
    ) -> str:
        return str(
            build_repo_inputs_replay_fingerprint(
                root=root,
                index_payload=index_payload,
                repomap_payload=repomap_payload,
            )
        )

    @staticmethod
    def build_augment_replay_fingerprint(*, augment_payload: dict[str, Any]) -> str:
        return str(build_augment_replay_fingerprint(augment_payload=augment_payload))

    @staticmethod
    def build_skills_replay_fingerprint(*, skills_payload: dict[str, Any]) -> str:
        return str(build_skills_replay_fingerprint(skills_payload=skills_payload))


__all__ = ["SourcePlanReplayService"]
