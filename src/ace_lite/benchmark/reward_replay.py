from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from ace_lite.router_reward_store import load_reward_events_for_replay


def _normalize_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _distribution_rows(
    buckets: dict[str, dict[str, float]],
    *,
    label_key: str,
    total_count: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, bucket in sorted(
        buckets.items(),
        key=lambda item: (-int(item[1].get("event_count", 0) or 0), str(item[0])),
    ):
        event_count = max(0, int(bucket.get("event_count", 0) or 0))
        reward_total = float(bucket.get("reward_total", 0.0) or 0.0)
        rows.append(
            {
                label_key: label,
                "event_count": event_count,
                "event_rate": (
                    float(event_count) / float(total_count) if total_count > 0 else 0.0
                ),
                "mean_reward": (
                    reward_total / float(event_count) if event_count > 0 else 0.0
                ),
            }
        )
    return rows


def build_reward_replay_payload(
    *,
    events: list[dict[str, Any]],
    input_path: str | Path = "",
    total_row_count: int | None = None,
    skipped_row_count: int = 0,
) -> dict[str, Any]:
    dataset_rows: list[dict[str, Any]] = []
    query_ids: set[str] = set()
    context_fingerprints: set[str] = set()
    reward_values: list[float] = []
    reward_delays: list[float] = []
    exploration_event_count = 0

    chosen_arm_buckets: dict[str, dict[str, float]] = {}
    reward_source_buckets: dict[str, dict[str, float]] = {}
    router_mode_buckets: dict[str, dict[str, float]] = {}
    schema_version_buckets: dict[str, dict[str, float]] = {}

    for event in events:
        if not isinstance(event, dict):
            continue
        reward_value = _normalize_float(event.get("reward_value", 0.0))
        reward_delay_seconds = max(
            0.0,
            _normalize_float(event.get("reward_delay_seconds", 0.0)),
        )
        query_id = str(event.get("query_id") or "").strip()
        chosen_arm_id = str(event.get("chosen_arm_id") or "").strip()
        reward_source = str(event.get("reward_source") or "").strip().lower()
        router_mode = str(event.get("router_mode") or "").strip().lower()
        schema_version = str(event.get("schema_version") or "").strip()
        source_schema_version = str(
            event.get("source_schema_version") or schema_version or ""
        ).strip()
        context_fingerprint = str(event.get("context_fingerprint") or "").strip()
        is_exploration = bool(event.get("is_exploration", False))

        row = {
            "schema_version": schema_version,
            "source_schema_version": source_schema_version,
            "event_id": str(event.get("event_id") or "").strip(),
            "query_id": query_id,
            "chosen_arm_id": chosen_arm_id,
            "shadow_arm_id": str(event.get("shadow_arm_id") or "").strip(),
            "router_mode": router_mode,
            "context_fingerprint": context_fingerprint,
            "context_features": (
                dict(event.get("context_features", {}))
                if isinstance(event.get("context_features"), dict)
                else {}
            ),
            "is_exploration": is_exploration,
            "reward_source": reward_source,
            "reward_value": reward_value,
            "reward_delay_seconds": reward_delay_seconds,
            "observed_at": str(event.get("observed_at") or "").strip(),
            "reward_observed_at": str(event.get("reward_observed_at") or "").strip(),
            "reward_metadata": (
                dict(event.get("reward_metadata", {}))
                if isinstance(event.get("reward_metadata"), dict)
                else {}
            ),
        }
        dataset_rows.append(row)

        if query_id:
            query_ids.add(query_id)
        if context_fingerprint:
            context_fingerprints.add(context_fingerprint)
        if is_exploration:
            exploration_event_count += 1
        reward_values.append(reward_value)
        reward_delays.append(reward_delay_seconds)

        for label, buckets in (
            (chosen_arm_id or "(unknown)", chosen_arm_buckets),
            (reward_source or "(unknown)", reward_source_buckets),
            (router_mode or "(unknown)", router_mode_buckets),
            (source_schema_version or "(unknown)", schema_version_buckets),
        ):
            bucket = buckets.setdefault(label, {"event_count": 0.0, "reward_total": 0.0})
            bucket["event_count"] += 1.0
            bucket["reward_total"] += reward_value

    event_count = len(dataset_rows)
    resolved_total_row_count = (
        event_count if total_row_count is None else max(event_count, int(total_row_count))
    )
    summary = {
        "input_path": str(input_path),
        "event_count": event_count,
        "total_row_count": resolved_total_row_count,
        "skipped_row_count": max(0, int(skipped_row_count)),
        "load_success_rate": (
            float(event_count) / float(resolved_total_row_count)
            if resolved_total_row_count > 0
            else 0.0
        ),
        "query_count": len(query_ids),
        "context_fingerprint_count": len(context_fingerprints),
        "exploration_event_count": exploration_event_count,
        "exploration_event_rate": (
            float(exploration_event_count) / float(event_count) if event_count > 0 else 0.0
        ),
        "reward_value_mean": mean(reward_values) if reward_values else 0.0,
        "reward_value_min": min(reward_values) if reward_values else 0.0,
        "reward_value_max": max(reward_values) if reward_values else 0.0,
        "reward_delay_mean_seconds": mean(reward_delays) if reward_delays else 0.0,
        "reward_delay_max_seconds": max(reward_delays) if reward_delays else 0.0,
        "chosen_arms": _distribution_rows(
            chosen_arm_buckets,
            label_key="arm_id",
            total_count=event_count,
        ),
        "reward_sources": _distribution_rows(
            reward_source_buckets,
            label_key="reward_source",
            total_count=event_count,
        ),
        "router_modes": _distribution_rows(
            router_mode_buckets,
            label_key="router_mode",
            total_count=event_count,
        ),
        "schema_versions": _distribution_rows(
            schema_version_buckets,
            label_key="schema_version",
            total_count=event_count,
        ),
    }
    return {"events": dataset_rows, "summary": summary}


def write_reward_replay_artifacts(
    *,
    input_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    source = Path(input_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"reward log not found: {source}")

    replay_load = load_reward_events_for_replay(path=source)
    payload = build_reward_replay_payload(
        events=list(replay_load.get("events", [])),
        input_path=source,
        total_row_count=int(replay_load.get("total_row_count", 0) or 0),
        skipped_row_count=int(replay_load.get("skipped_row_count", 0) or 0),
    )

    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    dataset_path = base / "dataset.jsonl"
    summary_path = base / "summary.json"

    lines = [json.dumps(row, ensure_ascii=False) for row in payload["events"]]
    dataset_path.write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(payload["summary"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = payload["summary"]
    return {
        "input_path": str(source),
        "dataset_jsonl": str(dataset_path),
        "summary_json": str(summary_path),
        "event_count": int(summary.get("event_count", 0) or 0),
        "query_count": int(summary.get("query_count", 0) or 0),
    }


__all__ = ["build_reward_replay_payload", "write_reward_replay_artifacts"]
