"""Memory stage for the orchestrator pipeline.

This module handles memory search, retrieval, and timeline building.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from ace_lite.memory import MemoryRecord, MemoryRecordCompact
from ace_lite.memory.gate import decide_memory_retrieval
from ace_lite.memory.postprocess import PostprocessConfig, postprocess_hits_preview
from ace_lite.temporal_filter import TemporalFilter, resolve_temporal_filter
from ace_lite.token_estimator import estimate_tokens

logger = logging.getLogger(__name__)

_LTM_FEEDBACK_SIGNALS = frozenset({"helpful", "stale", "harmful"})


def _estimate_tokens_cached(
    text: str,
    *,
    model: str,
    cache: dict[tuple[str, str], int] | None = None,
) -> int:
    """Estimate tokens with optional per-run memoization."""
    normalized = str(text or "")
    cache_key = (model, normalized)
    if cache is not None:
        cached = cache.get(cache_key)
        if isinstance(cached, int) and cached > 0:
            return cached

    estimated = max(1, int(estimate_tokens(normalized, model=model)))
    if cache is not None:
        cache[cache_key] = estimated
    return estimated


def memory_record_handle(record: MemoryRecord) -> str:
    """Generate a handle for a memory record.

    Args:
        record: MemoryRecord instance.

    Returns:
        Handle string (from metadata or SHA256 fingerprint).
    """
    metadata = record.metadata
    if isinstance(metadata, dict):
        for key in ("id", "handle", "memory_id", "uid"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    metadata_json = json.dumps(
        dict(metadata), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    fingerprint_source = f"{record.text}::{metadata_json}".encode()
    return f"sha256:{hashlib.sha256(fingerprint_source).hexdigest()}"


def parse_memory_timestamp(value: Any) -> float | None:
    """Parse a timestamp value to Unix epoch seconds.

    Args:
        value: Timestamp value (int, float, or ISO string).

    Returns:
        Unix epoch seconds or None if invalid.
    """
    if isinstance(value, (int, float)):
        candidate = float(value)
        if math.isfinite(candidate):
            return candidate
        return None

    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).timestamp()


def extract_memory_record_timestamp(metadata: dict[str, Any]) -> float | None:
    """Extract an epoch timestamp from memory record metadata.

    This helper is intentionally permissive and tries a small set of common keys.
    It does not guess timezones; naive ISO datetimes are treated as UTC for
    deterministic behavior.
    """
    for key in (
        "updated_at_ts",
        "created_at_ts",
        "timestamp",
        "updated_at",
        "created_at",
        "captured_at",
        "last_used_at",
    ):
        ts = parse_memory_timestamp(metadata.get(key))
        if ts is None:
            continue
        if ts <= 0.0:
            continue
        return float(ts)
    return None


def filter_hits_by_temporal_window(
    hits_preview: list[dict[str, Any]],
    *,
    temporal: TemporalFilter,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float | None]]:
    """Filter compact memory hits by a resolved temporal window.

    Unknown-timestamp hits are kept (fail-open) and counted in stats.
    """
    ts_by_handle: dict[str, float | None] = {}
    if not temporal.enabled or (temporal.start_ts is None and temporal.end_ts is None):
        for hit in hits_preview:
            if not isinstance(hit, dict):
                continue
            handle = str(hit.get("handle") or "").strip()
            if not handle:
                continue
            metadata = hit.get("metadata")
            if isinstance(metadata, dict):
                ts_by_handle[handle] = extract_memory_record_timestamp(metadata)
        stats = {
            "requested": True,
            "enabled_effective": True,
            "filtered_out_count": 0,
            "kept_count": len(hits_preview),
            "unknown_timestamp_count": sum(
                1 for value in ts_by_handle.values() if value is None
            ),
        }
        return hits_preview, stats, ts_by_handle

    filtered: list[dict[str, Any]] = []
    filtered_out = 0
    unknown_ts = 0

    start_ts = temporal.start_ts
    end_ts = temporal.end_ts
    for hit in hits_preview:
        if not isinstance(hit, dict):
            continue
        handle = str(hit.get("handle") or "").strip()
        metadata = hit.get("metadata")
        ts: float | None = None
        if isinstance(metadata, dict):
            ts = extract_memory_record_timestamp(metadata)
        if handle:
            ts_by_handle[handle] = ts

        if ts is None:
            unknown_ts += 1
            filtered.append(hit)
            continue

        if start_ts is not None and ts < float(start_ts):
            filtered_out += 1
            continue
        if end_ts is not None and ts > float(end_ts):
            filtered_out += 1
            continue
        filtered.append(hit)

    stats = {
        "requested": True,
        "enabled_effective": True,
        "filtered_out_count": int(filtered_out),
        "kept_count": len(filtered),
        "unknown_timestamp_count": int(unknown_ts),
    }
    return filtered, stats, ts_by_handle


def apply_recency_boost_to_hits(
    hits_preview: list[dict[str, Any]],
    *,
    ts_by_handle: dict[str, float | None],
    max_boost: float,
    bounds_start_ts: float | None,
    bounds_end_ts: float | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    """Apply a capped linear recency boost to hits and re-rank deterministically."""
    resolved_max_boost = max(0.0, float(max_boost))
    if not hits_preview or resolved_max_boost <= 0.0:
        return hits_preview, {
            "enabled_effective": False,
            "max": float(resolved_max_boost),
            "applied_count": 0,
            "max_applied": 0.0,
            "bounds": {"start_ts": bounds_start_ts, "end_ts": bounds_end_ts},
        }, {}

    min_ts: float | None = None
    max_ts: float | None = None
    for _handle, ts in ts_by_handle.items():
        if ts is None:
            continue
        if min_ts is None or ts < min_ts:
            min_ts = ts
        if max_ts is None or ts > max_ts:
            max_ts = ts

    start = (
        float(bounds_start_ts)
        if isinstance(bounds_start_ts, (int, float))
        else min_ts
    )
    end = float(bounds_end_ts) if isinstance(bounds_end_ts, (int, float)) else max_ts

    boost_by_handle: dict[str, float] = {}
    applied_count = 0
    max_applied = 0.0

    denom = None
    if start is not None and end is not None and end > start:
        denom = float(end - start)

    for hit in hits_preview:
        if not isinstance(hit, dict):
            continue
        handle = str(hit.get("handle") or "").strip()
        ts = ts_by_handle.get(handle)
        recency_norm = 0.0
        if ts is not None:
            if denom is not None and start is not None:
                recency_norm = (float(ts) - float(start)) / denom
            elif min_ts is not None and max_ts is not None and max_ts > min_ts:
                recency_norm = (float(ts) - float(min_ts)) / float(max_ts - min_ts)
            else:
                recency_norm = 1.0
        if recency_norm < 0.0:
            recency_norm = 0.0
        if recency_norm > 1.0:
            recency_norm = 1.0

        boost = resolved_max_boost * recency_norm
        if boost > resolved_max_boost:
            boost = resolved_max_boost
        if boost < 0.0:
            boost = 0.0

        boost_by_handle[handle] = boost
        if boost > 0.0:
            applied_count += 1
            if boost > max_applied:
                max_applied = boost

        score = hit.get("score")
        base_score = float(score) if isinstance(score, (int, float)) else 0.0
        hit["score"] = round(base_score + boost, 6)
        breakdown = hit.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            hit["score_breakdown"] = breakdown
        breakdown["recency_boost"] = round(boost, 6)

    hits_preview.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("handle") or ""),
        )
    )

    payload = {
        "enabled_effective": True,
        "max": float(resolved_max_boost),
        "applied_count": int(applied_count),
        "max_applied": float(round(max_applied, 6)),
        "bounds": {"start_ts": start, "end_ts": end},
    }
    return hits_preview, payload, boost_by_handle


def compact_memory_record(
    record: MemoryRecordCompact,
    *,
    preview_max_chars: int = 280,
    tokenizer_model: str = "gpt-4o",
    token_estimate_cache: dict[tuple[str, str], int] | None = None,
) -> dict[str, Any]:
    """Compact a memory record for preview display.

    Args:
        record: MemoryRecordCompact instance.
        preview_max_chars: Maximum characters for preview.
        tokenizer_backend: Tokenizer backend for estimation.
        tokenizer_model: Tokenizer model for estimation.

    Returns:
        Dict with handle, preview, metadata, est_tokens, source.
    """
    preview = str(record.preview or "").strip()
    max_chars = max(32, int(preview_max_chars))
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "..."

    metadata = (
        dict(record.metadata)
        if isinstance(record.metadata, dict)
        else dict(record.metadata or {})
    )
    handle = str(record.handle or "").strip()
    if not handle:
        handle = memory_record_handle(
            MemoryRecord(
                text=preview,
                score=(
                    float(record.score)
                    if isinstance(record.score, (int, float))
                    else None
                ),
                metadata=metadata,
            )
        )

    est_tokens = max(
        1,
        int(
            record.est_tokens
            or _estimate_tokens_cached(
                preview,
                model=tokenizer_model,
                cache=token_estimate_cache,
            )
        ),
    )

    payload: dict[str, Any] = {
        "handle": handle,
        "preview": preview,
        "metadata": metadata,
        "est_tokens": est_tokens,
        "source": str(record.source or "memory"),
    }
    if record.score is not None:
        payload["score"] = float(record.score)
    return payload


def _build_ltm_selected_entry(hit: dict[str, Any]) -> dict[str, Any] | None:
    metadata = hit.get("metadata")
    if not isinstance(metadata, dict):
        return None
    memory_kind = str(metadata.get("memory_kind") or "").strip().lower()
    if memory_kind not in {"fact", "observation"}:
        return None

    handle = str(hit.get("handle") or "").strip()
    if not handle:
        return None

    payload: dict[str, Any] = {
        "handle": handle,
        "memory_kind": memory_kind,
        "source": str(hit.get("source") or "memory"),
    }
    for key in ("as_of", "derived_from_observation_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            payload[key] = value

    if memory_kind == "fact":
        for key in ("fact_type", "subject", "predicate", "object"):
            value = str(metadata.get(key) or "").strip()
            if value:
                payload[key] = value
    else:
        for key in ("kind", "query", "status"):
            value = str(metadata.get(key) or "").strip()
            if value:
                payload[key] = value
    for key in (
        "abstraction_level",
        "freshness_state",
        "contradiction_state",
        "last_confirmed_at",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            payload[key] = value
    support_count = metadata.get("support_count")
    if isinstance(support_count, int):
        payload["support_count"] = max(1, int(support_count))
    feedback_signal = str(metadata.get("feedback_signal") or "").strip().lower()
    if feedback_signal in _LTM_FEEDBACK_SIGNALS:
        payload["feedback_signal"] = feedback_signal
    attribution_scope = str(metadata.get("attribution_scope") or "").strip().lower()
    if attribution_scope:
        payload["attribution_scope"] = attribution_scope
    return payload


def _build_ltm_attribution_entry(hit: dict[str, Any]) -> dict[str, Any] | None:
    metadata = hit.get("metadata")
    if not isinstance(metadata, dict):
        return None
    selected = _build_ltm_selected_entry(hit)
    if selected is None:
        return None

    memory_kind = str(selected["memory_kind"])
    summary = ""
    if memory_kind == "fact":
        summary = " ".join(
            value
            for value in (
                str(selected.get("subject") or "").strip(),
                str(selected.get("predicate") or "").strip(),
                str(selected.get("object") or "").strip(),
            )
            if value
        )
    else:
        summary = " ".join(
            value
            for value in (
                str(selected.get("kind") or "").strip(),
                str(selected.get("query") or "").strip(),
            )
            if value
        )

    payload: dict[str, Any] = {
        "handle": str(selected["handle"]),
        "memory_kind": memory_kind,
        "signals": [memory_kind],
    }
    if summary:
        payload["summary"] = summary
    feedback_signal = str(selected.get("feedback_signal") or "").strip().lower()
    if feedback_signal in _LTM_FEEDBACK_SIGNALS:
        payload["feedback_signal"] = feedback_signal
        payload["signals"].append(feedback_signal)
    attribution_scope = str(selected.get("attribution_scope") or "").strip().lower()
    if attribution_scope:
        payload["attribution_scope"] = attribution_scope

    neighborhood = metadata.get("neighborhood")
    if isinstance(neighborhood, dict):
        triple_count = int(neighborhood.get("triple_count", 0) or 0)
        payload["graph_neighborhood"] = {
            "hops": int(neighborhood.get("hops", 0) or 0),
            "limit": int(neighborhood.get("limit", 0) or 0),
            "triple_count": triple_count,
            "triples": (
                neighborhood.get("triples")
                if isinstance(neighborhood.get("triples"), list)
                else []
            ),
        }
        if triple_count > 0:
            payload["signals"].append("graph_neighborhood")

    derived_from = str(selected.get("derived_from_observation_id") or "").strip()
    if derived_from:
        payload["derived_from_observation_id"] = derived_from
    return payload


def build_ltm_explainability(
    *,
    hits_preview: list[dict[str, Any]],
    hits: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    detail_by_handle: dict[str, dict[str, Any]] = {}
    if isinstance(hits, list):
        for item in hits:
            if not isinstance(item, dict):
                continue
            handle = str(item.get("handle") or "").strip()
            if handle:
                detail_by_handle[handle] = item

    selected: list[dict[str, Any]] = []
    attribution: list[dict[str, Any]] = []
    feedback_signal_counts = {signal: 0 for signal in sorted(_LTM_FEEDBACK_SIGNALS)}
    attribution_scope_counts: dict[str, int] = {}
    for preview_hit in hits_preview:
        if not isinstance(preview_hit, dict):
            continue
        handle = str(preview_hit.get("handle") or "").strip()
        effective_hit = detail_by_handle.get(handle, preview_hit)
        selected_entry = _build_ltm_selected_entry(effective_hit)
        if selected_entry is None:
            continue
        selected.append(selected_entry)
        feedback_signal = str(selected_entry.get("feedback_signal") or "").strip().lower()
        if feedback_signal in feedback_signal_counts:
            feedback_signal_counts[feedback_signal] += 1
        attribution_entry = _build_ltm_attribution_entry(effective_hit)
        if attribution_entry is not None:
            attribution.append(attribution_entry)
            attribution_scope = str(
                attribution_entry.get("attribution_scope") or ""
            ).strip()
            if attribution_scope:
                attribution_scope_counts[attribution_scope] = (
                    int(attribution_scope_counts.get(attribution_scope, 0) or 0) + 1
                )

    return {
        "selected_count": len(selected),
        "attribution_count": len(attribution),
        "selected": selected,
        "attribution": attribution,
        "feedback_signal_counts": feedback_signal_counts,
        "attribution_scope_counts": attribution_scope_counts,
    }


def build_memory_timeline(
    hits_preview: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a timeline grouping of memory hits by date.

    Args:
        hits_preview: List of hit dicts with metadata.

    Returns:
        Dict with enabled, groups, and ungrouped_count.
    """
    groups: dict[str, list[str]] = {}
    ungrouped_count = 0

    for hit in hits_preview:
        if not isinstance(hit, dict):
            continue
        metadata = hit.get("metadata")
        if not isinstance(metadata, dict):
            ungrouped_count += 1
            continue

        handle = str(hit.get("handle") or "").strip()
        if not handle:
            ungrouped_count += 1
            continue

        timestamp = parse_memory_timestamp(
            metadata.get("updated_at")
            or metadata.get("created_at")
            or metadata.get("timestamp")
        )
        if timestamp is None:
            ungrouped_count += 1
            continue

        bucket = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
        groups.setdefault(bucket, [])
        if handle and handle not in groups[bucket]:
            groups[bucket].append(handle)

    ordered_buckets = sorted(groups.keys(), reverse=True)
    return {
        "enabled": True,
        "groups": [
            {
                "date_bucket": bucket,
                "count": len(groups[bucket]),
                "handles": groups[bucket],
            }
            for bucket in ordered_buckets
        ],
        "ungrouped_count": ungrouped_count,
    }


