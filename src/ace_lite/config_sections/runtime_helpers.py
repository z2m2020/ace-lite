from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_MEMORY_PROFILE_PATH = "~/.ace-lite/profile.json"
DEFAULT_MEMORY_NOTES_PATH = "context-map/memory_notes.jsonl"
DEFAULT_LONG_TERM_MEMORY_PATH = "context-map/long_term_memory.db"
DEFAULT_SCIP_INDEX_PATH = "context-map/scip/index.json"
DEFAULT_EMBEDDINGS_INDEX_PATH = "context-map/embeddings/index.json"
DEFAULT_TRACE_EXPORT_PATH = "context-map/traces/stage_spans.jsonl"
DEFAULT_PLAN_REPLAY_CACHE_PATH = "context-map/plan-replay/cache.json"
DEFAULT_TOKENIZER_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "hash-v1"


def normalize_default_path(value: Any, *, default: str) -> str | Path:
    normalized = str(value or "").strip()
    return normalized or default


def normalize_string_default(value: Any, *, default: str) -> str:
    return str(value or default).strip() or default


def normalize_positive_int(
    value: Any,
    *,
    default: int,
    minimum: int = 1,
) -> int:
    try:
        normalized = int(value)
    except Exception:
        normalized = int(default)
    return max(int(minimum), normalized)


def normalize_non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        normalized = int(value)
    except Exception:
        normalized = int(default)
    return max(0, normalized)


def normalize_non_negative_float(value: Any, *, default: float = 0.0) -> float:
    try:
        normalized = float(value)
    except Exception:
        normalized = float(default)
    return max(0.0, normalized)


def normalize_clamped_float(
    value: Any,
    *,
    default: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    try:
        normalized = float(value)
    except Exception:
        normalized = float(default)
    return max(float(minimum), min(float(maximum), normalized))


__all__ = [
    "DEFAULT_EMBEDDINGS_INDEX_PATH",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_LONG_TERM_MEMORY_PATH",
    "DEFAULT_MEMORY_NOTES_PATH",
    "DEFAULT_MEMORY_PROFILE_PATH",
    "DEFAULT_PLAN_REPLAY_CACHE_PATH",
    "DEFAULT_SCIP_INDEX_PATH",
    "DEFAULT_TOKENIZER_MODEL",
    "DEFAULT_TRACE_EXPORT_PATH",
    "normalize_clamped_float",
    "normalize_default_path",
    "normalize_non_negative_float",
    "normalize_non_negative_int",
    "normalize_positive_int",
    "normalize_string_default",
]
