"""Typed chunk skeleton payload helpers for Year 2 contract freeze."""

from __future__ import annotations

from typing import Any

from ace_lite.chunking.disclosure_policy import (
    CHUNK_DISCLOSURE_CHOICES,
    SKELETON_DISCLOSURE_CHOICES,
    normalize_chunk_disclosure,
)
from ace_lite.chunking.robust_signature import summarize_robust_signature

CHUNK_SKELETON_SCHEMA_VERSION = "y2-freeze-v1"


def build_chunk_skeleton(
    *,
    chunk: dict[str, Any],
    disclosure_mode: str,
    robust_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = normalize_chunk_disclosure(disclosure_mode)
    if mode not in SKELETON_DISCLOSURE_CHOICES:
        raise ValueError(f"Unsupported chunk skeleton mode: {mode}")

    lineno = int(chunk.get("lineno") or 0)
    end_lineno = max(lineno, int(chunk.get("end_lineno") or lineno))
    robust_summary = (
        summarize_robust_signature(robust_signature)
        if isinstance(robust_signature, dict)
        else {"available": False}
    )

    payload: dict[str, Any] = {
        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "mode": mode,
        "language": str(chunk.get("language") or "").strip().lower(),
        "module": str(chunk.get("module") or "").strip(),
        "symbol": {
            "name": str(chunk.get("name") or "").strip(),
            "qualified_name": str(chunk.get("qualified_name") or "").strip(),
            "kind": str(chunk.get("kind") or "").strip(),
        },
        "span": {
            "start_line": lineno,
            "end_line": end_lineno,
            "line_count": max(1, end_lineno - lineno + 1),
        },
        "anchors": {
            "path": str(chunk.get("path") or "").strip(),
            "signature": str(chunk.get("signature") or "").strip(),
            "robust_signature_available": bool(
                robust_summary.get("available", False)
            ),
        },
    }

    if mode == "skeleton_full":
        payload["metadata"] = {
            "sha256": str(chunk.get("sha256") or "").strip(),
            "size_bytes": max(0, int(chunk.get("size_bytes") or 0)),
            "generated": bool(chunk.get("generated", False)),
            "imports_count": max(0, int(chunk.get("imports_count") or 0)),
            "references_count": max(0, int(chunk.get("references_count") or 0)),
        }
        if robust_summary.get("available", False):
            payload["robust_signature_summary"] = robust_summary

    return payload


def summarize_chunk_contract(
    *,
    candidate_chunks: list[dict[str, Any]],
    requested_disclosure: str,
) -> dict[str, Any]:
    normalized_requested = normalize_chunk_disclosure(requested_disclosure)
    observed_disclosures: list[str] = []
    skeleton_modes: list[str] = []
    skeleton_schema_versions: list[str] = []
    fallback_count = 0
    skeleton_chunk_count = 0

    for item in candidate_chunks:
        if not isinstance(item, dict):
            continue
        disclosure = normalize_chunk_disclosure(
            str(item.get("disclosure") or normalized_requested)
        )
        if disclosure in CHUNK_DISCLOSURE_CHOICES and disclosure not in observed_disclosures:
            observed_disclosures.append(disclosure)
        if str(item.get("disclosure_fallback_reason") or "").strip():
            fallback_count += 1

        skeleton = item.get("skeleton")
        if not isinstance(skeleton, dict):
            continue
        skeleton_chunk_count += 1
        mode = normalize_chunk_disclosure(str(skeleton.get("mode") or disclosure))
        if mode in SKELETON_DISCLOSURE_CHOICES and mode not in skeleton_modes:
            skeleton_modes.append(mode)
        version = str(skeleton.get("schema_version") or "").strip()
        if version and version not in skeleton_schema_versions:
            skeleton_schema_versions.append(version)

    if not observed_disclosures:
        observed_disclosures.append(normalized_requested)

    return {
        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "requested_disclosure": normalized_requested,
        "observed_disclosures": observed_disclosures,
        "fallback_count": int(fallback_count),
        "chunk_count": len([item for item in candidate_chunks if isinstance(item, dict)]),
        "skeleton_chunk_count": int(skeleton_chunk_count),
        "skeleton_modes": skeleton_modes,
        "skeleton_schema_versions": skeleton_schema_versions,
    }


__all__ = [
    "CHUNK_SKELETON_SCHEMA_VERSION",
    "build_chunk_skeleton",
    "summarize_chunk_contract",
]
