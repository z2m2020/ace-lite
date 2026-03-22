from __future__ import annotations

from typing import Any


def _build_multi_channel_granularity_observability(
    multi_channel_fusion_payload: dict[str, Any],
) -> dict[str, float | int]:
    channels = (
        multi_channel_fusion_payload.get("channels", {})
        if isinstance(multi_channel_fusion_payload.get("channels"), dict)
        else {}
    )
    granularity = (
        channels.get("granularity", {})
        if isinstance(channels.get("granularity"), dict)
        else {}
    )
    fused = (
        multi_channel_fusion_payload.get("fused", {})
        if isinstance(multi_channel_fusion_payload.get("fused"), dict)
        else {}
    )
    count = max(0, int(granularity.get("count", 0) or 0))
    pool_size = max(0, int(fused.get("pool_size", 0) or 0))
    pool_ratio = float(count) / float(pool_size) if pool_size > 0 else 0.0
    return {
        "count": count,
        "pool_size": pool_size,
        "pool_ratio": round(pool_ratio, 6),
    }


def _resolve_online_bandit_payload(
    *, adaptive_router_payload: dict[str, Any]
) -> dict[str, Any]:
    online_bandit = adaptive_router_payload.get("online_bandit")
    return online_bandit if isinstance(online_bandit, dict) else {}


