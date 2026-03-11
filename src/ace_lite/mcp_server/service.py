"""MCP server exposing ACE-Lite capabilities as tools.

This module provides a production-ready stdio MCP server built on FastMCP.
It can also run in a self-test mode for health validation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.cli_app.orchestrator_factory import create_memory_provider, run_plan
from ace_lite.feedback_store import FeedbackBoostConfig, SelectionFeedbackStore
from ace_lite.index_stage.terms import extract_terms
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
from ace_lite.mcp_server.service_index_handlers import handle_index_request
from ace_lite.mcp_server.service_memory_handlers import (
    handle_memory_search,
    handle_memory_store,
    handle_memory_wipe,
)
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

    @property
    def config(self) -> AceLiteMcpConfig:
        return self._config

    def health(self) -> dict[str, Any]:
        memory_primary = str(self._config.memory_primary or "none").strip().lower() or "none"
        memory_secondary = (
            str(self._config.memory_secondary or "none").strip().lower() or "none"
        )
        memory_disabled = memory_primary == "none" and memory_secondary == "none"
        warnings: list[str] = []
        recommendations: list[str] = []
        version_info = get_version_info()
        if bool(version_info.get("drifted")):
            warnings.append(
                "Version drift detected: pyproject.toml="
                f"{version_info.get('pyproject_version')} but installed metadata="
                f"{version_info.get('installed_version')} (dist={version_info.get('dist_name')}). "
                "Run: python -m pip install -e .[dev]"
            )
        if memory_disabled:
            warnings.append(
                "Memory providers are disabled (ACE_LITE_MEMORY_PRIMARY/SECONDARY are none)."
            )
            recommendations.extend(
                [
                    "Set ACE_LITE_MEMORY_PRIMARY=mcp",
                    "Set ACE_LITE_MEMORY_SECONDARY=rest",
                    "Set ACE_LITE_MCP_BASE_URL / ACE_LITE_REST_BASE_URL to your OpenMemory endpoint",
                ]
            )
        return {
            "ok": True,
            "server_name": self._config.server_name,
            "version": get_version(),
            "version_info": version_info,
            "default_root": str(self._config.default_root),
            "default_repo": self._config.default_repo,
            "default_skills_dir": str(self._config.default_skills_dir),
            "default_languages": self._config.default_languages,
            "default_config_pack": str(self._config.config_pack or ""),
            "memory_primary": memory_primary,
            "memory_secondary": memory_secondary,
            "memory_ready": not memory_disabled,
            "plan_timeout_seconds": float(self._config.plan_timeout_seconds),
            "mcp_base_url": self._config.mcp_base_url,
            "rest_base_url": self._config.rest_base_url,
            "embedding_enabled": bool(self._config.embedding_enabled),
            "embedding_provider": str(self._config.embedding_provider or "hash").strip().lower()
            or "hash",
            "embedding_model": str(self._config.embedding_model or "hash-v1").strip()
            or "hash-v1",
            "embedding_dimension": max(1, int(self._config.embedding_dimension)),
            "embedding_index_path": str(self._config.embedding_index_path or "").strip()
            or "context-map/embeddings/index.json",
            "ollama_base_url": str(self._config.ollama_base_url or "").strip()
            or "http://localhost:11434",
            "user_id": self._config.user_id,
            "app": self._config.app,
            "warnings": warnings,
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        root_path = self._resolve_root(root)
        language_csv = str(languages or self._config.default_languages).strip()
        index_payload = build_index(
            root_dir=str(root_path),
            languages=parse_language_csv(language_csv),
        )
        repo_map = build_repo_map(
            index_payload=index_payload,
            budget_tokens=max(1, int(budget_tokens)),
            top_k=max(1, int(top_k)),
            ranking_profile=str(ranking_profile or "heuristic").strip().lower()
            or "heuristic",
            tokenizer_model=str(self._config.tokenizer_model),
        )

        json_path = self._resolve_output_path(
            root_path=root_path,
            output=output_json,
            default="context-map/repo_map.json",
        )
        md_path = self._resolve_output_path(
            root_path=root_path,
            output=output_md,
            default="context-map/repo_map.md",
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)

        json_payload = dict(repo_map)
        markdown = str(json_payload.pop("markdown", "") or "")
        json_path.write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        md_path.write_text(markdown, encoding="utf-8")

        return {
            "ok": True,
            "root": str(root_path),
            "languages": language_csv,
            "ranking_profile": str(repo_map.get("ranking_profile", "")),
            "budget_tokens": int(repo_map.get("budget_tokens", budget_tokens) or 0),
            "used_tokens": int(repo_map.get("used_tokens", 0) or 0),
            "selected_count": int(repo_map.get("selected_count", 0) or 0),
            "output_json": str(json_path),
            "output_md": str(md_path),
        }

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

        provider = create_memory_provider(
            primary=str(memory_primary or self._config.memory_primary).strip().lower() or "none",
            secondary=str(memory_secondary or self._config.memory_secondary).strip().lower()
            or "none",
            memory_strategy="hybrid",
            memory_hybrid_limit=20,
            memory_cache_enabled=True,
            memory_cache_path=str(root_path / "context-map" / "memory_cache.jsonl"),
            memory_cache_ttl_seconds=604800,
            memory_cache_max_entries=5000,
            memory_notes_enabled=bool(options.memory_notes_enabled),
            mcp_base_url=self._config.mcp_base_url,
            rest_base_url=self._config.rest_base_url,
            timeout_seconds=self._config.memory_timeout,
            user_id=self._config.user_id,
            app=self._config.app,
            limit=self._config.memory_limit,
        )
        return run_plan(
            query=normalized_query,
            repo=resolved_repo,
            root=str(root_path),
            skills_dir=str(skills_path),
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            memory_provider=provider,
            **options.to_run_plan_kwargs(),
        )

    def memory_search(
        self,
        *,
        query: str,
        limit: int = 5,
        namespace: str | None = None,
        notes_path: str | None = None,
    ) -> dict[str, Any]:
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
        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise ValueError("query cannot be empty")
        normalized_selected_path = str(selected_path or "").strip()
        if not normalized_selected_path:
            raise ValueError("selected_path cannot be empty")

        root_path = self._resolve_root(root)
        resolved_repo = str(repo or self._config.default_repo).strip() or self._config.default_repo
        profile = Path(profile_path).expanduser() if profile_path else Path("~/.ace-lite/profile.json").expanduser()
        if not profile.is_absolute():
            profile = (root_path / profile).resolve()
        else:
            profile = profile.resolve()

        store = SelectionFeedbackStore(
            profile_path=profile,
            max_entries=max(0, int(max_entries)),
        )
        recorded = store.record(
            query=normalized_query,
            repo=resolved_repo,
            selected_path=normalized_selected_path,
            position=position,
            root_path=root_path,
        )
        return {
            "ok": True,
            "root": str(root_path),
            "repo": resolved_repo,
            "profile_path": str(profile),
            "recorded": recorded,
        }

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
        root_path = self._resolve_root(root)
        resolved_repo = str(repo or self._config.default_repo).strip() or self._config.default_repo
        profile = Path(profile_path).expanduser() if profile_path else Path("~/.ace-lite/profile.json").expanduser()
        if not profile.is_absolute():
            profile = (root_path / profile).resolve()
        else:
            profile = profile.resolve()

        store = SelectionFeedbackStore(
            profile_path=profile,
            max_entries=max(0, int(max_entries)),
        )
        query_terms: list[str] | None = None
        normalized_query = str(query or "").strip()
        if normalized_query:
            query_terms = extract_terms(query=normalized_query, memory_stage={})
        stats = store.stats(
            repo=resolved_repo if repo is not None else None,
            query_terms=query_terms,
            boost=FeedbackBoostConfig(
                boost_per_select=max(0.0, float(boost_per_select)),
                max_boost=max(0.0, float(max_boost)),
                decay_days=max(0.0, float(decay_days)),
            ),
            top_n=max(1, int(top_n)),
        )
        return {
            "ok": True,
            "root": str(root_path),
            "repo": resolved_repo,
            "profile_path": str(profile),
            "stats": stats,
        }

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
