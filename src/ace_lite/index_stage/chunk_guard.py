from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.chunking.robust_signature import (
    chunk_identity_key,
    count_available_robust_signatures,
)

CHUNK_GUARD_MODE_CHOICES: tuple[str, ...] = ("off", "report_only", "enforce")


@dataclass(frozen=True, slots=True)
class ChunkGuardResult:
    candidate_chunks: list[dict[str, Any]]
    chunk_guard_payload: dict[str, Any]


def _normalize_mode(value: Any) -> str:
    normalized = str(value or "off").strip().lower() or "off"
    if normalized not in CHUNK_GUARD_MODE_CHOICES:
        return "off"
    return normalized


def apply_chunk_guard(
    *,
    candidate_chunks: list[dict[str, Any]],
    robust_signature_sidecar: dict[str, dict[str, Any]] | None = None,
    enabled: bool,
    mode: str,
    lambda_penalty: float,
    min_pool: int,
    max_pool: int,
    min_marginal_utility: float,
    compatibility_min_overlap: float,
) -> ChunkGuardResult:
    chunks = list(candidate_chunks) if isinstance(candidate_chunks, list) else []
    output_chunks = list(chunks)
    normalized_mode = _normalize_mode(mode)
    enabled_effective = bool(enabled) or normalized_mode != "off"
    if bool(enabled) and normalized_mode == "off":
        normalized_mode = "report_only"
        enabled_effective = True
    elif normalized_mode == "off":
        enabled_effective = False

    normalized_min_pool = max(1, int(min_pool or 0))
    normalized_max_pool = max(normalized_min_pool, int(max_pool or 0))
    signed_chunk_count = count_available_robust_signatures(
        candidate_chunks=chunks,
        sidecar=robust_signature_sidecar,
    )
    if signed_chunk_count <= 0:
        signed_chunk_count = sum(
            1
            for item in chunks
            if isinstance(item, dict) and str(item.get("signature") or "").strip()
        )

    candidate_pool = len(chunks)
    reason = "disabled"
    fallback = False
    filtered_keys: list[str] = []
    retained_keys: list[str] = []
    filtered_refs: list[str] = []
    retained_refs: list[str] = []
    pairwise_conflict_count = 0
    max_conflict_penalty = 0.0
    if enabled_effective:
        if candidate_pool <= 0:
            reason = "no_chunks"
        elif candidate_pool < normalized_min_pool:
            reason = "pool_below_min"
            fallback = normalized_mode == "enforce"
        elif candidate_pool > normalized_max_pool:
            reason = "pool_above_max"
            fallback = normalized_mode == "enforce"
        elif signed_chunk_count <= 0:
            reason = "no_signatures"
            fallback = normalized_mode == "enforce"
        else:
            try:
                report = _build_report_only_subset(
                    chunks=chunks,
                    sidecar=(
                        robust_signature_sidecar
                        if isinstance(robust_signature_sidecar, dict)
                        else {}
                    ),
                    lambda_penalty=float(lambda_penalty),
                    min_marginal_utility=float(min_marginal_utility),
                    compatibility_min_overlap=float(compatibility_min_overlap),
                )
            except Exception:
                reason = (
                    "enforce_error"
                    if normalized_mode == "enforce"
                    else "report_only_error"
                )
                fallback = normalized_mode == "enforce"
            else:
                filtered_keys = report["filtered_keys"]
                retained_keys = report["retained_keys"]
                filtered_refs = report["filtered_refs"]
                retained_refs = report["retained_refs"]
                pairwise_conflict_count = int(report["pairwise_conflict_count"])
                max_conflict_penalty = float(report["max_conflict_penalty"])
                if normalized_mode == "enforce":
                    enforced_chunks = list(report["retained_chunks"])
                    if enforced_chunks:
                        output_chunks = enforced_chunks
                        reason = "enforce_applied"
                    else:
                        reason = "enforce_empty_retained"
                        fallback = True
                        filtered_keys = []
                        retained_keys = [
                            key
                            for item in chunks
                            if (key := chunk_identity_key(chunk=item))
                        ]
                        filtered_refs = []
                        retained_refs = _preview_refs(chunks)
                else:
                    reason = "report_only"

    payload = {
        "enabled": bool(enabled_effective),
        "mode": normalized_mode,
        "reason": reason,
        "candidate_pool": int(candidate_pool),
        "signed_chunk_count": int(signed_chunk_count),
        "filtered_count": int(len(filtered_keys)),
        "retained_count": int(candidate_pool - len(filtered_keys)),
        "pairwise_conflict_count": int(pairwise_conflict_count),
        "max_conflict_penalty": float(round(max_conflict_penalty, 6)),
        "retained_keys": retained_keys,
        "filtered_keys": filtered_keys,
        "retained_refs": retained_refs,
        "filtered_refs": filtered_refs,
        "report_only": normalized_mode == "report_only",
        "fallback": bool(fallback),
    }
    return ChunkGuardResult(
        candidate_chunks=output_chunks,
        chunk_guard_payload=payload,
    )


