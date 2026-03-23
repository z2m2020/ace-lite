"""Metrics and observability snapshot helpers for benchmark case evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.benchmark.case_evaluation_payloads import (
    compute_chunks_per_file_mean,
    count_unique_paths,
    extract_stage_latency_ms,
    extract_stage_observability,
    normalize_source_plan_evidence_summary,
    safe_ratio,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _graph_lookup_is_guarded(reason: Any) -> bool:
    normalized = str(reason or "").strip()
    return normalized in {
        "candidate_count_guarded",
        "query_terms_too_few",
        "query_terms_too_many",
    }


def _build_ltm_attribution_preview(attribution: list[Any], *, limit: int = 2) -> list[str]:
    preview: list[str] = []
    resolved_limit = max(1, int(limit or 2))
    for item in attribution:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or "").strip()
        graph_neighborhood = _as_dict(item.get("graph_neighborhood"))
        graph_triples = _as_list(graph_neighborhood.get("triples"))
        graph_preview = ""
        for triple in graph_triples:
            if not isinstance(triple, dict):
                continue
            edge = " ".join(
                value
                for value in (
                    str(triple.get("subject") or "").strip(),
                    str(triple.get("predicate") or "").strip(),
                    str(triple.get("object") or "").strip(),
                )
                if value
            )
            if edge:
                graph_preview = edge
                break
        text = summary
        if graph_preview:
            text = f"{summary} | graph: {graph_preview}" if summary else graph_preview
        text = text.strip()
        if not text or text in preview:
            continue
        preview.append(text)
        if len(preview) >= resolved_limit:
            break
    return preview


@dataclass(frozen=True, slots=True)
class CaseEvaluationMetrics:
    source_plan_evidence_summary: dict[str, float]
    source_plan_card_summary: dict[str, Any]
    source_plan_failure_signal_summary: dict[str, Any]
    skills_payload: dict[str, Any]
    plan_replay_cache_payload: dict[str, Any]
    subgraph_payload: dict[str, Any]
    subgraph_edge_counts: dict[str, Any]
    subgraph_seed_paths: list[str]
    chunk_guard_payload: dict[str, Any]
    validation_tests: list[Any]
    validation_probe_enabled: bool
    validation_probe_status: str
    validation_probe_executed_count: int
    validation_probe_issue_count: int
    source_plan_validation_feedback_present: bool
    source_plan_validation_feedback_status: str
    source_plan_validation_feedback_issue_count: int
    source_plan_validation_feedback_probe_status: str
    source_plan_validation_feedback_probe_issue_count: int
    source_plan_validation_feedback_probe_executed_count: int
    source_plan_validation_feedback_selected_test_count: int
    source_plan_validation_feedback_executed_test_count: int
    source_plan_failure_signal_origin: str
    source_plan_failure_signal_present: bool
    source_plan_failure_signal_status: str
    source_plan_failure_signal_issue_count: int
    source_plan_failure_signal_probe_status: str
    source_plan_failure_signal_probe_issue_count: int
    source_plan_failure_signal_probe_executed_count: int
    source_plan_failure_signal_selected_test_count: int
    source_plan_failure_signal_executed_test_count: int
    source_plan_failure_signal_has_failure: bool
    source_plan_evidence_card_count: int
    source_plan_file_card_count: int
    source_plan_chunk_card_count: int
    source_plan_validation_card_present: bool
    exact_search_payload: dict[str, Any]
    second_pass_payload: dict[str, Any]
    refine_pass_payload: dict[str, Any]
    candidate_ranker_fallbacks: list[str]
    neighbor_paths: list[str]
    dependency_recall: float
    repomap_latency_ms: float
    repomap_worktree_seed_count: int
    repomap_subgraph_seed_count: int
    repomap_seed_candidates_count: int
    repomap_cache_hit: bool
    repomap_precompute_hit: bool
    memory_latency_ms: float
    index_latency_ms: float
    augment_latency_ms: float
    skills_latency_ms: float
    source_plan_latency_ms: float
    notes_hit_ratio: float
    profile_selected_count: int
    capture_triggered: bool
    ltm_selected_count: int
    ltm_attribution_count: int
    ltm_graph_neighbor_count: int
    ltm_plan_constraint_count: int
    ltm_attribution_preview: list[str]
    feedback_enabled: bool
    feedback_reason: str
    feedback_event_count: int
    feedback_matched_event_count: int
    feedback_boosted_count: int
    feedback_boosted_paths: int
    multi_channel_rrf_enabled: bool
    multi_channel_rrf_applied: bool
    multi_channel_rrf_granularity_count: int
    multi_channel_rrf_pool_size: int
    multi_channel_rrf_granularity_pool_ratio: float
    graph_lookup_enabled: bool
    graph_lookup_reason: str
    graph_lookup_guarded: bool
    graph_lookup_boosted_count: int
    graph_lookup_weight_scip: float
    graph_lookup_weight_xref: float
    graph_lookup_weight_query_xref: float
    graph_lookup_weight_symbol: float
    graph_lookup_weight_import: float
    graph_lookup_weight_coverage: float
    graph_lookup_candidate_count: int
    graph_lookup_pool_size: int
    graph_lookup_query_terms_count: int
    graph_lookup_normalization: str
    graph_lookup_guard_max_candidates: int
    graph_lookup_guard_min_query_terms: int
    graph_lookup_guard_max_query_terms: int
    graph_lookup_query_hit_paths: int
    graph_lookup_scip_signal_paths: int
    graph_lookup_xref_signal_paths: int
    graph_lookup_symbol_hit_paths: int
    graph_lookup_import_hit_paths: int
    graph_lookup_coverage_hit_paths: int
    graph_lookup_max_inbound: float
    graph_lookup_max_xref_count: float
    graph_lookup_max_query_hits: float
    graph_lookup_max_symbol_hits: float
    graph_lookup_max_import_hits: float
    graph_lookup_max_query_coverage: float
    graph_lookup_boosted_path_ratio: float
    graph_lookup_query_hit_path_ratio: float
    native_scip_loaded: bool
    native_scip_document_count: int
    native_scip_definition_occurrence_count: int
    native_scip_reference_occurrence_count: int
    native_scip_symbol_definition_count: int
    embedding_enabled: bool
    embedding_fallback: bool
    embedding_cache_hit: bool
    embedding_rerank_ratio: float
    embedding_similarity_mean: float
    embedding_similarity_max: float
    docs_backend_fallback_reason: str
    memory_gate_skipped: bool
    memory_gate_skip_reason: str
    memory_fallback_reason: str
    memory_namespace_fallback: str
    chunk_semantic_reason: str
    parallel_time_budget_ms: float
    embedding_time_budget_ms: float
    chunk_semantic_time_budget_ms: float
    xref_time_budget_ms: float
    parallel_docs_timed_out: bool
    parallel_worktree_timed_out: bool
    embedding_time_budget_exceeded: bool
    embedding_adaptive_budget_applied: bool
    chunk_semantic_time_budget_exceeded: bool
    chunk_semantic_fallback: bool
    chunk_guard_candidate_pool: int
    chunk_guard_filtered_count: int
    chunk_guard_retained_count: int
    chunk_guard_signed_chunk_count: int
    chunk_guard_pairwise_conflict_count: int
    chunk_guard_max_conflict_penalty: float
    chunk_guard_mode: str
    chunk_guard_reason: str
    chunk_guard_enabled: bool
    chunk_guard_report_only: bool
    chunk_guard_fallback: bool
    chunk_guard_filter_ratio: float
    xref_budget_exhausted: bool
    chunk_budget_used: float
    chunks_per_file_mean: float
    retrieval_context_chunk_count: int
    retrieval_context_coverage_ratio: float
    retrieval_context_char_count_mean: float
    contextual_sidecar_parent_symbol_chunk_count: int
    contextual_sidecar_parent_symbol_coverage_ratio: float
    contextual_sidecar_reference_hint_chunk_count: int
    contextual_sidecar_reference_hint_coverage_ratio: float
    retrieval_context_pool_chunk_count: int
    retrieval_context_pool_coverage_ratio: float
    chunk_contract_fallback_count: int
    chunk_contract_skeleton_chunk_count: int
    chunk_contract_fallback_ratio: float
    chunk_contract_skeleton_ratio: float
    unsupported_language_fallback_count: int
    unsupported_language_fallback_ratio: float
    robust_signature_count: int
    robust_signature_coverage_ratio: float
    graph_prior_chunk_count: int
    graph_prior_coverage_ratio: float
    graph_prior_total: float
    graph_seeded_chunk_count: int
    graph_transfer_count: int
    graph_hub_suppressed_chunk_count: int
    graph_hub_penalty_total: float
    graph_closure_enabled: bool
    graph_closure_boosted_chunk_count: int
    graph_closure_coverage_ratio: float
    graph_closure_anchor_count: int
    graph_closure_support_edge_count: int
    graph_closure_total: float
    topological_shield_enabled: bool
    topological_shield_report_only: bool
    topological_shield_attenuated_chunk_count: int
    topological_shield_coverage_ratio: float
    topological_shield_attenuation_total: float
    skills_selected_count: float
    skills_skipped_for_budget_count: float
    skills_token_budget: float
    skills_token_budget_used: float
    skills_budget_exhausted: bool
    skills_route_latency_ms: float
    skills_hydration_latency_ms: float
    skills_metadata_only_routing: bool
    skills_precomputed_route: bool
    plan_replay_cache_enabled: bool
    plan_replay_cache_hit: bool
    plan_replay_cache_stale_hit_safe: bool
    source_plan_graph_closure_preference_enabled: bool
    source_plan_graph_closure_bonus_candidate_count: int
    source_plan_graph_closure_preferred_count: int
    source_plan_granularity_preferred_count: int
    source_plan_focused_file_promoted_count: int
    source_plan_packed_path_count: int
    source_plan_packing_reason: str
    source_plan_chunk_retention_ratio: float
    source_plan_packed_path_ratio: float
    skills_token_budget_utilization_ratio: float
    graph_transfer_per_seed_ratio: float
    chunk_guard_pairwise_conflict_density: float
    topological_shield_attenuation_per_chunk: float
    router_enabled: bool
    router_mode: str
    router_arm_set: str
    router_arm_id: str
    router_confidence: float
    router_shadow_arm_id: str
    router_shadow_source: str
    router_shadow_confidence: float
    router_online_bandit_requested: bool
    router_experiment_enabled: bool
    router_online_bandit_active: bool
    router_is_exploration: bool
    router_exploration_probability: float
    router_fallback_applied: bool
    router_fallback_reason: str
    router_online_bandit_reason: str
    policy_profile: str
    docs_enabled_flag: bool
    docs_hit: float
    hint_inject: float
    subgraph_seed_path_count: int
    subgraph_edge_type_count: int
    subgraph_edge_total_count: int
    subgraph_payload_enabled: bool


def build_case_evaluation_metrics(
    *,
    plan_payload: dict[str, Any],
    index_payload: dict[str, Any],
    index_metadata: dict[str, Any],
    source_plan_payload: dict[str, Any],
    candidate_files: list[Any],
    raw_candidate_chunks: list[dict[str, Any]],
    candidate_chunks: list[dict[str, Any]],
    source_plan_has_candidate_chunks: bool,
) -> CaseEvaluationMetrics:
    chunk_metrics = _as_dict(index_payload.get("chunk_metrics"))
    embeddings_payload = _as_dict(index_payload.get("embeddings"))
    docs_payload = _as_dict(index_payload.get("docs"))
    chunk_semantic_payload = _as_dict(index_payload.get("chunk_semantic_rerank"))
    topological_shield_payload = _as_dict(index_payload.get("topological_shield"))
    chunk_guard_payload = _as_dict(index_payload.get("chunk_guard"))
    chunk_contract_payload = _as_dict(index_payload.get("chunk_contract"))
    scip_payload = _as_dict(index_payload.get("scip"))
    parallel_payload = _as_dict(index_payload.get("parallel"))
    parallel_docs_payload = _as_dict(parallel_payload.get("docs"))
    parallel_worktree_payload = _as_dict(parallel_payload.get("worktree"))
    candidate_ranking_payload = _as_dict(index_payload.get("candidate_ranking"))
    adaptive_router_payload = _as_dict(index_payload.get("adaptive_router"))
    graph_lookup_payload = _as_dict(index_payload.get("graph_lookup"))
    exact_search_payload = _as_dict(candidate_ranking_payload.get("exact_search"))
    second_pass_payload = _as_dict(candidate_ranking_payload.get("second_pass"))
    refine_pass_payload = _as_dict(candidate_ranking_payload.get("refine_pass"))
    candidate_ranker_fallbacks = _as_list(candidate_ranking_payload.get("fallbacks"))
    augment_payload = _as_dict(plan_payload.get("augment"))
    xref_payload = _as_dict(augment_payload.get("xref"))

    stage_observability = extract_stage_observability(plan_payload)
    index_stage = _as_dict(stage_observability.get("index"))
    index_tags = _as_dict(index_stage.get("tags"))
    augment_stage = _as_dict(stage_observability.get("augment"))
    augment_tags = _as_dict(augment_stage.get("tags"))
    source_plan_stage = _as_dict(stage_observability.get("source_plan"))
    source_plan_tags = _as_dict(source_plan_stage.get("tags"))
    validation_stage = _as_dict(stage_observability.get("validation"))
    validation_tags = _as_dict(validation_stage.get("tags"))
    validation_payload = _as_dict(plan_payload.get("validation"))
    validation_probe_payload = _as_dict(
        validation_payload.get("probes")
        or _as_dict(_as_dict(validation_payload.get("result")).get("probes"))
    )

    source_plan_packing_payload = _as_dict(source_plan_payload.get("packing"))
    source_plan_subgraph_payload = _as_dict(source_plan_payload.get("subgraph_payload"))
    source_plan_evidence_summary = normalize_source_plan_evidence_summary(
        source_plan_payload.get("evidence_summary", {})
    )
    source_plan_card_summary = _as_dict(source_plan_payload.get("card_summary"))
    source_plan_steps = _as_list(source_plan_payload.get("steps"))
    validate_step = next(
        (
            item
            for item in source_plan_steps
            if isinstance(item, dict)
            and str(item.get("stage") or "").strip() == "validate"
        ),
        {},
    )
    source_plan_validation_feedback = _as_dict(
        _as_dict(validate_step).get("validation_feedback_summary")
    )
    source_plan_evidence_card_count = max(
        0,
        int(source_plan_card_summary.get("evidence_card_count", 0) or 0),
    )
    source_plan_file_card_count = max(
        0,
        int(source_plan_card_summary.get("file_card_count", 0) or 0),
    )
    source_plan_chunk_card_count = max(
        0,
        int(source_plan_card_summary.get("chunk_card_count", 0) or 0),
    )
    source_plan_validation_card_present = bool(
        source_plan_card_summary.get("validation_card_present", False)
    )
    skills_payload = _as_dict(plan_payload.get("skills"))
    repomap_payload = _as_dict(plan_payload.get("repomap"))
    index_subgraph_payload = _as_dict(index_payload.get("subgraph_payload"))
    subgraph_payload = (
        source_plan_subgraph_payload
        if source_plan_subgraph_payload
        else index_subgraph_payload
    )
    subgraph_edge_counts = _as_dict(subgraph_payload.get("edge_counts"))
    subgraph_seed_paths = _as_list(subgraph_payload.get("seed_paths"))
    subgraph_seed_path_count = len(
        [item for item in subgraph_seed_paths if str(item).strip()]
    )
    subgraph_edge_type_count = len(
        [
            key
            for key, value in subgraph_edge_counts.items()
            if str(key).strip() and int(value or 0) > 0
        ]
    )
    subgraph_edge_total_count = sum(
        max(0, int(value or 0)) for value in subgraph_edge_counts.values()
    )
    subgraph_payload_enabled = bool(subgraph_payload.get("enabled", False))
    validation_probe_enabled = bool(
        validation_tags.get(
            "validation_probe_enabled",
            validation_probe_payload.get("enabled", False),
        )
    )
    validation_probe_status = str(
        validation_tags.get(
            "validation_probe_status",
            validation_probe_payload.get("status", ""),
        )
        or ""
    )
    validation_probe_executed_count = max(
        0,
        int(
            validation_tags.get(
                "validation_probe_executed_count",
                validation_probe_payload.get("executed_count", 0),
            )
            or 0
        ),
    )
    validation_probe_issue_count = max(
        0,
        int(
            validation_tags.get(
                "validation_probe_issue_count",
                validation_probe_payload.get("issue_count", 0),
            )
            or 0
        ),
    )
    source_plan_validation_feedback_present = bool(source_plan_validation_feedback)
    source_plan_validation_feedback_status = str(
        source_plan_validation_feedback.get("status", "") or ""
    )
    source_plan_validation_feedback_issue_count = max(
        0,
        int(source_plan_validation_feedback.get("issue_count", 0) or 0),
    )
    source_plan_validation_feedback_probe_status = str(
        source_plan_validation_feedback.get("probe_status", "") or ""
    )
    source_plan_validation_feedback_probe_issue_count = max(
        0,
        int(source_plan_validation_feedback.get("probe_issue_count", 0) or 0),
    )
    source_plan_validation_feedback_probe_executed_count = max(
        0,
        int(source_plan_validation_feedback.get("probe_executed_count", 0) or 0),
    )
    source_plan_validation_feedback_selected_test_count = max(
        0,
        int(source_plan_validation_feedback.get("selected_test_count", 0) or 0),
    )
    source_plan_validation_feedback_executed_test_count = max(
        0,
        int(source_plan_validation_feedback.get("executed_test_count", 0) or 0),
    )

    dependency = _as_dict(repomap_payload.get("dependency_recall"))
    dependency_recall = float(dependency.get("hit_rate", 0.0) or 0.0)
    neighbor_paths = _as_list(repomap_payload.get("neighbor_paths"))
    repomap_latency_ms = extract_stage_latency_ms(plan_payload=plan_payload, stage="repomap")
    repomap_cache_payload = _as_dict(repomap_payload.get("cache"))
    repomap_precompute_payload = _as_dict(repomap_payload.get("precompute"))
    repomap_worktree_seed_count = max(
        0,
        int(
            repomap_payload.get(
                "worktree_seed_count",
                _as_dict(stage_observability.get("repomap")).get("tags", {}).get(
                    "worktree_seed_count", 0
                ),
            )
            or 0
        ),
    )
    repomap_subgraph_seed_count = max(
        0,
        int(
            repomap_payload.get(
                "subgraph_seed_count",
                _as_dict(stage_observability.get("repomap")).get("tags", {}).get(
                    "subgraph_seed_count", 0
                ),
            )
            or 0
        ),
    )
    repomap_seed_candidates_count = max(
        0,
        int(
            repomap_payload.get(
                "seed_candidates_count",
                _as_dict(stage_observability.get("repomap")).get("tags", {}).get(
                    "seed_candidates_count", 0
                ),
            )
            or 0
        ),
    )
    repomap_cache_hit = bool(
        repomap_cache_payload.get(
            "hit",
            _as_dict(stage_observability.get("repomap")).get("tags", {}).get(
                "cache_hit", False
            ),
        )
    )
    repomap_precompute_hit = bool(repomap_precompute_payload.get("hit", False))
    memory_latency_ms = extract_stage_latency_ms(plan_payload=plan_payload, stage="memory")
    index_latency_ms = extract_stage_latency_ms(plan_payload=plan_payload, stage="index")
    augment_latency_ms = extract_stage_latency_ms(plan_payload=plan_payload, stage="augment")
    skills_latency_ms = extract_stage_latency_ms(plan_payload=plan_payload, stage="skills")
    source_plan_latency_ms = extract_stage_latency_ms(
        plan_payload=plan_payload,
        stage="source_plan",
    )

    memory_payload = _as_dict(plan_payload.get("memory"))
    memory_gate_payload = _as_dict(memory_payload.get("gate"))
    memory_namespace_payload = _as_dict(memory_payload.get("namespace"))
    profile_payload = _as_dict(memory_payload.get("profile"))
    capture_payload = _as_dict(memory_payload.get("capture"))
    notes_payload = _as_dict(memory_payload.get("notes"))
    ltm_payload = _as_dict(memory_payload.get("ltm"))
    validation_tests = _as_list(source_plan_payload.get("validation_tests"))
    memory_count = max(0, int(memory_payload.get("count", 0) or 0))
    notes_selected_count = max(0, int(notes_payload.get("selected_count", 0) or 0))
    notes_hit_ratio = (
        float(notes_selected_count) / float(memory_count)
        if memory_count > 0
        else 0.0
    )
    profile_selected_count = max(
        0,
        int(profile_payload.get("selected_count", 0) or 0),
    )
    capture_triggered = bool(capture_payload.get("triggered", False))
    ltm_selected = _as_list(ltm_payload.get("selected"))
    ltm_attribution = _as_list(ltm_payload.get("attribution"))
    ltm_selected_count = max(
        0,
        int(ltm_payload.get("selected_count", len(ltm_selected)) or 0),
    )
    ltm_attribution_count = max(
        0,
        int(ltm_payload.get("attribution_count", len(ltm_attribution)) or 0),
    )
    ltm_graph_neighbor_count = sum(
        1
        for item in ltm_attribution
        if isinstance(item, dict)
        and isinstance(item.get("graph_neighborhood"), dict)
        and int(
            _as_dict(item.get("graph_neighborhood")).get("triple_count", 0) or 0
        )
        > 0
    )
    ltm_constraint_summary = _as_dict(source_plan_payload.get("ltm_constraint_summary"))
    ltm_plan_constraint_count = max(
        0,
        int(ltm_constraint_summary.get("constraint_count", 0) or 0),
    )
    ltm_attribution_preview = _build_ltm_attribution_preview(ltm_attribution)
    feedback_enabled = bool(candidate_ranking_payload.get("feedback_enabled", False))
    feedback_reason = str(candidate_ranking_payload.get("feedback_reason", "") or "").strip()
    feedback_event_count = max(
        0,
        int(candidate_ranking_payload.get("feedback_event_count", 0) or 0),
    )
    feedback_matched_event_count = max(
        0,
        int(candidate_ranking_payload.get("feedback_matched_event_count", 0) or 0),
    )
    feedback_boosted_count = max(
        0,
        int(candidate_ranking_payload.get("feedback_boosted_count", 0) or 0),
    )
    feedback_boosted_paths = max(
        0,
        int(candidate_ranking_payload.get("feedback_boosted_paths", 0) or 0),
    )
    multi_channel_rrf_enabled = bool(
        candidate_ranking_payload.get("multi_channel_rrf_enabled", False)
    )
    multi_channel_rrf_applied = bool(
        candidate_ranking_payload.get("multi_channel_rrf_applied", False)
    )
    multi_channel_rrf_granularity_count = max(
        0,
        int(
            candidate_ranking_payload.get(
                "multi_channel_rrf_granularity_count",
                index_metadata.get(
                    "multi_channel_rrf_granularity_count",
                    index_tags.get("multi_channel_rrf_granularity_count", 0),
                ),
            )
            or 0
        ),
    )
    multi_channel_rrf_pool_size = max(
        0,
        int(
            candidate_ranking_payload.get(
                "multi_channel_rrf_pool_size",
                index_metadata.get(
                    "multi_channel_rrf_pool_size",
                    index_tags.get("multi_channel_rrf_pool_size", 0),
                ),
            )
            or 0
        ),
    )
    multi_channel_rrf_granularity_pool_ratio = float(
        candidate_ranking_payload.get(
            "multi_channel_rrf_granularity_pool_ratio",
            index_metadata.get(
                "multi_channel_rrf_granularity_pool_ratio",
                index_tags.get("multi_channel_rrf_granularity_pool_ratio", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_enabled = bool(
        graph_lookup_payload.get(
            "enabled",
            candidate_ranking_payload.get(
                "graph_lookup_enabled",
                index_metadata.get("graph_lookup_enabled", False),
            ),
        )
    )
    graph_lookup_reason = str(
        graph_lookup_payload.get(
            "reason",
            candidate_ranking_payload.get(
                "graph_lookup_reason",
                index_metadata.get("graph_lookup_reason", ""),
            ),
        )
        or ""
    ).strip()
    graph_lookup_guarded = bool(
        graph_lookup_payload.get(
            "guarded",
            candidate_ranking_payload.get(
                "graph_lookup_guarded",
                index_metadata.get(
                    "graph_lookup_guarded",
                    _graph_lookup_is_guarded(graph_lookup_reason),
                ),
            ),
        )
    )
    graph_lookup_boosted_count = max(
        0,
        int(
            graph_lookup_payload.get(
                "boosted_count",
                candidate_ranking_payload.get(
                    "graph_lookup_boosted_count",
                    index_metadata.get("graph_lookup_boosted_count", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_weight_scip = float(
        candidate_ranking_payload.get(
            "graph_lookup_weight_scip",
            index_metadata.get("graph_lookup_weight_scip", 0.0),
        )
        or 0.0
    )
    graph_lookup_weight_xref = float(
        candidate_ranking_payload.get(
            "graph_lookup_weight_xref",
            index_metadata.get("graph_lookup_weight_xref", 0.0),
        )
        or 0.0
    )
    graph_lookup_weight_query_xref = float(
        candidate_ranking_payload.get(
            "graph_lookup_weight_query_xref",
            index_metadata.get("graph_lookup_weight_query_xref", 0.0),
        )
        or 0.0
    )
    graph_lookup_weight_symbol = float(
        candidate_ranking_payload.get(
            "graph_lookup_weight_symbol",
            index_metadata.get("graph_lookup_weight_symbol", 0.0),
        )
        or 0.0
    )
    graph_lookup_weight_import = float(
        candidate_ranking_payload.get(
            "graph_lookup_weight_import",
            index_metadata.get("graph_lookup_weight_import", 0.0),
        )
        or 0.0
    )
    graph_lookup_weight_coverage = float(
        candidate_ranking_payload.get(
            "graph_lookup_weight_coverage",
            index_metadata.get("graph_lookup_weight_coverage", 0.0),
        )
        or 0.0
    )
    graph_lookup_candidate_count = max(
        0,
        int(
            graph_lookup_payload.get(
                "candidate_count",
                candidate_ranking_payload.get(
                    "graph_lookup_candidate_count",
                    index_metadata.get("graph_lookup_candidate_count", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_pool_size = max(
        0,
        int(
            graph_lookup_payload.get(
                "pool_size",
                candidate_ranking_payload.get(
                    "graph_lookup_pool_size",
                    index_metadata.get("graph_lookup_pool_size", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_query_terms_count = max(
        0,
        int(
            graph_lookup_payload.get(
                "query_terms_count",
                candidate_ranking_payload.get(
                    "graph_lookup_query_terms_count",
                    index_metadata.get("graph_lookup_query_terms_count", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_normalization = str(
        graph_lookup_payload.get(
            "normalization",
            candidate_ranking_payload.get(
                "graph_lookup_normalization",
                index_metadata.get("graph_lookup_normalization", ""),
            ),
        )
        or ""
    ).strip()
    graph_lookup_guard_max_candidates = max(
        0,
        int(
            graph_lookup_payload.get(
                "guard_max_candidates",
                candidate_ranking_payload.get(
                    "graph_lookup_guard_max_candidates",
                    index_metadata.get("graph_lookup_guard_max_candidates", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_guard_min_query_terms = max(
        0,
        int(
            graph_lookup_payload.get(
                "guard_min_query_terms",
                candidate_ranking_payload.get(
                    "graph_lookup_guard_min_query_terms",
                    index_metadata.get("graph_lookup_guard_min_query_terms", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_guard_max_query_terms = max(
        0,
        int(
            graph_lookup_payload.get(
                "guard_max_query_terms",
                candidate_ranking_payload.get(
                    "graph_lookup_guard_max_query_terms",
                    index_metadata.get("graph_lookup_guard_max_query_terms", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_query_hit_paths = max(
        0,
        int(
            graph_lookup_payload.get(
                "query_hit_paths",
                candidate_ranking_payload.get(
                    "graph_lookup_query_hit_paths",
                    index_metadata.get("graph_lookup_query_hit_paths", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_scip_signal_paths = max(
        0,
        int(
            graph_lookup_payload.get(
                "scip_signal_paths",
                candidate_ranking_payload.get(
                    "graph_lookup_scip_signal_paths",
                    index_metadata.get("graph_lookup_scip_signal_paths", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_xref_signal_paths = max(
        0,
        int(
            graph_lookup_payload.get(
                "xref_signal_paths",
                candidate_ranking_payload.get(
                    "graph_lookup_xref_signal_paths",
                    index_metadata.get("graph_lookup_xref_signal_paths", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_symbol_hit_paths = max(
        0,
        int(
            graph_lookup_payload.get(
                "symbol_hit_paths",
                candidate_ranking_payload.get(
                    "graph_lookup_symbol_hit_paths",
                    index_metadata.get("graph_lookup_symbol_hit_paths", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_import_hit_paths = max(
        0,
        int(
            graph_lookup_payload.get(
                "import_hit_paths",
                candidate_ranking_payload.get(
                    "graph_lookup_import_hit_paths",
                    index_metadata.get("graph_lookup_import_hit_paths", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_coverage_hit_paths = max(
        0,
        int(
            graph_lookup_payload.get(
                "coverage_hit_paths",
                candidate_ranking_payload.get(
                    "graph_lookup_coverage_hit_paths",
                    index_metadata.get("graph_lookup_coverage_hit_paths", 0),
                ),
            )
            or 0
        ),
    )
    graph_lookup_max_inbound = float(
        graph_lookup_payload.get(
            "max_inbound",
            candidate_ranking_payload.get(
                "graph_lookup_max_inbound",
                index_metadata.get("graph_lookup_max_inbound", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_max_xref_count = float(
        graph_lookup_payload.get(
            "max_xref_count",
            candidate_ranking_payload.get(
                "graph_lookup_max_xref_count",
                index_metadata.get("graph_lookup_max_xref_count", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_max_query_hits = float(
        graph_lookup_payload.get(
            "max_query_hits",
            candidate_ranking_payload.get(
                "graph_lookup_max_query_hits",
                index_metadata.get("graph_lookup_max_query_hits", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_max_symbol_hits = float(
        graph_lookup_payload.get(
            "max_symbol_hits",
            candidate_ranking_payload.get(
                "graph_lookup_max_symbol_hits",
                index_metadata.get("graph_lookup_max_symbol_hits", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_max_import_hits = float(
        graph_lookup_payload.get(
            "max_import_hits",
            candidate_ranking_payload.get(
                "graph_lookup_max_import_hits",
                index_metadata.get("graph_lookup_max_import_hits", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_max_query_coverage = float(
        graph_lookup_payload.get(
            "max_query_coverage",
            candidate_ranking_payload.get(
                "graph_lookup_max_query_coverage",
                index_metadata.get("graph_lookup_max_query_coverage", 0.0),
            ),
        )
        or 0.0
    )
    graph_lookup_boosted_path_ratio = safe_ratio(
        graph_lookup_boosted_count,
        graph_lookup_pool_size,
    )
    graph_lookup_query_hit_path_ratio = safe_ratio(
        graph_lookup_query_hit_paths,
        graph_lookup_pool_size,
    )
    native_scip_provider = str(scip_payload.get("provider", "") or "").strip().lower()
    native_scip_loaded = bool(scip_payload.get("loaded", False)) and native_scip_provider == "scip"
    native_scip_document_count = (
        max(0, int(scip_payload.get("document_count", 0) or 0))
        if native_scip_loaded
        else 0
    )
    native_scip_definition_occurrence_count = (
        max(0, int(scip_payload.get("definition_occurrence_count", 0) or 0))
        if native_scip_loaded
        else 0
    )
    native_scip_reference_occurrence_count = (
        max(0, int(scip_payload.get("reference_occurrence_count", 0) or 0))
        if native_scip_loaded
        else 0
    )
    native_scip_symbol_definition_count = (
        max(0, int(scip_payload.get("symbol_definition_count", 0) or 0))
        if native_scip_loaded
        else 0
    )
    embedding_enabled = bool(embeddings_payload.get("enabled", False))
    embedding_fallback = bool(embeddings_payload.get("fallback", False))
    embedding_cache_hit = bool(embeddings_payload.get("cache_hit", False))
    embedding_rerank_pool = max(0, int(embeddings_payload.get("rerank_pool", 0) or 0))
    embedding_reranked_count = max(
        0,
        int(embeddings_payload.get("reranked_count", 0) or 0),
    )
    embedding_rerank_ratio = (
        float(embedding_reranked_count) / float(embedding_rerank_pool)
        if embedding_rerank_pool > 0
        else 0.0
    )
    embedding_similarity_mean = float(
        embeddings_payload.get("similarity_mean", 0.0) or 0.0
    )
    embedding_similarity_max = float(
        embeddings_payload.get("similarity_max", 0.0) or 0.0
    )
    docs_backend_fallback_reason = str(
        docs_payload.get("backend_fallback_reason", "") or ""
    ).strip()
    memory_fallback_reason = str(memory_payload.get("fallback_reason", "") or "").strip()
    memory_gate_skip_reason = str(
        memory_gate_payload.get("skip_reason", "") or ""
    ).strip()
    memory_namespace_fallback = str(
        memory_namespace_payload.get("fallback", "") or ""
    ).strip()
    chunk_semantic_reason = str(chunk_semantic_payload.get("reason", "") or "").strip()
    parallel_time_budget_ms = float(
        parallel_payload.get("time_budget_ms", index_tags.get("parallel_time_budget_ms", 0.0))
        or 0.0
    )
    embedding_time_budget_ms = float(
        embeddings_payload.get(
            "time_budget_ms",
            index_tags.get("embedding_time_budget_ms", 0.0),
        )
        or 0.0
    )
    chunk_semantic_time_budget_ms = float(
        chunk_semantic_payload.get(
            "time_budget_ms",
            index_tags.get("chunk_semantic_time_budget_ms", 0.0),
        )
        or 0.0
    )
    xref_time_budget_ms = float(
        xref_payload.get("time_budget_ms", augment_tags.get("xref_time_budget_ms", 0.0))
        or 0.0
    )
    parallel_docs_timed_out = bool(
        parallel_docs_payload.get(
            "timed_out",
            index_tags.get("parallel_docs_timed_out", False),
        )
    )
    parallel_worktree_timed_out = bool(
        parallel_worktree_payload.get(
            "timed_out",
            index_tags.get("parallel_worktree_timed_out", False),
        )
    )
    embedding_time_budget_exceeded = bool(
        embeddings_payload.get(
            "time_budget_exceeded",
            index_tags.get("embedding_time_budget_exceeded", False),
        )
    )
    embedding_adaptive_budget_applied = bool(
        embeddings_payload.get(
            "adaptive_budget_applied",
            index_tags.get("embedding_adaptive_budget_applied", False),
        )
    )
    chunk_semantic_time_budget_exceeded = bool(
        chunk_semantic_payload.get(
            "time_budget_exceeded",
            index_tags.get("chunk_semantic_time_budget_exceeded", False),
        )
    )
    chunk_semantic_fallback = bool(
        chunk_semantic_payload.get(
            "fallback",
            index_tags.get("chunk_semantic_fallback", False),
        )
    )
    chunk_guard_candidate_pool = max(
        0,
        int(
            chunk_guard_payload.get(
                "candidate_pool",
                index_tags.get("chunk_guard_candidate_pool", 0),
            )
            or 0
        ),
    )
    chunk_guard_filtered_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "filtered_count",
                index_tags.get("chunk_guard_filtered_count", 0),
            )
            or 0
        ),
    )
    chunk_guard_retained_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "retained_count",
                index_tags.get("chunk_guard_retained_count", 0),
            )
            or 0
        ),
    )
    chunk_guard_signed_chunk_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "signed_chunk_count",
                index_tags.get("chunk_guard_signed_chunk_count", 0),
            )
            or 0
        ),
    )
    chunk_guard_pairwise_conflict_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "pairwise_conflict_count",
                index_tags.get("chunk_guard_pairwise_conflict_count", 0),
            )
            or 0
        ),
    )
    chunk_guard_max_conflict_penalty = float(
        chunk_guard_payload.get(
            "max_conflict_penalty",
            index_tags.get("chunk_guard_max_conflict_penalty", 0.0),
        )
        or 0.0
    )
    chunk_guard_mode = str(
        chunk_guard_payload.get("mode", index_tags.get("chunk_guard_mode", "")) or ""
    ).strip()
    chunk_guard_reason = str(
        chunk_guard_payload.get("reason", index_tags.get("chunk_guard_reason", "")) or ""
    ).strip()
    chunk_guard_enabled = bool(
        chunk_guard_payload.get(
            "enabled",
            index_tags.get("chunk_guard_enabled", False),
        )
    )
    chunk_guard_report_only = bool(
        chunk_guard_payload.get(
            "report_only",
            index_tags.get("chunk_guard_report_only", False),
        )
    )
    chunk_guard_fallback = bool(
        chunk_guard_payload.get(
            "fallback",
            index_tags.get("chunk_guard_fallback", False),
        )
    )
    chunk_guard_filter_ratio = (
        float(chunk_guard_filtered_count) / float(chunk_guard_candidate_pool)
        if chunk_guard_candidate_pool > 0
        else 0.0
    )
    xref_budget_exhausted = bool(
        xref_payload.get(
            "budget_exhausted",
            augment_tags.get("xref_budget_exhausted", False),
        )
    )
    chunk_budget_used = float(
        source_plan_payload.get(
            "chunk_budget_used",
            chunk_metrics.get("chunk_budget_used", 0.0),
        )
        or 0.0
    )
    chunks_per_file_mean = (
        compute_chunks_per_file_mean(candidate_chunks)
        if source_plan_has_candidate_chunks
        else float(chunk_metrics.get("chunks_per_file_mean", 0.0) or 0.0)
    )
    raw_candidate_chunk_count = len(raw_candidate_chunks)
    chunk_contract_fallback_count = max(
        0,
        int(chunk_contract_payload.get("fallback_count", 0) or 0),
    )
    chunk_contract_skeleton_chunk_count = max(
        0,
        int(chunk_contract_payload.get("skeleton_chunk_count", 0) or 0),
    )
    chunk_contract_fallback_ratio = safe_ratio(
        chunk_contract_fallback_count,
        raw_candidate_chunk_count,
    )
    chunk_contract_skeleton_ratio = safe_ratio(
        chunk_contract_skeleton_chunk_count,
        raw_candidate_chunk_count,
    )
    unsupported_language_fallback_count = sum(
        1
        for item in raw_candidate_chunks
        if str(item.get("disclosure_fallback_reason") or "").strip()
        == "unsupported_language"
    )
    unsupported_language_fallback_ratio = safe_ratio(
        unsupported_language_fallback_count,
        raw_candidate_chunk_count,
    )
    retrieval_context_chunk_count = max(
        0,
        int(chunk_metrics.get("retrieval_context_chunk_count", 0.0) or 0),
    )
    retrieval_context_coverage_ratio = float(
        chunk_metrics.get("retrieval_context_coverage_ratio", 0.0) or 0.0
    )
    retrieval_context_char_count_mean = float(
        chunk_metrics.get("retrieval_context_char_count_mean", 0.0) or 0.0
    )
    contextual_sidecar_parent_symbol_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "contextual_sidecar_parent_symbol_chunk_count",
                index_tags.get("contextual_sidecar_parent_symbol_chunk_count", 0),
            )
            or 0
        ),
    )
    contextual_sidecar_parent_symbol_coverage_ratio = float(
        chunk_metrics.get(
            "contextual_sidecar_parent_symbol_coverage_ratio",
            index_tags.get(
                "contextual_sidecar_parent_symbol_coverage_ratio",
                0.0,
            ),
        )
        or 0.0
    )
    contextual_sidecar_reference_hint_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "contextual_sidecar_reference_hint_chunk_count",
                index_tags.get("contextual_sidecar_reference_hint_chunk_count", 0),
            )
            or 0
        ),
    )
    contextual_sidecar_reference_hint_coverage_ratio = float(
        chunk_metrics.get(
            "contextual_sidecar_reference_hint_coverage_ratio",
            index_tags.get(
                "contextual_sidecar_reference_hint_coverage_ratio",
                0.0,
            ),
        )
        or 0.0
    )
    retrieval_context_pool_chunk_count = max(
        0,
        int(
            chunk_semantic_payload.get("retrieval_context_pool_chunk_count", 0.0) or 0
        ),
    )
    retrieval_context_pool_coverage_ratio = float(
        chunk_semantic_payload.get("retrieval_context_pool_coverage_ratio", 0.0)
        or 0.0
    )
    robust_signature_count = max(
        0,
        int(
            chunk_metrics.get(
                "robust_signature_count",
                index_tags.get("robust_signature_count", 0),
            )
            or 0
        ),
    )
    robust_signature_coverage_ratio = float(
        chunk_metrics.get(
            "robust_signature_coverage_ratio",
            index_tags.get("robust_signature_coverage_ratio", 0.0),
        )
        or 0.0
    )
    graph_prior_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_prior_chunk_count",
                index_tags.get("graph_prior_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_prior_coverage_ratio = float(
        chunk_metrics.get(
            "graph_prior_coverage_ratio",
            index_tags.get("graph_prior_coverage_ratio", 0.0),
        )
        or 0.0
    )
    graph_prior_total = float(
        chunk_metrics.get(
            "graph_prior_total",
            index_tags.get("graph_prior_total", 0.0),
        )
        or 0.0
    )
    graph_seeded_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_seeded_chunk_count",
                index_tags.get("graph_seeded_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_transfer_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_transfer_count",
                index_tags.get("graph_transfer_count", 0),
            )
            or 0
        ),
    )
    graph_hub_suppressed_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_hub_suppressed_chunk_count",
                index_tags.get("graph_hub_suppressed_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_hub_penalty_total = float(
        chunk_metrics.get(
            "graph_hub_penalty_total",
            index_tags.get("graph_hub_penalty_total", 0.0),
        )
        or 0.0
    )
    graph_closure_enabled = bool(
        chunk_metrics.get(
            "graph_closure_enabled",
            index_tags.get("graph_closure_enabled", 0.0),
        )
    )
    graph_closure_boosted_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_closure_boosted_chunk_count",
                index_tags.get("graph_closure_boosted_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_closure_coverage_ratio = float(
        chunk_metrics.get(
            "graph_closure_coverage_ratio",
            index_tags.get("graph_closure_coverage_ratio", 0.0),
        )
        or 0.0
    )
    graph_closure_anchor_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_closure_anchor_count",
                index_tags.get("graph_closure_anchor_count", 0),
            )
            or 0
        ),
    )
    graph_closure_support_edge_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_closure_support_edge_count",
                index_tags.get("graph_closure_support_edge_count", 0),
            )
            or 0
        ),
    )
    graph_closure_total = float(
        chunk_metrics.get(
            "graph_closure_total",
            index_tags.get("graph_closure_total", 0.0),
        )
        or 0.0
    )
    topological_shield_enabled = bool(
        topological_shield_payload.get(
            "enabled",
            chunk_metrics.get("topological_shield_enabled", 0.0),
        )
    )
    topological_shield_report_only = bool(
        topological_shield_payload.get(
            "report_only",
            chunk_metrics.get("topological_shield_report_only", 0.0),
        )
    )
    topological_shield_attenuated_chunk_count = max(
        0,
        int(
            topological_shield_payload.get(
                "attenuated_chunk_count",
                chunk_metrics.get("topological_shield_attenuated_chunk_count", 0.0),
            )
            or 0
        ),
    )
    topological_shield_coverage_ratio = float(
        topological_shield_payload.get(
            "coverage_ratio",
            chunk_metrics.get("topological_shield_coverage_ratio", 0.0),
        )
        or 0.0
    )
    topological_shield_attenuation_total = float(
        topological_shield_payload.get(
            "attenuation_total",
            chunk_metrics.get("topological_shield_attenuation_total", 0.0),
        )
        or 0.0
    )
    selected_skills = _as_list(skills_payload.get("selected"))
    skipped_for_budget = _as_list(skills_payload.get("skipped_for_budget"))
    skills_selected_count = float(
        len([item for item in selected_skills if isinstance(item, dict)])
    )
    skills_skipped_for_budget_count = float(
        len([item for item in skipped_for_budget if isinstance(item, dict)])
    )
    skills_token_budget = float(skills_payload.get("token_budget", 0.0) or 0.0)
    skills_token_budget_used = float(
        skills_payload.get(
            "token_budget_used",
            skills_payload.get("selected_token_estimate_total", 0.0),
        )
        or 0.0
    )
    skills_budget_exhausted = bool(skills_payload.get("budget_exhausted", False))
    skills_route_latency_ms = float(skills_payload.get("route_latency_ms", 0.0) or 0.0)
    skills_hydration_latency_ms = float(
        skills_payload.get("hydration_latency_ms", 0.0) or 0.0
    )
    skills_metadata_only_routing = bool(
        skills_payload.get("metadata_only_routing", False)
    )
    skills_precomputed_route = (
        str(skills_payload.get("routing_source") or "").strip().lower() == "precomputed"
    )
    observability_payload = _as_dict(plan_payload.get("observability"))
    plan_replay_cache_payload = _as_dict(observability_payload.get("plan_replay_cache"))
    plan_replay_cache_enabled = bool(plan_replay_cache_payload.get("enabled", False))
    plan_replay_cache_hit = bool(plan_replay_cache_payload.get("hit", False))
    plan_replay_cache_stale_hit_safe = bool(
        plan_replay_cache_payload.get(
            "stale_hit_safe",
            plan_replay_cache_payload.get("safe_hit", False),
        )
    )
    source_plan_failure_signal_summary = _as_dict(
        plan_replay_cache_payload.get("failure_signal_summary")
    )
    source_plan_failure_signal_origin = "plan_replay_cache" if source_plan_failure_signal_summary else ""
    if not source_plan_failure_signal_summary:
        source_plan_failure_signal_summary = _as_dict(
            observability_payload.get("source_plan_failure_signal_summary")
        )
        source_plan_failure_signal_origin = (
            "observability" if source_plan_failure_signal_summary else ""
        )
    if not source_plan_failure_signal_summary:
        source_plan_failure_signal_summary = _as_dict(
            source_plan_payload.get("failure_signal_summary")
        )
        source_plan_failure_signal_origin = (
            "source_plan" if source_plan_failure_signal_summary else ""
        )
    if not source_plan_failure_signal_summary and source_plan_validation_feedback:
        source_plan_failure_signal_summary = dict(source_plan_validation_feedback)
        source_plan_failure_signal_origin = "validate_step"
    source_plan_failure_signal_present = bool(source_plan_failure_signal_summary)
    source_plan_failure_signal_status = str(
        source_plan_failure_signal_summary.get("status", "") or ""
    )
    source_plan_failure_signal_issue_count = max(
        0,
        int(source_plan_failure_signal_summary.get("issue_count", 0) or 0),
    )
    source_plan_failure_signal_probe_status = str(
        source_plan_failure_signal_summary.get("probe_status", "") or ""
    )
    source_plan_failure_signal_probe_issue_count = max(
        0,
        int(source_plan_failure_signal_summary.get("probe_issue_count", 0) or 0),
    )
    source_plan_failure_signal_probe_executed_count = max(
        0,
        int(source_plan_failure_signal_summary.get("probe_executed_count", 0) or 0),
    )
    source_plan_failure_signal_selected_test_count = max(
        0,
        int(source_plan_failure_signal_summary.get("selected_test_count", 0) or 0),
    )
    source_plan_failure_signal_executed_test_count = max(
        0,
        int(source_plan_failure_signal_summary.get("executed_test_count", 0) or 0),
    )
    source_plan_failure_signal_has_failure = bool(
        source_plan_failure_signal_summary.get("has_failure", False)
    )
    if source_plan_failure_signal_present and not source_plan_failure_signal_has_failure:
        source_plan_failure_signal_has_failure = bool(
            str(source_plan_failure_signal_status or "").strip().lower()
            in {"failed", "degraded", "timeout"}
            or str(source_plan_failure_signal_probe_status or "").strip().lower()
            in {"failed", "degraded", "timeout"}
            or source_plan_failure_signal_issue_count > 0
            or source_plan_failure_signal_probe_issue_count > 0
        )
    source_plan_graph_closure_preference_enabled = bool(
        source_plan_packing_payload.get(
            "graph_closure_preference_enabled",
            source_plan_tags.get("packing_graph_closure_preference_enabled", False),
        )
    )
    source_plan_graph_closure_bonus_candidate_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "graph_closure_bonus_candidate_count",
                source_plan_tags.get("packing_graph_closure_bonus_candidate_count", 0),
            )
            or 0
        ),
    )
    source_plan_graph_closure_preferred_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "graph_closure_preferred_count",
                source_plan_tags.get("packing_graph_closure_preferred_count", 0),
            )
            or 0
        ),
    )
    source_plan_granularity_preferred_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "granularity_preferred_count",
                source_plan_tags.get("packing_granularity_preferred_count", 0),
            )
            or 0
        ),
    )
    source_plan_focused_file_promoted_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "focused_file_promoted_count",
                source_plan_tags.get("packing_focused_file_promoted_count", 0),
            )
            or 0
        ),
    )
    source_plan_packed_path_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "packed_path_count",
                source_plan_tags.get("packing_packed_path_count", 0),
            )
            or 0
        ),
    )
    source_plan_packing_reason = str(
        source_plan_packing_payload.get(
            "reason",
            source_plan_tags.get("packing_reason", ""),
        )
        or ""
    )
    candidate_file_path_count = count_unique_paths(
        [item for item in candidate_files if isinstance(item, dict)]
    )
    effective_packed_path_count = (
        source_plan_packed_path_count
        if source_plan_packed_path_count > 0
        else (
            count_unique_paths(candidate_chunks)
            if source_plan_has_candidate_chunks
            else candidate_file_path_count
        )
    )
    source_plan_chunk_retention_ratio = safe_ratio(
        len(candidate_chunks),
        len(raw_candidate_chunks),
    )
    source_plan_packed_path_ratio = safe_ratio(
        effective_packed_path_count,
        candidate_file_path_count,
    )
    skills_token_budget_utilization_ratio = safe_ratio(
        skills_token_budget_used,
        skills_token_budget,
    )
    graph_transfer_per_seed_ratio = safe_ratio(
        graph_transfer_count,
        graph_seeded_chunk_count,
    )
    chunk_guard_pairwise_conflict_density = safe_ratio(
        chunk_guard_pairwise_conflict_count,
        chunk_guard_candidate_pool,
    )
    topological_shield_attenuation_per_chunk = safe_ratio(
        topological_shield_attenuation_total,
        topological_shield_attenuated_chunk_count,
    )
    router_enabled = bool(
        adaptive_router_payload.get(
            "enabled",
            index_metadata.get("router_enabled", index_tags.get("router_enabled", False)),
        )
    )
    router_mode = str(
        adaptive_router_payload.get(
            "mode",
            index_metadata.get("router_mode", index_tags.get("router_mode", "")),
        )
        or ""
    )
    router_arm_set = str(
        adaptive_router_payload.get(
            "arm_set",
            index_metadata.get("router_arm_set", index_tags.get("router_arm_set", "")),
        )
        or ""
    )
    router_arm_id = str(
        adaptive_router_payload.get(
            "arm_id",
            index_metadata.get("router_arm_id", index_tags.get("router_arm_id", "")),
        )
        or ""
    )
    router_confidence = float(
        adaptive_router_payload.get(
            "confidence",
            index_metadata.get("router_confidence", index_tags.get("router_confidence", 0.0)),
        )
        or 0.0
    )
    router_shadow_arm_id = str(
        adaptive_router_payload.get(
            "shadow_arm_id",
            index_metadata.get(
                "router_shadow_arm_id",
                index_tags.get("router_shadow_arm_id", ""),
            ),
        )
        or ""
    )
    router_shadow_source = str(
        adaptive_router_payload.get(
            "shadow_source",
            index_metadata.get(
                "router_shadow_source",
                index_tags.get("router_shadow_source", ""),
            ),
        )
        or ""
    )
    router_shadow_confidence = float(
        adaptive_router_payload.get(
            "shadow_confidence",
            index_metadata.get(
                "router_shadow_confidence",
                index_tags.get("router_shadow_confidence", 0.0),
            ),
        )
        or 0.0
    )
    router_online_bandit_payload = _as_dict(adaptive_router_payload.get("online_bandit"))
    router_online_bandit_requested = bool(
        router_online_bandit_payload.get(
            "requested",
            index_metadata.get(
                "router_online_bandit_requested",
                index_tags.get("router_online_bandit_requested", False),
            ),
        )
    )
    router_experiment_enabled = bool(
        router_online_bandit_payload.get(
            "experiment_enabled",
            index_metadata.get(
                "router_experiment_enabled",
                index_tags.get("router_experiment_enabled", False),
            ),
        )
    )
    router_online_bandit_active = bool(
        router_online_bandit_payload.get(
            "active",
            index_metadata.get(
                "router_online_bandit_active",
                index_tags.get("router_online_bandit_active", False),
            ),
        )
    )
    router_is_exploration = bool(
        router_online_bandit_payload.get(
            "is_exploration",
            index_metadata.get(
                "router_is_exploration",
                index_tags.get("router_is_exploration", False),
            ),
        )
    )
    router_exploration_probability = float(
        router_online_bandit_payload.get(
            "exploration_probability",
            index_metadata.get(
                "router_exploration_probability",
                index_tags.get("router_exploration_probability", 0.0),
            ),
        )
        or 0.0
    )
    router_fallback_applied = bool(
        router_online_bandit_payload.get(
            "fallback_applied",
            index_metadata.get(
                "router_fallback_applied",
                index_tags.get("router_fallback_applied", False),
            ),
        )
    )
    router_fallback_reason = str(
        router_online_bandit_payload.get(
            "fallback_reason",
            index_metadata.get(
                "router_fallback_reason",
                index_tags.get("router_fallback_reason", ""),
            ),
        )
        or ""
    )
    router_online_bandit_reason = str(
        router_online_bandit_payload.get(
            "reason",
            index_metadata.get(
                "router_online_bandit_reason",
                index_tags.get("router_online_bandit_reason", ""),
            ),
        )
        or ""
    )

    policy_profile = str(index_payload.get("policy_name") or "").strip()
    docs_enabled_flag = bool(
        index_metadata.get("docs_enabled", docs_payload.get("enabled", False))
    )
    docs_section_count = int(
        index_metadata.get("docs_section_count", docs_payload.get("section_count", 0)) or 0
    )
    docs_injected_count = int(index_metadata.get("docs_injected_count", 0) or 0)
    docs_hit = 1.0 if docs_enabled_flag and docs_section_count > 0 else 0.0
    hint_inject = 1.0 if docs_injected_count > 0 else 0.0

    return CaseEvaluationMetrics(
        source_plan_evidence_summary=source_plan_evidence_summary,
        source_plan_card_summary=source_plan_card_summary,
        source_plan_failure_signal_summary=source_plan_failure_signal_summary,
        skills_payload=skills_payload,
        plan_replay_cache_payload=plan_replay_cache_payload,
        subgraph_payload=subgraph_payload,
        subgraph_edge_counts=subgraph_edge_counts,
        subgraph_seed_paths=subgraph_seed_paths,
        chunk_guard_payload=chunk_guard_payload,
        validation_tests=validation_tests,
        validation_probe_enabled=validation_probe_enabled,
        validation_probe_status=validation_probe_status,
        validation_probe_executed_count=validation_probe_executed_count,
        validation_probe_issue_count=validation_probe_issue_count,
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
        source_plan_failure_signal_issue_count=source_plan_failure_signal_issue_count,
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
        source_plan_failure_signal_has_failure=source_plan_failure_signal_has_failure,
        source_plan_evidence_card_count=source_plan_evidence_card_count,
        source_plan_file_card_count=source_plan_file_card_count,
        source_plan_chunk_card_count=source_plan_chunk_card_count,
        source_plan_validation_card_present=source_plan_validation_card_present,
        exact_search_payload=exact_search_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        candidate_ranker_fallbacks=[
            str(item).strip() for item in candidate_ranker_fallbacks if str(item).strip()
        ],
        neighbor_paths=[str(item).strip() for item in neighbor_paths if str(item).strip()],
        dependency_recall=dependency_recall,
        repomap_latency_ms=repomap_latency_ms,
        repomap_worktree_seed_count=repomap_worktree_seed_count,
        repomap_subgraph_seed_count=repomap_subgraph_seed_count,
        repomap_seed_candidates_count=repomap_seed_candidates_count,
        repomap_cache_hit=repomap_cache_hit,
        repomap_precompute_hit=repomap_precompute_hit,
        memory_latency_ms=memory_latency_ms,
        index_latency_ms=index_latency_ms,
        augment_latency_ms=augment_latency_ms,
        skills_latency_ms=skills_latency_ms,
        source_plan_latency_ms=source_plan_latency_ms,
        notes_hit_ratio=notes_hit_ratio,
        profile_selected_count=profile_selected_count,
        capture_triggered=capture_triggered,
        ltm_selected_count=ltm_selected_count,
        ltm_attribution_count=ltm_attribution_count,
        ltm_graph_neighbor_count=ltm_graph_neighbor_count,
        ltm_plan_constraint_count=ltm_plan_constraint_count,
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
        embedding_enabled=embedding_enabled,
        embedding_fallback=embedding_fallback,
        embedding_cache_hit=embedding_cache_hit,
        embedding_rerank_ratio=embedding_rerank_ratio,
        embedding_similarity_mean=embedding_similarity_mean,
        embedding_similarity_max=embedding_similarity_max,
        docs_backend_fallback_reason=docs_backend_fallback_reason,
        memory_gate_skipped=bool(memory_gate_payload.get("skipped", False)),
        memory_gate_skip_reason=memory_gate_skip_reason,
        memory_fallback_reason=memory_fallback_reason,
        memory_namespace_fallback=memory_namespace_fallback,
        chunk_semantic_reason=chunk_semantic_reason,
        parallel_time_budget_ms=parallel_time_budget_ms,
        embedding_time_budget_ms=embedding_time_budget_ms,
        chunk_semantic_time_budget_ms=chunk_semantic_time_budget_ms,
        xref_time_budget_ms=xref_time_budget_ms,
        parallel_docs_timed_out=parallel_docs_timed_out,
        parallel_worktree_timed_out=parallel_worktree_timed_out,
        embedding_time_budget_exceeded=embedding_time_budget_exceeded,
        embedding_adaptive_budget_applied=embedding_adaptive_budget_applied,
        chunk_semantic_time_budget_exceeded=chunk_semantic_time_budget_exceeded,
        chunk_semantic_fallback=chunk_semantic_fallback,
        chunk_guard_candidate_pool=chunk_guard_candidate_pool,
        chunk_guard_filtered_count=chunk_guard_filtered_count,
        chunk_guard_retained_count=chunk_guard_retained_count,
        chunk_guard_signed_chunk_count=chunk_guard_signed_chunk_count,
        chunk_guard_pairwise_conflict_count=chunk_guard_pairwise_conflict_count,
        chunk_guard_max_conflict_penalty=chunk_guard_max_conflict_penalty,
        chunk_guard_mode=chunk_guard_mode,
        chunk_guard_reason=chunk_guard_reason,
        chunk_guard_enabled=chunk_guard_enabled,
        chunk_guard_report_only=chunk_guard_report_only,
        chunk_guard_fallback=chunk_guard_fallback,
        chunk_guard_filter_ratio=chunk_guard_filter_ratio,
        xref_budget_exhausted=xref_budget_exhausted,
        chunk_budget_used=chunk_budget_used,
        chunks_per_file_mean=chunks_per_file_mean,
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
        unsupported_language_fallback_count=unsupported_language_fallback_count,
        unsupported_language_fallback_ratio=unsupported_language_fallback_ratio,
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
        topological_shield_report_only=topological_shield_report_only,
        topological_shield_attenuated_chunk_count=topological_shield_attenuated_chunk_count,
        topological_shield_coverage_ratio=topological_shield_coverage_ratio,
        topological_shield_attenuation_total=topological_shield_attenuation_total,
        skills_selected_count=skills_selected_count,
        skills_skipped_for_budget_count=skills_skipped_for_budget_count,
        skills_token_budget=skills_token_budget,
        skills_token_budget_used=skills_token_budget_used,
        skills_budget_exhausted=skills_budget_exhausted,
        skills_route_latency_ms=skills_route_latency_ms,
        skills_hydration_latency_ms=skills_hydration_latency_ms,
        skills_metadata_only_routing=skills_metadata_only_routing,
        skills_precomputed_route=skills_precomputed_route,
        plan_replay_cache_enabled=plan_replay_cache_enabled,
        plan_replay_cache_hit=plan_replay_cache_hit,
        plan_replay_cache_stale_hit_safe=plan_replay_cache_stale_hit_safe,
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
        source_plan_packing_reason=source_plan_packing_reason,
        source_plan_chunk_retention_ratio=source_plan_chunk_retention_ratio,
        source_plan_packed_path_ratio=source_plan_packed_path_ratio,
        skills_token_budget_utilization_ratio=(
            skills_token_budget_utilization_ratio
        ),
        graph_transfer_per_seed_ratio=graph_transfer_per_seed_ratio,
        chunk_guard_pairwise_conflict_density=(
            chunk_guard_pairwise_conflict_density
        ),
        topological_shield_attenuation_per_chunk=(
            topological_shield_attenuation_per_chunk
        ),
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
        policy_profile=policy_profile,
        docs_enabled_flag=docs_enabled_flag,
        docs_hit=docs_hit,
        hint_inject=hint_inject,
        subgraph_seed_path_count=subgraph_seed_path_count,
        subgraph_edge_type_count=subgraph_edge_type_count,
        subgraph_edge_total_count=subgraph_edge_total_count,
        subgraph_payload_enabled=subgraph_payload_enabled,
    )


__all__ = ["CaseEvaluationMetrics", "build_case_evaluation_metrics"]
