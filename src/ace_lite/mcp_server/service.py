"""MCP server exposing ACE-Lite capabilities as tools.

This module provides a production-ready stdio MCP server built on FastMCP.
It can also run in a self-test mode for health validation.
"""

from __future__ import annotations

import logging
import os
import sys
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, cast

from ace_lite.cli_app.orchestrator_factory import create_memory_provider, run_plan
from ace_lite.cli_app.runtime_settings_support import (
    build_runtime_settings_governance_payload,
    resolve_runtime_settings_bundle,
)
from ace_lite.indexer import build_index
from ace_lite.indexing_resilience import build_index_with_resilience
from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.file_support import (
    append_note,
    iter_notes,
    load_notes,
    resolve_config_pack_path,
    resolve_notes_path,
    resolve_output_path,
    resolve_root,
    resolve_skills_dir,
    save_notes,
    wipe_notes,
)
from ace_lite.mcp_server.plan_request import resolve_plan_request_options
from ace_lite.mcp_server.service_dev_feedback_handlers import (
    handle_dev_feedback_summary_request,
    handle_dev_fix_record_request,
    handle_dev_issue_apply_fix_request,
    handle_dev_issue_from_runtime_request,
    handle_dev_issue_record_request,
)
from ace_lite.mcp_server.service_feedback_handlers import (
    handle_feedback_record_request,
    handle_feedback_stats_request,
)
from ace_lite.mcp_server.service_health import (
    build_health_response_payload,
    build_runtime_identity_payload,
    resolve_runtime_source_tree,
)
from ace_lite.mcp_server.service_index_handlers import handle_index_request
from ace_lite.mcp_server.service_issue_report_handlers import (
    handle_issue_report_apply_fix_request,
    handle_issue_report_export_case_request,
    handle_issue_report_list_request,
    handle_issue_report_record_request,
)
from ace_lite.mcp_server.service_memory_handlers import (
    handle_memory_graph_view,
    handle_memory_search,
    handle_memory_store,
)
from ace_lite.mcp_server.service_plan_handlers import (
    handle_plan_quick_request,
    handle_plan_request,
)
from ace_lite.mcp_server.service_plan_runtime import execute_mcp_plan_payload
from ace_lite.mcp_server.service_repomap_handlers import handle_repomap_build_request
from ace_lite.mcp_server.service_retrieval_graph_view_handlers import (
    handle_retrieval_graph_view_request,
)
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.plan_quick import build_plan_quick
from ace_lite.repomap.builder import build_repo_map
from ace_lite.runtime_settings_store import (
    DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
)
from ace_lite.skills_contract import build_skills_catalog_contract
from ace_lite.vcs_history import collect_git_head_snapshot
from ace_lite.version import get_update_status, get_version, get_version_info

logger = logging.getLogger(__name__)
_RECENT_REQUEST_LIMIT = 10
_SLOW_REQUEST_THRESHOLD_MS = 1000.0


