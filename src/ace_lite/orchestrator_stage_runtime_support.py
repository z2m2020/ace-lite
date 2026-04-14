from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.orchestrator_validation_support import (
    build_orchestrator_validation_runtime,
)
from ace_lite.pipeline.stages.repomap import run_repomap
from ace_lite.pipeline.stages.validation import run_validation_stage
from ace_lite.pipeline.types import StageContext


def run_orchestrator_repomap_stage(
    *,
    ctx: StageContext,
    config: Any,
    tokenizer_model: str,
) -> dict[str, Any]:
    return run_repomap(
        ctx=ctx,
        repomap_enabled=config.repomap.enabled,
        repomap_neighbor_limit=config.repomap.neighbor_limit,
        repomap_budget_tokens=config.repomap.budget_tokens,
        repomap_top_k=config.repomap.top_k,
        repomap_ranking_profile=config.repomap.ranking_profile,
        repomap_signal_weights=config.repomap.signal_weights,
        tokenizer_model=tokenizer_model,
        policy_version=config.retrieval.policy_version,
    )


def run_orchestrator_validation_stage(
    *,
    ctx: StageContext,
    config: Any,
    lsp_broker: Any,
    resolve_validation_preference_capture_store_fn: Callable[..., Any],
) -> dict[str, Any]:
    runtime = build_orchestrator_validation_runtime(ctx_state=ctx.state)
    preference_capture_store = resolve_validation_preference_capture_store_fn(
        root=ctx.root,
    )
    return run_validation_stage(
        root=ctx.root,
        query=ctx.query,
        source_plan_stage=runtime.source_plan_stage,
        index_stage=runtime.index_stage,
        enabled=config.validation.enabled,
        include_xref=config.validation.include_xref,
        top_n=config.validation.top_n,
        xref_top_n=config.validation.xref_top_n,
        sandbox_timeout_seconds=config.validation.sandbox_timeout_seconds,
        broker=lsp_broker,
        patch_artifact=runtime.patch_artifact,
        policy_name=runtime.policy_name,
        policy_version=runtime.policy_version or str(config.retrieval.policy_version),
        preference_capture_store=preference_capture_store,
        preference_capture_repo_key=ctx.repo,
    )


__all__ = [
    "run_orchestrator_repomap_stage",
    "run_orchestrator_validation_stage",
]
