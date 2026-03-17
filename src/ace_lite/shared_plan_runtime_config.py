from __future__ import annotations

from typing import Any

from ace_lite.config_choices import EMBEDDING_PROVIDER_CHOICES
from ace_lite.config_model_shared import (
    normalize_embedding_provider,
    normalize_memory_auto_tag_mode,
    normalize_memory_gate_mode,
    normalize_memory_notes_mode,
    normalize_ranking_profile,
    validate_embedding_provider,
    validate_memory_auto_tag_mode,
    validate_memory_gate_mode,
    validate_memory_notes_mode,
    validate_ranking_profile,
    validate_scip_provider,
)
from ace_lite.config_sections import (
    DEFAULT_EMBEDDINGS_INDEX_PATH,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_PLAN_REPLAY_CACHE_PATH,
    DEFAULT_SCIP_INDEX_PATH,
    DEFAULT_TOKENIZER_MODEL,
    DEFAULT_TRACE_EXPORT_PATH,
    normalize_clamped_float,
    normalize_default_path,
    normalize_string_default,
)
from ace_lite.token_estimator import normalize_tokenizer_model
from ace_lite.utils import normalize_optional_str


def normalize_container_tag(value: Any) -> str | None:
    return normalize_optional_str(value)


def resolve_memory_auto_tag_mode(
    value: Any,
    *,
    field_name: str | None = None,
) -> str | None:
    if field_name is None:
        return normalize_memory_auto_tag_mode(value)
    return validate_memory_auto_tag_mode(
        normalize_optional_str(value),
        field_name=field_name,
    )


def resolve_memory_gate_mode(
    value: Any,
    *,
    default: str = "auto",
    field_name: str | None = None,
) -> str | None:
    if field_name is None:
        return normalize_memory_gate_mode(value, default=default)
    return validate_memory_gate_mode(
        normalize_optional_str(value),
        field_name=field_name,
    )


def resolve_memory_notes_mode(
    value: Any,
    *,
    default: str = "supplement",
    field_name: str | None = None,
) -> str | None:
    if field_name is None:
        return normalize_memory_notes_mode(value, default=default)
    return validate_memory_notes_mode(
        normalize_optional_str(value),
        field_name=field_name,
    )


def resolve_ranking_profile(
    value: Any,
    *,
    default: str = "graph",
    field_name: str | None = None,
) -> str | None:
    if field_name is None:
        return normalize_ranking_profile(value, default=default)
    return validate_ranking_profile(
        normalize_optional_str(value),
        field_name=field_name,
    )


def resolve_scip_provider(
    value: Any,
    *,
    default: str | None = None,
    field_name: str,
) -> str | None:
    normalized = normalize_optional_str(value)
    if normalized is None:
        if default is None:
            return None
        normalized = default
    validated = validate_scip_provider(normalized, field_name=field_name)
    if validated is None and default is not None:
        return default
    return validated


def resolve_embedding_provider(
    value: Any,
    *,
    default: str = "hash",
    field_name: str | None = None,
) -> str | None:
    normalized = str(value or "").strip().lower()
    if field_name is None:
        if not normalized:
            return default
        if normalized in EMBEDDING_PROVIDER_CHOICES:
            return normalize_embedding_provider(normalized, default=default)
        return normalized
    return validate_embedding_provider(
        normalize_optional_str(value),
        field_name=field_name,
    )


def resolve_tokenizer_model(
    value: Any,
    *,
    default: str = DEFAULT_TOKENIZER_MODEL,
) -> str:
    return normalize_tokenizer_model(
        normalize_string_default(value, default=default)
    )


def resolve_embedding_model(
    value: Any,
    *,
    default: str = DEFAULT_EMBEDDING_MODEL,
) -> str:
    return normalize_string_default(value, default=default)


def resolve_embedding_index_path(
    value: Any,
    *,
    default: str = DEFAULT_EMBEDDINGS_INDEX_PATH,
) -> str:
    return str(normalize_default_path(value, default=default))


def resolve_scip_index_path(
    value: Any,
    *,
    default: str = DEFAULT_SCIP_INDEX_PATH,
) -> str:
    return str(normalize_default_path(value, default=default))


def resolve_trace_export_path(
    value: Any,
    *,
    default: str = DEFAULT_TRACE_EXPORT_PATH,
) -> str:
    return str(normalize_default_path(value, default=default))


def resolve_trace_otlp_timeout_seconds(
    value: Any,
    *,
    default: float = 1.5,
    minimum: float = 0.1,
) -> float:
    return normalize_clamped_float(
        value,
        default=default,
        minimum=minimum,
        maximum=float("inf"),
    )


def resolve_trace_otlp_endpoint(value: Any) -> str:
    return str(value or "").strip()


def resolve_optional_path(value: Any) -> str | None:
    normalized = normalize_optional_str(value)
    return normalized or None


def resolve_plan_replay_cache_path(
    value: Any,
    *,
    default: str = DEFAULT_PLAN_REPLAY_CACHE_PATH,
) -> str:
    return str(normalize_default_path(value, default=default))


__all__ = [
    "normalize_container_tag",
    "resolve_embedding_index_path",
    "resolve_embedding_model",
    "resolve_embedding_provider",
    "resolve_memory_auto_tag_mode",
    "resolve_memory_gate_mode",
    "resolve_memory_notes_mode",
    "resolve_optional_path",
    "resolve_plan_replay_cache_path",
    "resolve_ranking_profile",
    "resolve_scip_index_path",
    "resolve_scip_provider",
    "resolve_tokenizer_model",
    "resolve_trace_export_path",
    "resolve_trace_otlp_endpoint",
    "resolve_trace_otlp_timeout_seconds",
]
