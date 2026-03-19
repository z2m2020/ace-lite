from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict


class MemoryProviderKwargs(TypedDict):
    primary: str
    secondary: str
    memory_strategy: str
    memory_hybrid_limit: int
    memory_cache_enabled: bool
    memory_cache_path: str
    memory_cache_ttl_seconds: int
    memory_cache_max_entries: int
    memory_notes_enabled: bool
    memory_notes_path: str
    memory_notes_limit: int
    memory_notes_mode: str
    memory_notes_expiry_enabled: bool
    memory_notes_ttl_days: int
    memory_notes_max_age_days: int
    memory_long_term_enabled: bool
    memory_long_term_path: str
    memory_long_term_top_n: int
    memory_long_term_token_budget: int
    memory_long_term_write_enabled: bool
    memory_long_term_as_of_enabled: bool
    mcp_base_url: str
    rest_base_url: str
    timeout_seconds: float
    user_id: str | None
    app: str | None
    limit: int


class EmbeddingRuntimeKwargs(TypedDict):
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


class RetrievalPolicyRuntimeKwargs(TypedDict):
    retrieval_policy: str
    policy_version: str


class MemoryGatePostprocessRuntimeKwargs(TypedDict):
    memory_gate_enabled: bool
    memory_gate_mode: str
    memory_postprocess_enabled: bool
    memory_postprocess_noise_filter_enabled: bool
    memory_postprocess_length_norm_anchor_chars: int
    memory_postprocess_time_decay_half_life_days: float
    memory_postprocess_hard_min_score: float
    memory_postprocess_diversity_enabled: bool
    memory_postprocess_diversity_similarity_threshold: float


EMBEDDING_RUNTIME_KWARGS_KEYS = frozenset(EmbeddingRuntimeKwargs.__annotations__.keys())
RETRIEVAL_POLICY_RUNTIME_KWARGS_KEYS = frozenset(
    RetrievalPolicyRuntimeKwargs.__annotations__.keys()
)
MEMORY_GATE_POSTPROCESS_RUNTIME_KWARGS_KEYS = frozenset(
    MemoryGatePostprocessRuntimeKwargs.__annotations__.keys()
)


class SharedMemoryRuntimePayload(MemoryGatePostprocessRuntimeKwargs):
    memory_disclosure_mode: str
    memory_preview_max_chars: int
    memory_strategy: str
    memory_timeline_enabled: bool
    memory_container_tag: str | None
    memory_auto_tag_mode: str | None
    memory_profile_enabled: bool
    memory_profile_path: str
    memory_profile_top_n: int
    memory_profile_token_budget: int
    memory_profile_expiry_enabled: bool
    memory_profile_ttl_days: int
    memory_profile_max_age_days: int
    memory_feedback_enabled: bool
    memory_feedback_path: str
    memory_feedback_max_entries: int
    memory_feedback_boost_per_select: float
    memory_feedback_max_boost: float
    memory_feedback_decay_days: float
    memory_long_term_enabled: bool
    memory_long_term_path: str
    memory_long_term_top_n: int
    memory_long_term_token_budget: int
    memory_long_term_write_enabled: bool
    memory_long_term_as_of_enabled: bool
    memory_capture_enabled: bool
    memory_capture_notes_path: str
    memory_capture_min_query_length: int
    memory_capture_keywords: list[str]
    memory_notes_enabled: bool
    memory_notes_path: str
    memory_notes_limit: int
    memory_notes_mode: str
    memory_notes_expiry_enabled: bool
    memory_notes_ttl_days: int
    memory_notes_max_age_days: int


class GroupedRuntimePayload(RetrievalPolicyRuntimeKwargs):
    skills_config: dict[str, Any]
    index_config: dict[str, Any]
    embeddings_config: dict[str, Any]
    adaptive_router_config: dict[str, Any]
    plan_replay_cache_config: dict[str, Any]
    retrieval_config: dict[str, Any]
    repomap_config: dict[str, Any]
    lsp_config: dict[str, Any]
    plugins_config: dict[str, Any]
    chunking_config: dict[str, Any]
    tokenizer_config: dict[str, Any]
    cochange_config: dict[str, Any]
    tests_config: dict[str, Any]
    scip_config: dict[str, Any]
    trace_config: dict[str, Any]


