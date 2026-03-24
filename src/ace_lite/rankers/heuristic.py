"""Heuristic candidate ranker.

This ranker uses hand-crafted scoring rules based on path, module,
symbol, and import matching. It's designed to be fast and deterministic,
providing a reliable baseline for more sophisticated rankers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.scoring_config import (
    resolve_heuristic_scoring_config,
)

# Default stopwords (same as orchestrator)
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "being", "but",
        "by", "can", "could", "did", "do", "does", "doing", "else", "for",
        "from", "had", "has", "have", "here", "how", "if", "in", "into",
        "is", "it", "its", "may", "might", "must", "no", "not", "of", "on",
        "or", "our", "should", "that", "the", "their", "then", "there",
        "these", "they", "this", "those", "to", "was", "we", "were", "what",
        "when", "where", "which", "who", "why", "with", "without", "would",
        "you", "your",
    }
)


def rank_candidates_heuristic(
    files_map: Any,
    terms: list[str],
    *,
    min_score: int = 1,
    scoring_config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank candidates using heuristic scoring.

    This is the primary heuristic ranker that scores files based on:
    - Path matching (exact, prefix, contains)
    - Module matching (exact, tail, contains)
    - Symbol matching (exact, partial)
    - Import matching
    - Content matching
    - Path depth bonus for src/api/ui directories

    Args:
        files_map: Dict mapping file paths to their index entries.
        terms: List of query terms to match.
        min_score: Minimum score threshold (default 1).

    Returns:
        List of candidate dicts sorted by score (descending).
    """
    if not isinstance(files_map, dict):
        return []

    normalized_terms = [
        str(term).strip().lower() for term in terms if str(term).strip()
    ]
    scoring = resolve_heuristic_scoring_config(scoring_config)
    threshold = max(0, int(min_score))
    ranked: list[dict[str, Any]] = []

    for path, entry in files_map.items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            continue

        path_lower = path.lower()
        module = str(entry.get("module", ""))
        module_lower = module.lower()
        tier = str(entry.get("tier") or "").strip().lower()

        # Collect symbol information
        symbols_blob: list[str] = []
        symbol_names: list[str] = []
        exact_symbols: set[str] = set()
        symbols = entry.get("symbols", [])
        if isinstance(symbols, list):
            for item in symbols:
                if isinstance(item, dict):
                    qualified = str(item.get("qualified_name", ""))
                    name = str(item.get("name", ""))
                    if qualified:
                        symbols_blob.append(qualified)
                        exact_symbols.add(qualified.lower())
                    if name:
                        symbols_blob.append(name)
                        symbol_names.append(name.lower())
                        exact_symbols.add(name.lower())

        # Collect import information
        imports_blob: list[str] = []
        import_names: list[str] = []
        imports = entry.get("imports", [])
        if isinstance(imports, list):
            for item in imports:
                if isinstance(item, dict):
                    module_name = str(item.get("module", ""))
                    import_name = str(item.get("name", ""))
                    if module_name:
                        imports_blob.append(module_name)
                        import_names.append(module_name.lower())
                    if import_name:
                        imports_blob.append(import_name)
                        import_names.append(import_name.lower())

        # Handle empty terms case
        if not normalized_terms:
            depth = len([part for part in path.split("/") if part])
            score = (
                max(0.1, 2.5 - (depth * 0.2))
                if path.startswith(("src/", "api/", "ui/"))
                else 0.0
            )
            breakdown = {
                "path": round(score, 6),
                "symbol": 0.0,
                "import": 0.0,
                "content": 0.0,
                "depth": round(score, 6),
            }
        else:
            # Compute scores for each term
            path_score = 0.0
            symbol_score = 0.0
            import_score = 0.0
            content_score = 0.0

            symbols_blob_lower = [blob.lower() for blob in symbols_blob]
            imports_blob_lower = [blob.lower() for blob in imports_blob]

            for term in normalized_terms:
                is_short = len(term) < 4

                # Path matching
                if path_lower.startswith(term) or f"/{term}" in path_lower:
                    path_score += float(scoring["path_exact"])
                elif not is_short and term in path_lower:
                    path_score += float(scoring["path_contains"])

                # Module matching
                if module_lower == term:
                    path_score += float(scoring["module_exact"])
                elif module_lower.endswith(f".{term}"):
                    path_score += float(scoring["module_tail"])
                elif not is_short and term in module_lower:
                    path_score += float(scoring["module_contains"])

                # Symbol matching
                symbol_exact = term in exact_symbols
                if symbol_exact:
                    symbol_score += float(scoring["symbol_exact"])
                elif not is_short:
                    symbol_hits = sum(1 for name in symbol_names if term in name)
                    if symbol_hits:
                        symbol_score += min(
                            float(scoring["symbol_partial_cap"]),
                            symbol_hits * float(scoring["symbol_partial_factor"]),
                        )

                # Import matching
                if not is_short:
                    import_hits = sum(1 for name in import_names if term in name)
                    if import_hits:
                        import_score += min(
                            float(scoring["import_cap"]),
                            import_hits * float(scoring["import_factor"]),
                        )

                # Content matching (when no exact symbol match)
                if not is_short and not symbol_exact:
                    symbol_blob_hits = sum(
                        1 for blob in symbols_blob_lower if term in blob
                    )
                    import_blob_hits = sum(
                        1 for blob in imports_blob_lower if term in blob
                    )
                    if symbol_blob_hits or import_blob_hits:
                        content_score += min(
                            float(scoring["content_cap"]),
                            (
                                symbol_blob_hits
                                * float(scoring["content_symbol_factor"])
                            )
                            + (
                                import_blob_hits
                                * float(scoring["content_import_factor"])
                            ),
                        )

            # Depth bonus for source directories
            depth = len([part for part in path.split("/") if part])
            base_score = path_score + symbol_score + import_score + content_score
            depth_bonus = (
                max(
                    0.0,
                    float(scoring["depth_base"])
                    - (depth * float(scoring["depth_factor"])),
                )
                if base_score > 0.0 and path.startswith(("src/", "api/", "ui/"))
                else 0.0
            )
            score = base_score + depth_bonus
            breakdown = {
                "path": round(path_score, 6),
                "symbol": round(symbol_score, 6),
                "import": round(import_score, 6),
                "content": round(content_score, 6),
                "depth": round(depth_bonus, 6),
            }

        # Down-rank dependency code by default so first-party logic wins unless
        # the query strongly indicates otherwise.
        if tier == "dependency" and score > 0.0:
            score *= 0.35

        if score < threshold:
            continue

        ranked.append(
            {
                "path": path,
                "module": module,
                "language": entry.get("language", ""),
                "score": round(float(score), 6),
                "symbol_count": len(symbol_names),
                "import_count": len(import_names),
                "score_breakdown": breakdown,
            }
        )

    # Sort by score descending, then by path for determinism
    ranked.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
        )
    )
    return ranked


__all__ = ["_STOPWORDS", "rank_candidates_heuristic"]
