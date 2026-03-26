"""BM25-based candidate ranker.

This ranker implements the Okapi BM25 ranking function with extensions
for file-specific features like path prefixes and module names.
"""

from __future__ import annotations

import hashlib
import inspect
import math
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

from ace_lite.text_tokens import code_tokens
from ace_lite.scoring_config import resolve_bm25_scoring_config


def _tokenize_words(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric words."""
    return code_tokens(str(text), min_len=2, max_tokens=96)


_BM25_CACHE_MAX_ENTRIES = 4
_BM25_CACHE_VERSION = "bm25-docs-v2"
_BM25_DOC_CACHE: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()


def _bm25_scope_fingerprint(files_map: Any) -> str:
    if not isinstance(files_map, dict):
        return ""
    paths = [
        str(path).strip()
        for path, entry in files_map.items()
        if isinstance(path, str) and isinstance(entry, dict)
    ]
    if not paths:
        return ""
    normalized = "\n".join(sorted(paths)).encode("utf-8", errors="ignore")
    return hashlib.sha256(normalized).hexdigest()[:16]


def _bm25_cache_key(index_hash: str | None, files_map: Any) -> str | None:
    normalized = str(index_hash or "").strip()
    if not normalized:
        return None
    scope = _bm25_scope_fingerprint(files_map)
    if not scope:
        return None
    return f"{_BM25_CACHE_VERSION}:{normalized}:{scope}"


def _get_cached_docs(cache_key: str | None) -> list[dict[str, Any]] | None:
    if cache_key is None:
        return None
    docs = _BM25_DOC_CACHE.get(cache_key)
    if docs is None:
        return None
    _BM25_DOC_CACHE.move_to_end(cache_key)
    return docs


def _store_cached_docs(cache_key: str | None, docs: list[dict[str, Any]]) -> None:
    if cache_key is None:
        return
    _BM25_DOC_CACHE[cache_key] = docs
    _BM25_DOC_CACHE.move_to_end(cache_key)
    while len(_BM25_DOC_CACHE) > _BM25_CACHE_MAX_ENTRIES:
        _BM25_DOC_CACHE.popitem(last=False)


def rank_candidates_bm25(
    files_map: Any,
    terms: list[str],
    *,
    min_score: int = 1,
    index_hash: str | None = None,
    bm25_config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank candidates using BM25 scoring.

    BM25 is a probabilistic ranking function that considers:
    - Term frequency in documents
    - Document length normalization
    - Inverse document frequency

    Extended with path prior for src/api/ui directories.

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
    if not normalized_terms:
        return []
    scoring = resolve_bm25_scoring_config(bm25_config)

    cache_key = _bm25_cache_key(index_hash, files_map)
    cached_docs = _get_cached_docs(cache_key)
    docs: list[dict[str, Any]] = list(cached_docs) if cached_docs is not None else []

    if cached_docs is None:
        # Build document representations
        docs = []
        for path, entry in files_map.items():
            if not isinstance(path, str) or not isinstance(entry, dict):
                continue

            module = str(entry.get("module", ""))
            tier = str(entry.get("tier") or "").strip().lower()
            symbols = entry.get("symbols", [])
            imports = entry.get("imports", [])

            tokens: list[str] = []
            # Path tokens (weighted 3x)
            tokens.extend(token for token in _tokenize_words(path) for _ in range(3))
            # Module tokens (weighted 2x)
            tokens.extend(token for token in _tokenize_words(module) for _ in range(2))

            symbol_count = 0
            if isinstance(symbols, list):
                for item in symbols:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", ""))
                    qualified = str(item.get("qualified_name", ""))
                    if name:
                        symbol_count += 1
                        tokens.extend(token for token in _tokenize_words(name) for _ in range(2))
                    if qualified:
                        tokens.extend(_tokenize_words(qualified))

            import_count = 0
            if isinstance(imports, list):
                for item in imports:
                    if not isinstance(item, dict):
                        continue
                    module_name = str(item.get("module", ""))
                    import_name = str(item.get("name", ""))
                    if module_name:
                        import_count += 1
                        tokens.extend(_tokenize_words(module_name))
                    if import_name:
                        tokens.extend(_tokenize_words(import_name))

            if not tokens:
                continue

            # Compute term frequencies
            term_frequency: dict[str, int] = {}
            for token in tokens:
                term_frequency[token] = term_frequency.get(token, 0) + 1

            docs.append(
                {
                    "path": path,
                    "module": module,
                    "language": entry.get("language", ""),
                    "tier": tier,
                    "term_frequency": term_frequency,
                    "doc_length": len(tokens),
                    "symbol_count": symbol_count,
                    "import_count": import_count,
                }
            )

        if docs:
            _store_cached_docs(cache_key, docs)

    if not docs:
        return []

    # Compute collection statistics
    total_docs = len(docs)
    average_doc_length = sum(int(doc["doc_length"]) for doc in docs) / max(
        1.0, float(total_docs)
    )

    # Document frequency for each term
    document_frequency = {term: 0 for term in normalized_terms}
    for doc in docs:
        term_frequency = doc.get("term_frequency", {})
        if not isinstance(term_frequency, dict):
            continue
        for term in normalized_terms:
            if term_frequency.get(term, 0) > 0:
                document_frequency[term] = document_frequency.get(term, 0) + 1

    k1 = float(scoring["k1"])
    b = float(scoring["b"])
    threshold = max(0.0, float(min_score))

    ranked: list[dict[str, Any]] = []
    for doc in docs:
        path = str(doc.get("path", ""))
        module = str(doc.get("module", ""))
        language = doc.get("language", "")
        term_frequency = doc.get("term_frequency", {})
        if not isinstance(term_frequency, dict):
            continue

        doc_length = float(doc.get("doc_length", 0) or 0)
        raw_score = 0.0
        matched_terms = 0

        for term in normalized_terms:
            tf = float(term_frequency.get(term, 0) or 0)
            if tf <= 0:
                continue

            matched_terms += 1
            df = float(document_frequency.get(term, 0) or 0)
            idf = math.log(1.0 + ((total_docs - df + 0.5) / (df + 0.5)))
            denom = tf + k1 * (
                1.0 - b + b * (doc_length / max(average_doc_length, 1e-9))
            )
            raw_score += idf * ((tf * (k1 + 1.0)) / max(denom, 1e-9))

        # Path prior for source directories
        path_prior = 0.0
        if path.startswith(("src/", "api/", "ui/")):
            path_prior = float(scoring["path_prior_factor"]) * matched_terms

        score = (raw_score * float(scoring["score_scale"])) + path_prior
        tier = str(doc.get("tier") or "")
        if tier == "dependency" and score > 0.0:
            score *= 0.35
        if score < threshold:
            continue

        ranked.append(
            {
                "path": path,
                "module": module,
                "language": language,
                "score": round(float(score), 6),
                "symbol_count": int(doc.get("symbol_count", 0) or 0),
                "import_count": int(doc.get("import_count", 0) or 0),
                "score_breakdown": {
                    "bm25": round(raw_score * float(scoring["score_scale"]), 6),
                    "path_prior": round(path_prior, 6),
                    "matched_terms": matched_terms,
                    "ranker": "bm25_lite",
                },
            }
        )

    ranked.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
        )
    )
    return ranked


def rank_candidates_bm25_two_stage(
    files_map: Any,
    terms: list[str],
    *,
    min_score: int = 1,
    top_k_files: int = 8,
    heuristic_ranker: Callable[..., list[dict[str, Any]]],
    index_hash: str | None = None,
    bm25_config: Mapping[str, Any] | None = None,
    heuristic_config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Two-stage BM25 ranking with heuristic shortlist.

    First uses heuristic ranking to create a shortlist, then applies
    BM25 only to the shortlist for efficiency. Falls back to full corpus
    BM25 if shortlist is empty.

    Args:
        files_map: Dict mapping file paths to their index entries.
        terms: List of query terms to match.
        min_score: Minimum score threshold (default 1).
        top_k_files: Top-k parameter for shortlist sizing.
        heuristic_ranker: Function to use for first-stage ranking.

    Returns:
        List of candidate dicts sorted by score (descending).
    """
    if not isinstance(files_map, dict):
        return []
    scoring = resolve_bm25_scoring_config(bm25_config)

    def _call_bm25(
        corpus: dict[str, Any],
        *,
        min_score: int,
        index_hash: str | None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "min_score": min_score,
            "index_hash": index_hash,
            "bm25_config": scoring,
        }
        try:
            signature = inspect.signature(rank_candidates_bm25)
        except (TypeError, ValueError):
            signature = None
        if signature is not None:
            supported = {
                name
                for name, parameter in signature.parameters.items()
                if parameter.kind
                in (
                    inspect.Parameter.KEYWORD_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            }
            kwargs = {
                key: value for key, value in kwargs.items() if key in supported
            }
        return rank_candidates_bm25(corpus, terms, **kwargs)

    # First stage: heuristic ranking
    try:
        heuristic_ranked = heuristic_ranker(
            files_map,
            terms,
            min_score=0,
            scoring_config=heuristic_config,
        )
    except TypeError:
        heuristic_ranked = heuristic_ranker(files_map, terms, min_score=0)
    if not heuristic_ranked:
        return _call_bm25(files_map, min_score=min_score, index_hash=index_hash)

    # Compute shortlist size
    shortlist_limit = max(
        max(1, int(top_k_files)) * int(scoring["shortlist_factor"]),
        int(scoring["shortlist_min"]),
    )
    shortlist_paths = [
        str(item.get("path") or "").strip()
        for item in heuristic_ranked[:shortlist_limit]
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]

    shortlist_files = {
        path: files_map[path]
        for path in shortlist_paths
        if path in files_map and isinstance(files_map.get(path), dict)
    }

    # Second stage: BM25 on shortlist
    ranked = _call_bm25(shortlist_files, min_score=min_score, index_hash=None)
    if ranked:
        return ranked

    # Fallback: BM25 on full corpus
    return _call_bm25(files_map, min_score=min_score, index_hash=index_hash)


__all__ = [
    "_tokenize_words",
    "rank_candidates_bm25",
    "rank_candidates_bm25_two_stage",
]