class SharedRuntimePayload(SharedMemoryRuntimePayload, GroupedRuntimePayload):
    pass


class RunPlanOnlyRuntimePayload(EmbeddingRuntimeKwargs):
    memory_config: dict[str, Any]
    junit_xml: Any
    coverage_json: Any
    sbfl_json: Any
    sbfl_metric: str
    scip_enabled: bool
    scip_index_path: str
    scip_provider: str
    scip_generate_fallback: bool
    trace_export_enabled: bool
    trace_export_path: str
    trace_otlp_enabled: bool
    trace_otlp_endpoint: str
    trace_otlp_timeout_seconds: float


class RunPlanRuntimeKwargs(SharedRuntimePayload, RunPlanOnlyRuntimePayload):
    pass


class OrchestratorRuntimeKwargs(SharedRuntimePayload):
    skills_dir: str


SHARED_RUNTIME_PAYLOAD_KEYS = frozenset(
    SharedRuntimePayload.__annotations__.keys()
)


def build_memory_provider_kwargs(
    *,
    primary: str,
    secondary: str,
    memory_strategy: str,
    memory_hybrid_limit: int,
    memory_cache_enabled: bool,
    memory_cache_path: str,
    memory_cache_ttl_seconds: int,
    memory_cache_max_entries: int,
    memory_notes_enabled: bool = False,
    memory_notes_path: str = "context-map/memory_notes.jsonl",
    memory_notes_limit: int = 8,
    memory_notes_mode: str = "supplement",
    memory_notes_expiry_enabled: bool = True,
    memory_notes_ttl_days: int = 90,
    memory_notes_max_age_days: int = 365,
    memory_long_term_enabled: bool = False,
    memory_long_term_path: str = "context-map/long_term_memory.db",
    memory_long_term_top_n: int = 4,
    memory_long_term_token_budget: int = 192,
    memory_long_term_write_enabled: bool = False,
    memory_long_term_as_of_enabled: bool = True,
    mcp_base_url: str,
    rest_base_url: str,
    timeout_seconds: float,
    user_id: str | None,
    app: str | None,
    limit: int,
) -> MemoryProviderKwargs:
    return {
        "primary": str(primary or "").strip().lower() or "none",
        "secondary": str(secondary or "").strip().lower() or "none",
        "memory_strategy": str(memory_strategy or "hybrid").strip().lower() or "hybrid",
        "memory_hybrid_limit": max(1, int(memory_hybrid_limit)),
        "memory_cache_enabled": bool(memory_cache_enabled),
        "memory_cache_path": str(memory_cache_path),
        "memory_cache_ttl_seconds": max(1, int(memory_cache_ttl_seconds)),
        "memory_cache_max_entries": max(16, int(memory_cache_max_entries)),
        "memory_notes_enabled": bool(memory_notes_enabled),
        "memory_notes_path": str(memory_notes_path).strip()
        or "context-map/memory_notes.jsonl",
        "memory_notes_limit": max(1, int(memory_notes_limit)),
        "memory_notes_mode": str(memory_notes_mode or "supplement").strip().lower()
        or "supplement",
        "memory_notes_expiry_enabled": bool(memory_notes_expiry_enabled),
        "memory_notes_ttl_days": max(1, int(memory_notes_ttl_days)),
        "memory_notes_max_age_days": max(1, int(memory_notes_max_age_days)),
        "memory_long_term_enabled": bool(memory_long_term_enabled),
        "memory_long_term_path": str(memory_long_term_path).strip()
        or "context-map/long_term_memory.db",
        "memory_long_term_top_n": max(1, int(memory_long_term_top_n)),
        "memory_long_term_token_budget": max(1, int(memory_long_term_token_budget)),
        "memory_long_term_write_enabled": bool(memory_long_term_write_enabled),
        "memory_long_term_as_of_enabled": bool(memory_long_term_as_of_enabled),
        "mcp_base_url": str(mcp_base_url),
        "rest_base_url": str(rest_base_url),
        "timeout_seconds": float(timeout_seconds),
        "user_id": user_id,
        "app": app,
        "limit": max(1, int(limit)),
    }


