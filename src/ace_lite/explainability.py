"""Compact retrieval explainability helpers."""

from __future__ import annotations

from typing import Any

_SIGNAL_ORDER: tuple[str, ...] = (
    "file",
    "path",
    "module",
    "symbol",
    "import",
    "signature",
    "reference",
    "lexical",
    "exact",
    "docs",
    "worktree",
    "priors",
    "graph",
    "semantic",
    "feedback",
    "cochange",
    "candidate",
    "tests",
    "fusion",
)

_SIGNAL_RANK = {token: index for index, token in enumerate(_SIGNAL_ORDER)}

_BREAKDOWN_SIGNAL_MAP: dict[str, tuple[str, ...]] = {
    "file_prior": ("file",),
    "path": ("path",),
    "path_prior": ("path",),
    "module": ("module",),
    "symbol": ("symbol",),
    "import": ("import",),
    "signature": ("signature",),
    "reference": ("reference",),
    "content": ("lexical",),
    "bm25": ("lexical",),
    "bm25_norm": ("lexical",),
    "heuristic_norm": ("lexical",),
    "rrf_norm": ("lexical",),
    "re2_coverage": ("lexical",),
    "exact_search": ("exact",),
    "docs_hint_injection": ("docs",),
    "worktree_seed_injection": ("worktree",),
    "prior_docs_worktree": ("priors",),
    "scip": ("graph",),
    "scip_pagerank": ("graph",),
    "scip_centrality": ("graph",),
    "graph_lookup": ("graph",),
    "graph_prior": ("graph",),
    "graph_closure_bonus": ("graph",),
    "prior_feedback": ("feedback",),
    "cochange": ("cochange",),
    "candidate": ("candidate",),
    "test_signal": ("tests",),
    "rrf_multi_channel": ("fusion",),
}

_IGNORED_BREAKDOWN_KEYS: frozenset[str] = frozenset(
    {
        "matched_terms",
        "estimated_tokens",
        "diversity_penalty",
        "diversity_adjusted_score",
        "diversity_selected",
        "policy_chunk_weight",
        "graph_seeded",
        "graph_closure_seeded",
        "graph_closure_support_count",
        "graph_transfer_count",
        "fusion_mode",
        "rrf_k",
        "ranker",
    }
)


def _is_positive_signal(value: Any) -> bool:
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return float(value) > 0.0
    return False


def collect_selection_signals(item: dict[str, Any]) -> list[str]:
    """Return canonical signal tokens for a ranked file/chunk item."""
    if not isinstance(item, dict):
        return []

    signals: set[str] = set()
    breakdown = item.get("score_breakdown")
    if isinstance(breakdown, dict):
        for key, value in breakdown.items():
            normalized_key = str(key or "").strip()
            if not normalized_key or normalized_key in _IGNORED_BREAKDOWN_KEYS:
                continue
            if not _is_positive_signal(value):
                continue
            for token in _BREAKDOWN_SIGNAL_MAP.get(normalized_key, ()):
                if token:
                    signals.add(token)

    if _is_positive_signal(item.get("score_lexical")):
        signals.add("lexical")
    if _is_positive_signal(item.get("score_embedding")):
        signals.add("semantic")
    if _is_positive_signal(item.get("score_fused")) or _is_positive_signal(
        item.get("score_rrf_multi")
    ):
        signals.add("fusion")

    return sorted(signals, key=lambda token: (_SIGNAL_RANK.get(token, 999), token))


def build_selection_reason(
    item: dict[str, Any],
    *,
    default_reason: str,
) -> str:
    """Build a compact reason string from stable ranking signals."""
    signals = collect_selection_signals(item)
    if signals:
        return "signals:" + ",".join(signals)

    retrieval_pass = str(item.get("retrieval_pass") or "").strip()
    if retrieval_pass:
        return f"retrieval:{retrieval_pass}"

    existing = str(item.get("why") or "").strip()
    if existing:
        return existing
    return str(default_reason or "").strip() or "ranked_candidate"


def attach_selection_why(
    rows: list[dict[str, Any]],
    *,
    default_reason: str,
) -> list[dict[str, Any]]:
    """Return shallow-copied rows with a stable `why` field attached."""
    output: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        payload["why"] = build_selection_reason(
            item,
            default_reason=default_reason,
        )
        output.append(payload)
    return output


__all__ = [
    "attach_selection_why",
    "build_selection_reason",
    "collect_selection_signals",
]