def run_memory(
    *,
    memory_provider: Any,
    query: str,
    disclosure_mode: str = "compact",
    strategy: str = "semantic",
    timeline_enabled: bool = True,
    preview_max_chars: int = 280,
    tokenizer_model: str = "gpt-4o",
    container_tag: str | None = None,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    temporal_enabled: bool = True,
    recency_boost_enabled: bool = False,
    recency_boost_max: float = 0.15,
    timezone_mode: str = "utc",
    now: datetime | None = None,
    namespace_mode: str = "disabled",
    namespace_source: str = "disabled",
    gate_enabled: bool = False,
    gate_mode: str = "auto",
    postprocess_enabled: bool = False,
    postprocess_noise_filter_enabled: bool = True,
    postprocess_length_norm_anchor_chars: int = 500,
    postprocess_time_decay_half_life_days: float = 0.0,
    postprocess_hard_min_score: float = 0.0,
    postprocess_diversity_enabled: bool = True,
    postprocess_diversity_similarity_threshold: float = 0.9,
) -> dict[str, Any]:
    """Run the memory stage.

    Args:
        memory_provider: Memory provider instance (must have search_compact, fetch).
        query: Search query string.
        disclosure_mode: "compact" or "full".
        strategy: "semantic" or "hybrid".
        timeline_enabled: Whether to build timeline.
        preview_max_chars: Maximum characters for preview.
        tokenizer_backend: Tokenizer backend for estimation.
        tokenizer_model: Tokenizer model for estimation.

    Returns:
        Dict with hits_preview, timeline, cache stats, and metrics.
    """
    search_compact = getattr(memory_provider, "search_compact", None)
    fetch = getattr(memory_provider, "fetch", None)
    if not callable(search_compact) or not callable(fetch):
        raise TypeError(
            "memory_provider must implement MemoryProvider: "
            "search_compact(query, limit=...) and fetch(handles)"
        )

    started = perf_counter()
    gate_payload: dict[str, Any] = {
        "enabled": bool(gate_enabled),
        "mode": str(gate_mode or "auto").strip().lower() or "auto",
        "skipped": False,
        "skip_reason": None,
    }
    namespace_fallback: str | None = None
    normalized_gate_mode = gate_payload["mode"]
    should_retrieve = True
    if bool(gate_enabled) and normalized_gate_mode != "never":
        if normalized_gate_mode == "always":
            should_retrieve = True
        else:
            decision = decide_memory_retrieval(query=query)
            should_retrieve = bool(decision.should_retrieve)
            if not should_retrieve:
                gate_payload["skipped"] = True
                gate_payload["skip_reason"] = decision.reason

    if should_retrieve:
        try:
            if container_tag:
                compact_rows_raw = search_compact(
                    query,
                    limit=None,
                    container_tag=container_tag,
                )
            else:
                compact_rows_raw = search_compact(query, limit=None)
        except TypeError:
            namespace_fallback = "provider_unsupported_container_tag"
            compact_rows_raw = search_compact(query, limit=None)
    else:
        compact_rows_raw = []
    provider_namespace_fallback = getattr(
        memory_provider,
        "last_container_tag_fallback",
        None,
    )
    if isinstance(provider_namespace_fallback, str) and provider_namespace_fallback.strip():
        namespace_fallback = provider_namespace_fallback.strip()
    token_estimate_cache: dict[tuple[str, str], int] = {}
    compact_rows: list[MemoryRecordCompact] = []
    if isinstance(compact_rows_raw, list):
        for row in compact_rows_raw:
            if isinstance(row, MemoryRecordCompact):
                compact_rows.append(row)
            elif isinstance(row, dict):
                score_value = row.get("score")
                est_tokens_value = row.get("est_tokens")
                compact_rows.append(
                    MemoryRecordCompact(
                        handle=str(row.get("handle") or ""),
                        preview=str(row.get("preview") or row.get("text") or ""),
                        score=float(score_value)
                        if isinstance(score_value, (int, float))
                        else None,
                        metadata=(
                            row.get("metadata", {})
                            if isinstance(row.get("metadata"), dict)
                            else {}
                        ),
                        est_tokens=max(
                            1,
                            int(
                                est_tokens_value
                                if isinstance(est_tokens_value, int)
                                else _estimate_tokens_cached(
                                    str(row.get("preview") or row.get("text") or ""),
                                    model=tokenizer_model,
                                    cache=token_estimate_cache,
                                )
                            ),
                        ),
                        source=str(row.get("source") or "memory"),
                    )
                )

    hits_preview: list[dict[str, Any]] = []
    for row in compact_rows:
        hits_preview.append(
            compact_memory_record(
                row,
                preview_max_chars=preview_max_chars,
                tokenizer_model=tokenizer_model,
                token_estimate_cache=token_estimate_cache,
            )
        )

    requested_time_range = str(time_range or "").strip() or None
    requested_start_date = str(start_date or "").strip() or None
    requested_end_date = str(end_date or "").strip() or None
    temporal_requested = bool(
        requested_time_range or requested_start_date or requested_end_date
    )

    temporal_payload: dict[str, Any] = {
        "enabled": bool(temporal_enabled),
        "requested": temporal_requested,
        "reason": "disabled",
        "filter": None,
        "filtered_out_count": 0,
        "unknown_timestamp_count": 0,
        "recency_boost": {
            "enabled": bool(recency_boost_enabled),
            "enabled_effective": False,
            "max": float(max(0.0, float(recency_boost_max))),
            "applied_count": 0,
            "max_applied": 0.0,
            "bounds": {"start_ts": None, "end_ts": None},
        },
    }

    ts_by_handle: dict[str, float | None] = {}
    temporal_filter: TemporalFilter | None = None
    if temporal_requested and bool(temporal_enabled):
        temporal_filter = resolve_temporal_filter(
            time_range=requested_time_range,
            start_date=requested_start_date,
            end_date=requested_end_date,
            timezone_mode=str(timezone_mode or "utc"),
            now=now,
        )
        temporal_payload["reason"] = str(temporal_filter.reason)
        temporal_payload["filter"] = temporal_filter.to_payload()
        hits_preview, stats, ts_by_handle = filter_hits_by_temporal_window(
            hits_preview, temporal=temporal_filter
        )
        temporal_payload["filtered_out_count"] = int(stats.get("filtered_out_count", 0) or 0)
        temporal_payload["unknown_timestamp_count"] = int(
            stats.get("unknown_timestamp_count", 0) or 0
        )
    elif temporal_requested and not bool(temporal_enabled):
        temporal_payload["reason"] = "disabled_by_config"
        temporal_payload["filter"] = {
            "enabled": False,
            "reason": "disabled_by_config",
            "timezone_mode": str(timezone_mode or "utc").strip().lower() or "utc",
            "warning": None,
            "input": {
                "time_range": requested_time_range,
                "start_date": requested_start_date,
                "end_date": requested_end_date,
            },
            "resolved": {"start_iso": None, "end_iso": None, "start_ts": None, "end_ts": None},
        }

    recency_effective = (
        bool(temporal_enabled)
        and bool(recency_boost_enabled)
        and float(recency_boost_max) > 0.0
        and bool(hits_preview)
    )
    boost_by_handle: dict[str, float] = {}
    if recency_effective:
        if not ts_by_handle:
            for preview_hit in hits_preview:
                if not isinstance(preview_hit, dict):
                    continue
                handle = str(preview_hit.get("handle") or "").strip()
                if not handle:
                    continue
                metadata = preview_hit.get("metadata")
                if isinstance(metadata, dict):
                    ts_by_handle[handle] = extract_memory_record_timestamp(metadata)
                else:
                    ts_by_handle[handle] = None

        bounds_start_ts: float | None = None
        bounds_end_ts: float | None = None
        if (
            temporal_filter is not None
            and temporal_filter.enabled
            and isinstance(temporal_filter.start_ts, (int, float))
            and isinstance(temporal_filter.end_ts, (int, float))
            and float(temporal_filter.end_ts) > float(temporal_filter.start_ts)
        ):
            bounds_start_ts = float(temporal_filter.start_ts)
            bounds_end_ts = float(temporal_filter.end_ts)

        hits_preview, recency_payload, boost_by_handle = apply_recency_boost_to_hits(
            hits_preview,
            ts_by_handle=ts_by_handle,
            max_boost=float(recency_boost_max),
            bounds_start_ts=bounds_start_ts,
            bounds_end_ts=bounds_end_ts,
        )
        temporal_payload["recency_boost"] = {
            "enabled": bool(recency_boost_enabled),
            **recency_payload,
        }

    postprocess_cfg = PostprocessConfig(
        enabled=bool(postprocess_enabled),
        noise_filter_enabled=bool(postprocess_noise_filter_enabled),
        length_norm_anchor_chars=max(0, int(postprocess_length_norm_anchor_chars)),
        time_decay_half_life_days=max(0.0, float(postprocess_time_decay_half_life_days)),
        hard_min_score=max(0.0, float(postprocess_hard_min_score)),
        diversity_enabled=bool(postprocess_diversity_enabled),
        diversity_similarity_threshold=max(
            0.0,
            min(1.0, float(postprocess_diversity_similarity_threshold)),
        ),
    )
    hits_preview, postprocess_payload = postprocess_hits_preview(
        hits_preview,
        config=postprocess_cfg,
        now=now,
    )

    handles: list[str] = []
    preview_by_handle: dict[str, dict[str, Any]] = {}
    preview_tokens = 0
    for item in hits_preview:
        if not isinstance(item, dict):
            continue
        preview_tokens += int(item.get("est_tokens") or 0)
        handle = str(item.get("handle") or "").strip()
        if not handle:
            continue
        handles.append(handle)
        preview_by_handle[handle] = item

    hits: list[dict[str, Any]] | None = None
    full_tokens = 0
    if disclosure_mode == "full" and handles:
        fetched_records_raw = fetch(handles)
        fetched_records = (
            fetched_records_raw if isinstance(fetched_records_raw, list) else []
        )
        records_by_handle: dict[str, MemoryRecord] = {}
        for record in fetched_records:
            if not isinstance(record, MemoryRecord):
                continue
            handle = str(record.handle or "").strip() or memory_record_handle(record)
            records_by_handle[handle] = record

        hits = []
        for handle in handles:
            record = records_by_handle.get(handle)
            preview_hit = preview_by_handle.get(handle, {})
            if record is None:
                fallback = preview_hit
                text = str(fallback.get("preview") or "")
                metadata = fallback.get("metadata", {})
                score = fallback.get("score")
                score_breakdown = fallback.get("score_breakdown")
                source = fallback.get("source")
                hit: dict[str, Any] = {
                    "handle": handle,
                    "text": text,
                    "metadata": metadata if isinstance(metadata, dict) else {},
                    "source": source,
                }
                if isinstance(score, (int, float)):
                    hit["score"] = float(score)
                if isinstance(score_breakdown, dict):
                    hit["score_breakdown"] = dict(score_breakdown)
            else:
                hit = record.to_dict()
                hit["handle"] = handle
                record_text = str(record.text or "")
                preview_text = str(preview_hit.get("preview") or "")
                preview_est_tokens = preview_hit.get("est_tokens")
                if (
                    isinstance(preview_est_tokens, int)
                    and preview_est_tokens > 0
                    and preview_text == record_text
                ):
                    full_tokens += int(preview_est_tokens)
                else:
                    full_tokens += _estimate_tokens_cached(
                        record_text,
                        model=tokenizer_model,
                        cache=token_estimate_cache,
                    )
                boost = float(boost_by_handle.get(handle, 0.0) or 0.0)
                if boost > 0.0:
                    base_score = (
                        float(hit.get("score", 0.0) or 0.0)
                        if isinstance(hit.get("score"), (int, float))
                        else 0.0
                    )
                    hit["score"] = round(base_score + boost, 6)
                    breakdown = hit.get("score_breakdown")
                    if not isinstance(breakdown, dict):
                        breakdown = {}
                        hit["score_breakdown"] = breakdown
                    breakdown["recency_boost"] = round(boost, 6)
            hits.append(hit)

    provider_strategy = str(
        getattr(memory_provider, "strategy", strategy) or strategy
    )
    channel_used = getattr(memory_provider, "last_channel_used", "unknown")
    fallback_reason = getattr(memory_provider, "fallback_reason", None)
    cache_stats = getattr(memory_provider, "last_cache_stats", {})
    if not isinstance(cache_stats, dict):
        cache_stats = {}
    hybrid_stats = getattr(memory_provider, "last_hybrid_stats", {})
    if not isinstance(hybrid_stats, dict):
        hybrid_stats = {}
    notes_stats = getattr(memory_provider, "last_notes_stats", {})
    if not isinstance(notes_stats, dict):
        notes_stats = {}

    timeline = (
        build_memory_timeline(hits_preview=hits_preview)
        if timeline_enabled
        else {"enabled": False, "groups": [], "ungrouped_count": len(hits_preview)}
    )

    elapsed_ms = (perf_counter() - started) * 1000.0
    log_event = "memory.search"
    if bool(gate_payload.get("skipped")):
        log_event = "memory.search.skipped"
    logger.info(
        log_event,
        extra={
            "channel": str(channel_used),
            "count": len(hits_preview),
            "strategy": provider_strategy,
            "disclosure": disclosure_mode,
            "preview_tokens_est": preview_tokens,
            "full_tokens_est": full_tokens,
            "fallback": bool(fallback_reason),
            "elapsed_ms": round(elapsed_ms, 3),
            "gate_enabled": bool(gate_enabled),
            "gate_mode": str(normalized_gate_mode),
            "gate_skipped": bool(gate_payload.get("skipped")),
            "gate_skip_reason": gate_payload.get("skip_reason"),
            "postprocess_enabled": bool(postprocess_enabled),
        },
    )

    payload: dict[str, Any] = {
        "query": query,
        "count": len(hits_preview),
        "hits_preview": hits_preview,
        "gate": gate_payload,
        "postprocess": postprocess_payload,
        "channel_used": channel_used,
        "fallback_reason": fallback_reason,
        "strategy": provider_strategy,
        "temporal": temporal_payload,
        "namespace": {
            "mode": str(namespace_mode or "disabled"),
            "source": str(namespace_source or "disabled"),
            "container_tag_effective": container_tag if not namespace_fallback else None,
            "container_tag_requested": container_tag,
            "fallback": namespace_fallback,
        },
        "timeline": timeline,
        "cache": {
            "enabled": bool(cache_stats.get("enabled", False)),
            "hit_count": int(cache_stats.get("hit_count", 0) or 0),
            "miss_count": int(cache_stats.get("miss_count", 0) or 0),
            "evicted_count": int(cache_stats.get("evicted_count", 0) or 0),
        },
        "hybrid": {
            "semantic_candidates": int(hybrid_stats.get("semantic_candidates", 0) or 0),
            "keyword_candidates": int(hybrid_stats.get("keyword_candidates", 0) or 0),
            "merged_candidates": int(hybrid_stats.get("merged_candidates", 0) or 0),
            "rrf_k": int(hybrid_stats.get("rrf_k", 0) or 0),
        },
        "notes": {
            "enabled": bool(notes_stats.get("enabled", False)),
            "mode": str(notes_stats.get("mode", "")),
            "notes_path": str(notes_stats.get("notes_path", "")),
            "expiry_enabled": bool(notes_stats.get("expiry_enabled", False)),
            "ttl_days": int(notes_stats.get("ttl_days", 0) or 0),
            "max_age_days": int(notes_stats.get("max_age_days", 0) or 0),
            "loaded_count": int(notes_stats.get("loaded_count", 0) or 0),
            "matched_count": int(notes_stats.get("matched_count", 0) or 0),
            "selected_count": int(notes_stats.get("selected_count", 0) or 0),
            "upstream_selected_count": int(
                notes_stats.get("upstream_selected_count", 0) or 0
            ),
            "local_share": float(notes_stats.get("local_share", 0.0) or 0.0),
            "expired_count": int(notes_stats.get("expired_count", 0) or 0),
            "namespace_filtered_count": int(
                notes_stats.get("namespace_filtered_count", 0) or 0
            ),
        },
        "ltm": build_ltm_explainability(hits_preview=hits_preview, hits=hits),
        "disclosure": {
            "mode": disclosure_mode,
            "preview_max_chars": int(preview_max_chars),
        },
        "cost": {
            "preview_est_tokens_total": int(preview_tokens),
            "full_est_tokens_total": int(full_tokens) if disclosure_mode == "full" else None,
            "fetch_est_tokens_total": int(full_tokens) if disclosure_mode == "full" else 0,
            "saved_est_tokens_total": max(0, int(full_tokens) - int(preview_tokens))
            if disclosure_mode == "full"
            else None,
            "tokenizer_model": tokenizer_model,
            "tokenizer_backend": "tiktoken",
            "tokenizer_encoding": "cl100k_base",
        },
    }
    if hits is not None:
        payload["hits"] = hits

    return payload


__all__ = [
    "apply_recency_boost_to_hits",
    "build_memory_timeline",
    "compact_memory_record",
    "extract_memory_record_timestamp",
    "filter_hits_by_temporal_window",
    "memory_record_handle",
    "parse_memory_timestamp",
    "run_memory",
]
