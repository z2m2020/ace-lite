"""Base row assembly helpers for benchmark case evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ace_lite.benchmark.case_contracts import derive_benchmark_case_dev_feedback


def _normalize_timestamp(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _time_delta_hours(*, start: Any, end: Any) -> float:
    start_normalized = _normalize_timestamp(start)
    end_normalized = _normalize_timestamp(end)
    if not start_normalized or not end_normalized:
        return 0.0
    try:
        start_dt = datetime.fromisoformat(start_normalized)
        end_dt = datetime.fromisoformat(end_normalized)
    except ValueError:
        return 0.0
    delta_seconds = (end_dt - start_dt).total_seconds()
    if delta_seconds <= 0.0:
        return 0.0
    return float(delta_seconds) / 3600.0


def build_case_evaluation_row(
    *,
    case: dict[str, Any],
    expected: list[str],
    top_k: int,
    recall_hit: float,
    precision: float,
    first_hit_rank: int | None,
    hit_at_1: float,
    reciprocal_rank: float,
    utility: float,
    task_success_hit: float,
    task_success_config: dict[str, Any],
    task_success_failed_checks: list[str],
    noise: float,
    dependency_recall: float,
    memory_latency_ms: float,
    index_latency_ms: float,
    repomap_latency_ms: float,
    repomap_worktree_seed_count: int,
    repomap_subgraph_seed_count: int,
    repomap_seed_candidates_count: int,
    repomap_cache_hit: bool,
    repomap_precompute_hit: bool,
    augment_latency_ms: float,
    skills_latency_ms: float,
    source_plan_latency_ms: float,
    latency_ms: float,
    chunk_hit_at_k: float,
    chunks_per_file_mean: float,
    chunk_budget_used: float,
    retrieval_context_chunk_count: int,
    retrieval_context_coverage_ratio: float,
    retrieval_context_char_count_mean: float,
    contextual_sidecar_parent_symbol_chunk_count: int,
    contextual_sidecar_parent_symbol_coverage_ratio: float,
    contextual_sidecar_reference_hint_chunk_count: int,
    contextual_sidecar_reference_hint_coverage_ratio: float,
    retrieval_context_pool_chunk_count: int,
    retrieval_context_pool_coverage_ratio: float,
    chunk_contract_fallback_count: int,
    chunk_contract_skeleton_chunk_count: int,
    chunk_contract_fallback_ratio: float,
    chunk_contract_skeleton_ratio: float,
    unsupported_language_fallback_count: int,
    unsupported_language_fallback_ratio: float,
    subgraph_payload_enabled: bool,
    subgraph_seed_path_count: int,
    subgraph_edge_type_count: int,
    subgraph_edge_total_count: int,
    robust_signature_count: int,
    robust_signature_coverage_ratio: float,
    graph_prior_chunk_count: int,
    graph_prior_coverage_ratio: float,
    graph_prior_total: float,
    graph_seeded_chunk_count: int,
    graph_transfer_count: int,
    graph_hub_suppressed_chunk_count: int,
    graph_hub_penalty_total: float,
    graph_closure_enabled: bool,
    graph_closure_boosted_chunk_count: int,
    graph_closure_coverage_ratio: float,
    graph_closure_anchor_count: int,
    graph_closure_support_edge_count: int,
    graph_closure_total: float,
    topological_shield_enabled: bool,
    topological_shield_report_only: bool,
    topological_shield_attenuated_chunk_count: int,
    topological_shield_coverage_ratio: float,
    topological_shield_attenuation_total: float,
    topological_shield_attenuation_per_chunk: float,
    skills_selected_count: float,
    skills_token_budget: float,
    skills_token_budget_used: float,
    skills_token_budget_utilization_ratio: float,
    skills_budget_exhausted: bool,
    skills_skipped_for_budget_count: float,
    skills_route_latency_ms: float,
    skills_hydration_latency_ms: float,
    skills_metadata_only_routing: bool,
    skills_precomputed_route: bool,
    plan_replay_cache_enabled: bool,
    plan_replay_cache_hit: bool,
    plan_replay_cache_stale_hit_safe: bool,
    chunk_stage_miss: dict[str, Any],
    validation_tests: list[Any],
    validation_probe_enabled: bool,
    validation_probe_status: str,
    validation_probe_executed_count: int,
    validation_probe_issue_count: int,
    source_plan_validation_feedback_present: bool,
    source_plan_validation_feedback_status: str,
    source_plan_validation_feedback_issue_count: int,
    source_plan_validation_feedback_probe_status: str,
    source_plan_validation_feedback_probe_issue_count: int,
    source_plan_validation_feedback_probe_executed_count: int,
    source_plan_validation_feedback_selected_test_count: int,
    source_plan_validation_feedback_executed_test_count: int,
    source_plan_evidence_summary: dict[str, float],
    source_plan_graph_closure_preference_enabled: bool,
    source_plan_graph_closure_bonus_candidate_count: int,
    source_plan_graph_closure_preferred_count: int,
    source_plan_granularity_preferred_count: int,
    source_plan_focused_file_promoted_count: int,
    source_plan_packed_path_count: int,
    source_plan_chunk_retention_ratio: float,
    source_plan_packed_path_ratio: float,
    notes_hit_ratio: float,
    profile_selected_count: int,
    capture_triggered: bool,
    ltm_selected_count: int,
    ltm_attribution_count: int,
    ltm_graph_neighbor_count: int,
    ltm_plan_constraint_count: int,
    ltm_attribution_preview: list[str],
    feedback_enabled: bool,
    feedback_reason: str,
    feedback_event_count: int,
    feedback_matched_event_count: int,
    feedback_boosted_count: int,
    feedback_boosted_paths: int,
    multi_channel_rrf_enabled: bool,
    multi_channel_rrf_applied: bool,
    multi_channel_rrf_granularity_count: int,
    multi_channel_rrf_pool_size: int,
    multi_channel_rrf_granularity_pool_ratio: float,
    graph_lookup_enabled: bool,
    graph_lookup_reason: str,
    graph_lookup_guarded: bool,
    graph_lookup_boosted_count: int,
    graph_lookup_weight_scip: float,
    graph_lookup_weight_xref: float,
    graph_lookup_weight_query_xref: float,
    graph_lookup_weight_symbol: float,
    graph_lookup_weight_import: float,
    graph_lookup_weight_coverage: float,
    graph_lookup_candidate_count: int,
    graph_lookup_pool_size: int,
    graph_lookup_query_terms_count: int,
    graph_lookup_normalization: str,
    graph_lookup_guard_max_candidates: int,
    graph_lookup_guard_min_query_terms: int,
    graph_lookup_guard_max_query_terms: int,
    graph_lookup_query_hit_paths: int,
    graph_lookup_scip_signal_paths: int,
    graph_lookup_xref_signal_paths: int,
    graph_lookup_symbol_hit_paths: int,
    graph_lookup_import_hit_paths: int,
    graph_lookup_coverage_hit_paths: int,
    graph_lookup_max_inbound: float,
    graph_lookup_max_xref_count: float,
    graph_lookup_max_query_hits: float,
    graph_lookup_max_symbol_hits: float,
    graph_lookup_max_import_hits: float,
    graph_lookup_max_query_coverage: float,
    graph_lookup_boosted_path_ratio: float,
    graph_lookup_query_hit_path_ratio: float,
    native_scip_loaded: bool,
    native_scip_document_count: int,
    native_scip_definition_occurrence_count: int,
    native_scip_reference_occurrence_count: int,
    native_scip_symbol_definition_count: int,
    policy_profile: str,
    graph_transfer_per_seed_ratio: float,
    router_enabled: bool,
    router_mode: str,
    router_arm_set: str,
    router_arm_id: str,
    router_confidence: float,
    router_shadow_arm_id: str,
    router_shadow_source: str,
    router_shadow_confidence: float,
    router_online_bandit_requested: bool,
    router_experiment_enabled: bool,
    router_online_bandit_active: bool,
    router_is_exploration: bool,
    router_exploration_probability: float,
    router_fallback_applied: bool,
    router_fallback_reason: str,
    router_online_bandit_reason: str,
    docs_enabled_flag: bool,
    docs_hit: float,
    hint_inject: float,
    embedding_enabled: bool,
    embedding_similarity_mean: float,
    embedding_similarity_max: float,
    embedding_rerank_ratio: float,
    embedding_cache_hit: bool,
    embedding_fallback: bool,
    parallel_time_budget_ms: float,
    embedding_time_budget_ms: float,
    chunk_semantic_time_budget_ms: float,
    xref_time_budget_ms: float,
    parallel_docs_timed_out: bool,
    parallel_worktree_timed_out: bool,
    embedding_time_budget_exceeded: bool,
    embedding_adaptive_budget_applied: bool,
    chunk_semantic_time_budget_exceeded: bool,
    chunk_semantic_fallback: bool,
    chunk_guard_enabled: bool,
    chunk_guard_mode: str,
    chunk_guard_reason: str,
    chunk_guard_report_only: bool,
    chunk_guard_filtered_count: int,
    chunk_guard_filter_ratio: float,
    chunk_guard_pairwise_conflict_count: int,
    chunk_guard_pairwise_conflict_density: float,
    chunk_guard_fallback: bool,
    chunk_guard_expectation: dict[str, Any],
    xref_budget_exhausted: bool,
    slo_downgrade_signals: list[str],
    decision_trace: list[dict[str, Any]],
    evidence_insufficiency: dict[str, Any],
) -> dict[str, Any]:
    issue_report_raw = case.get("issue_report")
    issue_report = issue_report_raw if isinstance(issue_report_raw, dict) else {}
    issue_report_issue_id = str(issue_report.get("issue_id") or "").strip()
    issue_report_plan_payload_ref = str(
        issue_report.get("plan_payload_ref") or ""
    ).strip()
    issue_report_status = str(issue_report.get("status") or "").strip()
    issue_report_occurred_at = _normalize_timestamp(issue_report.get("occurred_at"))
    issue_report_resolved_at = _normalize_timestamp(issue_report.get("resolved_at"))
    issue_report_created_at = _normalize_timestamp(issue_report.get("created_at"))
    issue_report_updated_at = _normalize_timestamp(issue_report.get("updated_at"))
    issue_report_resolution_note = str(issue_report.get("resolution_note") or "").strip()
    issue_report_time_to_fix_hours = _time_delta_hours(
        start=issue_report.get("occurred_at") or issue_report.get("created_at"),
        end=issue_report.get("resolved_at"),
    )
    dev_feedback = derive_benchmark_case_dev_feedback(case)
    dev_feedback_issue_count = max(0, int(dev_feedback.get("issue_count", 0) or 0))
    dev_feedback_linked_fix_issue_count = max(
        0, int(dev_feedback.get("linked_fix_issue_count", 0) or 0)
    )
    dev_feedback_resolved_issue_count = max(
        0, int(dev_feedback.get("resolved_issue_count", 0) or 0)
    )
    dev_feedback_created_at = _normalize_timestamp(dev_feedback.get("created_at"))
    dev_feedback_resolved_at = _normalize_timestamp(dev_feedback.get("resolved_at"))
    dev_feedback_issue_time_to_fix_hours = float(
        dev_feedback.get("issue_time_to_fix_hours", 0.0) or 0.0
    )
    if dev_feedback_issue_time_to_fix_hours <= 0.0:
        dev_feedback_issue_time_to_fix_hours = _time_delta_hours(
            start=dev_feedback.get("created_at"),
            end=dev_feedback.get("resolved_at"),
        )
    feedback_surface = str(case.get("feedback_surface") or "").strip()
    retrieval_surface = str(case.get("retrieval_surface") or "").strip()
    deep_symbol_case = retrieval_surface == "deep_symbol"

    return {
        "case_id": case.get("case_id", "unknown"),
        "query": case.get("query", ""),
        "retrieval_surface": retrieval_surface,
        "deep_symbol_case": 1.0 if deep_symbol_case else 0.0,
        "expected_keys": expected,
        "top_k": top_k,
        "recall_hit": recall_hit,
        "precision_at_k": precision,
        "first_hit_rank": first_hit_rank,
        "hit_at_1": hit_at_1,
        "reciprocal_rank": reciprocal_rank,
        "utility_hit": utility,
        "task_success_hit": task_success_hit,
        "task_success_mode": str(task_success_config["mode"]),
        "task_success_failed_checks": task_success_failed_checks,
        "task_success_requirements": {
            "require_recall_hit": bool(task_success_config["require_recall_hit"]),
            "min_validation_tests": int(task_success_config["min_validation_tests"]),
        },
        "noise_rate": noise,
        "dependency_recall": dependency_recall,
        "memory_latency_ms": memory_latency_ms,
        "index_latency_ms": index_latency_ms,
        "repomap_latency_ms": repomap_latency_ms,
        "repomap_worktree_seed_count": float(repomap_worktree_seed_count),
        "repomap_subgraph_seed_count": float(repomap_subgraph_seed_count),
        "repomap_seed_candidates_count": float(repomap_seed_candidates_count),
        "repomap_cache_hit": 1.0 if repomap_cache_hit else 0.0,
        "repomap_precompute_hit": 1.0 if repomap_precompute_hit else 0.0,
        "augment_latency_ms": augment_latency_ms,
        "skills_latency_ms": skills_latency_ms,
        "source_plan_latency_ms": source_plan_latency_ms,
        "latency_ms": latency_ms,
        "chunk_hit_at_k": chunk_hit_at_k,
        "chunks_per_file_mean": chunks_per_file_mean,
        "chunk_budget_used": chunk_budget_used,
        "retrieval_context_chunk_count": float(retrieval_context_chunk_count),
        "retrieval_context_coverage_ratio": retrieval_context_coverage_ratio,
        "retrieval_context_char_count_mean": retrieval_context_char_count_mean,
        "contextual_sidecar_parent_symbol_chunk_count": float(
            contextual_sidecar_parent_symbol_chunk_count
        ),
        "contextual_sidecar_parent_symbol_coverage_ratio": float(
            contextual_sidecar_parent_symbol_coverage_ratio
        ),
        "contextual_sidecar_reference_hint_chunk_count": float(
            contextual_sidecar_reference_hint_chunk_count
        ),
        "contextual_sidecar_reference_hint_coverage_ratio": float(
            contextual_sidecar_reference_hint_coverage_ratio
        ),
        "retrieval_context_pool_chunk_count": float(
            retrieval_context_pool_chunk_count
        ),
        "retrieval_context_pool_coverage_ratio": (
            retrieval_context_pool_coverage_ratio
        ),
        "chunk_contract_fallback_count": float(chunk_contract_fallback_count),
        "chunk_contract_skeleton_chunk_count": float(
            chunk_contract_skeleton_chunk_count
        ),
        "chunk_contract_fallback_ratio": chunk_contract_fallback_ratio,
        "chunk_contract_skeleton_ratio": chunk_contract_skeleton_ratio,
        "unsupported_language_fallback_count": float(
            unsupported_language_fallback_count
        ),
        "unsupported_language_fallback_ratio": unsupported_language_fallback_ratio,
        "subgraph_payload_enabled": 1.0 if subgraph_payload_enabled else 0.0,
        "subgraph_seed_path_count": float(subgraph_seed_path_count),
        "subgraph_edge_type_count": float(subgraph_edge_type_count),
        "subgraph_edge_total_count": float(subgraph_edge_total_count),
        "repomap_seed": {
            "worktree_seed_count": int(repomap_worktree_seed_count),
            "subgraph_seed_count": int(repomap_subgraph_seed_count),
            "seed_candidates_count": int(repomap_seed_candidates_count),
            "cache_hit": bool(repomap_cache_hit),
            "precompute_hit": bool(repomap_precompute_hit),
        },
        "robust_signature_count": float(robust_signature_count),
        "robust_signature_coverage_ratio": robust_signature_coverage_ratio,
        "graph_prior_chunk_count": float(graph_prior_chunk_count),
        "graph_prior_coverage_ratio": float(graph_prior_coverage_ratio),
        "graph_prior_total": float(graph_prior_total),
        "graph_seeded_chunk_count": float(graph_seeded_chunk_count),
        "graph_transfer_count": float(graph_transfer_count),
        "graph_hub_suppressed_chunk_count": float(graph_hub_suppressed_chunk_count),
        "graph_hub_penalty_total": float(graph_hub_penalty_total),
        "graph_closure_enabled": 1.0 if graph_closure_enabled else 0.0,
        "graph_closure_boosted_chunk_count": float(graph_closure_boosted_chunk_count),
        "graph_closure_coverage_ratio": float(graph_closure_coverage_ratio),
        "graph_closure_anchor_count": float(graph_closure_anchor_count),
        "graph_closure_support_edge_count": float(graph_closure_support_edge_count),
        "graph_closure_total": float(graph_closure_total),
        "topological_shield_enabled": 1.0 if topological_shield_enabled else 0.0,
        "topological_shield_report_only": (
            1.0 if topological_shield_report_only else 0.0
        ),
        "topological_shield_attenuated_chunk_count": float(
            topological_shield_attenuated_chunk_count
        ),
        "topological_shield_coverage_ratio": float(
            topological_shield_coverage_ratio
        ),
        "topological_shield_attenuation_total": float(
            topological_shield_attenuation_total
        ),
        "topological_shield_attenuation_per_chunk": (
            topological_shield_attenuation_per_chunk
        ),
        "skills_selected_count": skills_selected_count,
        "skills_token_budget": skills_token_budget,
        "skills_token_budget_used": skills_token_budget_used,
        "skills_token_budget_utilization_ratio": (
            skills_token_budget_utilization_ratio
        ),
        "skills_budget_exhausted": 1.0 if skills_budget_exhausted else 0.0,
        "skills_skipped_for_budget_count": skills_skipped_for_budget_count,
        "skills_route_latency_ms": skills_route_latency_ms,
        "skills_hydration_latency_ms": skills_hydration_latency_ms,
        "skills_metadata_only_routing": (
            1.0 if skills_metadata_only_routing else 0.0
        ),
        "skills_precomputed_route": 1.0 if skills_precomputed_route else 0.0,
        "plan_replay_cache_enabled": 1.0 if plan_replay_cache_enabled else 0.0,
        "plan_replay_cache_hit": 1.0 if plan_replay_cache_hit else 0.0,
        "plan_replay_cache_stale_hit_safe": (
            1.0 if plan_replay_cache_stale_hit_safe else 0.0
        ),
        "chunk_stage_miss_applicable": 1.0 if chunk_stage_miss["applicable"] else 0.0,
        "chunk_stage_miss_classified": 1.0 if chunk_stage_miss["label"] else 0.0,
        "chunk_stage_miss": str(chunk_stage_miss["label"]),
        "validation_test_count": len(validation_tests),
        "validation_probe_enabled": 1.0 if validation_probe_enabled else 0.0,
        "validation_probe_status": str(validation_probe_status or ""),
        "validation_probe_executed_count": float(validation_probe_executed_count),
        "validation_probe_issue_count": float(validation_probe_issue_count),
        "validation_probe_failed": (
            1.0
            if str(validation_probe_status or "").strip().lower() in {"failed", "degraded"}
            or int(validation_probe_issue_count or 0) > 0
            else 0.0
        ),
        "source_plan_validation_feedback_present": (
            1.0 if source_plan_validation_feedback_present else 0.0
        ),
        "source_plan_validation_feedback_status": str(
            source_plan_validation_feedback_status or ""
        ),
        "source_plan_validation_feedback_issue_count": float(
            source_plan_validation_feedback_issue_count
        ),
        "source_plan_validation_feedback_failed": (
            1.0
            if str(source_plan_validation_feedback_status or "").strip().lower()
            in {"failed", "degraded"}
            or int(source_plan_validation_feedback_issue_count or 0) > 0
            else 0.0
        ),
        "source_plan_validation_feedback_probe_status": str(
            source_plan_validation_feedback_probe_status or ""
        ),
        "source_plan_validation_feedback_probe_issue_count": float(
            source_plan_validation_feedback_probe_issue_count
        ),
        "source_plan_validation_feedback_probe_executed_count": float(
            source_plan_validation_feedback_probe_executed_count
        ),
        "source_plan_validation_feedback_probe_failed": (
            1.0
            if str(source_plan_validation_feedback_probe_status or "")
            .strip()
            .lower()
            in {"failed", "degraded"}
            or int(source_plan_validation_feedback_probe_issue_count or 0) > 0
            else 0.0
        ),
        "source_plan_validation_feedback_selected_test_count": float(
            source_plan_validation_feedback_selected_test_count
        ),
        "source_plan_validation_feedback_executed_test_count": float(
            source_plan_validation_feedback_executed_test_count
        ),
        "source_plan_direct_evidence_ratio": float(
            source_plan_evidence_summary.get("direct_ratio", 0.0) or 0.0
        ),
        "source_plan_neighbor_context_ratio": float(
            source_plan_evidence_summary.get("neighbor_context_ratio", 0.0) or 0.0
        ),
        "source_plan_hint_only_ratio": float(
            source_plan_evidence_summary.get("hint_only_ratio", 0.0) or 0.0
        ),
        "source_plan_symbol_count": float(
            source_plan_evidence_summary.get("symbol_count", 0.0) or 0.0
        ),
        "source_plan_signature_count": float(
            source_plan_evidence_summary.get("signature_count", 0.0) or 0.0
        ),
        "source_plan_skeleton_count": float(
            source_plan_evidence_summary.get("skeleton_count", 0.0) or 0.0
        ),
        "source_plan_robust_signature_count": float(
            source_plan_evidence_summary.get("robust_signature_count", 0.0) or 0.0
        ),
        "source_plan_symbol_ratio": float(
            source_plan_evidence_summary.get("symbol_ratio", 0.0) or 0.0
        ),
        "source_plan_signature_ratio": float(
            source_plan_evidence_summary.get("signature_ratio", 0.0) or 0.0
        ),
        "source_plan_skeleton_ratio": float(
            source_plan_evidence_summary.get("skeleton_ratio", 0.0) or 0.0
        ),
        "source_plan_robust_signature_ratio": float(
            source_plan_evidence_summary.get("robust_signature_ratio", 0.0) or 0.0
        ),
        "source_plan_graph_closure_preference_enabled": (
            1.0 if source_plan_graph_closure_preference_enabled else 0.0
        ),
        "source_plan_graph_closure_bonus_candidate_count": float(
            source_plan_graph_closure_bonus_candidate_count
        ),
        "source_plan_graph_closure_preferred_count": float(
            source_plan_graph_closure_preferred_count
        ),
        "source_plan_granularity_preferred_count": float(
            source_plan_granularity_preferred_count
        ),
        "source_plan_focused_file_promoted_count": float(
            source_plan_focused_file_promoted_count
        ),
        "source_plan_packed_path_count": float(source_plan_packed_path_count),
        "source_plan_chunk_retention_ratio": source_plan_chunk_retention_ratio,
        "source_plan_packed_path_ratio": source_plan_packed_path_ratio,
        "notes_hit_ratio": notes_hit_ratio,
        "profile_selected_count": float(profile_selected_count),
        "capture_triggered": 1.0 if capture_triggered else 0.0,
        "ltm_selected_count": float(ltm_selected_count),
        "ltm_attribution_count": float(ltm_attribution_count),
        "ltm_graph_neighbor_count": float(ltm_graph_neighbor_count),
        "ltm_plan_constraint_count": float(ltm_plan_constraint_count),
        "preference_capture": {
            "notes_hit_ratio": float(notes_hit_ratio),
            "profile_selected_count": int(profile_selected_count),
            "capture_triggered": bool(capture_triggered),
        },
        "ltm_explainability": {
            "selected_count": int(ltm_selected_count),
            "attribution_count": int(ltm_attribution_count),
            "graph_neighbor_count": int(ltm_graph_neighbor_count),
            "plan_constraint_count": int(ltm_plan_constraint_count),
            "attribution_preview": [
                str(item).strip()
                for item in ltm_attribution_preview
                if str(item).strip()
            ],
        },
        "feedback_surface": feedback_surface,
        "issue_report_issue_id": issue_report_issue_id,
        "issue_report_has_plan_ref": 1.0 if issue_report_plan_payload_ref else 0.0,
        "issue_report_status": issue_report_status,
        "issue_report_occurred_at": issue_report_occurred_at,
        "issue_report_resolved_at": issue_report_resolved_at,
        "issue_report_created_at": issue_report_created_at,
        "issue_report_updated_at": issue_report_updated_at,
        "issue_report_resolution_note": issue_report_resolution_note,
        "issue_report_time_to_fix_hours": float(issue_report_time_to_fix_hours),
        "dev_feedback_issue_count": float(dev_feedback_issue_count),
        "dev_feedback_linked_fix_issue_count": float(
            dev_feedback_linked_fix_issue_count
        ),
        "dev_feedback_resolved_issue_count": float(
            dev_feedback_resolved_issue_count
        ),
        "dev_feedback_created_at": dev_feedback_created_at,
        "dev_feedback_resolved_at": dev_feedback_resolved_at,
        "dev_feedback_issue_time_to_fix_hours": float(
            dev_feedback_issue_time_to_fix_hours
        ),
        "dev_issue_to_fix_rate": (
            float(dev_feedback_linked_fix_issue_count) / float(dev_feedback_issue_count)
            if dev_feedback_issue_count > 0
            else 0.0
        ),
        "feedback_loop": {
            "feedback_surface": feedback_surface,
            "issue_report_issue_id": issue_report_issue_id,
            "issue_report_has_plan_ref": bool(issue_report_plan_payload_ref),
            "issue_report_status": issue_report_status,
            "issue_report_occurred_at": issue_report_occurred_at,
            "issue_report_resolved_at": issue_report_resolved_at,
            "issue_report_time_to_fix_hours": float(issue_report_time_to_fix_hours),
            "dev_feedback_issue_count": int(dev_feedback_issue_count),
            "dev_feedback_linked_fix_issue_count": int(
                dev_feedback_linked_fix_issue_count
            ),
            "dev_feedback_resolved_issue_count": int(
                dev_feedback_resolved_issue_count
            ),
            "dev_feedback_created_at": dev_feedback_created_at,
            "dev_feedback_resolved_at": dev_feedback_resolved_at,
            "dev_feedback_issue_time_to_fix_hours": float(
                dev_feedback_issue_time_to_fix_hours
            ),
            "dev_issue_to_fix_rate": (
                float(dev_feedback_linked_fix_issue_count)
                / float(dev_feedback_issue_count)
                if dev_feedback_issue_count > 0
                else 0.0
            ),
        },
        "feedback_enabled": 1.0 if feedback_enabled else 0.0,
        "feedback_reason": feedback_reason,
        "feedback_event_count": float(feedback_event_count),
        "feedback_matched_event_count": float(feedback_matched_event_count),
        "feedback_boosted_count": float(feedback_boosted_count),
        "feedback_boosted_paths": float(feedback_boosted_paths),
        "multi_channel_rrf_enabled": 1.0 if multi_channel_rrf_enabled else 0.0,
        "multi_channel_rrf_applied": 1.0 if multi_channel_rrf_applied else 0.0,
        "multi_channel_rrf_granularity_count": float(
            multi_channel_rrf_granularity_count
        ),
        "multi_channel_rrf_pool_size": float(multi_channel_rrf_pool_size),
        "multi_channel_rrf_granularity_pool_ratio": float(
            multi_channel_rrf_granularity_pool_ratio
        ),
        "graph_lookup_enabled": 1.0 if graph_lookup_enabled else 0.0,
        "graph_lookup_reason": str(graph_lookup_reason),
        "graph_lookup_guarded": 1.0 if graph_lookup_guarded else 0.0,
        "graph_lookup_boosted_count": float(graph_lookup_boosted_count),
        "graph_lookup_weight_scip": float(graph_lookup_weight_scip),
        "graph_lookup_weight_xref": float(graph_lookup_weight_xref),
        "graph_lookup_weight_query_xref": float(graph_lookup_weight_query_xref),
        "graph_lookup_weight_symbol": float(graph_lookup_weight_symbol),
        "graph_lookup_weight_import": float(graph_lookup_weight_import),
        "graph_lookup_weight_coverage": float(graph_lookup_weight_coverage),
        "graph_lookup_candidate_count": float(graph_lookup_candidate_count),
        "graph_lookup_pool_size": float(graph_lookup_pool_size),
        "graph_lookup_query_terms_count": float(graph_lookup_query_terms_count),
        "graph_lookup_normalization": str(graph_lookup_normalization),
        "graph_lookup_guard_max_candidates": float(graph_lookup_guard_max_candidates),
        "graph_lookup_guard_min_query_terms": float(
            graph_lookup_guard_min_query_terms
        ),
        "graph_lookup_guard_max_query_terms": float(
            graph_lookup_guard_max_query_terms
        ),
        "graph_lookup_query_hit_paths": float(graph_lookup_query_hit_paths),
        "graph_lookup_scip_signal_paths": float(graph_lookup_scip_signal_paths),
        "graph_lookup_xref_signal_paths": float(graph_lookup_xref_signal_paths),
        "graph_lookup_symbol_hit_paths": float(graph_lookup_symbol_hit_paths),
        "graph_lookup_import_hit_paths": float(graph_lookup_import_hit_paths),
        "graph_lookup_coverage_hit_paths": float(graph_lookup_coverage_hit_paths),
        "graph_lookup_max_inbound": float(graph_lookup_max_inbound),
        "graph_lookup_max_xref_count": float(graph_lookup_max_xref_count),
        "graph_lookup_max_query_hits": float(graph_lookup_max_query_hits),
        "graph_lookup_max_symbol_hits": float(graph_lookup_max_symbol_hits),
        "graph_lookup_max_import_hits": float(graph_lookup_max_import_hits),
        "graph_lookup_max_query_coverage": float(graph_lookup_max_query_coverage),
        "graph_lookup_boosted_path_ratio": float(graph_lookup_boosted_path_ratio),
        "graph_lookup_query_hit_path_ratio": float(graph_lookup_query_hit_path_ratio),
        "feedback_boost": {
            "enabled": bool(feedback_enabled),
            "reason": feedback_reason,
            "event_count": int(feedback_event_count),
            "matched_event_count": int(feedback_matched_event_count),
            "boosted_candidate_count": int(feedback_boosted_count),
            "boosted_unique_paths": int(feedback_boosted_paths),
        },
        "multi_channel_fusion": {
            "enabled": bool(multi_channel_rrf_enabled),
            "applied": bool(multi_channel_rrf_applied),
            "granularity_count": int(multi_channel_rrf_granularity_count),
            "pool_size": int(multi_channel_rrf_pool_size),
            "granularity_pool_ratio": float(multi_channel_rrf_granularity_pool_ratio),
        },
        "graph_lookup": {
            "enabled": bool(graph_lookup_enabled),
            "reason": str(graph_lookup_reason),
            "guarded": bool(graph_lookup_guarded),
            "boosted_count": int(graph_lookup_boosted_count),
            "weights": {
                "scip": float(graph_lookup_weight_scip),
                "xref": float(graph_lookup_weight_xref),
                "query_xref": float(graph_lookup_weight_query_xref),
                "symbol": float(graph_lookup_weight_symbol),
                "import": float(graph_lookup_weight_import),
                "coverage": float(graph_lookup_weight_coverage),
            },
            "candidate_count": int(graph_lookup_candidate_count),
            "pool_size": int(graph_lookup_pool_size),
            "query_terms_count": int(graph_lookup_query_terms_count),
            "normalization": str(graph_lookup_normalization),
            "guard_max_candidates": int(graph_lookup_guard_max_candidates),
            "guard_min_query_terms": int(graph_lookup_guard_min_query_terms),
            "guard_max_query_terms": int(graph_lookup_guard_max_query_terms),
            "query_hit_paths": int(graph_lookup_query_hit_paths),
            "scip_signal_paths": int(graph_lookup_scip_signal_paths),
            "xref_signal_paths": int(graph_lookup_xref_signal_paths),
            "symbol_hit_paths": int(graph_lookup_symbol_hit_paths),
            "import_hit_paths": int(graph_lookup_import_hit_paths),
            "coverage_hit_paths": int(graph_lookup_coverage_hit_paths),
            "max_inbound": float(graph_lookup_max_inbound),
            "max_xref_count": float(graph_lookup_max_xref_count),
            "max_query_hits": float(graph_lookup_max_query_hits),
            "max_symbol_hits": float(graph_lookup_max_symbol_hits),
            "max_import_hits": float(graph_lookup_max_import_hits),
            "max_query_coverage": float(graph_lookup_max_query_coverage),
            "boosted_path_ratio": float(graph_lookup_boosted_path_ratio),
            "query_hit_path_ratio": float(graph_lookup_query_hit_path_ratio),
        },
        "native_scip_loaded": 1.0 if native_scip_loaded else 0.0,
        "native_scip_document_count": float(native_scip_document_count),
        "native_scip_definition_occurrence_count": float(
            native_scip_definition_occurrence_count
        ),
        "native_scip_reference_occurrence_count": float(
            native_scip_reference_occurrence_count
        ),
        "native_scip_symbol_definition_count": float(
            native_scip_symbol_definition_count
        ),
        "native_scip": {
            "loaded": bool(native_scip_loaded),
            "document_count": int(native_scip_document_count),
            "definition_occurrence_count": int(
                native_scip_definition_occurrence_count
            ),
            "reference_occurrence_count": int(
                native_scip_reference_occurrence_count
            ),
            "symbol_definition_count": int(native_scip_symbol_definition_count),
        },
        "policy_profile": policy_profile,
        "graph_transfer_per_seed_ratio": graph_transfer_per_seed_ratio,
        "router_enabled": 1.0 if router_enabled else 0.0,
        "router_mode": router_mode,
        "router_arm_set": router_arm_set,
        "router_arm_id": router_arm_id,
        "router_confidence": router_confidence,
        "router_shadow_arm_id": router_shadow_arm_id,
        "router_shadow_source": router_shadow_source,
        "router_shadow_confidence": router_shadow_confidence,
        "router_online_bandit_requested": (
            1.0 if router_online_bandit_requested else 0.0
        ),
        "router_experiment_enabled": 1.0 if router_experiment_enabled else 0.0,
        "router_online_bandit_active": 1.0 if router_online_bandit_active else 0.0,
        "router_is_exploration": 1.0 if router_is_exploration else 0.0,
        "router_exploration_probability": router_exploration_probability,
        "router_fallback_applied": 1.0 if router_fallback_applied else 0.0,
        "router_fallback_reason": router_fallback_reason,
        "router_online_bandit_reason": router_online_bandit_reason,
        "docs_enabled": 1.0 if docs_enabled_flag else 0.0,
        "docs_hit": docs_hit,
        "hint_inject": hint_inject,
        "embedding_enabled": 1.0 if embedding_enabled else 0.0,
        "embedding_similarity_mean": embedding_similarity_mean,
        "embedding_similarity_max": embedding_similarity_max,
        "embedding_rerank_ratio": embedding_rerank_ratio,
        "embedding_cache_hit": 1.0 if embedding_cache_hit else 0.0,
        "embedding_fallback": 1.0 if embedding_fallback else 0.0,
        "parallel_time_budget_ms": parallel_time_budget_ms,
        "embedding_time_budget_ms": embedding_time_budget_ms,
        "chunk_semantic_time_budget_ms": chunk_semantic_time_budget_ms,
        "xref_time_budget_ms": xref_time_budget_ms,
        "parallel_docs_timed_out": 1.0 if parallel_docs_timed_out else 0.0,
        "parallel_worktree_timed_out": 1.0 if parallel_worktree_timed_out else 0.0,
        "embedding_time_budget_exceeded": (
            1.0 if embedding_time_budget_exceeded else 0.0
        ),
        "embedding_adaptive_budget_applied": (
            1.0 if embedding_adaptive_budget_applied else 0.0
        ),
        "chunk_semantic_time_budget_exceeded": (
            1.0 if chunk_semantic_time_budget_exceeded else 0.0
        ),
        "chunk_semantic_fallback": 1.0 if chunk_semantic_fallback else 0.0,
        "chunk_guard_enabled": 1.0 if chunk_guard_enabled else 0.0,
        "chunk_guard_mode": chunk_guard_mode,
        "chunk_guard_reason": chunk_guard_reason,
        "chunk_guard_report_only": 1.0 if chunk_guard_report_only else 0.0,
        "chunk_guard_filtered_count": float(chunk_guard_filtered_count),
        "chunk_guard_filter_ratio": float(chunk_guard_filter_ratio),
        "chunk_guard_pairwise_conflict_count": float(
            chunk_guard_pairwise_conflict_count
        ),
        "chunk_guard_pairwise_conflict_density": (
            chunk_guard_pairwise_conflict_density
        ),
        "chunk_guard_fallback": 1.0 if chunk_guard_fallback else 0.0,
        "chunk_guard_expectation_applicable": (
            1.0 if chunk_guard_expectation["applicable"] else 0.0
        ),
        "chunk_guard_stale_majority_case": (
            1.0 if chunk_guard_expectation["scenario"] == "stale_majority" else 0.0
        ),
        "chunk_guard_expected_retained_hit": (
            1.0 if chunk_guard_expectation["expected_retained_hit"] else 0.0
        ),
        "chunk_guard_expected_filtered_hit_count": float(
            chunk_guard_expectation["expected_filtered_hit_count"]
        ),
        "chunk_guard_expected_filtered_hit_rate": float(
            chunk_guard_expectation["expected_filtered_hit_rate"]
        ),
        "chunk_guard_report_only_improved": (
            1.0 if chunk_guard_expectation["report_only_improved"] else 0.0
        ),
        "xref_budget_exhausted": 1.0 if xref_budget_exhausted else 0.0,
        "slo_downgrade_triggered": 1.0 if slo_downgrade_signals else 0.0,
        "decision_trace_count": len(decision_trace),
        "decision_trace": decision_trace,
        **evidence_insufficiency,
    }


__all__ = ["build_case_evaluation_row"]
