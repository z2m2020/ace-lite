"""Types and protocols for ranker modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class Candidate:
    """Represents a ranked candidate file."""

    path: str
    score: float
    module: str = ""
    language: str = ""
    symbol_count: int = 0
    import_count: int = 0
    score_breakdown: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "module": self.module,
            "language": self.language,
            "score": self.score,
            "symbol_count": self.symbol_count,
            "import_count": self.import_count,
            "score_breakdown": self.score_breakdown,
        }


@dataclass(slots=True)
class RankResult:
    """Container for ranking results with metadata."""

    candidates: list[Candidate]
    ranker: str
    elapsed_ms: float = 0.0

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.candidates]


class RankerFunc(Protocol):
    """Protocol for ranker functions."""

    def __call__(
        self,
        files_map: Any,
        terms: list[str],
        *,
        min_score: int = 1,
    ) -> list[dict[str, Any]]: ...


__all__ = ["Candidate", "RankResult", "RankerFunc"]