def build_memory_provider_kwargs_from_resolved(
    *,
    resolved: Mapping[str, Any],
    primary: str,
    secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    timeout_seconds: float,
    user_id: str | None,
    app: str | None,
    limit: int,
) -> MemoryProviderKwargs:
    return build_memory_provider_kwargs(
        primary=primary,
        secondary=secondary,
        memory_strategy=str(resolved["memory_strategy"]).strip().lower(),
        memory_hybrid_limit=max(1, int(resolved["memory_hybrid_limit"])),
        memory_cache_enabled=bool(resolved["memory_cache_enabled"]),
        memory_cache_path=str(resolved["memory_cache_path"]),
        memory_cache_ttl_seconds=max(1, int(resolved["memory_cache_ttl_seconds"])),
        memory_cache_max_entries=max(16, int(resolved["memory_cache_max_entries"])),
        memory_notes_enabled=bool(resolved["memory_notes_enabled"]),
        memory_notes_path=str(resolved["memory_notes_path"]).strip()
        or "context-map/memory_notes.jsonl",
        memory_notes_limit=max(1, int(resolved["memory_notes_limit"])),
        memory_notes_mode=str(resolved["memory_notes_mode"]).strip().lower()
        or "supplement",
        memory_notes_expiry_enabled=bool(resolved["memory_notes_expiry_enabled"]),
        memory_notes_ttl_days=max(1, int(resolved["memory_notes_ttl_days"])),
        memory_notes_max_age_days=max(1, int(resolved["memory_notes_max_age_days"])),
        memory_long_term_enabled=bool(resolved.get("memory_long_term_enabled", False)),
        memory_long_term_path=str(
            resolved.get("memory_long_term_path", "context-map/long_term_memory.db")
        ).strip()
        or "context-map/long_term_memory.db",
        memory_long_term_top_n=max(
            1,
            int(resolved.get("memory_long_term_top_n", 4)),
        ),
        memory_long_term_token_budget=max(
            1,
            int(resolved.get("memory_long_term_token_budget", 192)),
        ),
        memory_long_term_write_enabled=bool(
            resolved.get("memory_long_term_write_enabled", False)
        ),
        memory_long_term_as_of_enabled=bool(
            resolved.get("memory_long_term_as_of_enabled", True)
        ),
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        timeout_seconds=timeout_seconds,
        user_id=user_id,
        app=app,
        limit=limit,
    )


