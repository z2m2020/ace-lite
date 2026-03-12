from __future__ import annotations

from typing import Any


def append_case_sections(
    lines: list[str],
    *,
    cases: list[Any],
    format_decision_event: Any,
) -> None:
    for case in cases:
        _append_case_section(
            lines,
            case=case,
            format_decision_event=format_decision_event,
        )


def _append_case_section(
    lines: list[str],
    *,
    case: dict[str, Any],
    format_decision_event: Any,
) -> None:
    lines.append(f"### {case.get('case_id', 'unknown')}")
    lines.append(f"- Query: {case.get('query', '')}")
    comparison_lane = str(case.get("comparison_lane") or "").strip()
    if comparison_lane:
        lines.append(f"- comparison_lane: {comparison_lane}")
    lines.append(f"- policy_profile: {case.get('policy_profile', '')}")
    lines.append(f"- docs_hit: {float(case.get('docs_hit', 0.0)):.4f}")
    lines.append(f"- hint_inject: {float(case.get('hint_inject', 0.0)):.4f}")
    lines.append(f"- recall_hit: {float(case.get('recall_hit', 0.0)):.0f}")
    first_hit_rank = case.get("first_hit_rank")
    if first_hit_rank is None:
        lines.append("- first_hit_rank: (none)")
    else:
        lines.append(f"- first_hit_rank: {int(first_hit_rank)}")
    lines.append(f"- hit_at_1: {float(case.get('hit_at_1', 0.0)):.4f}")
    lines.append(f"- reciprocal_rank: {float(case.get('reciprocal_rank', 0.0)):.4f}")
    lines.append(f"- task_success_hit: {float(case.get('task_success_hit', 0.0)):.4f}")
    lines.append(f"- task_success_mode: {case.get('task_success_mode', 'positive')}")
    lines.append(f"- precision_at_k: {float(case.get('precision_at_k', 0.0)):.4f}")
    lines.append(f"- noise_rate: {float(case.get('noise_rate', 0.0)):.4f}")
    lines.append(
        f"- source_plan_direct_evidence_ratio: {float(case.get('source_plan_direct_evidence_ratio', 0.0)):.4f}"
    )
    lines.append(
        f"- source_plan_neighbor_context_ratio: {float(case.get('source_plan_neighbor_context_ratio', 0.0)):.4f}"
    )
    lines.append(
        f"- source_plan_hint_only_ratio: {float(case.get('source_plan_hint_only_ratio', 0.0)):.4f}"
    )
    lines.append(
        "- graph_closure_enabled: "
        f"{float(case.get('graph_closure_enabled', 0.0)):.4f}"
    )
    lines.append(
        "- graph_closure_boosted_chunk_count: "
        f"{float(case.get('graph_closure_boosted_chunk_count', 0.0)):.4f}"
    )
    lines.append(
        "- graph_closure_coverage_ratio: "
        f"{float(case.get('graph_closure_coverage_ratio', 0.0)):.4f}"
    )
    lines.append(
        "- graph_closure_anchor_count: "
        f"{float(case.get('graph_closure_anchor_count', 0.0)):.4f}"
    )
    lines.append(
        "- graph_closure_support_edge_count: "
        f"{float(case.get('graph_closure_support_edge_count', 0.0)):.4f}"
    )
    lines.append(
        "- graph_closure_total: "
        f"{float(case.get('graph_closure_total', 0.0)):.4f}"
    )
    lines.append(
        "- source_plan_graph_closure_preference_enabled: "
        f"{float(case.get('source_plan_graph_closure_preference_enabled', 0.0)):.4f}"
    )
    lines.append(
        "- source_plan_graph_closure_bonus_candidate_count: "
        f"{float(case.get('source_plan_graph_closure_bonus_candidate_count', 0.0)):.4f}"
    )
    lines.append(
        "- source_plan_graph_closure_preferred_count: "
        f"{float(case.get('source_plan_graph_closure_preferred_count', 0.0)):.4f}"
    )
    lines.append(
        "- source_plan_focused_file_promoted_count: "
        f"{float(case.get('source_plan_focused_file_promoted_count', 0.0)):.4f}"
    )
    lines.append(
        "- source_plan_packed_path_count: "
        f"{float(case.get('source_plan_packed_path_count', 0.0)):.4f}"
    )
    lines.append(
        f"- plan_replay_cache_enabled: {float(case.get('plan_replay_cache_enabled', 0.0)):.4f}"
    )
    lines.append(
        f"- plan_replay_cache_hit: {float(case.get('plan_replay_cache_hit', 0.0)):.4f}"
    )
    lines.append(
        f"- plan_replay_cache_stale_hit_safe: {float(case.get('plan_replay_cache_stale_hit_safe', 0.0)):.4f}"
    )
    lines.append(
        f"- chunk_guard_enabled: {float(case.get('chunk_guard_enabled', 0.0)):.4f}"
    )
    lines.append(
        f"- chunk_guard_report_only: {float(case.get('chunk_guard_report_only', 0.0)):.4f}"
    )
    lines.append(
        f"- chunk_guard_filtered_count: {float(case.get('chunk_guard_filtered_count', 0.0)):.4f}"
    )
    lines.append(
        f"- chunk_guard_filter_ratio: {float(case.get('chunk_guard_filter_ratio', 0.0)):.4f}"
    )
    lines.append(
        f"- chunk_guard_pairwise_conflict_count: {float(case.get('chunk_guard_pairwise_conflict_count', 0.0)):.4f}"
    )
    lines.append(
        f"- chunk_guard_fallback: {float(case.get('chunk_guard_fallback', 0.0)):.4f}"
    )
    lines.append(
        f"- robust_signature_count: {float(case.get('robust_signature_count', 0.0)):.4f}"
    )
    lines.append(
        f"- robust_signature_coverage_ratio: {float(case.get('robust_signature_coverage_ratio', 0.0)):.4f}"
    )
    chunk_stage_miss = str(case.get("chunk_stage_miss") or "").strip()
    if chunk_stage_miss:
        lines.append(f"- chunk_stage_miss: {chunk_stage_miss}")
    lines.append(
        f"- evidence_insufficient: {float(case.get('evidence_insufficient', 0.0)):.4f}"
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
    lines.append(f"- dependency_recall: {float(case.get('dependency_recall', 0.0)):.4f}")
    failed_checks = case.get("task_success_failed_checks", [])
    if isinstance(failed_checks, list) and failed_checks:
        lines.append(
            "- task_success_failed_checks: "
            + ", ".join(str(item) for item in failed_checks if str(item).strip())
        )
    stage_latency_ms = case.get("stage_latency_ms")
    if isinstance(stage_latency_ms, dict) and stage_latency_ms:
        lines.append(
            "- stage_latency_ms: "
            + ", ".join(
                f"{name}={float(value or 0.0):.2f}"
                for name, value in stage_latency_ms.items()
            )
        )
    slo_downgrade_signals = case.get("slo_downgrade_signals")
    if isinstance(slo_downgrade_signals, list) and slo_downgrade_signals:
        lines.append(
            "- slo_downgrade_signals: "
            + ", ".join(str(item) for item in slo_downgrade_signals if str(item).strip())
        )
    _append_plan_replay_cache_details(lines, case=case)
    _append_chunk_guard_details(lines, case=case)
    _append_chunk_guard_expectation(lines, case=case)
    _append_robust_signature_details(lines, case=case)
    _append_subgraph_payload_details(lines, case=case)
    _append_graph_prior_details(lines, case=case)
    _append_graph_closure_details(lines, case=case)
    _append_source_plan_packing_details(lines, case=case)
    _append_chunk_stage_miss_details(lines, case=case)
    lines.append(f"- latency_ms: {float(case.get('latency_ms', 0.0)):.2f}")
    lines.append("")


def _append_plan_replay_cache_details(lines: list[str], *, case: dict[str, Any]) -> None:
    plan_replay_cache = case.get("plan_replay_cache")
    if isinstance(plan_replay_cache, dict) and plan_replay_cache:
        lines.append(
            "- plan_replay_cache: "
            + ", ".join(
                [
                    f"stage={str(plan_replay_cache.get('stage', '') or '(none)')}",
                    f"reason={str(plan_replay_cache.get('reason', '') or '(none)')}",
                    f"stored={bool(plan_replay_cache.get('stored', False))}",
                ]
            )
        )


def _append_chunk_guard_details(lines: list[str], *, case: dict[str, Any]) -> None:
    chunk_guard = case.get("chunk_guard")
    if not isinstance(chunk_guard, dict) or not chunk_guard:
        return
    retained_refs = (
        chunk_guard.get("retained_refs")
        if isinstance(chunk_guard.get("retained_refs"), list)
        else []
    )
    filtered_refs = (
        chunk_guard.get("filtered_refs")
        if isinstance(chunk_guard.get("filtered_refs"), list)
        else []
    )
    lines.append(
        "- chunk_guard: "
        + ", ".join(
            [
                f"mode={str(chunk_guard.get('mode', '') or '(none)')}",
                f"reason={str(chunk_guard.get('reason', '') or '(none)')}",
                f"candidate_pool={int(chunk_guard.get('candidate_pool', 0) or 0)}",
                f"filtered_count={int(chunk_guard.get('filtered_count', 0) or 0)}",
                f"retained_count={int(chunk_guard.get('retained_count', 0) or 0)}",
                "retained_refs={value}".format(
                    value=";".join(str(item) for item in retained_refs[:4]) or "(none)"
                ),
                "filtered_refs={value}".format(
                    value=";".join(str(item) for item in filtered_refs[:4]) or "(none)"
                ),
            ]
        )
    )


def _append_chunk_guard_expectation(lines: list[str], *, case: dict[str, Any]) -> None:
    chunk_guard_expectation = case.get("chunk_guard_expectation")
    if not isinstance(chunk_guard_expectation, dict) or not chunk_guard_expectation:
        return
    lines.append(
        "- chunk_guard_expectation: "
        + ", ".join(
            [
                f"scenario={str(chunk_guard_expectation.get('scenario', '') or '(none)')}",
                "expected_retained_hit={value}".format(
                    value=bool(
                        chunk_guard_expectation.get("expected_retained_hit", False)
                    )
                ),
                "expected_filtered_hit_count={value}".format(
                    value=int(
                        chunk_guard_expectation.get("expected_filtered_hit_count", 0)
                        or 0
                    )
                ),
                "expected_filtered_hit_rate={value:.4f}".format(
                    value=float(
                        chunk_guard_expectation.get("expected_filtered_hit_rate", 0.0)
                        or 0.0
                    )
                ),
                "report_only_improved={value}".format(
                    value=bool(
                        chunk_guard_expectation.get("report_only_improved", False)
                    )
                ),
            ]
        )
    )


def _append_robust_signature_details(lines: list[str], *, case: dict[str, Any]) -> None:
    robust_signature = case.get("robust_signature")
    if isinstance(robust_signature, dict) and robust_signature:
        lines.append(
            "- robust_signature: "
            + ", ".join(
                [
                    f"count={int(robust_signature.get('count', 0) or 0)}",
                    f"coverage_ratio={float(robust_signature.get('coverage_ratio', 0.0) or 0.0):.4f}",
                ]
            )
        )


def _append_subgraph_payload_details(lines: list[str], *, case: dict[str, Any]) -> None:
    subgraph_payload = case.get("subgraph_payload")
    if not isinstance(subgraph_payload, dict) or not subgraph_payload:
        return
    edge_counts = (
        subgraph_payload.get("edge_counts")
        if isinstance(subgraph_payload.get("edge_counts"), dict)
        else {}
    )
    lines.append(
        "- subgraph_payload: "
        + ", ".join(
            [
                f"enabled={bool(subgraph_payload.get('enabled', False))}",
                f"reason={str(subgraph_payload.get('reason', '') or '(none)')}",
                f"seed_path_count={int(subgraph_payload.get('seed_path_count', 0) or 0)}",
                f"edge_type_count={int(subgraph_payload.get('edge_type_count', 0) or 0)}",
                f"edge_total_count={int(subgraph_payload.get('edge_total_count', 0) or 0)}",
                "edge_counts={value}".format(
                    value=";".join(
                        f"{str(key)}={int(value or 0)}" for key, value in edge_counts.items()
                    )
                    or "(none)"
                ),
            ]
        )
    )


def _append_graph_prior_details(lines: list[str], *, case: dict[str, Any]) -> None:
    graph_prior = case.get("graph_prior")
    if isinstance(graph_prior, dict) and graph_prior:
        lines.append(
            "- graph_prior: "
            + ", ".join(
                [
                    f"chunk_count={int(graph_prior.get('chunk_count', 0) or 0)}",
                    f"coverage_ratio={float(graph_prior.get('coverage_ratio', 0.0) or 0.0):.4f}",
                    f"total={float(graph_prior.get('total', 0.0) or 0.0):.4f}",
                    f"seeded_chunk_count={int(graph_prior.get('seeded_chunk_count', 0) or 0)}",
                    f"transfer_count={int(graph_prior.get('transfer_count', 0) or 0)}",
                    f"hub_suppressed_chunk_count={int(graph_prior.get('hub_suppressed_chunk_count', 0) or 0)}",
                    f"hub_penalty_total={float(graph_prior.get('hub_penalty_total', 0.0) or 0.0):.4f}",
                ]
            )
        )


def _append_graph_closure_details(lines: list[str], *, case: dict[str, Any]) -> None:
    graph_closure = case.get("graph_closure")
    if isinstance(graph_closure, dict) and graph_closure:
        lines.append(
            "- graph_closure: "
            + ", ".join(
                [
                    f"enabled={bool(graph_closure.get('enabled', False))}",
                    f"boosted_chunk_count={int(graph_closure.get('boosted_chunk_count', 0) or 0)}",
                    f"coverage_ratio={float(graph_closure.get('coverage_ratio', 0.0) or 0.0):.4f}",
                    f"anchor_count={int(graph_closure.get('anchor_count', 0) or 0)}",
                    f"support_edge_count={int(graph_closure.get('support_edge_count', 0) or 0)}",
                    f"total={float(graph_closure.get('total', 0.0) or 0.0):.4f}",
                ]
            )
        )


def _append_source_plan_packing_details(
    lines: list[str], *, case: dict[str, Any]
) -> None:
    source_plan_packing = case.get("source_plan_packing")
    if not isinstance(source_plan_packing, dict) or not source_plan_packing:
        return
    lines.append(
        "- source_plan_packing: "
        + ", ".join(
            [
                "graph_closure_preference_enabled={value}".format(
                    value=bool(
                        source_plan_packing.get(
                            "graph_closure_preference_enabled", False
                        )
                    )
                ),
                "graph_closure_bonus_candidate_count={value}".format(
                    value=int(
                        source_plan_packing.get(
                            "graph_closure_bonus_candidate_count", 0
                        )
                        or 0
                    )
                ),
                "graph_closure_preferred_count={value}".format(
                    value=int(
                        source_plan_packing.get("graph_closure_preferred_count", 0)
                        or 0
                    )
                ),
                "focused_file_promoted_count={value}".format(
                    value=int(
                        source_plan_packing.get("focused_file_promoted_count", 0) or 0
                    )
                ),
                "packed_path_count={value}".format(
                    value=int(source_plan_packing.get("packed_path_count", 0) or 0)
                ),
                "reason={value}".format(
                    value=str(source_plan_packing.get("reason", "") or "(none)")
                ),
            ]
        )
    )


def _append_chunk_stage_miss_details(lines: list[str], *, case: dict[str, Any]) -> None:
    chunk_stage_miss_details = case.get("chunk_stage_miss_details")
    if not isinstance(chunk_stage_miss_details, dict) or not chunk_stage_miss_details:
        return
    oracle_file_path = str(
        chunk_stage_miss_details.get("oracle_file_path", "") or ""
    ).strip()
    lines.append(
        "- chunk_stage_miss_details: "
        + ", ".join(
            [
                f"oracle_file_path={oracle_file_path or '(none)'}",
                "file_present={value}".format(
                    value=bool(chunk_stage_miss_details.get("file_present", False))
                ),
                "raw_chunk_present={value}".format(
                    value=bool(chunk_stage_miss_details.get("raw_chunk_present", False))
                ),
                "source_plan_chunk_present={value}".format(
                    value=bool(
                        chunk_stage_miss_details.get("source_plan_chunk_present", False)
                    )
                ),
            ]
        )
    )


__all__ = ["append_case_sections"]
