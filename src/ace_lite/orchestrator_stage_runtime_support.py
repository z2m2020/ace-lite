from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.orchestrator_augment_support import (
    build_orchestrator_augment_runtime,
    resolve_augment_candidates,
)
from ace_lite.orchestrator_validation_support import (
    build_orchestrator_validation_runtime,
)
from ace_lite.pipeline.stages.augment import run_diagnostics_augment
from ace_lite.pipeline.stages.index import IndexStageConfig, run_index
from ace_lite.pipeline.stages.repomap import run_repomap
from ace_lite.pipeline.stages.validation import run_validation_stage
from ace_lite.pipeline.types import StageContext


def run_orchestrator_index_stage(
    *,
    ctx: StageContext,
    config: Any,
    tokenizer_model: str,
    cochange_neighbor_cap: int,
    cochange_min_neighbor_score: float,
    cochange_max_boost: float,
) -> dict[str, Any]:
    return run_index(
        ctx=ctx,
        config=IndexStageConfig.from_orchestrator_config(
            config=config,
            tokenizer_model=tokenizer_model,
            cochange_neighbor_cap=cochange_neighbor_cap,
            cochange_min_neighbor_score=cochange_min_neighbor_score,
            cochange_max_boost=cochange_max_boost,
        ),
    )


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


def run_orchestrator_augment_stage(
    *,
    ctx: StageContext,
    config: Any,
    lsp_broker: Any,
) -> dict[str, Any]:
    runtime = build_orchestrator_augment_runtime(ctx_state=ctx.state)
    candidates = resolve_augment_candidates(
        index_stage=runtime.index_stage,
        repomap_stage=runtime.repomap_stage,
        index_files=runtime.index_files,
    )
    payload = run_diagnostics_augment(
        root=ctx.root,
        query=ctx.query,
        index_stage={"candidate_files": candidates},
        enabled=config.lsp.enabled,
        top_n=config.lsp.top_n,
        broker=lsp_broker,
        xref_enabled=config.lsp.xref_enabled,
        xref_top_n=config.lsp.xref_top_n,
        xref_time_budget_ms=config.lsp.time_budget_ms,
        candidate_chunks=runtime.candidate_chunks,
        junit_xml_path=config.tests.junit_xml,
        coverage_json_path=config.tests.coverage_json,
        sbfl_json_path=config.tests.sbfl_json,
        sbfl_metric=config.tests.sbfl_metric,
        vcs_enabled=config.cochange.enabled,
        vcs_worktree_override=runtime.vcs_worktree_override,
    )
    payload["policy_name"] = runtime.policy_name
    payload["policy_version"] = (
        runtime.policy_version or str(config.retrieval.policy_version)
    )
    return payload


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
    "run_orchestrator_augment_stage",
    "run_orchestrator_index_stage",
    "run_orchestrator_repomap_stage",
    "run_orchestrator_validation_stage",
]
