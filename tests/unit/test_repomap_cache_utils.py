"""Unit tests for repomap cache_utils module.

Tests verify the lightweight payload utilities for reducing
unnecessary deepcopy operations (QO-1102).
"""

from __future__ import annotations

import pytest

from ace_lite.repomap.cache_utils import (
    CacheEntryBuilder,
    ImmutablePayload,
    PayloadType,
    build_fingerprint,
    build_meta_fingerprint,
    estimate_token_weight,
    selective_copy_payload,
    shallow_copy_payload,
    wrap_read_only_payload,
    wrap_write_payload,
)


class TestPayloadType:
    """Tests for PayloadType constants."""

    def test_payload_types_defined(self):
        """Test that all payload types are defined."""
        assert PayloadType.READ_ONLY == "read_only"
        assert PayloadType.WRITE == "write"
        assert PayloadType.ARTIFACT_MEMORY == "artifact_memory"
        assert PayloadType.LEGACY == "legacy"


class TestShallowCopyPayload:
    """Tests for shallow_copy_payload."""

    def test_shallow_copy_simple(self):
        """Test simple dict shallow copy."""
        original = {"a": 1, "b": 2}
        copy = shallow_copy_payload(original)

        assert copy == original
        assert copy is not original
        assert copy["a"] == original["a"]

    def test_shallow_copy_nested(self):
        """Test that nested objects are NOT copied."""
        original = {"a": {"nested": 1}, "b": [1, 2, 3]}
        copy = shallow_copy_payload(original)

        # Top level is copied
        assert copy is not original

        # But nested objects are the same references
        assert copy["a"] is original["a"]
        assert copy["b"] is original["b"]

    def test_shallow_copy_empty(self):
        """Test empty dict."""
        assert shallow_copy_payload({}) == {}

    def test_shallow_copy_mutable_protection(self):
        """Test that top-level mutation doesn't affect original."""
        original = {"a": 1, "b": 2}
        copy = shallow_copy_payload(original)

        copy["a"] = 99
        assert original["a"] == 1


class TestSelectiveCopyPayload:
    """Tests for selective_copy_payload."""

    def test_selective_copy_deep(self):
        """Test that nested objects ARE copied."""
        original = {"a": {"nested": 1}}
        copy = selective_copy_payload(original)

        assert copy is not original
        assert copy["a"] is not original["a"]
        assert copy["a"] == original["a"]

    def test_selective_copy_list(self):
        """Test that lists are copied."""
        original = {"items": [1, 2, 3]}
        copy = selective_copy_payload(original)

        assert copy["items"] is not original["items"]
        assert copy["items"] == original["items"]

    def test_selective_copy_no_nested(self):
        """Test with copy_nested=False behaves like shallow."""
        original = {"a": {"nested": 1}}
        copy = selective_copy_payload(original, copy_nested=False)

        assert copy["a"] is original["a"]

    def test_selective_copy_immutable_values(self):
        """Test that immutable values are kept as references."""
        original = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
        }
        copy = selective_copy_payload(original)

        # All values should be equal (immutables)
        assert copy == original


class TestImmutablePayload:
    """Tests for ImmutablePayload frozen dataclass."""

    def test_creation(self):
        """Test basic creation."""
        payload = ImmutablePayload(
            data={"key": "value"},
            payload_type=PayloadType.READ_ONLY,
            source="test",
        )

        assert payload.data == {"key": "value"}
        assert payload.payload_type == PayloadType.READ_ONLY
        assert payload.source == "test"

    def test_frozen(self):
        """Test that the dataclass is frozen."""
        payload = ImmutablePayload(data={"key": "value"})

        # Attempting to set attributes should raise
        with pytest.raises(AttributeError):
            payload.data = {"new": "value"}  # type: ignore

    def test_unwrap(self):
        """Test unwrap returns the original data."""
        data = {"key": "value"}
        payload = ImmutablePayload(data=data)

        assert payload.unwrap() is data

    def test_unwrap_copy(self):
        """Test unwrap_copy returns a shallow copy."""
        data = {"key": "value"}
        payload = ImmutablePayload(data=data)

        copy = payload.unwrap_copy()
        assert copy == data
        assert copy is not data


class TestWrapFunctions:
    """Tests for wrap_read_only_payload and wrap_write_payload."""

    def test_wrap_read_only(self):
        """Test wrap_read_only_payload."""
        data = {"key": "value"}
        payload = wrap_read_only_payload(data, source="test")

        assert isinstance(payload, ImmutablePayload)
        assert payload.payload_type == PayloadType.READ_ONLY
        assert payload.source == "test"
        assert payload.data is data

    def test_wrap_write(self):
        """Test wrap_write_payload."""
        data = {"key": "value"}
        payload = wrap_write_payload(data, source="test")

        assert isinstance(payload, ImmutablePayload)
        assert payload.payload_type == PayloadType.WRITE
        assert payload.source == "test"


