from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ace_lite.mcp_server.service import AceLiteMcpService

MCP_TOOL_DESCRIPTIONS: dict[str, str] = {
    "ace_health": "Return ACE-Lite MCP server health and default runtime settings.",
    "ace_index": "Build repository distilled index and persist it under context-map.",
    "ace_repomap_build": "Build repo map JSON/Markdown artifacts from current repository index.",
    "ace_plan_quick": "Fast candidate-file plan from index + repomap (for low-latency first pass).",
    "ace_plan": "Run ACE-Lite deterministic pipeline and return source plan payload.",
    "ace_memory_search": "Search local ACE-Lite notes memory by lexical matching.",
    "ace_memory_graph_view": "Build a read-only long-term memory graph view payload for CLI/MCP/UI.",
    "ace_memory_store": "Store a memory note into local ACE-Lite JSONL memory.",
    "ace_memory_wipe": "Wipe local ACE-Lite memory notes (optionally by namespace).",
    "ace_feedback_record": "Record a selection feedback event into local profile storage.",
    "ace_feedback_stats": "Summarize stored selection feedback and computed boosts.",
    "ace_issue_report_record": "Record a structured issue report into the local issue report store.",
    "ace_issue_report_list": "List structured issue reports from the local issue report store.",
    "ace_issue_report_export_case": "Export an issue report into a benchmark case YAML entry.",
    "ace_issue_report_apply_fix": "Apply a stored developer fix to an issue report resolution.",
    "ace_dev_issue_record": "Record a developer-side issue into the local dev feedback store.",
    "ace_dev_issue_from_runtime": "Promote an auto-captured runtime event into a developer-side issue.",
    "ace_dev_issue_apply_fix": "Apply a stored developer fix to a developer-side issue resolution.",
    "ace_dev_fix_record": "Record a developer-side fix into the local dev feedback store.",
    "ace_dev_feedback_summary": "Summarize stored developer issues and fixes from the local dev feedback store.",
}

MCP_REGISTERED_TOOL_NAMES: tuple[str, ...] = tuple(MCP_TOOL_DESCRIPTIONS.keys())


def _tool(server: FastMCP, name: str):
    return server.tool(name=name, description=MCP_TOOL_DESCRIPTIONS[name])


def _register_core_tools(*, server: FastMCP, service: AceLiteMcpService) -> None:
    @_tool(server, "ace_health")
    def ace_health() -> dict[str, Any]:
        return service.health()

    @_tool(server, "ace_index")
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

    @_tool(server, "ace_repomap_build")
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

    @_tool(server, "ace_plan_quick")
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

    @_tool(server, "ace_plan")
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


