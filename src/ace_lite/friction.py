from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
VALID_STATUSES = {"open", "resolved", "suppressed"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_severity(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text not in SEVERITY_ORDER:
        raise ValueError(f"invalid severity: {value!r}")
    return text


def normalize_status(value: Any) -> str:
    text = str(value or "").strip().lower() or "open"
    if text not in VALID_STATUSES:
        raise ValueError(f"invalid status: {value!r}")
    return text


def normalize_text(value: Any, *, max_len: int = 2000) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = " ".join(raw.split())
    return normalized[:max_len]


def normalize_tags(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        tag = normalize_text(item, max_len=64).lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def normalize_time_cost_min(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = 0.0
    return round(max(0.0, parsed), 4)


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except Exception:
        return normalize_text(value, max_len=2000)


def make_event(
    *,
    stage: str,
    expected: str,
    actual: str,
    query: str = "",
    manual_fix: str = "",
    severity: str = "medium",
    status: str = "open",
    source: str = "manual",
    root_cause: str = "",
    time_cost_min: float = 0.0,
    tags: Iterable[Any] | None = None,
    context: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_stage = normalize_text(stage, max_len=128)
    normalized_expected = normalize_text(expected, max_len=2000)
    normalized_actual = normalize_text(actual, max_len=2000)
    if not normalized_stage:
        raise ValueError("stage is required")
    if not normalized_expected:
        raise ValueError("expected is required")
    if not normalized_actual:
        raise ValueError("actual is required")

    normalized_query = normalize_text(query, max_len=500)
    normalized_manual_fix = normalize_text(manual_fix, max_len=2000)
    normalized_source = normalize_text(source, max_len=128) or "manual"
    normalized_root_cause = normalize_text(root_cause, max_len=256)
    normalized_tags = normalize_tags(tags)
    normalized_context = (
        {
            str(key): json_safe(value)
            for key, value in (context or {}).items()
            if normalize_text(key, max_len=128)
        }
        if isinstance(context, dict)
        else {}
    )
    normalized_severity = normalize_severity(severity)
    normalized_status = normalize_status(status)
    normalized_time_cost_min = normalize_time_cost_min(time_cost_min)
    timestamp = normalize_text(created_at, max_len=64) or utc_now_iso()

    fingerprint_source = "|".join(
        [
            normalized_stage,
            normalized_query,
            normalized_expected,
            normalized_actual,
            normalized_root_cause,
            normalized_severity,
            normalized_status,
        ]
    )
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    event_id_seed = f"{timestamp}|{normalized_source}|{fingerprint}"
    event_id = "fric_" + hashlib.sha256(event_id_seed.encode("utf-8")).hexdigest()[:12]

    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "created_at": timestamp,
        "source": normalized_source,
        "stage": normalized_stage,
        "query": normalized_query,
        "expected": normalized_expected,
        "actual": normalized_actual,
        "manual_fix": normalized_manual_fix,
        "severity": normalized_severity,
        "status": normalized_status,
        "time_cost_min": normalized_time_cost_min,
        "root_cause": normalized_root_cause,
        "tags": normalized_tags,
        "context": normalized_context,
        "fingerprint": fingerprint,
    }


def append_event(*, path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_events(*, path: Path) -> list[dict[str, Any]]:
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
            rows.append(payload)
    return rows


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(math.ceil(len(ordered) * 0.95) - 1)
    idx = max(0, min(idx, len(ordered) - 1))
    return round(float(ordered[idx]), 4)


def aggregate_events(*, events: list[dict[str, Any]], top_n: int = 10) -> dict[str, Any]:
    stage_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    root_cause_counts: dict[str, int] = {}
    costs: list[float] = []

    for item in events:
        if not isinstance(item, dict):
            continue
        stage = normalize_text(item.get("stage"), max_len=128) or "(unknown)"
        severity = str(item.get("severity") or "").strip().lower() or "unknown"
        status = str(item.get("status") or "").strip().lower() or "open"
        root_cause = normalize_text(item.get("root_cause"), max_len=256) or "(unknown)"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        root_cause_counts[root_cause] = root_cause_counts.get(root_cause, 0) + 1
        costs.append(normalize_time_cost_min(item.get("time_cost_min", 0.0)))

    top = max(1, int(top_n))
    total = len(events)
    total_cost = round(sum(costs), 4)
    mean_cost = round(total_cost / float(total), 4) if total > 0 else 0.0

    top_root_causes = [
        {"root_cause": key, "count": value}
        for key, value in sorted(
            root_cause_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:top]
    ]

    top_stages = [
        {"stage": key, "count": value}
        for key, value in sorted(
            stage_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:top]
    ]

    return {
        "event_count": total,
        "open_count": int(status_counts.get("open", 0)),
        "stage_counts": dict(sorted(stage_counts.items(), key=lambda item: item[0])),
        "severity_counts": dict(sorted(severity_counts.items(), key=lambda item: item[0])),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: item[0])),
        "root_cause_counts": dict(
            sorted(root_cause_counts.items(), key=lambda item: item[0])
        ),
        "total_time_cost_min": total_cost,
        "mean_time_cost_min": mean_cost,
        "p95_time_cost_min": _p95(costs),
        "top_root_causes": top_root_causes,
        "top_stages": top_stages,
    }


__all__ = [
    "SCHEMA_VERSION",
    "SEVERITY_ORDER",
    "VALID_STATUSES",
    "aggregate_events",
    "append_event",
    "load_events",
    "make_event",
    "normalize_severity",
    "normalize_status",
    "normalize_tags",
    "normalize_text",
    "normalize_time_cost_min",
    "utc_now_iso",
]
