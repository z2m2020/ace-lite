"""Output assembly helpers for benchmark case evaluation."""

from __future__ import annotations

from typing import Any


def build_case_detail_payload(
    *,
    top_candidates: list[Any],
    included_candidate_paths: list[str],
    included_candidate_globs: list[str],
    excluded_candidate_paths: list[str],
    excluded_candidate_globs: list[str],
    relevant_candidate_paths: list[str],
    noise_candidate_paths: list[str],
    candidate_matches: list[dict[str, Any]],
    top_chunks: list[Any],
    expected_hits: list[str],
    chunk_hits: list[str],
    validation_tests: list[Any],
    source_plan_evidence_summary: dict[str, float],
    memory_latency_ms: float,
    index_latency_ms: float,
    repomap_latency_ms: float,
    augment_latency_ms: float,
    skills_latency_ms: float,
    source_plan_latency_ms: float,
    chunk_contract_fallback_count: int,
    chunk_contract_skeleton_chunk_count: int,
    chunk_contract_fallback_ratio: float,
    chunk_contract_skeleton_ratio: float,
    unsupported_language_fallback_count: int,
    unsupported_language_fallback_ratio: float,
    subgraph_payload_enabled: bool,
    subgraph_payload: dict[str, Any],
    subgraph_seed_path_count: int,
    subgraph_edge_type_count: int,
    subgraph_edge_total_count: int,
    subgraph_seed_paths: list[str],
    subgraph_edge_counts: dict[str, Any],
    skills_selected_count: int,
    skills_token_budget: float,
    skills_token_budget_used: float,
    skills_token_budget_utilization_ratio: float,
    skills_budget_exhausted: bool,
    skills_skipped_for_budget_count: int,
    skills_payload: dict[str, Any],
    skills_metadata_only_routing: bool,
    skills_route_latency_ms: float,
    skills_hydration_latency_ms: float,
    plan_replay_cache_enabled: bool,
    plan_replay_cache_hit: bool,
    plan_replay_cache_stale_hit_safe: bool,
    plan_replay_cache_payload: dict[str, Any],
    chunk_stage_miss: dict[str, Any],
    slo_downgrade_signals: list[str],
    parallel_time_budget_ms: float,
    embedding_time_budget_ms: float,
    chunk_semantic_time_budget_ms: float,
    xref_time_budget_ms: float,
    chunk_guard_mode: str,
    chunk_guard_reason: str,
    chunk_guard_candidate_pool: int,
    chunk_guard_signed_chunk_count: int,
    chunk_guard_filtered_count: int,
    chunk_guard_retained_count: int,
    chunk_guard_pairwise_conflict_count: int,
    chunk_guard_pairwise_conflict_density: float,
    chunk_guard_max_conflict_penalty: float,
    chunk_guard_payload: dict[str, Any],
    chunk_guard_report_only: bool,
    chunk_guard_fallback: bool,
    chunk_guard_expectation: dict[str, Any],
    robust_signature_count: int,
    robust_signature_coverage_ratio: float,
    graph_prior_chunk_count: int,
    graph_prior_coverage_ratio: float,
    graph_prior_total: float,
    graph_seeded_chunk_count: int,
    graph_transfer_count: int,
    graph_transfer_per_seed_ratio: float,
    graph_hub_suppressed_chunk_count: int,
    graph_hub_penalty_total: float,
    topological_shield_enabled: bool,
    topological_shield_report_only: bool,
    topological_shield_attenuated_chunk_count: int,
    topological_shield_coverage_ratio: float,
    topological_shield_attenuation_total: float,
    topological_shield_attenuation_per_chunk: float,
    graph_closure_enabled: bool,
    graph_closure_boosted_chunk_count: int,
    graph_closure_coverage_ratio: float,
    graph_closure_anchor_count: int,
    graph_closure_support_edge_count: int,
    graph_closure_total: float,
    source_plan_graph_closure_preference_enabled: bool,
    source_plan_graph_closure_bonus_candidate_count: int,
    source_plan_graph_closure_preferred_count: int,
    source_plan_focused_file_promoted_count: int,
    source_plan_packed_path_count: int,
    source_plan_packed_path_ratio: float,
    source_plan_chunk_retention_ratio: float,
    source_plan_packing_reason: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "candidate_paths": [
            item.get("path") for item in top_candidates if isinstance(item, dict)
        ],
        "relevant_candidate_paths": relevant_candidate_paths,
        "noise_candidate_paths": noise_candidate_paths,
        "candidate_matches": candidate_matches,
        "candidate_chunk_refs": [
            item.get("qualified_name") for item in top_chunks if isinstance(item, dict)
        ],
        "expected_hits": expected_hits,
        "chunk_hits": chunk_hits,
        "validation_tests": [
            str(item).strip() for item in validation_tests if str(item).strip()
        ][:20],
        "source_plan_evidence_summary": source_plan_evidence_summary,
        "stage_latency_ms": {
            "memory": round(memory_latency_ms, 3),
            "index": round(index_latency_ms, 3),
            "repomap": round(repomap_latency_ms, 3),
            "augment": round(augment_latency_ms, 3),
            "skills": round(skills_latency_ms, 3),
            "source_plan": round(source_plan_latency_ms, 3),
        },
        "chunk_contract": {
            "fallback_count": chunk_contract_fallback_count,
            "skeleton_chunk_count": chunk_contract_skeleton_chunk_count,
            "fallback_ratio": round(chunk_contract_fallback_ratio, 6),
            "skeleton_ratio": round(chunk_contract_skeleton_ratio, 6),
            "unsupported_language_fallback_count": unsupported_language_fallback_count,
            "unsupported_language_fallback_ratio": round(
                unsupported_language_fallback_ratio,
                6,
            ),
        },
        "subgraph_payload": {
            "enabled": subgraph_payload_enabled,
            "reason": str(subgraph_payload.get("reason") or ""),
            "seed_path_count": subgraph_seed_path_count,
            "edge_type_count": subgraph_edge_type_count,
            "edge_total_count": subgraph_edge_total_count,
            "seed_paths": [
                str(item).strip() for item in subgraph_seed_paths if str(item).strip()
            ],
            "edge_counts": {
                str(key): max(0, int(value or 0))
                for key, value in subgraph_edge_counts.items()
                if str(key).strip()
            },
        },
        "skills_budget": {
            "selected_count": int(skills_selected_count),
            "token_budget": round(skills_token_budget, 3),
            "token_budget_used": round(skills_token_budget_used, 3),
            "utilization_ratio": round(skills_token_budget_utilization_ratio, 6),
            "budget_exhausted": bool(skills_budget_exhausted),
            "skipped_for_budget_count": int(skills_skipped_for_budget_count),
        },
        "skills_routing": {
            "source": str(skills_payload.get("routing_source") or ""),
            "mode": str(skills_payload.get("routing_mode") or ""),
            "metadata_only_routing": bool(skills_metadata_only_routing),
            "route_latency_ms": round(skills_route_latency_ms, 3),
            "hydration_latency_ms": round(skills_hydration_latency_ms, 3),
            "selected_manifest_token_estimate_total": round(
                float(skills_payload.get("selected_manifest_token_estimate_total", 0.0) or 0.0),
                3,
            ),
            "hydrated_skill_count": int(skills_payload.get("hydrated_skill_count", 0) or 0),
            "hydrated_sections_count": int(
                skills_payload.get("hydrated_sections_count", 0) or 0
            ),
        },
        "plan_replay_cache": {
            "enabled": plan_replay_cache_enabled,
            "hit": plan_replay_cache_hit,
            "stale_hit_safe": plan_replay_cache_stale_hit_safe,
            "stage": str(plan_replay_cache_payload.get("stage", "")),
            "reason": str(plan_replay_cache_payload.get("reason", "")),
            "stored": bool(plan_replay_cache_payload.get("stored", False)),
        },
        "slo_downgrade_signals": slo_downgrade_signals,
        "slo_budget_limits_ms": {
            "parallel_time_budget_ms": round(parallel_time_budget_ms, 3),
            "embedding_time_budget_ms": round(embedding_time_budget_ms, 3),
            "chunk_semantic_time_budget_ms": round(chunk_semantic_time_budget_ms, 3),
            "xref_time_budget_ms": round(xref_time_budget_ms, 3),
        },
        "chunk_guard": {
            "mode": chunk_guard_mode,
            "reason": chunk_guard_reason,
            "candidate_pool": chunk_guard_candidate_pool,
            "signed_chunk_count": chunk_guard_signed_chunk_count,
            "filtered_count": chunk_guard_filtered_count,
            "retained_count": chunk_guard_retained_count,
            "pairwise_conflict_count": chunk_guard_pairwise_conflict_count,
            "pairwise_conflict_density": round(
                chunk_guard_pairwise_conflict_density,
                6,
            ),
            "max_conflict_penalty": round(chunk_guard_max_conflict_penalty, 6),
            "retained_refs": list(chunk_guard_payload.get("retained_refs", []))
            if isinstance(chunk_guard_payload.get("retained_refs"), list)
            else [],
            "filtered_refs": list(chunk_guard_payload.get("filtered_refs", []))
            if isinstance(chunk_guard_payload.get("filtered_refs"), list)
            else [],
            "report_only": chunk_guard_report_only,
            "fallback": chunk_guard_fallback,
        },
        "robust_signature": {
            "count": robust_signature_count,
            "coverage_ratio": round(robust_signature_coverage_ratio, 6),
        },
        "graph_prior": {
            "chunk_count": graph_prior_chunk_count,
            "coverage_ratio": round(graph_prior_coverage_ratio, 6),
            "total": round(graph_prior_total, 6),
            "seeded_chunk_count": graph_seeded_chunk_count,
            "transfer_count": graph_transfer_count,
            "transfer_per_seed_ratio": round(graph_transfer_per_seed_ratio, 6),
            "hub_suppressed_chunk_count": graph_hub_suppressed_chunk_count,
            "hub_penalty_total": round(graph_hub_penalty_total, 6),
        },
        "topological_shield": {
            "enabled": topological_shield_enabled,
            "report_only": topological_shield_report_only,
            "attenuated_chunk_count": topological_shield_attenuated_chunk_count,
            "coverage_ratio": round(topological_shield_coverage_ratio, 6),
            "attenuation_total": round(topological_shield_attenuation_total, 6),
            "attenuation_per_chunk": round(
                topological_shield_attenuation_per_chunk,
                6,
            ),
        },
        "graph_closure": {
            "enabled": graph_closure_enabled,
            "boosted_chunk_count": graph_closure_boosted_chunk_count,
            "coverage_ratio": round(graph_closure_coverage_ratio, 6),
            "anchor_count": graph_closure_anchor_count,
            "support_edge_count": graph_closure_support_edge_count,
            "total": round(graph_closure_total, 6),
        },
        "source_plan_packing": {
            "graph_closure_preference_enabled": (
                source_plan_graph_closure_preference_enabled
            ),
            "graph_closure_bonus_candidate_count": (
                source_plan_graph_closure_bonus_candidate_count
            ),
            "graph_closure_preferred_count": source_plan_graph_closure_preferred_count,
            "focused_file_promoted_count": source_plan_focused_file_promoted_count,
            "packed_path_count": source_plan_packed_path_count,
            "packed_path_ratio": round(source_plan_packed_path_ratio, 6),
            "chunk_retention_ratio": round(source_plan_chunk_retention_ratio, 6),
            "reason": source_plan_packing_reason,
        },
        "year2_normalized_kpis": {
            "skills_token_budget_utilization_ratio": round(
                skills_token_budget_utilization_ratio,
                6,
            ),
            "source_plan_chunk_retention_ratio": round(
                source_plan_chunk_retention_ratio,
                6,
            ),
            "source_plan_packed_path_ratio": round(
                source_plan_packed_path_ratio,
                6,
            ),
            "graph_transfer_per_seed_ratio": round(
                graph_transfer_per_seed_ratio,
                6,
            ),
            "chunk_guard_pairwise_conflict_density": round(
                chunk_guard_pairwise_conflict_density,
                6,
            ),
            "topological_shield_attenuation_per_chunk": round(
                topological_shield_attenuation_per_chunk,
                6,
            ),
        },
    }
    if (
        included_candidate_paths
        or included_candidate_globs
        or excluded_candidate_paths
        or excluded_candidate_globs
    ):
        payload["candidate_path_filters"] = {
            "include_paths": included_candidate_paths,
            "include_globs": included_candidate_globs,
            "exclude_paths": excluded_candidate_paths,
            "exclude_globs": excluded_candidate_globs,
        }
    if chunk_stage_miss["applicable"]:
        payload["chunk_stage_miss_details"] = {
            "oracle_file_path": str(chunk_stage_miss["oracle_file_path"]),
            "oracle_chunk_ref": dict(chunk_stage_miss["oracle_chunk_ref"]),
            "file_present": bool(chunk_stage_miss["file_present"]),
            "raw_chunk_present": bool(chunk_stage_miss["raw_chunk_present"]),
            "source_plan_chunk_present": bool(
                chunk_stage_miss["source_plan_chunk_present"]
            ),
        }
    if chunk_guard_expectation["applicable"]:
        payload["chunk_guard_expectation"] = {
            "scenario": str(chunk_guard_expectation["scenario"]),
            "expected_retained_refs": list(
                chunk_guard_expectation["expected_retained_refs"]
            ),
            "expected_filtered_refs": list(
                chunk_guard_expectation["expected_filtered_refs"]
            ),
            "retained_hits": list(chunk_guard_expectation["retained_hits"]),
            "filtered_hits": list(chunk_guard_expectation["filtered_hits"]),
            "expected_retained_hit": bool(
                chunk_guard_expectation["expected_retained_hit"]
            ),
            "expected_filtered_hit_count": int(
                chunk_guard_expectation["expected_filtered_hit_count"]
            ),
            "expected_filtered_hit_rate": round(
                float(chunk_guard_expectation["expected_filtered_hit_rate"]),
                6,
            ),
            "report_only_improved": bool(
                chunk_guard_expectation["report_only_improved"]
            ),
        }
    return payload


__all__ = ["build_case_detail_payload"]
