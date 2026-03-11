from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.service import AceLiteMcpService


def build_mcp_server(*, config: AceLiteMcpConfig) -> FastMCP:
    service = AceLiteMcpService(config=config)
    server = FastMCP(
        name=config.server_name,
        instructions=(
            "ACE-Lite tools for deterministic code context planning, indexing, "
            "repomap generation, and local memory note operations."
        ),
        log_level="INFO",
    )

    @server.tool(
        name="ace_health",
        description="Return ACE-Lite MCP server health and default runtime settings.",
    )
    def ace_health() -> dict[str, Any]:
        return service.health()

    @server.tool(
        name="ace_index",
        description="Build repository distilled index and persist it under context-map.",
    )
    def ace_index(
        root: str | None = None,
        languages: str | None = None,
        output: str | None = None,
        batch_mode: bool = False,
        batch_size: int = 200,
        timeout_per_file_seconds: float | None = None,
        resume: bool = False,
        resume_state_path: str | None = None,
        retry_timeouts: bool = False,
        subprocess_batch: bool = False,
        subprocess_batch_timeout_seconds: float | None = None,
        include_payload: bool = False,
    ) -> dict[str, Any]:
        return service.index(
            root=root,
            languages=languages,
            output=output,
            batch_mode=bool(batch_mode),
            batch_size=int(batch_size),
            timeout_per_file_seconds=timeout_per_file_seconds,
            resume=bool(resume),
            resume_state_path=resume_state_path,
            retry_timeouts=bool(retry_timeouts),
            subprocess_batch=bool(subprocess_batch),
            subprocess_batch_timeout_seconds=subprocess_batch_timeout_seconds,
            include_payload=bool(include_payload),
        )

    @server.tool(
        name="ace_repomap_build",
        description="Build repo map JSON/Markdown artifacts from current repository index.",
    )
    def ace_repomap_build(
        root: str | None = None,
        languages: str | None = None,
        budget_tokens: int = 800,
        top_k: int = 40,
        ranking_profile: str = "heuristic",
        output_json: str | None = None,
        output_md: str | None = None,
    ) -> dict[str, Any]:
        return service.repomap_build(
            root=root,
            languages=languages,
            budget_tokens=budget_tokens,
            top_k=top_k,
            ranking_profile=ranking_profile,
            output_json=output_json,
            output_md=output_md,
        )

    @server.tool(
        name="ace_plan_quick",
        description="Fast candidate-file plan from index + repomap (for low-latency first pass).",
    )
    def ace_plan_quick(
        query: str,
        repo: str | None = None,
        root: str | None = None,
        languages: str | None = None,
        top_k_files: int = 8,
        repomap_top_k: int = 24,
        candidate_ranker: str = "rrf_hybrid",
        index_cache_path: str = "context-map/index.json",
        index_incremental: bool = True,
        repomap_expand: bool = False,
        repomap_neighbor_limit: int = 20,
        repomap_neighbor_depth: int = 1,
        budget_tokens: int = 800,
        ranking_profile: str = "graph",
        include_rows: bool = False,
    ) -> dict[str, Any]:
        return service.plan_quick(
            query=query,
            repo=repo,
            root=root,
            languages=languages,
            top_k_files=top_k_files,
            repomap_top_k=repomap_top_k,
            candidate_ranker=candidate_ranker,
            index_cache_path=index_cache_path,
            index_incremental=index_incremental,
            repomap_expand=repomap_expand,
            repomap_neighbor_limit=repomap_neighbor_limit,
            repomap_neighbor_depth=repomap_neighbor_depth,
            budget_tokens=budget_tokens,
            ranking_profile=ranking_profile,
            include_rows=bool(include_rows),
        )

    @server.tool(
        name="ace_plan",
        description="Run ACE-Lite deterministic pipeline and return source plan payload.",
    )
    def ace_plan(
        query: str,
        repo: str | None = None,
        root: str | None = None,
        skills_dir: str | None = None,
        config_pack: str | None = None,
        time_range: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        memory_primary: str | None = None,
        memory_secondary: str | None = None,
        lsp_enabled: bool = False,
        plugins_enabled: bool = False,
        top_k_files: int = 8,
        min_candidate_score: int = 2,
        retrieval_policy: str = "auto",
        include_full_payload: bool = True,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return service.plan(
            query=query,
            repo=repo,
            root=root,
            skills_dir=skills_dir,
            config_pack=config_pack,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            memory_primary=memory_primary,
            memory_secondary=memory_secondary,
            lsp_enabled=bool(lsp_enabled),
            plugins_enabled=bool(plugins_enabled),
            top_k_files=top_k_files,
            min_candidate_score=min_candidate_score,
            retrieval_policy=retrieval_policy,
            include_full_payload=bool(include_full_payload),
            timeout_seconds=timeout_seconds,
        )

    @server.tool(
        name="ace_memory_search",
        description="Search local ACE-Lite notes memory by lexical matching.",
    )
    def ace_memory_search(
        query: str,
        limit: int = 5,
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        return service.memory_search(
            query=query,
            limit=limit,
            namespace=namespace,
            notes_path=notes_path,
        )

    @server.tool(
        name="ace_memory_store",
        description="Store a memory note into local ACE-Lite JSONL memory.",
    )
    def ace_memory_store(
        text: str,
        namespace: str | None = None,
        tags: dict[str, str] | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        return service.memory_store(
            text=text,
            namespace=namespace,
            tags=tags,
            notes_path=notes_path,
        )

    @server.tool(
        name="ace_memory_wipe",
        description="Wipe local ACE-Lite memory notes (optionally by namespace).",
    )
    def ace_memory_wipe(
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        return service.memory_wipe(namespace=namespace, notes_path=notes_path)

    @server.tool(
        name="ace_feedback_record",
        description="Record a selection feedback event into local profile storage.",
    )
    def ace_feedback_record(
        query: str,
        selected_path: str,
        repo: str | None = None,
        root: str | None = None,
        profile_path: str | None = None,
        position: int | None = None,
        max_entries: int = 512,
    ) -> dict[str, Any]:
        return service.feedback_record(
            query=query,
            selected_path=selected_path,
            repo=repo,
            root=root,
            profile_path=profile_path,
            position=position,
            max_entries=max_entries,
        )

    @server.tool(
        name="ace_feedback_stats",
        description="Summarize stored selection feedback and computed boosts.",
    )
    def ace_feedback_stats(
        repo: str | None = None,
        root: str | None = None,
        profile_path: str | None = None,
        query: str | None = None,
        boost_per_select: float = 0.15,
        max_boost: float = 0.6,
        decay_days: float = 60.0,
        top_n: int = 10,
        max_entries: int = 512,
    ) -> dict[str, Any]:
        return service.feedback_stats(
            repo=repo,
            root=root,
            profile_path=profile_path,
            query=query,
            boost_per_select=boost_per_select,
            max_boost=max_boost,
            decay_days=decay_days,
            top_n=top_n,
            max_entries=max_entries,
        )

    return server


__all__ = ["build_mcp_server"]
