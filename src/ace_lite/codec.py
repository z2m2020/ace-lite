"""Pluggable JSON Codec for ACE-Lite

This module provides a pluggable JSON codec interface that supports
multiple JSON implementations (standard library, orjson, etc.).

PRD-91 QO-3103/QO-3104: Pluggable orjson Codec

Key features:
1. Pluggable codec interface
2. Automatic fallback to standard library
3. Benchmark integration
4. Type hints for better IDE support
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


# =============================================================================
# Codec Interface
# =============================================================================


class JSONCodec(ABC):
    """Abstract base class for JSON codecs."""

    @abstractmethod
    def dumps(self, obj: Any) -> str | bytes:
        """Serialize an object to JSON string.

        Args:
            obj: Object to serialize

        Returns:
            JSON string or bytes
        """
        pass

    @abstractmethod
    def loads(self, s: str | bytes) -> Any:
        """Deserialize a JSON string to an object.

        Args:
            s: JSON string or bytes

        Returns:
            Deserialized object
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the codec name."""
        pass

    @property
    def is_available(self) -> bool:
        """Check if the codec is available."""
        return True


# =============================================================================
# Standard JSON Codec
# =============================================================================


class StandardJSONCodec(JSONCodec):
    """Standard library JSON codec."""

    @property
    def name(self) -> str:
        """Get the codec name."""
        return "json"

    def dumps(self, obj: Any) -> str:
        """Serialize using standard json.dumps."""
        return json.dumps(
            obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def loads(self, s: str | bytes) -> Any:
        """Deserialize using standard json.loads."""
        return json.loads(s)


# =============================================================================
# orjson Codec
# =============================================================================


class OrjsonCodec(JSONCodec):
    """orjson-based codec for high-performance JSON operations.

    orjson is significantly faster than the standard library for
    both serialization and deserialization.
    """

    def __init__(self):
        """Initialize the orjson codec."""
        self._orjson = self._import_orjson()

    def _import_orjson(self):
        """Import orjson with fallback."""
        try:
            import orjson

            return orjson
        except ImportError:
            return None

    @property
    def name(self) -> str:
        """Get the codec name."""
        return "orjson"

    @property
    def is_available(self) -> bool:
        """Check if orjson is available."""
        return self._orjson is not None

    def dumps(self, obj: Any) -> bytes:
        """Serialize using orjson.dumps.

        orjson returns bytes, not str. This is more efficient
        as it avoids encoding/decoding overhead.
        """
        if self._orjson is None:
            raise RuntimeError("orjson is not available")
        return bytes(self._orjson.dumps(obj))

    def loads(self, s: str | bytes) -> Any:
        """Deserialize using orjson.loads."""
        if self._orjson is None:
            raise RuntimeError("orjson is not available")
        return self._orjson.loads(s)


# =============================================================================
# Codec Registry
# =============================================================================


class CodecRegistry:
    """Registry for JSON codecs with auto-detection."""

    def __init__(self):
        """Initialize the codec registry."""
        self._codecs: dict[str, JSONCodec] = {}
        self._default_codec: JSONCodec | None = None
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """Set up default codecs."""
        # Register standard JSON (always available)
        self.register(StandardJSONCodec())

        # Register orjson (if available)
        orjson_codec = OrjsonCodec()
        if orjson_codec.is_available:
            self.register(orjson_codec)

        # Set default
        self.set_default("json")

    def register(self, codec: JSONCodec) -> None:
        """Register a codec.

        Args:
            codec: The codec to register
        """
        self._codecs[codec.name] = codec

    def get(self, name: str) -> JSONCodec | None:
        """Get a codec by name.

        Args:
            name: Codec name

        Returns:
            The codec or None if not found
        """
        return self._codecs.get(name)

    def set_default(self, name: str) -> bool:
        """Set the default codec.

        Args:
            name: Codec name

        Returns:
            True if successful
        """
        codec = self._codecs.get(name)
        if codec:
            self._default_codec = codec
            return True
        return False

    @property
    def default(self) -> JSONCodec:
        """Get the default codec."""
        if self._default_codec is None:
            self._default_codec = self._codecs.get("json", StandardJSONCodec())
        return self._default_codec

    @property
    def available_codecs(self) -> list[str]:
        """Get list of available codec names."""
        return [name for name, codec in self._codecs.items() if codec.is_available]

    def dumps(self, obj: Any, codec_name: str | None = None) -> str | bytes:
        """Serialize using a specific codec or the default.

        Args:
            obj: Object to serialize
            codec_name: Optional codec name, uses default if not specified

        Returns:
            JSON string or bytes
        """
        if codec_name:
            codec = self._codecs.get(codec_name)
            if codec:
                return codec.dumps(obj)
            raise ValueError(f"Unknown codec: {codec_name}")
        return self.default.dumps(obj)

    def loads(self, s: str | bytes, codec_name: str | None = None) -> Any:
        """Deserialize using a specific codec or the default.

        Args:
            s: JSON string or bytes
            codec_name: Optional codec name, uses default if not specified

        Returns:
            Deserialized object
        """
        if codec_name:
            codec = self._codecs.get(codec_name)
            if codec:
                return codec.loads(s)
            raise ValueError(f"Unknown codec: {codec_name}")
        return self.default.loads(s)


# =============================================================================
# Global Registry
# =============================================================================

_global_registry: CodecRegistry | None = None


def get_codec_registry() -> CodecRegistry:
    """Get the global codec registry.

    Returns:
        The global CodecRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = CodecRegistry()
    return _global_registry