def build_candidate_ranking_payload(
    *,
    selection_observability: dict[str, Any],
    embeddings_payload: dict[str, Any],
    exact_search_payload: dict[str, Any],
    docs_payload: dict[str, Any],
    prior_payload: dict[str, Any],
    multi_channel_fusion_payload: dict[str, Any],
    worktree_prior: dict[str, Any],
    graph_lookup_payload: dict[str, Any],
    chunk_semantic_rerank_payload: dict[str, Any],
    chunk_semantic_pool_effective: int,
    chunk_semantic_reranked_count: int,
    chunk_semantic_rerank_ratio: float,
    topological_shield_payload: dict[str, Any],
    feedback_payload: dict[str, Any],
    chunk_guard_payload: dict[str, Any],
    adaptive_router_payload: dict[str, Any],
    second_pass_payload: dict[str, Any],
    refine_pass_payload: dict[str, Any],
) -> dict[str, Any]:
    granularity = _build_multi_channel_granularity_observability(
        multi_channel_fusion_payload
    )
    return {
        **selection_observability,
        "embedding_enabled": bool(embeddings_payload.get("enabled", False)),
        "embedding_fallback": bool(embeddings_payload.get("fallback", False)),
        "embedding_reranked_count": int(
            embeddings_payload.get("reranked_count", 0) or 0
        ),
        "embedding_auto_normalized": bool(
            embeddings_payload.get("auto_normalized", False)
        ),
        "embedding_runtime_model": str(embeddings_payload.get("runtime_model", "")),
        "embedding_runtime_dimension": int(
            embeddings_payload.get("runtime_dimension", 0) or 0
        ),
        "exact_search": exact_search_payload,
        "docs_enabled": bool(docs_payload.get("enabled", False)),
        "docs_section_count": int(docs_payload.get("section_count", 0) or 0),
        "docs_hint_path_count": int(prior_payload.get("docs_hint_paths", 0) or 0),
        "multi_channel_rrf_enabled": bool(
            multi_channel_fusion_payload.get("enabled", False)
        ),
        "multi_channel_rrf_applied": bool(
            multi_channel_fusion_payload.get("applied", False)
        ),
        "multi_channel_rrf_reason": str(
            multi_channel_fusion_payload.get("reason", "")
        ),
        "multi_channel_rrf_k": int(
            multi_channel_fusion_payload.get("rrf_k", 0) or 0
        ),
        "multi_channel_rrf_granularity_count": int(granularity["count"]),
        "multi_channel_rrf_pool_size": int(granularity["pool_size"]),
        "multi_channel_rrf_granularity_pool_ratio": float(granularity["pool_ratio"]),
        "worktree_enabled": bool(worktree_prior.get("enabled", False)),
        "worktree_changed_count": int(worktree_prior.get("changed_count", 0) or 0),
        "worktree_seed_count": len(worktree_prior.get("seed_paths", []))
        if isinstance(worktree_prior.get("seed_paths"), list)
        else 0,
        "worktree_guard_enabled": bool(
            prior_payload.get("worktree_guard_enabled", False)
        ),
        "worktree_guard_applied": bool(
            prior_payload.get("worktree_guard_applied", False)
        ),
        "worktree_guard_reason": str(prior_payload.get("worktree_guard_reason", "")),
        "worktree_guard_filtered_changed_count": int(
            prior_payload.get("worktree_guard_filtered_changed_count", 0) or 0
        ),
        "worktree_guard_filtered_seed_count": int(
            prior_payload.get("worktree_guard_filtered_seed_count", 0) or 0
        ),
        "prior_boosted_count": int(prior_payload.get("boosted_candidate_count", 0) or 0),
        "prior_added_count": int(prior_payload.get("added_candidate_count", 0) or 0),
        "docs_injected_count": int(
            prior_payload.get("docs_injected_candidate_count", 0) or 0
        ),
        "graph_lookup_enabled": bool(graph_lookup_payload.get("enabled", False)),
        "graph_lookup_boosted_count": int(
            graph_lookup_payload.get("boosted_count", 0) or 0
        ),
        "graph_lookup_query_hit_paths": int(
            graph_lookup_payload.get("query_hit_paths", 0) or 0
        ),
        "semantic_time_budget_ms": int(embeddings_payload.get("time_budget_ms", 0) or 0),
        "semantic_time_budget_base_ms": int(
            embeddings_payload.get("time_budget_base_ms", 0) or 0
        ),
        "semantic_time_budget_exceeded": bool(
            embeddings_payload.get("time_budget_exceeded", False)
        ),
        "semantic_adaptive_budget_applied": bool(
            embeddings_payload.get("adaptive_budget_applied", False)
        ),
        "semantic_rerank_pool_effective": int(
            embeddings_payload.get("rerank_pool_effective", 0) or 0
        ),
        "chunk_semantic_rerank_enabled": bool(
            chunk_semantic_rerank_payload.get("enabled", False)
        ),
        "chunk_semantic_rerank_reason": str(
            chunk_semantic_rerank_payload.get("reason", "")
        ),
        "chunk_semantic_rerank_reranked_count": chunk_semantic_reranked_count,
        "chunk_semantic_rerank_pool_effective": chunk_semantic_pool_effective,
        "chunk_semantic_rerank_ratio": float(round(chunk_semantic_rerank_ratio, 6)),
        "chunk_semantic_time_budget_ms": int(
            chunk_semantic_rerank_payload.get("time_budget_ms", 0) or 0
        ),
        "chunk_semantic_time_budget_exceeded": bool(
            chunk_semantic_rerank_payload.get("time_budget_exceeded", False)
        ),
        "chunk_semantic_fallback": bool(
            chunk_semantic_rerank_payload.get("fallback", False)
        ),
        "chunk_semantic_similarity_mean": float(
            chunk_semantic_rerank_payload.get("similarity_mean", 0.0) or 0.0
        ),
        "chunk_semantic_similarity_max": float(
            chunk_semantic_rerank_payload.get("similarity_max", 0.0) or 0.0
        ),
        "topological_shield": topological_shield_payload,
        "feedback_enabled": bool(feedback_payload.get("enabled", False)),
        "feedback_reason": str(feedback_payload.get("reason", "")),
        "feedback_event_count": int(feedback_payload.get("event_count", 0) or 0),
        "feedback_matched_event_count": int(
            feedback_payload.get("matched_event_count", 0) or 0
        ),
        "feedback_boosted_count": int(
            feedback_payload.get("boosted_candidate_count", 0) or 0
        ),
        "feedback_boosted_paths": int(
            feedback_payload.get("boosted_unique_paths", 0) or 0
        ),
        "chunk_guard": chunk_guard_payload,
        "adaptive_router": adaptive_router_payload,
        "second_pass": second_pass_payload,
        "refine_pass": refine_pass_payload,
    }