def _register_memory_tools(*, server: FastMCP, service: AceLiteMcpService) -> None:
    @_tool(server, "ace_memory_search")
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

    @_tool(server, "ace_memory_graph_view")
    def ace_memory_graph_view(
        db_path: str | None = None,
        fact_handle: str | None = None,
        seeds: list[str] | None = None,
        repo: str | None = None,
        namespace: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        as_of: str | None = None,
        max_hops: int = 1,
        limit: int = 8,
        root: str | None = None,
    ) -> dict[str, Any]:
        return service.memory_graph_view(
            db_path=db_path,
            fact_handle=fact_handle,
            seeds=seeds or [],
            repo=repo,
            namespace=namespace,
            user_id=user_id,
            profile_key=profile_key,
            as_of=as_of,
            max_hops=max_hops,
            limit=limit,
            root=root,
        )

    @_tool(server, "ace_memory_store")
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

    @_tool(server, "ace_memory_wipe")
    def ace_memory_wipe(
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        return service.memory_wipe(namespace=namespace, notes_path=notes_path)


def _register_feedback_tools(*, server: FastMCP, service: AceLiteMcpService) -> None:
    @_tool(server, "ace_feedback_record")
    def ace_feedback_record(
        query: str,
        selected_path: str,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        root: str | None = None,
        profile_path: str | None = None,
        position: int | None = None,
        max_entries: int = 512,
    ) -> dict[str, Any]:
        return service.feedback_record(
            query=query,
            selected_path=selected_path,
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            root=root,
            profile_path=profile_path,
            position=position,
            max_entries=max_entries,
        )

    @_tool(server, "ace_feedback_stats")
    def ace_feedback_stats(
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
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
            user_id=user_id,
            profile_key=profile_key,
            root=root,
            profile_path=profile_path,
            query=query,
            boost_per_select=boost_per_select,
            max_boost=max_boost,
            decay_days=decay_days,
            top_n=top_n,
            max_entries=max_entries,
        )

    @_tool(server, "ace_issue_report_record")
    def ace_issue_report_record(
        title: str,
        query: str,
        actual_behavior: str,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        root: str | None = None,
        store_path: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        expected_behavior: str | None = None,
        repro_steps: list[str] | None = None,
        selected_path: str | None = None,
        plan_payload_ref: str | None = None,
        attachments: list[str] | None = None,
        occurred_at: str | None = None,
        resolved_at: str | None = None,
        resolution_note: str | None = None,
        issue_id: str | None = None,
    ) -> dict[str, Any]:
        return service.issue_report_record(
            title=title,
            query=query,
            actual_behavior=actual_behavior,
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            root=root,
            store_path=store_path,
            category=category,
            severity=severity,
            status=status,
            expected_behavior=expected_behavior,
            repro_steps=repro_steps,
            selected_path=selected_path,
            plan_payload_ref=plan_payload_ref,
            attachments=attachments,
            occurred_at=occurred_at,
            resolved_at=resolved_at,
            resolution_note=resolution_note,
            issue_id=issue_id,
        )

    @_tool(server, "ace_issue_report_list")
    def ace_issue_report_list(
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        root: str | None = None,
        store_path: str | None = None,
        status: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return service.issue_report_list(
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            root=root,
            store_path=store_path,
            status=status,
            category=category,
            severity=severity,
            limit=limit,
        )

    @_tool(server, "ace_issue_report_export_case")
    def ace_issue_report_export_case(
        issue_id: str,
        root: str | None = None,
        store_path: str | None = None,
        output_path: str = "benchmark/cases/feedback_issue_reports.yaml",
        case_id: str | None = None,
        comparison_lane: str = "issue_report_feedback",
        top_k: int = 8,
        min_validation_tests: int = 1,
        append: bool = True,
    ) -> dict[str, Any]:
        return service.issue_report_export_case(
            issue_id=issue_id,
            root=root,
            store_path=store_path,
            output_path=output_path,
            case_id=case_id,
            comparison_lane=comparison_lane,
            top_k=top_k,
            min_validation_tests=min_validation_tests,
            append=append,
        )

    @_tool(server, "ace_issue_report_apply_fix")
    def ace_issue_report_apply_fix(
        issue_id: str,
        fix_id: str,
        root: str | None = None,
        issue_store_path: str | None = None,
        dev_feedback_path: str | None = None,
        status: str = "resolved",
        resolved_at: str | None = None,
    ) -> dict[str, Any]:
        return service.issue_report_apply_fix(
            issue_id=issue_id,
            fix_id=fix_id,
            root=root,
            issue_store_path=issue_store_path,
            dev_feedback_path=dev_feedback_path,
            status=status,
            resolved_at=resolved_at,
        )

    @_tool(server, "ace_dev_issue_record")
    def ace_dev_issue_record(
        title: str,
        reason_code: str,
        repo: str,
        store_path: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        query: str | None = None,
        selected_path: str | None = None,
        related_invocation_id: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        resolved_at: str | None = None,
        issue_id: str | None = None,
    ) -> dict[str, Any]:
        return service.dev_issue_record(
            title=title,
            reason_code=reason_code,
            repo=repo,
            store_path=store_path,
            user_id=user_id,
            profile_key=profile_key,
            query=query,
            selected_path=selected_path,
            related_invocation_id=related_invocation_id,
            notes=notes,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            issue_id=issue_id,
        )

    @_tool(server, "ace_dev_fix_record")
    def ace_dev_fix_record(
        reason_code: str,
        repo: str,
        resolution_note: str,
        store_path: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        issue_id: str | None = None,
        query: str | None = None,
        selected_path: str | None = None,
        related_invocation_id: str | None = None,
        created_at: str | None = None,
        fix_id: str | None = None,
    ) -> dict[str, Any]:
        return service.dev_fix_record(
            reason_code=reason_code,
            repo=repo,
            resolution_note=resolution_note,
            store_path=store_path,
            user_id=user_id,
            profile_key=profile_key,
            issue_id=issue_id,
            query=query,
            selected_path=selected_path,
            related_invocation_id=related_invocation_id,
            created_at=created_at,
            fix_id=fix_id,
        )

    @_tool(server, "ace_dev_issue_from_runtime")
    def ace_dev_issue_from_runtime(
        invocation_id: str,
        stats_db_path: str | None = None,
        store_path: str | None = None,
        reason_code: str | None = None,
        title: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        issue_id: str | None = None,
    ) -> dict[str, Any]:
        return service.dev_issue_from_runtime(
            invocation_id=invocation_id,
            stats_db_path=stats_db_path,
            store_path=store_path,
            reason_code=reason_code,
            title=title,
            notes=notes,
            status=status,
            user_id=user_id,
            profile_key=profile_key,
            issue_id=issue_id,
        )

    @_tool(server, "ace_dev_issue_apply_fix")
    def ace_dev_issue_apply_fix(
        issue_id: str,
        fix_id: str,
        store_path: str | None = None,
        status: str | None = None,
        resolved_at: str | None = None,
    ) -> dict[str, Any]:
        return service.dev_issue_apply_fix(
            issue_id=issue_id,
            fix_id=fix_id,
            store_path=store_path,
            status=status,
            resolved_at=resolved_at,
        )

    @_tool(server, "ace_dev_feedback_summary")
    def ace_dev_feedback_summary(
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        store_path: str | None = None,
    ) -> dict[str, Any]:
        return service.dev_feedback_summary(
            repo=repo,
            user_id=user_id,
            profile_key=profile_key,
            store_path=store_path,
        )


def register_mcp_tools(*, server: FastMCP, service: AceLiteMcpService) -> None:
    _register_core_tools(server=server, service=service)
    _register_memory_tools(server=server, service=service)
    _register_feedback_tools(server=server, service=service)


__all__ = [
    "MCP_REGISTERED_TOOL_NAMES",
    "MCP_TOOL_DESCRIPTIONS",
    "register_mcp_tools",
]
