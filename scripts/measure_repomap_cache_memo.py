from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ace_lite.repomap.cache import (
    load_cached_repomap_checked,
    load_cached_repomap_precompute_checked,
)


def _read_cache_file(*, path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _first_entry_key(*, payload: dict[str, Any]) -> str | None:
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return None
    first = entries[0]
    if not isinstance(first, dict):
        return None
    key = str(first.get("key") or "").strip()
    return key or None


def _measure_loader(
    *,
    label: str,
    cache_path: Path,
    loader: Callable[..., dict[str, Any] | None],
    loops: int,
) -> dict[str, Any]:
    file_payload = _read_cache_file(path=cache_path)
    if file_payload is None:
        return {
            "label": label,
            "cache_path": str(cache_path),
            "ok": False,
            "error": "cache_missing_or_invalid",
        }

    key = _first_entry_key(payload=file_payload)
    if key is None:
        return {
            "label": label,
            "cache_path": str(cache_path),
            "ok": False,
            "schema_version": str(file_payload.get("schema_version") or ""),
            "entries_count": len(file_payload.get("entries", []) or []),
            "error": "cache_has_no_entries",
        }

    try:
        size_bytes = cache_path.stat().st_size
    except OSError:
        size_bytes = 0

    max_age_seconds = 10**9
    t0 = time.perf_counter()
    first = loader(
        cache_path=cache_path,
        key=key,
        max_age_seconds=max_age_seconds,
        required_meta=None,
    )
    first_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    second = loader(
        cache_path=cache_path,
        key=key,
        max_age_seconds=max_age_seconds,
        required_meta=None,
    )
    second_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    hits = 0
    for _ in range(max(0, int(loops))):
        if loader(
            cache_path=cache_path,
            key=key,
            max_age_seconds=max_age_seconds,
            required_meta=None,
        ):
            hits += 1
    loop_ms = (time.perf_counter() - t0) * 1000.0
    avg_ms = loop_ms / max(1, int(loops))

    return {
        "label": label,
        "cache_path": str(cache_path),
        "ok": bool(first is not None and second is not None),
        "schema_version": str(file_payload.get("schema_version") or ""),
        "entries_count": len(file_payload.get("entries", []) or []),
        "size_bytes": int(size_bytes),
        "key": key,
        "first_ms": round(first_ms, 3),
        "second_ms": round(second_ms, 3),
        "avg_loop_ms": round(avg_ms, 6),
        "loop_hits": int(hits),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure in-process memoization of repomap cache file loads."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root containing context-map/repomap/*.",
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=50,
        help="How many repeated loads to average for memo hits.",
    )
    args = parser.parse_args()

    root = Path(str(args.root)).resolve()
    repomap_dir = root / "context-map" / "repomap"
    cache_path = repomap_dir / "cache.json"
    precompute_path = repomap_dir / "precompute_cache.json"

    report = {
        "root": str(root),
        "generated_at_epoch": round(time.time(), 3),
        "loops": int(args.loops),
        "results": [
            _measure_loader(
                label="repomap_cache",
                cache_path=cache_path,
                loader=load_cached_repomap_checked,
                loops=int(args.loops),
            ),
            _measure_loader(
                label="repomap_precompute_cache",
                cache_path=precompute_path,
                loader=load_cached_repomap_precompute_checked,
                loops=int(args.loops),
            ),
        ],
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

