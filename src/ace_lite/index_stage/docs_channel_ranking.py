"""Ranking helpers for docs-channel retrieval."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any


def build_query_tokens(
    *,
    query: str,
    terms: list[str],
    token_re: re.Pattern[str],
) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in token_re.findall(str(query or "").lower()):
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    for raw in terms:
        token = str(raw or "").strip().lower()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def rank_sections(
    *,
    sections: list[dict[str, Any]],
    query_tokens: list[str],
    intent_weight: float,
    doc_intent_markers: frozenset[str],
    term_frequency: Callable[..., float],
) -> list[dict[str, Any]]:
    if not sections:
        return []

    matched_counts: dict[str, int] = {token: 0 for token in query_tokens}
    avg_len = (
        sum(max(1, int(item.get("weighted_len", 1) or 1)) for item in sections)
        / float(max(1, len(sections)))
    )
    for item in sections:
        for token in query_tokens:
            if term_frequency(item=item, token=token) > 0.0:
                matched_counts[token] = matched_counts.get(token, 0) + 1

    total_docs = max(1, len(sections))
    k1 = 1.2
    b = 0.75
    query_markers = set(query_tokens) & doc_intent_markers
    scored: list[dict[str, Any]] = []

    for item in sections:
        document_len = max(1.0, float(item.get("weighted_len", 1.0) or 1.0))
        score = 0.0
        matched_terms: list[str] = []
        for token in query_tokens:
            tf = term_frequency(item=item, token=token)
            if tf <= 0.0:
                continue
            matched_terms.append(token)
            df = max(1, int(matched_counts.get(token, 0)))
            idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - b + b * (document_len / max(1e-9, avg_len)))
            score += idf * ((tf * (k1 + 1.0)) / max(1e-9, denom))

        if score <= 0.0:
            continue

        weighted_score = score * max(0.1, float(intent_weight)) * _marker_boost(
            item=item,
            query_markers=query_markers,
        )
        scored.append(
            {
                **item,
                "score": weighted_score,
                "matched_terms": matched_terms,
            }
        )

    _sort_scored(scored)
    return scored


def rank_sections_fts5(
    *,
    sections: list[dict[str, Any]],
    query_tokens: list[str],
    intent_weight: float,
    doc_intent_markers: frozenset[str],
    term_frequency: Callable[..., float],
    build_fts5_query: Callable[..., str],
    normalize_fts5_score: Callable[[float], float],
) -> list[dict[str, Any]]:
    import sqlite3

    if not sections:
        return []
    query_expr = build_fts5_query(query_tokens=query_tokens)
    if not query_expr:
        return []

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    scored: list[dict[str, Any]] = []
    query_markers = set(query_tokens) & doc_intent_markers
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE docs_fts USING fts5(path, heading, heading_path, body)"
        )
        conn.executemany(
            "INSERT INTO docs_fts(path, heading, heading_path, body) VALUES (?, ?, ?, ?)",
            [
                (
                    str(item.get("path") or ""),
                    str(item.get("heading") or ""),
                    str(item.get("heading_path") or ""),
                    str(item.get("body") or ""),
                )
                for item in sections
            ],
        )
        cursor = conn.execute(
            (
                "SELECT rowid, bm25(docs_fts, 0.8, 1.6, 1.2, 1.0) AS bm25_score "
                "FROM docs_fts WHERE docs_fts MATCH ? ORDER BY bm25_score ASC"
            ),
            (query_expr,),
        )
        for row in cursor.fetchall():
            rowid = int(row["rowid"] or 0)
            if rowid <= 0 or rowid > len(sections):
                continue
            item = sections[rowid - 1]
            matched_terms = [
                token for token in query_tokens if term_frequency(item=item, token=token) > 0.0
            ]
            if not matched_terms:
                continue

            raw = float(row["bm25_score"] or 0.0)
            lexical_score = normalize_fts5_score(raw)
            weighted_score = lexical_score * max(0.1, float(intent_weight)) * _marker_boost(
                item=item,
                query_markers=query_markers,
            )
            if weighted_score <= 0.0:
                continue
            scored.append(
                {
                    **item,
                    "score": weighted_score,
                    "matched_terms": matched_terms,
                }
            )
    finally:
        conn.close()

    _sort_scored(scored)
    return scored


def rank_sections_mirror_fts5(
    *,
    sections: list[dict[str, Any]],
    query_tokens: list[str],
    intent_weight: float,
    db_path: Path,
    limit: int,
    doc_intent_markers: frozenset[str],
    term_frequency: Callable[..., float],
    build_fts5_query: Callable[..., str],
    normalize_fts5_score: Callable[[float], float],
    query_docs_fts: Callable[..., list[tuple[int, float]]],
) -> list[dict[str, Any]]:
    if not sections:
        return []
    query_expr = build_fts5_query(query_tokens=query_tokens)
    if not query_expr:
        return []

    hits = query_docs_fts(db_path=db_path, query_expr=query_expr, limit=limit)
    if not hits:
        return []

    scored: list[dict[str, Any]] = []
    query_markers = set(query_tokens) & doc_intent_markers
    for rowid, raw_score in hits:
        if rowid <= 0 or rowid > len(sections):
            continue
        item = sections[rowid - 1]
        matched_terms = [
            token for token in query_tokens if term_frequency(item=item, token=token) > 0.0
        ]
        if not matched_terms:
            continue

        lexical_score = normalize_fts5_score(float(raw_score))
        weighted_score = lexical_score * max(0.1, float(intent_weight)) * _marker_boost(
            item=item,
            query_markers=query_markers,
        )
        if weighted_score <= 0.0:
            continue
        scored.append(
            {
                **item,
                "score": weighted_score,
                "matched_terms": matched_terms,
            }
        )

    _sort_scored(scored)
    return scored


def build_fts5_query(*, query_tokens: list[str]) -> str:
    terms: list[str] = []
    for token in query_tokens:
        normalized = str(token or "").strip().lower()
        if len(normalized) < 2:
            continue
        escaped = normalized.replace('"', '""')
        terms.append(f'"{escaped}"')
        if len(terms) >= 48:
            break
    return " OR ".join(terms)


def normalize_fts5_score(raw_score: float) -> float:
    score = float(raw_score)
    if score <= 0.0:
        return abs(score) + 1.0
    return 1.0 / (1.0 + score)


def sqlite_supports_fts5() -> bool:
    try:
        import sqlite3

        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE VIRTUAL TABLE docs_fts_probe USING fts5(content)")
            conn.execute("DROP TABLE docs_fts_probe")
            return True
        finally:
            conn.close()
    except Exception:
        return False


def term_frequency(*, item: dict[str, Any], token: str) -> float:
    heading = item.get("heading_tokens", {})
    heading_path = item.get("heading_path_tokens", {})
    body = item.get("body_tokens", {})
    return (
        float(heading.get(token, 0)) * 3.0
        + float(heading_path.get(token, 0)) * 2.0
        + float(body.get(token, 0))
    )


def _marker_boost(*, item: dict[str, Any], query_markers: set[str]) -> float:
    if not query_markers:
        return 1.0
    section_lexicon = (
        str(item.get("heading", "")).lower()
        + " "
        + str(item.get("heading_path", "")).lower()
        + " "
        + str(item.get("path", "")).lower()
    )
    if any(marker in section_lexicon for marker in query_markers):
        return 1.15
    return 1.0


def _sort_scored(scored: list[dict[str, Any]]) -> None:
    scored.sort(
        key=lambda row: (
            -float(row.get("score", 0.0) or 0.0),
            str(row.get("path", "")),
            str(row.get("heading_path", "")),
            int(row.get("line_start", 0) or 0),
        )
    )
