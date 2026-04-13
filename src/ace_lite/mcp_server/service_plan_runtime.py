from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ace_lite.entrypoint_runtime import (
    MemoryProviderKwargs,
    build_memory_provider_kwargs,
)
from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.plan_request import (
    PlanRequestOptions,
    PlanRequestRunPlanKwargs,
)


def build_mcp_plan_memory_provider_kwargs(
    *,
    config: AceLiteMcpConfig,
    root_path: Path,
    options: PlanRequestOptions,
    memory_primary: str | None,
    memory_secondary: str | None,
) -> MemoryProviderKwargs:
    return build_memory_provider_kwargs(
        primary=str(memory_primary or config.memory_primary).strip().lower() or "none",
        secondary=str(memory_secondary or config.memory_secondary).strip().lower()
        or "none",
        memory_strategy="hybrid",
        memory_hybrid_limit=20,
        memory_cache_enabled=True,
        memory_cache_path=str(root_path / "context-map" / "memory_cache.jsonl"),
        memory_cache_ttl_seconds=604800,
        memory_cache_max_entries=5000,
        memory_notes_enabled=bool(options.memory_notes_enabled),
        mcp_base_url=config.mcp_base_url,
        rest_base_url=config.rest_base_url,
        timeout_seconds=config.memory_timeout,
        user_id=config.user_id,
        app=config.app,
        limit=config.memory_limit,
    )


def execute_mcp_plan_payload(
    *,
    create_memory_provider_fn: Callable[..., Any],
    run_plan_fn: Callable[..., dict[str, Any]],
    config: AceLiteMcpConfig,
    normalized_query: str,
    resolved_repo: str,
    root_path: Path,
    skills_path: Path,
    time_range: str | None,
    start_date: str | None,
    end_date: str | None,
    memory_primary: str | None,
    memory_secondary: str | None,
    options: PlanRequestOptions,
) -> dict[str, Any]:
    memory_provider_kwargs = build_mcp_plan_memory_provider_kwargs(
        config=config,
        root_path=root_path,
        options=options,
        memory_primary=memory_primary,
        memory_secondary=memory_secondary,
    )
    memory_provider = create_memory_provider_fn(**memory_provider_kwargs)
    run_plan_kwargs: PlanRequestRunPlanKwargs = options.to_run_plan_kwargs()
    return run_plan_fn(
        query=normalized_query,
        repo=resolved_repo,
        root=str(root_path),
        skills_dir=str(skills_path),
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        memory_provider=memory_provider,
        **run_plan_kwargs,
    )


__all__ = [
    "build_mcp_plan_memory_provider_kwargs",
    "execute_mcp_plan_payload",
]
