"""Hint extraction helpers for the docs retrieval channel."""

from __future__ import annotations

from collections.abc import Callable
from re import Pattern
from typing import Any


def extract_code_hints(
    *,
    evidence: list[dict[str, Any]],
    query_tokens: list[str],
    path_hint_re: Pattern[str],
    module_hint_re: Pattern[str],
    symbol_hint_re: Pattern[str],
    normalize_path: Callable[[str], str],
    normalize_module: Callable[[str], str],
    normalize_symbol: Callable[[str], str],
    normalize_score_table: Callable[..., list[dict[str, Any]]],
    extract_code_fence_values: Callable[[str], list[str]],
) -> dict[str, Any]:
    path_scores: dict[str, float] = {}
    module_scores: dict[str, float] = {}
    symbol_scores: dict[str, float] = {}

    for rank, item in enumerate(evidence):
        base_score = float(item.get("score", 0.0) or 0.0)
        decay = 1.0 / float(rank + 1)
        weight = base_score * decay
        blob = " ".join(
            [
                str(item.get("path", "")),
                str(item.get("heading", "")),
                str(item.get("heading_path", "")),
                str(item.get("snippet", "")),
            ]
        )
        if not blob:
            continue

        body = str(item.get("body", ""))
        if body:
            for raw in path_hint_re.findall(body):
                path = normalize_path(raw)
                if not path:
                    continue
                path_scores[path] = path_scores.get(path, 0.0) + weight

            for raw in extract_code_fence_values(body):
                for path in path_hint_re.findall(raw):
                    normalized = normalize_path(path)
                    if not normalized:
                        continue
                    path_scores[normalized] = path_scores.get(normalized, 0.0) + weight

                for module in module_hint_re.findall(raw):
                    normalized = normalize_module(module)
                    if not normalized:
                        continue
                    module_scores[normalized] = (
                        module_scores.get(normalized, 0.0) + weight
                    )

                for symbol in symbol_hint_re.findall(raw):
                    normalized = normalize_symbol(symbol)
                    if not normalized:
                        continue
                    symbol_scores[normalized] = (
                        symbol_scores.get(normalized, 0.0) + weight
                    )

        for raw in path_hint_re.findall(blob):
            path = normalize_path(raw)
            if not path:
                continue
            path_scores[path] = path_scores.get(path, 0.0) + weight

        for raw in extract_code_fence_values(blob):
            for path in path_hint_re.findall(raw):
                normalized = normalize_path(path)
                if not normalized:
                    continue
                path_scores[normalized] = path_scores.get(normalized, 0.0) + weight

            for module in module_hint_re.findall(raw):
                normalized = normalize_module(module)
                if not normalized:
                    continue
                module_scores[normalized] = module_scores.get(normalized, 0.0) + weight

            for symbol in symbol_hint_re.findall(raw):
                normalized = normalize_symbol(symbol)
                if not normalized:
                    continue
                symbol_scores[normalized] = symbol_scores.get(normalized, 0.0) + weight

        for module in module_hint_re.findall(blob):
            normalized = normalize_module(module)
            if not normalized:
                continue
            module_scores[normalized] = module_scores.get(normalized, 0.0) + (
                weight * 0.7
            )

    normalized_path_scores = normalize_score_table(path_scores)
    normalized_module_scores = normalize_score_table(module_scores)
    normalized_symbol_scores = normalize_score_table(symbol_scores)

    return {
        "paths": [item["value"] for item in normalized_path_scores],
        "modules": [item["value"] for item in normalized_module_scores],
        "symbols": [item["value"] for item in normalized_symbol_scores],
        "path_scores": normalized_path_scores,
        "module_scores": normalized_module_scores,
        "symbol_scores": normalized_symbol_scores,
        "query_tokens": list(query_tokens),
    }


def extract_code_fence_values(blob: str, *, code_fence_re: Pattern[str]) -> list[str]:
    return [
        str(item or "").strip()
        for item in code_fence_re.findall(blob)
        if str(item or "").strip()
    ]


__all__ = ["extract_code_fence_values", "extract_code_hints"]