def build_result_metadata(
    *,
    selection_observability: dict[str, Any],
    multi_channel_fusion_payload: dict[str, Any],
    adaptive_router_payload: dict[str, Any],
    policy_name: str,
    policy_version: str,
    cochange_payload: dict[str, Any],
    chunk_metrics: dict[str, Any],
    chunk_semantic_rerank_payload: dict[str, Any],
    chunk_semantic_pool_effective: int,
    chunk_semantic_rerank_ratio: float,
    topological_shield_payload: dict[str, Any],
    chunk_guard_payload: dict[str, Any],
    docs_payload: dict[str, Any],
    prior_payload: dict[str, Any],
    worktree_prior: dict[str, Any],
    graph_lookup_payload: dict[str, Any],
    embeddings_payload: dict[str, Any],
    feedback_payload: dict[str, Any],
    refine_pass_payload: dict[str, Any],
    second_pass_payload: dict[str, Any],
    selection_fingerprint: str,
    timings_ms: dict[str, Any],
) -> dict[str, Any]:
    online_bandit_payload = _resolve_online_bandit_payload(
        adaptive_router_payload=adaptive_router_payload
    )
    granularity = _build_multi_channel_granularity_observability(
        multi_channel_fusion_payload
    )
    return {
        "candidate_ranker": str(selection_observability["selected"]),
        "candidate_ranker_requested": str(selection_observability["requested"]),
        "candidate_ranker_fallbacks": list(selection_observability["fallbacks"]),
        "candidate_min_score_used": int(selection_observability["min_score_used"]),
        "candidate_fusion_mode": str(selection_observability["fusion_mode"]),
        "candidate_rrf_k": int(selection_observability["rrf_k"]),
        "multi_channel_rrf_enabled": bool(
            multi_channel_fusion_payload.get("enabled", False)
        ),
        "multi_channel_rrf_applied": bool(
            multi_channel_fusion_payload.get("applied", False)
        ),
        "multi_channel_rrf_reason": str(
            multi_channel_fusion_payload.get("reason", "")
        ),
        "multi_channel_rrf_k": int(
            multi_channel_fusion_payload.get("rrf_k", 0) or 0
        ),
        "multi_channel_rrf_granularity_count": int(granularity["count"]),
        "multi_channel_rrf_pool_size": int(granularity["pool_size"]),
        "multi_channel_rrf_granularity_pool_ratio": float(granularity["pool_ratio"]),
        "router_enabled": bool(adaptive_router_payload.get("enabled", False)),
        "router_mode": str(adaptive_router_payload.get("mode", "")),
        "router_model_path": str(adaptive_router_payload.get("model_path", "")),
        "router_state_path": str(adaptive_router_payload.get("state_path", "")),
        "router_arm_set": str(adaptive_router_payload.get("arm_set", "")),
        "router_arm_id": str(adaptive_router_payload.get("arm_id", "")),
        "router_source": str(adaptive_router_payload.get("source", "")),
        "router_confidence": float(adaptive_router_payload.get("confidence", 0.0) or 0.0),
        "router_shadow_arm_id": str(adaptive_router_payload.get("shadow_arm_id", "")),
        "router_shadow_source": str(adaptive_router_payload.get("shadow_source", "")),
        "router_shadow_confidence": float(
            adaptive_router_payload.get("shadow_confidence", 0.0) or 0.0
        ),
        "router_online_bandit_requested": bool(
            online_bandit_payload.get("requested", False)
        ),
        "router_experiment_enabled": bool(
            online_bandit_payload.get("experiment_enabled", False)
        ),
        "router_online_bandit_eligible": bool(
            online_bandit_payload.get("eligible", False)
        ),
        "router_online_bandit_active": bool(
            online_bandit_payload.get("active", False)
        ),
        "router_is_exploration": bool(
            online_bandit_payload.get("is_exploration", False)
        ),
        "router_exploration_probability": float(
            online_bandit_payload.get("exploration_probability", 0.0) or 0.0
        ),
        "router_fallback_applied": bool(
            online_bandit_payload.get("fallback_applied", False)
        ),
        "router_fallback_reason": str(online_bandit_payload.get("fallback_reason", "")),
        "router_online_bandit_reason": str(online_bandit_payload.get("reason", "")),
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
        "cochange_neighbors_added": int(cochange_payload.get("neighbors_added", 0) or 0),
        "chunk_count": int(chunk_metrics.get("candidate_chunk_count", 0) or 0),
        "chunk_semantic_rerank_enabled": bool(
            chunk_semantic_rerank_payload.get("enabled", False)
        ),
        "chunk_semantic_rerank_reason": str(
            chunk_semantic_rerank_payload.get("reason", "")
        ),
        "chunk_semantic_rerank_reranked_count": int(
            chunk_semantic_rerank_payload.get("reranked_count", 0) or 0
        ),
        "chunk_semantic_rerank_pool_effective": chunk_semantic_pool_effective,
        "chunk_semantic_rerank_ratio": float(round(chunk_semantic_rerank_ratio, 6)),
        "chunk_semantic_time_budget_ms": int(
            chunk_semantic_rerank_payload.get("time_budget_ms", 0) or 0
        ),
        "chunk_semantic_time_budget_exceeded": bool(
            chunk_semantic_rerank_payload.get("time_budget_exceeded", False)
        ),
        "chunk_semantic_fallback": bool(
            chunk_semantic_rerank_payload.get("fallback", False)
        ),
        "chunk_semantic_similarity_mean": float(
            chunk_semantic_rerank_payload.get("similarity_mean", 0.0) or 0.0
        ),
        "chunk_semantic_similarity_max": float(
            chunk_semantic_rerank_payload.get("similarity_max", 0.0) or 0.0
        ),
        "topological_shield_enabled": bool(
            topological_shield_payload.get("enabled", False)
        ),
        "topological_shield_mode": str(topological_shield_payload.get("mode", "")),
        "topological_shield_report_only": bool(
            topological_shield_payload.get("report_only", False)
        ),
        "topological_shield_attenuated_chunk_count": int(
            topological_shield_payload.get("attenuated_chunk_count", 0) or 0
        ),
        "topological_shield_coverage_ratio": float(
            topological_shield_payload.get("coverage_ratio", 0.0) or 0.0
        ),
        "topological_shield_attenuation_total": float(
            topological_shield_payload.get("attenuation_total", 0.0) or 0.0
        ),
        "chunk_guard_enabled": bool(chunk_guard_payload.get("enabled", False)),
        "chunk_guard_mode": str(chunk_guard_payload.get("mode", "")),
        "chunk_guard_reason": str(chunk_guard_payload.get("reason", "")),
        "chunk_guard_candidate_pool": int(
            chunk_guard_payload.get("candidate_pool", 0) or 0
        ),
        "chunk_guard_signed_chunk_count": int(
            chunk_guard_payload.get("signed_chunk_count", 0) or 0
        ),
        "chunk_guard_filtered_count": int(
            chunk_guard_payload.get("filtered_count", 0) or 0
        ),
        "chunk_guard_retained_count": int(
            chunk_guard_payload.get("retained_count", 0) or 0
        ),
        "chunk_guard_pairwise_conflict_count": int(
            chunk_guard_payload.get("pairwise_conflict_count", 0) or 0
        ),
        "chunk_guard_max_conflict_penalty": float(
            chunk_guard_payload.get("max_conflict_penalty", 0.0) or 0.0
        ),
        "chunk_guard_report_only": bool(chunk_guard_payload.get("report_only", False)),
        "chunk_guard_fallback": bool(chunk_guard_payload.get("fallback", False)),
        "robust_signature_count": int(
            chunk_metrics.get("robust_signature_count", 0) or 0
        ),
        "robust_signature_coverage_ratio": float(
            chunk_metrics.get("robust_signature_coverage_ratio", 0.0) or 0.0
        ),
        "docs_enabled": bool(docs_payload.get("enabled", False)),
        "docs_section_count": int(docs_payload.get("section_count", 0) or 0),
        "docs_hint_path_count": int(prior_payload.get("docs_hint_paths", 0) or 0),
        "docs_hint_module_count": int(prior_payload.get("docs_hint_modules", 0) or 0),
        "worktree_enabled": bool(worktree_prior.get("enabled", False)),
        "worktree_changed_count": int(worktree_prior.get("changed_count", 0) or 0),
        "worktree_seed_count": len(worktree_prior.get("seed_paths", []))
        if isinstance(worktree_prior.get("seed_paths"), list)
        else 0,
        "worktree_guard_enabled": bool(
            prior_payload.get("worktree_guard_enabled", False)
        ),
        "worktree_guard_applied": bool(
            prior_payload.get("worktree_guard_applied", False)
        ),
        "worktree_guard_reason": str(prior_payload.get("worktree_guard_reason", "")),
        "worktree_guard_filtered_changed_count": int(
            prior_payload.get("worktree_guard_filtered_changed_count", 0) or 0
        ),
        "worktree_guard_filtered_seed_count": int(
            prior_payload.get("worktree_guard_filtered_seed_count", 0) or 0
        ),
        "worktree_state_hash": str(worktree_prior.get("state_hash", "")),
        "prior_boosted_count": int(prior_payload.get("boosted_candidate_count", 0) or 0),
        "prior_added_count": int(prior_payload.get("added_candidate_count", 0) or 0),
        "docs_injected_count": int(
            prior_payload.get("docs_injected_candidate_count", 0) or 0
        ),
        "graph_lookup_enabled": bool(graph_lookup_payload.get("enabled", False)),
        "graph_lookup_boosted_count": int(
            graph_lookup_payload.get("boosted_count", 0) or 0
        ),
        "graph_lookup_query_hit_paths": int(
            graph_lookup_payload.get("query_hit_paths", 0) or 0
        ),
        "embedding_enabled": bool(embeddings_payload.get("enabled", False)),
        "embedding_fallback": bool(embeddings_payload.get("fallback", False)),
        "embedding_reranked_count": int(
            embeddings_payload.get("reranked_count", 0) or 0
        ),
        "embedding_similarity_mean": float(
            embeddings_payload.get("similarity_mean", 0.0) or 0.0
        ),
        "embedding_auto_normalized": bool(
            embeddings_payload.get("auto_normalized", False)
        ),
        "embedding_auto_normalized_fields": list(
            embeddings_payload.get("auto_normalized_fields", [])
        ),
        "embedding_runtime_provider": str(
            embeddings_payload.get("runtime_provider", "")
        ),
        "embedding_runtime_model": str(embeddings_payload.get("runtime_model", "")),
        "embedding_runtime_dimension": int(
            embeddings_payload.get("runtime_dimension", 0) or 0
        ),
        "embedding_time_budget_ms": int(
            embeddings_payload.get("time_budget_ms", 0) or 0
        ),
        "embedding_time_budget_base_ms": int(
            embeddings_payload.get("time_budget_base_ms", 0) or 0
        ),
        "embedding_time_budget_exceeded": bool(
            embeddings_payload.get("time_budget_exceeded", False)
        ),
        "embedding_adaptive_budget_applied": bool(
            embeddings_payload.get("adaptive_budget_applied", False)
        ),
        "embedding_rerank_pool_effective": int(
            embeddings_payload.get("rerank_pool_effective", 0) or 0
        ),
        "feedback_enabled": bool(feedback_payload.get("enabled", False)),
        "feedback_reason": str(feedback_payload.get("reason", "")),
        "feedback_boosted_count": int(
            feedback_payload.get("boosted_candidate_count", 0) or 0
        ),
        "refine_pass_enabled": bool(refine_pass_payload.get("enabled", False)),
        "refine_pass_trigger_condition_met": bool(
            refine_pass_payload.get("trigger_condition_met", False)
        ),
        "refine_pass_triggered": bool(refine_pass_payload.get("triggered", False)),
        "refine_pass_applied": bool(refine_pass_payload.get("applied", False)),
        "refine_pass_reason": str(refine_pass_payload.get("reason", "")),
        "refine_pass_retry_ranker": str(refine_pass_payload.get("retry_ranker", "")),
        "second_pass_triggered": bool(second_pass_payload.get("triggered", False)),
        "second_pass_applied": bool(second_pass_payload.get("applied", False)),
        "second_pass_reason": str(second_pass_payload.get("reason", "")),
        "second_pass_retry_ranker": str(
            second_pass_payload.get("retry_ranker", "")
        ),
        "selection_fingerprint": str(selection_fingerprint),
        "timings_ms": timings_ms,
    }


__all__ = [
    "build_candidate_ranking_payload",
    "build_result_metadata",
]
