"""Deterministic prior signals for index-stage ranking."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ace_lite.index_cache import expand_changed_files_with_reverse_dependencies
from ace_lite.vcs_worktree import collect_git_worktree_summary

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_WORKTREE_SUMMARY_MIN_FILES = 48
_WORKTREE_GUARD_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "does",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "what",
        "when",
        "where",
        "why",
        "with",
        # Repo-path boilerplate segments that otherwise cause unrelated worktree
        # changes to pass overlap guards when query_terms include full paths.
        "src",
        "ace_lite",
        "tests",
        "scripts",
        "unit",
        "integration",
        "e2e",
    }
)


def collect_worktree_prior(
    *,
    root: str | Path,
    files_map: dict[str, dict[str, Any]],
    max_seed_paths: int,
) -> dict[str, Any]:
    payload = collect_git_worktree_summary(
        repo_root=root,
        max_files=max(_WORKTREE_SUMMARY_MIN_FILES, max(24, int(max_seed_paths) * 3)),
    )
    if not bool(payload.get("enabled", False)):
        return {
            "enabled": False,
            "reason": str(payload.get("reason", "disabled")),
            "changed_count": 0,
            "changed_paths": [],
            "seed_paths": [],
            "reverse_added_count": 0,
            "state_hash": _state_hash(changed_paths=[], seed_paths=[]),
            "raw": payload,
        }

    entries = payload.get("entries", [])
    changed_paths: list[str] = []
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized = _normalize_path(str(entry.get("path") or ""))
            if not normalized or normalized in changed_paths:
                continue
            changed_paths.append(normalized)

    expanded, reverse_added = expand_changed_files_with_reverse_dependencies(
        changed_files=changed_paths,
        index_files=files_map,
        max_depth=1,
        max_extra=max(0, int(max_seed_paths)),
    )
    seed_paths: list[str] = []
    for item in expanded:
        normalized = _normalize_path(item)
        if not normalized or normalized in seed_paths:
            continue
        if normalized in files_map:
            seed_paths.append(normalized)
        if len(seed_paths) >= max(1, int(max_seed_paths)):
            break

    return {
        "enabled": True,
        "reason": str(payload.get("reason", "ok")),
        "changed_count": int(payload.get("changed_count", 0) or 0),
        "changed_paths": changed_paths,
        "seed_paths": seed_paths,
        "reverse_added_count": int(reverse_added),
        "state_hash": _state_hash(changed_paths=changed_paths, seed_paths=seed_paths),
        "raw": payload,
    }


def apply_candidate_priors(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    docs_payload: dict[str, Any],
    worktree_prior: dict[str, Any],
    policy: dict[str, Any],
    top_k_files: int,
    query: str | None = None,
    query_terms: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [dict(item) for item in candidates if isinstance(item, dict)]
    if not rows:
        return rows, _empty_summary(docs_payload=docs_payload, worktree_prior=worktree_prior)

    query_tokens = _normalize_query_tokens(query_terms=query_terms or [])

    docs_hints = docs_payload.get("hints", {}) if isinstance(docs_payload.get("hints"), dict) else {}
    path_scores = _score_lookup(docs_hints.get("path_scores"))
    module_scores = _score_lookup(docs_hints.get("module_scores"))
    symbol_scores = _score_lookup(docs_hints.get("symbol_scores"))

    changed_paths_original = [
        _normalize_path(item)
        for item in worktree_prior.get("changed_paths", [])
        if _normalize_path(item)
    ]
    changed_paths = set(changed_paths_original)
    seed_paths = [
        _normalize_path(item)
        for item in worktree_prior.get("seed_paths", [])
        if _normalize_path(item)
    ]
    guard_payload = _apply_worktree_query_guard(
        changed_paths=changed_paths_original,
        seed_paths=seed_paths,
        files_map=files_map,
        policy=policy,
        query_terms=query_terms or [],
    )
    changed_paths = set(guard_payload["changed_paths"])
    seed_paths = list(guard_payload["seed_paths"])
    seed_set = set(seed_paths)
    reverse_only = seed_set - changed_paths

    docs_weight = max(0.0, float(policy.get("docs_weight", 0.0) or 0.0))
    docs_module_weight = max(
        0.0,
        float(policy.get("docs_module_weight", max(0.0, docs_weight * 0.45)) or 0.0),
    )
    docs_symbol_weight = max(
        0.0,
        float(policy.get("docs_symbol_weight", max(0.0, docs_weight * 0.35)) or 0.0),
    )
    docs_expand_candidates = bool(policy.get("docs_expand_candidates", False))
    docs_expand_limit = max(0, int(policy.get("docs_expand_limit", 0) or 0))
    docs_injection_min_overlap = max(
        0, int(policy.get("docs_injection_min_overlap", 0) or 0)
    )
    worktree_weight = max(0.0, float(policy.get("worktree_weight", 0.0) or 0.0))
    worktree_neighbor_weight = max(
        0.0,
        float(
            policy.get(
                "worktree_neighbor_weight",
                max(0.0, worktree_weight * 0.55),
            )
            or 0.0
        ),
    )
    worktree_expand_candidates = bool(policy.get("worktree_expand_candidates", True))
    expand_limit = max(
        0,
        int(
            policy.get(
                "worktree_expand_limit",
                max(2, min(10, int(top_k_files) * 2)),
            )
            or 0
        ),
    )

    boosted_count = 0
    boosted_paths: set[str] = set()
    max_score = max(float(item.get("score", 0.0) or 0.0) for item in rows)
    existing_paths = {
        _normalize_path(str(item.get("path") or ""))
        for item in rows
        if isinstance(item, dict) and _normalize_path(str(item.get("path") or ""))
    }

    for row in rows:
        path = _normalize_path(str(row.get("path") or ""))
        if not path:
            continue
        score_boost = 0.0

        if path in changed_paths:
            score_boost += worktree_weight
        elif path in reverse_only:
            score_boost += worktree_neighbor_weight

        docs_path_score = float(path_scores.get(path, 0.0) or 0.0)
        if docs_path_score > 0.0 and docs_weight > 0.0:
            score_boost += docs_weight * docs_path_score

        module = str(row.get("module") or "").strip()
        module_score = _match_module_score(module=module, module_scores=module_scores)
        if module_score > 0.0 and docs_module_weight > 0.0:
            score_boost += docs_module_weight * module_score

        symbol_score = _match_symbol_score(
            path=path,
            files_map=files_map,
            symbol_scores=symbol_scores,
        )
        if symbol_score > 0.0 and docs_symbol_weight > 0.0:
            score_boost += docs_symbol_weight * symbol_score

        if score_boost <= 0.0:
            continue

        row["score"] = round(float(row.get("score", 0.0) or 0.0) + score_boost, 6)
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        breakdown["prior_docs_worktree"] = round(
            float(breakdown.get("prior_docs_worktree", 0.0) or 0.0) + score_boost,
            6,
        )
        boosted_count += 1
        boosted_paths.add(path)

    docs_injected_count = 0
    if docs_expand_candidates and docs_expand_limit > 0 and files_map:
        injection_weights: dict[str, float] = {}

        hint_path_scores = docs_hints.get("path_scores", [])
        if isinstance(hint_path_scores, list) and docs_weight > 0.0:
            for row in hint_path_scores:
                if not isinstance(row, dict):
                    continue
                path = _normalize_path(str(row.get("value") or ""))
                if not path or path in existing_paths or path not in files_map:
                    continue
                if (
                    docs_injection_min_overlap > 0
                    and query_tokens
                    and _path_query_overlap(
                        path=path, files_map=files_map, query_tokens=query_tokens
                    )
                    < docs_injection_min_overlap
                ):
                    continue
                score = max(0.0, float(row.get("score", 0.0) or 0.0))
                if score <= 0.0:
                    continue
                weight = docs_weight * score
                injection_weights[path] = max(float(injection_weights.get(path, 0.0)), float(weight))

        hint_module_scores = docs_hints.get("module_scores", [])
        if isinstance(hint_module_scores, list) and docs_module_weight > 0.0:
            module_candidates: list[tuple[str, float]] = []
            for row in hint_module_scores:
                if not isinstance(row, dict):
                    continue
                module = str(row.get("value") or "").strip().strip(".")
                if not module:
                    continue
                score = max(0.0, float(row.get("score", 0.0) or 0.0))
                if score <= 0.0:
                    continue
                module_candidates.append((module, docs_module_weight * score))

            for module, weight in module_candidates:
                matches: list[str] = []
                for raw_path, entry in files_map.items():
                    if not isinstance(raw_path, str) or not isinstance(entry, dict):
                        continue
                    path = _normalize_path(raw_path)
                    if not path or path in existing_paths:
                        continue
                    entry_module = str(entry.get("module") or "").strip().strip(".")
                    if not entry_module:
                        continue
                    if (
                        entry_module == module
                        or entry_module.endswith(f".{module}")
                        or module.endswith(f".{entry_module}")
                    ):
                        if (
                            docs_injection_min_overlap > 0
                            and query_tokens
                            and _path_query_overlap(
                                path=path,
                                files_map=files_map,
                                query_tokens=query_tokens,
                            )
                            < docs_injection_min_overlap
                        ):
                            continue
                        matches.append(path)

                matches = sorted(set(matches))
                if not matches or len(matches) > 3:
                    continue
                for path in matches:
                    injection_weights[path] = max(
                        float(injection_weights.get(path, 0.0)),
                        float(weight),
                    )

        injection_candidates = [
            (weight, path)
            for path, weight in injection_weights.items()
            if weight > 0.0 and path not in existing_paths
        ]
        injection_candidates.sort(key=lambda item: (-float(item[0]), str(item[1])))
        docs_rank = 0
        for weight, path in injection_candidates:
            docs_rank += 1
            if docs_rank > docs_expand_limit:
                break
            injected_entry = files_map.get(path)
            if not isinstance(injected_entry, dict):
                continue
            base = max(max_score, 1.0) + float(docs_expand_limit - docs_rank + 1) * 1e-4
            synthetic_score = round(base + float(weight), 6)
            rows.append(
                {
                    "path": path,
                    "language": str(injected_entry.get("language") or ""),
                    "module": str(injected_entry.get("module") or ""),
                    "symbol_count": len(injected_entry.get("symbols", []))
                    if isinstance(injected_entry.get("symbols"), list)
                    else 0,
                    "import_count": len(injected_entry.get("imports", []))
                    if isinstance(injected_entry.get("imports"), list)
                    else 0,
                    "score": synthetic_score,
                    "score_breakdown": {
                        "docs_hint_injection": round(float(weight), 6),
                    },
                    "retrieval_pass": "docs_hint",
                }
            )
            existing_paths.add(path)
            docs_injected_count += 1

    added_count = 0
    if worktree_expand_candidates and expand_limit > 0 and files_map:
        synthetic_rank = 0
        for path in seed_paths:
            if not path or path in existing_paths:
                continue
            injected_entry = files_map.get(path)
            if not isinstance(injected_entry, dict):
                continue
            synthetic_rank += 1
            if synthetic_rank > expand_limit:
                break
            base = max(max_score, 1.0) + float(expand_limit - synthetic_rank + 1) * 1e-4
            worktree_score = worktree_weight if path in changed_paths else worktree_neighbor_weight
            synthetic_score = round(base + worktree_score, 6)
            rows.append(
                {
                    "path": path,
                    "language": str(injected_entry.get("language") or ""),
                    "module": str(injected_entry.get("module") or ""),
                    "symbol_count": len(injected_entry.get("symbols", []))
                    if isinstance(injected_entry.get("symbols"), list)
                    else 0,
                    "import_count": len(injected_entry.get("imports", []))
                    if isinstance(injected_entry.get("imports"), list)
                    else 0,
                    "score": synthetic_score,
                    "score_breakdown": {"worktree_seed_injection": round(worktree_score, 6)},
                    "retrieval_pass": "worktree_prior",
                }
            )
            existing_paths.add(path)
            added_count += 1

    policy_name = str(policy.get("name") or "").strip().lower()
    policy_source = str(policy.get("source") or "").strip().lower()

    tests_penalized_count = 0
    tests_penalty = max(0.0, float(policy.get("tests_path_penalty", 0.0) or 0.0))
    if (
        tests_penalty > 0.0
        and policy_source == "auto"
        and policy_name
        and policy_name != "bugfix_test"
        and not _raw_query_mentions_tests(raw_query=str(query or ""))
        and not _query_terms_mention_tests(query_terms=list(query_terms or []))
    ):
        for row in rows:
            path = _normalize_path(str(row.get("path") or ""))
            if not path or not path.startswith("tests/"):
                continue
            previous = float(row.get("score", 0.0) or 0.0)
            updated = max(0.0, previous - tests_penalty)
            if updated == previous:
                continue
            row["score"] = round(updated, 6)
            breakdown = row.get("score_breakdown")
            if not isinstance(breakdown, dict):
                breakdown = {}
                row["score_breakdown"] = breakdown
            breakdown["prior_tests_path_penalty"] = round(
                float(breakdown.get("prior_tests_path_penalty", 0.0) or 0.0)
                - tests_penalty,
                6,
            )
            tests_penalized_count += 1

    rankers_boosted_count = 0
    rankers_focus_boost = max(
        0.0, float(policy.get("rankers_focus_boost", 0.0) or 0.0)
    )
    if (
        rankers_focus_boost > 0.0
        and policy_source == "auto"
        and query_tokens
        and "candidate" in query_tokens
        and {"rank", "ranking", "ranked"} & query_tokens
    ):
        for row in rows:
            path = _normalize_path(str(row.get("path") or ""))
            if not path or "/rankers/" not in f"/{path}":
                continue
            previous = float(row.get("score", 0.0) or 0.0)
            row["score"] = round(previous + rankers_focus_boost, 6)
            breakdown = row.get("score_breakdown")
            if not isinstance(breakdown, dict):
                breakdown = {}
                row["score_breakdown"] = breakdown
            breakdown["prior_rankers_focus_boost"] = round(
                float(breakdown.get("prior_rankers_focus_boost", 0.0) or 0.0)
                + rankers_focus_boost,
                6,
            )
            rankers_boosted_count += 1

    rows.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("path") or ""),
        )
    )
    summary = _empty_summary(docs_payload=docs_payload, worktree_prior=worktree_prior)
    summary["boosted_candidate_count"] = boosted_count
    summary["docs_injected_candidate_count"] = docs_injected_count
    summary["added_candidate_count"] = added_count
    summary["boosted_unique_paths"] = len(boosted_paths)
    summary["worktree_expand_candidates"] = bool(worktree_expand_candidates)
    summary["docs_expand_candidates"] = bool(docs_expand_candidates)
    summary["docs_expand_limit"] = int(docs_expand_limit)
    summary["tests_path_penalty"] = float(tests_penalty)
    summary["tests_penalized_candidate_count"] = int(tests_penalized_count)
    summary["rankers_focus_boost"] = float(rankers_focus_boost)
    summary["rankers_focus_boosted_candidate_count"] = int(rankers_boosted_count)
    summary["worktree_guard_enabled"] = bool(guard_payload["enabled"])
    summary["worktree_guard_applied"] = bool(guard_payload["applied"])
    summary["worktree_guard_reason"] = str(guard_payload["reason"])
    summary["worktree_guard_min_overlap"] = int(guard_payload["min_overlap"])
    summary["worktree_guard_filtered_changed_count"] = int(guard_payload["filtered_changed_count"])
    summary["worktree_guard_filtered_seed_count"] = int(guard_payload["filtered_seed_count"])
    summary["worktree_effective_changed_paths"] = list(guard_payload["changed_paths"])
    summary["worktree_effective_seed_paths"] = list(guard_payload["seed_paths"])
    summary["worktree_effective_state_hash"] = str(
        _state_hash(
            changed_paths=list(guard_payload["changed_paths"]),
            seed_paths=list(guard_payload["seed_paths"]),
        )
    )
    return rows, summary


def _empty_summary(
    *,
    docs_payload: dict[str, Any],
    worktree_prior: dict[str, Any],
) -> dict[str, Any]:
    hints = docs_payload.get("hints", {}) if isinstance(docs_payload.get("hints"), dict) else {}
    return {
        "docs_enabled": bool(docs_payload.get("enabled", False)),
        "docs_section_count": int(docs_payload.get("section_count", 0) or 0),
        "docs_hint_paths": len(hints.get("paths", []))
        if isinstance(hints.get("paths"), list)
        else 0,
        "docs_hint_modules": len(hints.get("modules", []))
        if isinstance(hints.get("modules"), list)
        else 0,
        "docs_hint_symbols": len(hints.get("symbols", []))
        if isinstance(hints.get("symbols"), list)
        else 0,
        "worktree_enabled": bool(worktree_prior.get("enabled", False)),
        "worktree_changed_count": int(worktree_prior.get("changed_count", 0) or 0),
        "worktree_seed_count": len(worktree_prior.get("seed_paths", []))
        if isinstance(worktree_prior.get("seed_paths"), list)
        else 0,
        "worktree_reverse_added_count": int(worktree_prior.get("reverse_added_count", 0) or 0),
        "boosted_candidate_count": 0,
        "docs_injected_candidate_count": 0,
        "added_candidate_count": 0,
        "boosted_unique_paths": 0,
        "worktree_expand_candidates": False,
        "docs_expand_candidates": False,
        "docs_expand_limit": 0,
        "tests_path_penalty": 0.0,
        "tests_penalized_candidate_count": 0,
        "rankers_focus_boost": 0.0,
        "rankers_focus_boosted_candidate_count": 0,
        "worktree_guard_enabled": False,
        "worktree_guard_applied": False,
        "worktree_guard_reason": "disabled",
        "worktree_guard_min_overlap": 0,
        "worktree_guard_filtered_changed_count": 0,
        "worktree_guard_filtered_seed_count": 0,
        "worktree_effective_changed_paths": [
            _normalize_path(item)
            for item in worktree_prior.get("changed_paths", [])
            if _normalize_path(item)
        ]
        if isinstance(worktree_prior.get("changed_paths"), list)
        else [],
        "worktree_effective_seed_paths": [
            _normalize_path(item)
            for item in worktree_prior.get("seed_paths", [])
            if _normalize_path(item)
        ]
        if isinstance(worktree_prior.get("seed_paths"), list)
        else [],
        "worktree_effective_state_hash": _state_hash(
            changed_paths=[
                _normalize_path(item)
                for item in worktree_prior.get("changed_paths", [])
                if _normalize_path(item)
            ]
            if isinstance(worktree_prior.get("changed_paths"), list)
            else [],
            seed_paths=[
                _normalize_path(item)
                for item in worktree_prior.get("seed_paths", [])
                if _normalize_path(item)
            ]
            if isinstance(worktree_prior.get("seed_paths"), list)
            else [],
        ),
    }


def _apply_worktree_query_guard(
    *,
    changed_paths: list[str],
    seed_paths: list[str],
    files_map: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    query_terms: list[str],
) -> dict[str, Any]:
    guard_enabled = bool(policy.get("worktree_query_guard_enabled", False))
    min_overlap = max(1, int(policy.get("worktree_query_guard_min_overlap", 1) or 1))
    if not guard_enabled:
        return {
            "enabled": False,
            "applied": False,
            "reason": "disabled",
            "min_overlap": min_overlap,
            "filtered_changed_count": 0,
            "filtered_seed_count": 0,
            "changed_paths": list(changed_paths),
            "seed_paths": list(seed_paths),
        }

    query_tokens = _normalize_query_tokens(query_terms=query_terms)
    if not query_tokens:
        return {
            "enabled": True,
            "applied": False,
            "reason": "empty_query_tokens",
            "min_overlap": min_overlap,
            "filtered_changed_count": 0,
            "filtered_seed_count": 0,
            "changed_paths": list(changed_paths),
            "seed_paths": list(seed_paths),
        }

    filtered_changed: list[str] = []
    for path in changed_paths:
        if _path_query_overlap(path=path, files_map=files_map, query_tokens=query_tokens) >= min_overlap:
            filtered_changed.append(path)

    reason = "ok"
    if not filtered_changed and changed_paths:
        # Keep one deterministic fallback to preserve local-change sensitivity.
        filtered_changed = [changed_paths[0]]
        reason = "fallback_first_changed"

    filtered_seed: list[str] = []
    changed_set = set(filtered_changed)
    for path in seed_paths:
        if path in changed_set:
            filtered_seed.append(path)
            continue
        if _path_query_overlap(path=path, files_map=files_map, query_tokens=query_tokens) >= min_overlap:
            filtered_seed.append(path)

    if not filtered_seed:
        filtered_seed = list(filtered_changed)

    return {
        "enabled": True,
        "applied": True,
        "reason": reason,
        "min_overlap": min_overlap,
        "filtered_changed_count": max(0, len(changed_paths) - len(filtered_changed)),
        "filtered_seed_count": max(0, len(seed_paths) - len(filtered_seed)),
        "changed_paths": filtered_changed,
        "seed_paths": filtered_seed,
    }


def _normalize_query_tokens(*, query_terms: list[str]) -> set[str]:
    tokens: set[str] = set()
    for raw in query_terms:
        for token in _TOKEN_RE.findall(str(raw or "").lower()):
            if len(token) < 3 or token in _WORKTREE_GUARD_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _raw_query_mentions_tests(*, raw_query: str) -> bool:
    tokens = _TOKEN_RE.findall(str(raw_query or "").lower())
    for token in tokens:
        if token in {"test", "tests", "pytest", "unittest"}:
            return True
        if token.startswith("test"):
            return True
    return False


def _query_terms_mention_tests(*, query_terms: list[str]) -> bool:
    for raw in query_terms:
        tokens = _TOKEN_RE.findall(str(raw or "").lower())
        for token in tokens:
            if token in {"test", "tests", "pytest", "unittest"}:
                return True
            if token.startswith("test"):
                return True
    return False


def _path_query_overlap(
    *,
    path: str,
    files_map: dict[str, dict[str, Any]],
    query_tokens: set[str],
) -> int:
    if not query_tokens:
        return 0
    entry = files_map.get(path, {})
    module = str(entry.get("module") or "") if isinstance(entry, dict) else ""
    blob = f"{path} {module}"
    signal_tokens = {
        token
        for token in _TOKEN_RE.findall(blob.lower())
        if len(token) >= 3 and token not in _WORKTREE_GUARD_STOPWORDS
    }
    if not signal_tokens:
        return 0
    return len(signal_tokens & query_tokens)


def _score_lookup(raw_rows: Any) -> dict[str, float]:
    if not isinstance(raw_rows, list):
        return {}
    lookup: dict[str, float] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        score = max(0.0, float(row.get("score", 0.0) or 0.0))
        key = _normalize_path(value)
        if not key:
            key = value
        if score > float(lookup.get(key, 0.0)):
            lookup[key] = score
    return lookup


def _match_module_score(*, module: str, module_scores: dict[str, float]) -> float:
    normalized = str(module or "").strip().strip(".")
    if not normalized:
        return 0.0
    direct = float(module_scores.get(normalized, 0.0) or 0.0)
    if direct > 0.0:
        return direct
    best = 0.0
    for candidate, score in module_scores.items():
        if normalized.endswith(candidate) or candidate.endswith(normalized):
            best = max(best, float(score))
    return best


def _match_symbol_score(
    *,
    path: str,
    files_map: dict[str, dict[str, Any]],
    symbol_scores: dict[str, float],
) -> float:
    entry = files_map.get(path)
    if not isinstance(entry, dict):
        return 0.0
    symbols = entry.get("symbols", [])
    if not isinstance(symbols, list):
        return 0.0
    best = 0.0
    for symbol in symbols:
        if not isinstance(symbol, dict):
            continue
        for candidate in (
            str(symbol.get("name") or "").strip(),
            str(symbol.get("qualified_name") or "").strip(),
        ):
            if not candidate:
                continue
            direct = float(symbol_scores.get(candidate, 0.0) or 0.0)
            if direct > best:
                best = direct
    return best


def _state_hash(*, changed_paths: list[str], seed_paths: list[str]) -> str:
    payload = {
        "changed_paths": [item for item in changed_paths if item],
        "seed_paths": [item for item in seed_paths if item],
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _normalize_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


__all__ = ["apply_candidate_priors", "collect_worktree_prior"]
