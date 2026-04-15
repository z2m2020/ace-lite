from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ace_lite.benchmark.pq_overlay import resolve_benchmark_pq_003_overlay
from ace_lite.benchmark.report_cases import append_case_sections
from ace_lite.benchmark.report_metrics import (
    ALL_METRIC_ORDER,
    METRIC_ORDER,
    SLO_BUDGET_LIMIT_ORDER,
    SLO_SIGNAL_ORDER,
    STAGE_LATENCY_ORDER,
)
from ace_lite.benchmark.report_metrics import (
    format_metric as _format_metric,
)
from ace_lite.benchmark.report_metrics import (
    format_optional_metric as _format_optional_metric,
)
from ace_lite.benchmark.report_metrics import (
    normalize_metrics as _normalize_metrics,
)
from ace_lite.benchmark.report_observability import (
    append_adaptive_router_observability_summary,
    append_context_refine_summary,
    append_decision_observability_summary,
    append_evidence_insufficiency_summary,
    append_feedback_loop_summary,
    append_feedback_observability_summary,
    append_ltm_explainability_summary,
    append_missing_context_risk_summary,
    append_preference_observability_summary,
    append_retrieval_context_observability_summary,
    append_retrieval_control_plane_gate_summary,
    append_retrieval_default_strategy_summary,
    append_reward_log_summary,
    append_wave1_context_governance_summary,
    append_workload_taxonomy_summary,
    format_decision_event,
)
from ace_lite.benchmark.report_sections import (
    append_retrieval_frontier_gate_summary,
    append_validation_branch_gate_summary,
    append_validation_branch_summary,
)
from ace_lite.benchmark.report_summary import (
    copy_optional_summary_sections,
    get_nested_mapping,
    get_summary_mapping,
)
from ace_lite.cli_app.runtime_stats_enrichment_support import (
    attach_runtime_memory_ltm_signal_summary,
)


def _append_metrics_table(
    lines: list[str], title: str, metrics: dict[str, Any], *, signed: bool = False
) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for metric in METRIC_ORDER:
        lines.append(
            f"| {metric} | {_format_metric(metric, metrics.get(metric, 0.0), signed=signed)} |"
        )
    lines.append("")


def _append_source_plan_granularity_summary(
    lines: list[str], metrics: dict[str, Any]
) -> None:
    granularity_rows = (
        (
            "symbol",
            "source_plan_symbol_count_mean",
            "source_plan_symbol_ratio",
        ),
        (
            "signature",
            "source_plan_signature_count_mean",
            "source_plan_signature_ratio",
        ),
        (
            "skeleton",
            "source_plan_skeleton_count_mean",
            "source_plan_skeleton_ratio",
        ),
        (
            "robust_signature",
            "source_plan_robust_signature_count_mean",
            "source_plan_robust_signature_ratio",
        ),
    )
    if not any(
        float(metrics.get(count_metric, 0.0) or 0.0) > 0.0
        or float(metrics.get(ratio_metric, 0.0) or 0.0) > 0.0
        for _, count_metric, ratio_metric in granularity_rows
    ):
        return

    lines.append("## Source Plan Granularity Summary")
    lines.append("")
    lines.append(
        "- Evidence mix: direct={direct}, neighbor_context={neighbor}, hint_only={hint}".format(
            direct=_format_metric(
                "source_plan_direct_evidence_ratio",
                metrics.get("source_plan_direct_evidence_ratio", 0.0),
            ),
            neighbor=_format_metric(
                "source_plan_neighbor_context_ratio",
                metrics.get("source_plan_neighbor_context_ratio", 0.0),
            ),
            hint=_format_metric(
                "source_plan_hint_only_ratio",
                metrics.get("source_plan_hint_only_ratio", 0.0),
            ),
        )
    )
    lines.append(
        "- Packing granularity-preferred count mean: {value}".format(
            value=_format_metric(
                "source_plan_granularity_preferred_count_mean",
                metrics.get("source_plan_granularity_preferred_count_mean", 0.0),
            )
        )
    )
    lines.append("")
    lines.append("| Granularity | Count Mean | Ratio |")
    lines.append("| --- | ---: | ---: |")
    for label, count_metric, ratio_metric in granularity_rows:
        lines.append(
            "| "
            f"{label} | {_format_metric(count_metric, metrics.get(count_metric, 0.0))}"
            f" | {_format_metric(ratio_metric, metrics.get(ratio_metric, 0.0))} |"
        )
    lines.append("")


def _append_index_fusion_granularity_summary(
    lines: list[str], metrics: dict[str, Any]
) -> None:
    enabled_ratio = float(metrics.get("multi_channel_rrf_enabled_ratio", 0.0) or 0.0)
    applied_ratio = float(metrics.get("multi_channel_rrf_applied_ratio", 0.0) or 0.0)
    count_mean = float(
        metrics.get("multi_channel_rrf_granularity_count_mean", 0.0) or 0.0
    )
    case_ratio = float(
        metrics.get("multi_channel_rrf_granularity_case_ratio", 0.0) or 0.0
    )
    pool_ratio = float(
        metrics.get("multi_channel_rrf_granularity_pool_ratio", 0.0) or 0.0
    )
    pool_size_mean = float(
        metrics.get("multi_channel_rrf_pool_size_mean", 0.0) or 0.0
    )
    if (
        enabled_ratio <= 0.0
        and applied_ratio <= 0.0
        and count_mean <= 0.0
        and case_ratio <= 0.0
        and pool_ratio <= 0.0
        and pool_size_mean <= 0.0
    ):
        return

    lines.append("## Index Fusion Granularity Summary")
    lines.append("")
    lines.append(
        "- Channel enabled ratio: {enabled}; applied ratio: {applied}".format(
            enabled=_format_metric("multi_channel_rrf_enabled_ratio", enabled_ratio),
            applied=_format_metric("multi_channel_rrf_applied_ratio", applied_ratio),
        )
    )
    lines.append(
        "- Granularity channel case ratio: {case_ratio}; count mean: {count_mean}".format(
            case_ratio=_format_metric(
                "multi_channel_rrf_granularity_case_ratio", case_ratio
            ),
            count_mean=_format_metric(
                "multi_channel_rrf_granularity_count_mean", count_mean
            ),
        )
    )
    lines.append(
        "- Fusion pool size mean: {pool_size}; granularity/pool ratio: {pool_ratio}".format(
            pool_size=_format_metric("multi_channel_rrf_pool_size_mean", pool_size_mean),
            pool_ratio=_format_metric(
                "multi_channel_rrf_granularity_pool_ratio", pool_ratio
            ),
        )
    )
    lines.append("")


