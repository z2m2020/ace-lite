from __future__ import annotations

from ace_lite.memory import MemoryChannelRegistry, NullMemoryProvider


def test_memory_channel_registry_resolves_aliases() -> None:
    registry = MemoryChannelRegistry()
    registry.register(
        name="none",
        aliases=("off", "disabled"),
        factory=lambda: NullMemoryProvider(),
    )

    assert isinstance(registry.create("none"), NullMemoryProvider)
    assert isinstance(registry.create("off"), NullMemoryProvider)
    assert isinstance(registry.create("disabled"), NullMemoryProvider)
    assert registry.canonical_name("OFF") == "none"


def test_memory_channel_registry_rejects_duplicate_alias() -> None:
    registry = MemoryChannelRegistry()
    registry.register(name="none", aliases=("off",), factory=lambda: NullMemoryProvider())
    try:
        registry.register(name="other", aliases=("off",), factory=lambda: NullMemoryProvider())
        raise AssertionError("expected duplicate alias error")
    except ValueError:
        pass


def test_memory_channel_registry_rejects_unknown_channel() -> None:
    registry = MemoryChannelRegistry()
    registry.register(name="none", factory=lambda: NullMemoryProvider())
    try:
        registry.create("missing")
        raise AssertionError("expected KeyError for unsupported channel")
    except KeyError:
        pass
