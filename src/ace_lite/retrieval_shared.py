"""Shared retrieval helpers for plan_quick and the index stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.index_cache import build_or_refresh_index
from ace_lite.index_stage.terms import extract_terms
from ace_lite.rankers import (
    rank_candidates_bm25_two_stage,
    rank_candidates_heuristic,
    rank_candidates_hybrid_re2,
)
from ace_lite.scoring_config import CANDIDATE_RANKER_CHOICES
from ace_lite.utils import normalize_choice


@dataclass(frozen=True, slots=True)
class CandidateSelectionResult:
    """Deterministic result of the first-pass candidate selection."""

    requested_ranker: str
    selected_ranker: str
    min_score_used: int
    fallback_reasons: list[str]
    candidates: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class RetrievalIndexSnapshot:
    """Shared normalized index snapshot for retrieval entrypoints."""

    index_payload: dict[str, Any]
    cache_info: dict[str, Any]
    files_map: dict[str, dict[str, Any]]
    corpus_size: int
    index_hash: str


@dataclass(frozen=True, slots=True)
class RetrievalRuntimeProfile:
    """Shared retrieval runtime controls for quick and full retrieval paths."""

    candidate_ranker: str
    min_candidate_score: int
    top_k_files: int
    hybrid_fusion_mode: str
    hybrid_rrf_k: int
    hybrid_weights: dict[str, float]
    index_hash: str | None
    allow_empty_terms_fail_open: bool = True

    def selection_kwargs(self, *, corpus_size: int) -> dict[str, Any]:
        return {
            "candidate_ranker": self.candidate_ranker,
            "min_candidate_score": int(self.min_candidate_score),
            "top_k_files": int(self.top_k_files),
            "corpus_size": int(corpus_size),
            "hybrid_fusion_mode": self.hybrid_fusion_mode,
            "hybrid_rrf_k": int(self.hybrid_rrf_k),
            "hybrid_weights": dict(self.hybrid_weights),
            "index_hash": self.index_hash,
            "allow_empty_terms_fail_open": bool(self.allow_empty_terms_fail_open),
        }

    def rank_candidates(
        self,
        *,
        files_map: Any,
        terms: list[str],
        min_score: int | None = None,
        candidate_ranker: str | None = None,
    ) -> list[dict[str, Any]]:
        return rank_candidate_files(
            files_map=files_map,
            terms=terms,
            candidate_ranker=str(candidate_ranker or self.candidate_ranker),
            min_score=(
                int(self.min_candidate_score)
                if min_score is None
                else max(1, int(min_score))
            ),
            top_k_files=int(self.top_k_files),
            hybrid_fusion_mode=self.hybrid_fusion_mode,
            hybrid_rrf_k=int(self.hybrid_rrf_k),
            hybrid_weights=dict(self.hybrid_weights),
            index_hash=self.index_hash,
        )


def extract_retrieval_terms(
    *,
    query: str,
    memory_stage: dict[str, Any] | None = None,
) -> list[str]:
    normalized_memory_stage = memory_stage if isinstance(memory_stage, dict) else {}
    return extract_terms(query=query, memory_stage=normalized_memory_stage)


def normalize_candidate_ranker(candidate_ranker: str) -> str:
    return normalize_choice(
        str(candidate_ranker or ""),
        CANDIDATE_RANKER_CHOICES,
        default="heuristic",
    )


def _normalize_hybrid_weights(
    hybrid_weights: dict[str, float] | None,
) -> dict[str, float]:
    if not isinstance(hybrid_weights, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, value in hybrid_weights.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        try:
            normalized[normalized_key] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


def build_retrieval_runtime_profile(
    *,
    candidate_ranker: str,
    min_candidate_score: int = 1,
    top_k_files: int = 8,
    hybrid_fusion_mode: str = "linear",
    hybrid_rrf_k: int = 60,
    hybrid_weights: dict[str, float] | None = None,
    index_hash: str | None = None,
    allow_empty_terms_fail_open: bool = True,
) -> RetrievalRuntimeProfile:
    """Build the canonical retrieval runtime profile shared by retrieval entrypoints."""

    normalized_fusion_mode = str(hybrid_fusion_mode or "").strip().lower() or "linear"
    normalized_index_hash = None if index_hash is None else str(index_hash)
    return RetrievalRuntimeProfile(
        candidate_ranker=normalize_candidate_ranker(candidate_ranker),
        min_candidate_score=max(1, int(min_candidate_score)),
        top_k_files=max(1, int(top_k_files)),
        hybrid_fusion_mode=normalized_fusion_mode,
        hybrid_rrf_k=max(1, int(hybrid_rrf_k)),
        hybrid_weights=_normalize_hybrid_weights(hybrid_weights),
        index_hash=normalized_index_hash,
        allow_empty_terms_fail_open=bool(allow_empty_terms_fail_open),
    )


def _normalize_selected_fusion_mode(
    *,
    selected_ranker: str,
    fusion_mode: str | None,
) -> str:
    normalized_ranker = str(selected_ranker or "").strip().lower()
    if normalized_ranker == "rrf_hybrid":
        return "rrf"
    if normalized_ranker == "hybrid_re2":
        normalized_mode = str(fusion_mode or "").strip().lower()
        return normalized_mode or "linear"
    return "linear"


def build_selection_observability(
    *,
    requested_ranker: str,
    selected_ranker: str,
    fallback_reasons: list[str],
    min_score_used: int,
    corpus_size: int | None = None,
    terms_count: int | None = None,
    fusion_mode: str | None = None,
    rrf_k: int | None = None,
) -> dict[str, Any]:
    """Build the canonical retrieval-selection observability payload."""

    payload: dict[str, Any] = {
        "requested": str(requested_ranker or ""),
        "selected": str(selected_ranker or ""),
        "fallbacks": [str(item) for item in fallback_reasons if str(item or "")],
        "min_score_used": int(min_score_used),
    }
    if corpus_size is not None:
        payload["corpus_size"] = int(corpus_size)
    if terms_count is not None:
        payload["terms_count"] = int(terms_count)
    if fusion_mode is not None or rrf_k is not None:
        payload["fusion_mode"] = _normalize_selected_fusion_mode(
            selected_ranker=selected_ranker,
            fusion_mode=fusion_mode,
        )
    if rrf_k is not None:
        payload["rrf_k"] = int(rrf_k)
    return payload


def build_guarded_rollout_payload(
    *,
    rollout_decision: dict[str, Any] | None = None,
    enabled: bool = False,
) -> dict[str, Any]:
    """Build the guarded-rollout scaffold without changing execution behavior."""

    decision_payload = (
        rollout_decision if isinstance(rollout_decision, dict) else {}
    )
    eligible = bool(decision_payload.get("eligible_for_guarded_rollout", False))
    rollout_enabled = bool(enabled)
    active = bool(rollout_enabled and eligible)
    source_reason = str(decision_payload.get("reason", "")).strip()
    shadow_arm_id = str(decision_payload.get("shadow_arm_id", "")).strip()
    decision = "apply_guarded_rollout" if active else "stay_report_only"
    reason = "guarded_rollout_active" if active else "guarded_rollout_disabled"
    return {
        "enabled": rollout_enabled,
        "eligible": eligible,
        "active": active,
        "decision": decision,
        "reason": reason,
        "source_reason": source_reason,
        "shadow_arm_id": shadow_arm_id,
    }


def rank_candidate_files(
    *,
    files_map: Any,
    terms: list[str],
    candidate_ranker: str,
    min_score: int = 1,
    top_k_files: int = 8,
    hybrid_fusion_mode: str = "linear",
    hybrid_rrf_k: int = 60,
    hybrid_weights: dict[str, float] | None = None,
    index_hash: str | None = None,
) -> list[dict[str, Any]]:
    strategy = normalize_candidate_ranker(candidate_ranker)
    candidate_limit = max(1, int(top_k_files))
    threshold = int(min_score)
    if strategy == "bm25_lite":
        return rank_candidates_bm25_two_stage(
            files_map,
            terms,
            min_score=threshold,
            top_k_files=candidate_limit,
            heuristic_ranker=rank_candidates_heuristic,
            index_hash=index_hash,
        )
    if strategy in {"hybrid_re2", "rrf_hybrid"}:
        return rank_candidates_hybrid_re2(
            files_map,
            terms,
            min_score=threshold,
            top_n=candidate_limit,
            fusion_mode="rrf" if strategy == "rrf_hybrid" else hybrid_fusion_mode,
            rrf_k=int(hybrid_rrf_k),
            weights=hybrid_weights,
            index_hash=index_hash,
        )
    return rank_candidates_heuristic(files_map, terms, min_score=threshold)


def _compute_index_hash(
    *,
    index_payload: dict[str, Any],
    files_map: dict[str, dict[str, Any]],
) -> str:
    import hashlib
    import json

    digest = hashlib.sha256()
    digest.update(
        str(index_payload.get("git_head_sha", "")).encode("utf-8", "ignore")
    )
    digest.update(str(index_payload.get("file_count", 0)).encode("utf-8", "ignore"))
    digest.update(
        json.dumps(
            list(index_payload.get("languages_covered", [])),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", "ignore")
    )

    for path in sorted(item for item in files_map if isinstance(item, str)):
        entry = files_map.get(path, {})
        if not isinstance(entry, dict):
            continue
        digest.update(path.encode("utf-8", "ignore"))
        digest.update(str(entry.get("sha256", "")).encode("utf-8", "ignore"))
        digest.update(b"|")
    return digest.hexdigest()


def load_retrieval_index_snapshot(
    *,
    root_dir: str,
    cache_path: str,
    languages: list[str],
    incremental: bool,
    fail_open: bool = False,
    include_index_hash: bool = True,
) -> RetrievalIndexSnapshot:
    """Load and normalize index/cache state for quick and full retrieval paths."""

    try:
        index_payload, cache_info = build_or_refresh_index(
            root_dir=root_dir,
            cache_path=cache_path,
            languages=languages,
            incremental=incremental,
        )
    except ValueError:
        if not fail_open:
            raise
        index_payload = {
            "files": {},
            "file_count": 0,
            "indexed_at": None,
            "languages_covered": [],
            "parser": {},
        }
        cache_info = {"cache_hit": False, "mode": "error", "changed_files": 0}

    files_map_raw = index_payload.get("files", {})
    files_map = files_map_raw if isinstance(files_map_raw, dict) else {}
    corpus_size = sum(
        1
        for path, entry in files_map.items()
        if isinstance(path, str) and isinstance(entry, dict)
    )
    index_hash = (
        _compute_index_hash(index_payload=index_payload, files_map=files_map)
        if bool(include_index_hash)
        else ""
    )
    return RetrievalIndexSnapshot(
        index_payload=index_payload,
        cache_info=cache_info if isinstance(cache_info, dict) else {},
        files_map=files_map,
        corpus_size=corpus_size,
        index_hash=index_hash,
    )


def select_initial_candidates(
    *,
    files_map: dict[str, Any],
    terms: list[str],
    candidate_ranker: str,
    min_candidate_score: int,
    top_k_files: int,
    corpus_size: int,
    hybrid_fusion_mode: str,
    hybrid_rrf_k: int,
    hybrid_weights: dict[str, float],
    index_hash: str | None,
    allow_empty_terms_fail_open: bool = True,
) -> CandidateSelectionResult:
    """Select initial candidates while preserving deterministic fail-open behavior."""

    requested_ranker = normalize_candidate_ranker(candidate_ranker)
    selected_ranker = requested_ranker
    fallback_reasons: list[str] = []

    if selected_ranker != "heuristic" and int(corpus_size) < 4:
        selected_ranker = "heuristic"
        fallback_reasons.append("tiny_corpus")

    def rank(*, ranker: str, min_score: int, ranked_terms: list[str]) -> list[dict[str, Any]]:
        return rank_candidate_files(
            files_map=files_map,
            terms=ranked_terms,
            candidate_ranker=ranker,
            min_score=min_score,
            top_k_files=int(top_k_files),
            hybrid_fusion_mode=hybrid_fusion_mode,
            hybrid_rrf_k=int(hybrid_rrf_k),
            hybrid_weights=hybrid_weights,
            index_hash=index_hash,
        )

    min_score_used = int(min_candidate_score)
    candidates = rank(
        ranker=selected_ranker,
        min_score=min_score_used,
        ranked_terms=terms,
    )
    if not candidates and int(min_candidate_score) > 1:
        min_score_used = 1
        candidates = rank(
            ranker=selected_ranker,
            min_score=min_score_used,
            ranked_terms=terms,
        )

    if not candidates and selected_ranker != "heuristic":
        selected_ranker = "heuristic"
        fallback_reasons.append("empty_retrieval")
        min_score_used = int(min_candidate_score)
        candidates = rank(
            ranker=selected_ranker,
            min_score=min_score_used,
            ranked_terms=terms,
        )
        if not candidates and int(min_candidate_score) > 1:
            min_score_used = 1
            candidates = rank(
                ranker=selected_ranker,
                min_score=min_score_used,
                ranked_terms=terms,
            )

    if not candidates and bool(allow_empty_terms_fail_open):
        min_score_used = 1
        candidates = rank(
            ranker="heuristic",
            min_score=min_score_used,
            ranked_terms=[],
        )

    return CandidateSelectionResult(
        requested_ranker=requested_ranker,
        selected_ranker=selected_ranker,
        min_score_used=min_score_used,
        fallback_reasons=fallback_reasons,
        candidates=candidates,
    )


__all__ = [
    "build_guarded_rollout_payload",
    "build_selection_observability",
    "build_retrieval_runtime_profile",
    "CandidateSelectionResult",
    "extract_retrieval_terms",
    "RetrievalIndexSnapshot",
    "RetrievalRuntimeProfile",
    "load_retrieval_index_snapshot",
    "normalize_candidate_ranker",
    "rank_candidate_files",
    "select_initial_candidates",
]