def _build_report_only_subset(
    *,
    chunks: list[dict[str, Any]],
    sidecar: dict[str, dict[str, Any]],
    lambda_penalty: float,
    min_marginal_utility: float,
    compatibility_min_overlap: float,
) -> dict[str, Any]:
    normalized_lambda = max(0.0, float(lambda_penalty))
    normalized_min_utility = float(min_marginal_utility)
    normalized_overlap = max(0.0, min(1.0, float(compatibility_min_overlap)))

    keyed_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        key = chunk_identity_key(chunk=chunk)
        if not key:
            continue
        signature = sidecar.get(key, {})
        if not isinstance(signature, dict) or not bool(signature.get("available", False)):
            continue
        keyed_rows.append((key, chunk, signature))

    conflict_penalties: dict[tuple[str, str], float] = {}
    max_penalty = 0.0
    for index, (left_key, _, left_signature) in enumerate(keyed_rows):
        for right_key, _, right_signature in keyed_rows[index + 1 :]:
            penalty = _pairwise_conflict_penalty(
                left_signature=left_signature,
                right_signature=right_signature,
                compatibility_min_overlap=normalized_overlap,
            )
            if penalty <= 0.0:
                continue
            pair_key = tuple(sorted((left_key, right_key)))
            conflict_penalties[pair_key] = penalty
            max_penalty = max(max_penalty, penalty)

    ordered_chunks = sorted(
        chunks,
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("path") or ""),
            int(item.get("lineno") or 0),
            str(item.get("qualified_name") or ""),
        ),
    )

    retained: list[dict[str, Any]] = []
    retained_key_set: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for chunk in ordered_chunks:
        if not isinstance(chunk, dict):
            continue
        key = chunk_identity_key(chunk=chunk)
        signature = sidecar.get(key, {}) if key else {}
        if not key or not isinstance(signature, dict) or not bool(signature.get("available", False)):
            retained.append(chunk)
            if key:
                retained_key_set.add(key)
            continue

        conflict_total = 0.0
        for retained_chunk in retained:
            retained_key = chunk_identity_key(chunk=retained_chunk)
            if not retained_key:
                continue
            pair_key = tuple(sorted((key, retained_key)))
            conflict_total += float(conflict_penalties.get(pair_key, 0.0) or 0.0)

        marginal_utility = float(chunk.get("score", 0.0) or 0.0) - (
            normalized_lambda * conflict_total
        )
        if marginal_utility >= normalized_min_utility:
            retained.append(chunk)
            retained_key_set.add(key)
        else:
            filtered.append(chunk)

    retained_keys = [
        chunk_identity_key(chunk=item)
        for item in retained
        if chunk_identity_key(chunk=item)
    ]
    filtered_keys = [
        chunk_identity_key(chunk=item)
        for item in filtered
        if chunk_identity_key(chunk=item)
    ]
    return {
        "retained_chunks": retained,
        "retained_keys": retained_keys,
        "filtered_keys": filtered_keys,
        "retained_refs": _preview_refs(retained),
        "filtered_refs": _preview_refs(filtered),
        "pairwise_conflict_count": len(conflict_penalties),
        "max_conflict_penalty": float(max_penalty),
    }


def _pairwise_conflict_penalty(
    *,
    left_signature: dict[str, Any],
    right_signature: dict[str, Any],
    compatibility_min_overlap: float,
) -> float:
    left_shape_hash = str(left_signature.get("shape_hash") or "").strip()
    right_shape_hash = str(right_signature.get("shape_hash") or "").strip()
    if not left_shape_hash or not right_shape_hash or left_shape_hash == right_shape_hash:
        return 0.0

    left_vocab = {
        str(item).strip().lower()
        for item in left_signature.get("entity_vocab", ())
        if str(item).strip()
    }
    right_vocab = {
        str(item).strip().lower()
        for item in right_signature.get("entity_vocab", ())
        if str(item).strip()
    }
    if not left_vocab or not right_vocab:
        return 0.0

    overlap_ratio = float(len(left_vocab & right_vocab)) / float(
        len(left_vocab | right_vocab)
    )
    if overlap_ratio < compatibility_min_overlap:
        return 0.0

    left_domain = str(left_signature.get("compatibility_domain") or "").strip()
    right_domain = str(right_signature.get("compatibility_domain") or "").strip()
    same_domain = bool(left_domain) and left_domain == right_domain
    domain_weight = 1.0 if same_domain else 0.75
    return round(overlap_ratio * domain_weight, 6)


def _preview_refs(chunks: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        label = str(chunk.get("qualified_name") or chunk.get("path") or "").strip()
        if not label or label in refs:
            continue
        refs.append(label)
        if len(refs) >= 8:
            break
    return refs


__all__ = [
    "CHUNK_GUARD_MODE_CHOICES",
    "ChunkGuardResult",
    "apply_chunk_guard",
]
