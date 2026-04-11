from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ace_lite.run_manifest_schema import RunManifestEntryV1, validate_run_manifest_entry

DEFAULT_RUN_MANIFEST_PATH = "context-map/run_manifest.jsonl"


def append_run_manifest_entry(
    *,
    manifest_path: str | Path = DEFAULT_RUN_MANIFEST_PATH,
    entry: RunManifestEntryV1 | dict[str, Any],
) -> dict[str, Any]:
    normalized = validate_run_manifest_entry(entry)
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True) + "\n")
    return normalized


def load_run_manifest_entries(*, manifest_path: str | Path) -> list[dict[str, Any]]:
    path = Path(manifest_path)
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"run manifest contains invalid JSON on line {line_number}"
                ) from exc
            rows.append(validate_run_manifest_entry(payload))
    return rows
