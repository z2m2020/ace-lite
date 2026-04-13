"""Deterministic memory hit post-processing utilities.

These helpers operate on the memory stage `hits_preview` dicts and are intended
to make memory injection safer (less noise, less drift) while keeping outputs
deterministic and testable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ace_lite.memory.timestamps import extract_memory_record_timestamp

_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bas an ai language model\b", re.IGNORECASE),
    re.compile(r"\bi (can'?t|cannot) (help|comply|do that)\b", re.IGNORECASE),
    re.compile(r"\bi('?m| am) sorry\b", re.IGNORECASE),
    re.compile(r"\bpolicy\b", re.IGNORECASE),
    re.compile(r"^i (can't|cannot)\b", re.IGNORECASE),
    # Chinese refusals / boilerplate (conservative)
    re.compile(r"(抱歉|无法|不能|我不能|我无法)"),
)


def _coerce_text(hit: dict[str, Any]) -> str:
    text = hit.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    preview = hit.get("preview")
    if isinstance(preview, str):
        return preview.strip()
    return ""


def _stable_handle(hit: dict[str, Any]) -> str:
    handle = hit.get("handle")
    if isinstance(handle, str) and handle.strip():
        return handle.strip()
    return ""


def filter_noise_hits(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    dropped = 0
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        text = _coerce_text(hit)
        if not text:
            dropped += 1
            continue
        lower = text.lower()
        if any(p.search(lower) for p in _NOISE_PATTERNS):
            dropped += 1
            continue
        filtered.append(hit)
    return filtered, {"dropped": int(dropped), "kept": len(filtered)}


def apply_length_normalization(
    hits: list[dict[str, Any]], *, anchor_chars: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    anchor = max(0, int(anchor_chars))
    if not hits or anchor <= 0:
        return hits, {"enabled_effective": False, "anchor_chars": int(anchor), "applied_count": 0}

    applied = 0
    max_penalty = 0.0
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        text = _coerce_text(hit)
        if not text:
            continue
        length = max(0, len(text))
        # penalty factor in (0, 1]; shorter texts get ~1.0.
        factor = 1.0
        if length > 0 and anchor > 0:
            ratio = float(length) / float(anchor)
            if ratio > 1.0:
                factor = 1.0 / (1.0 + math.log2(max(1.0, ratio)))
        if factor < 1.0:
            applied += 1
            penalty = 1.0 - factor
            if penalty > max_penalty:
                max_penalty = penalty

        base_score = float(hit.get("score") or 0.0) if isinstance(hit.get("score"), (int, float)) else 0.0
        hit["score"] = round(base_score * factor, 6)
        breakdown = hit.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            hit["score_breakdown"] = breakdown
        breakdown["length_norm_factor"] = round(float(factor), 6)
    hits.sort(key=lambda item: (-float(item.get("score") or 0.0), _stable_handle(item)))
    return hits, {
        "enabled_effective": True,
        "anchor_chars": int(anchor),
        "applied_count": int(applied),
        "max_penalty": round(float(max_penalty), 6),
    }


def apply_time_decay(
    hits: list[dict[str, Any]], *, half_life_days: float, now: datetime | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hl = float(half_life_days) if isinstance(half_life_days, (int, float)) else 0.0
    if not hits or hl <= 0.0:
        return hits, {"enabled_effective": False, "half_life_days": float(hl), "applied_count": 0}

    effective_now = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    now_ts = effective_now.timestamp()
    applied = 0
    min_factor = 1.0
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        metadata = hit.get("metadata")
        ts = extract_memory_record_timestamp(metadata) if isinstance(metadata, dict) else None
        factor = 1.0
        if ts is not None and ts > 0.0:
            age_days = max(0.0, (now_ts - float(ts)) / 86400.0)
            # Floor at 0.5x, exponential toward 0.5 with half-life.
            factor = 0.5 + 0.5 * math.exp(-age_days / hl)
            applied += 1
            if factor < min_factor:
                min_factor = factor

        base_score = float(hit.get("score") or 0.0) if isinstance(hit.get("score"), (int, float)) else 0.0
        hit["score"] = round(base_score * factor, 6)
        breakdown = hit.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            hit["score_breakdown"] = breakdown
        breakdown["time_decay_factor"] = round(float(factor), 6)

    hits.sort(key=lambda item: (-float(item.get("score") or 0.0), _stable_handle(item)))
    return hits, {
        "enabled_effective": True,
        "half_life_days": float(hl),
        "applied_count": int(applied),
        "min_factor": round(float(min_factor), 6),
    }


def hard_min_score_filter(
    hits: list[dict[str, Any]], *, hard_min_score: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    threshold = float(hard_min_score) if isinstance(hard_min_score, (int, float)) else 0.0
    if not hits or threshold <= 0.0:
        return hits, {"enabled_effective": False, "hard_min_score": float(threshold), "dropped": 0}
    kept: list[dict[str, Any]] = []
    dropped = 0
    for hit in hits:
        score = hit.get("score")
        s = float(score) if isinstance(score, (int, float)) else 0.0
        if s >= threshold:
            kept.append(hit)
        else:
            dropped += 1
    return kept, {"enabled_effective": True, "hard_min_score": float(threshold), "dropped": int(dropped)}


def _tokenize(text: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()
    return {token for token in normalized.split() if token}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    if inter <= 0:
        return 0.0
    union = len(a.union(b))
    return float(inter) / float(max(1, union))


def apply_diversity_filter(
    hits: list[dict[str, Any]], *, similarity_threshold: float = 0.9
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    thr = float(similarity_threshold)
    if not hits or thr <= 0.0:
        return hits, {"enabled_effective": False, "threshold": float(thr), "dropped": 0}

    selected: list[dict[str, Any]] = []
    selected_tokens: list[set[str]] = []
    dropped = 0

    for hit in hits:
        text = _coerce_text(hit)
        tokens = _tokenize(text)
        is_dup = any(_jaccard(tokens, existing) >= thr for existing in selected_tokens)
        if is_dup:
            dropped += 1
            continue
        selected.append(hit)
        selected_tokens.append(tokens)

    return selected, {"enabled_effective": True, "threshold": float(thr), "dropped": int(dropped)}


@dataclass(frozen=True, slots=True)
class PostprocessConfig:
    enabled: bool = False
    noise_filter_enabled: bool = True
    length_norm_anchor_chars: int = 500
    time_decay_half_life_days: float = 0.0
    hard_min_score: float = 0.0
    diversity_enabled: bool = True
    diversity_similarity_threshold: float = 0.9


def postprocess_hits_preview(
    hits_preview: list[dict[str, Any]],
    *,
    config: PostprocessConfig,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not config.enabled:
        return hits_preview, {"enabled": False}

    working = [dict(item) for item in hits_preview if isinstance(item, dict)]
    telemetry: dict[str, Any] = {"enabled": True}

    if config.noise_filter_enabled:
        working, noise_stats = filter_noise_hits(working)
        telemetry["noise_filter"] = noise_stats

    working, length_stats = apply_length_normalization(
        working, anchor_chars=int(config.length_norm_anchor_chars)
    )
    telemetry["length_norm"] = length_stats

    working, decay_stats = apply_time_decay(
        working, half_life_days=float(config.time_decay_half_life_days), now=now
    )
    telemetry["time_decay"] = decay_stats

    working, hard_stats = hard_min_score_filter(working, hard_min_score=float(config.hard_min_score))
    telemetry["hard_min_score"] = hard_stats

    if config.diversity_enabled:
        working, div_stats = apply_diversity_filter(
            working, similarity_threshold=float(config.diversity_similarity_threshold)
        )
        telemetry["diversity"] = div_stats

    working.sort(key=lambda item: (-float(item.get("score") or 0.0), _stable_handle(item)))
    telemetry["kept_count"] = len(working)
    return working, telemetry


__all__ = [
    "PostprocessConfig",
    "postprocess_hits_preview",
]
