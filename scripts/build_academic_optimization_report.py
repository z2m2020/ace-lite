from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

TRACKED_METRICS: tuple[str, ...] = (
    "precision_at_k",
    "noise_rate",
    "latency_ms",
    "hit_at_1",
    "reciprocal_rank",
    "chunk_hit_at_k",
    "dependency_recall",
    "task_success_hit",
)

SEMANTIC_RERANK_METRICS: tuple[str, ...] = (
    "embedding_enabled",
    "embedding_semantic_rerank_applied",
    "embedding_rerank_ratio",
    "embedding_similarity_mean",
    "embedding_fallback",
    "embedding_time_budget_exceeded",
    "chunk_semantic_rerank_enabled",
    "chunk_semantic_rerank_ratio",
    "chunk_semantic_similarity_mean",
    "chunk_semantic_fallback",
    "chunk_semantic_time_budget_exceeded",
)


COMPARISON_METRICS: tuple[str, ...] = (
    "precision_at_k_mean",
    "noise_rate_mean",
    "latency_ms_mean",
    "hit_at_1_mean",
    "reciprocal_rank_mean",
    "task_success_hit_mean",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw = payload.get("cases")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _parse_bool_flag(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true", "on", "yes"}:
        return True
    if normalized in {"0", "false", "off", "no"}:
        return False
    raise ValueError(f"invalid boolean flag: {value}")


def _build_case_metadata_map(*, cases: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for item in cases:
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            continue
        output[case_id] = {
            "comparison_lane": str(item.get("comparison_lane") or "").strip(),
            "optimization_surface": str(item.get("optimization_surface") or "").strip(),
            "query_bucket": str(item.get("query_bucket") or "").strip(),
            "query": str(item.get("query") or "").strip(),
        }
    return output


def _aggregate_group(
    *,
    group_name: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    metric_values: dict[str, list[float]] = {name: [] for name in TRACKED_METRICS}
    case_ids: list[str] = []
    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if case_id:
            case_ids.append(case_id)
        for metric in TRACKED_METRICS:
            metric_values[metric].append(_safe_float(row.get(metric), 0.0))

    metrics = {
        f"{metric}_mean": _mean(values)
        for metric, values in metric_values.items()
    }
    return {
        "group": group_name,
        "case_count": len(rows),
        "case_ids": sorted(case_ids),
        "metrics": metrics,
    }


def _aggregate_rows(
    *,
    rows: list[dict[str, Any]],
    metadata_by_case: dict[str, dict[str, str]],
    key_name: str,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        metadata = metadata_by_case.get(case_id, {})
        group_name = str(metadata.get(key_name) or "").strip() or "(unknown)"
        buckets.setdefault(group_name, []).append(row)

    aggregated = [
        _aggregate_group(group_name=group_name, rows=group_rows)
        for group_name, group_rows in buckets.items()
    ]
    aggregated.sort(key=lambda item: (-int(item.get("case_count", 0) or 0), str(item.get("group") or "")))
    return aggregated


def _aggregate_surface_bucket_matrix(
    *,
    rows: list[dict[str, Any]],
    metadata_by_case: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    matrix: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        metadata = metadata_by_case.get(case_id, {})
        surface = str(metadata.get("optimization_surface") or "").strip() or "(unknown)"
        bucket = str(metadata.get("query_bucket") or "").strip() or "(unknown)"
        matrix.setdefault((surface, bucket), []).append(row)

    output: list[dict[str, Any]] = []
    for (surface, bucket), group_rows in matrix.items():
        summary = _aggregate_group(
            group_name=f"{surface}:{bucket}",
            rows=group_rows,
        )
        summary["optimization_surface"] = surface
        summary["query_bucket"] = bucket
        output.append(summary)
    output.sort(
        key=lambda item: (
            str(item.get("optimization_surface") or ""),
            str(item.get("query_bucket") or ""),
        )
    )
    return output


def _aggregate_semantic_rerank_by_bucket(
    *,
    rows: list[dict[str, Any]],
    metadata_by_case: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        metadata = metadata_by_case.get(case_id, {})
        bucket = str(metadata.get("query_bucket") or "").strip() or "(unknown)"
        buckets.setdefault(bucket, []).append(row)

    summaries: list[dict[str, Any]] = []
    for bucket, group_rows in buckets.items():
        provider_counts: dict[str, int] = {}
        mode_counts: dict[str, int] = {}
        metrics: dict[str, float] = {}
        for metric in SEMANTIC_RERANK_METRICS:
            metrics[f"{metric}_mean"] = _mean(
                [_safe_float(item.get(metric), 0.0) for item in group_rows]
            )

        for row in group_rows:
            provider = str(row.get("embedding_runtime_provider") or "").strip() or "(none)"
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            mode = str(row.get("embedding_strategy_mode") or "").strip() or "(unknown)"
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

        dominant_provider = ""
        if provider_counts:
            dominant_provider = sorted(
                provider_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]
        dominant_mode = ""
        if mode_counts:
            dominant_mode = sorted(
                mode_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]

        summaries.append(
            {
                "query_bucket": bucket,
                "case_count": len(group_rows),
                "dominant_provider": dominant_provider,
                "dominant_mode": dominant_mode,
                "provider_case_counts": dict(sorted(provider_counts.items())),
                "mode_case_counts": dict(sorted(mode_counts.items())),
                "metrics": metrics,
            }
        )
    summaries.sort(key=lambda item: (-int(item.get("case_count", 0) or 0), str(item.get("query_bucket") or "")))
    return summaries


def build_academic_optimization_summary(
    *,
    results_payload: dict[str, Any],
    cases_payload: list[dict[str, Any]],
    runtime_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows_raw = results_payload.get("cases")
    rows = [item for item in rows_raw if isinstance(item, dict)] if isinstance(rows_raw, list) else []
    metadata_by_case = _build_case_metadata_map(cases=cases_payload)

    missing_metadata_case_ids = sorted(
        {
            str(item.get("case_id") or "").strip()
            for item in rows
            if str(item.get("case_id") or "").strip()
            and str(item.get("case_id") or "").strip() not in metadata_by_case
        }
    )
    comparison_lanes = sorted(
        {
            str(item.get("comparison_lane") or "").strip()
            for item in rows
            if str(item.get("comparison_lane") or "").strip()
        }
    )
    overall = _aggregate_group(group_name="overall", rows=rows)
    return {
        "generated_at": str(results_payload.get("generated_at") or ""),
        "repo": str(results_payload.get("repo") or ""),
        "root": str(results_payload.get("root") or ""),
        "runtime_flags": dict(runtime_flags or {}),
        "case_count": len(rows),
        "comparison_lanes": comparison_lanes,
        "metadata_coverage": {
            "linked_case_count": len(rows) - len(missing_metadata_case_ids),
            "missing_case_count": len(missing_metadata_case_ids),
            "missing_case_ids": missing_metadata_case_ids,
        },
        "overall": overall,
        "by_surface": _aggregate_rows(
            rows=rows,
            metadata_by_case=metadata_by_case,
            key_name="optimization_surface",
        ),
        "by_query_bucket": _aggregate_rows(
            rows=rows,
            metadata_by_case=metadata_by_case,
            key_name="query_bucket",
        ),
        "semantic_rerank_by_query_bucket": _aggregate_semantic_rerank_by_bucket(
            rows=rows,
            metadata_by_case=metadata_by_case,
        ),
        "surface_bucket_matrix": _aggregate_surface_bucket_matrix(
            rows=rows,
            metadata_by_case=metadata_by_case,
        ),
    }


def build_academic_optimization_markdown(*, summary: dict[str, Any]) -> str:
    overall = summary.get("overall", {})
    overall_metrics_raw = overall.get("metrics")
    overall_metrics = overall_metrics_raw if isinstance(overall_metrics_raw, dict) else {}

    lines = [
        "# Academic Optimization Benchmark Summary",
        "",
        "- Repo: {repo}".format(repo=str(summary.get("repo") or "")),
        "- Case count: {count}".format(count=int(summary.get("case_count", 0) or 0)),
        "- Comparison lanes: {lanes}".format(
            lanes=", ".join(summary.get("comparison_lanes", [])) or "(none)"
        ),
        "- Metadata coverage: linked={linked} missing={missing}".format(
            linked=int(
                summary.get("metadata_coverage", {}).get("linked_case_count", 0) or 0
            ),
            missing=int(
                summary.get("metadata_coverage", {}).get("missing_case_count", 0) or 0
            ),
        ),
    ]
    runtime_flags = summary.get("runtime_flags", {})
    if isinstance(runtime_flags, dict) and runtime_flags:
        lines.append(
            "- Runtime flags: {flags}".format(
                flags=", ".join(
                    f"{key}={value}"
                    for key, value in sorted(runtime_flags.items())
                )
            )
        )
    lines.extend(
        [
            "",
            "## Overall",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
    )
    for metric in TRACKED_METRICS:
        lines.append(
            "| {metric} | {value:.4f} |".format(
                metric=f"{metric}_mean",
                value=_safe_float(overall_metrics.get(f"{metric}_mean"), 0.0),
            )
        )
    lines.append("")

    lines.append("## By Surface")
    lines.append("")
    lines.append(
        "| Surface | Case Count | Precision | Noise | Latency | Chunk Hit | Dependency Recall | Task Success |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in summary.get("by_surface", []):
        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        lines.append(
            "| {surface} | {count} | {precision:.4f} | {noise:.4f} | {latency:.4f} | {chunk_hit:.4f} | {dependency:.4f} | {task_success:.4f} |".format(
                surface=str(item.get("group") or ""),
                count=int(item.get("case_count", 0) or 0),
                precision=_safe_float(metrics.get("precision_at_k_mean"), 0.0),
                noise=_safe_float(metrics.get("noise_rate_mean"), 0.0),
                latency=_safe_float(metrics.get("latency_ms_mean"), 0.0),
                chunk_hit=_safe_float(metrics.get("chunk_hit_at_k_mean"), 0.0),
                dependency=_safe_float(metrics.get("dependency_recall_mean"), 0.0),
                task_success=_safe_float(metrics.get("task_success_hit_mean"), 0.0),
            )
        )
    lines.append("")

    lines.append("## By Query Bucket")
    lines.append("")
    lines.append(
        "| Query Bucket | Case Count | Precision | Noise | Latency | Hit@1 | MRR | Task Success |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in summary.get("by_query_bucket", []):
        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        lines.append(
            "| {bucket} | {count} | {precision:.4f} | {noise:.4f} | {latency:.4f} | {hit_at_1:.4f} | {mrr:.4f} | {task_success:.4f} |".format(
                bucket=str(item.get("group") or ""),
                count=int(item.get("case_count", 0) or 0),
                precision=_safe_float(metrics.get("precision_at_k_mean"), 0.0),
                noise=_safe_float(metrics.get("noise_rate_mean"), 0.0),
                latency=_safe_float(metrics.get("latency_ms_mean"), 0.0),
                hit_at_1=_safe_float(metrics.get("hit_at_1_mean"), 0.0),
                mrr=_safe_float(metrics.get("reciprocal_rank_mean"), 0.0),
                task_success=_safe_float(metrics.get("task_success_hit_mean"), 0.0),
            )
        )
    lines.append("")

    lines.append("## Semantic Rerank By Query Bucket")
    lines.append("")
    lines.append(
        "| Query Bucket | Case Count | Provider | Mode | Embedding Enabled | Embedding Applied | Embedding Fallback | Embedding Budget Exceeded | Chunk Semantic Enabled | Chunk Semantic Fallback | Chunk Semantic Budget Exceeded |"
    )
    lines.append("| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in summary.get("semantic_rerank_by_query_bucket", []):
        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        lines.append(
            "| {bucket} | {count} | {provider} | {mode} | {embedding_enabled:.4f} | {embedding_applied:.4f} | {embedding_fallback:.4f} | {embedding_budget:.4f} | {chunk_enabled:.4f} | {chunk_fallback:.4f} | {chunk_budget:.4f} |".format(
                bucket=str(item.get("query_bucket") or ""),
                count=int(item.get("case_count", 0) or 0),
                provider=str(item.get("dominant_provider") or ""),
                mode=str(item.get("dominant_mode") or ""),
                embedding_enabled=_safe_float(metrics.get("embedding_enabled_mean"), 0.0),
                embedding_applied=_safe_float(
                    metrics.get("embedding_semantic_rerank_applied_mean"), 0.0
                ),
                embedding_fallback=_safe_float(metrics.get("embedding_fallback_mean"), 0.0),
                embedding_budget=_safe_float(
                    metrics.get("embedding_time_budget_exceeded_mean"), 0.0
                ),
                chunk_enabled=_safe_float(
                    metrics.get("chunk_semantic_rerank_enabled_mean"), 0.0
                ),
                chunk_fallback=_safe_float(
                    metrics.get("chunk_semantic_fallback_mean"), 0.0
                ),
                chunk_budget=_safe_float(
                    metrics.get("chunk_semantic_time_budget_exceeded_mean"), 0.0
                ),
            )
        )
    lines.append("")

    lines.append("## Surface x Bucket")
    lines.append("")
    lines.append(
        "| Surface | Query Bucket | Case Count | Precision | Noise | Task Success |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for item in summary.get("surface_bucket_matrix", []):
        metrics_raw = item.get("metrics")
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
        lines.append(
            "| {surface} | {bucket} | {count} | {precision:.4f} | {noise:.4f} | {task_success:.4f} |".format(
                surface=str(item.get("optimization_surface") or ""),
                bucket=str(item.get("query_bucket") or ""),
                count=int(item.get("case_count", 0) or 0),
                precision=_safe_float(metrics.get("precision_at_k_mean"), 0.0),
                noise=_safe_float(metrics.get("noise_rate_mean"), 0.0),
                task_success=_safe_float(metrics.get("task_success_hit_mean"), 0.0),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_metric_triplet(
    *,
    baseline_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
    metric_names: tuple[str, ...],
) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for metric in metric_names:
        baseline_value = _safe_float(baseline_metrics.get(metric), 0.0)
        current_value = _safe_float(current_metrics.get(metric), 0.0)
        output[metric] = {
            "baseline": baseline_value,
            "current": current_value,
            "delta": current_value - baseline_value,
        }
    return output


def build_academic_optimization_comparison(
    *,
    baseline_summary: dict[str, Any],
    current_summary: dict[str, Any],
) -> dict[str, Any]:
    baseline_overall = baseline_summary.get("overall", {})
    current_overall = current_summary.get("overall", {})
    baseline_overall_metrics = (
        baseline_overall.get("metrics") if isinstance(baseline_overall, dict) else {}
    )
    current_overall_metrics = (
        current_overall.get("metrics") if isinstance(current_overall, dict) else {}
    )
    baseline_bucket_map = {
        str(item.get("group") or ""): item
        for item in baseline_summary.get("by_query_bucket", [])
        if isinstance(item, dict)
    }
    current_bucket_map = {
        str(item.get("group") or ""): item
        for item in current_summary.get("by_query_bucket", [])
        if isinstance(item, dict)
    }
    baseline_surface_map = {
        str(item.get("group") or ""): item
        for item in baseline_summary.get("by_surface", [])
        if isinstance(item, dict)
    }
    current_surface_map = {
        str(item.get("group") or ""): item
        for item in current_summary.get("by_surface", [])
        if isinstance(item, dict)
    }
    baseline_semantic_map = {
        str(item.get("query_bucket") or ""): item
        for item in baseline_summary.get("semantic_rerank_by_query_bucket", [])
        if isinstance(item, dict)
    }
    current_semantic_map = {
        str(item.get("query_bucket") or ""): item
        for item in current_summary.get("semantic_rerank_by_query_bucket", [])
        if isinstance(item, dict)
    }

    query_bucket_comparison: list[dict[str, Any]] = []
    for bucket in sorted(set(baseline_bucket_map) | set(current_bucket_map)):
        baseline_bucket = baseline_bucket_map.get(bucket, {})
        current_bucket = current_bucket_map.get(bucket, {})
        baseline_metrics = (
            baseline_bucket.get("metrics") if isinstance(baseline_bucket, dict) else {}
        )
        current_metrics = (
            current_bucket.get("metrics") if isinstance(current_bucket, dict) else {}
        )
        query_bucket_comparison.append(
            {
                "query_bucket": bucket,
                "baseline_case_count": int(
                    baseline_bucket.get("case_count", 0) if isinstance(baseline_bucket, dict) else 0
                ),
                "current_case_count": int(
                    current_bucket.get("case_count", 0) if isinstance(current_bucket, dict) else 0
                ),
                "metrics": _build_metric_triplet(
                    baseline_metrics=(
                        baseline_metrics if isinstance(baseline_metrics, dict) else {}
                    ),
                    current_metrics=(
                        current_metrics if isinstance(current_metrics, dict) else {}
                    ),
                    metric_names=COMPARISON_METRICS,
                ),
            }
        )

    surface_comparison: list[dict[str, Any]] = []
    for surface in sorted(set(baseline_surface_map) | set(current_surface_map)):
        baseline_surface = baseline_surface_map.get(surface, {})
        current_surface = current_surface_map.get(surface, {})
        baseline_metrics = (
            baseline_surface.get("metrics") if isinstance(baseline_surface, dict) else {}
        )
        current_metrics = (
            current_surface.get("metrics") if isinstance(current_surface, dict) else {}
        )
        surface_comparison.append(
            {
                "optimization_surface": surface,
                "baseline_case_count": int(
                    baseline_surface.get("case_count", 0)
                    if isinstance(baseline_surface, dict)
                    else 0
                ),
                "current_case_count": int(
                    current_surface.get("case_count", 0)
                    if isinstance(current_surface, dict)
                    else 0
                ),
                "metrics": _build_metric_triplet(
                    baseline_metrics=(
                        baseline_metrics if isinstance(baseline_metrics, dict) else {}
                    ),
                    current_metrics=(
                        current_metrics if isinstance(current_metrics, dict) else {}
                    ),
                    metric_names=COMPARISON_METRICS,
                ),
            }
        )

    semantic_bucket_comparison: list[dict[str, Any]] = []
    for bucket in sorted(set(baseline_semantic_map) | set(current_semantic_map)):
        baseline_bucket = baseline_semantic_map.get(bucket, {})
        current_bucket = current_semantic_map.get(bucket, {})
        baseline_metrics = (
            baseline_bucket.get("metrics") if isinstance(baseline_bucket, dict) else {}
        )
        current_metrics = (
            current_bucket.get("metrics") if isinstance(current_bucket, dict) else {}
        )
        semantic_bucket_comparison.append(
            {
                "query_bucket": bucket,
                "baseline_provider": str(
                    baseline_bucket.get("dominant_provider") if isinstance(baseline_bucket, dict) else ""
                ),
                "current_provider": str(
                    current_bucket.get("dominant_provider") if isinstance(current_bucket, dict) else ""
                ),
                "baseline_mode": str(
                    baseline_bucket.get("dominant_mode") if isinstance(baseline_bucket, dict) else ""
                ),
                "current_mode": str(
                    current_bucket.get("dominant_mode") if isinstance(current_bucket, dict) else ""
                ),
                "metrics": _build_metric_triplet(
                    baseline_metrics=(
                        baseline_metrics if isinstance(baseline_metrics, dict) else {}
                    ),
                    current_metrics=(
                        current_metrics if isinstance(current_metrics, dict) else {}
                    ),
                    metric_names=(
                        "embedding_enabled_mean",
                        "embedding_semantic_rerank_applied_mean",
                        "embedding_fallback_mean",
                        "embedding_time_budget_exceeded_mean",
                        "chunk_semantic_rerank_enabled_mean",
                        "chunk_semantic_fallback_mean",
                        "chunk_semantic_time_budget_exceeded_mean",
                    ),
                ),
            }
        )

    return {
        "generated_at": str(current_summary.get("generated_at") or ""),
        "repo": str(current_summary.get("repo") or ""),
        "baseline_runtime_flags": (
            dict(baseline_summary.get("runtime_flags", {}))
            if isinstance(baseline_summary.get("runtime_flags"), dict)
            else {}
        ),
        "current_runtime_flags": (
            dict(current_summary.get("runtime_flags", {}))
            if isinstance(current_summary.get("runtime_flags"), dict)
            else {}
        ),
        "baseline_case_count": int(baseline_summary.get("case_count", 0) or 0),
        "current_case_count": int(current_summary.get("case_count", 0) or 0),
        "overall_metrics": _build_metric_triplet(
            baseline_metrics=(
                baseline_overall_metrics if isinstance(baseline_overall_metrics, dict) else {}
            ),
            current_metrics=(
                current_overall_metrics if isinstance(current_overall_metrics, dict) else {}
            ),
            metric_names=COMPARISON_METRICS,
        ),
        "by_surface": surface_comparison,
        "by_query_bucket": query_bucket_comparison,
        "semantic_rerank_by_query_bucket": semantic_bucket_comparison,
    }


def build_academic_optimization_comparison_markdown(
    *,
    comparison: dict[str, Any],
) -> str:
    lines = [
        "# Academic Optimization Benchmark Comparison",
        "",
        "- Repo: {repo}".format(repo=str(comparison.get("repo") or "")),
        "- Baseline case count: {count}".format(
            count=int(comparison.get("baseline_case_count", 0) or 0)
        ),
        "- Current case count: {count}".format(
            count=int(comparison.get("current_case_count", 0) or 0)
        ),
    ]
    baseline_runtime_flags = comparison.get("baseline_runtime_flags", {})
    current_runtime_flags = comparison.get("current_runtime_flags", {})
    if isinstance(baseline_runtime_flags, dict) and baseline_runtime_flags:
        lines.append(
            "- Baseline runtime flags: {flags}".format(
                flags=", ".join(
                    f"{key}={value}"
                    for key, value in sorted(baseline_runtime_flags.items())
                )
            )
        )
    if isinstance(current_runtime_flags, dict) and current_runtime_flags:
        lines.append(
            "- Current runtime flags: {flags}".format(
                flags=", ".join(
                    f"{key}={value}"
                    for key, value in sorted(current_runtime_flags.items())
                )
            )
        )
    lines.extend(
        [
            "",
            "## Overall Delta",
            "",
            "| Metric | Baseline | Current | Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    overall_metrics = comparison.get("overall_metrics", {})
    for metric in COMPARISON_METRICS:
        item = overall_metrics.get(metric, {}) if isinstance(overall_metrics, dict) else {}
        lines.append(
            "| {metric} | {baseline:.4f} | {current:.4f} | {delta:+.4f} |".format(
                metric=metric,
                baseline=_safe_float(item.get("baseline"), 0.0),
                current=_safe_float(item.get("current"), 0.0),
                delta=_safe_float(item.get("delta"), 0.0),
            )
        )
    lines.append("")

    lines.append("## Surface Delta")
    lines.append("")
    lines.append(
        "| Surface | Precision Delta | Noise Delta | Latency Delta | Hit@1 Delta | MRR Delta | Task Success Delta |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in comparison.get("by_surface", []):
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        lines.append(
            "| {surface} | {precision:+.4f} | {noise:+.4f} | {latency:+.4f} | {hit_at_1:+.4f} | {mrr:+.4f} | {task_success:+.4f} |".format(
                surface=str(item.get("optimization_surface") or ""),
                precision=_safe_float(
                    metrics.get("precision_at_k_mean", {}).get("delta"), 0.0
                ),
                noise=_safe_float(metrics.get("noise_rate_mean", {}).get("delta"), 0.0),
                latency=_safe_float(metrics.get("latency_ms_mean", {}).get("delta"), 0.0),
                hit_at_1=_safe_float(metrics.get("hit_at_1_mean", {}).get("delta"), 0.0),
                mrr=_safe_float(metrics.get("reciprocal_rank_mean", {}).get("delta"), 0.0),
                task_success=_safe_float(
                    metrics.get("task_success_hit_mean", {}).get("delta"), 0.0
                ),
            )
        )
    lines.append("")

    lines.append("## Query Bucket Delta")
    lines.append("")
    lines.append(
        "| Query Bucket | Precision Delta | Noise Delta | Latency Delta | Hit@1 Delta | MRR Delta | Task Success Delta |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in comparison.get("by_query_bucket", []):
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        lines.append(
            "| {bucket} | {precision:+.4f} | {noise:+.4f} | {latency:+.4f} | {hit_at_1:+.4f} | {mrr:+.4f} | {task_success:+.4f} |".format(
                bucket=str(item.get("query_bucket") or ""),
                precision=_safe_float(
                    metrics.get("precision_at_k_mean", {}).get("delta"), 0.0
                ),
                noise=_safe_float(metrics.get("noise_rate_mean", {}).get("delta"), 0.0),
                latency=_safe_float(metrics.get("latency_ms_mean", {}).get("delta"), 0.0),
                hit_at_1=_safe_float(metrics.get("hit_at_1_mean", {}).get("delta"), 0.0),
                mrr=_safe_float(metrics.get("reciprocal_rank_mean", {}).get("delta"), 0.0),
                task_success=_safe_float(
                    metrics.get("task_success_hit_mean", {}).get("delta"), 0.0
                ),
            )
        )
    lines.append("")

    lines.append("## Semantic Rerank Delta")
    lines.append("")
    lines.append(
        "| Query Bucket | Baseline Provider | Current Provider | Baseline Mode | Current Mode | Embedding Enabled Delta | Embedding Applied Delta | Embedding Fallback Delta | Chunk Enabled Delta | Chunk Fallback Delta |"
    )
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for item in comparison.get("semantic_rerank_by_query_bucket", []):
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        lines.append(
            "| {bucket} | {baseline_provider} | {current_provider} | {baseline_mode} | {current_mode} | {embedding_enabled:+.4f} | {embedding_applied:+.4f} | {embedding_fallback:+.4f} | {chunk_enabled:+.4f} | {chunk_fallback:+.4f} |".format(
                bucket=str(item.get("query_bucket") or ""),
                baseline_provider=str(item.get("baseline_provider") or ""),
                current_provider=str(item.get("current_provider") or ""),
                baseline_mode=str(item.get("baseline_mode") or ""),
                current_mode=str(item.get("current_mode") or ""),
                embedding_enabled=_safe_float(
                    metrics.get("embedding_enabled_mean", {}).get("delta"), 0.0
                ),
                embedding_applied=_safe_float(
                    metrics.get("embedding_semantic_rerank_applied_mean", {}).get("delta"),
                    0.0,
                ),
                embedding_fallback=_safe_float(
                    metrics.get("embedding_fallback_mean", {}).get("delta"), 0.0
                ),
                chunk_enabled=_safe_float(
                    metrics.get("chunk_semantic_rerank_enabled_mean", {}).get("delta"),
                    0.0,
                ),
                chunk_fallback=_safe_float(
                    metrics.get("chunk_semantic_fallback_mean", {}).get("delta"), 0.0
                ),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an aggregated summary for the academic optimization benchmark lane."
    )
    parser.add_argument("--results", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--baseline-summary",
        default=None,
        help="Optional academic_summary.json from the baseline lane for comparison output.",
    )
    parser.add_argument(
        "--query-expansion-enabled",
        default=None,
        help="Optional runtime flag recorded into summary/comparison outputs.",
    )
    args = parser.parse_args(argv)

    results_path = Path(str(args.results)).expanduser().resolve()
    cases_path = Path(str(args.cases)).expanduser().resolve()
    output_dir = Path(str(args.output_dir)).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = build_academic_optimization_summary(
        results_payload=_load_json(results_path),
        cases_payload=_load_cases(cases_path),
        runtime_flags=(
            {"query_expansion_enabled": _parse_bool_flag(args.query_expansion_enabled)}
            if args.query_expansion_enabled is not None
            else None
        ),
    )
    markdown = build_academic_optimization_markdown(summary=summary)

    summary_path = output_dir / "academic_summary.json"
    report_path = output_dir / "academic_report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    report_path.write_text(markdown, encoding="utf-8")

    comparison_path: Path | None = None
    comparison_report_path: Path | None = None
    if args.baseline_summary:
        baseline_summary_path = Path(str(args.baseline_summary)).expanduser().resolve()
        baseline_summary = _load_json(baseline_summary_path)
        if baseline_summary:
            comparison = build_academic_optimization_comparison(
                baseline_summary=baseline_summary,
                current_summary=summary,
            )
            comparison_markdown = build_academic_optimization_comparison_markdown(
                comparison=comparison,
            )
            comparison_path = output_dir / "academic_comparison.json"
            comparison_report_path = output_dir / "academic_comparison.md"
            comparison_path.write_text(
                json.dumps(comparison, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            comparison_report_path.write_text(comparison_markdown, encoding="utf-8")

    print(
        json.dumps(
            {
                "summary_json": str(summary_path),
                "report_md": str(report_path),
                "comparison_json": str(comparison_path) if comparison_path else "",
                "comparison_md": (
                    str(comparison_report_path) if comparison_report_path else ""
                ),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
