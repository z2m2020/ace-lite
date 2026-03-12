from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_paths import DEFAULT_USER_RUNTIME_DB_PATH
from ace_lite.runtime_paths import resolve_user_runtime_db_path
from ace_lite.runtime_stats import RuntimeScopeRollup
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
    RUNTIME_STATS_INVOCATIONS_TABLE,
    build_runtime_stats_migration_bootstrap,
)
from ace_lite.runtime_stats_store import DurableStatsStore


DEFAULT_RUNTIME_STATS_DB_PATH = DEFAULT_USER_RUNTIME_DB_PATH


def load_runtime_snapshot(
    *,
    root: str,
    mcp_name: str,
    use_snapshot: bool,
    snapshot_path_fn: Any,
    load_snapshot_fn: Any,
) -> tuple[dict[str, str], Path]:
    snapshot_env: dict[str, str] = {}
    snapshot_path = snapshot_path_fn(root=root, mcp_name=mcp_name)
    if use_snapshot:
        snapshot_env, snapshot_path = load_snapshot_fn(root=root, mcp_name=mcp_name)
    return snapshot_env, snapshot_path


def evaluate_runtime_memory_state(
    *,
    payload: dict[str, Any],
    root: str,
    skills_dir: str,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
) -> dict[str, Any]:
    primary, secondary = extract_memory_channels_fn(payload)
    memory_disabled = memory_channels_disabled_fn(primary=primary, secondary=secondary)
    warnings: list[str] = []
    recommendations: list[str] = []
    if memory_disabled:
        warnings.append(
            "Memory providers are disabled (memory_primary=none, memory_secondary=none)."
        )
        recommendations.extend(
            memory_config_recommendations_fn(root=root, skills_dir=skills_dir)
        )
    return {
        "primary": primary,
        "secondary": secondary,
        "memory_disabled": memory_disabled,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def build_codex_mcp_setup_plan(
    *,
    name: str,
    root: str,
    skills_dir: str,
    codex_executable: str,
    python_executable: str,
    enable_memory: bool,
    memory_primary: str,
    memory_secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    user_id: str,
    app: str,
    config_pack: str,
    enable_embeddings: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_index_path: str,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
    ollama_base_url: str,
    replace: bool,
    apply: bool,
    verify: bool,
    resolve_cli_path_fn: Any,
    env_get_fn: Any,
) -> dict[str, Any]:
    normalized_name = str(name or "").strip() or "ace-lite"
    normalized_root = resolve_cli_path_fn(root)
    normalized_skills = resolve_cli_path_fn(skills_dir)
    normalized_config_pack = str(config_pack or "").strip()
    if normalized_config_pack:
        normalized_config_pack = resolve_cli_path_fn(normalized_config_pack)
    resolved_user_id = (
        str(user_id or "").strip()
        or str(env_get_fn("ACE_LITE_USER_ID", "")).strip()
        or str(env_get_fn("USERNAME", "")).strip()
        or str(env_get_fn("USER", "")).strip()
        or "codex"
    )

    env_items: list[str] = [
        f"ACE_LITE_DEFAULT_ROOT={normalized_root}",
        f"ACE_LITE_DEFAULT_SKILLS_DIR={normalized_skills}",
    ]
    if normalized_config_pack:
        env_items.append(f"ACE_LITE_CONFIG_PACK={normalized_config_pack}")
    if enable_memory:
        env_items.extend(
            [
                f"ACE_LITE_MEMORY_PRIMARY={str(memory_primary).strip().lower() or 'mcp'}",
                f"ACE_LITE_MEMORY_SECONDARY={str(memory_secondary).strip().lower() or 'rest'}",
                f"ACE_LITE_MCP_BASE_URL={str(mcp_base_url).strip() or 'http://localhost:8765'}",
                f"ACE_LITE_REST_BASE_URL={str(rest_base_url).strip() or 'http://localhost:8765'}",
                f"ACE_LITE_USER_ID={resolved_user_id}",
                f"ACE_LITE_APP={str(app).strip() or 'ace-lite'}",
            ]
        )
    else:
        env_items.extend(
            [
                "ACE_LITE_MEMORY_PRIMARY=none",
                "ACE_LITE_MEMORY_SECONDARY=none",
            ]
        )
    if enable_embeddings:
        env_items.extend(
            [
                "ACE_LITE_EMBEDDING_ENABLED=1",
                f"ACE_LITE_EMBEDDING_PROVIDER={str(embedding_provider).strip().lower() or 'ollama'}",
                f"ACE_LITE_EMBEDDING_MODEL={str(embedding_model).strip() or 'dengcao/Qwen3-Embedding-4B:Q4_K_M'}",
                f"ACE_LITE_EMBEDDING_DIMENSION={max(8, int(embedding_dimension))}",
                f"ACE_LITE_EMBEDDING_INDEX_PATH={str(embedding_index_path).strip() or 'context-map/embeddings/index.json'}",
                f"ACE_LITE_EMBEDDING_RERANK_POOL={max(1, int(embedding_rerank_pool))}",
                f"ACE_LITE_EMBEDDING_LEXICAL_WEIGHT={max(0.0, float(embedding_lexical_weight))}",
                f"ACE_LITE_EMBEDDING_SEMANTIC_WEIGHT={max(0.0, float(embedding_semantic_weight))}",
                f"ACE_LITE_EMBEDDING_MIN_SIMILARITY={float(embedding_min_similarity)}",
                f"ACE_LITE_EMBEDDING_FAIL_OPEN={'1' if embedding_fail_open else '0'}",
                f"ACE_LITE_OLLAMA_BASE_URL={str(ollama_base_url).strip() or 'http://localhost:11434'}",
            ]
        )
    else:
        env_items.append("ACE_LITE_EMBEDDING_ENABLED=0")

    remove_cmd = [str(codex_executable), "mcp", "remove", normalized_name]
    add_cmd: list[str] = [str(codex_executable), "mcp", "add", normalized_name]
    for item in env_items:
        add_cmd.extend(["--env", item])
    add_cmd.extend(
        [
            "--",
            str(python_executable),
            "-m",
            "ace_lite.mcp_server",
            "--transport",
            "stdio",
        ]
    )

    self_test_env: dict[str, str] = {
        "ACE_LITE_DEFAULT_ROOT": normalized_root,
        "ACE_LITE_DEFAULT_SKILLS_DIR": normalized_skills,
        "ACE_LITE_MEMORY_PRIMARY": "none",
        "ACE_LITE_MEMORY_SECONDARY": "none",
        "ACE_LITE_EMBEDDING_ENABLED": "0",
    }
    if normalized_config_pack:
        self_test_env["ACE_LITE_CONFIG_PACK"] = normalized_config_pack
    if enable_memory:
        self_test_env = {
            "ACE_LITE_DEFAULT_ROOT": normalized_root,
            "ACE_LITE_DEFAULT_SKILLS_DIR": normalized_skills,
            "ACE_LITE_MEMORY_PRIMARY": str(memory_primary).strip().lower() or "mcp",
            "ACE_LITE_MEMORY_SECONDARY": str(memory_secondary).strip().lower() or "rest",
            "ACE_LITE_EMBEDDING_ENABLED": "0",
            "ACE_LITE_MCP_BASE_URL": str(mcp_base_url).strip() or "http://localhost:8765",
            "ACE_LITE_REST_BASE_URL": str(rest_base_url).strip() or "http://localhost:8765",
            "ACE_LITE_USER_ID": resolved_user_id,
            "ACE_LITE_APP": str(app).strip() or "ace-lite",
        }
        if normalized_config_pack:
            self_test_env["ACE_LITE_CONFIG_PACK"] = normalized_config_pack
    if enable_embeddings:
        self_test_env.update(
            {
                "ACE_LITE_EMBEDDING_ENABLED": "1",
                "ACE_LITE_EMBEDDING_PROVIDER": str(embedding_provider).strip().lower()
                or "ollama",
                "ACE_LITE_EMBEDDING_MODEL": str(embedding_model).strip()
                or "dengcao/Qwen3-Embedding-4B:Q4_K_M",
                "ACE_LITE_EMBEDDING_DIMENSION": str(max(8, int(embedding_dimension))),
                "ACE_LITE_EMBEDDING_INDEX_PATH": str(embedding_index_path).strip()
                or "context-map/embeddings/index.json",
                "ACE_LITE_EMBEDDING_RERANK_POOL": str(
                    max(1, int(embedding_rerank_pool))
                ),
                "ACE_LITE_EMBEDDING_LEXICAL_WEIGHT": str(
                    max(0.0, float(embedding_lexical_weight))
                ),
                "ACE_LITE_EMBEDDING_SEMANTIC_WEIGHT": str(
                    max(0.0, float(embedding_semantic_weight))
                ),
                "ACE_LITE_EMBEDDING_MIN_SIMILARITY": str(
                    float(embedding_min_similarity)
                ),
                "ACE_LITE_EMBEDDING_FAIL_OPEN": "1" if embedding_fail_open else "0",
                "ACE_LITE_OLLAMA_BASE_URL": str(ollama_base_url).strip()
                or "http://localhost:11434",
            }
        )

    return {
        "normalized_name": normalized_name,
        "normalized_root": normalized_root,
        "normalized_skills": normalized_skills,
        "normalized_config_pack": normalized_config_pack,
        "resolved_user_id": resolved_user_id,
        "env_items": env_items,
        "remove_cmd": remove_cmd,
        "add_cmd": add_cmd,
        "self_test_env": self_test_env,
        "result": {
            "ok": True,
            "event": "setup_codex_mcp",
            "apply": bool(apply),
            "replace": bool(replace),
            "verify": bool(verify),
            "name": normalized_name,
            "memory_enabled": bool(enable_memory),
            "embeddings_enabled": bool(enable_embeddings),
            "config_pack": normalized_config_pack,
            "resolved_user_id": resolved_user_id,
            "env": env_items,
        },
    }


def resolve_user_runtime_stats_path(
    *,
    home_path: str | Path | None = None,
    configured_path: str | Path | None = None,
) -> Path:
    base = Path(home_path).expanduser() if home_path is not None else Path.home()
    resolved = resolve_user_runtime_db_path(
        home_path=str(base),
        configured_path=configured_path or DEFAULT_RUNTIME_STATS_DB_PATH,
    )
    return Path(str(resolved)).resolve()


def _normalize_filter_value(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _summarize_scope(scope: RuntimeScopeRollup | None) -> dict[str, Any] | None:
    if scope is None:
        return None
    payload = scope.to_payload()
    counters = payload.get("counters", {})
    invocation_count = max(0, int(counters.get("invocation_count", 0) or 0))
    latency = dict(payload.get("latency", {}))
    latency_sum = float(latency.get("latency_ms_sum", 0.0) or 0.0)
    latency["latency_ms_avg"] = (
        round(latency_sum / invocation_count, 6) if invocation_count else 0.0
    )
    payload["latency"] = latency
    payload["stage_latencies"] = [
        {
            **dict(item),
            "latency_ms_avg": (
                round(
                    float(item.get("latency_ms_sum", 0.0) or 0.0)
                    / max(1, int(item.get("invocation_count", 0) or 0)),
                    6,
                )
                if int(item.get("invocation_count", 0) or 0) > 0
                else 0.0
            ),
        }
        for item in payload.get("stage_latencies", [])
    ]
    return payload


def _connect_runtime_stats_db(db_path: Path) -> Any:
    return connect_runtime_db(
        db_path=db_path,
        row_factory=sqlite3.Row,
        migration_bootstrap=build_runtime_stats_migration_bootstrap(),
    )


def load_latest_runtime_stats_match(
    *,
    db_path: str | Path,
    session_id: str | None = None,
    repo_key: str | None = None,
    profile_key: str | None = None,
) -> dict[str, Any] | None:
    resolved_path = Path(db_path).resolve()
    normalized_session = _normalize_filter_value(session_id)
    normalized_repo = _normalize_filter_value(repo_key)
    normalized_profile = _normalize_filter_value(profile_key)
    conn = _connect_runtime_stats_db(resolved_path)
    try:
        clauses: list[str] = []
        params: list[str] = []
        if normalized_session is not None:
            clauses.append("session_id = ?")
            params.append(normalized_session)
        if normalized_repo is not None:
            clauses.append("repo_key = ?")
            params.append(normalized_repo)
        if normalized_profile is not None:
            clauses.append("profile_key = ?")
            params.append(normalized_profile)
        sql = (
            f"SELECT invocation_id, session_id, repo_key, profile_key, finished_at "
            f"FROM {RUNTIME_STATS_INVOCATIONS_TABLE}"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY finished_at DESC, invocation_id DESC LIMIT 1"
        row = conn.execute(sql, tuple(params)).fetchone()
        if row is None:
            return None
        return {
            "invocation_id": str(row["invocation_id"]),
            "session_id": str(row["session_id"]),
            "repo_key": str(row["repo_key"]),
            "profile_key": str(row["profile_key"]),
            "finished_at": str(row["finished_at"]),
        }
    finally:
        conn.close()


def load_runtime_stats_summary(
    *,
    db_path: str | Path | None = None,
    session_id: str | None = None,
    repo_key: str | None = None,
    profile_key: str | None = None,
    home_path: str | Path | None = None,
) -> dict[str, Any]:
    resolved_path = resolve_user_runtime_stats_path(
        home_path=home_path,
        configured_path=db_path or DEFAULT_RUNTIME_STATS_DB_PATH,
    )
    normalized_repo = _normalize_filter_value(repo_key)
    normalized_profile = _normalize_filter_value(profile_key)
    store = DurableStatsStore(db_path=resolved_path)
    latest_match = load_latest_runtime_stats_match(
        db_path=resolved_path,
        session_id=session_id,
        repo_key=normalized_repo,
        profile_key=normalized_profile,
    )
    scope_map: dict[str, dict[str, Any] | None] = {
        "session": None,
        "all_time": _summarize_scope(
            store.read_scope(
                scope_kind="all_time",
                scope_key=RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
            )
        ),
        "repo": None,
        "profile": None,
        "repo_profile": None,
    }
    if latest_match is not None:
        snapshot = store.read_snapshot(
            session_id=str(latest_match["session_id"]),
            repo_key=str(latest_match["repo_key"]),
            profile_key=str(latest_match["profile_key"]) or None,
        )
        for scope in snapshot.scopes:
            scope_map[scope.scope_kind] = _summarize_scope(scope)
    scopes = [
        scope_map[name]
        for name in ("session", "all_time", "repo", "profile", "repo_profile")
        if scope_map[name] is not None
    ]
    return {
        "db_path": str(resolved_path),
        "filters": {
            "repo": normalized_repo,
            "profile": normalized_profile,
        },
        "latest_match": latest_match,
        "summary": scope_map,
        "scopes": scopes,
    }


def _resolve_repo_relative_path(*, root: str | Path, configured_path: str | Path | None) -> str | None:
    if configured_path is None:
        return None
    raw = str(configured_path).strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(root).resolve() / path
    return str(path.resolve())


def build_runtime_status_payload(
    *,
    root: str | Path,
    settings: dict[str, Any],
    fingerprint: str,
    selected_profile: str | None,
    stats_tags: dict[str, Any] | None,
    snapshot_loaded: bool,
    snapshot_path: str | Path,
    memory_state: dict[str, Any],
    runtime_stats: dict[str, Any],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    plan = settings.get("plan", {}) if isinstance(settings.get("plan"), dict) else {}
    mcp = settings.get("mcp", {}) if isinstance(settings.get("mcp"), dict) else {}
    plan_index = plan.get("index", {}) if isinstance(plan.get("index"), dict) else {}
    plan_embeddings = (
        plan.get("embeddings", {})
        if isinstance(plan.get("embeddings"), dict)
        else {}
    )
    plan_replay = (
        plan.get("plan_replay_cache", {})
        if isinstance(plan.get("plan_replay_cache"), dict)
        else {}
    )
    plan_trace = plan.get("trace", {}) if isinstance(plan.get("trace"), dict) else {}
    plan_lsp = plan.get("lsp", {}) if isinstance(plan.get("lsp"), dict) else {}
    plan_skills = (
        plan.get("skills", {}) if isinstance(plan.get("skills"), dict) else {}
    )
    plan_plugins = (
        plan.get("plugins", {}) if isinstance(plan.get("plugins"), dict) else {}
    )
    plan_cochange = (
        plan.get("cochange", {}) if isinstance(plan.get("cochange"), dict) else {}
    )

    cache_paths = {
        "index": _resolve_repo_relative_path(
            root=root_path,
            configured_path=plan_index.get("cache_path"),
        ),
        "embeddings": _resolve_repo_relative_path(
            root=root_path,
            configured_path=plan_embeddings.get("index_path"),
        ),
        "plan_replay_cache": _resolve_repo_relative_path(
            root=root_path,
            configured_path=plan_replay.get("cache_path"),
        ),
        "trace_export": _resolve_repo_relative_path(
            root=root_path,
            configured_path=plan_trace.get("export_path"),
        )
        if bool(plan_trace.get("export_enabled"))
        else None,
        "memory_notes": _resolve_repo_relative_path(
            root=root_path,
            configured_path=mcp.get("notes_path"),
        ),
        "cochange": _resolve_repo_relative_path(
            root=root_path,
            configured_path=plan_cochange.get("cache_path"),
        ),
        "runtime_stats_db": str(Path(runtime_stats.get("db_path", "")).resolve()),
        "skills_dir": _resolve_repo_relative_path(
            root=root_path,
            configured_path=plan_skills.get("dir"),
        ),
    }

    skills_dir_path = (
        Path(cache_paths["skills_dir"]) if isinstance(cache_paths["skills_dir"], str) else None
    )
    lsp_commands = plan_lsp.get("commands")
    lsp_xref_commands = plan_lsp.get("xref_commands")
    lsp_has_commands = bool(lsp_commands) or bool(lsp_xref_commands)

    service_health = [
        {
            "name": "memory",
            "status": "disabled" if bool(memory_state.get("memory_disabled")) else "ok",
            "primary": memory_state.get("primary"),
            "secondary": memory_state.get("secondary"),
            "warnings": list(memory_state.get("warnings", [])),
            "recommendations": list(memory_state.get("recommendations", [])),
        },
        {
            "name": "embeddings",
            "status": "ok" if bool(mcp.get("embedding_enabled")) else "disabled",
            "provider": mcp.get("embedding_provider"),
            "model": mcp.get("embedding_model"),
            "index_path": cache_paths["embeddings"],
        },
        {
            "name": "plugins",
            "status": "ok" if bool(plan_plugins.get("enabled", True)) else "disabled",
            "remote_slot_policy_mode": plan_plugins.get("remote_slot_policy_mode"),
        },
        {
            "name": "lsp",
            "status": (
                "disabled"
                if not bool(plan_lsp.get("enabled"))
                else ("ok" if lsp_has_commands else "degraded")
            ),
            "enabled": bool(plan_lsp.get("enabled")),
            "commands_configured": lsp_has_commands,
            "reason": "enabled_without_commands"
            if bool(plan_lsp.get("enabled")) and not lsp_has_commands
            else "",
        },
        {
            "name": "skills",
            "status": (
                "ok"
                if skills_dir_path is not None and skills_dir_path.exists()
                else "degraded"
            ),
            "skills_dir": cache_paths["skills_dir"],
            "precomputed_routing_enabled": bool(
                plan_skills.get("precomputed_routing_enabled")
            ),
            "reason": ""
            if skills_dir_path is not None and skills_dir_path.exists()
            else "skills_dir_missing",
        },
        {
            "name": "trace_export",
            "status": (
                "ok"
                if bool(plan_trace.get("export_enabled") or plan_trace.get("otlp_enabled"))
                else "disabled"
            ),
            "export_enabled": bool(plan_trace.get("export_enabled")),
            "otlp_enabled": bool(plan_trace.get("otlp_enabled")),
            "export_path": cache_paths["trace_export"],
            "otlp_endpoint": plan_trace.get("otlp_endpoint"),
        },
        {
            "name": "plan_replay_cache",
            "status": "ok" if bool(plan_replay.get("enabled")) else "disabled",
            "enabled": bool(plan_replay.get("enabled")),
            "cache_path": cache_paths["plan_replay_cache"],
        },
        {
            "name": "durable_stats",
            "status": (
                "ok"
                if runtime_stats.get("latest_match") is not None
                or Path(runtime_stats.get("db_path", "")).exists()
                else "idle"
            ),
            "db_path": runtime_stats.get("db_path"),
            "latest_session_id": (
                runtime_stats.get("latest_match", {}) or {}
            ).get("session_id"),
        },
    ]

    degraded_services = [
        {
            "name": item["name"],
            "reason": item.get("reason") or item.get("status"),
            "source": "service_health",
        }
        for item in service_health
        if item.get("status") == "degraded"
    ]

    latest_session = runtime_stats.get("summary", {}).get("session")
    if isinstance(latest_session, dict):
        degraded_states = latest_session.get("degraded_states", [])
        reason_map = {
            "memory_fallback": "memory",
            "memory_namespace_fallback": "memory",
            "trace_export_failed": "trace_export",
            "plan_replay_invalid_cached_payload": "plan_replay_cache",
            "plan_replay_store_failed": "plan_replay_cache",
            "candidate_ranker_fallback": "retrieval",
            "embedding_time_budget_exceeded": "embeddings",
            "embedding_fallback": "embeddings",
        }
        for item in degraded_states if isinstance(degraded_states, list) else []:
            reason_code = str(item.get("reason_code", "")).strip()
            if not reason_code:
                continue
            degraded_services.append(
                {
                    "name": reason_map.get(reason_code, "runtime"),
                    "reason": reason_code,
                    "source": "latest_runtime_stats",
                }
            )

    return {
        "settings_fingerprint": fingerprint,
        "selected_profile": selected_profile,
        "stats_tags": dict(stats_tags or {}),
        "snapshot_loaded": bool(snapshot_loaded),
        "snapshot_path": str(snapshot_path),
        "cache_paths": cache_paths,
        "service_health": service_health,
        "degraded_services": degraded_services,
        "latest_runtime": {
            "latest_match": runtime_stats.get("latest_match"),
            "session": runtime_stats.get("summary", {}).get("session"),
            "all_time": runtime_stats.get("summary", {}).get("all_time"),
        },
    }


__all__ = [
    "build_codex_mcp_setup_plan",
    "DEFAULT_RUNTIME_STATS_DB_PATH",
    "evaluate_runtime_memory_state",
    "build_runtime_status_payload",
    "load_latest_runtime_stats_match",
    "load_runtime_snapshot",
    "load_runtime_stats_summary",
    "resolve_user_runtime_stats_path",
]
