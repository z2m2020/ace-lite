from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_summary import get_summary_mapping


def append_retrieval_context_observability_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("retrieval_context_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Retrieval Context Observability Summary")
    lines.append("")
    lines.append(
        "- Available cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Pool-available cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("pool_available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("pool_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Parent-symbol cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("parent_symbol_available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("parent_symbol_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Reference-hint cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("reference_hint_available_case_count", 0) or 0),
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("reference_hint_available_case_rate", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(
        "| chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| coverage_ratio_mean | {value:.4f} |".format(
            value=float(summary.get("coverage_ratio_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| parent_symbol_chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("parent_symbol_chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| parent_symbol_coverage_ratio_mean | {value:.4f} |".format(
            value=float(
                summary.get("parent_symbol_coverage_ratio_mean", 0.0) or 0.0
            )
        )
    )
    lines.append(
        "| reference_hint_chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("reference_hint_chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| reference_hint_coverage_ratio_mean | {value:.4f} |".format(
            value=float(
                summary.get("reference_hint_coverage_ratio_mean", 0.0) or 0.0
            )
        )
    )
    lines.append(
        "| pool_chunk_count_mean | {value:.4f} |".format(
            value=float(summary.get("pool_chunk_count_mean", 0.0) or 0.0)
        )
    )
    lines.append(
        "| pool_coverage_ratio_mean | {value:.4f} |".format(
            value=float(summary.get("pool_coverage_ratio_mean", 0.0) or 0.0)
        )
    )
    lines.append("")


def append_retrieval_default_strategy_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("retrieval_default_strategy_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    case_count = int(summary.get("case_count", 0) or 0)
    if case_count <= 0:
        return

    weights_raw = summary.get("graph_lookup_weight_means")
    weights = weights_raw if isinstance(weights_raw, dict) else {}

    lines.append("## Retrieval Default Strategy Summary")
    lines.append("")
    lines.append(
        "- Retrieval-context cases: {count}/{total} ({rate:.4f}); parent-symbol: {parent_count}/{total} ({parent_rate:.4f}); reference-hint: {hint_count}/{total} ({hint_rate:.4f})".format(
            count=int(summary.get("retrieval_context_available_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("retrieval_context_available_case_rate", 0.0) or 0.0),
            parent_count=int(
                summary.get("parent_symbol_available_case_count", 0) or 0
            ),
            parent_rate=float(
                summary.get("parent_symbol_available_case_rate", 0.0) or 0.0
            ),
            hint_count=int(
                summary.get("reference_hint_available_case_count", 0) or 0
            ),
            hint_rate=float(
                summary.get("reference_hint_available_case_rate", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Semantic rerank default: configured={configured_count}/{total} ({configured_rate:.4f}); enabled={enabled_count}/{total} ({enabled_rate:.4f}); applied={applied_count}/{total} ({applied_rate:.4f}); mode={mode}; provider={provider}".format(
            configured_count=int(
                summary.get("semantic_rerank_configured_case_count", 0) or 0
            ),
            total=case_count,
            configured_rate=float(
                summary.get("semantic_rerank_configured_case_rate", 0.0) or 0.0
            ),
            enabled_count=int(
                summary.get("semantic_rerank_enabled_case_count", 0) or 0
            ),
            enabled_rate=float(
                summary.get("semantic_rerank_enabled_case_rate", 0.0) or 0.0
            ),
            applied_count=int(
                summary.get("semantic_rerank_applied_case_count", 0) or 0
            ),
            applied_rate=float(
                summary.get("semantic_rerank_applied_case_rate", 0.0) or 0.0
            ),
            mode=str(summary.get("semantic_rerank_dominant_mode") or "(none)"),
            provider=str(
                summary.get("semantic_rerank_dominant_provider") or "(none)"
            ),
        )
    )
    provider_case_counts_raw = summary.get("semantic_rerank_provider_case_counts")
    provider_case_counts = (
        provider_case_counts_raw if isinstance(provider_case_counts_raw, dict) else {}
    )
    if provider_case_counts:
        distribution = ", ".join(
            f"{provider!s}={int(count or 0)}"
            for provider, count in sorted(provider_case_counts.items())
        )
        lines.append(f"- Semantic rerank providers: {distribution}")
    lines.append(
        "- Graph lookup default: enabled={enabled_count}/{total} ({enabled_rate:.4f}); guarded={guarded_count}/{total} ({guarded_rate:.4f}); normalization={normalization}".format(
            enabled_count=int(summary.get("graph_lookup_enabled_case_count", 0) or 0),
            total=case_count,
            enabled_rate=float(
                summary.get("graph_lookup_enabled_case_rate", 0.0) or 0.0
            ),
            guarded_count=int(summary.get("graph_lookup_guarded_case_count", 0) or 0),
            guarded_rate=float(
                summary.get("graph_lookup_guarded_case_rate", 0.0) or 0.0
            ),
            normalization=str(
                summary.get("graph_lookup_dominant_normalization") or "(none)"
            ),
        )
    )
    lines.append(
        "- Graph lookup guard means: pool={pool:.4f}; max_candidates={max_candidates:.4f}; min_query_terms={min_terms:.4f}; max_query_terms={max_terms:.4f}".format(
            pool=float(summary.get("graph_lookup_pool_size_mean", 0.0) or 0.0),
            max_candidates=float(
                summary.get("graph_lookup_guard_max_candidates_mean", 0.0) or 0.0
            ),
            min_terms=float(
                summary.get("graph_lookup_guard_min_query_terms_mean", 0.0) or 0.0
            ),
            max_terms=float(
                summary.get("graph_lookup_guard_max_query_terms_mean", 0.0) or 0.0
            ),
        )
    )
    lines.append(
        "- Graph lookup weight means: scip={scip:.4f}; xref={xref:.4f}; query_xref={query_xref:.4f}; symbol={symbol:.4f}; import={imports:.4f}; coverage={coverage:.4f}".format(
            scip=float(weights.get("scip", 0.0) or 0.0),
            xref=float(weights.get("xref", 0.0) or 0.0),
            query_xref=float(weights.get("query_xref", 0.0) or 0.0),
            symbol=float(weights.get("symbol", 0.0) or 0.0),
            imports=float(weights.get("import", 0.0) or 0.0),
            coverage=float(weights.get("coverage", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Topological shield default: enabled={enabled_count}/{total} ({enabled_rate:.4f}); report_only={report_only_count}/{total} ({report_only_rate:.4f}); mode={mode}".format(
            enabled_count=int(
                summary.get("topological_shield_enabled_case_count", 0) or 0
            ),
            total=case_count,
            enabled_rate=float(
                summary.get("topological_shield_enabled_case_rate", 0.0) or 0.0
            ),
            report_only_count=int(
                summary.get("topological_shield_report_only_case_count", 0) or 0
            ),
            report_only_rate=float(
                summary.get("topological_shield_report_only_case_rate", 0.0) or 0.0
            ),
            mode=str(summary.get("topological_shield_dominant_mode") or "(none)"),
        )
    )
    lines.append(
        "- Topological shield attenuation means: max={max_value:.4f}; shared_parent={shared_parent:.4f}; adjacency={adjacency:.4f}".format(
            max_value=float(
                summary.get("topological_shield_max_attenuation_mean", 0.0) or 0.0
            ),
            shared_parent=float(
                summary.get(
                    "topological_shield_shared_parent_attenuation_mean", 0.0
                )
                or 0.0
            ),
            adjacency=float(
                summary.get("topological_shield_adjacency_attenuation_mean", 0.0)
                or 0.0
            ),
        )
    )
    lines.append("")


def append_adaptive_router_observability_summary(
    lines: list[str],
    results: dict[str, Any],
) -> None:
    summary_raw = results.get("adaptive_router_observability_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    enabled_case_count = int(summary.get("enabled_case_count", 0) or 0)
    shadow_coverage_case_count = int(summary.get("shadow_coverage_case_count", 0) or 0)
    comparable_case_count = int(summary.get("comparable_case_count", 0) or 0)
    agreement_case_count = int(summary.get("agreement_case_count", 0) or 0)
    disagreement_case_count = int(summary.get("disagreement_case_count", 0) or 0)

    lines.append("## Adaptive Router Observability")
    lines.append("")
    lines.append(
        "- Enabled cases: {count}/{total} ({rate:.4f})".format(
            count=enabled_case_count,
            total=int(summary.get("case_count", 0) or 0),
            rate=float(summary.get("enabled_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Shadow coverage: {count}/{enabled} ({rate:.4f})".format(
            count=shadow_coverage_case_count,
            enabled=enabled_case_count,
            rate=float(summary.get("shadow_coverage_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Comparable cases: {count}/{enabled} ({rate:.4f})".format(
            count=comparable_case_count,
            enabled=enabled_case_count,
            rate=float(summary.get("comparable_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Agreement: {count}/{comparable} ({rate:.4f})".format(
            count=agreement_case_count,
            comparable=comparable_case_count,
            rate=float(summary.get("agreement_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Disagreement: {count}/{comparable} ({rate:.4f})".format(
            count=disagreement_case_count,
            comparable=comparable_case_count,
            rate=float(summary.get("disagreement_rate", 0.0) or 0.0),
        )
    )
    shadow_source_counts_raw = summary.get("shadow_source_counts")
    shadow_source_counts: dict[str, Any] = (
        shadow_source_counts_raw if isinstance(shadow_source_counts_raw, dict) else {}
    )
    if shadow_source_counts:
        formatted = ", ".join(
            f"{name}={int(count or 0)}"
            for name, count in sorted(
                shadow_source_counts.items(),
                key=lambda item: (-int(item[1] or 0), str(item[0])),
            )
        )
        lines.append(f"- Shadow sources: {formatted}")
    lines.append("")

    executed_arms = summary.get("executed_arms", [])
    if isinstance(executed_arms, list) and executed_arms:
        lines.append("### Executed Arms")
        lines.append("")
        _append_adaptive_router_arm_rows(lines=lines, rows=executed_arms)
        lines.append("")

    shadow_arms = summary.get("shadow_arms", [])
    if isinstance(shadow_arms, list) and shadow_arms:
        lines.append("### Shadow Arms")
        lines.append("")
        _append_adaptive_router_arm_rows(lines=lines, rows=shadow_arms)
        lines.append("")


def _append_adaptive_router_arm_rows(*, lines: list[str], rows: list[Any]) -> None:
    for item in rows:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- {arm_id}: cases={case_count} rate={case_rate:.4f} task_success={task_success:.4f} mrr={mrr:.4f} fallback_cases={fallback_cases} downgrade_cases={downgrade_cases} latency_p95_ms={latency_p95:.4f} index_latency_p95_ms={index_latency_p95:.4f}".format(
                arm_id=str(item.get("arm_id", "") or "(unknown)"),
                case_count=int(item.get("case_count", 0) or 0),
                case_rate=float(item.get("case_rate", 0.0) or 0.0),
                task_success=float(item.get("task_success_rate", 0.0) or 0.0),
                mrr=float(item.get("mrr", 0.0) or 0.0),
                fallback_cases=int(item.get("fallback_case_count", 0) or 0),
                downgrade_cases=int(item.get("downgrade_case_count", 0) or 0),
                latency_p95=float(item.get("latency_p95_ms", 0.0) or 0.0),
                index_latency_p95=float(item.get("index_latency_p95_ms", 0.0) or 0.0),
            )
        )


def append_context_refine_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary = get_summary_mapping(results=results, key="context_refine_summary")
    if not summary:
        return

    case_count = int(summary.get("case_count", 0) or 0)
    lines.append("## Context Refine Summary")
    lines.append("")
    lines.append(
        "- Present cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("present_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("present_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Watch cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("watch_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("watch_case_rate", 0.0) or 0.0),
        )
    )
    lines.append(
        "- Thin-context cases: {count}/{total} ({rate:.4f})".format(
            count=int(summary.get("thin_context_case_count", 0) or 0),
            total=case_count,
            rate=float(summary.get("thin_context_case_rate", 0.0) or 0.0),
        )
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for key in (
        "keep_count_mean",
        "downrank_count_mean",
        "drop_count_mean",
        "need_more_read_count_mean",
        "focused_file_count_mean",
    ):
        lines.append(f"| {key} | {float(summary.get(key, 0.0) or 0.0):.4f} |")
    lines.append("")


__all__ = [
    "append_adaptive_router_observability_summary",
    "append_context_refine_summary",
    "append_retrieval_context_observability_summary",
    "append_retrieval_default_strategy_summary",
]
