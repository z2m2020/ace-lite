"""Exact-search candidate boost helpers for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

RunExactSearchFn = Callable[..., Any]
ScoreExactSearchHitsFn = Callable[[dict[str, int]], dict[str, float]]


@dataclass(slots=True)
class ExactSearchBoostResult:
    candidates: list[dict[str, Any]]
    payload: dict[str, Any]


def build_exact_search_payload(*, time_budget_ms: int, max_paths: int) -> dict[str, Any]:
    return {
        "enabled": False,
        "backend": "ripgrep",
        "reason": "disabled",
        "applied": False,
        "time_budget_ms": int(time_budget_ms),
        "max_paths": int(max_paths),
        "include_globs": [],
        "hit_paths": 0,
        "eligible_paths": 0,
        "boosted_count": 0,
        "injected_count": 0,
        "elapsed_ms": 0.0,
        "timed_out": False,
        "returncode": 0,
        "stderr": "",
    }


def apply_exact_search_boost(
    *,
    root: str,
    query: str,
    files_map: dict[str, Any],
    candidates: list[dict[str, Any]],
    include_globs: list[str],
    time_budget_ms: int,
    max_paths: int,
    run_exact_search: RunExactSearchFn,
    score_exact_hits: ScoreExactSearchHitsFn,
) -> ExactSearchBoostResult:
    """Apply exact-search boosts while keeping payload structure stable."""

    payload = build_exact_search_payload(
        time_budget_ms=int(time_budget_ms),
        max_paths=int(max_paths),
    )
    payload["enabled"] = True
    payload["reason"] = "pending"
    payload["include_globs"] = list(include_globs)
    boosted_candidates = [dict(item) for item in candidates]

    try:
        result = run_exact_search(
            root=root,
            query=query,
            include_globs=list(include_globs),
            timeout_ms=int(time_budget_ms),
        )
        payload.update(result.to_payload())
        payload["time_budget_ms"] = int(time_budget_ms)
        payload["max_paths"] = int(max_paths)
        payload["include_globs"] = list(include_globs)

        eligible_hits = {
            path: int(hits)
            for path, hits in result.hits_by_path.items()
            if path in files_map and int(hits) > 0
        }
        payload["eligible_paths"] = len(eligible_hits)
        if not eligible_hits:
            return ExactSearchBoostResult(candidates=boosted_candidates, payload=payload)

        limited_hits_items = sorted(
            eligible_hits.items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[: int(max_paths)]
        scored_hits = score_exact_hits(hits_by_path=dict(limited_hits_items))

        candidates_by_path: dict[str, dict[str, Any]] = {
            str(item.get("path") or ""): item
            for item in boosted_candidates
            if str(item.get("path") or "")
        }
        max_score = max(
            (float(item.get("score") or 0.0) for item in candidates_by_path.values()),
            default=0.0,
        )
        boost_cap = max(1.0, max_score * 0.35)
        injection_base = max(0.0, max_score * 0.15)
        boosted_count = 0
        injected_count = 0

        for path, strength in sorted(
            scored_hits.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        ):
            normalized_path = str(path or "").strip().replace("\\", "/")
            if not normalized_path or normalized_path not in files_map:
                continue
            boost = float(strength) * boost_cap
            existing = candidates_by_path.get(normalized_path)
            if existing is not None:
                existing["score"] = round(float(existing.get("score") or 0.0) + boost, 6)
                breakdown = existing.get("score_breakdown")
                if not isinstance(breakdown, dict):
                    breakdown = {}
                    existing["score_breakdown"] = breakdown
                breakdown["exact_search"] = round(boost, 6)
                boosted_count += 1
                continue

            entry = files_map.get(normalized_path, {})
            symbols = entry.get("symbols", [])
            imports = entry.get("imports", [])
            score_value = round(injection_base + boost, 6)
            injected = {
                "path": normalized_path,
                "module": str(entry.get("module", "")),
                "language": str(entry.get("language", "")),
                "score": score_value,
                "symbol_count": len(symbols) if isinstance(symbols, list) else 0,
                "import_count": len(imports) if isinstance(imports, list) else 0,
                "score_breakdown": {"exact_search": score_value},
            }
            boosted_candidates.append(injected)
            candidates_by_path[normalized_path] = injected
            injected_count += 1

        if boosted_count or injected_count:
            boosted_candidates.sort(
                key=lambda item: (
                    -float(item.get("score") or 0.0),
                    str(item.get("path") or ""),
                )
            )
            payload["applied"] = True
            payload["boost_cap"] = round(boost_cap, 6)
            payload["injection_base"] = round(injection_base, 6)
            payload["boosted_count"] = int(boosted_count)
            payload["injected_count"] = int(injected_count)
            payload["reason"] = "applied"
    except Exception as exc:
        payload["reason"] = f"error:{exc.__class__.__name__}"
        payload["warning"] = str(exc)[:240]

    return ExactSearchBoostResult(candidates=boosted_candidates, payload=payload)


__all__ = [
    "ExactSearchBoostResult",
    "apply_exact_search_boost",
    "build_exact_search_payload",
]
