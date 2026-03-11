from __future__ import annotations

import importlib

from ace_lite.memory import (
    LocalCacheProvider,
    LocalNotesProvider,
    MemoryProvider,
    MemoryRecord,
    MemoryRecordCompact,
    NullMemoryProvider,
    OpenMemoryMemoryProvider,
    prune_memory_notes_rows,
)


def test_memory_package_exports_match_provider_modules() -> None:
    local_cache_module = importlib.import_module("ace_lite.memory.local_cache")
    local_notes_module = importlib.import_module("ace_lite.memory.local_notes")
    openmemory_module = importlib.import_module("ace_lite.memory.openmemory_provider")
    protocol_module = importlib.import_module("ace_lite.memory.protocol")
    helpers_module = importlib.import_module("ace_lite.memory.helpers")

    assert LocalCacheProvider is local_cache_module.LocalCacheProvider
    assert LocalNotesProvider is local_notes_module.LocalNotesProvider
    assert OpenMemoryMemoryProvider is openmemory_module.OpenMemoryMemoryProvider
    assert MemoryProvider is protocol_module.MemoryProvider
    assert prune_memory_notes_rows is helpers_module.prune_memory_notes_rows


def test_memory_package_records_roundtrip() -> None:
    compact = MemoryRecordCompact(handle="h1", preview="preview", est_tokens=2)
    full = MemoryRecord(text="full text", handle="h1")

    assert compact.to_dict()["handle"] == "h1"
    assert full.to_dict()["handle"] == "h1"


def test_null_provider_contract_stable_after_split() -> None:
    provider = NullMemoryProvider()
    assert provider.search_compact("query") == []
    assert provider.fetch(["h1"]) == []
