"""Cache Payload Utilities for Reducing Unnecessary deepcopy Operations

This module provides utilities for managing cache payloads with a focus on
reducing unnecessary deepcopy operations while maintaining data safety.

PRD-91 QO-1102: Repomap Cache Lightweight Payload Path

Key optimizations:
1. ImmutablePayload: wrapper that prevents accidental mutation without deepcopy
2. Fingerprint utilities: unified single-pass construction
3. Payload categorization: read-only vs write vs artifact memory paths
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass


# =============================================================================
# Payload Type Tags
# =============================================================================


class PayloadType:
    """Payload type tags for cache optimization."""

    # Read-only payload: cached data returned to callers
    # Safe to return directly without deepcopy if immutable
    READ_ONLY = "read_only"

    # Write payload: data being written to cache
    # Needs defensive copy when writing to prevent caller mutation
    WRITE = "write"

    # Artifact memory payload: stored in memory cache layer
    # May need copy depending on mutation risks
    ARTIFACT_MEMORY = "artifact_memory"

    # Legacy payload: old format from cache files
    # Always needs copy for safety
    LEGACY = "legacy"


# =============================================================================
# Immutable Payload Wrapper
# =============================================================================


@dataclass(frozen=True, slots=True)
class ImmutablePayload:
    """A frozen dataclass wrapper that prevents accidental mutation.

    Unlike deepcopy which creates a full copy, this wrapper signals intent
    and allows the caller to understand the data contract.

    Usage:
        # Instead of: return copy.deepcopy(payload)
        # Use: return ImmutablePayload(payload, PayloadType.READ_ONLY)

        # When mutation is needed:
        # Use: dict(payload) or shallow copy for simple dicts
    """

    data: dict[str, Any]
    payload_type: str = PayloadType.READ_ONLY
    source: str = "unknown"

    def unwrap(self) -> dict[str, Any]:
        """Get the underlying dict. Caller should not mutate this."""
        return self.data

    def unwrap_copy(self) -> dict[str, Any]:
        """Get a shallow copy of the underlying dict."""
        return dict(self.data)


# =============================================================================
# Shallow Copy Utilities
# =============================================================================


def shallow_copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a shallow copy of a payload.

    For most use cases, a shallow copy is sufficient to prevent
    accidental mutation of the original dict while being much faster
    than deepcopy.

    Only use this when:
    - The top-level dict keys are immutable (strings, numbers)
    - Nested dicts/lists don't need isolation
    """
    return dict(payload)


def selective_copy_payload(
    payload: dict[str, Any],
    *,
    copy_nested: bool = True,
) -> dict[str, Any]:
    """Create a partially deep copy of a payload.

    This is a middle ground between shallow copy and full deepcopy.
    It copies nested dicts and lists that might be mutated while
    keeping immutable values as references.

    Args:
        payload: The source payload
        copy_nested: If True, recursively copy nested dicts/lists

    Returns:
        A new dict with selectively copied nested structures
    """
    if copy_nested:
        return cast(dict[str, Any], _deep_copy_impl(payload))
    return dict(payload)


def _deep_copy_impl(obj: Any) -> Any:
    """Lightweight deep copy implementation for common payload structures."""
    if isinstance(obj, dict):
        return {k: _deep_copy_impl(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy_impl(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_deep_copy_impl(item) for item in obj)
    # Immutable types: int, float, str, bool, None - return as-is
    return obj


# =============================================================================
# Fingerprint Utilities
# =============================================================================


def build_fingerprint(*, key: str, **kwargs: Any) -> str:
    """Build a fingerprint from key and additional parameters.

    This unifies fingerprint construction into a single pass,
    avoiding repeated hashing operations.
    """
    return hashlib.sha256(
        json.dumps(
            {"key": str(key), **kwargs},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", "ignore")
    ).hexdigest()


def build_meta_fingerprint(meta: dict[str, Any] | None) -> str:
    """Build a fingerprint from cache metadata.

    Normalizes None to empty dict and produces a consistent hash.
    """
    normalized = dict(meta) if meta else {}
    return hashlib.sha256(
        json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", "ignore")
    ).hexdigest()


# =============================================================================
# Token Weight Estimation (Lightweight)
# =============================================================================


def estimate_token_weight(payload: dict[str, Any]) -> int:
    """Estimate token weight of a payload.

    Uses a lightweight heuristic based on JSON string length.
    For more accurate counting, use the full tokenizer.
    """
    try:
        json_str = json.dumps(payload, ensure_ascii=False)
        # Rough estimate: ~4 chars per token on average
        return max(1, len(json_str) // 4)
    except (TypeError, ValueError):
        return 0


# =============================================================================
# Cache Entry Builder
# =============================================================================


@dataclass
class CacheEntryBuilder:
    """Builder for cache entries with optimized copying.

    This builder helps create cache entries while minimizing
    unnecessary deepcopy operations.
    """

    key: str
    payload: dict[str, Any]
    payload_type: str = PayloadType.WRITE
    meta: dict[str, Any] | None = None
    stage_name: str = "unknown"

    def build(
        self,
        *,
        include_payload_copy: bool = True,
    ) -> dict[str, Any]:
        """Build a cache entry dict.

        Args:
            include_payload_copy: If True and payload_type is WRITE,
                                 include a shallow copy of the payload

        Returns:
            A dict suitable for cache storage
        """
        entry: dict[str, Any] = {
            "key": str(self.key),
            "stage_name": self.stage_name,
        }

        if self.meta:
            entry["meta"] = self.meta

        if include_payload_copy and self.payload_type == PayloadType.WRITE:
            # Use shallow copy for WRITE payloads to prevent caller mutation
            entry["payload"] = shallow_copy_payload(self.payload)
        elif self.payload_type in (PayloadType.ARTIFACT_MEMORY, PayloadType.LEGACY):
            # These need protection against mutation
            entry["payload"] = selective_copy_payload(self.payload)
        else:
            # READ_ONLY payloads are typically already protected upstream
            entry["payload"] = self.payload

        return entry


# =============================================================================
# Export Helpers
# =============================================================================


def wrap_read_only_payload(
    payload: dict[str, Any],
    *,
    source: str = "unknown",
) -> ImmutablePayload:
    """Wrap a payload as read-only.

    Use this when returning cached data to callers to make the
    contract explicit without requiring deepcopy.
    """
    return ImmutablePayload(
        data=payload,
        payload_type=PayloadType.READ_ONLY,
        source=source,
    )


def wrap_write_payload(
    payload: dict[str, Any],
    *,
    source: str = "unknown",
) -> ImmutablePayload:
    """Wrap a payload as write-in-progress.

    The payload is still mutable internally but the type tag
    signals intent.
    """
    return ImmutablePayload(
        data=payload,
        payload_type=PayloadType.WRITE,
        source=source,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CacheEntryBuilder",
    "ImmutablePayload",
    "PayloadType",
    "build_fingerprint",
    "build_meta_fingerprint",
    "estimate_token_weight",
    "selective_copy_payload",
    "shallow_copy_payload",
    "wrap_read_only_payload",
    "wrap_write_payload",
]