def _build_shared_memory_runtime_payload(
    resolved: Mapping[str, Any],
) -> SharedMemoryRuntimePayload:
    return {
        "memory_disclosure_mode": str(resolved["memory_disclosure_mode"])
        .strip()
        .lower(),
        "memory_preview_max_chars": max(32, int(resolved["memory_preview_max_chars"])),
        "memory_strategy": str(resolved["memory_strategy"]).strip().lower(),
        "memory_gate_enabled": bool(resolved["memory_gate_enabled"]),
        "memory_gate_mode": str(resolved["memory_gate_mode"]).strip().lower() or "auto",
        "memory_timeline_enabled": bool(resolved["memory_timeline_enabled"]),
        "memory_container_tag": resolved["memory_container_tag"],
        "memory_auto_tag_mode": resolved["memory_auto_tag_mode"],
        "memory_profile_enabled": bool(resolved["memory_profile_enabled"]),
        "memory_profile_path": str(resolved["memory_profile_path"]).strip()
        or "~/.ace-lite/profile.json",
        "memory_profile_top_n": max(1, int(resolved["memory_profile_top_n"])),
        "memory_profile_token_budget": max(
            1,
            int(resolved["memory_profile_token_budget"]),
        ),
        "memory_profile_expiry_enabled": bool(resolved["memory_profile_expiry_enabled"]),
        "memory_profile_ttl_days": max(1, int(resolved["memory_profile_ttl_days"])),
        "memory_profile_max_age_days": max(
            1,
            int(resolved["memory_profile_max_age_days"]),
        ),
        "memory_feedback_enabled": bool(resolved["memory_feedback_enabled"]),
        "memory_feedback_path": str(resolved["memory_feedback_path"]).strip()
        or "~/.ace-lite/profile.json",
        "memory_feedback_max_entries": max(
            0,
            int(resolved["memory_feedback_max_entries"]),
        ),
        "memory_feedback_boost_per_select": max(
            0.0,
            float(resolved["memory_feedback_boost_per_select"]),
        ),
        "memory_feedback_max_boost": max(
            0.0,
            float(resolved["memory_feedback_max_boost"]),
        ),
        "memory_feedback_decay_days": max(
            0.0,
            float(resolved["memory_feedback_decay_days"]),
        ),
        "memory_long_term_enabled": bool(
            resolved.get("memory_long_term_enabled", False)
        ),
        "memory_long_term_path": str(
            resolved.get("memory_long_term_path", "context-map/long_term_memory.db")
        ).strip()
        or "context-map/long_term_memory.db",
        "memory_long_term_top_n": max(
            1,
            int(resolved.get("memory_long_term_top_n", 4)),
        ),
        "memory_long_term_token_budget": max(
            1,
            int(resolved.get("memory_long_term_token_budget", 192)),
        ),
        "memory_long_term_write_enabled": bool(
            resolved.get("memory_long_term_write_enabled", False)
        ),
        "memory_long_term_as_of_enabled": bool(
            resolved.get("memory_long_term_as_of_enabled", True)
        ),
        "memory_capture_enabled": bool(resolved["memory_capture_enabled"]),
        "memory_capture_notes_path": str(resolved["memory_capture_notes_path"])
        .strip()
        or "context-map/memory_notes.jsonl",
        "memory_capture_min_query_length": max(
            1,
            int(resolved["memory_capture_min_query_length"]),
        ),
        "memory_capture_keywords": list(resolved["memory_capture_keywords"]),
        "memory_notes_enabled": bool(resolved["memory_notes_enabled"]),
        "memory_notes_path": str(resolved["memory_notes_path"]).strip()
        or "context-map/memory_notes.jsonl",
        "memory_notes_limit": max(1, int(resolved["memory_notes_limit"])),
        "memory_notes_mode": str(resolved["memory_notes_mode"]).strip().lower()
        or "supplement",
        "memory_notes_expiry_enabled": bool(resolved["memory_notes_expiry_enabled"]),
        "memory_notes_ttl_days": max(1, int(resolved["memory_notes_ttl_days"])),
        "memory_notes_max_age_days": max(
            1,
            int(resolved["memory_notes_max_age_days"]),
        ),
        "memory_postprocess_enabled": bool(resolved["memory_postprocess_enabled"]),
        "memory_postprocess_noise_filter_enabled": bool(
            resolved["memory_postprocess_noise_filter_enabled"]
        ),
        "memory_postprocess_length_norm_anchor_chars": max(
            1,
            int(resolved["memory_postprocess_length_norm_anchor_chars"]),
        ),
        "memory_postprocess_time_decay_half_life_days": max(
            0.0,
            float(resolved["memory_postprocess_time_decay_half_life_days"]),
        ),
        "memory_postprocess_hard_min_score": max(
            0.0,
            float(resolved["memory_postprocess_hard_min_score"]),
        ),
        "memory_postprocess_diversity_enabled": bool(
            resolved["memory_postprocess_diversity_enabled"]
        ),
        "memory_postprocess_diversity_similarity_threshold": max(
            0.0,
            min(
                1.0,
                float(resolved["memory_postprocess_diversity_similarity_threshold"]),
            ),
        ),
    }


def _build_grouped_runtime_payload(
    *,
    resolved: Mapping[str, Any],
    skills_dir: str,
    retrieval_policy: str,
) -> GroupedRuntimePayload:
    return {
        "skills_config": {
            "dir": skills_dir,
            **dict(resolved["skills"]),
        },
        "index_config": dict(resolved["index"]),
        "embeddings_config": dict(resolved["embeddings"]),
        "adaptive_router_config": dict(resolved["adaptive_router"]),
        "plan_replay_cache_config": dict(resolved["plan_replay_cache"]),
        "retrieval_config": dict(resolved["retrieval"]),
        "repomap_config": dict(resolved["repomap"]),
        "lsp_config": dict(resolved["lsp"]),
        "plugins_config": dict(resolved["plugins"]),
        "chunking_config": dict(resolved["chunk"]),
        "tokenizer_config": dict(resolved["tokenizer"]),
        "cochange_config": dict(resolved["cochange"]),
        "retrieval_policy": retrieval_policy,
        "policy_version": str(resolved["policy_version"]),
        "tests_config": dict(resolved["tests"]),
        "scip_config": dict(resolved["scip"]),
        "trace_config": dict(resolved["trace"]),
    }