def _append_graph_lookup_summary(lines: list[str], metrics: dict[str, Any]) -> None:
    enabled_ratio = float(metrics.get("graph_lookup_enabled_ratio", 0.0) or 0.0)
    guarded_ratio = float(metrics.get("graph_lookup_guarded_ratio", 0.0) or 0.0)
    log_norm_ratio = float(metrics.get("graph_lookup_log_norm_ratio", 0.0) or 0.0)
    linear_norm_ratio = float(
        metrics.get("graph_lookup_linear_norm_ratio", 0.0) or 0.0
    )
    boosted_count_mean = float(
        metrics.get("graph_lookup_boosted_count_mean", 0.0) or 0.0
    )
    weight_scip_mean = float(metrics.get("graph_lookup_weight_scip_mean", 0.0) or 0.0)
    weight_xref_mean = float(metrics.get("graph_lookup_weight_xref_mean", 0.0) or 0.0)
    weight_query_xref_mean = float(
        metrics.get("graph_lookup_weight_query_xref_mean", 0.0) or 0.0
    )
    weight_symbol_mean = float(
        metrics.get("graph_lookup_weight_symbol_mean", 0.0) or 0.0
    )
    weight_import_mean = float(
        metrics.get("graph_lookup_weight_import_mean", 0.0) or 0.0
    )
    weight_coverage_mean = float(
        metrics.get("graph_lookup_weight_coverage_mean", 0.0) or 0.0
    )
    candidate_count_mean = float(
        metrics.get("graph_lookup_candidate_count_mean", 0.0) or 0.0
    )
    pool_size_mean = float(metrics.get("graph_lookup_pool_size_mean", 0.0) or 0.0)
    query_terms_mean = float(
        metrics.get("graph_lookup_query_terms_count_mean", 0.0) or 0.0
    )
    guard_max_candidates_mean = float(
        metrics.get("graph_lookup_guard_max_candidates_mean", 0.0) or 0.0
    )
    guard_min_query_terms_mean = float(
        metrics.get("graph_lookup_guard_min_query_terms_mean", 0.0) or 0.0
    )
    guard_max_query_terms_mean = float(
        metrics.get("graph_lookup_guard_max_query_terms_mean", 0.0) or 0.0
    )
    query_hit_mean = float(
        metrics.get("graph_lookup_query_hit_paths_mean", 0.0) or 0.0
    )
    boosted_ratio = float(
        metrics.get("graph_lookup_boosted_path_ratio", 0.0) or 0.0
    )
    query_hit_ratio = float(
        metrics.get("graph_lookup_query_hit_path_ratio", 0.0) or 0.0
    )
    scip_signal_mean = float(
        metrics.get("graph_lookup_scip_signal_paths_mean", 0.0) or 0.0
    )
    xref_signal_mean = float(
        metrics.get("graph_lookup_xref_signal_paths_mean", 0.0) or 0.0
    )
    symbol_hit_mean = float(
        metrics.get("graph_lookup_symbol_hit_paths_mean", 0.0) or 0.0
    )
    import_hit_mean = float(
        metrics.get("graph_lookup_import_hit_paths_mean", 0.0) or 0.0
    )
    coverage_hit_mean = float(
        metrics.get("graph_lookup_coverage_hit_paths_mean", 0.0) or 0.0
    )
    max_inbound_mean = float(metrics.get("graph_lookup_max_inbound_mean", 0.0) or 0.0)
    max_xref_count_mean = float(
        metrics.get("graph_lookup_max_xref_count_mean", 0.0) or 0.0
    )
    max_query_hits_mean = float(
        metrics.get("graph_lookup_max_query_hits_mean", 0.0) or 0.0
    )
    max_symbol_hits_mean = float(
        metrics.get("graph_lookup_max_symbol_hits_mean", 0.0) or 0.0
    )
    max_import_hits_mean = float(
        metrics.get("graph_lookup_max_import_hits_mean", 0.0) or 0.0
    )
    max_query_coverage_mean = float(
        metrics.get("graph_lookup_max_query_coverage_mean", 0.0) or 0.0
    )
    candidate_guard_ratio = float(
        metrics.get("graph_lookup_candidate_count_guard_ratio", 0.0) or 0.0
    )
    query_terms_too_few_ratio = float(
        metrics.get("graph_lookup_query_terms_too_few_ratio", 0.0) or 0.0
    )
    query_terms_too_many_ratio = float(
        metrics.get("graph_lookup_query_terms_too_many_ratio", 0.0) or 0.0
    )
    if (
        enabled_ratio <= 0.0
        and guarded_ratio <= 0.0
        and log_norm_ratio <= 0.0
        and linear_norm_ratio <= 0.0
        and boosted_count_mean <= 0.0
        and weight_scip_mean <= 0.0
        and weight_xref_mean <= 0.0
        and weight_query_xref_mean <= 0.0
        and weight_symbol_mean <= 0.0
        and weight_import_mean <= 0.0
        and weight_coverage_mean <= 0.0
        and candidate_count_mean <= 0.0
        and pool_size_mean <= 0.0
        and query_terms_mean <= 0.0
        and guard_max_candidates_mean <= 0.0
        and guard_min_query_terms_mean <= 0.0
        and guard_max_query_terms_mean <= 0.0
        and query_hit_mean <= 0.0
        and boosted_ratio <= 0.0
        and query_hit_ratio <= 0.0
        and scip_signal_mean <= 0.0
        and xref_signal_mean <= 0.0
        and symbol_hit_mean <= 0.0
        and import_hit_mean <= 0.0
        and coverage_hit_mean <= 0.0
        and max_inbound_mean <= 0.0
        and max_xref_count_mean <= 0.0
        and max_query_hits_mean <= 0.0
        and max_symbol_hits_mean <= 0.0
        and max_import_hits_mean <= 0.0
        and max_query_coverage_mean <= 0.0
        and candidate_guard_ratio <= 0.0
        and query_terms_too_few_ratio <= 0.0
        and query_terms_too_many_ratio <= 0.0
    ):
        return

    lines.append("## Graph Lookup Summary")
    lines.append("")
    lines.append(
        "- Enabled ratio: {enabled}; boosted count mean: {boosted}; pool size mean: {pool}".format(
            enabled=_format_metric("graph_lookup_enabled_ratio", enabled_ratio),
            boosted=_format_metric(
                "graph_lookup_boosted_count_mean", boosted_count_mean
            ),
            pool=_format_metric("graph_lookup_pool_size_mean", pool_size_mean),
        )
    )
    lines.append(
        "- Query terms mean: {terms}; query-hit mean: {hits}; boosted/pool ratio: {boosted_ratio}; query-hit/pool ratio: {hit_ratio}".format(
            terms=_format_metric(
                "graph_lookup_query_terms_count_mean", query_terms_mean
            ),
            hits=_format_metric("graph_lookup_query_hit_paths_mean", query_hit_mean),
            boosted_ratio=_format_metric(
                "graph_lookup_boosted_path_ratio", boosted_ratio
            ),
            hit_ratio=_format_metric(
                "graph_lookup_query_hit_path_ratio", query_hit_ratio
            ),
        )
    )
    lines.append(
        "- Normalization ratios: log1p={log1p}; linear={linear}".format(
            log1p=_format_metric("graph_lookup_log_norm_ratio", log_norm_ratio),
            linear=_format_metric("graph_lookup_linear_norm_ratio", linear_norm_ratio),
        )
    )
    lines.append(
        "- Weight means: scip={scip}; xref={xref}; query_xref={query}; symbol={symbol}; import={imports}; coverage={coverage}".format(
            scip=_format_metric("graph_lookup_weight_scip_mean", weight_scip_mean),
            xref=_format_metric("graph_lookup_weight_xref_mean", weight_xref_mean),
            query=_format_metric(
                "graph_lookup_weight_query_xref_mean", weight_query_xref_mean
            ),
            symbol=_format_metric(
                "graph_lookup_weight_symbol_mean", weight_symbol_mean
            ),
            imports=_format_metric(
                "graph_lookup_weight_import_mean", weight_import_mean
            ),
            coverage=_format_metric(
                "graph_lookup_weight_coverage_mean", weight_coverage_mean
            ),
        )
    )
    lines.append(
        "- Guard summary: guarded={guarded}; candidate_count_mean={candidate_count}; max_candidates_mean={max_candidates}; min_terms_mean={min_terms}; max_terms_mean={max_terms}".format(
            guarded=_format_metric("graph_lookup_guarded_ratio", guarded_ratio),
            candidate_count=_format_metric(
                "graph_lookup_candidate_count_mean", candidate_count_mean
            ),
            max_candidates=_format_metric(
                "graph_lookup_guard_max_candidates_mean",
                guard_max_candidates_mean,
            ),
            min_terms=_format_metric(
                "graph_lookup_guard_min_query_terms_mean",
                guard_min_query_terms_mean,
            ),
            max_terms=_format_metric(
                "graph_lookup_guard_max_query_terms_mean",
                guard_max_query_terms_mean,
            ),
        )
    )
    lines.append(
        "- Signal maxima mean: inbound={inbound}; xref={xref}; query={query}; symbol={symbol}; import={imports}; coverage={coverage}".format(
            inbound=_format_metric("graph_lookup_max_inbound_mean", max_inbound_mean),
            xref=_format_metric(
                "graph_lookup_max_xref_count_mean", max_xref_count_mean
            ),
            query=_format_metric(
                "graph_lookup_max_query_hits_mean", max_query_hits_mean
            ),
            symbol=_format_metric(
                "graph_lookup_max_symbol_hits_mean", max_symbol_hits_mean
            ),
            imports=_format_metric(
                "graph_lookup_max_import_hits_mean", max_import_hits_mean
            ),
            coverage=_format_metric(
                "graph_lookup_max_query_coverage_mean", max_query_coverage_mean
            ),
        )
    )
    lines.append(
        "- Guard reason ratios: candidate_count={candidate_count}; query_terms_too_few={too_few}; query_terms_too_many={too_many}".format(
            candidate_count=_format_metric(
                "graph_lookup_candidate_count_guard_ratio", candidate_guard_ratio
            ),
            too_few=_format_metric(
                "graph_lookup_query_terms_too_few_ratio",
                query_terms_too_few_ratio,
            ),
            too_many=_format_metric(
                "graph_lookup_query_terms_too_many_ratio",
                query_terms_too_many_ratio,
            ),
        )
    )
    lines.append(
        "- Signal paths mean: scip={scip}, xref={xref}, symbol={symbol}, import={imports}, coverage={coverage}".format(
            scip=_format_metric(
                "graph_lookup_scip_signal_paths_mean", scip_signal_mean
            ),
            xref=_format_metric(
                "graph_lookup_xref_signal_paths_mean", xref_signal_mean
            ),
            symbol=_format_metric(
                "graph_lookup_symbol_hit_paths_mean", symbol_hit_mean
            ),
            imports=_format_metric(
                "graph_lookup_import_hit_paths_mean", import_hit_mean
            ),
            coverage=_format_metric(
                "graph_lookup_coverage_hit_paths_mean", coverage_hit_mean
            ),
        )
    )
    lines.append("")


def _append_graph_context_source_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    metrics = _normalize_metrics(results.get("metrics"))
    provider_loaded_ratio = float(
        metrics.get("graph_source_provider_loaded_ratio", 0.0) or 0.0
    )
    projection_fallback_ratio = float(
        metrics.get("graph_source_projection_fallback_ratio", 0.0) or 0.0
    )
    edge_count_mean = float(metrics.get("graph_source_edge_count_mean", 0.0) or 0.0)
    inbound_count_mean = float(
        metrics.get("graph_source_inbound_signal_chunk_count_mean", 0.0) or 0.0
    )
    inbound_coverage_ratio = float(
        metrics.get("graph_source_inbound_signal_coverage_ratio", 0.0) or 0.0
    )
    centrality_count_mean = float(
        metrics.get("graph_source_centrality_signal_chunk_count_mean", 0.0) or 0.0
    )
    centrality_coverage_ratio = float(
        metrics.get("graph_source_centrality_signal_coverage_ratio", 0.0) or 0.0
    )
    pagerank_count_mean = float(
        metrics.get("graph_source_pagerank_signal_chunk_count_mean", 0.0) or 0.0
    )
    pagerank_coverage_ratio = float(
        metrics.get("graph_source_pagerank_signal_coverage_ratio", 0.0) or 0.0
    )
    if (
        provider_loaded_ratio <= 0.0
        and projection_fallback_ratio <= 0.0
        and edge_count_mean <= 0.0
        and inbound_count_mean <= 0.0
        and inbound_coverage_ratio <= 0.0
        and centrality_count_mean <= 0.0
        and centrality_coverage_ratio <= 0.0
        and pagerank_count_mean <= 0.0
        and pagerank_coverage_ratio <= 0.0
    ):
        return

    lines.append("## Graph Context Source Summary")
    lines.append("")
    lines.append(
        "- Source loaded ratio: {loaded}; projection fallback ratio: {fallback}; edge count mean: {edges}".format(
            loaded=_format_metric(
                "graph_source_provider_loaded_ratio",
                provider_loaded_ratio,
            ),
            fallback=_format_metric(
                "graph_source_projection_fallback_ratio",
                projection_fallback_ratio,
            ),
            edges=_format_metric("graph_source_edge_count_mean", edge_count_mean),
        )
    )
    lines.append(
        "- Inbound signal chunk count mean / coverage ratio: {count} / {ratio}".format(
            count=_format_metric(
                "graph_source_inbound_signal_chunk_count_mean",
                inbound_count_mean,
            ),
            ratio=_format_metric(
                "graph_source_inbound_signal_coverage_ratio",
                inbound_coverage_ratio,
            ),
        )
    )
    lines.append(
        "- Centrality signal chunk count mean / coverage ratio: {count} / {ratio}".format(
            count=_format_metric(
                "graph_source_centrality_signal_chunk_count_mean",
                centrality_count_mean,
            ),
            ratio=_format_metric(
                "graph_source_centrality_signal_coverage_ratio",
                centrality_coverage_ratio,
            ),
        )
    )
    lines.append(
        "- Pagerank signal chunk count mean / coverage ratio: {count} / {ratio}".format(
            count=_format_metric(
                "graph_source_pagerank_signal_chunk_count_mean",
                pagerank_count_mean,
            ),
            ratio=_format_metric(
                "graph_source_pagerank_signal_coverage_ratio",
                pagerank_coverage_ratio,
            ),
        )
    )
    lines.append("")


