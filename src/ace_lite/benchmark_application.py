from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ace_lite.entrypoint_runtime import (
    MemoryProviderKwargs,
    OrchestratorRuntimeKwargs,
    build_memory_provider_kwargs_from_resolved,
    build_orchestrator_kwargs_from_resolved,
)


def create_benchmark_orchestrator_from_resolved(
    *,
    create_memory_provider_fn: Callable[..., Any],
    create_orchestrator_fn: Callable[..., Any],
    resolved: Mapping[str, Any],
    skills_dir: str,
    retrieval_policy: str,
    memory_primary: str,
    memory_secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    memory_timeout: float,
    user_id: str | None,
    app: str | None,
    memory_limit: int,
) -> Any:
    memory_provider_kwargs: MemoryProviderKwargs = (
        build_memory_provider_kwargs_from_resolved(
            resolved=resolved,
            primary=memory_primary,
            secondary=memory_secondary,
            mcp_base_url=mcp_base_url,
            rest_base_url=rest_base_url,
            timeout_seconds=memory_timeout,
            user_id=user_id,
            app=app,
            limit=memory_limit,
        )
    )
    memory_provider = create_memory_provider_fn(**memory_provider_kwargs)
    orchestrator_kwargs: OrchestratorRuntimeKwargs = (
        build_orchestrator_kwargs_from_resolved(
            resolved=resolved,
            skills_dir=skills_dir,
            retrieval_policy=retrieval_policy,
        )
    )
    return create_orchestrator_fn(
        memory_provider=memory_provider,
        **orchestrator_kwargs,
    )


__all__ = ["create_benchmark_orchestrator_from_resolved"]
