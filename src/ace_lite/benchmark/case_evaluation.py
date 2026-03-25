"""Case-level benchmark evaluation helpers."""

from __future__ import annotations

from typing import Any

from ace_lite.benchmark.case_evaluation_context import build_candidate_context
from ace_lite.benchmark.case_evaluation_details import classify_chunk_stage_miss
from ace_lite.benchmark.case_evaluation_diagnostics import (
    build_case_evaluation_diagnostics,
)
from ace_lite.benchmark.case_evaluation_matching import (
    collect_candidate_match_details,
    collect_chunk_match_details,
)
from ace_lite.benchmark.case_evaluation_metrics import (
    build_case_evaluation_metrics,
)
from ace_lite.benchmark.case_evaluation_output import (
    build_case_detail_payload,
)
from ace_lite.benchmark.case_evaluation_payloads import coerce_chunk_refs
from ace_lite.benchmark.case_evaluation_row import build_case_evaluation_row


def evaluate_case_result(
    *,
    case: dict[str, Any],
    plan_payload: dict[str, Any],
    latency_ms: float,
    include_case_details: bool = True,
) -> dict[str, Any]:
    comparison_lane = str(case.get("comparison_lane") or "").strip()
    expected_keys = case.get("expected_keys", [])
    if isinstance(expected_keys, str):
        expected = [item.strip() for item in expected_keys.split(";") if item.strip()]
    else:
        expected = [str(item).strip() for item in expected_keys if str(item).strip()]

    top_k = int(case.get("top_k", 8))
    observability = (
        plan_payload.get("observability", {})
        if isinstance(plan_payload.get("observability"), dict)
        else {}
    )

    index_payload = plan_payload.get("index", {}) if isinstance(plan_payload.get("index"), dict) else {}
    index_metadata = (
        index_payload.get("metadata", {})
        if isinstance(index_payload.get("metadata"), dict)
        else {}
    )
    index_benchmark_filters = (
        index_payload.get("benchmark_filters", {})
        if isinstance(index_payload.get("benchmark_filters"), dict)
        else {}
    )
    source_plan_payload = (
        plan_payload.get("source_plan", {})
        if isinstance(plan_payload.get("source_plan"), dict)
        else {}
    )
    candidate_context = build_candidate_context(
        case=case,
        index_payload=index_payload,
        index_benchmark_filters=index_benchmark_filters,
        source_plan_payload=source_plan_payload,
        coerce_chunk_refs=coerce_chunk_refs,
    )
    included_candidate_paths = candidate_context.included_candidate_paths
    included_candidate_globs = candidate_context.included_candidate_globs
    excluded_candidate_paths = candidate_context.excluded_candidate_paths
    excluded_candidate_globs = candidate_context.excluded_candidate_globs
    candidate_files = candidate_context.candidate_files
    raw_candidate_chunks = candidate_context.raw_candidate_chunks
    source_plan_has_candidate_chunks = candidate_context.source_plan_has_candidate_chunks
    source_plan_candidate_chunks = candidate_context.source_plan_candidate_chunks
    candidate_chunks = candidate_context.candidate_chunks
    metrics = build_case_evaluation_metrics(
        plan_payload=plan_payload,
        index_payload=index_payload,
        index_metadata=index_metadata,
        source_plan_payload=source_plan_payload,
        candidate_files=candidate_files,
        raw_candidate_chunks=raw_candidate_chunks,
        candidate_chunks=candidate_chunks,
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
    )
    chunk_guard_payload = metrics.chunk_guard_payload
    source_plan_evidence_summary = metrics.source_plan_evidence_summary
    skills_payload = metrics.skills_payload
    plan_replay_cache_payload = metrics.plan_replay_cache_payload
    subgraph_payload = metrics.subgraph_payload
    subgraph_edge_counts = metrics.subgraph_edge_counts
    subgraph_seed_paths = metrics.subgraph_seed_paths
    subgraph_seed_path_count = metrics.subgraph_seed_path_count
    subgraph_edge_type_count = metrics.subgraph_edge_type_count
    subgraph_edge_total_count = metrics.subgraph_edge_total_count
    subgraph_payload_enabled = metrics.subgraph_payload_enabled
    dependency_recall = metrics.dependency_recall
    neighbor_paths = metrics.neighbor_paths
    exact_search_payload = metrics.exact_search_payload
    second_pass_payload = metrics.second_pass_payload
    refine_pass_payload = metrics.refine_pass_payload
    candidate_ranker_fallbacks = metrics.candidate_ranker_fallbacks
    repomap_worktree_seed_count = metrics.repomap_worktree_seed_count
    repomap_subgraph_seed_count = metrics.repomap_subgraph_seed_count
    repomap_seed_candidates_count = metrics.repomap_seed_candidates_count
    repomap_cache_hit = metrics.repomap_cache_hit
    repomap_precompute_hit = metrics.repomap_precompute_hit
    chunk_stage_miss = classify_chunk_stage_miss(
        case=case,
        candidate_files=candidate_files,
        raw_candidate_chunks=raw_candidate_chunks,
        source_plan_candidate_chunks=source_plan_candidate_chunks,
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
    )

    top_candidates = candidate_files[:top_k]
    top_chunks = candidate_chunks[: max(1, top_k * 3)]

    candidate_match_details = collect_candidate_match_details(
        top_candidates=top_candidates,
        expected=expected,
        top_k=top_k,
    )
    expected_hits = list(candidate_match_details["expected_hits"])
    recall_hit = float(candidate_match_details["recall_hit"])
    relevant_candidates = int(candidate_match_details["relevant_candidates"])
    first_hit_rank = candidate_match_details["first_hit_rank"]
    relevant_candidate_paths = list(candidate_match_details["relevant_candidate_paths"])
    noise_candidate_paths = list(candidate_match_details["noise_candidate_paths"])
    candidate_matches = list(candidate_match_details["candidate_matches"])
    precision = float(candidate_match_details["precision"])
    utility = float(candidate_match_details["utility"])
    noise = float(candidate_match_details["noise"])
    hit_at_1 = float(candidate_match_details["hit_at_1"])
    reciprocal_rank = float(candidate_match_details["reciprocal_rank"])

    chunk_match_details = collect_chunk_match_details(
        top_chunks=top_chunks,
        expected=expected,
    )
    chunk_hits = list(chunk_match_details["chunk_hits"])
    chunk_hit_at_k = float(chunk_match_details["chunk_hit_at_k"])
    chunk_contract_fallback_count = metrics.chunk_contract_fallback_count
    chunk_contract_skeleton_chunk_count = metrics.chunk_contract_skeleton_chunk_count
    chunk_contract_fallback_ratio = metrics.chunk_contract_fallback_ratio
    chunk_contract_skeleton_ratio = metrics.chunk_contract_skeleton_ratio
    chunk_cache_contract_present = metrics.chunk_cache_contract_present
    chunk_cache_contract_fingerprint_present = (
        metrics.chunk_cache_contract_fingerprint_present
    )
    chunk_cache_contract_metadata_aligned = (
        metrics.chunk_cache_contract_metadata_aligned
    )
    chunk_cache_contract_file_count = metrics.chunk_cache_contract_file_count
    chunk_cache_contract_chunk_count = metrics.chunk_cache_contract_chunk_count
    unsupported_language_fallback_count = metrics.unsupported_language_fallback_count
    unsupported_language_fallback_ratio = metrics.unsupported_language_fallback_ratio

    repomap_latency_ms = metrics.repomap_latency_ms
    memory_latency_ms = metrics.memory_latency_ms
    index_latency_ms = metrics.index_latency_ms
    augment_latency_ms = metrics.augment_latency_ms
    skills_latency_ms = metrics.skills_latency_ms
    source_plan_latency_ms = metrics.source_plan_latency_ms

    validation_tests = metrics.validation_tests
    validation_probe_enabled = metrics.validation_probe_enabled
    validation_probe_status = metrics.validation_probe_status
    validation_probe_executed_count = metrics.validation_probe_executed_count
    validation_probe_issue_count = metrics.validation_probe_issue_count
    validation_branch_case = metrics.validation_branch_case
    validation_branch_candidate_count = metrics.validation_branch_candidate_count
    validation_branch_rejected_count = metrics.validation_branch_rejected_count
    validation_branch_selection_present = (
        metrics.validation_branch_selection_present
    )
    validation_branch_patch_artifact_present = (
        metrics.validation_branch_patch_artifact_present
    )
    validation_branch_archive_present = metrics.validation_branch_archive_present
    validation_branch_parallel = metrics.validation_branch_parallel
    validation_branch_winner_passed = metrics.validation_branch_winner_passed
    validation_branch_winner_regressed = metrics.validation_branch_winner_regressed
    validation_branch_winner_score = metrics.validation_branch_winner_score
    validation_branch_winner_after_issue_count = (
        metrics.validation_branch_winner_after_issue_count
    )
    agent_loop_observed = metrics.agent_loop_observed
    agent_loop_enabled = metrics.agent_loop_enabled
    agent_loop_attempted = metrics.agent_loop_attempted
    agent_loop_actions_requested = metrics.agent_loop_actions_requested
    agent_loop_actions_executed = metrics.agent_loop_actions_executed
    agent_loop_stop_reason = metrics.agent_loop_stop_reason
    agent_loop_replay_safe = metrics.agent_loop_replay_safe
    agent_loop_last_policy_id = metrics.agent_loop_last_policy_id
    agent_loop_request_more_context_count = (
        metrics.agent_loop_request_more_context_count
    )
    agent_loop_request_source_plan_retry_count = (
        metrics.agent_loop_request_source_plan_retry_count
    )
    agent_loop_request_validation_retry_count = (
        metrics.agent_loop_request_validation_retry_count
    )
    source_plan_validation_feedback_present = (
        metrics.source_plan_validation_feedback_present
    )
    source_plan_validation_feedback_status = (
        metrics.source_plan_validation_feedback_status
    )
    source_plan_validation_feedback_issue_count = (
        metrics.source_plan_validation_feedback_issue_count
    )
    source_plan_validation_feedback_probe_status = (
        metrics.source_plan_validation_feedback_probe_status
    )
    source_plan_validation_feedback_probe_issue_count = (
        metrics.source_plan_validation_feedback_probe_issue_count
    )
    source_plan_validation_feedback_probe_executed_count = (
        metrics.source_plan_validation_feedback_probe_executed_count
    )
    source_plan_validation_feedback_selected_test_count = (
        metrics.source_plan_validation_feedback_selected_test_count
    )
    source_plan_validation_feedback_executed_test_count = (
        metrics.source_plan_validation_feedback_executed_test_count
    )
    source_plan_card_summary = metrics.source_plan_card_summary
    source_plan_failure_signal_summary = metrics.source_plan_failure_signal_summary
    source_plan_failure_signal_origin = metrics.source_plan_failure_signal_origin
    source_plan_failure_signal_present = metrics.source_plan_failure_signal_present
    source_plan_failure_signal_status = metrics.source_plan_failure_signal_status
    source_plan_failure_signal_issue_count = (
        metrics.source_plan_failure_signal_issue_count
    )
    source_plan_failure_signal_probe_status = (
        metrics.source_plan_failure_signal_probe_status
    )
    source_plan_failure_signal_probe_issue_count = (
        metrics.source_plan_failure_signal_probe_issue_count
    )
    source_plan_failure_signal_probe_executed_count = (
        metrics.source_plan_failure_signal_probe_executed_count
    )
    source_plan_failure_signal_selected_test_count = (
        metrics.source_plan_failure_signal_selected_test_count
    )
    source_plan_failure_signal_executed_test_count = (
        metrics.source_plan_failure_signal_executed_test_count
    )
    source_plan_failure_signal_has_failure = (
        metrics.source_plan_failure_signal_has_failure
    )
    source_plan_evidence_card_count = metrics.source_plan_evidence_card_count
    source_plan_file_card_count = metrics.source_plan_file_card_count
    source_plan_chunk_card_count = metrics.source_plan_chunk_card_count
    source_plan_validation_card_present = (
        metrics.source_plan_validation_card_present
    )
    notes_hit_ratio = metrics.notes_hit_ratio
    profile_selected_count = metrics.profile_selected_count
    capture_triggered = metrics.capture_triggered
    ltm_selected_count = metrics.ltm_selected_count
    ltm_attribution_count = metrics.ltm_attribution_count
    ltm_graph_neighbor_count = metrics.ltm_graph_neighbor_count
    ltm_plan_constraint_count = metrics.ltm_plan_constraint_count
    ltm_feedback_signal_counts = metrics.ltm_feedback_signal_counts
    ltm_attribution_scope_counts = metrics.ltm_attribution_scope_counts
    ltm_attribution_preview = metrics.ltm_attribution_preview
    feedback_enabled = metrics.feedback_enabled
    feedback_reason = metrics.feedback_reason
    feedback_event_count = metrics.feedback_event_count
    feedback_matched_event_count = metrics.feedback_matched_event_count
    feedback_boosted_count = metrics.feedback_boosted_count
    feedback_boosted_paths = metrics.feedback_boosted_paths
    multi_channel_rrf_enabled = metrics.multi_channel_rrf_enabled
    multi_channel_rrf_applied = metrics.multi_channel_rrf_applied
    multi_channel_rrf_granularity_count = (
        metrics.multi_channel_rrf_granularity_count
    )
    multi_channel_rrf_pool_size = metrics.multi_channel_rrf_pool_size
    multi_channel_rrf_granularity_pool_ratio = (
        metrics.multi_channel_rrf_granularity_pool_ratio
    )
    graph_lookup_enabled = metrics.graph_lookup_enabled
    graph_lookup_reason = metrics.graph_lookup_reason
    graph_lookup_guarded = metrics.graph_lookup_guarded
    graph_lookup_boosted_count = metrics.graph_lookup_boosted_count
    graph_lookup_weight_scip = metrics.graph_lookup_weight_scip
    graph_lookup_weight_xref = metrics.graph_lookup_weight_xref
    graph_lookup_weight_query_xref = metrics.graph_lookup_weight_query_xref
    graph_lookup_weight_symbol = metrics.graph_lookup_weight_symbol
    graph_lookup_weight_import = metrics.graph_lookup_weight_import
    graph_lookup_weight_coverage = metrics.graph_lookup_weight_coverage
    graph_lookup_candidate_count = metrics.graph_lookup_candidate_count
    graph_lookup_pool_size = metrics.graph_lookup_pool_size
    graph_lookup_query_terms_count = metrics.graph_lookup_query_terms_count
    graph_lookup_normalization = metrics.graph_lookup_normalization
    graph_lookup_guard_max_candidates = metrics.graph_lookup_guard_max_candidates
    graph_lookup_guard_min_query_terms = metrics.graph_lookup_guard_min_query_terms
    graph_lookup_guard_max_query_terms = metrics.graph_lookup_guard_max_query_terms
    graph_lookup_query_hit_paths = metrics.graph_lookup_query_hit_paths
    graph_lookup_scip_signal_paths = metrics.graph_lookup_scip_signal_paths
    graph_lookup_xref_signal_paths = metrics.graph_lookup_xref_signal_paths
    graph_lookup_symbol_hit_paths = metrics.graph_lookup_symbol_hit_paths
    graph_lookup_import_hit_paths = metrics.graph_lookup_import_hit_paths
    graph_lookup_coverage_hit_paths = metrics.graph_lookup_coverage_hit_paths
    graph_lookup_max_inbound = metrics.graph_lookup_max_inbound
    graph_lookup_max_xref_count = metrics.graph_lookup_max_xref_count
    graph_lookup_max_query_hits = metrics.graph_lookup_max_query_hits
    graph_lookup_max_symbol_hits = metrics.graph_lookup_max_symbol_hits
    graph_lookup_max_import_hits = metrics.graph_lookup_max_import_hits
    graph_lookup_max_query_coverage = metrics.graph_lookup_max_query_coverage
    graph_lookup_boosted_path_ratio = metrics.graph_lookup_boosted_path_ratio
    graph_lookup_query_hit_path_ratio = metrics.graph_lookup_query_hit_path_ratio
    native_scip_loaded = metrics.native_scip_loaded
    native_scip_document_count = metrics.native_scip_document_count
    native_scip_definition_occurrence_count = (
        metrics.native_scip_definition_occurrence_count
    )
    native_scip_reference_occurrence_count = (
        metrics.native_scip_reference_occurrence_count
    )
    native_scip_symbol_definition_count = metrics.native_scip_symbol_definition_count
    embedding_enabled = metrics.embedding_enabled
    embedding_fallback = metrics.embedding_fallback
    embedding_cache_hit = metrics.embedding_cache_hit
    embedding_runtime_provider = metrics.embedding_runtime_provider
    embedding_strategy_mode = metrics.embedding_strategy_mode
    embedding_semantic_rerank_applied = (
        metrics.embedding_semantic_rerank_applied
    )
    embedding_rerank_ratio = metrics.embedding_rerank_ratio
    embedding_similarity_mean = metrics.embedding_similarity_mean
    embedding_similarity_max = metrics.embedding_similarity_max
    docs_backend_fallback_reason = metrics.docs_backend_fallback_reason
    memory_gate_skipped = metrics.memory_gate_skipped
    memory_gate_skip_reason = metrics.memory_gate_skip_reason
    memory_fallback_reason = metrics.memory_fallback_reason
    memory_namespace_fallback = metrics.memory_namespace_fallback
    chunk_semantic_reason = metrics.chunk_semantic_reason
    parallel_time_budget_ms = metrics.parallel_time_budget_ms
    embedding_time_budget_ms = metrics.embedding_time_budget_ms
    chunk_semantic_time_budget_ms = metrics.chunk_semantic_time_budget_ms
    xref_time_budget_ms = metrics.xref_time_budget_ms
    parallel_docs_timed_out = metrics.parallel_docs_timed_out
    parallel_worktree_timed_out = metrics.parallel_worktree_timed_out
    embedding_time_budget_exceeded = metrics.embedding_time_budget_exceeded
    embedding_adaptive_budget_applied = metrics.embedding_adaptive_budget_applied
    chunk_semantic_time_budget_exceeded = (
        metrics.chunk_semantic_time_budget_exceeded
    )
    chunk_semantic_fallback = metrics.chunk_semantic_fallback
    chunk_guard_candidate_pool = metrics.chunk_guard_candidate_pool
    chunk_guard_filtered_count = metrics.chunk_guard_filtered_count
    chunk_guard_retained_count = metrics.chunk_guard_retained_count
    chunk_guard_signed_chunk_count = metrics.chunk_guard_signed_chunk_count
    chunk_guard_pairwise_conflict_count = (
        metrics.chunk_guard_pairwise_conflict_count
    )
    chunk_guard_max_conflict_penalty = metrics.chunk_guard_max_conflict_penalty
    chunk_guard_mode = metrics.chunk_guard_mode
    chunk_guard_reason = metrics.chunk_guard_reason
    chunk_guard_enabled = metrics.chunk_guard_enabled
    chunk_guard_report_only = metrics.chunk_guard_report_only
    chunk_guard_fallback = metrics.chunk_guard_fallback
    chunk_guard_filter_ratio = metrics.chunk_guard_filter_ratio
    xref_budget_exhausted = metrics.xref_budget_exhausted
    chunk_budget_used = metrics.chunk_budget_used
    chunks_per_file_mean = metrics.chunks_per_file_mean
    retrieval_context_chunk_count = metrics.retrieval_context_chunk_count
    retrieval_context_coverage_ratio = metrics.retrieval_context_coverage_ratio
    retrieval_context_char_count_mean = metrics.retrieval_context_char_count_mean
    contextual_sidecar_parent_symbol_chunk_count = (
        metrics.contextual_sidecar_parent_symbol_chunk_count
    )
    contextual_sidecar_parent_symbol_coverage_ratio = (
        metrics.contextual_sidecar_parent_symbol_coverage_ratio
    )
    contextual_sidecar_reference_hint_chunk_count = (
        metrics.contextual_sidecar_reference_hint_chunk_count
    )
    contextual_sidecar_reference_hint_coverage_ratio = (
        metrics.contextual_sidecar_reference_hint_coverage_ratio
    )
    retrieval_context_pool_chunk_count = metrics.retrieval_context_pool_chunk_count
    retrieval_context_pool_coverage_ratio = (
        metrics.retrieval_context_pool_coverage_ratio
    )
    robust_signature_count = metrics.robust_signature_count
    robust_signature_coverage_ratio = metrics.robust_signature_coverage_ratio
    graph_prior_chunk_count = metrics.graph_prior_chunk_count
    graph_prior_coverage_ratio = metrics.graph_prior_coverage_ratio
    graph_prior_total = metrics.graph_prior_total
    graph_seeded_chunk_count = metrics.graph_seeded_chunk_count
    graph_transfer_count = metrics.graph_transfer_count
    graph_hub_suppressed_chunk_count = metrics.graph_hub_suppressed_chunk_count
    graph_hub_penalty_total = metrics.graph_hub_penalty_total
    graph_closure_enabled = metrics.graph_closure_enabled
    graph_closure_boosted_chunk_count = metrics.graph_closure_boosted_chunk_count
    graph_closure_coverage_ratio = metrics.graph_closure_coverage_ratio
    graph_closure_anchor_count = metrics.graph_closure_anchor_count
    graph_closure_support_edge_count = metrics.graph_closure_support_edge_count
    graph_closure_total = metrics.graph_closure_total
    topological_shield_enabled = metrics.topological_shield_enabled
    topological_shield_mode = metrics.topological_shield_mode
    topological_shield_report_only = metrics.topological_shield_report_only
    topological_shield_max_attenuation = metrics.topological_shield_max_attenuation
    topological_shield_shared_parent_attenuation = (
        metrics.topological_shield_shared_parent_attenuation
    )
    topological_shield_adjacency_attenuation = (
        metrics.topological_shield_adjacency_attenuation
    )
    topological_shield_attenuated_chunk_count = (
        metrics.topological_shield_attenuated_chunk_count
    )
    topological_shield_coverage_ratio = metrics.topological_shield_coverage_ratio
    topological_shield_attenuation_total = metrics.topological_shield_attenuation_total
    graph_source_provider_loaded = metrics.graph_source_provider_loaded
    graph_source_projection_fallback = metrics.graph_source_projection_fallback
    graph_source_edge_count = metrics.graph_source_edge_count
    graph_source_inbound_signal_chunk_count = (
        metrics.graph_source_inbound_signal_chunk_count
    )
    graph_source_inbound_signal_coverage_ratio = (
        metrics.graph_source_inbound_signal_coverage_ratio
    )
    graph_source_centrality_signal_chunk_count = (
        metrics.graph_source_centrality_signal_chunk_count
    )
    graph_source_centrality_signal_coverage_ratio = (
        metrics.graph_source_centrality_signal_coverage_ratio
    )
    graph_source_pagerank_signal_chunk_count = (
        metrics.graph_source_pagerank_signal_chunk_count
    )
    graph_source_pagerank_signal_coverage_ratio = (
        metrics.graph_source_pagerank_signal_coverage_ratio
    )
    skills_selected_count = metrics.skills_selected_count
    skills_skipped_for_budget_count = metrics.skills_skipped_for_budget_count
    skills_token_budget = metrics.skills_token_budget
    skills_token_budget_used = metrics.skills_token_budget_used
    skills_budget_exhausted = metrics.skills_budget_exhausted
    skills_route_latency_ms = metrics.skills_route_latency_ms
    skills_hydration_latency_ms = metrics.skills_hydration_latency_ms
    skills_metadata_only_routing = metrics.skills_metadata_only_routing
    skills_precomputed_route = metrics.skills_precomputed_route
    plan_replay_cache_enabled = metrics.plan_replay_cache_enabled
    plan_replay_cache_hit = metrics.plan_replay_cache_hit
    plan_replay_cache_stale_hit_safe = metrics.plan_replay_cache_stale_hit_safe
    source_plan_graph_closure_preference_enabled = (
        metrics.source_plan_graph_closure_preference_enabled
    )
    source_plan_graph_closure_bonus_candidate_count = (
        metrics.source_plan_graph_closure_bonus_candidate_count
    )
    source_plan_graph_closure_preferred_count = (
        metrics.source_plan_graph_closure_preferred_count
    )
    source_plan_granularity_preferred_count = (
        metrics.source_plan_granularity_preferred_count
    )
    source_plan_focused_file_promoted_count = (
        metrics.source_plan_focused_file_promoted_count
    )
    source_plan_packed_path_count = metrics.source_plan_packed_path_count
    source_plan_packing_reason = metrics.source_plan_packing_reason
    source_plan_chunk_retention_ratio = metrics.source_plan_chunk_retention_ratio
    source_plan_packed_path_ratio = metrics.source_plan_packed_path_ratio
    skills_token_budget_utilization_ratio = (
        metrics.skills_token_budget_utilization_ratio
    )
    graph_transfer_per_seed_ratio = metrics.graph_transfer_per_seed_ratio
    chunk_guard_pairwise_conflict_density = (
        metrics.chunk_guard_pairwise_conflict_density
    )
    topological_shield_attenuation_per_chunk = (
        metrics.topological_shield_attenuation_per_chunk
    )
    router_enabled = metrics.router_enabled
    router_mode = metrics.router_mode
    router_arm_set = metrics.router_arm_set
    router_arm_id = metrics.router_arm_id
    router_confidence = metrics.router_confidence
    router_shadow_arm_id = metrics.router_shadow_arm_id
    router_shadow_source = metrics.router_shadow_source
    router_shadow_confidence = metrics.router_shadow_confidence
    router_online_bandit_requested = metrics.router_online_bandit_requested
    router_experiment_enabled = metrics.router_experiment_enabled
    router_online_bandit_active = metrics.router_online_bandit_active
    router_is_exploration = metrics.router_is_exploration
    router_exploration_probability = metrics.router_exploration_probability
    router_fallback_applied = metrics.router_fallback_applied
    router_fallback_reason = metrics.router_fallback_reason
    router_online_bandit_reason = metrics.router_online_bandit_reason
    policy_profile = metrics.policy_profile
    docs_enabled_flag = metrics.docs_enabled_flag
    docs_hit = metrics.docs_hit
    hint_inject = metrics.hint_inject
    diagnostics = build_case_evaluation_diagnostics(
        case=case,
        expected=expected,
        recall_hit=recall_hit,
        validation_tests=validation_tests,
        candidate_file_count=len(top_candidates),
        candidate_chunk_count=len(candidate_chunks),
        chunk_hit_at_k=chunk_hit_at_k,
        noise_rate=noise,
        docs_enabled=docs_enabled_flag,
        docs_hit=docs_hit,
        dependency_recall=dependency_recall,
        neighbor_paths=neighbor_paths,
        skills_budget_exhausted=skills_budget_exhausted,
        memory_gate_skipped=memory_gate_skipped,
        memory_gate_skip_reason=memory_gate_skip_reason,
        memory_fallback_reason=memory_fallback_reason,
        memory_namespace_fallback=memory_namespace_fallback,
        candidate_ranker_fallbacks=candidate_ranker_fallbacks,
        exact_search_payload=exact_search_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        docs_backend_fallback_reason=docs_backend_fallback_reason,
        parallel_docs_timed_out=parallel_docs_timed_out,
        parallel_worktree_timed_out=parallel_worktree_timed_out,
        embedding_adaptive_budget_applied=embedding_adaptive_budget_applied,
        embedding_time_budget_exceeded=embedding_time_budget_exceeded,
        embedding_fallback=embedding_fallback,
        chunk_semantic_time_budget_exceeded=(
            chunk_semantic_time_budget_exceeded
        ),
        chunk_semantic_fallback=chunk_semantic_fallback,
        chunk_semantic_reason=chunk_semantic_reason,
        xref_budget_exhausted=xref_budget_exhausted,
        chunk_guard_payload=chunk_guard_payload,
    )
    task_success_config = diagnostics.task_success_config
    task_success_failed_checks = diagnostics.task_success_failed_checks
    task_success_hit = diagnostics.task_success_hit
    slo_downgrade_signals = diagnostics.slo_downgrade_signals
    evidence_insufficiency = diagnostics.evidence_insufficiency
    decision_trace = diagnostics.decision_trace
    chunk_guard_expectation = diagnostics.chunk_guard_expectation

    payload = build_case_evaluation_row(
        case=case,
        expected=expected,
        top_k=top_k,
        recall_hit=recall_hit,
        precision=precision,
        first_hit_rank=first_hit_rank,
        hit_at_1=hit_at_1,
        reciprocal_rank=reciprocal_rank,
        utility=utility,
        task_success_hit=task_success_hit,
        task_success_config=task_success_config,
        task_success_failed_checks=task_success_failed_checks,
        noise=noise,
        dependency_recall=dependency_recall,
        memory_latency_ms=memory_latency_ms,
        index_latency_ms=index_latency_ms,
        repomap_latency_ms=repomap_latency_ms,
        repomap_worktree_seed_count=repomap_worktree_seed_count,
        repomap_subgraph_seed_count=repomap_subgraph_seed_count,
        repomap_seed_candidates_count=repomap_seed_candidates_count,
        repomap_cache_hit=repomap_cache_hit,
        repomap_precompute_hit=repomap_precompute_hit,
        augment_latency_ms=augment_latency_ms,
        skills_latency_ms=skills_latency_ms,
        source_plan_latency_ms=source_plan_latency_ms,
        latency_ms=latency_ms,
        chunk_hit_at_k=chunk_hit_at_k,
        chunks_per_file_mean=chunks_per_file_mean,
        chunk_budget_used=chunk_budget_used,
        retrieval_context_chunk_count=retrieval_context_chunk_count,
        retrieval_context_coverage_ratio=retrieval_context_coverage_ratio,
        retrieval_context_char_count_mean=retrieval_context_char_count_mean,
        contextual_sidecar_parent_symbol_chunk_count=(
            contextual_sidecar_parent_symbol_chunk_count
        ),
        contextual_sidecar_parent_symbol_coverage_ratio=(
            contextual_sidecar_parent_symbol_coverage_ratio
        ),
        contextual_sidecar_reference_hint_chunk_count=(
            contextual_sidecar_reference_hint_chunk_count
        ),
        contextual_sidecar_reference_hint_coverage_ratio=(
            contextual_sidecar_reference_hint_coverage_ratio
        ),
        retrieval_context_pool_chunk_count=retrieval_context_pool_chunk_count,
        retrieval_context_pool_coverage_ratio=retrieval_context_pool_coverage_ratio,
        chunk_contract_fallback_count=chunk_contract_fallback_count,
        chunk_contract_skeleton_chunk_count=chunk_contract_skeleton_chunk_count,
        chunk_contract_fallback_ratio=chunk_contract_fallback_ratio,
        chunk_contract_skeleton_ratio=chunk_contract_skeleton_ratio,
        chunk_cache_contract_present=chunk_cache_contract_present,
        chunk_cache_contract_fingerprint_present=(
            chunk_cache_contract_fingerprint_present
        ),
        chunk_cache_contract_metadata_aligned=(
            chunk_cache_contract_metadata_aligned
        ),
        chunk_cache_contract_file_count=chunk_cache_contract_file_count,
        chunk_cache_contract_chunk_count=chunk_cache_contract_chunk_count,
        unsupported_language_fallback_count=unsupported_language_fallback_count,
        unsupported_language_fallback_ratio=unsupported_language_fallback_ratio,
        subgraph_payload_enabled=subgraph_payload_enabled,
        subgraph_seed_path_count=subgraph_seed_path_count,
        subgraph_edge_type_count=subgraph_edge_type_count,
        subgraph_edge_total_count=subgraph_edge_total_count,
        robust_signature_count=robust_signature_count,
        robust_signature_coverage_ratio=robust_signature_coverage_ratio,
        graph_prior_chunk_count=graph_prior_chunk_count,
        graph_prior_coverage_ratio=graph_prior_coverage_ratio,
        graph_prior_total=graph_prior_total,
        graph_seeded_chunk_count=graph_seeded_chunk_count,
        graph_transfer_count=graph_transfer_count,
        graph_hub_suppressed_chunk_count=graph_hub_suppressed_chunk_count,
        graph_hub_penalty_total=graph_hub_penalty_total,
        graph_closure_enabled=graph_closure_enabled,
        graph_closure_boosted_chunk_count=graph_closure_boosted_chunk_count,
        graph_closure_coverage_ratio=graph_closure_coverage_ratio,
        graph_closure_anchor_count=graph_closure_anchor_count,
        graph_closure_support_edge_count=graph_closure_support_edge_count,
        graph_closure_total=graph_closure_total,
        topological_shield_enabled=topological_shield_enabled,
        topological_shield_mode=topological_shield_mode,
        topological_shield_report_only=topological_shield_report_only,
        topological_shield_max_attenuation=topological_shield_max_attenuation,
        topological_shield_shared_parent_attenuation=(
            topological_shield_shared_parent_attenuation
        ),
        topological_shield_adjacency_attenuation=(
            topological_shield_adjacency_attenuation
        ),
        topological_shield_attenuated_chunk_count=(
            topological_shield_attenuated_chunk_count
        ),
        topological_shield_coverage_ratio=topological_shield_coverage_ratio,
        topological_shield_attenuation_total=topological_shield_attenuation_total,
        topological_shield_attenuation_per_chunk=(
            topological_shield_attenuation_per_chunk
        ),
        graph_source_provider_loaded=graph_source_provider_loaded,
        graph_source_projection_fallback=graph_source_projection_fallback,
        graph_source_edge_count=graph_source_edge_count,
        graph_source_inbound_signal_chunk_count=(
            graph_source_inbound_signal_chunk_count
        ),
        graph_source_inbound_signal_coverage_ratio=(
            graph_source_inbound_signal_coverage_ratio
        ),
        graph_source_centrality_signal_chunk_count=(
            graph_source_centrality_signal_chunk_count
        ),
        graph_source_centrality_signal_coverage_ratio=(
            graph_source_centrality_signal_coverage_ratio
        ),
        graph_source_pagerank_signal_chunk_count=(
            graph_source_pagerank_signal_chunk_count
        ),
        graph_source_pagerank_signal_coverage_ratio=(
            graph_source_pagerank_signal_coverage_ratio
        ),
        skills_selected_count=skills_selected_count,
        skills_token_budget=skills_token_budget,
        skills_token_budget_used=skills_token_budget_used,
        skills_token_budget_utilization_ratio=(
            skills_token_budget_utilization_ratio
        ),
        skills_budget_exhausted=skills_budget_exhausted,
        skills_skipped_for_budget_count=skills_skipped_for_budget_count,
        skills_route_latency_ms=skills_route_latency_ms,
        skills_hydration_latency_ms=skills_hydration_latency_ms,
        skills_metadata_only_routing=skills_metadata_only_routing,
        skills_precomputed_route=skills_precomputed_route,
        plan_replay_cache_enabled=plan_replay_cache_enabled,
        plan_replay_cache_hit=plan_replay_cache_hit,
        plan_replay_cache_stale_hit_safe=plan_replay_cache_stale_hit_safe,
        chunk_stage_miss=chunk_stage_miss,
        validation_tests=validation_tests,
        validation_probe_enabled=validation_probe_enabled,
        validation_probe_status=validation_probe_status,
        validation_probe_executed_count=validation_probe_executed_count,
        validation_probe_issue_count=validation_probe_issue_count,
        validation_branch_case=validation_branch_case,
        validation_branch_candidate_count=validation_branch_candidate_count,
        validation_branch_rejected_count=validation_branch_rejected_count,
        validation_branch_selection_present=validation_branch_selection_present,
        validation_branch_patch_artifact_present=(
            validation_branch_patch_artifact_present
        ),
        validation_branch_archive_present=validation_branch_archive_present,
        validation_branch_parallel=validation_branch_parallel,
        validation_branch_winner_passed=validation_branch_winner_passed,
        validation_branch_winner_regressed=validation_branch_winner_regressed,
        validation_branch_winner_score=validation_branch_winner_score,
        validation_branch_winner_after_issue_count=(
            validation_branch_winner_after_issue_count
        ),
        agent_loop_observed=agent_loop_observed,
        agent_loop_enabled=agent_loop_enabled,
        agent_loop_attempted=agent_loop_attempted,
        agent_loop_actions_requested=agent_loop_actions_requested,
        agent_loop_actions_executed=agent_loop_actions_executed,
        agent_loop_stop_reason=agent_loop_stop_reason,
        agent_loop_replay_safe=agent_loop_replay_safe,
        agent_loop_last_policy_id=agent_loop_last_policy_id,
        agent_loop_request_more_context_count=(
            agent_loop_request_more_context_count
        ),
        agent_loop_request_source_plan_retry_count=(
            agent_loop_request_source_plan_retry_count
        ),
        agent_loop_request_validation_retry_count=(
            agent_loop_request_validation_retry_count
        ),
        source_plan_validation_feedback_present=(
            source_plan_validation_feedback_present
        ),
        source_plan_validation_feedback_status=(
            source_plan_validation_feedback_status
        ),
        source_plan_validation_feedback_issue_count=(
            source_plan_validation_feedback_issue_count
        ),
        source_plan_validation_feedback_probe_status=(
            source_plan_validation_feedback_probe_status
        ),
        source_plan_validation_feedback_probe_issue_count=(
            source_plan_validation_feedback_probe_issue_count
        ),
        source_plan_validation_feedback_probe_executed_count=(
            source_plan_validation_feedback_probe_executed_count
        ),
        source_plan_validation_feedback_selected_test_count=(
            source_plan_validation_feedback_selected_test_count
        ),
        source_plan_validation_feedback_executed_test_count=(
            source_plan_validation_feedback_executed_test_count
        ),
        source_plan_failure_signal_origin=source_plan_failure_signal_origin,
        source_plan_failure_signal_present=source_plan_failure_signal_present,
        source_plan_failure_signal_status=source_plan_failure_signal_status,
        source_plan_failure_signal_issue_count=(
            source_plan_failure_signal_issue_count
        ),
        source_plan_failure_signal_probe_status=(
            source_plan_failure_signal_probe_status
        ),
        source_plan_failure_signal_probe_issue_count=(
            source_plan_failure_signal_probe_issue_count
        ),
        source_plan_failure_signal_probe_executed_count=(
            source_plan_failure_signal_probe_executed_count
        ),
        source_plan_failure_signal_selected_test_count=(
            source_plan_failure_signal_selected_test_count
        ),
        source_plan_failure_signal_executed_test_count=(
            source_plan_failure_signal_executed_test_count
        ),
        source_plan_failure_signal_has_failure=(
            source_plan_failure_signal_has_failure
        ),
        source_plan_evidence_card_count=source_plan_evidence_card_count,
        source_plan_file_card_count=source_plan_file_card_count,
        source_plan_chunk_card_count=source_plan_chunk_card_count,
        source_plan_validation_card_present=source_plan_validation_card_present,
        source_plan_evidence_summary=source_plan_evidence_summary,
        source_plan_graph_closure_preference_enabled=(
            source_plan_graph_closure_preference_enabled
        ),
        source_plan_graph_closure_bonus_candidate_count=(
            source_plan_graph_closure_bonus_candidate_count
        ),
        source_plan_graph_closure_preferred_count=(
            source_plan_graph_closure_preferred_count
        ),
        source_plan_granularity_preferred_count=(
            source_plan_granularity_preferred_count
        ),
        source_plan_focused_file_promoted_count=(
            source_plan_focused_file_promoted_count
        ),
        source_plan_packed_path_count=source_plan_packed_path_count,
        source_plan_chunk_retention_ratio=source_plan_chunk_retention_ratio,
        source_plan_packed_path_ratio=source_plan_packed_path_ratio,
        notes_hit_ratio=notes_hit_ratio,
        profile_selected_count=profile_selected_count,
        capture_triggered=capture_triggered,
        ltm_selected_count=ltm_selected_count,
        ltm_attribution_count=ltm_attribution_count,
        ltm_graph_neighbor_count=ltm_graph_neighbor_count,
        ltm_plan_constraint_count=ltm_plan_constraint_count,
        ltm_feedback_signal_counts=ltm_feedback_signal_counts,
        ltm_attribution_scope_counts=ltm_attribution_scope_counts,
        ltm_attribution_preview=ltm_attribution_preview,
        feedback_enabled=feedback_enabled,
        feedback_reason=feedback_reason,
        feedback_event_count=feedback_event_count,
        feedback_matched_event_count=feedback_matched_event_count,
        feedback_boosted_count=feedback_boosted_count,
        feedback_boosted_paths=feedback_boosted_paths,
        multi_channel_rrf_enabled=multi_channel_rrf_enabled,
        multi_channel_rrf_applied=multi_channel_rrf_applied,
        multi_channel_rrf_granularity_count=multi_channel_rrf_granularity_count,
        multi_channel_rrf_pool_size=multi_channel_rrf_pool_size,
        multi_channel_rrf_granularity_pool_ratio=(
            multi_channel_rrf_granularity_pool_ratio
        ),
        graph_lookup_enabled=graph_lookup_enabled,
        graph_lookup_reason=graph_lookup_reason,
        graph_lookup_guarded=graph_lookup_guarded,
        graph_lookup_boosted_count=graph_lookup_boosted_count,
        graph_lookup_weight_scip=graph_lookup_weight_scip,
        graph_lookup_weight_xref=graph_lookup_weight_xref,
        graph_lookup_weight_query_xref=graph_lookup_weight_query_xref,
        graph_lookup_weight_symbol=graph_lookup_weight_symbol,
        graph_lookup_weight_import=graph_lookup_weight_import,
        graph_lookup_weight_coverage=graph_lookup_weight_coverage,
        graph_lookup_candidate_count=graph_lookup_candidate_count,
        graph_lookup_pool_size=graph_lookup_pool_size,
        graph_lookup_query_terms_count=graph_lookup_query_terms_count,
        graph_lookup_normalization=graph_lookup_normalization,
        graph_lookup_guard_max_candidates=graph_lookup_guard_max_candidates,
        graph_lookup_guard_min_query_terms=graph_lookup_guard_min_query_terms,
        graph_lookup_guard_max_query_terms=graph_lookup_guard_max_query_terms,
        graph_lookup_query_hit_paths=graph_lookup_query_hit_paths,
        graph_lookup_scip_signal_paths=graph_lookup_scip_signal_paths,
        graph_lookup_xref_signal_paths=graph_lookup_xref_signal_paths,
        graph_lookup_symbol_hit_paths=graph_lookup_symbol_hit_paths,
        graph_lookup_import_hit_paths=graph_lookup_import_hit_paths,
        graph_lookup_coverage_hit_paths=graph_lookup_coverage_hit_paths,
        graph_lookup_max_inbound=graph_lookup_max_inbound,
        graph_lookup_max_xref_count=graph_lookup_max_xref_count,
        graph_lookup_max_query_hits=graph_lookup_max_query_hits,
        graph_lookup_max_symbol_hits=graph_lookup_max_symbol_hits,
        graph_lookup_max_import_hits=graph_lookup_max_import_hits,
        graph_lookup_max_query_coverage=graph_lookup_max_query_coverage,
        graph_lookup_boosted_path_ratio=graph_lookup_boosted_path_ratio,
        graph_lookup_query_hit_path_ratio=graph_lookup_query_hit_path_ratio,
        native_scip_loaded=native_scip_loaded,
        native_scip_document_count=native_scip_document_count,
        native_scip_definition_occurrence_count=(
            native_scip_definition_occurrence_count
        ),
        native_scip_reference_occurrence_count=(
            native_scip_reference_occurrence_count
        ),
        native_scip_symbol_definition_count=native_scip_symbol_definition_count,
        policy_profile=policy_profile,
        graph_transfer_per_seed_ratio=graph_transfer_per_seed_ratio,
        router_enabled=router_enabled,
        router_mode=router_mode,
        router_arm_set=router_arm_set,
        router_arm_id=router_arm_id,
        router_confidence=router_confidence,
        router_shadow_arm_id=router_shadow_arm_id,
        router_shadow_source=router_shadow_source,
        router_shadow_confidence=router_shadow_confidence,
        router_online_bandit_requested=router_online_bandit_requested,
        router_experiment_enabled=router_experiment_enabled,
        router_online_bandit_active=router_online_bandit_active,
        router_is_exploration=router_is_exploration,
        router_exploration_probability=router_exploration_probability,
        router_fallback_applied=router_fallback_applied,
        router_fallback_reason=router_fallback_reason,
        router_online_bandit_reason=router_online_bandit_reason,
        docs_enabled_flag=docs_enabled_flag,
        docs_hit=docs_hit,
        hint_inject=hint_inject,
        embedding_enabled=embedding_enabled,
        embedding_runtime_provider=embedding_runtime_provider,
        embedding_strategy_mode=embedding_strategy_mode,
        embedding_semantic_rerank_applied=embedding_semantic_rerank_applied,
        embedding_similarity_mean=embedding_similarity_mean,
        embedding_similarity_max=embedding_similarity_max,
        embedding_rerank_ratio=embedding_rerank_ratio,
        embedding_cache_hit=embedding_cache_hit,
        embedding_fallback=embedding_fallback,
        parallel_time_budget_ms=parallel_time_budget_ms,
        embedding_time_budget_ms=embedding_time_budget_ms,
        chunk_semantic_time_budget_ms=chunk_semantic_time_budget_ms,
        xref_time_budget_ms=xref_time_budget_ms,
        parallel_docs_timed_out=parallel_docs_timed_out,
        parallel_worktree_timed_out=parallel_worktree_timed_out,
        embedding_time_budget_exceeded=embedding_time_budget_exceeded,
        embedding_adaptive_budget_applied=embedding_adaptive_budget_applied,
        chunk_semantic_time_budget_exceeded=(
            chunk_semantic_time_budget_exceeded
        ),
        chunk_semantic_fallback=chunk_semantic_fallback,
        chunk_guard_enabled=chunk_guard_enabled,
        chunk_guard_mode=chunk_guard_mode,
        chunk_guard_reason=chunk_guard_reason,
        chunk_guard_report_only=chunk_guard_report_only,
        chunk_guard_filtered_count=chunk_guard_filtered_count,
        chunk_guard_filter_ratio=chunk_guard_filter_ratio,
        chunk_guard_pairwise_conflict_count=(
            chunk_guard_pairwise_conflict_count
        ),
        chunk_guard_pairwise_conflict_density=(
            chunk_guard_pairwise_conflict_density
        ),
        chunk_guard_fallback=chunk_guard_fallback,
        chunk_guard_expectation=chunk_guard_expectation,
        xref_budget_exhausted=xref_budget_exhausted,
        slo_downgrade_signals=slo_downgrade_signals,
        decision_trace=decision_trace,
        evidence_insufficiency=evidence_insufficiency,
    )
    if comparison_lane:
        payload["comparison_lane"] = comparison_lane
    if include_case_details:
        payload.update(
            build_case_detail_payload(
                top_candidates=top_candidates,
                included_candidate_paths=included_candidate_paths,
                included_candidate_globs=included_candidate_globs,
                excluded_candidate_paths=excluded_candidate_paths,
                excluded_candidate_globs=excluded_candidate_globs,
                relevant_candidate_paths=relevant_candidate_paths,
                noise_candidate_paths=noise_candidate_paths,
                candidate_matches=candidate_matches,
                top_chunks=top_chunks,
                expected_hits=expected_hits,
                chunk_hits=chunk_hits,
        validation_tests=validation_tests,
        source_plan_evidence_summary=source_plan_evidence_summary,
        source_plan_card_summary=source_plan_card_summary,
        source_plan_failure_signal_summary=source_plan_failure_signal_summary,
        memory_latency_ms=memory_latency_ms,
        index_latency_ms=index_latency_ms,
                repomap_latency_ms=repomap_latency_ms,
                repomap_worktree_seed_count=repomap_worktree_seed_count,
                repomap_subgraph_seed_count=repomap_subgraph_seed_count,
                repomap_seed_candidates_count=repomap_seed_candidates_count,
                repomap_cache_hit=repomap_cache_hit,
                repomap_precompute_hit=repomap_precompute_hit,
                augment_latency_ms=augment_latency_ms,
                skills_latency_ms=skills_latency_ms,
                source_plan_latency_ms=source_plan_latency_ms,
                retrieval_context_chunk_count=retrieval_context_chunk_count,
                retrieval_context_coverage_ratio=retrieval_context_coverage_ratio,
                retrieval_context_char_count_mean=retrieval_context_char_count_mean,
                contextual_sidecar_parent_symbol_chunk_count=(
                    contextual_sidecar_parent_symbol_chunk_count
                ),
                contextual_sidecar_parent_symbol_coverage_ratio=(
                    contextual_sidecar_parent_symbol_coverage_ratio
                ),
                contextual_sidecar_reference_hint_chunk_count=(
                    contextual_sidecar_reference_hint_chunk_count
                ),
                contextual_sidecar_reference_hint_coverage_ratio=(
                    contextual_sidecar_reference_hint_coverage_ratio
                ),
                chunk_contract_fallback_count=chunk_contract_fallback_count,
                chunk_contract_skeleton_chunk_count=chunk_contract_skeleton_chunk_count,
                chunk_contract_fallback_ratio=chunk_contract_fallback_ratio,
                chunk_contract_skeleton_ratio=chunk_contract_skeleton_ratio,
                chunk_cache_contract_present=chunk_cache_contract_present,
                chunk_cache_contract_fingerprint_present=(
                    chunk_cache_contract_fingerprint_present
                ),
                chunk_cache_contract_metadata_aligned=(
                    chunk_cache_contract_metadata_aligned
                ),
                chunk_cache_contract_file_count=chunk_cache_contract_file_count,
                chunk_cache_contract_chunk_count=chunk_cache_contract_chunk_count,
                unsupported_language_fallback_count=unsupported_language_fallback_count,
                unsupported_language_fallback_ratio=unsupported_language_fallback_ratio,
                subgraph_payload_enabled=subgraph_payload_enabled,
                subgraph_payload=subgraph_payload,
                subgraph_seed_path_count=subgraph_seed_path_count,
                subgraph_edge_type_count=subgraph_edge_type_count,
                subgraph_edge_total_count=subgraph_edge_total_count,
                subgraph_seed_paths=subgraph_seed_paths,
                subgraph_edge_counts=subgraph_edge_counts,
                skills_selected_count=skills_selected_count,
                skills_token_budget=skills_token_budget,
                skills_token_budget_used=skills_token_budget_used,
                skills_token_budget_utilization_ratio=skills_token_budget_utilization_ratio,
                skills_budget_exhausted=skills_budget_exhausted,
                skills_skipped_for_budget_count=skills_skipped_for_budget_count,
                skills_payload=skills_payload,
                skills_metadata_only_routing=skills_metadata_only_routing,
                skills_route_latency_ms=skills_route_latency_ms,
                skills_hydration_latency_ms=skills_hydration_latency_ms,
                plan_replay_cache_enabled=plan_replay_cache_enabled,
                plan_replay_cache_hit=plan_replay_cache_hit,
                plan_replay_cache_stale_hit_safe=plan_replay_cache_stale_hit_safe,
                plan_replay_cache_payload=plan_replay_cache_payload,
                chunk_stage_miss=chunk_stage_miss,
                slo_downgrade_signals=slo_downgrade_signals,
                parallel_time_budget_ms=parallel_time_budget_ms,
                embedding_time_budget_ms=embedding_time_budget_ms,
                chunk_semantic_time_budget_ms=chunk_semantic_time_budget_ms,
                xref_time_budget_ms=xref_time_budget_ms,
                chunk_guard_mode=chunk_guard_mode,
                chunk_guard_reason=chunk_guard_reason,
                chunk_guard_candidate_pool=chunk_guard_candidate_pool,
                chunk_guard_signed_chunk_count=chunk_guard_signed_chunk_count,
                chunk_guard_filtered_count=chunk_guard_filtered_count,
                chunk_guard_retained_count=chunk_guard_retained_count,
                chunk_guard_pairwise_conflict_count=chunk_guard_pairwise_conflict_count,
                chunk_guard_pairwise_conflict_density=chunk_guard_pairwise_conflict_density,
                chunk_guard_max_conflict_penalty=chunk_guard_max_conflict_penalty,
                chunk_guard_payload=chunk_guard_payload,
                chunk_guard_report_only=chunk_guard_report_only,
                chunk_guard_fallback=chunk_guard_fallback,
                chunk_guard_expectation=chunk_guard_expectation,
                robust_signature_count=robust_signature_count,
                robust_signature_coverage_ratio=robust_signature_coverage_ratio,
                graph_prior_chunk_count=graph_prior_chunk_count,
                graph_prior_coverage_ratio=graph_prior_coverage_ratio,
                graph_prior_total=graph_prior_total,
                graph_seeded_chunk_count=graph_seeded_chunk_count,
                graph_transfer_count=graph_transfer_count,
                graph_transfer_per_seed_ratio=graph_transfer_per_seed_ratio,
                graph_hub_suppressed_chunk_count=graph_hub_suppressed_chunk_count,
                graph_hub_penalty_total=graph_hub_penalty_total,
                topological_shield_enabled=topological_shield_enabled,
                topological_shield_mode=topological_shield_mode,
                topological_shield_report_only=topological_shield_report_only,
                topological_shield_max_attenuation=topological_shield_max_attenuation,
                topological_shield_shared_parent_attenuation=(
                    topological_shield_shared_parent_attenuation
                ),
                topological_shield_adjacency_attenuation=(
                    topological_shield_adjacency_attenuation
                ),
                topological_shield_attenuated_chunk_count=topological_shield_attenuated_chunk_count,
                topological_shield_coverage_ratio=topological_shield_coverage_ratio,
                topological_shield_attenuation_total=topological_shield_attenuation_total,
                topological_shield_attenuation_per_chunk=topological_shield_attenuation_per_chunk,
                graph_source_provider_loaded=graph_source_provider_loaded,
                graph_source_projection_fallback=graph_source_projection_fallback,
                graph_source_edge_count=graph_source_edge_count,
                graph_source_inbound_signal_chunk_count=(
                    graph_source_inbound_signal_chunk_count
                ),
                graph_source_inbound_signal_coverage_ratio=(
                    graph_source_inbound_signal_coverage_ratio
                ),
                graph_source_centrality_signal_chunk_count=(
                    graph_source_centrality_signal_chunk_count
                ),
                graph_source_centrality_signal_coverage_ratio=(
                    graph_source_centrality_signal_coverage_ratio
                ),
                graph_source_pagerank_signal_chunk_count=(
                    graph_source_pagerank_signal_chunk_count
                ),
                graph_source_pagerank_signal_coverage_ratio=(
                    graph_source_pagerank_signal_coverage_ratio
                ),
                graph_closure_enabled=graph_closure_enabled,
                graph_closure_boosted_chunk_count=graph_closure_boosted_chunk_count,
                graph_closure_coverage_ratio=graph_closure_coverage_ratio,
                graph_closure_anchor_count=graph_closure_anchor_count,
                graph_closure_support_edge_count=graph_closure_support_edge_count,
                graph_closure_total=graph_closure_total,
                multi_channel_rrf_enabled=multi_channel_rrf_enabled,
                multi_channel_rrf_applied=multi_channel_rrf_applied,
                multi_channel_rrf_granularity_count=(
                    multi_channel_rrf_granularity_count
                ),
                multi_channel_rrf_pool_size=multi_channel_rrf_pool_size,
                multi_channel_rrf_granularity_pool_ratio=(
                    multi_channel_rrf_granularity_pool_ratio
                ),
                graph_lookup_enabled=graph_lookup_enabled,
                graph_lookup_reason=graph_lookup_reason,
                graph_lookup_guarded=graph_lookup_guarded,
                graph_lookup_boosted_count=graph_lookup_boosted_count,
                graph_lookup_weight_scip=graph_lookup_weight_scip,
                graph_lookup_weight_xref=graph_lookup_weight_xref,
                graph_lookup_weight_query_xref=graph_lookup_weight_query_xref,
                graph_lookup_weight_symbol=graph_lookup_weight_symbol,
                graph_lookup_weight_import=graph_lookup_weight_import,
                graph_lookup_weight_coverage=graph_lookup_weight_coverage,
                graph_lookup_candidate_count=graph_lookup_candidate_count,
                graph_lookup_pool_size=graph_lookup_pool_size,
                graph_lookup_query_terms_count=graph_lookup_query_terms_count,
                graph_lookup_normalization=graph_lookup_normalization,
                graph_lookup_guard_max_candidates=graph_lookup_guard_max_candidates,
                graph_lookup_guard_min_query_terms=graph_lookup_guard_min_query_terms,
                graph_lookup_guard_max_query_terms=graph_lookup_guard_max_query_terms,
                graph_lookup_query_hit_paths=graph_lookup_query_hit_paths,
                graph_lookup_scip_signal_paths=graph_lookup_scip_signal_paths,
                graph_lookup_xref_signal_paths=graph_lookup_xref_signal_paths,
                graph_lookup_symbol_hit_paths=graph_lookup_symbol_hit_paths,
                graph_lookup_import_hit_paths=graph_lookup_import_hit_paths,
                graph_lookup_coverage_hit_paths=graph_lookup_coverage_hit_paths,
                graph_lookup_max_inbound=graph_lookup_max_inbound,
                graph_lookup_max_xref_count=graph_lookup_max_xref_count,
                graph_lookup_max_query_hits=graph_lookup_max_query_hits,
                graph_lookup_max_symbol_hits=graph_lookup_max_symbol_hits,
                graph_lookup_max_import_hits=graph_lookup_max_import_hits,
                graph_lookup_max_query_coverage=graph_lookup_max_query_coverage,
                graph_lookup_boosted_path_ratio=graph_lookup_boosted_path_ratio,
                graph_lookup_query_hit_path_ratio=graph_lookup_query_hit_path_ratio,
                source_plan_graph_closure_preference_enabled=(
                    source_plan_graph_closure_preference_enabled
                ),
                source_plan_graph_closure_bonus_candidate_count=(
                    source_plan_graph_closure_bonus_candidate_count
                ),
                source_plan_graph_closure_preferred_count=(
                    source_plan_graph_closure_preferred_count
                ),
                source_plan_granularity_preferred_count=(
                    source_plan_granularity_preferred_count
                ),
                source_plan_focused_file_promoted_count=(
                    source_plan_focused_file_promoted_count
                ),
                source_plan_packed_path_count=source_plan_packed_path_count,
                source_plan_packed_path_ratio=source_plan_packed_path_ratio,
                source_plan_chunk_retention_ratio=source_plan_chunk_retention_ratio,
                source_plan_packing_reason=source_plan_packing_reason,
            )
        )
    return payload


__all__ = ["evaluate_case_result"]
