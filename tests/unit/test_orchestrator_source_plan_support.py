from __future__ import annotations

from types import SimpleNamespace

from ace_lite.orchestrator_source_plan_support import (
    build_orchestrator_source_plan_runtime,
)


def test_build_orchestrator_source_plan_runtime_extracts_chunking_contract() -> None:
    config = SimpleNamespace(
        chunking=SimpleNamespace(
            top_k=24,
            per_file_limit=3,
            token_budget=1200,
            disclosure="refs",
        ),
        retrieval=SimpleNamespace(policy_version="2026-04"),
    )

    runtime = build_orchestrator_source_plan_runtime(
        config=config,
        pipeline_order=("memory", "index", "repomap", "augment", "skills", "source_plan"),
    )

    assert runtime.pipeline_order == (
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
        "source_plan",
    )
    assert runtime.chunk_top_k == 24
    assert runtime.chunk_per_file_limit == 3
    assert runtime.chunk_token_budget == 1200
    assert runtime.chunk_disclosure == "refs"
    assert runtime.policy_version == "2026-04"
