"""Memory provider abstractions and OpenMemory client adapters.

This package defines the memory-provider contracts used by the orchestrator.
Providers expose compact search results first, and fetch full records only
when requested.
"""

from __future__ import annotations

from .channel_registry import MemoryChannelRegistry
from .dual_channel import DualChannelMemoryProvider
from .helpers import prune_memory_notes_rows
from .hybrid_provider import HybridMemoryProvider
from .local_cache import LocalCacheProvider
from .local_notes import LocalNotesProvider
from .null_provider import NullMemoryProvider
from .openmemory_provider import OpenMemoryMemoryProvider
from .protocol import MemoryProvider, OpenMemoryClient
from .record import MemoryRecord, MemoryRecordCompact

__all__ = [
    "DualChannelMemoryProvider",
    "HybridMemoryProvider",
    "LocalCacheProvider",
    "LocalNotesProvider",
    "MemoryChannelRegistry",
    "MemoryProvider",
    "MemoryRecord",
    "MemoryRecordCompact",
    "NullMemoryProvider",
    "OpenMemoryClient",
    "OpenMemoryMemoryProvider",
    "prune_memory_notes_rows",
]
