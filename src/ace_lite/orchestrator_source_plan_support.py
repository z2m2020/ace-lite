from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


@dataclass(slots=True)
class OrchestratorSourcePlanRuntime:
    pipeline_order: tuple[str, ...]
    chunk_top_k: int
    chunk_per_file_limit: int
    chunk_token_budget: int
    chunk_disclosure: str
    policy_version: str
    handoff_artifact_dir: str
    handoff_notes_path: str


def _repo_relative_posix_path(*parts: str) -> str:
    """Return a stable repo-relative path string regardless of local OS."""

    return PurePosixPath(*parts).as_posix()


def build_orchestrator_source_plan_runtime(
    *,
    config: Any,
    pipeline_order: tuple[str, ...] | list[str],
) -> OrchestratorSourcePlanRuntime:
    chunking = config.chunking
    retrieval = config.retrieval
    return OrchestratorSourcePlanRuntime(
        pipeline_order=tuple(str(item) for item in pipeline_order),
        chunk_top_k=int(chunking.top_k),
        chunk_per_file_limit=int(chunking.per_file_limit),
        chunk_token_budget=int(chunking.token_budget),
        chunk_disclosure=str(chunking.disclosure),
        policy_version=str(retrieval.policy_version),
        handoff_artifact_dir=_repo_relative_posix_path("artifacts", "handoffs", "latest"),
        handoff_notes_path=str(
            config.memory.capture.notes_path
            or _repo_relative_posix_path("context-map", "memory_notes.jsonl")
        ),
    )


__all__ = [
    "OrchestratorSourcePlanRuntime",
    "build_orchestrator_source_plan_runtime",
]