class TestBuildFingerprint:
    """Tests for fingerprint utilities."""

    def test_build_fingerprint_basic(self):
        """Test basic fingerprint generation."""
        fp1 = build_fingerprint(key="test_key")
        fp2 = build_fingerprint(key="test_key")

        assert fp1 == fp2
        assert len(fp1) == 64  # SHA256 hex length

    def test_build_fingerprint_different_keys(self):
        """Test different keys produce different fingerprints."""
        fp1 = build_fingerprint(key="key1")
        fp2 = build_fingerprint(key="key2")

        assert fp1 != fp2

    def test_build_fingerprint_with_kwargs(self):
        """Test fingerprint with additional parameters."""
        fp1 = build_fingerprint(key="test", param="value1")
        fp2 = build_fingerprint(key="test", param="value2")

        assert fp1 != fp2

    def test_build_meta_fingerprint(self):
        """Test meta fingerprint generation."""
        fp = build_meta_fingerprint({"key": "value"})

        assert len(fp) == 64
        assert fp == build_meta_fingerprint({"key": "value"})

    def test_build_meta_fingerprint_none(self):
        """Test meta fingerprint with None."""
        fp1 = build_meta_fingerprint(None)
        fp2 = build_meta_fingerprint({})

        assert fp1 == fp2


class TestEstimateTokenWeight:
    """Tests for token weight estimation."""

    def test_estimate_token_weight_basic(self):
        """Test basic token estimation."""
        weight = estimate_token_weight({"key": "hello world"})

        assert weight > 0

    def test_estimate_token_weight_empty(self):
        """Test empty payload."""
        weight = estimate_token_weight({})

        # Empty payload should still return at least 1
        assert weight >= 1

    def test_estimate_token_weight_consistency(self):
        """Test consistent estimation."""
        payload = {"key": "a" * 100}

        weight1 = estimate_token_weight(payload)
        weight2 = estimate_token_weight(payload)

        assert weight1 == weight2


class TestCacheEntryBuilder:
    """Tests for CacheEntryBuilder."""

    def test_build_write_entry(self):
        """Test building a WRITE entry."""
        builder = CacheEntryBuilder(
            key="test_key",
            payload={"data": "value"},
            payload_type=PayloadType.WRITE,
            stage_name="test_stage",
        )

        entry = builder.build()

        assert entry["key"] == "test_key"
        assert entry["stage_name"] == "test_stage"
        assert entry["payload"] == {"data": "value"}
        # For WRITE, we expect a shallow copy
        assert entry["payload"] is not builder.payload

    def test_build_read_only_entry(self):
        """Test building a READ_ONLY entry."""
        builder = CacheEntryBuilder(
            key="test_key",
            payload={"data": "value"},
            payload_type=PayloadType.READ_ONLY,
            stage_name="test_stage",
        )

        entry = builder.build()

        # For READ_ONLY, payload is kept as-is (upstream should protect)
        assert entry["payload"] is builder.payload

    def test_build_with_meta(self):
        """Test building entry with metadata."""
        builder = CacheEntryBuilder(
            key="test_key",
            payload={"data": "value"},
            meta={"ttl": 3600},
            stage_name="test_stage",
        )

        entry = builder.build()

        assert entry["meta"] == {"ttl": 3600}

    def test_build_no_payload_copy(self):
        """Test building without payload copy."""
        builder = CacheEntryBuilder(
            key="test_key",
            payload={"data": "value"},
            payload_type=PayloadType.WRITE,
        )

        entry = builder.build(include_payload_copy=False)

        assert entry["payload"] is builder.payload


class TestPerformanceCharacteristics:
    """Tests verifying performance characteristics of the utilities."""

    def test_shallow_copy_faster_than_deepcopy(self):
        """Verify shallow_copy is faster than deepcopy for simple structures."""
        import copy
        import time

        payload = {
            "key1": "value1",
            "key2": "value2",
            "key3": ["a", "b", "c"],
            "key4": {"nested": "data"},
        }

        # Warm up
        for _ in range(100):
            copy.deepcopy(payload)
            shallow_copy_payload(payload)

        # Measure
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            copy.deepcopy(payload)
        deepcopy_time = time.perf_counter() - start

        start = time.perf_counter()
        for _ in range(iterations):
            shallow_copy_payload(payload)
        shallow_time = time.perf_counter() - start

        # Shallow copy should be at least 2x faster
        assert shallow_time < deepcopy_time / 2, (
            f"Shallow copy ({shallow_time:.4f}s) should be significantly "
            f"faster than deepcopy ({deepcopy_time:.4f}s)"
        )

    def test_selective_copy_balances_safety_and_performance(self):
        """Verify selective_copy provides mutation protection."""
        original = {"a": {"b": 1}}

        # With selective copy, nested objects are protected
        protected = selective_copy_payload(original)
        protected["a"]["b"] = 999

        assert original["a"]["b"] == 1  # Original is safe

        # But we can still mutate top level
        protected["c"] = 3
        assert "c" not in original
