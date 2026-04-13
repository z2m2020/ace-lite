from __future__ import annotations

import hashlib
import json
import math
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_REWARD_LOG_PATH = "context-map/router/rewards.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any, *, max_len: int = 512) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return " ".join(raw.split())[:max_len]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except Exception:
        return normalize_text(value, max_len=512)


def _normalize_timestamp(value: Any, *, field_name: str, default: str | None = None) -> str:
    text = normalize_text(value, max_len=64) or normalize_text(default, max_len=64)
    if not text:
        text = utc_now_iso()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    return parsed.astimezone(timezone.utc).isoformat()


def _normalize_reward_value(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError("reward_value must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError("reward_value must be finite")
    return round(parsed, 6)


def _normalize_context_features(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, raw in value.items():
        name = normalize_text(key, max_len=128).lower()
        if not name:
            continue
        normalized[name] = _json_safe(raw)
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


def _build_context_fingerprint(
    *,
    query_id: str,
    chosen_arm_id: str,
    context_features: dict[str, Any],
) -> str:
    payload = {
        "query_id": query_id,
        "chosen_arm_id": chosen_arm_id,
        "context_features": context_features,
    }
    source = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def make_reward_event(
    *,
    query_id: str,
    chosen_arm_id: str,
    reward_source: str,
    reward_value: float,
    observed_at: str | None = None,
    reward_observed_at: str | None = None,
    context_features: dict[str, Any] | None = None,
    is_exploration: bool = False,
    router_mode: str = "",
    shadow_arm_id: str = "",
    reward_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_query_id = normalize_text(query_id, max_len=128)
    if not normalized_query_id:
        raise ValueError("query_id is required")
    normalized_arm_id = normalize_text(chosen_arm_id, max_len=128)
    if not normalized_arm_id:
        raise ValueError("chosen_arm_id is required")
    normalized_reward_source = normalize_text(reward_source, max_len=128).lower()
    if not normalized_reward_source:
        raise ValueError("reward_source is required")

    normalized_observed_at = _normalize_timestamp(
        observed_at,
        field_name="observed_at",
    )
    normalized_reward_observed_at = _normalize_timestamp(
        reward_observed_at,
        field_name="reward_observed_at",
        default=normalized_observed_at,
    )
    observed_dt = datetime.fromisoformat(normalized_observed_at)
    reward_observed_dt = datetime.fromisoformat(normalized_reward_observed_at)
    delay_seconds = (reward_observed_dt - observed_dt).total_seconds()
    if delay_seconds < 0.0:
        raise ValueError("reward_observed_at must be on or after observed_at")

    normalized_context_features = _normalize_context_features(context_features)
    normalized_reward_metadata = _normalize_context_features(reward_metadata)
    context_fingerprint = _build_context_fingerprint(
        query_id=normalized_query_id,
        chosen_arm_id=normalized_arm_id,
        context_features=normalized_context_features,
    )
    fingerprint_source = json.dumps(
        {
            "query_id": normalized_query_id,
            "chosen_arm_id": normalized_arm_id,
            "reward_source": normalized_reward_source,
            "reward_value": _normalize_reward_value(reward_value),
            "observed_at": normalized_observed_at,
            "reward_observed_at": normalized_reward_observed_at,
            "context_fingerprint": context_fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    event_id_seed = f"{normalized_reward_observed_at}|{fingerprint}"
    event_id = "rwd_" + hashlib.sha256(event_id_seed.encode("utf-8")).hexdigest()[:12]

    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "observed_at": normalized_observed_at,
        "reward_observed_at": normalized_reward_observed_at,
        "reward_delay_seconds": round(delay_seconds, 6),
        "query_id": normalized_query_id,
        "chosen_arm_id": normalized_arm_id,
        "shadow_arm_id": normalize_text(shadow_arm_id, max_len=128),
        "router_mode": normalize_text(router_mode, max_len=64).lower(),
        "context_fingerprint": context_fingerprint,
        "context_features": normalized_context_features,
        "is_exploration": bool(is_exploration),
        "reward_source": normalized_reward_source,
        "reward_value": _normalize_reward_value(reward_value),
        "reward_metadata": normalized_reward_metadata,
        "fingerprint": fingerprint,
    }


def validate_reward_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("reward event must be a dictionary")
    if str(event.get("schema_version") or "") != SCHEMA_VERSION:
        raise ValueError(f"unexpected schema_version: {event.get('schema_version')!r}")
    return make_reward_event(
        query_id=str(event.get("query_id") or ""),
        chosen_arm_id=str(event.get("chosen_arm_id") or ""),
        reward_source=str(event.get("reward_source") or ""),
        reward_value=event.get("reward_value", 0.0),
        observed_at=str(event.get("observed_at") or ""),
        reward_observed_at=str(event.get("reward_observed_at") or ""),
        context_features=event.get("context_features", {}),
        is_exploration=bool(event.get("is_exploration", False)),
        router_mode=str(event.get("router_mode") or ""),
        shadow_arm_id=str(event.get("shadow_arm_id") or ""),
        reward_metadata=event.get("reward_metadata", {}),
    )


def normalize_reward_event_for_replay(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("reward event must be a dictionary")

    source_schema_version = normalize_text(event.get("schema_version"), max_len=32)
    if source_schema_version == SCHEMA_VERSION:
        normalized = validate_reward_event(event)
    else:
        normalized = make_reward_event(
            query_id=str(event.get("query_id") or event.get("query") or ""),
            chosen_arm_id=str(event.get("chosen_arm_id") or event.get("arm_id") or ""),
            reward_source=str(event.get("reward_source") or event.get("source") or ""),
            reward_value=_normalize_reward_value(
                event.get("reward_value", event.get("reward", 0.0))
            ),
            observed_at=str(event.get("observed_at") or event.get("logged_at") or ""),
            reward_observed_at=str(
                event.get("reward_observed_at")
                or event.get("reward_ts")
                or event.get("reward_logged_at")
                or event.get("observed_at")
                or event.get("logged_at")
                or ""
            ),
            context_features=event.get("context_features", event.get("features", {})),
            is_exploration=bool(
                event.get("is_exploration", event.get("exploration", False))
            ),
            router_mode=str(event.get("router_mode") or event.get("mode") or ""),
            shadow_arm_id=str(event.get("shadow_arm_id") or event.get("shadow_arm") or ""),
            reward_metadata=event.get("reward_metadata", event.get("metadata", {})),
        )
    normalized["source_schema_version"] = source_schema_version or "unversioned"
    source_event_id = normalize_text(event.get("event_id"), max_len=128)
    if source_event_id:
        normalized["source_event_id"] = source_event_id
    return normalized


def append_reward_event(*, path: Path, event: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_reward_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(normalized, ensure_ascii=False) + "\n")
    return normalized


def load_reward_events(*, path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                rows.append(validate_reward_event(payload))
            except ValueError:
                continue
    return rows


def load_reward_events_for_replay(*, path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "events": [],
            "total_row_count": 0,
            "skipped_row_count": 0,
            "source_schema_versions": {},
        }

    rows: list[dict[str, Any]] = []
    skipped_row_count = 0
    total_row_count = 0
    source_schema_versions: dict[str, int] = {}

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            total_row_count += 1
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                skipped_row_count += 1
                continue
            if not isinstance(payload, dict):
                skipped_row_count += 1
                continue
            try:
                normalized = normalize_reward_event_for_replay(payload)
            except ValueError:
                skipped_row_count += 1
                continue
            rows.append(normalized)
            source_schema_version = str(
                normalized.get("source_schema_version")
                or normalized.get("schema_version")
                or "unversioned"
            )
            source_schema_versions[source_schema_version] = (
                source_schema_versions.get(source_schema_version, 0) + 1
            )

    return {
        "events": rows,
        "total_row_count": total_row_count,
        "skipped_row_count": skipped_row_count,
        "source_schema_versions": source_schema_versions,
    }


class AsyncRewardLogWriter:
    def __init__(self, *, path: str | Path, max_workers: int = 1) -> None:
        self._path = Path(path)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="router-reward-log",
        )
        self._pending: list[Future[dict[str, Any]]] = []
        self._written_count = 0
        self._error_count = 0
        self._last_error = ""

    def _collect_future(self, future: Future[dict[str, Any]]) -> None:
        try:
            future.result()
        except Exception as exc:
            self._error_count += 1
            self._last_error = normalize_text(exc, max_len=256)
        else:
            self._written_count += 1

    def _drain_completed(self) -> None:
        remaining: list[Future[dict[str, Any]]] = []
        for future in self._pending:
            if future.done():
                self._collect_future(future)
            else:
                remaining.append(future)
        self._pending = remaining

    def submit(self, *, event: dict[str, Any]) -> bool:
        normalized = validate_reward_event(event)
        self._drain_completed()
        self._pending.append(
            self._executor.submit(
                append_reward_event,
                path=self._path,
                event=normalized,
            )
        )
        return True

    def stats(self) -> dict[str, Any]:
        self._drain_completed()
        return {
            "path": str(self._path),
            "pending_count": len(self._pending),
            "written_count": self._written_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
        }

    def flush(self) -> dict[str, Any]:
        pending = list(self._pending)
        self._pending = []
        for future in pending:
            self._collect_future(future)
        return self.stats()

    def close(self) -> dict[str, Any]:
        stats = self.flush()
        self._executor.shutdown(wait=False)
        return stats


__all__ = [
    "DEFAULT_REWARD_LOG_PATH",
    "SCHEMA_VERSION",
    "AsyncRewardLogWriter",
    "append_reward_event",
    "load_reward_events",
    "load_reward_events_for_replay",
    "make_reward_event",
    "normalize_reward_event_for_replay",
    "validate_reward_event",
]
