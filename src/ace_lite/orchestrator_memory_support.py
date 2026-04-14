from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.signal_extractor import SignalExtraction


def normalize_temporal_input(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


@dataclass(slots=True)
class OrchestratorMemoryRuntime:
    container_tag: str | None
    namespace_mode: str
    namespace_source: str
    time_range: str | None
    start_date: str | None
    end_date: str | None
    extraction: SignalExtraction


def build_orchestrator_memory_runtime(
    *,
    query: str,
    repo: str,
    root: str,
    ctx_state: dict[str, Any],
    resolve_memory_namespace_fn: Any,
    extract_signal_fn: Any,
) -> OrchestratorMemoryRuntime:
    container_tag, namespace_mode, namespace_source = resolve_memory_namespace_fn(
        repo=repo,
        root=root,
    )
    temporal_input = (
        ctx_state.get("temporal", {})
        if isinstance(ctx_state.get("temporal"), dict)
        else {}
    )
    extraction = extract_signal_fn(query)
    return OrchestratorMemoryRuntime(
        container_tag=container_tag,
        namespace_mode=namespace_mode,
        namespace_source=namespace_source,
        time_range=normalize_temporal_input(temporal_input.get("time_range")),
        start_date=normalize_temporal_input(temporal_input.get("start_date")),
        end_date=normalize_temporal_input(temporal_input.get("end_date")),
        extraction=extraction,
    )


__all__ = [
    "OrchestratorMemoryRuntime",
    "build_orchestrator_memory_runtime",
    "normalize_temporal_input",
]
