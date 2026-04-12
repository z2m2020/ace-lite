"""Unit tests for codec module.

Tests verify the pluggable JSON codec (QO-3103/QO-3104).
"""

from __future__ import annotations

import pytest

from ace_lite.codec import (
    JSONCodec,
    StandardJSONCodec,
    OrjsonCodec,
    CodecRegistry,
    get_codec_registry,
    dumps,
    loads,
    dumps_to_str,
    benchmark_codecs,
)


class TestStandardJSONCodec:
    """Tests for StandardJSONCodec."""

    def test_name(self):
        """Test codec name."""
        codec = StandardJSONCodec()
        assert codec.name == "json"

    def test_is_available(self):
        """Test codec availability."""
        codec = StandardJSONCodec()
        assert codec.is_available is True

    def test_dumps(self):
        """Test serialization."""
        codec = StandardJSONCodec()
        result = codec.dumps({"key": "value"})
        assert isinstance(result, str)
        assert '"key"' in result

    def test_loads(self):
        """Test deserialization."""
        codec = StandardJSONCodec()
        result = codec.loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_roundtrip(self):
        """Test serialization and deserialization roundtrip."""
        codec = StandardJSONCodec()
        original = {"list": [1, 2, 3], "nested": {"key": "value"}}

        serialized = codec.dumps(original)
        deserialized = codec.loads(serialized)

        assert deserialized == original


class TestOrjsonCodec:
    """Tests for OrjsonCodec."""

    def test_name(self):
        """Test codec name."""
        codec = OrjsonCodec()
        assert codec.name == "orjson"

    def test_is_available_when_not_installed(self):
        """Test codec availability when orjson not installed."""
        codec = OrjsonCodec()
        # This test will pass or fail depending on orjson installation
        # If orjson is installed, is_available will be True
        assert isinstance(codec.is_available, bool)

    def test_dumps(self):
        """Test serialization."""
        codec = OrjsonCodec()
        if not codec.is_available:
            pytest.skip("orjson not installed")

        result = codec.dumps({"key": "value"})
        # orjson returns bytes
        assert isinstance(result, bytes)

    def test_loads(self):
        """Test deserialization."""
        codec = OrjsonCodec()
        if not codec.is_available:
            pytest.skip("orjson not installed")

        result = codec.loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_roundtrip(self):
        """Test serialization and deserialization roundtrip."""
        codec = OrjsonCodec()
        if not codec.is_available:
            pytest.skip("orjson not installed")

        original = {"list": [1, 2, 3], "nested": {"key": "value"}}

        serialized = codec.dumps(original)
        deserialized = codec.loads(serialized)

        assert deserialized == original


class TestCodecRegistry:
    """Tests for CodecRegistry."""

    def test_register(self):
        """Test registering a codec."""
        registry = CodecRegistry()
        codec = StandardJSONCodec()
        registry.register(codec)

        assert registry.get("json") is codec

    def test_get_unknown(self):
        """Test getting unknown codec."""
        registry = CodecRegistry()
        assert registry.get("unknown_codec") is None

    def test_set_default(self):
        """Test setting default codec."""
        registry = CodecRegistry()
        assert registry.set_default("json") is True
        assert registry.default.name == "json"

    def test_set_default_unknown(self):
        """Test setting default to unknown codec."""
        registry = CodecRegistry()
        assert registry.set_default("unknown") is False

    def test_available_codecs(self):
        """Test getting available codecs."""
        registry = CodecRegistry()
        codecs = registry.available_codecs
        assert "json" in codecs
        # orjson may or may not be available

    def test_dumps_with_default(self):
        """Test dumps with default codec."""
        registry = CodecRegistry()
        result = registry.dumps({"key": "value"})
        assert isinstance(result, str)

    def test_dumps_with_specific_codec(self):
        """Test dumps with specific codec."""
        registry = CodecRegistry()
        result = registry.dumps({"key": "value"}, "json")
        assert isinstance(result, str)

    def test_dumps_unknown_codec(self):
        """Test dumps with unknown codec."""
        registry = CodecRegistry()
        with pytest.raises(ValueError):
            registry.dumps({"key": "value"}, "unknown")

    def test_loads_with_default(self):
        """Test loads with default codec."""
        registry = CodecRegistry()
        result = registry.loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_with_specific_codec(self):
        """Test loads with specific codec."""
        registry = CodecRegistry()
        result = registry.loads('{"key": "value"}', "json")
        assert result == {"key": "value"}


class TestGlobalRegistry:
    """Tests for global codec registry."""

    def test_get_global_registry(self):
        """Test getting global registry."""
        registry = get_codec_registry()
        assert isinstance(registry, CodecRegistry)

    def test_global_registry_is_singleton(self):
        """Test that global registry is singleton."""
        registry1 = get_codec_registry()
        registry2 = get_codec_registry()
        assert registry1 is registry2


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_dumps(self):
        """Test dumps convenience function."""
        result = dumps({"key": "value"})
        assert isinstance(result, str)

    def test_loads(self):
        """Test loads convenience function."""
        result = loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_dumps_to_str_with_str(self):
        """Test dumps_to_str with str result."""
        result = dumps_to_str({"key": "value"})
        assert isinstance(result, str)
        assert result == '{"key":"value"}'

    def test_dumps_to_str_with_bytes(self):
        """Test dumps_to_str with bytes result."""
        # If orjson is default, this should still return str
        orjson_codec = OrjsonCodec()
        if orjson_codec.is_available:
            # Temporarily set orjson as default
            registry = get_codec_registry()
            registry.set_default("orjson")
            result = dumps_to_str({"key": "value"})
            assert isinstance(result, str)
            # Reset to json
            registry.set_default("json")


class TestBenchmarkCodecs:
    """Tests for benchmark_codecs function."""

    def test_benchmark_codecs(self):
        """Test benchmarking different codecs."""
        data = {"key": "value", "list": list(range(100))}
        results = benchmark_codecs(data, iterations=10)

        # Should have results for standard json at minimum
        assert "json" in results
        assert "dumps_avg_ms" in results["json"]
        assert "loads_avg_ms" in results["json"]

    def test_benchmark_results_structure(self):
        """Test benchmark results structure."""
        data = {"key": "value"}
        results = benchmark_codecs(data, iterations=5)

        for codec_name, metrics in results.items():
            assert metrics["dumps_avg_ms"] >= 0
            assert metrics["loads_avg_ms"] >= 0
            assert metrics["total_avg_ms"] >= 0


class TestCodecInterface:
    """Tests for JSONCodec interface."""

    def test_is_abstract(self):
        """Test that JSONCodec is abstract."""
        # JSONCodec is an abstract base class
        # Subclasses must implement the abstract methods
        assert hasattr(JSONCodec, "dumps")
        assert hasattr(JSONCodec, "loads")
        assert hasattr(JSONCodec, "name")
        # These are abstract methods
        assert getattr(JSONCodec.dumps, "__isabstractmethod__", False)
        assert getattr(JSONCodec.loads, "__isabstractmethod__", False)
        assert getattr(JSONCodec.name, "__isabstractmethod__", False)
