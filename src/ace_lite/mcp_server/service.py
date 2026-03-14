"""MCP server exposing ACE-Lite capabilities as tools.

This module provides a production-ready stdio MCP server built on FastMCP.
It can also run in a self-test mode for health validation.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any

from ace_lite.cli_app.orchestrator_factory import create_memory_provider, run_plan
from ace_lite.indexer import build_index
from ace_lite.indexing_resilience import build_index_with_resilience
from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.file_support import (
    load_notes,
    resolve_config_pack_path,
    resolve_notes_path,
    resolve_output_path,
    resolve_root,
    resolve_skills_dir,
    save_notes,
)
from ace_lite.mcp_server.service_health import build_health_response_payload
from ace_lite.mcp_server.service_feedback_handlers import (
    handle_feedback_record_request,
    handle_feedback_stats_request,
)
from ace_lite.mcp_server.service_index_handlers import handle_index_request
from ace_lite.mcp_server.service_memory_handlers import (
    handle_memory_search,
    handle_memory_store,
    handle_memory_wipe,
)
from ace_lite.mcp_server.service_plan_runtime import execute_mcp_plan_payload
from ace_lite.mcp_server.service_repomap_handlers import handle_repomap_build_request
from ace_lite.mcp_server.service_plan_handlers import (
    handle_plan_quick_request,
    handle_plan_request,
)
from ace_lite.mcp_server.plan_request import resolve_plan_request_options
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.plan_quick import build_plan_quick
from ace_lite.repomap.builder import build_repo_map
from ace_lite.version import get_version, get_version_info

logger = logging.getLogger(__name__)


class AceLiteMcpService:
    def __init__(self, *, config: AceLiteMcpConfig) -> None:
        self._config = config
        self._stats_lock = Lock()
        self._active_request_count = 0
        self._total_request_count = 0
        self._last_request_started_at = ""
        self._last_request_finished_at = ""
        self._last_request_tool = ""
        self._last_request_elapsed_ms = 0.0

    @property
    def config(self) -> AceLiteMcpConfig:
        return self._config

    @contextmanager
    def _track_request(self, tool_name: str):
        started = perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        with self._stats_lock:
            self._active_request_count += 1
            self._total_request_count += 1
            self._last_request_tool = str(tool_name or "").strip()
            self._last_request_started_at = started_at
        try:
            yield
        finally:
            finished_at = datetime.now(timezone.utc).isoformat()
            elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
            with self._stats_lock:
                self._active_request_count = max(0, self._active_request_count - 1)
                self._last_request_finished_at = finished_at
                self._last_request_elapsed_ms = elapsed_ms

    def _request_stats_payload(self) -> dict[str, Any]:
        with self._stats_lock:
            return {
                "active_request_count": int(self._active_request_count),
                "total_request_count": int(self._total_request_count),
                "last_request_tool": str(self._last_request_tool or "").strip(),
                "last_request_started_at": str(self._last_request_started_at or "").strip(),
                "last_request_finished_at": str(self._last_request_finished_at or "").strip(),
                "last_request_elapsed_ms": float(self._last_request_elapsed_ms),
            }

    def health(self) -> dict[str, Any]:
        version_info = get_version_info()
        return build_health_response_payload(
            config=self._config,
            request_stats=self._request_stats_payload(),
            version=get_version(),
            version_info=version_info,
        )

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
        with self._track_request("ace_index"):
            root_path = self._resolve_root(root)
            language_csv = str(languages or self._config.default_languages).strip()
            enabled_languages = parse_language_csv(language_csv)
            return handle_index_request(
                root_path=root_path,
                language_csv=language_csv,
                enabled_languages=enabled_languages,
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
        with self._track_request("ace_repomap_build"):
            root_path = self._resolve_root(root)
            language_csv = str(languages or self._config.default_languages).strip()
            return handle_repomap_build_request(
                root_path=root_path,
                language_csv=language_csv,
                budget_tokens=budget_tokens,
                top_k=top_k,
                ranking_profile=ranking_profile,
                output_json=output_json,
                output_md=output_md,
                tokenizer_model=str(self._config.tokenizer_model),
                build_index_fn=build_index,
                parse_language_csv_fn=parse_language_csv,
                build_repo_map_fn=build_repo_map,
                resolve_output_path_fn=self._resolve_output_path,
            )

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
        with self._track_request("ace_plan_quick"):
            root_path = self._resolve_root(root)
            language_csv = str(languages or self._config.default_languages).strip()
            return handle_plan_quick_request(
                query=query,
                repo=repo,
                root_path=root_path,
                default_repo=self._config.default_repo,
                language_csv=language_csv,
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
        with self._track_request("ace_plan"):
            root_path = self._resolve_root(root)
            skills_path = self._resolve_skills_dir(root_path=root_path, skills_dir=skills_dir)
            config_pack_path = self._resolve_config_pack_path(
                root_path=root_path,
                config_pack=config_pack,
            )
            return handle_plan_request(
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
            )

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
        return execute_mcp_plan_payload(
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
        )

    def memory_search(
        self,
        *,
        query: str,
        limit: int = 5,
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        with self._track_request("ace_memory_search"):
            path = self._resolve_notes_path(notes_path=notes_path)
            notes = self._load_notes(path)
            return handle_memory_search(
                query=query,
                limit=limit,
                namespace=namespace,
                path=path,
                notes=notes,
            )

    def memory_store(
        self,
        *,
        text: str,
        namespace: str | None = None,
        tags: dict[str, str] | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        with self._track_request("ace_memory_store"):
            path = self._resolve_notes_path(notes_path=notes_path)
            rows = self._load_notes(path)
            return handle_memory_store(
                text=text,
                namespace=namespace,
                tags=tags,
                path=path,
                rows=rows,
                save_notes_fn=self._save_notes,
            )

    def memory_wipe(
        self,
        *,
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
        with self._track_request("ace_memory_wipe"):
            path = self._resolve_notes_path(notes_path=notes_path)
            rows = self._load_notes(path)
            return handle_memory_wipe(
                namespace=namespace,
                path=path,
                rows=rows,
                save_notes_fn=self._save_notes,
            )

    def feedback_record(
        self,
        *,
        query: str,
        selected_path: str,
        repo: str | None = None,
        root: str | None = None,
        profile_path: str | None = None,
        position: int | None = None,
        max_entries: int = 512,
    ) -> dict[str, Any]:
        with self._track_request("ace_feedback_record"):
            root_path = self._resolve_root(root)
            return handle_feedback_record_request(
                query=query,
                selected_path=selected_path,
                repo=repo,
                root_path=root_path,
                default_repo=self._config.default_repo,
                profile_path=profile_path,
                position=position,
                max_entries=max_entries,
            )

    def feedback_stats(
        self,
        *,
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
        with self._track_request("ace_feedback_stats"):
            root_path = self._resolve_root(root)
            return handle_feedback_stats_request(
                repo=repo,
                root_path=root_path,
                default_repo=self._config.default_repo,
                profile_path=profile_path,
                query=query,
                boost_per_select=boost_per_select,
                max_boost=max_boost,
                decay_days=decay_days,
                top_n=top_n,
                max_entries=max_entries,
            )

    def _resolve_root(self, root: str | None) -> Path:
        return resolve_root(root=root, default_root=self._config.default_root)

    def _resolve_skills_dir(self, *, root_path: Path, skills_dir: str | None) -> Path:
        return resolve_skills_dir(
            root_path=root_path,
            skills_dir=skills_dir,
            default_skills_dir=self._config.default_skills_dir,
        )

    def _resolve_config_pack_path(self, *, root_path: Path, config_pack: str | None) -> str | None:
        return resolve_config_pack_path(
            root_path=root_path,
            config_pack=config_pack,
            default_config_pack=self._config.config_pack,
        )

    @staticmethod
    def _resolve_output_path(
        *,
        root_path: Path,
        output: str | None,
        default: str,
    ) -> Path:
        return resolve_output_path(
            root_path=root_path,
            output=output,
            default=default,
        )

    def _resolve_notes_path(self, *, notes_path: str | None) -> Path:
        return resolve_notes_path(
            notes_path=notes_path,
            default_notes_path=self._config.notes_path,
        )

    @staticmethod
    def _load_notes(path: Path) -> list[dict[str, Any]]:
        return load_notes(path)

    @staticmethod
    def _save_notes(path: Path, rows: list[dict[str, Any]]) -> None:
        save_notes(path, rows)


__all__ = ['AceLiteMcpService']