def _build_shared_runtime_payload(
    *,
    resolved: Mapping[str, Any],
    skills_dir: str,
    retrieval_policy: str,
) -> SharedRuntimePayload:
    return {
        **_build_shared_memory_runtime_payload(resolved),
        **_build_grouped_runtime_payload(
            resolved=resolved,
            skills_dir=skills_dir,
            retrieval_policy=retrieval_policy,
        ),
    }


def _build_run_plan_only_runtime_payload(
    resolved: Mapping[str, Any],
) -> RunPlanOnlyRuntimePayload:
    return {
        "memory_config": dict(resolved["memory"]),
        "embedding_enabled": bool(resolved["embedding_enabled"]),
        "embedding_provider": str(resolved["embedding_provider"]),
        "embedding_model": str(resolved["embedding_model"]),
        "embedding_dimension": max(1, int(resolved["embedding_dimension"])),
        "embedding_index_path": str(resolved["embedding_index_path"]),
        "embedding_rerank_pool": max(1, int(resolved["embedding_rerank_pool"])),
        "embedding_lexical_weight": float(resolved["embedding_lexical_weight"]),
        "embedding_semantic_weight": float(resolved["embedding_semantic_weight"]),
        "embedding_min_similarity": float(resolved["embedding_min_similarity"]),
        "embedding_fail_open": bool(resolved["embedding_fail_open"]),
        "junit_xml": resolved["junit_xml"],
        "coverage_json": resolved["coverage_json"],
        "sbfl_json": resolved["sbfl_json"],
        "sbfl_metric": str(resolved["sbfl_metric"]),
        "scip_enabled": bool(resolved["scip_enabled"]),
        "scip_index_path": str(resolved["scip_index_path"]),
        "scip_provider": str(resolved["scip_provider"]),
        "scip_generate_fallback": bool(resolved["scip_generate_fallback"]),
        "trace_export_enabled": bool(resolved["trace_export_enabled"]),
        "trace_export_path": str(resolved["trace_export_path"]),
        "trace_otlp_enabled": bool(resolved["trace_otlp_enabled"]),
        "trace_otlp_endpoint": str(resolved["trace_otlp_endpoint"]),
        "trace_otlp_timeout_seconds": float(resolved["trace_otlp_timeout_seconds"]),
    }


def build_run_plan_kwargs_from_resolved(
    *,
    resolved: Mapping[str, Any],
    skills_dir: str,
    retrieval_policy: str,
) -> RunPlanRuntimeKwargs:
    return {
        **_build_shared_runtime_payload(
            resolved=resolved,
            skills_dir=skills_dir,
            retrieval_policy=retrieval_policy,
        ),
        **_build_run_plan_only_runtime_payload(resolved),
    }


def build_orchestrator_kwargs_from_resolved(
    *,
    resolved: Mapping[str, Any],
    skills_dir: str,
    retrieval_policy: str,
) -> OrchestratorRuntimeKwargs:
    return {
        **_build_shared_runtime_payload(
            resolved=resolved,
            skills_dir=skills_dir,
            retrieval_policy=retrieval_policy,
        ),
        "skills_dir": skills_dir,
    }


__all__ = [
    "build_memory_provider_kwargs",
    "build_memory_provider_kwargs_from_resolved",
    "build_orchestrator_kwargs_from_resolved",
    "build_run_plan_kwargs_from_resolved",
    "MemoryProviderKwargs",
    "EmbeddingRuntimeKwargs",
    "RetrievalPolicyRuntimeKwargs",
    "MemoryGatePostprocessRuntimeKwargs",
    "OrchestratorRuntimeKwargs",
    "RunPlanRuntimeKwargs",
    "EMBEDDING_RUNTIME_KWARGS_KEYS",
    "RETRIEVAL_POLICY_RUNTIME_KWARGS_KEYS",
    "MEMORY_GATE_POSTPROCESS_RUNTIME_KWARGS_KEYS",
    "SHARED_RUNTIME_PAYLOAD_KEYS",
]
