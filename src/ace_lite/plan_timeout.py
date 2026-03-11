from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.pipeline.contracts import validate_stage_output
from ace_lite.schema import EXPECTED_PIPELINE_ORDER, SCHEMA_VERSION, validate_context_plan

PLAN_TIMEOUT_SECONDS_ENV = "ACE_LITE_PLAN_TIMEOUT_SECONDS"
PLAN_TIMEOUT_DEBUG_ENV = "ACE_LITE_PLAN_TIMEOUT_DEBUG"
PLAN_TIMEOUT_DEBUG_SCHEMA_VERSION = "ace-lite-plan-timeout-debug-v1"

PLAN_TIMEOUT_RECOMMENDATIONS: tuple[str, ...] = (
    "Run ace_health to verify memory channels and base URLs.",
    "Use rest-primary memory profile if OpenMemory MCP route is incompatible.",
    "Use ace_plan_quick first, then call ace_plan only for narrowed targets.",
    "Retry with smaller top_k_files and include_full_payload=false.",
)


@dataclass(frozen=True, slots=True)
class TimeoutResolution:
    seconds: float
    source: str
    raw: float | str | None = None


@dataclass(frozen=True, slots=True)
class PlanTimeoutOutcome:
    payload: dict[str, Any] | None
    timed_out: bool
    timeout_seconds: float
    elapsed_ms: float
    thread_ident: int | None = None
    thread_stack: str | None = None
    debug_dump_path: str | None = None


def resolve_plan_timeout_seconds(
    *,
    timeout_seconds: float | None,
    default_timeout_seconds: float = 25.0,
    env: dict[str, str] | None = None,
) -> TimeoutResolution:
    if isinstance(timeout_seconds, (int, float)) and float(timeout_seconds) > 0:
        resolved = max(1.0, float(timeout_seconds))
        return TimeoutResolution(seconds=resolved, source="explicit", raw=float(timeout_seconds))

    env_payload = env if env is not None else os.environ
    env_value = str(env_payload.get(PLAN_TIMEOUT_SECONDS_ENV, "")).strip()
    if env_value:
        try:
            env_seconds = float(env_value)
        except ValueError:
            env_seconds = 0.0
        if env_seconds > 0:
            resolved = max(1.0, float(env_seconds))
            return TimeoutResolution(seconds=resolved, source="env", raw=env_value)

    resolved = max(1.0, float(default_timeout_seconds))
    return TimeoutResolution(seconds=resolved, source="default", raw=float(default_timeout_seconds))


