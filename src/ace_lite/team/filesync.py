"""File-based TeamSync backend for shared filesystem workflows."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from .sync import TeamFact, TeamSyncBackend


def _parse_iso_timestamp(value: Any) -> float:
    if not isinstance(value, str):
        return 0.0
    text = value.strip()
    if not text:
        return 0.0
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return float(datetime.fromisoformat(text).timestamp())
    except ValueError:
        return 0.0


def _stable_fact_handle(fact: TeamFact) -> str:
    raw_handle = str(fact.get("handle") or "").strip()
    if raw_handle:
        return raw_handle
    payload = {
        "content": str(fact.get("content") or ""),
        "namespace": str(fact.get("namespace") or ""),
        "metadata": dict(fact.get("metadata") or {}),
    }
    source = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(source.encode('utf-8')).hexdigest()}"


class FileBasedTeamSync(TeamSyncBackend):
    """Team sync backend storing one JSON file per container tag."""

    def __init__(self, shared_path: str | Path) -> None:
        self._shared_path = Path(shared_path)

    def push(self, facts: list[TeamFact], container_tag: str) -> None:
        incoming: list[TeamFact] = list(facts)
        existing = self.pull(container_tag)
        merged = self.resolve_conflicts(local=incoming, remote=existing)
        path = self._resolve_container_path(container_tag)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(merged, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )

    def pull(self, container_tag: str) -> list[TeamFact]:
        path = self._resolve_container_path(container_tag)
        if not path.exists() or not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        rows: list[TeamFact] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(cast(TeamFact, dict(item)))
        return self._normalize_rows(rows)

    def resolve_conflicts(
        self,
        *,
        local: list[TeamFact],
        remote: list[TeamFact],
    ) -> list[TeamFact]:
        merged: dict[str, TeamFact] = {}
        for source in (remote, local):
            for fact in source:
                normalized = self._normalize_fact(fact)
                handle = _stable_fact_handle(normalized)
                previous = merged.get(handle)
                if previous is None:
                    merged[handle] = normalized
                    continue
                previous_ts = _parse_iso_timestamp(previous.get("updated_at"))
                current_ts = _parse_iso_timestamp(normalized.get("updated_at"))
                if current_ts >= previous_ts:
                    merged[handle] = normalized
        ordered = list(merged.values())
        ordered.sort(
            key=lambda row: (
                -_parse_iso_timestamp(row.get("updated_at")),
                str(row.get("handle") or ""),
            )
        )
        return ordered

    def _resolve_container_path(self, container_tag: str) -> Path:
        normalized = str(container_tag or "").strip().lower()
        if not normalized:
            normalized = "global"
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        safe_name = "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in normalized
        )
        safe_name = safe_name.strip("-") or "global"
        return self._shared_path / f"{safe_name}.{digest}.json"

    def _normalize_rows(self, rows: list[TeamFact]) -> list[TeamFact]:
        normalized = [self._normalize_fact(row) for row in rows]
        normalized.sort(
            key=lambda row: (
                -_parse_iso_timestamp(row.get("updated_at")),
                str(row.get("handle") or ""),
            )
        )
        return normalized

    def _normalize_fact(self, fact: TeamFact) -> TeamFact:
        normalized: TeamFact = {
            "content": str(fact.get("content") or "").strip(),
            "namespace": str(fact.get("namespace") or "").strip(),
            "updated_at": str(fact.get("updated_at") or "").strip(),
            "metadata": dict(fact.get("metadata") or {}),
        }
        handle = _stable_fact_handle({**fact, **normalized})
        normalized["handle"] = handle
        return normalized
