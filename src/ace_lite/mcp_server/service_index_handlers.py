from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ace_lite.indexing_resilience import IndexingResilienceConfig


def handle_index_request(
    *,
    root_path: Path,
    language_csv: str,
    enabled_languages: list[str],
    output: str | None,
    batch_mode: bool,
    batch_size: int,
    timeout_per_file_seconds: float | None,
    resume: bool,
    resume_state_path: str | None,
    retry_timeouts: bool,
    subprocess_batch: bool,
    subprocess_batch_timeout_seconds: float | None,
    include_payload: bool,
    build_index_fn: Any,
    build_index_with_resilience_fn: Any,
    resolve_output_path_fn: Any,
) -> dict[str, Any]:
    effective_batch_mode = bool(
        batch_mode
        or resume
        or retry_timeouts
        or subprocess_batch
        or (timeout_per_file_seconds is not None and float(timeout_per_file_seconds) > 0)
        or (
            subprocess_batch_timeout_seconds is not None
            and float(subprocess_batch_timeout_seconds) > 0
        )
    )

    if effective_batch_mode:
        config = IndexingResilienceConfig(
            batch_size=int(batch_size),
            timeout_per_file_seconds=timeout_per_file_seconds,
            resume=bool(resume),
            resume_state_path=Path(resume_state_path or "context-map/index.resume.json"),
            retry_timeouts=bool(retry_timeouts),
            subprocess_batch=bool(subprocess_batch),
            subprocess_batch_timeout_seconds=subprocess_batch_timeout_seconds,
        )
        payload = build_index_with_resilience_fn(
            root_dir=str(root_path),
            languages=enabled_languages,
            config=config,
        )
    else:
        payload = build_index_fn(
            root_dir=str(root_path),
            languages=enabled_languages,
        )

    output_path = resolve_output_path_fn(
        root_path=root_path,
        output=output,
        default="context-map/index.json",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    response: dict[str, Any] = {
        "ok": True,
        "root": str(root_path),
        "languages": language_csv,
        "output": str(output_path),
        "file_count": len(payload.get("files", {}))
        if isinstance(payload.get("files"), dict)
        else 0,
    }
    if isinstance(payload.get("indexing_resilience"), dict):
        response["indexing_resilience"] = payload.get("indexing_resilience")
    if include_payload:
        response["index"] = payload
    return response


__all__ = ["handle_index_request"]
