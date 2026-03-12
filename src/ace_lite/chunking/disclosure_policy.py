"""Chunk disclosure policy helpers for candidate chunk payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.parsers.languages import detect_language

CHUNK_DISCLOSURE_CHOICES: tuple[str, ...] = (
    "refs",
    "signature",
    "snippet",
    "skeleton_light",
    "skeleton_full",
)
SKELETON_DISCLOSURE_CHOICES: tuple[str, ...] = (
    "skeleton_light",
    "skeleton_full",
)
SKELETON_SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"python", "go", "javascript", "typescript", "tsx"}
)


def normalize_chunk_disclosure(value: str) -> str:
    normalized = str(value or "refs").strip().lower() or "refs"
    if normalized not in CHUNK_DISCLOSURE_CHOICES:
        return "refs"
    return normalized


def is_skeleton_disclosure(value: str) -> bool:
    return normalize_chunk_disclosure(value) in SKELETON_DISCLOSURE_CHOICES


def _detect_chunk_language(*, path: str, file_entry: dict[str, Any] | None) -> str:
    if isinstance(file_entry, dict):
        language = str(file_entry.get("language") or "").strip().lower()
        if language:
            return language
    detected = detect_language(Path(path))
    return str(detected or "").strip().lower()


def resolve_chunk_disclosure(
    *,
    requested_mode: str,
    path: str,
    file_entry: dict[str, Any] | None,
) -> tuple[str, str | None]:
    normalized = normalize_chunk_disclosure(requested_mode)
    if normalized not in SKELETON_DISCLOSURE_CHOICES:
        return normalized, None

    language = _detect_chunk_language(path=path, file_entry=file_entry)
    if language in SKELETON_SUPPORTED_LANGUAGES:
        return normalized, None

    fallback = "signature" if normalized == "skeleton_full" else "refs"
    return fallback, "unsupported_language"


__all__ = [
    "CHUNK_DISCLOSURE_CHOICES",
    "SKELETON_DISCLOSURE_CHOICES",
    "SKELETON_SUPPORTED_LANGUAGES",
    "is_skeleton_disclosure",
    "normalize_chunk_disclosure",
    "resolve_chunk_disclosure",
]