# =============================================================================
# Convenience Functions
# =============================================================================


def dumps(obj: Any, codec: str | None = None) -> str | bytes:
    """Serialize an object to JSON.

    Args:
        obj: Object to serialize
        codec: Optional codec name

    Returns:
        JSON string or bytes
    """
    return get_codec_registry().dumps(obj, codec)


def loads(s: str | bytes, codec: str | None = None) -> Any:
    """Deserialize a JSON string.

    Args:
        s: JSON string or bytes
        codec: Optional codec name

    Returns:
        Deserialized object
    """
    return get_codec_registry().loads(s, codec)


def dumps_to_str(obj: Any, codec: str | None = None) -> str:
    """Serialize an object to JSON string (always returns str).

    This is useful when you need a string regardless of the codec.

    Args:
        obj: Object to serialize
        codec: Optional codec name

    Returns:
        JSON string
    """
    result = dumps(obj, codec)
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return result


# =============================================================================
# Benchmark Integration
# =============================================================================


def benchmark_codecs(
    data: dict[str, Any],
    iterations: int = 1000,
) -> dict[str, dict[str, float]]:
    """Benchmark different JSON codecs.

    Args:
        data: Data to benchmark
        iterations: Number of iterations

    Returns:
        Dict of benchmark results keyed by codec name
    """
    import time

    from ace_lite.performance_benchmark import BenchmarkRunner, BenchmarkConfig

    results: dict[str, dict[str, float]] = {}
    runner = BenchmarkRunner(BenchmarkConfig(iterations=iterations))

    for codec_name in get_codec_registry().available_codecs:
        codec = get_codec_registry().get(codec_name)
        if not codec:
            continue

        def serialize():
            return codec.dumps(data)

        def deserialize():
            serialized = codec.dumps(data)
            return codec.loads(serialized)

        serialize_result = runner.run(f"{codec_name}_dumps", serialize)
        deserialize_result = runner.run(f"{codec_name}_loads", deserialize)

        results[codec_name] = {
            "dumps_avg_ms": serialize_result.avg_time_ms,
            "loads_avg_ms": deserialize_result.avg_time_ms,
            "total_avg_ms": serialize_result.avg_time_ms + deserialize_result.avg_time_ms,
        }

    return results


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "JSONCodec",
    "StandardJSONCodec",
    "OrjsonCodec",
    "CodecRegistry",
    "get_codec_registry",
    "dumps",
    "loads",
    "dumps_to_str",
    "benchmark_codecs",
]
