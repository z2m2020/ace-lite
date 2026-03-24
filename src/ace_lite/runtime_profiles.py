from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


def _deep_merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        normalized_key = str(key)
        if isinstance(value, Mapping) and isinstance(target.get(normalized_key), dict):
            _deep_merge(target[normalized_key], value)
            continue
        if isinstance(value, Mapping):
            child: dict[str, Any] = {}
            _deep_merge(child, value)
            target[normalized_key] = child
            continue
        if isinstance(value, tuple):
            target[normalized_key] = list(value)
            continue
        if isinstance(value, list):
            target[normalized_key] = list(value)
            continue
        target[normalized_key] = value


def _copy_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    cloned: dict[str, Any] = {}
    _deep_merge(cloned, payload)
    return cloned


def _flatten_knobs(
    payload: Mapping[str, Any],
    *,
    prefix: tuple[str, ...] = (),
) -> tuple[str, ...]:
    paths: list[str] = []
    for key, value in payload.items():
        normalized_key = str(key)
        current = prefix + (normalized_key,)
        if isinstance(value, Mapping):
            paths.extend(_flatten_knobs(value, prefix=current))
            continue
        paths.append(".".join(current))
    return tuple(sorted(paths))


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    name: str
    summary: str
    retrieval: Mapping[str, Any]
    cache: Mapping[str, Any]
    budget: Mapping[str, Any]
    extras: Mapping[str, Any] | None = None

    def plan_overrides(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for section in (self.retrieval, self.cache, self.budget, self.extras or {}):
            _deep_merge(merged, section)
        return merged

    def knob_paths(self) -> dict[str, tuple[str, ...]]:
        return {
            "retrieval": _flatten_knobs(self.retrieval),
            "cache": _flatten_knobs(self.cache),
            "budget": _flatten_knobs(self.budget),
            "extras": _flatten_knobs(self.extras or {}),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "retrieval": _copy_mapping(self.retrieval),
            "cache": _copy_mapping(self.cache),
            "budget": _copy_mapping(self.budget),
            "extras": _copy_mapping(self.extras or {}),
            "knob_paths": {
                key: list(value)
                for key, value in self.knob_paths().items()
            },
            "plan_overrides": self.plan_overrides(),
        }


def _profile(
    *,
    name: str,
    summary: str,
    retrieval: Mapping[str, Any],
    cache: Mapping[str, Any],
    budget: Mapping[str, Any],
    extras: Mapping[str, Any] | None = None,
) -> RuntimeProfile:
    return RuntimeProfile(
        name=str(name).strip().lower(),
        summary=str(summary).strip(),
        retrieval=_copy_mapping(retrieval),
        cache=_copy_mapping(cache),
        budget=_copy_mapping(budget),
        extras=_copy_mapping(extras or {}),
    )


RUNTIME_PROFILES: tuple[RuntimeProfile, ...] = (
    _profile(
        name="bugfix",
        summary="Bias toward exact fault localization with bounded but rich debugging context.",
        retrieval={
            "retrieval_policy": "bugfix_test",
            "retrieval": {
                "candidate_ranker": "rrf_hybrid",
                "exact_search_enabled": True,
                "exact_search_time_budget_ms": 80,
                "exact_search_max_paths": 32,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": True,
                "ranking_profile": "graph_seeded",
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 900,
                    "max_entries": 48,
                }
            },
            "plan_replay_cache": {
                "enabled": True,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 10,
                "min_candidate_score": 2,
            },
            "repomap": {
                "top_k": 10,
                "neighbor_limit": 20,
                "budget_tokens": 900,
            },
            "chunk": {
                "top_k": 28,
                "per_file_limit": 4,
                "token_budget": 1500,
            },
        },
    ),
    _profile(
        name="refactor",
        summary="Spend more budget on structural context and graph-guided impact surfacing.",
        retrieval={
            "retrieval_policy": "refactor",
            "retrieval": {
                "candidate_ranker": "rrf_hybrid",
                "exact_search_enabled": False,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": True,
                "ranking_profile": "graph_seeded",
            },
            "cochange": {
                "enabled": True,
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 1800,
                    "max_entries": 96,
                }
            },
            "plan_replay_cache": {
                "enabled": True,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 14,
                "min_candidate_score": 2,
            },
            "repomap": {
                "top_k": 12,
                "neighbor_limit": 28,
                "budget_tokens": 1300,
            },
            "chunk": {
                "top_k": 32,
                "per_file_limit": 4,
                "token_budget": 1800,
            },
        },
    ),
    _profile(
        name="docs",
        summary="Prefer intent-aligned document retrieval with smaller context windows and lighter graph work.",
        retrieval={
            "retrieval_policy": "doc_intent",
            "retrieval": {
                "candidate_ranker": "bm25_lite",
                "exact_search_enabled": True,
                "exact_search_time_budget_ms": 35,
                "exact_search_max_paths": 16,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": False,
                "ranking_profile": "heuristic",
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 600,
                    "max_entries": 24,
                }
            },
            "plan_replay_cache": {
                "enabled": False,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 6,
                "min_candidate_score": 2,
            },
            "repomap": {
                "top_k": 0,
                "neighbor_limit": 0,
                "budget_tokens": 0,
            },
            "chunk": {
                "top_k": 16,
                "per_file_limit": 2,
                "token_budget": 800,
            },
        },
    ),
    _profile(
        name="colbert_experiment",
        summary="Enable report-only hash_colbert semantic rerank for controlled benchmark experiments without changing default runtime behavior.",
        retrieval={
            "retrieval_policy": "general",
            "retrieval": {
                "candidate_ranker": "rrf_hybrid",
                "exact_search_enabled": False,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": True,
                "ranking_profile": "graph",
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 1800,
                    "max_entries": 64,
                }
            },
            "plan_replay_cache": {
                "enabled": True,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 8,
                "min_candidate_score": 2,
            },
            "repomap": {
                "top_k": 6,
                "neighbor_limit": 12,
                "budget_tokens": 480,
            },
            "chunk": {
                "top_k": 20,
                "per_file_limit": 3,
                "token_budget": 1100,
            },
        },
        extras={
            "embeddings": {
                "enabled": True,
                "provider": "hash_colbert",
                "model": "hash-colbert-v1",
                "fail_open": True,
                "rerank_pool": 24,
            }
        },
    ),
    _profile(
        name="benchmark",
        summary="Reduce variance by using deterministic retrieval and disabling replay-style caches.",
        retrieval={
            "retrieval_policy": "general",
            "retrieval": {
                "candidate_ranker": "heuristic",
                "exact_search_enabled": False,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": False,
                "ranking_profile": "heuristic",
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": False,
                    "ttl_seconds": 0,
                    "max_entries": 0,
                }
            },
            "plan_replay_cache": {
                "enabled": False,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 8,
                "min_candidate_score": 2,
            },
            "repomap": {
                "top_k": 0,
                "neighbor_limit": 0,
                "budget_tokens": 0,
            },
            "chunk": {
                "top_k": 20,
                "per_file_limit": 3,
                "token_budget": 1000,
            },
        },
        extras={
            "plugins": {
                "enabled": False,
            }
        },
    ),
    _profile(
        name="wide_search",
        summary="Broaden candidate exploration and graph context for ambiguous or cross-cutting tasks.",
        retrieval={
            "retrieval_policy": "feature",
            "retrieval": {
                "candidate_ranker": "rrf_hybrid",
                "exact_search_enabled": True,
                "exact_search_time_budget_ms": 120,
                "exact_search_max_paths": 48,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": True,
                "ranking_profile": "graph_seeded",
            },
            "adaptive_router": {
                "enabled": True,
                "mode": "observe",
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 1800,
                    "max_entries": 128,
                }
            },
            "plan_replay_cache": {
                "enabled": True,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 18,
                "min_candidate_score": 1,
            },
            "repomap": {
                "top_k": 16,
                "neighbor_limit": 32,
                "budget_tokens": 1800,
            },
            "chunk": {
                "top_k": 40,
                "per_file_limit": 4,
                "token_budget": 2400,
            },
        },
    ),
    _profile(
        name="fast_path",
        summary="Favor low-latency planning with small budgets while keeping high-value caches warm.",
        retrieval={
            "retrieval_policy": "general",
            "retrieval": {
                "candidate_ranker": "heuristic",
                "exact_search_enabled": False,
                "deterministic_refine_enabled": True,
            },
            "repomap": {
                "enabled": True,
                "ranking_profile": "graph",
            },
        },
        cache={
            "memory": {
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 1800,
                    "max_entries": 64,
                }
            },
            "plan_replay_cache": {
                "enabled": True,
            },
        },
        budget={
            "retrieval": {
                "top_k_files": 5,
                "min_candidate_score": 3,
            },
            "repomap": {
                "top_k": 4,
                "neighbor_limit": 10,
                "budget_tokens": 320,
            },
            "chunk": {
                "top_k": 12,
                "per_file_limit": 2,
                "token_budget": 700,
            },
        },
    ),
)

RUNTIME_PROFILE_NAMES: tuple[str, ...] = tuple(
    profile.name for profile in RUNTIME_PROFILES
)
RUNTIME_PROFILE_CATALOG: dict[str, RuntimeProfile] = {
    profile.name: profile for profile in RUNTIME_PROFILES
}


def get_runtime_profile(name: str | None) -> RuntimeProfile | None:
    normalized = str(name or "").strip().lower()
    if not normalized:
        return None
    return RUNTIME_PROFILE_CATALOG.get(normalized)


def list_runtime_profiles() -> tuple[RuntimeProfile, ...]:
    return RUNTIME_PROFILES


__all__ = [
    "RUNTIME_PROFILE_CATALOG",
    "RUNTIME_PROFILE_NAMES",
    "RUNTIME_PROFILES",
    "RuntimeProfile",
    "get_runtime_profile",
    "list_runtime_profiles",
]
