"""Glossary helpers for the docs retrieval channel."""

from __future__ import annotations

from re import Pattern
from typing import Any, Callable

Section = dict[str, Any]


def build_repo_glossary(
    *,
    sections: list[Section],
    max_terms: int,
    is_glossary_token: Callable[[str], bool],
) -> list[str]:
    token_scores: dict[str, float] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        for key, weight in (
            ("heading_tokens", 2.5),
            ("heading_path_tokens", 2.0),
            ("body_tokens", 1.0),
        ):
            mapping = section.get(key)
            if not isinstance(mapping, dict):
                continue
            for raw_token, raw_count in mapping.items():
                token = str(raw_token or "").strip().lower()
                if not is_glossary_token(token):
                    continue
                try:
                    parsed_count = float(raw_count or 0.0)
                except (TypeError, ValueError):
                    continue
                if parsed_count <= 0.0:
                    continue
                token_scores[token] = token_scores.get(token, 0.0) + (parsed_count * float(weight))
    ranked = sorted(token_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
    return [token for token, _ in ranked[: max(0, int(max_terms))]]


def derive_glossary_terms(
    *,
    heading_path: str,
    body: str,
    matched_terms: list[str],
    query_tokens: list[str],
    repo_glossary: list[str] | None = None,
    max_terms: int = 6,
    token_re: Pattern[str],
    module_hint_re: Pattern[str],
    symbol_hint_re: Pattern[str],
    is_glossary_token: Callable[[str], bool],
    build_snippet: Callable[..., str],
) -> list[str]:
    token_scores: dict[str, float] = {}

    def _add_terms(raw: str, weight: float) -> None:
        for token in token_re.findall(str(raw or "").lower()):
            if not is_glossary_token(token):
                continue
            token_scores[token] = token_scores.get(token, 0.0) + float(weight)

    _add_terms(str(heading_path or ""), 2.0)
    for token in matched_terms:
        _add_terms(token, 3.0)
    for token in query_tokens:
        _add_terms(token, 1.0)

    first_line = build_snippet(text=body, query_tokens=query_tokens, max_chars=320)
    _add_terms(first_line, 0.5)

    for module in module_hint_re.findall(str(body or "")):
        _add_terms(module, 1.4)
    for symbol in symbol_hint_re.findall(str(body or "")):
        _add_terms(symbol, 1.0)
    body_token_set = {
        token
        for token in token_re.findall(str(body or "").lower())
        if is_glossary_token(token)
    }
    for token in (repo_glossary or [])[:128]:
        normalized = str(token or "").strip().lower()
        if normalized and normalized in body_token_set:
            token_scores[normalized] = token_scores.get(normalized, 0.0) + 0.6

    ranked = sorted(token_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
    return [token for token, _ in ranked[: max(0, int(max_terms))]]


def is_glossary_token(
    token: str,
    *,
    glossary_stopwords: frozenset[str],
    module_stopwords: frozenset[str],
) -> bool:
    normalized = str(token or "").strip().lower()
    if len(normalized) < 3:
        return False
    if normalized.isdigit():
        return False
    if normalized in glossary_stopwords or normalized in module_stopwords:
        return False
    return True
