"""Selection-feedback storage and deterministic rerank boosts.

The feedback store is local-first and intended to be used as a light-weight
signal to improve ranking without introducing non-deterministic churn.

Storage format:
- Stored inside the `preferences` section of the profile JSON (ProfileStore).
- Key: `selection_feedback`
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.index_stage.terms import extract_terms
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
from ace_lite.profile_store import ProfileStore

_FEEDBACK_PREF_KEY = "selection_feedback"
_FEEDBACK_VERSION = 1
_FEEDBACK_PREFERENCE_KIND = "selection_feedback"
_FEEDBACK_SIGNAL_SOURCE = "feedback_store"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_repo(value: Any) -> str:
    return _normalize_text(value)


def _normalize_repo_path(value: Any) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    return normalized


def _resolve_root_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _normalize_selected_path(value: Any, *, root_path: Path | None = None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if root_path is not None:
            try:
                return resolved.relative_to(root_path).as_posix()
            except ValueError:
                pass
        return resolved.as_posix()

    return _normalize_repo_path(raw)


def _normalize_terms(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = str(item or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _decay_weight(*, age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0.0:
        return 1.0
    if age_days <= 0.0:
        return 1.0
    return float(math.pow(0.5, float(age_days) / float(half_life_days)))


def _event_sort_key(event: dict[str, Any]) -> tuple[float, str, str]:
    ts = _parse_iso_timestamp(event.get("captured_at"))
    return (
        ts,
        str(event.get("selected_path") or ""),
        str(event.get("query") or "").lower(),
    )


def _normalize_event(
    raw: Any,
    *,
    repo_override: str | None = None,
    user_id_override: str | None = None,
    profile_key_override: str | None = None,
    root_path: Path | None = None,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    query = _normalize_text(raw.get("query"))
    repo = _normalize_repo(raw.get("repo") or repo_override)
    selected_path = _normalize_selected_path(
        raw.get("selected_path") or raw.get("path"),
        root_path=root_path,
    )
    if not query or not repo or not selected_path:
        return None

    captured_at = str(raw.get("captured_at") or "").strip()
    terms = _normalize_terms(raw.get("terms"))
    if not terms:
        terms = [str(item).lower() for item in extract_terms(query=query, memory_stage={})]
    position = _optional_positive_int(raw.get("position"))
    user_id = _normalize_text(raw.get("user_id") or user_id_override)
    profile_key = _normalize_text(raw.get("profile_key") or profile_key_override)

    return {
        "query": query,
        "repo": repo,
        "user_id": user_id,
        "profile_key": profile_key,
        "selected_path": selected_path,
        "position": position,
        "captured_at": captured_at,
        "terms": terms,
    }


def _event_identity(event: dict[str, Any]) -> tuple[str, str, str, str, int | None]:
    return (
        str(event.get("query") or "").strip().lower(),
        str(event.get("repo") or "").strip(),
        str(event.get("selected_path") or "").strip(),
        str(event.get("captured_at") or "").strip(),
        _optional_positive_int(event.get("position")),
    )


def _resolve_capture_store_path(profile_path: str | Path) -> Path:
    candidate = Path(profile_path).expanduser()
    suffix = candidate.suffix.lower()
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return candidate
    if candidate.name == "profile.json":
        return candidate.with_name("preference_capture.db")
    if suffix == ".json":
        return candidate.with_suffix(".feedback.db")
    return candidate.with_name(candidate.name + ".feedback.db")


@dataclass(frozen=True, slots=True)
class FeedbackBoostConfig:
    boost_per_select: float
    max_boost: float
    decay_days: float


class SelectionFeedbackStore:
    def __init__(
        self,
        *,
        profile_path: str | Path = "~/.ace-lite/profile.json",
        max_entries: int = 512,
    ) -> None:
        self._configured_path = Path(profile_path).expanduser().resolve()
        self._store = ProfileStore(path=profile_path)
        self._capture_store = DurablePreferenceCaptureStore(
            db_path=_resolve_capture_store_path(profile_path),
        )
        self._max_entries = max(0, int(max_entries))

    @property
    def path(self) -> Path:
        return self._capture_store.db_path

    @property
    def configured_path(self) -> Path:
        return self._configured_path

    def _metadata_payload(self) -> dict[str, Any]:
        store_path = str(self.path)
        return {
            "path": store_path,
            "store_path": store_path,
            "configured_path": str(self.configured_path),
            "preference_key": _FEEDBACK_PREF_KEY,
        }

    def load_events(self) -> list[dict[str, Any]]:
        durable_rows = self._capture_store.list_events(
            preference_kind=_FEEDBACK_PREFERENCE_KIND,
            signal_source=_FEEDBACK_SIGNAL_SOURCE,
            limit=max(1, self._max_entries) if self._max_entries > 0 else 10000,
        )
        normalized = [self._capture_event_to_feedback_event(item.to_payload()) for item in durable_rows]
        normalized = [item for item in normalized if item is not None]
        if not normalized:
            normalized = self._load_legacy_events()
        normalized.sort(key=_event_sort_key)
        if self._max_entries > 0 and len(normalized) > self._max_entries:
            normalized = normalized[-self._max_entries :]
        return normalized

    def record(
        self,
        *,
        query: str,
        repo: str,
        user_id: str | None = None,
        profile_key: str | None = None,
        selected_path: str,
        position: int | None = None,
        captured_at: str | None = None,
        root_path: str | Path | None = None,
    ) -> dict[str, Any]:
        normalized_query = _normalize_text(query)
        if not normalized_query:
            raise ValueError("query cannot be empty")
        normalized_repo = _normalize_repo(repo)
        if not normalized_repo:
            raise ValueError("repo cannot be empty")
        normalized_path = _normalize_selected_path(
            selected_path,
            root_path=_resolve_root_path(root_path),
        )
        if not normalized_path:
            raise ValueError("selected_path cannot be empty")

        event = {
            "query": normalized_query,
            "repo": normalized_repo,
            "user_id": _normalize_text(user_id),
            "profile_key": _normalize_text(profile_key),
            "selected_path": normalized_path,
            "position": _optional_positive_int(position),
            "captured_at": str(captured_at or _utc_now_iso()),
            "terms": [
                str(item).lower()
                for item in extract_terms(query=normalized_query, memory_stage={})
            ],
        }
        self._capture_store.record(
            {
                "user_id": str(event.get("user_id") or "").strip(),
                "repo_key": normalized_repo,
                "profile_key": str(event.get("profile_key") or "").strip(),
                "preference_kind": _FEEDBACK_PREFERENCE_KIND,
                "signal_source": _FEEDBACK_SIGNAL_SOURCE,
                "signal_key": normalized_query,
                "target_path": normalized_path,
                "value_text": normalized_query,
                "weight": 1.0,
                "payload": dict(event),
                "created_at": event["captured_at"],
            }
        )
        pruned = 0
        if self._max_entries > 0:
            pruned = self._capture_store.trim_events(
                keep_latest=self._max_entries,
                preference_kind=_FEEDBACK_PREFERENCE_KIND,
                signal_source=_FEEDBACK_SIGNAL_SOURCE,
            )
        normalized_events = self.load_events()

        payload = {
            "ok": True,
            "event": dict(event),
            "event_count": len(normalized_events),
            "pruned": pruned,
        }
        payload.update(self._metadata_payload())
        return payload

    def export(
        self,
        *,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_repo = _normalize_repo(repo) if repo is not None else None
        normalized_user_id = _normalize_text(user_id) if user_id is not None else None
        normalized_profile_key = (
            _normalize_text(profile_key) if profile_key is not None else None
        )
        events = self.load_events()
        if normalized_repo is not None:
            events = [
                event
                for event in events
                if str(event.get("repo") or "").strip() == normalized_repo
            ]
        if normalized_user_id is not None:
            events = [
                event
                for event in events
                if str(event.get("user_id") or "").strip() == normalized_user_id
            ]
        if normalized_profile_key is not None:
            events = [
                event
                for event in events
                if str(event.get("profile_key") or "").strip()
                == normalized_profile_key
            ]
        payload = {
            "ok": True,
            "repo_filter": normalized_repo,
            "user_id_filter": normalized_user_id,
            "profile_key_filter": normalized_profile_key,
            "event_count": len(events),
            "events": [dict(event) for event in events],
        }
        payload.update(self._metadata_payload())
        return payload

    def replay(
        self,
        *,
        events: list[dict[str, Any]],
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        root_path: str | Path | None = None,
        reset: bool = False,
    ) -> dict[str, Any]:
        normalized_repo = _normalize_repo(repo) if repo is not None else None
        normalized_user_id = _normalize_text(user_id)
        normalized_profile_key = _normalize_text(profile_key)
        resolved_root = _resolve_root_path(root_path)
        if reset:
            self.reset()
        imported = 0
        skipped = 0
        for row in events:
            event = _normalize_event(
                row,
                repo_override=normalized_repo,
                user_id_override=normalized_user_id,
                profile_key_override=normalized_profile_key,
                root_path=resolved_root,
            )
            if event is None:
                skipped += 1
                continue
            self._capture_store.record(
                {
                    "user_id": str(event.get("user_id") or "").strip(),
                    "repo_key": str(event.get("repo") or "").strip(),
                    "profile_key": str(event.get("profile_key") or "").strip(),
                    "preference_kind": _FEEDBACK_PREFERENCE_KIND,
                    "signal_source": _FEEDBACK_SIGNAL_SOURCE,
                    "signal_key": str(event.get("query") or "").strip(),
                    "target_path": str(event.get("selected_path") or "").strip(),
                    "value_text": str(event.get("query") or "").strip(),
                    "weight": 1.0,
                    "payload": dict(event),
                    "created_at": str(event.get("captured_at") or _utc_now_iso()),
                }
            )
            imported += 1

        pruned = 0
        if self._max_entries > 0:
            pruned = self._capture_store.trim_events(
                keep_latest=self._max_entries,
                preference_kind=_FEEDBACK_PREFERENCE_KIND,
                signal_source=_FEEDBACK_SIGNAL_SOURCE,
            )
        normalized_events = self.load_events()

        payload = {
            "ok": True,
            "repo_override": normalized_repo,
            "user_id_override": normalized_user_id,
            "profile_key_override": normalized_profile_key,
            "root_path": str(resolved_root) if resolved_root is not None else None,
            "reset": bool(reset),
            "input_count": len(events),
            "imported": imported,
            "skipped": skipped,
            "event_count": len(normalized_events),
            "pruned": pruned,
        }
        payload.update(self._metadata_payload())
        return payload

    def reset(self) -> dict[str, Any]:
        removed = self._capture_store.delete_events(
            preference_kind=_FEEDBACK_PREFERENCE_KIND,
            signal_source=_FEEDBACK_SIGNAL_SOURCE,
        )
        payload = self._store.load()
        prefs = payload.get("preferences", {})
        prefs = dict(prefs) if isinstance(prefs, dict) else {}
        if _FEEDBACK_PREF_KEY in prefs:
            prefs.pop(_FEEDBACK_PREF_KEY, None)
            payload["preferences"] = prefs
            self._store.save(payload)
        payload = {
            "ok": True,
            "removed": removed,
        }
        payload.update(self._metadata_payload())
        return payload

    def stats(
        self,
        *,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        query_terms: list[str] | None = None,
        boost: FeedbackBoostConfig | None = None,
        now_ts: float | None = None,
        top_n: int = 10,
    ) -> dict[str, Any]:
        now = float(now_ts) if now_ts is not None else datetime.now(timezone.utc).timestamp()
        normalized_repo = _normalize_repo(repo) if repo is not None else None
        normalized_user_id = _normalize_text(user_id) if user_id is not None else None
        normalized_profile_key = (
            _normalize_text(profile_key) if profile_key is not None else None
        )
        query_terms_norm = _normalize_terms(list(query_terms or []))
        boost_cfg = boost or FeedbackBoostConfig(
            boost_per_select=0.15, max_boost=0.6, decay_days=60.0
        )

        events = self.load_events()
        filtered: list[dict[str, Any]] = []
        for event in events:
            if normalized_repo is not None and str(event.get("repo", "")).strip() != normalized_repo:
                continue
            if (
                normalized_user_id is not None
                and str(event.get("user_id") or "").strip() != normalized_user_id
            ):
                continue
            if (
                normalized_profile_key is not None
                and str(event.get("profile_key") or "").strip()
                != normalized_profile_key
            ):
                continue
            if query_terms_norm:
                event_terms = set(_normalize_terms(event.get("terms")))
                if not event_terms.intersection(query_terms_norm):
                    continue
            filtered.append(event)

        per_path: dict[str, dict[str, Any]] = {}
        for event in filtered:
            path = str(event.get("selected_path") or "").strip()
            if not path:
                continue
            ts = _parse_iso_timestamp(event.get("captured_at"))
            age_days = max(0.0, (now - ts) / 86400.0) if ts > 0.0 else 0.0
            weight = _decay_weight(age_days=age_days, half_life_days=float(boost_cfg.decay_days))
            bucket = per_path.setdefault(
                path,
                {
                    "selected_path": path,
                    "count": 0,
                    "decayed_weight_sum": 0.0,
                    "last_selected_at": "",
                },
            )
            bucket["count"] += 1
            bucket["decayed_weight_sum"] += float(weight)
            captured_at = str(event.get("captured_at") or "").strip()
            if captured_at and (
                not bucket["last_selected_at"]
                or _parse_iso_timestamp(captured_at)
                > _parse_iso_timestamp(bucket["last_selected_at"])
            ):
                bucket["last_selected_at"] = captured_at

        rows: list[dict[str, Any]] = []
        for path, bucket in per_path.items():
            weight_sum = float(bucket.get("decayed_weight_sum", 0.0) or 0.0)
            raw_boost = float(boost_cfg.boost_per_select) * weight_sum
            applied_boost = min(max(0.0, float(boost_cfg.max_boost)), max(0.0, raw_boost))
            rows.append(
                {
                    "selected_path": path,
                    "count": int(bucket.get("count", 0) or 0),
                    "decayed_weight_sum": round(weight_sum, 6),
                    "boost": round(applied_boost, 6),
                    "last_selected_at": str(bucket.get("last_selected_at") or ""),
                }
            )

        rows.sort(
            key=lambda item: (
                -float(item.get("boost") or 0.0),
                -int(item.get("count") or 0),
                str(item.get("selected_path") or ""),
            )
        )
        limit = max(1, int(top_n))

        payload = {
            "ok": True,
            "repo_filter": normalized_repo,
            "user_id_filter": normalized_user_id,
            "profile_key_filter": normalized_profile_key,
            "query_terms_filter": list(query_terms_norm),
            "boost_config": {
                "boost_per_select": float(boost_cfg.boost_per_select),
                "max_boost": float(boost_cfg.max_boost),
                "decay_days": float(boost_cfg.decay_days),
            },
            "event_count": len(events),
            "matched_event_count": len(filtered),
            "unique_paths": len(rows),
            "top_n": limit,
            "paths": rows[:limit],
        }
        payload.update(self._metadata_payload())
        return payload

    def _load_legacy_events(self) -> list[dict[str, Any]]:
        payload = self._store.load()
        prefs = payload.get("preferences", {})
        prefs = dict(prefs) if isinstance(prefs, dict) else {}
        feedback = prefs.get(_FEEDBACK_PREF_KEY, {})
        feedback = dict(feedback) if isinstance(feedback, dict) else {}
        raw_events = feedback.get("events", [])
        events = raw_events if isinstance(raw_events, list) else []
        return [
            event for event in (_normalize_event(item) for item in events) if event is not None
        ]

    def _capture_event_to_feedback_event(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        raw = payload.get("payload")
        if isinstance(raw, dict):
            normalized = _normalize_event(raw)
            if normalized is not None:
                return normalized
        normalized_repo = str(payload.get("repo_key") or "").strip()
        normalized_path = _normalize_selected_path(payload.get("target_path"))
        normalized_query = _normalize_text(payload.get("value_text") or payload.get("signal_key"))
        if not normalized_repo or not normalized_path or not normalized_query:
            return None
        return _normalize_event(
            {
                "query": normalized_query,
                "repo": normalized_repo,
                "user_id": payload.get("user_id"),
                "profile_key": payload.get("profile_key"),
                "selected_path": normalized_path,
                "captured_at": payload.get("created_at"),
            }
        )


def build_feedback_boosts(
    *,
    events: list[dict[str, Any]],
    repo: str,
    query_terms: list[str],
    boost: FeedbackBoostConfig,
    now_ts: float | None = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    normalized_repo = _normalize_repo(repo)
    normalized_terms = _normalize_terms(list(query_terms or []))
    if not normalized_repo:
        return {}, {"enabled": False, "reason": "empty_repo"}
    if not normalized_terms:
        return {}, {"enabled": False, "reason": "empty_query_terms"}

    now = float(now_ts) if now_ts is not None else datetime.now(timezone.utc).timestamp()
    boosts_by_path: dict[str, float] = {}
    matched_events = 0

    for event in events:
        if str(event.get("repo") or "").strip() != normalized_repo:
            continue
        event_terms = set(_normalize_terms(event.get("terms")))
        if not event_terms.intersection(normalized_terms):
            continue
        matched_events += 1
        path = _normalize_repo_path(event.get("selected_path"))
        if not path:
            continue
        ts = _parse_iso_timestamp(event.get("captured_at"))
        age_days = max(0.0, (now - ts) / 86400.0) if ts > 0.0 else 0.0
        weight = _decay_weight(age_days=age_days, half_life_days=float(boost.decay_days))
        prev = float(boosts_by_path.get(path, 0.0) or 0.0)
        raw = prev + float(boost.boost_per_select) * float(weight)
        boosts_by_path[path] = min(max(0.0, float(boost.max_boost)), max(0.0, raw))

    return boosts_by_path, {
        "enabled": True,
        "reason": "ok",
        "repo": normalized_repo,
        "query_terms_count": len(normalized_terms),
        "event_count": len(events),
        "matched_event_count": matched_events,
        "boosted_paths": len(boosts_by_path),
        "boost_config": {
            "boost_per_select": float(boost.boost_per_select),
            "max_boost": float(boost.max_boost),
            "decay_days": float(boost.decay_days),
        },
    }


__all__ = [
    "FeedbackBoostConfig",
    "SelectionFeedbackStore",
    "build_feedback_boosts",
]