def is_plan_timeout_debug_enabled(*, env: dict[str, str] | None = None) -> bool:
    env_payload = env if env is not None else os.environ
    value = str(env_payload.get(PLAN_TIMEOUT_DEBUG_ENV, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _capture_thread_stack(thread_ident: int | None) -> str | None:
    if thread_ident is None:
        return None
    frames = sys._current_frames()
    if thread_ident not in frames:
        return None
    return "".join(traceback.format_stack(frames[thread_ident]))


def _write_timeout_debug_dump(
    *,
    root_path: Path,
    dump_payload: dict[str, Any],
) -> str | None:
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dump_dir = (root_path / "context-map" / "timeouts").resolve()
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_path = (dump_dir / f"ace_plan_timeout_debug_{timestamp}.json").resolve()
        dump_path.write_text(
            json.dumps(dump_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(dump_path)
    except Exception:
        return None


def execute_with_timeout(
    *,
    run_payload: Callable[[], dict[str, Any]],
    timeout_seconds: float,
    debug_root: str | Path,
    debug_payload: dict[str, Any],
    debug_enabled: bool = False,
) -> PlanTimeoutOutcome:
    start_monotonic = datetime.now(timezone.utc)
    root_path = Path(debug_root).expanduser().resolve()

    executor: concurrent.futures.ThreadPoolExecutor | None = None
    future: concurrent.futures.Future[dict[str, Any]] | None = None
    plan_thread_ident: int | None = None
    timed_out = False

    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def wrapper() -> dict[str, Any]:
            nonlocal plan_thread_ident
            plan_thread_ident = threading.get_ident()
            return run_payload()

        future = executor.submit(wrapper)
        payload = future.result(timeout=max(1.0, float(timeout_seconds)))
        elapsed_ms = (
            datetime.now(timezone.utc) - start_monotonic
        ).total_seconds() * 1000.0
        return PlanTimeoutOutcome(
            payload=payload,
            timed_out=False,
            timeout_seconds=float(timeout_seconds),
            elapsed_ms=float(max(0.0, elapsed_ms)),
        )
    except concurrent.futures.TimeoutError:
        timed_out = True
        if future is not None:
            future.cancel()
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

        elapsed_ms = (
            datetime.now(timezone.utc) - start_monotonic
        ).total_seconds() * 1000.0
        thread_stack = _capture_thread_stack(plan_thread_ident)

        dump_path: str | None = None
        if debug_enabled:
            dump_payload = dict(debug_payload)
            dump_payload.setdefault("schema_version", PLAN_TIMEOUT_DEBUG_SCHEMA_VERSION)
            dump_payload.setdefault("event", "ace_plan_timeout")
            dump_payload.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
            dump_payload.setdefault("timeout_seconds", float(timeout_seconds))
            dump_payload.setdefault("elapsed_ms", float(max(0.0, elapsed_ms)))
            dump_payload.setdefault("thread_ident", plan_thread_ident)
            dump_payload.setdefault("thread_stack", thread_stack)
            dump_path = _write_timeout_debug_dump(root_path=root_path, dump_payload=dump_payload)

        return PlanTimeoutOutcome(
            payload=None,
            timed_out=True,
            timeout_seconds=float(timeout_seconds),
            elapsed_ms=float(max(0.0, elapsed_ms)),
            thread_ident=plan_thread_ident,
            thread_stack=thread_stack,
            debug_dump_path=dump_path,
        )
    finally:
        if executor is not None and not timed_out:
            executor.shutdown(wait=True, cancel_futures=False)


def build_plan_timeout_fallback_payload(
    *,
    query: str,
    repo: str,
    root: str,
    candidate_file_paths: list[str],
    steps: list[str],
    timeout_seconds: float,
    elapsed_ms: float,
    fallback_mode: str,
    debug_dump_path: str | None,
    chunk_token_budget: int = 1200,
    chunk_disclosure: str = "refs",
    policy_name: str = "general",
    policy_version: str = "v1",
    recommendations: list[str] | None = None,
) -> dict[str, Any]:
    root_path = str(Path(root).expanduser().resolve())
    pipeline_order = list(EXPECTED_PIPELINE_ORDER)

    normalized_candidates = [
        str(item).strip() for item in candidate_file_paths if str(item).strip()
    ]
    normalized_steps = [str(item).strip() for item in steps if str(item).strip()]
    recommendation_list = (
        list(recommendations)
        if isinstance(recommendations, list)
        else list(PLAN_TIMEOUT_RECOMMENDATIONS)
    )

    memory_payload: dict[str, Any] = {
        "query": str(query),
        "count": 0,
        "hits_preview": [],
        "channel_used": "none",
        "strategy": "none",
        "namespace": {},
        "timeline": {},
        "cache": {},
        "notes": {},
        "disclosure": {},
        "cost": {},
        "profile": {},
        "capture": {},
    }

    index_payload: dict[str, Any] = {
        "repo": str(repo),
        "root": root_path,
        "terms": [],
        "targets": list(normalized_candidates),
        "module_hint": "",
        "index_hash": "",
        "file_count": 0,
        "cache": {},
        "candidate_files": [
            {"path": path, "score": 0.0} for path in list(normalized_candidates)
        ],
        "candidate_chunks": [],
        "chunk_metrics": {},
        "docs": {},
        "worktree_prior": {},
        "cochange": {},
        "embeddings": {},
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
    }

    repomap_enabled = bool(normalized_candidates)
    repomap_payload: dict[str, Any] = {
        "enabled": repomap_enabled,
        "focused_files": list(normalized_candidates),
        "seed_paths": list(normalized_candidates),
        "neighbor_paths": [],
        "dependency_recall": {},
        "markdown": "",
        "ranking_profile": "graph",
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
        "neighbor_limit": 0,
        "neighbor_depth": 0,
        "budget_tokens": 0,
        "repomap_enabled_effective": repomap_enabled,
        "cache": {},
        "precompute": {},
    }
    if fallback_mode == "plan_quick":
        repomap_payload["ranking_profile"] = "graph"

    augment_payload: dict[str, Any] = {
        "enabled": False,
        "count": 0,
        "diagnostics": [],
        "errors": [],
        "vcs_history": {},
        "vcs_worktree": {},
        "xref_enabled": False,
        "xref": {},
        "tests": {},
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
    }

    skills_payload: dict[str, Any] = {
        "query_ctx": {},
        "available_count": 0,
        "selected": [],
    }

    source_plan_payload: dict[str, Any] = {
        "repo": str(repo),
        "root": root_path,
        "query": str(query),
        "stages": list(pipeline_order),
        "constraints": [],
        "diagnostics": [],
        "xref": {},
        "tests": {},
        "validation_tests": [],
        "candidate_chunks": [],
        "chunk_steps": [],
        "chunk_budget_used": 0.0,
        "chunk_budget_limit": float(max(1, int(chunk_token_budget))),
        "chunk_disclosure": str(chunk_disclosure or "refs"),
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
        "steps": list(normalized_steps),
        "writeback_template": {
            "title": "",
            "decision": "",
            "result": "",
            "caveat": "",
            "metadata": {
                "repo": str(repo),
                "branch": "",
                "path": "",
                "topic": "",
                "module": "",
                "updated_at": "",
                "app": "codex",
            },
        },
    }

    observability: dict[str, Any] = {
        "total_ms": float(max(0.0, float(elapsed_ms))),
        "stage_metrics": [],
        "plugins_loaded": [],
        "plugin_action_log": [],
        "plugin_conflicts": [],
        "error": {
            "type": "plan_timeout",
            "message": "ace_plan_timeout",
            "timeout_seconds": float(timeout_seconds),
            "timed_out": True,
            "fallback_mode": str(fallback_mode),
            "fallback_candidates": len(normalized_candidates),
            "fallback_candidate_paths": list(normalized_candidates),
            "fallback_steps": list(normalized_steps),
            "recommendations": list(recommendation_list),
            "debug_dump_path": debug_dump_path,
        },
    }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "query": str(query),
        "repo": str(repo),
        "root": root_path,
        "pipeline_order": list(pipeline_order),
        "conventions": {
            "count": 0,
            "rules_count": 0,
            "loaded_files": [],
            "rules": [],
            "cache_hit": False,
        },
        "memory": memory_payload,
        "index": index_payload,
        "repomap": repomap_payload,
        "augment": augment_payload,
        "skills": skills_payload,
        "source_plan": source_plan_payload,
        "observability": observability,
    }

    validate_stage_output("memory", payload["memory"])
    validate_stage_output("index", payload["index"])
    validate_stage_output("repomap", payload["repomap"])
    validate_stage_output("augment", payload["augment"])
    validate_stage_output("skills", payload["skills"])
    validate_stage_output("source_plan", payload["source_plan"])
    validate_context_plan(payload)

    return payload


__all__ = [
    "PLAN_TIMEOUT_DEBUG_ENV",
    "PLAN_TIMEOUT_RECOMMENDATIONS",
    "PLAN_TIMEOUT_SECONDS_ENV",
    "PlanTimeoutOutcome",
    "TimeoutResolution",
    "build_plan_timeout_fallback_payload",
    "execute_with_timeout",
    "is_plan_timeout_debug_enabled",
    "resolve_plan_timeout_seconds",
]