class AceLiteMcpService:
    def __init__(self, *, config: AceLiteMcpConfig) -> None:
        self._config = config
        self._process_id = os.getpid()
        self._parent_process_id = os.getppid()
        self._process_started_at_dt = datetime.now(timezone.utc)
        self._process_started_at = self._process_started_at_dt.isoformat()
        self._startup_cwd = str(Path.cwd())
        self._python_executable = str(sys.executable or "").strip()
        self._command_line = [str(item) for item in sys.argv if str(item).strip()]
        self._runtime_source_tree = resolve_runtime_source_tree(module_path=__file__)
        self._startup_head_snapshot = self._collect_runtime_head_snapshot()
        self._stats_lock = Lock()
        self._active_request_count = 0
        self._total_request_count = 0
        self._last_request_started_at = ""
        self._last_request_finished_at = ""
        self._last_request_tool = ""
        self._last_request_elapsed_ms = 0.0
        self._last_request_status = "idle"
        self._last_request_error: dict[str, Any] | None = None
        self._recent_requests: deque[dict[str, Any]] = deque(maxlen=_RECENT_REQUEST_LIMIT)

    @property
    def config(self) -> AceLiteMcpConfig:
        return self._config

    def _begin_request(self, tool_name: str) -> tuple[float, str]:
        started = perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        with self._stats_lock:
            self._active_request_count += 1
            self._total_request_count += 1
            self._last_request_tool = str(tool_name or "").strip()
            self._last_request_started_at = started_at
            self._last_request_status = "running"
            self._last_request_error = None
        return started, started_at

    def _finish_request(
        self,
        *,
        tool_name: str,
        started: float,
        started_at: str,
        status: str,
        error: dict[str, Any] | None,
    ) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
        request_record = {
            "tool": str(tool_name or "").strip(),
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_ms": elapsed_ms,
            "status": status,
            "slow": bool(elapsed_ms >= _SLOW_REQUEST_THRESHOLD_MS),
            "error": dict(error) if isinstance(error, dict) else None,
        }
        with self._stats_lock:
            self._active_request_count = max(0, self._active_request_count - 1)
            self._last_request_finished_at = finished_at
            self._last_request_elapsed_ms = elapsed_ms
            self._last_request_status = status
            self._last_request_error = dict(error) if isinstance(error, dict) else None
            self._recent_requests.append(request_record)

    def _request_stats_payload(self) -> dict[str, Any]:
        with self._stats_lock:
            current_request_runtime_ms = 0.0
            if self._active_request_count > 0 and self._last_request_started_at:
                try:
                    started_dt = datetime.fromisoformat(self._last_request_started_at)
                    current_request_runtime_ms = max(
                        0.0,
                        round(
                            (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000.0,
                            3,
                        ),
                    )
                except ValueError:
                    current_request_runtime_ms = 0.0
            return {
                "active_request_count": int(self._active_request_count),
                "total_request_count": int(self._total_request_count),
                "last_request_tool": str(self._last_request_tool or "").strip(),
                "last_request_started_at": str(self._last_request_started_at or "").strip(),
                "last_request_finished_at": str(self._last_request_finished_at or "").strip(),
                "last_request_elapsed_ms": float(self._last_request_elapsed_ms),
                "last_request_status": str(self._last_request_status or "idle"),
                "last_request_error": (
                    dict(self._last_request_error)
                    if isinstance(self._last_request_error, dict)
                    else None
                ),
                "current_request_runtime_ms": current_request_runtime_ms,
                "slow_request_threshold_ms": _SLOW_REQUEST_THRESHOLD_MS,
                "recent_requests": list(self._recent_requests),
            }

    def _run_tracked(
        self,
        tool_name: str,
        operation: Callable[[], Any],
    ) -> dict[str, Any]:
        started, started_at = self._begin_request(tool_name)
        status = "ok"
        error_payload: dict[str, Any] | None = None
        try:
            return cast(dict[str, Any], operation())
        except Exception as exc:
            status = "error"
            error_payload = {
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            raise
        finally:
            self._finish_request(
                tool_name=tool_name,
                started=started,
                started_at=started_at,
                status=status,
                error=error_payload,
            )

    def _collect_runtime_head_snapshot(self) -> dict[str, Any]:
        source_root = str(self._runtime_source_tree.get("source_root") or "").strip()
        if not source_root:
            return {}
        return cast(
            dict[str, Any],
            collect_git_head_snapshot(
                repo_root=source_root,
                timeout_seconds=0.2,
            ),
        )

    def _runtime_identity_payload(self) -> dict[str, Any]:
        current_head_snapshot = self._collect_runtime_head_snapshot()
        uptime_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - self._process_started_at_dt).total_seconds(),
        )
        return cast(
            dict[str, Any],
            build_runtime_identity_payload(
                pid=self._process_id,
                parent_pid=self._parent_process_id,
                process_started_at=self._process_started_at,
                process_uptime_seconds=uptime_seconds,
                current_working_directory=self._startup_cwd,
                python_executable=self._python_executable,
                command_line=self._command_line,
                source_root=str(self._runtime_source_tree.get("source_root") or "").strip(),
                pyproject_path=str(self._runtime_source_tree.get("pyproject_path") or "").strip(),
                module_path=str(self._runtime_source_tree.get("module_path") or "").strip(),
                startup_head_snapshot=self._startup_head_snapshot,
                current_head_snapshot=current_head_snapshot,
            ),
        )

    def health(self) -> dict[str, Any]:
        version_info = get_version_info()
        version_info["update_status"] = get_update_status(version_info=version_info)
        settings_governance = self._health_settings_governance_payload()
        return cast(
            dict[str, Any],
            build_health_response_payload(
                config=self._config,
                request_stats=self._request_stats_payload(),
                version=get_version(),
                version_info=version_info,
                runtime_identity=cast(Any, self._runtime_identity_payload()),
                settings_governance=settings_governance,
            ),
        )

    def _health_settings_governance_payload(self) -> dict[str, Any]:
        try:
            bundle = resolve_runtime_settings_bundle(
                root=str(self._config.default_root),
                config_file=".ace-lite.yml",
                mcp_name="ace-lite",
                runtime_profile=None,
                use_snapshot=False,
                current_path=DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
                last_known_good_path=DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
            )
            return cast(dict[str, Any], build_runtime_settings_governance_payload(bundle))
        except Exception as exc:
            return {
                "governance_state": "health_governance_unavailable",
                "config_consistency_state": "warning",
                "config_warning_count": 1,
                "config_warning_codes": ["CFG-HEALTH-001"],
                "config_warnings": [
                    {
                        "code": "CFG-HEALTH-001",
                        "path": "health.settings_governance",
                        "severity": "warning",
                        "message": (
                            "runtime settings governance unavailable; "
                            f"{exc.__class__.__name__}: {exc}"
                        ),
                    }
                ],
            }

    def index(
        self,
        *,
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
        return self._run_tracked(
            "ace_index",
            lambda: handle_index_request(
                root_path=self._resolve_root(root),
                language_csv=str(languages or self._config.default_languages).strip(),
                enabled_languages=parse_language_csv(
                    str(languages or self._config.default_languages).strip()
                )
                or [],
                output=output,
                batch_mode=batch_mode,
                batch_size=batch_size,
                timeout_per_file_seconds=timeout_per_file_seconds,
                resume=resume,
                resume_state_path=resume_state_path,
                retry_timeouts=retry_timeouts,
                subprocess_batch=subprocess_batch,
                subprocess_batch_timeout_seconds=subprocess_batch_timeout_seconds,
                include_payload=include_payload,
                build_index_fn=build_index,
                build_index_with_resilience_fn=build_index_with_resilience,
                resolve_output_path_fn=self._resolve_output_path,
            ),
        )

    def repomap_build(
        self,
        *,
        root: str | None = None,
        languages: str | None = None,
        budget_tokens: int = 800,
        top_k: int = 40,
        ranking_profile: str = "heuristic",
        output_json: str | None = None,
        output_md: str | None = None,
    ) -> dict[str, Any]:
        return self._run_tracked(
            "ace_repomap_build",
            lambda: handle_repomap_build_request(
                root_path=self._resolve_root(root),
                language_csv=str(languages or self._config.default_languages).strip(),
                budget_tokens=budget_tokens,
                top_k=top_k,
                ranking_profile=ranking_profile,
                output_json=output_json,
                output_md=output_md,
                tokenizer_model=str(self._config.tokenizer_model),
                build_index_fn=build_index,
                parse_language_csv_fn=lambda raw_languages: parse_language_csv(raw_languages) or [],
                build_repo_map_fn=build_repo_map,
                resolve_output_path_fn=self._resolve_output_path,
            ),
        )

    def skills_catalog(
        self,
        *,
        root: str | None = None,
        skills_dir: str | None = None,
    ) -> dict[str, Any]:
        def _operation() -> dict[str, Any]:
            root_path = self._resolve_root(root)
            skills_path = self._resolve_skills_dir(root_path=root_path, skills_dir=skills_dir)
            return build_skills_catalog_contract(root_path=root_path, skills_path=skills_path)

        return self._run_tracked("ace_skills_catalog", _operation)

    def plan_quick(
        self,
        *,
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
        return self._run_tracked(
            "ace_plan_quick",
            lambda: handle_plan_quick_request(
                query=query,
                repo=repo,
                root_path=self._resolve_root(root),
                default_repo=self._config.default_repo,
                language_csv=str(languages or self._config.default_languages).strip(),
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
                include_rows=include_rows,
                tokenizer_model=str(self._config.tokenizer_model),
                build_plan_quick_fn=build_plan_quick,
            ),
        )

    def plan(
        self,
        *,
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
        def _operation() -> dict[str, Any]:
            root_path = self._resolve_root(root)
            skills_path = self._resolve_skills_dir(root_path=root_path, skills_dir=skills_dir)
            config_pack_path = self._resolve_config_pack_path(
                root_path=root_path,
                config_pack=config_pack,
            )
            return cast(
                dict[str, Any],
                handle_plan_request(
                    query=query,
                    repo=repo,
                    root_path=root_path,
                    default_repo=self._config.default_repo,
                    skills_path=skills_path,
                    config_pack_path=config_pack_path,
                    time_range=time_range,
                    start_date=start_date,
                    end_date=end_date,
                    memory_primary=memory_primary,
                    memory_secondary=memory_secondary,
                    lsp_enabled=lsp_enabled,
                    plugins_enabled=plugins_enabled,
                    top_k_files=top_k_files,
                    min_candidate_score=min_candidate_score,
                    retrieval_policy=retrieval_policy,
                    include_full_payload=include_full_payload,
                    timeout_seconds=timeout_seconds,
                    default_timeout_seconds=float(self._config.plan_timeout_seconds),
                    run_plan_payload_fn=self._run_plan_payload,
                    plan_quick_fn=self.plan_quick,
                ),
            )

        return self._run_tracked("ace_plan", _operation)

    def _run_plan_payload(
        self,
        normalized_query: str,
        resolved_repo: str,
        root_path: Path,
        skills_path: Path,
        time_range: str | None,
        start_date: str | None,
        end_date: str | None,
        memory_primary: str | None,
        memory_secondary: str | None,
        lsp_enabled: bool,
        plugins_enabled: bool,
        top_k_files: int,
        min_candidate_score: int,
        retrieval_policy: str,
        config_pack_overrides: dict[str, Any] | None,
    ) -> dict[str, Any]:
        options = resolve_plan_request_options(
            config=self._config,
            top_k_files=top_k_files,
            min_candidate_score=min_candidate_score,
            retrieval_policy=retrieval_policy,
            lsp_enabled=lsp_enabled,
            plugins_enabled=plugins_enabled,
            config_pack_overrides=config_pack_overrides,
        )
        return cast(
            dict[str, Any],
            execute_mcp_plan_payload(
                create_memory_provider_fn=create_memory_provider,
                run_plan_fn=run_plan,
                config=self._config,
                normalized_query=normalized_query,
                resolved_repo=resolved_repo,
                root_path=root_path,
                skills_path=skills_path,
                time_range=time_range,
                start_date=start_date,
                end_date=end_date,
                memory_primary=memory_primary,
                memory_secondary=memory_secondary,
                options=options,
            ),
        )

    def memory_search(
        self,
        *,
        query: str,
        limit: int = 5,
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        def _operation() -> dict[str, Any]:
            path = self._resolve_notes_path(notes_path=notes_path)
            return cast(
                dict[str, Any],
                handle_memory_search(
                    query=query,
                    limit=limit,
                    namespace=namespace,
                    path=path,
                    notes=self._iter_notes(path),
                ),
            )

        return self._run_tracked("ace_memory_search", _operation)

    def memory_graph_view(
        self,
        *,
        db_path: str | None = None,
        fact_handle: str | None = None,
        seeds: list[str] | tuple[str, ...] | None = None,
        repo: str | None = None,
        namespace: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        as_of: str | None = None,
        max_hops: int = 1,
        limit: int = 8,
        root: str | None = None,
    ) -> dict[str, Any]:
        def _operation() -> dict[str, Any]:
            root_path = self._resolve_root(root)
            resolved_db_path = Path(
                str(db_path or "context-map/long_term_memory.db").strip()
                or "context-map/long_term_memory.db"
            ).expanduser()
            if not resolved_db_path.is_absolute():
                resolved_db_path = (root_path / resolved_db_path).resolve()
            return cast(
                dict[str, Any],
                handle_memory_graph_view(
                    db_path=resolved_db_path,
                    fact_handle=fact_handle,
                    seeds=tuple(seeds or ()),
                    repo=repo,
                    namespace=namespace,
                    user_id=user_id,
                    profile_key=profile_key,
                    as_of=as_of,
                    max_hops=max_hops,
                    limit=limit,
                ),
            )

        return self._run_tracked("ace_memory_graph_view", _operation)

    def retrieval_graph_view(
        self,
        *,
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
        timeout_seconds: float | None = None,
        limit: int = 50,
        max_hops: int = 1,
    ) -> dict[str, Any]:
        def _operation() -> dict[str, Any]:
            root_path = self._resolve_root(root)
            plan_result = self.plan(
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
                lsp_enabled=lsp_enabled,
                plugins_enabled=plugins_enabled,
                top_k_files=top_k_files,
                min_candidate_score=min_candidate_score,
                retrieval_policy=retrieval_policy,
                include_full_payload=True,
                timeout_seconds=timeout_seconds,
            )
            plan_payload = plan_result.get("plan", {})
            return cast(
                dict[str, Any],
                handle_retrieval_graph_view_request(
                    plan_payload=plan_payload,
                    limit=limit,
                    max_hops=max_hops,
                    repo=repo,
                    root=str(root_path),
                    query=query,
                ),
            )

        return self._run_tracked("ace_retrieval_graph_view", _operation)

    def memory_store(
        self,
        *,
        text: str,
        namespace: str | None = None,
        tags: dict[str, str] | None = None,
        notes_path: str | None = None,
        req: str | None = None,
        contract: str | None = None,
        area: str | None = None,
        decision_type: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        def _operation() -> dict[str, Any]:
            path = self._resolve_notes_path(notes_path=notes_path)
            return cast(
                dict[str, Any],
                handle_memory_store(
                    text=text,
                    namespace=namespace,
                    tags=tags,
                    path=path,
                    rows=None,
                    save_notes_fn=None,
                    append_note_fn=self._append_note,
                    req=req,
                    contract=contract,
                    area=area,
                    decision_type=decision_type,
                    task_id=task_id,
                ),
            )

        return self._run_tracked("ace_memory_store", _operation)

    def memory_wipe(
        self,
        *,
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        def _operation() -> dict[str, Any]:
            path = self._resolve_notes_path(notes_path=notes_path)
            removed_count, remaining_count = self._wipe_notes(path, namespace)
            return {
                "ok": True,
                "namespace": str(namespace or "").strip() or None,
                "removed_count": removed_count,
                "remaining_count": remaining_count,
                "notes_path": str(path),
            }

        return self._run_tracked("ace_memory_wipe", _operation)

    def feedback_record(
        self,
        *,
        query: str,
        selected_path: str,
        candidate_paths: list[str] | None = None,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        root: str | None = None,
        profile_path: str | None = None,
        position: int | None = None,
        max_entries: int = 512,
    ) -> dict[str, Any]:
        resolved_user_id = user_id if user_id is not None else self._config.user_id
        return self._run_tracked(
            "ace_feedback_record",
            lambda: handle_feedback_record_request(
                query=query,
                selected_path=selected_path,
                candidate_paths=candidate_paths,
                repo=repo,
                user_id=resolved_user_id,
                profile_key=profile_key,
                root_path=self._resolve_root(root),
                default_repo=self._config.default_repo,
                profile_path=profile_path,
                position=position,
                max_entries=max_entries,
            ),
        )

    def feedback_stats(
        self,
        *,
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
        return self._run_tracked(
            "ace_feedback_stats",
            lambda: handle_feedback_stats_request(
                repo=repo,
                user_id=user_id,
                profile_key=profile_key,
                root_path=self._resolve_root(root),
                default_repo=self._config.default_repo,
                profile_path=profile_path,
                query=query,
                boost_per_select=boost_per_select,
                max_boost=max_boost,
                decay_days=decay_days,
                top_n=top_n,
                max_entries=max_entries,
            ),
        )

    def issue_report_record(
        self,
        *,
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
        resolved_user_id = user_id if user_id is not None else self._config.user_id
        return self._run_tracked(
            "ace_issue_report_record",
            lambda: handle_issue_report_record_request(
                title=title,
                query=query,
                actual_behavior=actual_behavior,
                repo=repo,
                user_id=resolved_user_id,
                profile_key=profile_key,
                root_path=self._resolve_root(root),
                default_repo=self._config.default_repo,
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
            ),
        )

    def issue_report_list(
        self,
        *,
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
        return self._run_tracked(
            "ace_issue_report_list",
            lambda: handle_issue_report_list_request(
                repo=repo,
                user_id=user_id,
                profile_key=profile_key,
                root_path=self._resolve_root(root),
                store_path=store_path,
                status=status,
                category=category,
                severity=severity,
                limit=limit,
            ),
        )

    def issue_report_export_case(
        self,
        *,
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
        return self._run_tracked(
            "ace_issue_report_export_case",
            lambda: handle_issue_report_export_case_request(
                issue_id=issue_id,
                root_path=self._resolve_root(root),
                store_path=store_path,
                output_path=output_path,
                case_id=case_id,
                comparison_lane=comparison_lane,
                top_k=top_k,
                min_validation_tests=min_validation_tests,
                append=append,
            ),
        )

    def issue_report_apply_fix(
        self,
        *,
        issue_id: str,
        fix_id: str,
        root: str | None = None,
        issue_store_path: str | None = None,
        dev_feedback_path: str | None = None,
        status: str = "resolved",
        resolved_at: str | None = None,
    ) -> dict[str, Any]:
        return self._run_tracked(
            "ace_issue_report_apply_fix",
            lambda: handle_issue_report_apply_fix_request(
                issue_id=issue_id,
                fix_id=fix_id,
                root_path=self._resolve_root(root),
                issue_store_path=issue_store_path,
                dev_feedback_path=dev_feedback_path,
                status=status,
                resolved_at=resolved_at,
            ),
        )

    def dev_issue_record(
        self,
        *,
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
        resolved_user_id = user_id if user_id is not None else self._config.user_id
        return self._run_tracked(
            "ace_dev_issue_record",
            lambda: handle_dev_issue_record_request(
                title=title,
                reason_code=reason_code,
                repo=repo,
                store_path=store_path,
                user_id=resolved_user_id,
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
                root_path=self._config.default_root,
            ),
        )

    def dev_fix_record(
        self,
        *,
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
        resolved_user_id = user_id if user_id is not None else self._config.user_id
        return self._run_tracked(
            "ace_dev_fix_record",
            lambda: handle_dev_fix_record_request(
                reason_code=reason_code,
                repo=repo,
                resolution_note=resolution_note,
                store_path=store_path,
                user_id=resolved_user_id,
                profile_key=profile_key,
                issue_id=issue_id,
                query=query,
                selected_path=selected_path,
                related_invocation_id=related_invocation_id,
                created_at=created_at,
                fix_id=fix_id,
                root_path=self._config.default_root,
            ),
        )

    def dev_issue_from_runtime(
        self,
        *,
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
        resolved_user_id = user_id if user_id is not None else self._config.user_id
        return self._run_tracked(
            "ace_dev_issue_from_runtime",
            lambda: handle_dev_issue_from_runtime_request(
                invocation_id=invocation_id,
                stats_db_path=stats_db_path,
                store_path=store_path,
                reason_code=reason_code,
                title=title,
                notes=notes,
                status=status,
                user_id=resolved_user_id,
                profile_key=profile_key,
                issue_id=issue_id,
                root_path=self._config.default_root,
            ),
        )

    def dev_issue_apply_fix(
        self,
        *,
        issue_id: str,
        fix_id: str,
        store_path: str | None = None,
        status: str | None = None,
        resolved_at: str | None = None,
    ) -> dict[str, Any]:
        return self._run_tracked(
            "ace_dev_issue_apply_fix",
            lambda: handle_dev_issue_apply_fix_request(
                issue_id=issue_id,
                fix_id=fix_id,
                store_path=store_path,
                status=status,
                resolved_at=resolved_at,
                root_path=self._config.default_root,
            ),
        )

    def dev_feedback_summary(
        self,
        *,
        repo: str | None = None,
        user_id: str | None = None,
        profile_key: str | None = None,
        store_path: str | None = None,
    ) -> dict[str, Any]:
        return self._run_tracked(
            "ace_dev_feedback_summary",
            lambda: handle_dev_feedback_summary_request(
                repo=repo,
                user_id=user_id,
                profile_key=profile_key,
                store_path=store_path,
            ),
        )

    def _resolve_root(self, root: str | None) -> Path:
        return cast(Path, resolve_root(root=root, default_root=self._config.default_root))

    def _resolve_skills_dir(self, *, root_path: Path, skills_dir: str | None) -> Path:
        return cast(
            Path,
            resolve_skills_dir(
                root_path=root_path,
                skills_dir=skills_dir,
                default_skills_dir=self._config.default_skills_dir,
            ),
        )

    def _resolve_config_pack_path(self, *, root_path: Path, config_pack: str | None) -> str | None:
        return cast(
            str | None,
            resolve_config_pack_path(
                root_path=root_path,
                config_pack=config_pack,
                default_config_pack=self._config.config_pack,
            ),
        )

    @staticmethod
    def _resolve_output_path(
        *,
        root_path: Path,
        output: str | None,
        default: str,
    ) -> Path:
        return cast(
            Path,
            resolve_output_path(
                root_path=root_path,
                output=output,
                default=default,
            ),
        )

    def _resolve_notes_path(self, *, notes_path: str | None) -> Path:
        return cast(
            Path,
            resolve_notes_path(
                notes_path=notes_path,
                default_notes_path=self._config.notes_path,
            ),
        )

    @staticmethod
    def _load_notes(path: Path) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], load_notes(path))

    @staticmethod
    def _save_notes(path: Path, rows: list[dict[str, Any]]) -> None:
        save_notes(path, rows)

    @staticmethod
    def _append_note(path: Path, row: dict[str, Any]) -> None:
        append_note(path, row)

    @staticmethod
    def _iter_notes(path: Path):
        return iter_notes(path)

    @staticmethod
    def _wipe_notes(path: Path, namespace: str | None) -> tuple[int, int]:
        return cast(tuple[int, int], wipe_notes(path, namespace))


__all__ = ["AceLiteMcpService"]
