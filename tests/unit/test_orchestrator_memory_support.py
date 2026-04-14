from __future__ import annotations

from ace_lite.orchestrator_memory_support import (
    build_orchestrator_memory_runtime,
    normalize_temporal_input,
)
from ace_lite.signal_extractor import SignalExtraction


def test_normalize_temporal_input_trims_or_returns_none() -> None:
    assert normalize_temporal_input(None) is None
    assert normalize_temporal_input("  ") is None
    assert normalize_temporal_input("  7d ") == "7d"


def test_build_orchestrator_memory_runtime_normalizes_temporal_and_signal_state() -> None:
    runtime = build_orchestrator_memory_runtime(
        query="fix regression in runtime memory path",
        repo="demo",
        root="/repo",
        ctx_state={
            "temporal": {
                "time_range": " 30d ",
                "start_date": " 2026-04-01 ",
                "end_date": " ",
            }
        },
        resolve_memory_namespace_fn=lambda **_: ("repo:demo", "repo", "auto"),
        extract_signal_fn=lambda query: SignalExtraction(
            triggered=True,
            matched_keywords=("fix", "regression"),
            query_length=len(query),
            reason="keyword_match",
        ),
    )

    assert runtime.container_tag == "repo:demo"
    assert runtime.namespace_mode == "repo"
    assert runtime.namespace_source == "auto"
    assert runtime.time_range == "30d"
    assert runtime.start_date == "2026-04-01"
    assert runtime.end_date is None
    assert runtime.extraction.triggered is True
    assert runtime.extraction.matched_keywords == ("fix", "regression")
