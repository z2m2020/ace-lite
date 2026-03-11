"""Adaptive retrieval gate for memory stage.

This module decides whether a query should trigger memory retrieval at all.
It is designed to:
- avoid expensive/low-signal memory calls for greetings/commands
- still allow short, explicit memory-intent queries (force retrieve)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_SKIP_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Greetings & pleasantries
    re.compile(
        r"^(hi|hello|hey|good\s*(morning|afternoon|evening|night)|greetings|yo|sup|howdy|what'?s up)\b",
        re.IGNORECASE,
    ),
    # Slash commands
    re.compile(r"^/"),
    # Shell-like commands
    re.compile(
        r"^(run|build|test|ls|cd|git|npm|pnpm|yarn|pip|python|docker|curl|cat|grep|find|make|sudo)\b",
        re.IGNORECASE,
    ),
    # Simple affirmations/negations
    re.compile(
        r"^(yes|no|yep|nope|ok|okay|sure|fine|thanks|thank you|thx|ty|got it|understood|cool|nice|great|good|perfect)\b",
        re.IGNORECASE,
    ),
    # Pure emoji / whitespace
    re.compile(r"^[\W_]+$", re.UNICODE),
    # Heartbeat/system
    re.compile(r"^HEARTBEAT", re.IGNORECASE),
    re.compile(r"^\[System", re.IGNORECASE),
)

_FORCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(remember|recall|forgot|memory|memories)\b", re.IGNORECASE),
    re.compile(r"\b(last time|before|previously|earlier|yesterday|ago)\b", re.IGNORECASE),
    re.compile(r"\b(what did (i|we)|did i (tell|say|mention))\b", re.IGNORECASE),
    re.compile(r"\b(my (name|email|phone|address|birthday|preference))\b", re.IGNORECASE),
    # Chinese variants (minimal set)
    re.compile(r"(你记得|之前|上次|以前|还记得|我之前|我上次)"),
)


@dataclass(frozen=True, slots=True)
class MemoryGateDecision:
    should_retrieve: bool
    reason: str


def decide_memory_retrieval(*, query: str) -> MemoryGateDecision:
    """Return whether memory retrieval should run for ``query``.

    The decision is deterministic and intentionally conservative:
    - Explicit memory intent forces retrieval even for short queries.
    - Otherwise, short/command-like content is skipped.
    """
    text = str(query or "").strip()
    if not text:
        return MemoryGateDecision(False, "empty")

    for pattern in _FORCE_PATTERNS:
        if pattern.search(text):
            return MemoryGateDecision(True, "force")

    # Too short to be meaningful (unless forced).
    if len(text) < 5:
        return MemoryGateDecision(False, "too_short")

    for pattern in _SKIP_PATTERNS:
        if pattern.search(text):
            return MemoryGateDecision(False, "skip_pattern")

    # For very short non-question messages, skip by default.
    has_cjk = bool(re.search(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", text))
    min_len = 6 if has_cjk else 15
    if len(text) < min_len and "?" not in text and "？" not in text:
        return MemoryGateDecision(False, "short_non_question")

    return MemoryGateDecision(True, "default")


__all__ = ["MemoryGateDecision", "decide_memory_retrieval"]