def _append_chunk_cache_contract_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("chunk_cache_contract_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics = _normalize_metrics(results.get("metrics"))

    present_ratio = float(
        summary.get(
            "present_case_rate",
            metrics.get("chunk_cache_contract_present_ratio", 0.0),
        )
        or 0.0
    )
    fingerprint_present_ratio = float(
        summary.get(
            "fingerprint_present_case_rate",
            metrics.get("chunk_cache_contract_fingerprint_present_ratio", 0.0),
        )
        or 0.0
    )
    metadata_aligned_ratio = float(
        summary.get(
            "metadata_aligned_case_rate",
            metrics.get("chunk_cache_contract_metadata_aligned_ratio", 0.0),
        )
        or 0.0
    )
    file_count_mean = float(
        summary.get(
            "file_count_mean",
            metrics.get("chunk_cache_contract_file_count_mean", 0.0),
        )
        or 0.0
    )
    chunk_count_mean = float(
        summary.get(
            "chunk_count_mean",
            metrics.get("chunk_cache_contract_chunk_count_mean", 0.0),
        )
        or 0.0
    )
    if (
        present_ratio <= 0.0
        and fingerprint_present_ratio <= 0.0
        and metadata_aligned_ratio <= 0.0
        and file_count_mean <= 0.0
        and chunk_count_mean <= 0.0
    ):
        return

    lines.append("## Chunk Cache Contract Summary")
    lines.append("")
    lines.append(
        "- Present ratio: {present}; fingerprint present ratio: {fingerprint}; metadata aligned ratio: {aligned}".format(
            present=_format_metric(
                "chunk_cache_contract_present_ratio",
                present_ratio,
            ),
            fingerprint=_format_metric(
                "chunk_cache_contract_fingerprint_present_ratio",
                fingerprint_present_ratio,
            ),
            aligned=_format_metric(
                "chunk_cache_contract_metadata_aligned_ratio",
                metadata_aligned_ratio,
            ),
        )
    )
    lines.append(
        "- File count mean: {files}; chunk count mean: {chunks}".format(
            files=_format_metric(
                "chunk_cache_contract_file_count_mean",
                file_count_mean,
            ),
            chunks=_format_metric(
                "chunk_cache_contract_chunk_count_mean",
                chunk_count_mean,
            ),
        )
    )
    lines.append("")


def _append_validation_probe_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("validation_probe_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics = _normalize_metrics(results.get("metrics"))

    validation_test_count = float(
        summary.get("validation_test_count", metrics.get("validation_test_count", 0.0))
        or 0.0
    )
    probe_enabled_ratio = float(
        summary.get(
            "probe_enabled_ratio",
            metrics.get("validation_probe_enabled_ratio", 0.0),
        )
        or 0.0
    )
    probe_executed_count_mean = float(
        summary.get(
            "probe_executed_count_mean",
            metrics.get("validation_probe_executed_count_mean", 0.0),
        )
        or 0.0
    )
    probe_failure_rate = float(
        summary.get(
            "probe_failure_rate",
            metrics.get("validation_probe_failure_rate", 0.0),
        )
        or 0.0
    )
    if (
        validation_test_count <= 0.0
        and probe_enabled_ratio <= 0.0
        and probe_executed_count_mean <= 0.0
        and probe_failure_rate <= 0.0
    ):
        return

    lines.append("## Validation Probe Summary")
    lines.append("")
    lines.append(
        "- Validation tests mean: {tests}; probe enabled ratio: {enabled}".format(
            tests=_format_metric("validation_test_count", validation_test_count),
            enabled=_format_metric(
                "validation_probe_enabled_ratio",
                probe_enabled_ratio,
            ),
        )
    )
    lines.append(
        "- Probe executed count mean: {executed}; failure rate: {failure}".format(
            executed=_format_metric(
                "validation_probe_executed_count_mean",
                probe_executed_count_mean,
            ),
            failure=_format_metric(
                "validation_probe_failure_rate",
                probe_failure_rate,
            ),
        )
    )
    lines.append("")


def _append_source_plan_card_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("source_plan_card_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics = _normalize_metrics(results.get("metrics"))
    evidence_card_count_mean = float(
        summary.get(
            "evidence_card_count_mean",
            metrics.get("source_plan_evidence_card_count_mean", 0.0),
        )
        or 0.0
    )
    file_card_count_mean = float(
        summary.get(
            "file_card_count_mean",
            metrics.get("source_plan_file_card_count_mean", 0.0),
        )
        or 0.0
    )
    chunk_card_count_mean = float(
        summary.get(
            "chunk_card_count_mean",
            metrics.get("source_plan_chunk_card_count_mean", 0.0),
        )
        or 0.0
    )
    validation_card_present_ratio = float(
        summary.get(
            "validation_card_present_ratio",
            metrics.get("source_plan_validation_card_present_ratio", 0.0),
        )
        or 0.0
    )
    if (
        evidence_card_count_mean <= 0.0
        and file_card_count_mean <= 0.0
        and chunk_card_count_mean <= 0.0
        and validation_card_present_ratio <= 0.0
    ):
        return

    lines.append("## Source Plan Card Summary")
    lines.append("")
    lines.append(
        "- Evidence/file/chunk card means: evidence={evidence}; file={file}; chunk={chunk}".format(
            evidence=_format_metric(
                "source_plan_evidence_card_count_mean",
                evidence_card_count_mean,
            ),
            file=_format_metric(
                "source_plan_file_card_count_mean",
                file_card_count_mean,
            ),
            chunk=_format_metric(
                "source_plan_chunk_card_count_mean",
                chunk_card_count_mean,
            ),
        )
    )
    lines.append(
        "- Validation card present ratio: {ratio}".format(
            ratio=_format_metric(
                "source_plan_validation_card_present_ratio",
                validation_card_present_ratio,
            )
        )
    )
    lines.append("")


def _append_source_plan_validation_feedback_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("source_plan_validation_feedback_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics = _normalize_metrics(results.get("metrics"))
    present_ratio = float(
        summary.get(
            "present_ratio",
            metrics.get("source_plan_validation_feedback_present_ratio", 0.0),
        )
        or 0.0
    )
    issue_count_mean = float(
        summary.get(
            "issue_count_mean",
            metrics.get("source_plan_validation_feedback_issue_count_mean", 0.0),
        )
        or 0.0
    )
    failure_rate = float(
        summary.get(
            "failure_rate",
            metrics.get("source_plan_validation_feedback_failure_rate", 0.0),
        )
        or 0.0
    )
    probe_issue_count_mean = float(
        summary.get(
            "probe_issue_count_mean",
            metrics.get(
                "source_plan_validation_feedback_probe_issue_count_mean", 0.0
            ),
        )
        or 0.0
    )
    probe_executed_count_mean = float(
        summary.get(
            "probe_executed_count_mean",
            metrics.get(
                "source_plan_validation_feedback_probe_executed_count_mean", 0.0
            ),
        )
        or 0.0
    )
    probe_failure_rate = float(
        summary.get(
            "probe_failure_rate",
            metrics.get(
                "source_plan_validation_feedback_probe_failure_rate", 0.0
            ),
        )
        or 0.0
    )
    selected_test_count_mean = float(
        summary.get(
            "selected_test_count_mean",
            metrics.get(
                "source_plan_validation_feedback_selected_test_count_mean", 0.0
            ),
        )
        or 0.0
    )
    executed_test_count_mean = float(
        summary.get(
            "executed_test_count_mean",
            metrics.get(
                "source_plan_validation_feedback_executed_test_count_mean", 0.0
            ),
        )
        or 0.0
    )
    if (
        present_ratio <= 0.0
        and issue_count_mean <= 0.0
        and failure_rate <= 0.0
        and probe_issue_count_mean <= 0.0
        and probe_executed_count_mean <= 0.0
        and probe_failure_rate <= 0.0
        and selected_test_count_mean <= 0.0
        and executed_test_count_mean <= 0.0
    ):
        return

    lines.append("## Source Plan Validation Feedback Summary")
    lines.append("")
    lines.append(
        "- Present ratio: {present}; issue count mean: {issues}; failure rate: {failure}".format(
            present=_format_metric(
                "source_plan_validation_feedback_present_ratio",
                present_ratio,
            ),
            issues=_format_metric(
                "source_plan_validation_feedback_issue_count_mean",
                issue_count_mean,
            ),
            failure=_format_metric(
                "source_plan_validation_feedback_failure_rate",
                failure_rate,
            ),
        )
    )
    lines.append(
        "- Probe issue count mean: {issues}; probe executed count mean: {executed}; probe failure rate: {failure}".format(
            issues=_format_metric(
                "source_plan_validation_feedback_probe_issue_count_mean",
                probe_issue_count_mean,
            ),
            executed=_format_metric(
                "source_plan_validation_feedback_probe_executed_count_mean",
                probe_executed_count_mean,
            ),
            failure=_format_metric(
                "source_plan_validation_feedback_probe_failure_rate",
                probe_failure_rate,
            ),
        )
    )
    lines.append(
        "- Selected test count mean: {selected}; executed test count mean: {executed}".format(
            selected=_format_metric(
                "source_plan_validation_feedback_selected_test_count_mean",
                selected_test_count_mean,
            ),
            executed=_format_metric(
                "source_plan_validation_feedback_executed_test_count_mean",
                executed_test_count_mean,
            ),
        )
    )
    lines.append("")


def _append_source_plan_failure_signal_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("source_plan_failure_signal_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics = _normalize_metrics(results.get("metrics"))
    present_ratio = float(
        summary.get(
            "present_ratio",
            metrics.get("source_plan_failure_signal_present_ratio", 0.0),
        )
        or 0.0
    )
    issue_count_mean = float(
        summary.get(
            "issue_count_mean",
            metrics.get("source_plan_failure_signal_issue_count_mean", 0.0),
        )
        or 0.0
    )
    failure_rate = float(
        summary.get(
            "failure_rate",
            metrics.get("source_plan_failure_signal_failure_rate", 0.0),
        )
        or 0.0
    )
    probe_issue_count_mean = float(
        summary.get(
            "probe_issue_count_mean",
            metrics.get("source_plan_failure_signal_probe_issue_count_mean", 0.0),
        )
        or 0.0
    )
    probe_executed_count_mean = float(
        summary.get(
            "probe_executed_count_mean",
            metrics.get("source_plan_failure_signal_probe_executed_count_mean", 0.0),
        )
        or 0.0
    )
    probe_failure_rate = float(
        summary.get(
            "probe_failure_rate",
            metrics.get("source_plan_failure_signal_probe_failure_rate", 0.0),
        )
        or 0.0
    )
    selected_test_count_mean = float(
        summary.get(
            "selected_test_count_mean",
            metrics.get("source_plan_failure_signal_selected_test_count_mean", 0.0),
        )
        or 0.0
    )
    executed_test_count_mean = float(
        summary.get(
            "executed_test_count_mean",
            metrics.get("source_plan_failure_signal_executed_test_count_mean", 0.0),
        )
        or 0.0
    )
    replay_cache_origin_ratio = float(
        summary.get(
            "replay_cache_origin_ratio",
            metrics.get("source_plan_failure_signal_replay_cache_origin_ratio", 0.0),
        )
        or 0.0
    )
    observability_origin_ratio = float(
        summary.get(
            "observability_origin_ratio",
            metrics.get(
                "source_plan_failure_signal_observability_origin_ratio", 0.0
            ),
        )
        or 0.0
    )
    source_plan_origin_ratio = float(
        summary.get(
            "source_plan_origin_ratio",
            metrics.get("source_plan_failure_signal_source_plan_origin_ratio", 0.0),
        )
        or 0.0
    )
    validate_step_origin_ratio = float(
        summary.get(
            "validate_step_origin_ratio",
            metrics.get("source_plan_failure_signal_validate_step_origin_ratio", 0.0),
        )
        or 0.0
    )
    if (
        present_ratio <= 0.0
        and issue_count_mean <= 0.0
        and failure_rate <= 0.0
        and probe_issue_count_mean <= 0.0
        and probe_executed_count_mean <= 0.0
        and probe_failure_rate <= 0.0
        and selected_test_count_mean <= 0.0
        and executed_test_count_mean <= 0.0
        and replay_cache_origin_ratio <= 0.0
        and observability_origin_ratio <= 0.0
        and source_plan_origin_ratio <= 0.0
        and validate_step_origin_ratio <= 0.0
    ):
        return

    lines.append("## Source Plan Failure Signal Summary")
    lines.append("")
    lines.append(
        "- Present ratio: {present}; issue count mean: {issues}; failure rate: {failure}".format(
            present=_format_metric(
                "source_plan_failure_signal_present_ratio",
                present_ratio,
            ),
            issues=_format_metric(
                "source_plan_failure_signal_issue_count_mean",
                issue_count_mean,
            ),
            failure=_format_metric(
                "source_plan_failure_signal_failure_rate",
                failure_rate,
            ),
        )
    )
    lines.append(
        "- Probe issue count mean: {issues}; probe executed count mean: {executed}; probe failure rate: {failure}".format(
            issues=_format_metric(
                "source_plan_failure_signal_probe_issue_count_mean",
                probe_issue_count_mean,
            ),
            executed=_format_metric(
                "source_plan_failure_signal_probe_executed_count_mean",
                probe_executed_count_mean,
            ),
            failure=_format_metric(
                "source_plan_failure_signal_probe_failure_rate",
                probe_failure_rate,
            ),
        )
    )
    lines.append(
        "- Selected test count mean: {selected}; executed test count mean: {executed}".format(
            selected=_format_metric(
                "source_plan_failure_signal_selected_test_count_mean",
                selected_test_count_mean,
            ),
            executed=_format_metric(
                "source_plan_failure_signal_executed_test_count_mean",
                executed_test_count_mean,
            ),
        )
    )
    lines.append(
        "- Origin ratios: replay_cache={replay}; observability={observability}; source_plan={source_plan}; validate_step={validate_step}".format(
            replay=_format_metric(
                "source_plan_failure_signal_replay_cache_origin_ratio",
                replay_cache_origin_ratio,
            ),
            observability=_format_metric(
                "source_plan_failure_signal_observability_origin_ratio",
                observability_origin_ratio,
            ),
            source_plan=_format_metric(
                "source_plan_failure_signal_source_plan_origin_ratio",
                source_plan_origin_ratio,
            ),
            validate_step=_format_metric(
                "source_plan_failure_signal_validate_step_origin_ratio",
                validate_step_origin_ratio,
            ),
        )
    )
    lines.append("")


def _append_learning_router_rollout_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("learning_router_rollout_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    case_count = int(summary.get("case_count", 0) or 0)
    lines.append("## Learning Router Rollout Summary")
    lines.append("")
    lines.append(
        "- Router enabled: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("router_enabled_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("router_enabled_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Shadow mode: {count}/{total} ({rate:.4f}); shadow-ready: {ready}/{total} ({ready_rate:.4f})".format(
            count=int(summary.get("shadow_mode_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("shadow_mode_case_rate", 0.0) or 0.0),
            ready=int(summary.get("shadow_ready_case_count", 0) or 0),
            ready_rate=float(summary.get("shadow_ready_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Source-plan cards present: {count}/{total} ({rate:.4f}); failure-signal blocked: {blocked}/{total} ({blocked_rate:.4f})".format(
            count=int(summary.get("source_plan_card_present_case_count", 0) or 0),
            total=case_count,
            rate=float(
                summary.get("source_plan_card_present_case_rate", 0.0) or 0.0
            ),
            blocked=int(summary.get("failure_signal_blocked_case_count", 0) or 0),
            blocked_rate=float(
                summary.get("failure_signal_blocked_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Guarded-rollout eligible: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("eligible_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("eligible_case_rate", 0.0) or 0.0),
        )
    )
    reason_counts_raw = summary.get("reason_counts")
    reason_counts: dict[str, Any] = (
        reason_counts_raw if isinstance(reason_counts_raw, dict) else {}
    )
    if reason_counts:
        formatted = ", ".join(
            f"{name}={int(count or 0)}"
            for name, count in sorted(
                reason_counts.items(),
                key=lambda item: (-int(item[1] or 0), str(item[0])),
            )
        )
        lines.append(f"- Reason counts: {formatted}")
    lines.append("")


def _append_deep_symbol_summary(lines: list[str], results: dict[str, Any]) -> None:
    metrics = _normalize_metrics(results.get("metrics"))
    summary_raw = results.get("deep_symbol_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    frontier_gate_raw = results.get("retrieval_frontier_gate_summary")
    frontier_gate: dict[str, Any] = (
        frontier_gate_raw if isinstance(frontier_gate_raw, dict) else {}
    )
    case_count = float(
        summary.get("case_count", metrics.get("deep_symbol_case_count", 0.0)) or 0.0
    )
    recall = float(
        summary.get(
            "recall",
            frontier_gate.get(
                "deep_symbol_case_recall",
                metrics.get("deep_symbol_case_recall", 0.0),
            ),
        )
        or 0.0
    )
    if case_count <= 0.0 and recall <= 0.0:
        return

    lines.append("## Deep Symbol Summary")
    lines.append("")
    lines.append(
        "- Deep symbol case count: {count}; recall: {recall}".format(
            count=_format_metric("deep_symbol_case_count", case_count),
            recall=_format_metric("deep_symbol_case_recall", recall),
        )
    )
    lines.append("")


def _append_native_scip_summary(lines: list[str], results: dict[str, Any]) -> None:
    metrics = _normalize_metrics(results.get("metrics"))
    summary_raw = results.get("native_scip_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    frontier_gate_raw = results.get("retrieval_frontier_gate_summary")
    frontier_gate: dict[str, Any] = (
        frontier_gate_raw if isinstance(frontier_gate_raw, dict) else {}
    )
    loaded_rate = float(
        summary.get(
            "loaded_rate",
            frontier_gate.get(
                "native_scip_loaded_rate",
                metrics.get("native_scip_loaded_rate", 0.0),
            ),
        )
        or 0.0
    )
    document_count_mean = float(
        summary.get(
            "document_count_mean",
            metrics.get("native_scip_document_count_mean", 0.0),
        )
        or 0.0
    )
    definition_occurrence_count_mean = float(
        summary.get(
            "definition_occurrence_count_mean",
            metrics.get("native_scip_definition_occurrence_count_mean", 0.0),
        )
        or 0.0
    )
    reference_occurrence_count_mean = float(
        summary.get(
            "reference_occurrence_count_mean",
            metrics.get("native_scip_reference_occurrence_count_mean", 0.0),
        )
        or 0.0
    )
    symbol_definition_count_mean = float(
        summary.get(
            "symbol_definition_count_mean",
            metrics.get("native_scip_symbol_definition_count_mean", 0.0),
        )
        or 0.0
    )
    if (
        loaded_rate <= 0.0
        and document_count_mean <= 0.0
        and definition_occurrence_count_mean <= 0.0
        and reference_occurrence_count_mean <= 0.0
        and symbol_definition_count_mean <= 0.0
    ):
        return

    lines.append("## Native SCIP Summary")
    lines.append("")
    lines.append(
        "- Native SCIP loaded rate: {value}".format(
            value=_format_metric("native_scip_loaded_rate", loaded_rate)
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    metric_rows = (
        ("native_scip_document_count_mean", document_count_mean),
        (
            "native_scip_definition_occurrence_count_mean",
            definition_occurrence_count_mean,
        ),
        (
            "native_scip_reference_occurrence_count_mean",
            reference_occurrence_count_mean,
        ),
        ("native_scip_symbol_definition_count_mean", symbol_definition_count_mean),
    )
    for metric, value in metric_rows:
        lines.append(
            f"| {metric} | {_format_metric(metric, value)} |"
        )
    lines.append("")


def _append_repomap_seed_summary(lines: list[str], results: dict[str, Any]) -> None:
    metrics = _normalize_metrics(results.get("metrics"))
    summary_raw = results.get("repomap_seed_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}

    worktree_seed_mean = float(
        summary.get(
            "worktree_seed_count_mean",
            metrics.get("repomap_worktree_seed_count_mean", 0.0),
        )
        or 0.0
    )
    subgraph_seed_mean = float(
        summary.get(
            "subgraph_seed_count_mean",
            metrics.get("repomap_subgraph_seed_count_mean", 0.0),
        )
        or 0.0
    )
    seed_candidates_mean = float(
        summary.get(
            "seed_candidates_count_mean",
            metrics.get("repomap_seed_candidates_count_mean", 0.0),
        )
        or 0.0
    )
    cache_hit_ratio = float(
        summary.get("cache_hit_ratio", metrics.get("repomap_cache_hit_ratio", 0.0))
        or 0.0
    )
    precompute_hit_ratio = float(
        summary.get(
            "precompute_hit_ratio",
            metrics.get("repomap_precompute_hit_ratio", 0.0),
        )
        or 0.0
    )
    if (
        worktree_seed_mean <= 0.0
        and subgraph_seed_mean <= 0.0
        and seed_candidates_mean <= 0.0
        and cache_hit_ratio <= 0.0
        and precompute_hit_ratio <= 0.0
    ):
        return

    lines.append("## Repomap Seed Summary")
    lines.append("")
    lines.append(
        "- Seed count means: worktree={worktree}; subgraph={subgraph}; seed_candidates={candidates}".format(
            worktree=_format_metric(
                "repomap_worktree_seed_count_mean", worktree_seed_mean
            ),
            subgraph=_format_metric(
                "repomap_subgraph_seed_count_mean", subgraph_seed_mean
            ),
            candidates=_format_metric(
                "repomap_seed_candidates_count_mean", seed_candidates_mean
            ),
        )
    )
    lines.append(
        "- Cache hit ratios: cache={cache}; precompute={precompute}".format(
            cache=_format_metric("repomap_cache_hit_ratio", cache_hit_ratio),
            precompute=_format_metric(
                "repomap_precompute_hit_ratio", precompute_hit_ratio
            ),
        )
    )
    lines.append("")


def _build_ltm_latency_alignment_summary(*, results: dict[str, Any]) -> dict[str, Any]:
    metrics = _normalize_metrics(results.get("metrics"))
    runtime_stats_summary_raw = results.get("runtime_stats_summary")
    runtime_stats_summary: dict[str, Any] = (
        runtime_stats_summary_raw if isinstance(runtime_stats_summary_raw, dict) else {}
    )
    memory_health_summary_raw = runtime_stats_summary.get("memory_health_summary")
    memory_health_summary: dict[str, Any] = (
        memory_health_summary_raw
        if isinstance(memory_health_summary_raw, dict)
        else {}
    )

    benchmark_ltm_latency_overhead_ms = float(
        metrics.get("ltm_latency_overhead_ms", 0.0) or 0.0
    )
    runtime_memory_stage_latency_ms_avg = float(
        memory_health_summary.get("memory_stage_latency_ms_avg", 0.0) or 0.0
    )
    has_runtime_reference = bool(memory_health_summary)
    has_benchmark_signal = benchmark_ltm_latency_overhead_ms > 0.0
    comparable = has_runtime_reference and runtime_memory_stage_latency_ms_avg > 0.0

    if not has_runtime_reference and not has_benchmark_signal:
        return {}

    return {
        "benchmark_ltm_latency_overhead_ms": benchmark_ltm_latency_overhead_ms,
        "runtime_memory_stage_latency_ms_avg": runtime_memory_stage_latency_ms_avg,
        "alignment_gap_ms": round(
            runtime_memory_stage_latency_ms_avg - benchmark_ltm_latency_overhead_ms,
            6,
        ),
        "benchmark_to_runtime_ratio": (
            round(
                benchmark_ltm_latency_overhead_ms
                / runtime_memory_stage_latency_ms_avg,
                6,
            )
            if comparable
            else 0.0
        ),
        "has_runtime_reference": has_runtime_reference,
        "has_benchmark_signal": has_benchmark_signal,
        "comparable": comparable,
    }


def _append_plugin_policy_summary(lines: list[str], summary: dict[str, Any]) -> None:
    totals_raw = summary.get("totals")
    totals: dict[str, Any] = totals_raw if isinstance(totals_raw, dict) else {}

    per_case_raw = summary.get("per_case_mean")
    per_case: dict[str, Any] = per_case_raw if isinstance(per_case_raw, dict) else {}

    mode_distribution_raw = summary.get("mode_distribution")
    mode_distribution: dict[str, Any] = (
        mode_distribution_raw if isinstance(mode_distribution_raw, dict) else {}
    )

    allowlist_raw = summary.get("allowlist")
    allowlist: list[Any] = allowlist_raw if isinstance(allowlist_raw, list) else []

    by_stage_raw = summary.get("by_stage")
    by_stage: list[Any] = by_stage_raw if isinstance(by_stage_raw, list) else []

    by_stage_per_case_raw = summary.get("by_stage_per_case_mean")
    by_stage_per_case_mean: list[Any] = (
        by_stage_per_case_raw if isinstance(by_stage_per_case_raw, list) else []
    )

    lines.append("## Plugin Policy Summary")
    lines.append("")
    lines.append(f"- Mode: {summary.get('mode', '') or '(none)'}")
    if allowlist:
        lines.append(f"- Allowlist: {', '.join(str(item) for item in allowlist)}")
    else:
        lines.append("- Allowlist: (none)")
    if mode_distribution:
        formatted = ", ".join(
            f"{mode!s}={int(count)}"
            for mode, count in sorted(mode_distribution.items())
        )
        lines.append(f"- Mode distribution: {formatted}")
    lines.append("")

    lines.append("### Totals")
    lines.append("")
    lines.append("| Counter | Value |")
    lines.append("| --- | ---: |")
    for key in ("applied", "conflicts", "blocked", "warn", "remote_applied"):
        lines.append(f"| {key} | {int(totals.get(key, 0) or 0)} |")
    lines.append("")

    lines.append("### Per-case Mean")
    lines.append("")
    lines.append("| Counter | Value |")
    lines.append("| --- | ---: |")
    for key in ("applied", "conflicts", "blocked", "warn", "remote_applied"):
        lines.append(f"| {key} | {float(per_case.get(key, 0.0) or 0.0):.4f} |")
    lines.append("")

    if by_stage:
        lines.append("### By-stage Totals")
        lines.append("")
        lines.append(
            "| Stage | applied | conflicts | blocked | warn | remote_applied |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for item in by_stage:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "").strip() or "(unknown)"
            lines.append(
                "| "
                f"{stage} | {int(item.get('applied', 0) or 0)}"
                f" | {int(item.get('conflicts', 0) or 0)}"
                f" | {int(item.get('blocked', 0) or 0)}"
                f" | {int(item.get('warn', 0) or 0)}"
                f" | {int(item.get('remote_applied', 0) or 0)} |"
            )
        lines.append("")

    if by_stage_per_case_mean:
        lines.append("### By-stage Per-case Mean")
        lines.append("")
        lines.append(
            "| Stage | applied | conflicts | blocked | warn | remote_applied |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for item in by_stage_per_case_mean:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "").strip() or "(unknown)"
            lines.append(
                "| "
                f"{stage} | {float(item.get('applied', 0.0) or 0.0):.4f}"
                f" | {float(item.get('conflicts', 0.0) or 0.0):.4f}"
                f" | {float(item.get('blocked', 0.0) or 0.0):.4f}"
                f" | {float(item.get('warn', 0.0) or 0.0):.4f}"
                f" | {float(item.get('remote_applied', 0.0) or 0.0):.4f} |"
            )
        lines.append("")


def _append_task_success_summary(lines: list[str], summary: dict[str, Any]) -> None:
    lines.append("## Task Success Summary")
    lines.append("")


def _append_comparison_lane_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("comparison_lane_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    lanes_raw = summary.get("lanes")
    lanes: list[Any] = lanes_raw if isinstance(lanes_raw, list) else []
    if not lanes:
        return

    lines.append("## Comparison Lanes")
    lines.append("")
    lines.append(
        "- Labeled cases: {labeled} / {total}".format(
            labeled=int(summary.get("labeled_case_count", 0) or 0),
            total=int(summary.get("total_case_count", 0) or 0),
        )
    )
    lines.append("")
    lines.append(
        "| Lane | Cases | Task Success | Recall@K | Report-only | Filtered Cases | Filtered Count Mean | Filter Ratio Mean | Retained Hit | Improved | Conflict Mean |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for item in lanes:
        if not isinstance(item, dict):
            continue
        lane = str(item.get("comparison_lane") or "").strip() or "(none)"
        lines.append(
            "| "
            f"{lane} | {int(item.get('case_count', 0) or 0)}"
            f" | {float(item.get('task_success_rate', 0.0) or 0.0):.4f}"
            f" | {float(item.get('recall_at_k', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_report_only_ratio', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_filtered_case_rate', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_filtered_count_mean', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_filter_ratio_mean', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_expected_retained_hit_rate_mean', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_report_only_improved_rate', 0.0) or 0.0):.4f}"
            f" | {float(item.get('chunk_guard_pairwise_conflict_count_mean', 0.0) or 0.0):.4f} |"
        )
    lines.append("")


def _append_runtime_stats_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary = get_summary_mapping(results=results, key="runtime_stats_summary")
    if not summary:
        return

    latest = get_nested_mapping(payload=summary, key="latest_match")
    scopes = get_nested_mapping(payload=summary, key="summary")
    preference_snapshot = get_nested_mapping(payload=summary, key="preference_snapshot")
    memory_health_summary = get_nested_mapping(payload=summary, key="memory_health_summary")
    ltm_explainability_summary = get_summary_mapping(
        results=results, key="ltm_explainability_summary"
    )
    if memory_health_summary and ltm_explainability_summary:
        memory_health_summary = attach_runtime_memory_ltm_signal_summary(
            memory_health_summary=memory_health_summary,
            ltm_explainability_summary=ltm_explainability_summary,
        )
    next_cycle_input_summary = get_nested_mapping(
        payload=summary, key="next_cycle_input_summary"
    )

    lines.append("## Runtime Stats Summary")
    lines.append("")
    lines.append(f"- DB path: {summary.get('db_path', '')}")
    if latest:
        lines.append(f"- Latest session: {latest.get('session_id', '')}")
        lines.append(f"- Latest repo: {latest.get('repo_key', '')}")
        profile = str(latest.get("profile_key") or "").strip()
        lines.append(f"- Latest profile: {profile or '(none)'}")
        lines.append(f"- Latest finished_at: {latest.get('finished_at', '')}")
    else:
        lines.append("- Latest match: (none)")
    lines.append("")
    lines.append("| Scope | Invocations | Success | Degraded | Failed | Avg Latency ms |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for scope_name in ("session", "all_time", "repo", "profile", "repo_profile"):
        item_raw = scopes.get(scope_name)
        item: dict[str, Any] = item_raw if isinstance(item_raw, dict) else {}
        if not item:
            continue
        counters = item.get("counters", {}) if isinstance(item.get("counters"), dict) else {}
        latency = item.get("latency", {}) if isinstance(item.get("latency"), dict) else {}
        lines.append(
            "| "
            f"{scope_name} | {int(counters.get('invocation_count', 0) or 0)}"
            f" | {int(counters.get('success_count', 0) or 0)}"
            f" | {int(counters.get('degraded_count', 0) or 0)}"
            f" | {int(counters.get('failure_count', 0) or 0)}"
            f" | {float(latency.get('latency_ms_avg', 0.0) or 0.0):.2f} |"
        )
    lines.append("")
    if memory_health_summary:
        lines.append("### Memory Health")
        lines.append("")
        lines.append(
            "- Scope: {scope}".format(
                scope=str(memory_health_summary.get("scope_kind") or "all_time")
            )
        )
        lines.append(
            "- Runtime memory events: {count}".format(
                count=int(memory_health_summary.get("runtime_event_count", 0) or 0)
            )
        )
        lines.append(
            "- Developer issues: {count} open={open_count} fixes={fix_count} resolution_rate={rate:.4f}".format(
                count=int(memory_health_summary.get("issue_count", 0) or 0),
                open_count=int(memory_health_summary.get("open_issue_count", 0) or 0),
                fix_count=int(memory_health_summary.get("fix_count", 0) or 0),
                rate=float(memory_health_summary.get("resolution_rate", 0.0) or 0.0),
            )
        )
        lines.append(
            "- Memory stage latency avg: {value:.2f} ms".format(
                value=float(
                    memory_health_summary.get("memory_stage_latency_ms_avg", 0.0) or 0.0
                )
            )
        )
        ltm_signal_summary_raw = memory_health_summary.get("ltm_signal_summary")
        ltm_signal_summary: dict[str, Any] = (
            ltm_signal_summary_raw
            if isinstance(ltm_signal_summary_raw, dict)
            else {}
        )
        if ltm_signal_summary:
            case_count = int(ltm_signal_summary.get("case_count", 0) or 0)
            lines.append(
                "- LTM signal coverage: feedback_cases={feedback_cases}/{total} ({feedback_rate:.4f}); attribution_cases={attribution_cases}/{total} ({attribution_rate:.4f})".format(
                    feedback_cases=int(
                        ltm_signal_summary.get("feedback_signal_observed_case_count", 0)
                        or 0
                    ),
                    total=case_count,
                    feedback_rate=float(
                        ltm_signal_summary.get("feedback_signal_observed_case_rate", 0.0)
                        or 0.0
                    ),
                    attribution_cases=int(
                        ltm_signal_summary.get(
                            "attribution_scope_observed_case_count", 0
                        )
                        or 0
                    ),
                    attribution_rate=float(
                        ltm_signal_summary.get(
                            "attribution_scope_observed_case_rate", 0.0
                        )
                        or 0.0
                    ),
                )
            )
        alignment_summary_raw = results.get("ltm_latency_alignment_summary")
        alignment_summary: dict[str, Any] = (
            alignment_summary_raw if isinstance(alignment_summary_raw, dict) else {}
        )
        if not alignment_summary:
            alignment_summary = _build_ltm_latency_alignment_summary(results=results)
        if alignment_summary:
            lines.append(
                "- Benchmark LTM latency overhead: {value:.2f} ms".format(
                    value=float(
                        alignment_summary.get("benchmark_ltm_latency_overhead_ms", 0.0)
                        or 0.0
                    )
                )
            )
            lines.append(
                "- Benchmark/runtime alignment gap: {value:.2f} ms".format(
                    value=float(alignment_summary.get("alignment_gap_ms", 0.0) or 0.0)
                )
            )
            lines.append(
                "- Benchmark/runtime ratio: {value:.4f}".format(
                    value=float(
                        alignment_summary.get("benchmark_to_runtime_ratio", 0.0) or 0.0
                    )
                )
            )
            lines.append(
                "- Alignment note: runtime memory stage latency is an operational reference, not the primary benchmark aggregation source"
            )
        lines.append("")
        if ltm_signal_summary:
            feedback_rows_raw = ltm_signal_summary.get("feedback_signals")
            feedback_rows = feedback_rows_raw if isinstance(feedback_rows_raw, list) else []
            lines.append("| LTM Signal | Cases | Case Rate | Total Count | Count Mean |")
            lines.append("| --- | ---: | ---: | ---: | ---: |")
            for item in feedback_rows:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| "
                    f"{str(item.get('feedback_signal') or '').strip() or '(unknown)'}"
                    f" | {int(item.get('case_count', 0) or 0)}"
                    f" | {float(item.get('case_rate', 0.0) or 0.0):.4f}"
                    f" | {int(item.get('total_count', 0) or 0)}"
                    f" | {float(item.get('count_mean', 0.0) or 0.0):.4f} |"
                )
            lines.append("")
            attribution_rows_raw = ltm_signal_summary.get("attribution_scopes")
            attribution_rows = (
                attribution_rows_raw if isinstance(attribution_rows_raw, list) else []
            )
            if attribution_rows:
                lines.append(
                    "| Attribution Scope | Cases | Case Rate | Total Count | Count Mean |"
                )
                lines.append("| --- | ---: | ---: | ---: | ---: |")
                for item in attribution_rows:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        "| "
                        f"{str(item.get('attribution_scope') or '').strip() or '(unknown)'}"
                        f" | {int(item.get('case_count', 0) or 0)}"
                        f" | {float(item.get('case_rate', 0.0) or 0.0):.4f}"
                        f" | {int(item.get('total_count', 0) or 0)}"
                        f" | {float(item.get('count_mean', 0.0) or 0.0):.4f} |"
                    )
                lines.append("")
        reason_rows_raw = memory_health_summary.get("reasons")
        reason_rows = reason_rows_raw if isinstance(reason_rows_raw, list) else []
        if reason_rows:
            lines.append(
                "| Reason | Runtime Events | Issues | Open Issues | Fixes | Last Seen |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
            for item in reason_rows:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| "
                    f"{str(item.get('reason_code') or '').strip() or '(unknown)'}"
                    f" | {int(item.get('runtime_event_count', 0) or 0)}"
                    f" | {int(item.get('manual_issue_count', 0) or 0)}"
                    f" | {int(item.get('open_issue_count', 0) or 0)}"
                    f" | {int(item.get('fix_count', 0) or 0)}"
                    f" | {str(item.get('last_seen_at') or '').strip() or '-'} |"
                )
            lines.append("")
    if next_cycle_input_summary:
        lines.append("### Next Cycle Input")
        lines.append("")
        lines.append(
            "- Primary stream: {value}".format(
                value=str(next_cycle_input_summary.get("primary_stream") or "(none)")
            )
        )
        lines.append(
            "- Priority count: {value}".format(
                value=int(next_cycle_input_summary.get("priority_count", 0) or 0)
            )
        )
        degraded_service_names = next_cycle_input_summary.get("degraded_service_names")
        if isinstance(degraded_service_names, list) and degraded_service_names:
            lines.append(
                "- Degraded services: {value}".format(
                    value=", ".join(str(item) for item in degraded_service_names)
                )
            )
        doctor_reason_codes = next_cycle_input_summary.get("doctor_reason_codes")
        if isinstance(doctor_reason_codes, list) and doctor_reason_codes:
            lines.append(
                "- Doctor reasons: {value}".format(
                    value=", ".join(str(item) for item in doctor_reason_codes)
                )
            )
        lines.append("")
        priority_rows = (
            next_cycle_input_summary.get("priorities")
            if isinstance(next_cycle_input_summary.get("priorities"), list)
            else []
        )
        if priority_rows:
            lines.append("| Reason | Family | Class | Total | Open | Fixes | Action |")
            lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
            for item in priority_rows:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| "
                    f"{str(item.get('reason_code') or '').strip() or '(unknown)'}"
                    f" | {str(item.get('reason_family') or '').strip() or '-'}"
                    f" | {str(item.get('capture_class') or '').strip() or '-'}"
                    f" | {int(item.get('total_count', 0) or 0)}"
                    f" | {int(item.get('open_issue_count', 0) or 0)}"
                    f" | {int(item.get('fix_count', 0) or 0)}"
                    f" | {str(item.get('action_hint') or '').strip() or '-'} |"
                )
            lines.append("")
        memory_focus_raw = next_cycle_input_summary.get("memory_focus")
        memory_focus: dict[str, Any] = (
            memory_focus_raw if isinstance(memory_focus_raw, dict) else {}
        )
        if memory_focus:
            lines.append(
                "- Memory focus: reasons={reasons} runtime_events={events} open_issues={open_issues} fixes={fixes} resolution_rate={rate:.4f}".format(
                    reasons=int(memory_focus.get("reason_count", 0) or 0),
                    events=int(memory_focus.get("runtime_event_count", 0) or 0),
                    open_issues=int(memory_focus.get("open_issue_count", 0) or 0),
                    fixes=int(memory_focus.get("fix_count", 0) or 0),
                    rate=float(memory_focus.get("resolution_rate", 0.0) or 0.0),
                )
            )
            lines.append(
                "- Memory action: {value}".format(
                    value=str(memory_focus.get("action_hint") or "-")
                )
            )
            lines.append("")
    if preference_snapshot:
        lines.append("### Preference Snapshot")
        lines.append("")
        preference_summary_raw = preference_snapshot.get(
            "preference_observability_summary"
        )
        preference_summary: dict[str, Any] = (
            preference_summary_raw
            if isinstance(preference_summary_raw, dict)
            else {}
        )
        if preference_summary:
            lines.append(
                "- Preference observed cases: {count}/{total} ({rate:.4f})".format(
                    count=int(preference_summary.get("observed_case_count", 0) or 0),
                    total=int(preference_summary.get("case_count", 0) or 0),
                    rate=float(preference_summary.get("observed_case_rate", 0.0) or 0.0),
                )
            )
            lines.append(
                "- Preference notes-hit mean: {value:.4f}".format(
                    value=float(
                        preference_summary.get("notes_hit_ratio_mean", 0.0) or 0.0
                    )
                )
            )
            lines.append(
                "- Preference profile-selected mean: {value:.4f}".format(
                    value=float(
                        preference_summary.get("profile_selected_count_mean", 0.0)
                        or 0.0
                    )
                )
            )
        feedback_summary_raw = preference_snapshot.get("feedback_observability_summary")
        feedback_summary: dict[str, Any] = (
            feedback_summary_raw if isinstance(feedback_summary_raw, dict) else {}
        )
        if feedback_summary:
            lines.append(
                "- Feedback boosted cases: {count}/{total} ({rate:.4f})".format(
                    count=int(feedback_summary.get("boosted_case_count", 0) or 0),
                    total=int(feedback_summary.get("case_count", 0) or 0),
                    rate=float(feedback_summary.get("boosted_case_rate", 0.0) or 0.0),
                )
            )
            lines.append(
                "- Feedback matched-event mean: {value:.4f}".format(
                    value=float(
                        feedback_summary.get("matched_event_count_mean", 0.0) or 0.0
                    )
                )
            )
            lines.append(
                "- Feedback boosted-candidate mean: {value:.4f}".format(
                    value=float(
                        feedback_summary.get("boosted_candidate_count_mean", 0.0)
                        or 0.0
                    )
                )
            )
        durable_summary_raw = preference_snapshot.get(
            "durable_preference_capture_summary"
        )
        durable_summary: dict[str, Any] = (
            durable_summary_raw if isinstance(durable_summary_raw, dict) else {}
        )
        if durable_summary:
            lines.append(
                "- Durable preference store: {path}".format(
                    path=str(durable_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable preference user_id: {durable_user}")
            lines.append(
                "- Durable preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_summary.get("distinct_target_path_count", 0) or 0
                    ),
                    weight=float(durable_summary.get("total_weight", 0.0) or 0.0),
                )
            )
            latest_created_at = str(durable_summary.get("latest_created_at") or "").strip()
            if latest_created_at:
                lines.append(
                    f"- Durable preference latest_created_at: {latest_created_at}"
            )
            lines.append("")
        durable_scoped_summary_raw = preference_snapshot.get(
            "durable_preference_capture_scoped_summary"
        )
        durable_scoped_summary: dict[str, Any] = (
            durable_scoped_summary_raw
            if isinstance(durable_scoped_summary_raw, dict)
            else {}
        )
        if durable_scoped_summary:
            lines.append(
                "- Durable preference scoped store: {path}".format(
                    path=str(durable_scoped_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_scoped_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable preference scoped user_id: {durable_user}")
            durable_profile = str(durable_scoped_summary.get("profile_key") or "").strip()
            if durable_profile:
                lines.append(
                    f"- Durable preference scoped profile_key: {durable_profile}"
                )
            lines.append(
                "- Durable preference scoped events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_scoped_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_scoped_summary.get("distinct_target_path_count", 0)
                        or 0
                    ),
                    weight=float(
                        durable_scoped_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_scoped_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    f"- Durable preference scoped latest_created_at: {latest_created_at}"
                )
            lines.append("")
        durable_retrieval_summary_raw = preference_snapshot.get(
            "durable_retrieval_preference_summary"
        )
        durable_retrieval_summary: dict[str, Any] = (
            durable_retrieval_summary_raw
            if isinstance(durable_retrieval_summary_raw, dict)
            else {}
        )
        if durable_retrieval_summary:
            lines.append(
                "- Durable retrieval-preference store: {path}".format(
                    path=str(durable_retrieval_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_retrieval_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable retrieval-preference user_id: {durable_user}")
            lines.append(
                "- Durable retrieval-preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_retrieval_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_retrieval_summary.get("distinct_target_path_count", 0)
                        or 0
                    ),
                    weight=float(
                        durable_retrieval_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_retrieval_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    f"- Durable retrieval-preference latest_created_at: {latest_created_at}"
                )
            lines.append("")
        durable_packing_summary_raw = preference_snapshot.get(
            "durable_packing_preference_summary"
        )
        durable_packing_summary: dict[str, Any] = (
            durable_packing_summary_raw
            if isinstance(durable_packing_summary_raw, dict)
            else {}
        )
        if durable_packing_summary:
            lines.append(
                "- Durable packing-preference store: {path}".format(
                    path=str(durable_packing_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_packing_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable packing-preference user_id: {durable_user}")
            lines.append(
                "- Durable packing-preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_packing_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_packing_summary.get("distinct_target_path_count", 0)
                        or 0
                    ),
                    weight=float(
                        durable_packing_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_packing_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    f"- Durable packing-preference latest_created_at: {latest_created_at}"
                )
            lines.append("")
        durable_validation_summary_raw = preference_snapshot.get(
            "durable_validation_preference_summary"
        )
        durable_validation_summary: dict[str, Any] = (
            durable_validation_summary_raw
            if isinstance(durable_validation_summary_raw, dict)
            else {}
        )
        if durable_validation_summary:
            lines.append(
                "- Durable validation-preference store: {path}".format(
                    path=str(durable_validation_summary.get("store_path") or "")
                )
            )
            durable_user = str(durable_validation_summary.get("user_id") or "").strip()
            if durable_user:
                lines.append(f"- Durable validation-preference user_id: {durable_user}")
            lines.append(
                "- Durable validation-preference events: {count} paths={paths} total_weight={weight:.4f}".format(
                    count=int(durable_validation_summary.get("event_count", 0) or 0),
                    paths=int(
                        durable_validation_summary.get(
                            "distinct_target_path_count", 0
                        )
                        or 0
                    ),
                    weight=float(
                        durable_validation_summary.get("total_weight", 0.0) or 0.0
                    ),
                )
            )
            latest_created_at = str(
                durable_validation_summary.get("latest_created_at") or ""
            ).strip()
            if latest_created_at:
                lines.append(
                    f"- Durable validation-preference latest_created_at: {latest_created_at}"
                )
            lines.append("")
        lines.append("")


def _append_agent_loop_control_plane_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("agent_loop_control_plane_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    case_count = int(summary.get("case_count", 0) or 0)
    if case_count <= 0:
        return

    lines.append("## Agent Loop Control Plane Summary")
    lines.append("")
    lines.append(
        "- Observed={observed}/{total} ({observed_rate:.4f}); enabled={enabled}/{total} ({enabled_rate:.4f}); attempted={attempted}/{total} ({attempted_rate:.4f}); replay_safe={replay_safe}/{total} ({replay_safe_rate:.4f})".format(
            observed=int(summary.get("observed_case_count", 0) or 0),
            total=case_count,
            observed_rate=float(summary.get("observed_case_rate", 0.0) or 0.0),
            enabled=int(summary.get("enabled_case_count", 0) or 0),
            enabled_rate=float(summary.get("enabled_case_rate", 0.0) or 0.0),
            attempted=int(summary.get("attempted_case_count", 0) or 0),
            attempted_rate=float(summary.get("attempted_case_rate", 0.0) or 0.0),
            replay_safe=int(summary.get("replay_safe_case_count", 0) or 0),
            replay_safe_rate=float(summary.get("replay_safe_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Actions mean: requested={requested:.4f}; executed={executed:.4f}; dominant_stop_reason={stop_reason}; dominant_policy={policy_id}".format(
            requested=float(summary.get("actions_requested_mean", 0.0) or 0.0),
            executed=float(summary.get("actions_executed_mean", 0.0) or 0.0),
            stop_reason=str(summary.get("dominant_stop_reason") or "(none)"),
            policy_id=str(summary.get("dominant_last_policy_id") or "(none)"),
        )
    )
    lines.append(
        "- Action coverage: more_context={more_context}/{total} ({more_context_rate:.4f}); source_plan_retry={source_plan_retry}/{total} ({source_plan_retry_rate:.4f}); validation_retry={validation_retry}/{total} ({validation_retry_rate:.4f})".format(
            more_context=int(summary.get("request_more_context_case_count", 0) or 0),
            total=case_count,
            more_context_rate=float(
                summary.get("request_more_context_case_rate", 0.0) or 0.0
            ),
            source_plan_retry=int(
                summary.get("request_source_plan_retry_case_count", 0) or 0
            ),
            source_plan_retry_rate=float(
                summary.get("request_source_plan_retry_case_rate", 0.0) or 0.0
            ),
            validation_retry=int(
                summary.get("request_validation_retry_case_count", 0) or 0
            ),
            validation_retry_rate=float(
                summary.get("request_validation_retry_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append("")


def _append_chunk_stage_miss_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("chunk_stage_miss_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    labels_raw = summary.get("labels")
    labels: dict[str, Any] = labels_raw if isinstance(labels_raw, dict) else {}
    oracle_case_count = int(summary.get("oracle_case_count", 0) or 0)

    lines.append("## Chunk Stage Miss Summary")
    lines.append("")
    lines.append(f"- Oracle-tagged cases: {oracle_case_count}")
    lines.append(
        "- Classified stage-miss cases: {count} ({rate})".format(
            count=int(summary.get("classified_case_count", 0) or 0),
            rate=f"{float(summary.get('classified_case_rate', 0.0) or 0.0):.4f}",
        )
    )
    lines.append("")
    lines.append("### Labels")
    lines.append("")
    if not labels:
        lines.append("- None")
        lines.append("")
        return

    lines.append("| Label | Count | Rate |")
    lines.append("| --- | ---: | ---: |")
    for name, count in sorted(
        labels.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
    ):
        rate = (
            float(count or 0) / float(oracle_case_count) if oracle_case_count > 0 else 0.0
        )
        lines.append(f"| {name} | {int(count or 0)} | {rate:.4f} |")
    lines.append("")
def _append_stage_latency_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("stage_latency_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    baseline_metrics_raw = results.get("baseline_metrics")
    baseline_metrics = (
        _normalize_metrics(baseline_metrics_raw)
        if isinstance(baseline_metrics_raw, dict)
        else {}
    )
    delta_raw = results.get("delta")
    delta = _normalize_metrics(delta_raw) if isinstance(delta_raw, dict) else {}

    lines.append("## Stage Latency Summary")
    lines.append("")
    lines.append("| Stage | Mean (ms) | P95 (ms) | Baseline P95 | Delta P95 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")

    for stage, metric_name in STAGE_LATENCY_ORDER:
        stage_summary_raw = summary.get(stage)
        stage_summary = (
            stage_summary_raw if isinstance(stage_summary_raw, dict) else {}
        )
        lines.append(
            "| {stage} | {mean} | {p95} | {baseline} | {delta} |".format(
                stage=stage,
                mean=_format_metric("latency_p95_ms", stage_summary.get("mean_ms", 0.0)),
                p95=_format_metric("latency_p95_ms", stage_summary.get("p95_ms", 0.0)),
                baseline=_format_optional_metric(
                    metric_name, baseline_metrics.get(metric_name)
                ),
                delta=_format_optional_metric(metric_name, delta.get(metric_name), signed=True),
            )
        )

    total_raw = summary.get("total")
    total = total_raw if isinstance(total_raw, dict) else {}
    lines.append(
        "| total | {mean} | {p95} | {baseline} | {delta} |".format(
            mean=_format_metric("latency_p95_ms", total.get("mean_ms", 0.0)),
            p95=_format_metric("latency_p95_ms", total.get("p95_ms", 0.0)),
            baseline=_format_optional_metric(
                "latency_p95_ms", baseline_metrics.get("latency_p95_ms")
            ),
            delta=_format_optional_metric(
                "latency_p95_ms", delta.get("latency_p95_ms"), signed=True
            ),
        )
    )
    lines.append("")


def _append_slo_budget_summary(lines: list[str], results: dict[str, Any]) -> None:
    summary_raw = results.get("slo_budget_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    metrics = _normalize_metrics(results.get("metrics"))
    baseline_metrics_raw = results.get("baseline_metrics")
    baseline_metrics = (
        _normalize_metrics(baseline_metrics_raw)
        if isinstance(baseline_metrics_raw, dict)
        else {}
    )
    delta_raw = results.get("delta")
    delta = _normalize_metrics(delta_raw) if isinstance(delta_raw, dict) else {}

    lines.append("## SLO Budget Summary")
    lines.append("")
    lines.append(
        "- Downgrade cases: {count}/{case_count} ({rate})".format(
            count=int(summary.get("downgrade_case_count", 0) or 0),
            case_count=int(summary.get("case_count", 0) or 0),
            rate=_format_metric(
                "slo_downgrade_case_rate",
                summary.get("downgrade_case_rate", 0.0),
            ),
        )
    )
    if baseline_metrics:
        lines.append(
            "- Downgrade delta vs baseline: {delta}".format(
                delta=_format_optional_metric(
                    "slo_downgrade_case_rate",
                    delta.get("slo_downgrade_case_rate"),
                    signed=True,
                )
            )
        )
    lines.append("")

    budget_limits_raw = summary.get("budget_limits_ms")
    budget_limits = (
        budget_limits_raw if isinstance(budget_limits_raw, dict) else {}
    )
    lines.append("### Budget Limits")
    lines.append("")
    lines.append("| Budget | Mean (ms) | Baseline | Delta |")
    lines.append("| --- | ---: | ---: | ---: |")
    for metric_name in SLO_BUDGET_LIMIT_ORDER:
        lines.append(
            "| {name} | {current} | {baseline} | {delta} |".format(
                name=metric_name,
                current=_format_metric(metric_name, budget_limits.get(metric_name, 0.0)),
                baseline=_format_optional_metric(
                    metric_name, baseline_metrics.get(metric_name)
                ),
                delta=_format_optional_metric(metric_name, delta.get(metric_name), signed=True),
            )
        )
    lines.append("")

    signals_raw = summary.get("signals")
    signals = signals_raw if isinstance(signals_raw, dict) else {}
    lines.append("### Downgrade Signals")
    lines.append("")
    lines.append("| Signal | Count | Current Rate | Baseline | Delta |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for metric_name in SLO_SIGNAL_ORDER:
        signal_raw = signals.get(metric_name)
        signal = signal_raw if isinstance(signal_raw, dict) else {}
        count = int(signal.get("count", 0) or 0)
        current_rate = (
            metrics.get(metric_name, signal.get("rate", 0.0))
            if metric_name != "slo_downgrade_case_rate"
            else summary.get("downgrade_case_rate", 0.0)
        )
        lines.append(
            "| {name} | {count} | {current} | {baseline} | {delta} |".format(
                name=metric_name,
                count=count if metric_name != "slo_downgrade_case_rate" else int(
                    summary.get("downgrade_case_count", 0) or 0
                ),
                current=_format_metric(metric_name, current_rate),
                baseline=_format_optional_metric(
                    metric_name, baseline_metrics.get(metric_name)
                ),
                delta=_format_optional_metric(metric_name, delta.get(metric_name), signed=True),
            )
        )
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | ---: |")
    for key in (
        "case_count",
        "positive_case_count",
        "negative_control_case_count",
        "task_success_rate",
        "positive_task_success_rate",
        "negative_control_task_success_rate",
        "retrieval_task_gap_count",
        "retrieval_task_gap_rate",
    ):
        value = summary.get(key, 0.0)
        if key.endswith("_count"):
            lines.append(f"| {key} | {int(value or 0)} |")
        else:
            lines.append(f"| {key} | {float(value or 0.0):.4f} |")
    lines.append("")


def _append_retrieval_task_gap_cases(lines: list[str], cases: list[Any]) -> None:
    gap_cases: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        recall_hit = float(item.get("recall_hit", 0.0) or 0.0)
        task_success_hit = float(item.get("task_success_hit", 0.0) or 0.0)
        if recall_hit <= 0.0 or task_success_hit > 0.0:
            continue
        gap_cases.append(item)

    lines.append("## Retrieval-to-Task Gaps")
    lines.append("")
    if not gap_cases:
        lines.append("- None")
        lines.append("")
        return

    for case in gap_cases:
        lines.append(f"### {case.get('case_id', 'unknown')}")
        lines.append(f"- Query: {case.get('query', '')}")
        lines.append(f"- task_success_mode: {case.get('task_success_mode', 'positive')}")
        lines.append(f"- first_hit_rank: {case.get('first_hit_rank', '(none)')}")
        lines.append(f"- precision_at_k: {float(case.get('precision_at_k', 0.0)):.4f}")
        lines.append(f"- validation_test_count: {int(case.get('validation_test_count', 0) or 0)}")
        failed_checks = case.get("task_success_failed_checks", [])
        if isinstance(failed_checks, list) and failed_checks:
            lines.append(
                "- task_success_failed_checks: "
                + ", ".join(str(item) for item in failed_checks if str(item).strip())
            )
        reason = str(case.get("evidence_insufficiency_reason") or "").strip()
        if reason:
            lines.append(f"- evidence_insufficiency_reason: {reason}")
        signals = case.get("evidence_insufficiency_signals", [])
        if isinstance(signals, list) and signals:
            lines.append(
                "- evidence_insufficiency_signals: "
                + ", ".join(str(item) for item in signals if str(item).strip())
            )
        decision_trace = case.get("decision_trace", [])
        if isinstance(decision_trace, list):
            for event in decision_trace:
                if isinstance(event, dict):
                    lines.append(f"- decision_event: {format_decision_event(event)}")
        lines.append("")


def build_results_summary(results: dict[str, Any]) -> dict[str, Any]:
    metrics = _normalize_metrics(results.get("metrics"))

    regression_raw = results.get("regression")
    regression: dict[str, Any] = (
        regression_raw if isinstance(regression_raw, dict) else {}
    )

    failed_checks_raw = regression.get("failed_checks")
    failed_checks = (
        [str(item) for item in failed_checks_raw]
        if isinstance(failed_checks_raw, list)
        else []
    )

    metric_snapshot: dict[str, float] = {
        key: float(metrics.get(key, 0.0) or 0.0)
        for key in ALL_METRIC_ORDER
    }

    summary: dict[str, Any] = {
        "generated_at": results.get("generated_at"),
        "repo": results.get("repo", ""),
        "root": results.get("root", ""),
        "case_count": int(results.get("case_count", 0) or 0),
        "warmup_runs": int(results.get("warmup_runs", 0) or 0),
        "threshold_profile": results.get("threshold_profile"),
        "regressed": bool(regression.get("regressed", False)),
        "failed_checks": failed_checks,
        "metrics": metric_snapshot,
    }
    summary.update(copy_optional_summary_sections(results=results))
    runtime_stats_summary_raw = summary.get("runtime_stats_summary")
    ltm_explainability_summary_raw = summary.get("ltm_explainability_summary")
    if isinstance(runtime_stats_summary_raw, dict):
        runtime_stats_summary = dict(runtime_stats_summary_raw)
        memory_health_summary_raw = runtime_stats_summary.get("memory_health_summary")
        memory_health_summary = (
            memory_health_summary_raw
            if isinstance(memory_health_summary_raw, dict)
            else {}
        )
        if memory_health_summary and isinstance(ltm_explainability_summary_raw, dict):
            runtime_stats_summary["memory_health_summary"] = (
                attach_runtime_memory_ltm_signal_summary(
                    memory_health_summary=memory_health_summary,
                    ltm_explainability_summary=ltm_explainability_summary_raw,
                )
            )
        summary["runtime_stats_summary"] = runtime_stats_summary
    latency_alignment_summary = _build_ltm_latency_alignment_summary(results=results)
    if latency_alignment_summary:
        summary["ltm_latency_alignment_summary"] = latency_alignment_summary
    pq_003_overlay = resolve_benchmark_pq_003_overlay(results)
    if pq_003_overlay:
        summary["pq_003_overlay"] = pq_003_overlay

    return summary


def build_report_markdown(results: dict[str, Any]) -> str:
    metrics = _normalize_metrics(results.get("metrics"))
    cases = results.get("cases", [])
    policy_profiles_raw = results.get("policy_profile_distribution")
    policy_profiles: dict[str, Any] = (
        policy_profiles_raw if isinstance(policy_profiles_raw, dict) else {}
    )

    lines: list[str] = []
    lines.append("# ACE-Lite Benchmark Report")
    lines.append("")
    lines.append(f"- Generated: {results.get('generated_at', '')}")
    lines.append(f"- Repo: {results.get('repo', '')}")
    lines.append(f"- Case count: {results.get('case_count', 0)}")
    warmup_runs = int(results.get("warmup_runs", 0) or 0)
    if warmup_runs > 0:
        lines.append(f"- Warmup runs: {warmup_runs}")
    include_plan_payload = bool(results.get("include_plan_payload", True))
    if not include_plan_payload:
        lines.append("- Include plans: false")
    include_case_details = bool(results.get("include_case_details", True))
    if not include_case_details:
        lines.append("- Include case details: false")
    if results.get("threshold_profile"):
        lines.append(f"- Threshold profile: {results.get('threshold_profile')}")
    lines.append("")

    _append_metrics_table(lines, "Metrics", metrics)
    _append_source_plan_granularity_summary(lines, metrics)
    _append_index_fusion_granularity_summary(lines, metrics)
    _append_graph_lookup_summary(lines, metrics)
    _append_validation_probe_summary(lines, results)
    append_validation_branch_summary(lines, results)
    append_validation_branch_gate_summary(lines, results)
    _append_source_plan_card_summary(lines, results)
    _append_source_plan_validation_feedback_summary(lines, results)
    _append_source_plan_failure_signal_summary(lines, results)
    _append_learning_router_rollout_summary(lines, results)
    _append_repomap_seed_summary(lines, results)
    _append_deep_symbol_summary(lines, results)
    _append_native_scip_summary(lines, results)
    _append_graph_context_source_summary(lines, results)
    _append_chunk_cache_contract_summary(lines, results)
    append_retrieval_control_plane_gate_summary(lines, results)
    append_retrieval_frontier_gate_summary(lines, results)
    _append_agent_loop_control_plane_summary(lines, results)

    if policy_profiles:
        lines.append("## Policy Profile Distribution")
        lines.append("")
        for name, count in sorted(
            policy_profiles.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))
        ):
            label = str(name).strip() or "(unknown)"
            lines.append(f"- {label}: {int(count or 0)}")
        lines.append("")

    append_adaptive_router_observability_summary(lines, results)
    append_reward_log_summary(lines, results)
    _append_runtime_stats_summary(lines, results)

    baseline_metrics_raw = results.get("baseline_metrics")
    baseline_metrics = (
        _normalize_metrics(baseline_metrics_raw)
        if isinstance(baseline_metrics_raw, dict)
        else None
    )
    if isinstance(baseline_metrics, dict):
        _append_metrics_table(lines, "Baseline", baseline_metrics)

    delta_raw = results.get("delta")
    delta = _normalize_metrics(delta_raw) if isinstance(delta_raw, dict) else None
    if isinstance(delta, dict):
        _append_metrics_table(lines, "Delta vs Baseline", delta, signed=True)

    task_success_summary = results.get("task_success_summary")
    if isinstance(task_success_summary, dict):
        _append_task_success_summary(lines, task_success_summary)

    _append_comparison_lane_summary(lines, results)
    append_evidence_insufficiency_summary(lines, results)
    append_missing_context_risk_summary(lines, results)
    append_feedback_loop_summary(lines, results)
    append_feedback_observability_summary(lines, results)
    append_ltm_explainability_summary(lines, results)
    append_preference_observability_summary(lines, results)
    append_context_refine_summary(lines, results)
    append_wave1_context_governance_summary(lines, results)
    append_retrieval_default_strategy_summary(lines, results)
    append_retrieval_context_observability_summary(lines, results)
    append_workload_taxonomy_summary(lines, results)
    _append_chunk_stage_miss_summary(lines, results)
    append_decision_observability_summary(lines, results)
    _append_stage_latency_summary(lines, results)
    _append_slo_budget_summary(lines, results)

    _append_retrieval_task_gap_cases(lines, cases if isinstance(cases, list) else [])

    plugin_policy_summary = results.get("plugin_policy_summary")
    if isinstance(plugin_policy_summary, dict):
        _append_plugin_policy_summary(lines, plugin_policy_summary)

    regression_thresholds = results.get("regression_thresholds")
    if isinstance(regression_thresholds, dict):
        lines.append("## Regression Thresholds")
        lines.append("")
        lines.append("| Threshold | Value |")
        lines.append("| --- | ---: |")
        for key, value in regression_thresholds.items():
            lines.append(f"| {key} | {float(value):.4f} |")
        lines.append("")

    regression = results.get("regression")
    if isinstance(regression, dict):
        failed_checks = regression.get("failed_checks", [])
        failed_thresholds = regression.get("failed_thresholds", [])
        lines.append("## Regression")
        lines.append("")
        lines.append(f"- regressed: {bool(regression.get('regressed', False))}")
        lines.append(
            f"- failed_checks: {', '.join(str(item) for item in failed_checks) if failed_checks else '(none)'}"
        )
        if isinstance(failed_thresholds, list) and failed_thresholds:
            lines.append("- failed_thresholds:")
            for item in failed_thresholds:
                if not isinstance(item, dict):
                    continue
                metric = str(item.get("metric", ""))
                operator = str(item.get("operator", ""))
                current = float(item.get("current", 0.0))
                threshold = float(item.get("threshold", 0.0))
                lines.append(f"  - {metric}: {current:.4f} {operator} {threshold:.4f}")
        lines.append("")

    lines.append("## Cases")
    lines.append("")

    append_case_sections(
        lines,
        cases=cases if isinstance(cases, list) else [],
        format_decision_event=format_decision_event,
    )

    return "\n".join(lines).strip() + "\n"


def write_results(results: dict[str, Any], *, output_dir: str | Path) -> dict[str, str]:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)

    results_path = base / "results.json"
    report_path = base / "report.md"
    summary_path = base / "summary.json"

    summary = build_results_summary(results)
    report_results = dict(results)
    report_results.update(summary)

    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(build_report_markdown(report_results), encoding="utf-8")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "results_json": str(results_path),
        "report_md": str(report_path),
        "summary_json": str(summary_path),
    }


def write_report_from_json(
    *, input_path: str | Path, output_path: str | Path | None = None
) -> str:
    source = Path(input_path)
    results = json.loads(source.read_text(encoding="utf-8"))

    target = Path(output_path) if output_path else source.with_name("report.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_report_markdown(results), encoding="utf-8")
    return str(target)


__all__ = [
    "build_report_markdown",
    "build_results_summary",
    "write_report_from_json",
    "write_results",
]
