"""Local user profile storage for deterministic memory enrichment."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.token_estimator import estimate_tokens


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_iso_timestamp(value: Any) -> float:
    if not isinstance(value, str):
        return 0.0
    normalized = str(value).strip()
    if not normalized:
        return 0.0
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return float(datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return 0.0


def _normalize_tokens(value: str) -> tuple[str, ...]:
    normalized = _normalize_text(value).lower()
    if not normalized:
        return ()
    pieces = [
        token
        for token in re.split(r"[^a-z0-9_]+", normalized)
        if token
    ]
    return tuple(dict.fromkeys(pieces))


def _clamp_score(value: Any, *, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    return max(0.0, min(1.0, parsed))


def _coerce_non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(0, parsed)


class ProfileStore:
    """JSON-backed profile storage with deterministic ordering and eviction."""

    def __init__(
        self,
        *,
        path: str | Path = "~/.ace-lite/profile.json",
        max_facts: int = 128,
        max_recent_contexts: int = 64,
        dedupe_token_overlap_threshold: float = 0.85,
        expiry_enabled: bool = True,
        ttl_days: int = 90,
        max_age_days: int = 365,
    ) -> None:
        self._path = Path(path).expanduser()
        self._max_facts = max(1, int(max_facts))
        self._max_recent_contexts = max(1, int(max_recent_contexts))
        self._dedupe_token_overlap_threshold = max(
            0.0, min(1.0, float(dedupe_token_overlap_threshold))
        )
        self._expiry_enabled = bool(expiry_enabled)
        self._ttl_days = max(1, int(ttl_days))
        self._max_age_days = max(1, int(max_age_days))

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        normalized = self._load_raw_payload()
        normalized, expiry_stats = self._apply_expiry_policy(
            payload=normalized,
            expiry_enabled=self._expiry_enabled,
            ttl_days=self._ttl_days,
            max_age_days=self._max_age_days,
        )
        if (
            self._path.exists()
            and (
                int(expiry_stats.get("removed_facts", 0) or 0) > 0
                or int(expiry_stats.get("removed_recent_contexts", 0) or 0) > 0
            )
        ):
            self._write_payload(normalized)
        return normalized

    def save(self, payload: dict[str, Any]) -> None:
        normalized = self._build_normalized_payload(payload)
        normalized, _ = self._apply_expiry_policy(
            payload=normalized,
            expiry_enabled=self._expiry_enabled,
            ttl_days=self._ttl_days,
            max_age_days=self._max_age_days,
        )
        self._write_payload(normalized)

    def vacuum(
        self,
        *,
        expiry_enabled: bool | None = None,
        ttl_days: int | None = None,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        normalized = self._load_raw_payload()
        applied_expiry_enabled = (
            self._expiry_enabled if expiry_enabled is None else bool(expiry_enabled)
        )
        applied_ttl_days = (
            self._ttl_days if ttl_days is None else max(1, int(ttl_days))
        )
        applied_max_age_days = (
            self._max_age_days if max_age_days is None else max(1, int(max_age_days))
        )
        pruned, stats = self._apply_expiry_policy(
            payload=normalized,
            expiry_enabled=applied_expiry_enabled,
            ttl_days=applied_ttl_days,
            max_age_days=applied_max_age_days,
        )
        self._write_payload(pruned)
        return {
            "ok": True,
            "path": str(self._path),
            "expiry_enabled": applied_expiry_enabled,
            "ttl_days": applied_ttl_days,
            "max_age_days": applied_max_age_days,
            "removed_facts": int(stats.get("removed_facts", 0) or 0),
            "removed_recent_contexts": int(
                stats.get("removed_recent_contexts", 0) or 0
            ),
            "fact_count": len(pruned.get("facts", []))
            if isinstance(pruned.get("facts"), list)
            else 0,
            "recent_context_count": len(pruned.get("recent_contexts", []))
            if isinstance(pruned.get("recent_contexts"), list)
            else 0,
        }

    def wipe(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def add_fact(
        self,
        text: str,
        *,
        confidence: float = 1.0,
        importance_score: float | None = None,
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            raise ValueError("fact text cannot be empty")

        now_iso = _utc_now_iso()
        confidence_value = _clamp_score(confidence, default=1.0)
        importance_value = _clamp_score(
            importance_score,
            default=confidence_value,
        )

        payload = self.load()
        facts = list(payload.get("facts", []))
        facts.append(
            {
                "text": normalized_text,
                "confidence": confidence_value,
                "importance_score": importance_value,
                "use_count": 0,
                "last_used_at": now_iso,
                "source": str(source or "manual").strip() or "manual",
                "metadata": dict(metadata or {}),
                "updated_at": now_iso,
            }
        )
        payload["facts"] = self._normalize_facts(facts)
        self.save(payload)
        return payload

    def add_recent_context(self, *, query: str, repo: str) -> dict[str, Any]:
        normalized_query = _normalize_text(query)
        if not normalized_query:
            raise ValueError("query cannot be empty")

        payload = self.load()
        contexts = list(payload.get("recent_contexts", []))
        contexts.append(
            {
                "query": normalized_query,
                "repo": _normalize_text(repo),
                "captured_at": _utc_now_iso(),
            }
        )
        payload["recent_contexts"] = self._normalize_recent_contexts(contexts)
        self.save(payload)
        return payload

    def build_injection(
        self,
        *,
        top_n: int,
        token_budget: int,
        tokenizer_model: str,
    ) -> dict[str, Any]:
        facts = self.load().get("facts", [])
        ranked_facts = self._rank_facts_for_injection(facts)
        selected: list[dict[str, Any]] = []
        used_tokens = 0
        limit = max(1, int(top_n))
        budget = max(1, int(token_budget))

        for fact in ranked_facts:
            if not isinstance(fact, dict):
                continue
            text = _normalize_text(str(fact.get("text", "")))
            if not text:
                continue
            est_tokens = max(1, int(estimate_tokens(text, model=tokenizer_model)))
            if used_tokens + est_tokens > budget:
                continue

            selected.append(
                {
                    "text": text,
                    "confidence": float(fact.get("confidence", 0.0) or 0.0),
                    "importance_score": _clamp_score(
                        fact.get("importance_score"),
                        default=float(fact.get("confidence", 0.0) or 0.0),
                    ),
                    "use_count": _coerce_non_negative_int(fact.get("use_count")),
                    "last_used_at": str(
                        fact.get("last_used_at") or fact.get("updated_at") or ""
                    ),
                    "source": str(fact.get("source", "manual") or "manual"),
                    "metadata": (
                        dict(fact.get("metadata", {}))
                        if isinstance(fact.get("metadata"), dict)
                        else {}
                    ),
                    "est_tokens": est_tokens,
                }
            )
            used_tokens += est_tokens
            if len(selected) >= limit:
                break

        return {
            "enabled": True,
            "path": str(self._path),
            "fact_count_total": len(facts) if isinstance(facts, list) else 0,
            "facts": selected,
            "selected_count": len(selected),
            "selected_est_tokens_total": used_tokens,
            "top_n": limit,
            "token_budget": budget,
            "ranking": "confidence_importance_recency_v1",
        }

    def _default_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "facts": [],
            "preferences": {},
            "recent_contexts": [],
        }

    def _load_raw_payload(self) -> dict[str, Any]:
        payload = self._default_payload()
        if not self._path.exists() or not self._path.is_file():
            return payload

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return payload
        if not isinstance(raw, dict):
            return payload
        return self._build_normalized_payload(raw)

    def _build_normalized_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": 1,
            "facts": self._normalize_facts(payload.get("facts", [])),
            "preferences": (
                dict(payload.get("preferences", {}))
                if isinstance(payload.get("preferences"), dict)
                else {}
            ),
            "recent_contexts": self._normalize_recent_contexts(
                payload.get("recent_contexts", [])
            ),
        }

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _apply_expiry_policy(
        self,
        *,
        payload: dict[str, Any],
        expiry_enabled: bool,
        ttl_days: int,
        max_age_days: int,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        facts_raw = payload.get("facts", [])
        facts = facts_raw if isinstance(facts_raw, list) else []
        contexts_raw = payload.get("recent_contexts", [])
        contexts = contexts_raw if isinstance(contexts_raw, list) else []
        if not expiry_enabled:
            return (
                {
                    "version": 1,
                    "facts": list(facts),
                    "preferences": (
                        dict(payload.get("preferences", {}))
                        if isinstance(payload.get("preferences"), dict)
                        else {}
                    ),
                    "recent_contexts": list(contexts),
                },
                {"removed_facts": 0, "removed_recent_contexts": 0},
            )

        now_ts = datetime.now(timezone.utc).timestamp()
        ttl_cutoff = now_ts - max(1, int(ttl_days)) * 86400.0
        max_age_cutoff = now_ts - max(1, int(max_age_days)) * 86400.0

        kept_facts: list[dict[str, Any]] = []
        removed_facts = 0
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            last_used_ts = _parse_iso_timestamp(
                fact.get("last_used_at") or fact.get("updated_at")
            )
            updated_ts = _parse_iso_timestamp(
                fact.get("updated_at") or fact.get("last_used_at")
            )
            ttl_expired = last_used_ts > 0.0 and last_used_ts < ttl_cutoff
            max_age_expired = updated_ts > 0.0 and updated_ts < max_age_cutoff
            if ttl_expired or max_age_expired:
                removed_facts += 1
                continue
            kept_facts.append(fact)

        kept_contexts: list[dict[str, Any]] = []
        removed_recent_contexts = 0
        for row in contexts:
            if not isinstance(row, dict):
                continue
            captured_ts = _parse_iso_timestamp(row.get("captured_at"))
            ttl_expired = captured_ts > 0.0 and captured_ts < ttl_cutoff
            max_age_expired = captured_ts > 0.0 and captured_ts < max_age_cutoff
            if ttl_expired or max_age_expired:
                removed_recent_contexts += 1
                continue
            kept_contexts.append(row)

        return (
            {
                "version": 1,
                "facts": kept_facts,
                "preferences": (
                    dict(payload.get("preferences", {}))
                    if isinstance(payload.get("preferences"), dict)
                    else {}
                ),
                "recent_contexts": kept_contexts,
            },
            {
                "removed_facts": removed_facts,
                "removed_recent_contexts": removed_recent_contexts,
            },
        )

    def _normalize_facts(self, values: Any) -> list[dict[str, Any]]:
        if not isinstance(values, list):
            return []

        deduped: list[dict[str, Any]] = []
        for item in values:
            if not isinstance(item, dict):
                continue

            text = _normalize_text(str(item.get("text", "")))
            if not text:
                continue

            confidence = _clamp_score(item.get("confidence"), default=0.0)
            importance_score = _clamp_score(
                item.get("importance_score"),
                default=confidence,
            )
            now_iso = _utc_now_iso()
            updated_at = str(item.get("updated_at") or now_iso)
            last_used_at = str(item.get("last_used_at") or updated_at)
            candidate = {
                "text": text,
                "confidence": confidence,
                "importance_score": importance_score,
                "use_count": _coerce_non_negative_int(item.get("use_count")),
                "last_used_at": last_used_at,
                "source": str(item.get("source", "manual") or "manual"),
                "metadata": (
                    dict(item.get("metadata", {}))
                    if isinstance(item.get("metadata"), dict)
                    else {}
                ),
                "updated_at": updated_at,
            }

            duplicate_index = self._find_near_duplicate_index(
                deduped=deduped,
                candidate=candidate,
            )
            if duplicate_index < 0:
                deduped.append(candidate)
                continue
            merged = self._merge_duplicate_fact(deduped[duplicate_index], candidate)
            deduped[duplicate_index] = merged

        ordered = sorted(deduped, key=self._fact_storage_sort_key)
        return ordered[: self._max_facts]

    def _rank_facts_for_injection(self, facts: Any) -> list[dict[str, Any]]:
        if not isinstance(facts, list):
            return []

        normalized_facts = [
            item for item in self._normalize_facts(facts) if isinstance(item, dict)
        ]
        if not normalized_facts:
            return []

        last_used_timestamps = [
            _parse_iso_timestamp(
                item.get("last_used_at") or item.get("updated_at")
            )
            for item in normalized_facts
            if isinstance(item, dict)
        ]
        max_ts = max(last_used_timestamps) if last_used_timestamps else 0.0
        min_ts = min(last_used_timestamps) if last_used_timestamps else 0.0
        has_ts_range = max_ts > min_ts

        scored: list[tuple[float, tuple[Any, ...], dict[str, Any]]] = []
        for item in normalized_facts:
            confidence = _clamp_score(item.get("confidence"), default=0.0)
            importance = _clamp_score(
                item.get("importance_score"),
                default=confidence,
            )
            use_count = _coerce_non_negative_int(item.get("use_count"))
            usage_norm = min(1.0, math.log1p(use_count) / math.log1p(10.0))
            last_used_ts = _parse_iso_timestamp(
                item.get("last_used_at") or item.get("updated_at")
            )
            if has_ts_range:
                recency_norm = (last_used_ts - min_ts) / (max_ts - min_ts)
            else:
                recency_norm = 1.0 if last_used_ts > 0.0 else 0.0
            score = (
                0.60 * confidence
                + 0.30 * importance
                + 0.07 * recency_norm
                + 0.03 * usage_norm
            )
            tie_breaker = (
                -confidence,
                -importance,
                -use_count,
                -last_used_ts,
                str(item.get("text", "")).lower(),
                str(item.get("source", "")),
            )
            scored.append((float(score), tie_breaker, item))

        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        return [entry[2] for entry in scored]

    def _find_near_duplicate_index(
        self,
        *,
        deduped: list[dict[str, Any]],
        candidate: dict[str, Any],
    ) -> int:
        candidate_text = str(candidate.get("text", ""))
        candidate_tokens = _normalize_tokens(candidate_text)
        for index, existing in enumerate(deduped):
            existing_text = str(existing.get("text", ""))
            if self._is_near_duplicate(
                left_text=existing_text,
                right_text=candidate_text,
                left_tokens=_normalize_tokens(existing_text),
                right_tokens=candidate_tokens,
            ):
                return index
        return -1

    def _is_near_duplicate(
        self,
        *,
        left_text: str,
        right_text: str,
        left_tokens: tuple[str, ...],
        right_tokens: tuple[str, ...],
    ) -> bool:
        if left_text.lower() == right_text.lower():
            return True
        if not left_tokens or not right_tokens:
            return False
        left_set = set(left_tokens)
        right_set = set(right_tokens)
        shared = len(left_set.intersection(right_set))
        if shared <= 0:
            return False
        baseline = max(1, max(len(left_set), len(right_set)))
        overlap = float(shared) / float(baseline)
        return overlap >= self._dedupe_token_overlap_threshold

    @staticmethod
    def _fact_quality_key(fact: dict[str, Any]) -> tuple[Any, ...]:
        confidence = _clamp_score(fact.get("confidence"), default=0.0)
        importance = _clamp_score(
            fact.get("importance_score"),
            default=confidence,
        )
        use_count = _coerce_non_negative_int(fact.get("use_count"))
        last_used_ts = _parse_iso_timestamp(
            fact.get("last_used_at") or fact.get("updated_at")
        )
        return (
            confidence,
            importance,
            use_count,
            last_used_ts,
            str(fact.get("text", "")).lower(),
        )

    def _merge_duplicate_fact(
        self,
        existing: dict[str, Any],
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        preferred = (
            candidate
            if self._fact_quality_key(candidate) > self._fact_quality_key(existing)
            else existing
        )
        other = existing if preferred is candidate else candidate
        merged_metadata = {}
        if isinstance(other.get("metadata"), dict):
            merged_metadata.update(other.get("metadata", {}))
        if isinstance(preferred.get("metadata"), dict):
            merged_metadata.update(preferred.get("metadata", {}))

        preferred_confidence = _clamp_score(preferred.get("confidence"), default=0.0)
        preferred_importance = _clamp_score(
            preferred.get("importance_score"),
            default=preferred_confidence,
        )
        other_confidence = _clamp_score(other.get("confidence"), default=0.0)
        other_importance = _clamp_score(
            other.get("importance_score"),
            default=other_confidence,
        )
        merged_use_count = (
            max(
                _coerce_non_negative_int(existing.get("use_count")),
                _coerce_non_negative_int(candidate.get("use_count")),
            )
            + 1
        )
        preferred_last_used = str(
            preferred.get("last_used_at") or preferred.get("updated_at") or _utc_now_iso()
        )
        other_last_used = str(
            other.get("last_used_at") or other.get("updated_at") or _utc_now_iso()
        )
        preferred_updated = str(preferred.get("updated_at") or preferred_last_used)
        other_updated = str(other.get("updated_at") or other_last_used)

        return {
            "text": str(preferred.get("text", "")),
            "confidence": max(preferred_confidence, other_confidence),
            "importance_score": max(preferred_importance, other_importance),
            "use_count": merged_use_count,
            "last_used_at": (
                preferred_last_used
                if _parse_iso_timestamp(preferred_last_used)
                >= _parse_iso_timestamp(other_last_used)
                else other_last_used
            ),
            "source": str(preferred.get("source", "manual") or "manual"),
            "metadata": merged_metadata,
            "updated_at": (
                preferred_updated
                if _parse_iso_timestamp(preferred_updated)
                >= _parse_iso_timestamp(other_updated)
                else other_updated
            ),
        }

    @staticmethod
    def _fact_storage_sort_key(fact: dict[str, Any]) -> tuple[Any, ...]:
        confidence = _clamp_score(fact.get("confidence"), default=0.0)
        importance = _clamp_score(
            fact.get("importance_score"),
            default=confidence,
        )
        use_count = _coerce_non_negative_int(fact.get("use_count"))
        last_used_ts = _parse_iso_timestamp(
            fact.get("last_used_at") or fact.get("updated_at")
        )
        updated_ts = _parse_iso_timestamp(fact.get("updated_at"))
        return (
            -confidence,
            -importance,
            -use_count,
            -last_used_ts,
            -updated_ts,
            str(fact.get("text", "")).lower(),
            str(fact.get("source", "")),
        )

    def _normalize_recent_contexts(self, values: Any) -> list[dict[str, Any]]:
        if not isinstance(values, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            query = _normalize_text(str(item.get("query", "")))
            if not query:
                continue
            normalized.append(
                {
                    "query": query,
                    "repo": _normalize_text(str(item.get("repo", ""))),
                    "captured_at": str(item.get("captured_at") or _utc_now_iso()),
                }
            )

        normalized.sort(
            key=lambda row: (
                str(row.get("captured_at", "")),
                str(row.get("repo", "")),
                str(row.get("query", "")),
            ),
            reverse=True,
        )
        return normalized[: self._max_recent_contexts]


__all__ = ["ProfileStore"]
