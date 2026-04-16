from __future__ import annotations

from pathlib import PurePosixPath
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
        memory=SimpleNamespace(
            capture=SimpleNamespace(notes_path="context-map/custom_notes.jsonl"),
        ),
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
    assert runtime.handoff_artifact_dir == "artifacts/handoffs/latest"
    assert runtime.handoff_notes_path == "context-map/custom_notes.jsonl"


def test_build_orchestrator_source_plan_runtime_uses_posix_defaults_on_all_platforms() -> None:
    config = SimpleNamespace(
        chunking=SimpleNamespace(
            top_k=24,
            per_file_limit=3,
            token_budget=1200,
            disclosure="refs",
        ),
        retrieval=SimpleNamespace(policy_version="2026-04"),
        memory=SimpleNamespace(
            capture=SimpleNamespace(notes_path=""),
        ),
    )

    runtime = build_orchestrator_source_plan_runtime(
        config=config,
        pipeline_order=("memory", "index", "repomap", "augment", "skills", "source_plan"),
    )

    assert runtime.handoff_artifact_dir == PurePosixPath(
        "artifacts", "handoffs", "latest"
    ).as_posix()
    assert runtime.handoff_notes_path == PurePosixPath(
        "context-map", "memory_notes.jsonl"
    ).as_posix()
