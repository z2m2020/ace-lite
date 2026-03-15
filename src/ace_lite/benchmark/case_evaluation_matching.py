"""Tokenization and hit-matching helpers for benchmark case evaluation."""

from __future__ import annotations

from typing import Any


def tokenize(text: str) -> set[str]:
    tokens = [
        item.strip().lower()
        for item in text.replace("/", " ").replace(".", " ").split()
    ]
    return {token for token in tokens if token}


def collect_candidate_match_details(
    *,
    top_candidates: list[Any],
    expected: list[str],
    top_k: int,
) -> dict[str, Any]:
    candidate_text = " ".join(
        str(item.get("path", "")) + " " + str(item.get("module", ""))
        for item in top_candidates
        if isinstance(item, dict)
    )
    candidate_tokens = tokenize(candidate_text)

    expected_token_sets = [tokenize(key) for key in expected]
    expected_hits = [
        key
        for key, token_set in zip(expected, expected_token_sets, strict=True)
        if token_set and candidate_tokens.intersection(token_set)
    ]
    recall_hit = 1.0 if expected and expected_hits else 0.0

    relevant_candidates = 0
    first_hit_rank: int | None = None
    relevant_candidate_paths: list[str] = []
    noise_candidate_paths: list[str] = []
    candidate_matches: list[dict[str, Any]] = []
    for idx, item in enumerate(top_candidates):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        text = f"{path} {item.get('module', '')}"
        token_set = tokenize(text)
        matched = [
            key
            for key, expected_tokens in zip(expected, expected_token_sets, strict=True)
            if expected_tokens and token_set.intersection(expected_tokens)
        ]
        if matched:
            relevant_candidates += 1
            relevant_candidate_paths.append(path)
            if first_hit_rank is None:
                first_hit_rank = idx + 1
        else:
            noise_candidate_paths.append(path)
        candidate_matches.append({"path": path, "matched_expected_keys": matched})

    denominator = max(1, min(top_k, len(top_candidates)) if top_candidates else top_k)
    precision = relevant_candidates / denominator
    noise = max(0.0, 1.0 - precision)
    hit_at_1 = 1.0 if first_hit_rank == 1 else 0.0
    reciprocal_rank = (1.0 / float(first_hit_rank)) if first_hit_rank else 0.0
    return {
        "expected_hits": expected_hits,
        "recall_hit": recall_hit,
        "relevant_candidates": relevant_candidates,
        "first_hit_rank": first_hit_rank,
        "relevant_candidate_paths": relevant_candidate_paths,
        "noise_candidate_paths": noise_candidate_paths,
        "candidate_matches": candidate_matches,
        "precision": precision,
        "utility": recall_hit,
        "noise": noise,
        "hit_at_1": hit_at_1,
        "reciprocal_rank": reciprocal_rank,
    }


def collect_chunk_match_details(
    *,
    top_chunks: list[Any],
    expected: list[str],
) -> dict[str, Any]:
    chunk_text = " ".join(
        f"{item.get('path', '')} {item.get('qualified_name', '')} {item.get('signature', '')}"
        for item in top_chunks
        if isinstance(item, dict)
    )
    chunk_tokens = tokenize(chunk_text)
    chunk_hits = [
        key for key in expected if any(tok in chunk_tokens for tok in tokenize(key))
    ]
    return {
        "chunk_hits": chunk_hits,
        "chunk_hit_at_k": 1.0 if expected and chunk_hits else 0.0,
    }


__all__ = [
    "collect_candidate_match_details",
    "collect_chunk_match_details",
    "tokenize",
]
