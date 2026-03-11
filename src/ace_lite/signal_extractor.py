"""Deterministic reusable-signal extraction from plan queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "bug",
    "fix",
    "issue",
    "incident",
    "todo",
    "regression",
    "root cause",
)


@dataclass(frozen=True, slots=True)
class SignalExtraction:
    triggered: bool
    matched_keywords: tuple[str, ...]
    query_length: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "matched_keywords": list(self.matched_keywords),
            "query_length": self.query_length,
            "reason": self.reason,
        }


class SignalExtractor:
    """Rule-based extractor designed for deterministic behavior and regression tests."""

    def __init__(
        self,
        *,
        keywords: list[str] | tuple[str, ...] | None = None,
        min_query_length: int = 24,
    ) -> None:
        normalized_keywords = [
            str(item).strip().lower()
            for item in (keywords or DEFAULT_SIGNAL_KEYWORDS)
            if str(item).strip()
        ]
        self._keywords = tuple(dict.fromkeys(normalized_keywords))
        self._min_query_length = max(1, int(min_query_length))

    def extract(self, query: str) -> SignalExtraction:
        normalized_query = str(query or "").strip().lower()
        query_length = len(normalized_query)
        if not normalized_query:
            return SignalExtraction(
                triggered=False,
                matched_keywords=(),
                query_length=0,
                reason="empty_query",
            )
        if query_length < self._min_query_length:
            return SignalExtraction(
                triggered=False,
                matched_keywords=(),
                query_length=query_length,
                reason="below_min_length",
            )

        matches = tuple(
            keyword for keyword in self._keywords if keyword in normalized_query
        )
        if not matches:
            return SignalExtraction(
                triggered=False,
                matched_keywords=(),
                query_length=query_length,
                reason="no_keyword_match",
            )
        return SignalExtraction(
            triggered=True,
            matched_keywords=matches,
            query_length=query_length,
            reason="keyword_match",
        )


__all__ = ["DEFAULT_SIGNAL_KEYWORDS", "SignalExtraction", "SignalExtractor"]
