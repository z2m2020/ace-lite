from __future__ import annotations

import os
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import click

from ace_lite.cli_app.runtime_mcp_ops import (
    extract_memory_channels,
    load_mcp_env_snapshot,
    mcp_env_snapshot_path,
    memory_channels_disabled,
    memory_config_recommendations,
    probe_mcp_memory_endpoint,
    probe_rest_memory_endpoint,
    run_mcp_self_test,
)
from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_paths import DEFAULT_USER_RUNTIME_DB_PATH
from ace_lite.runtime_paths import resolve_user_runtime_db_path
from ace_lite.runtime_settings import RuntimeSettingsManager
from ace_lite.runtime_settings_store import (
    load_runtime_settings_with_fallback,
    resolve_user_runtime_settings_last_known_good_path,
    resolve_user_runtime_settings_path,
)
from ace_lite.runtime_stats import RuntimeScopeRollup
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
    RUNTIME_STATS_INVOCATIONS_TABLE,
    build_runtime_stats_migration_bootstrap,
)
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.stage_artifact_cache_gc import (
    vacuum_stage_artifact_cache,
    verify_stage_artifact_cache,
)


DEFAULT_RUNTIME_STATS_DB_PATH = DEFAULT_USER_RUNTIME_DB_PATH


@dataclass(frozen=True)
class RuntimeCommandDomainDescriptor:
    name: str
    handlers: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeStatusSections:
    mcp: dict[str, Any]
    plan_index: dict[str, Any]
    plan_embeddings: dict[str, Any]
    plan_replay: dict[str, Any]
    plan_trace: dict[str, Any]
    plan_lsp: dict[str, Any]
    plan_skills: dict[str, Any]
    plan_plugins: dict[str, Any]
    plan_cochange: dict[str, Any]


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


def selected_profile_from_resolved_settings(
    *,
    resolved: Any,
    persisted_record: dict[str, Any] | None,
) -> str | None:
    selected_profile = resolved.metadata.get("selected_profile")
    if selected_profile is None and isinstance(persisted_record, dict):
        metadata = persisted_record.get("metadata", {})
        if isinstance(metadata, dict):
            selected_profile = metadata.get("selected_profile")
    return str(selected_profile) if selected_profile is not None else None


def resolve_runtime_settings_bundle(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    snapshot_env, snapshot_path = load_runtime_snapshot(
        root=root,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    resolved = RuntimeSettingsManager().resolve(
        root=root,
        cwd=Path.cwd(),
        config_file=config_file,
        plan_runtime_profile=runtime_profile,
        mcp_env=dict(os.environ),
        mcp_snapshot_env=snapshot_env if snapshot_env else None,
    )
    resolved_current_path = resolve_user_runtime_settings_path(
        configured_path=current_path,
    )
    resolved_lkg_path = resolve_user_runtime_settings_last_known_good_path(
        configured_path=last_known_good_path,
    )
    persisted_record, persisted_source = load_runtime_settings_with_fallback(
        current_path=resolved_current_path,
        last_known_good_path=resolved_lkg_path,
    )
    persisted_dict = persisted_record if isinstance(persisted_record, dict) else None
    return {
        "snapshot_env": snapshot_env,
        "snapshot_path": snapshot_path,
        "resolved": resolved,
        "resolved_current_path": resolved_current_path,
        "resolved_lkg_path": resolved_lkg_path,
        "persisted_record": persisted_dict,
        "persisted_source": persisted_source,
        "selected_profile": selected_profile_from_resolved_settings(
            resolved=resolved,
            persisted_record=persisted_dict,
        ),
    }


def build_runtime_settings_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    resolved = bundle["resolved"]
    return {
        "settings": resolved.snapshot,
        "provenance": resolved.provenance,
        "fingerprint": resolved.fingerprint,
        "selected_profile": bundle["selected_profile"],
        "persisted_source": bundle["persisted_source"],
        "current_path": str(bundle["resolved_current_path"]),
        "last_known_good_path": str(bundle["resolved_lkg_path"]),
        "snapshot_loaded": bool(bundle["snapshot_env"]),
        "snapshot_path": str(bundle["snapshot_path"]),
        "stats_tags": resolved.metadata.get("stats_tags", {}),
        "metadata": resolved.metadata,
    }


def resolve_effective_runtime_skills_dir(
    settings: dict[str, Any],
    *,
    skills_dir: str = "",
) -> str:
    if skills_dir:
        return str(skills_dir)
    plan = settings.get("plan", {}) if isinstance(settings.get("plan"), dict) else {}
    plan_skills = plan.get("skills", {}) if isinstance(plan.get("skills"), dict) else {}
    return str(plan_skills.get("dir", "skills"))


def collect_runtime_settings_show_payload(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    return {
        "ok": True,
        "event": "runtime_settings_show",
        **build_runtime_settings_payload(bundle),
    }


def collect_runtime_mcp_doctor_payload(
    *,
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
) -> dict[str, Any]:
    snapshot_env, snapshot_path = load_runtime_snapshot(
        root=root,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        snapshot_path_fn=mcp_env_snapshot_path,
        load_snapshot_fn=load_mcp_env_snapshot,
    )
    payload = run_mcp_self_test(
        root=root,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        env_overrides=snapshot_env if snapshot_env else None,
    )
    memory_state = evaluate_runtime_memory_state(
        payload=payload,
        root=root,
        skills_dir=skills_dir,
        extract_memory_channels_fn=extract_memory_channels,
        memory_channels_disabled_fn=memory_channels_disabled,
        memory_config_recommendations_fn=memory_config_recommendations,
    )
    primary = str(memory_state["primary"])
    secondary = str(memory_state["secondary"])
    memory_disabled = bool(memory_state["memory_disabled"])

    checks: list[dict[str, Any]] = [
        {
            "name": "self_test",
            "ok": True,
        }
    ]
    warnings = list(memory_state["warnings"])
    recommendations = list(memory_state["recommendations"])
    endpoint_checks: list[dict[str, Any]] = []
    ok = True

    if memory_disabled:
        checks.append(
            {
                "name": "memory_configured",
                "ok": False,
                "detail": "memory_primary and memory_secondary are both none",
            }
        )
        warnings.append("Remote memory is disabled (none/none).")
        if require_memory:
            ok = False
    else:
        checks.append(
            {
                "name": "memory_configured",
                "ok": True,
                "primary": primary,
                "secondary": secondary,
            }
        )

    if probe_endpoints and not memory_disabled:
        timeout = max(0.5, float(timeout_seconds))
        channels = {primary, secondary}
        if "mcp" in channels:
            mcp_result = probe_mcp_memory_endpoint(
                base_url=str(payload.get("mcp_base_url") or "http://localhost:8765"),
                timeout_seconds=timeout,
            )
            endpoint_checks.append({"name": "mcp_endpoint", **mcp_result})
        if "rest" in channels:
            rest_result = probe_rest_memory_endpoint(
                base_url=str(payload.get("rest_base_url") or "http://localhost:8765"),
                timeout_seconds=timeout,
                user_id=str(payload.get("user_id") or "codex"),
                app=str(payload.get("app") or "ace-lite"),
            )
            endpoint_checks.append({"name": "rest_endpoint", **rest_result})

        checks.extend(endpoint_checks)
        if (
            require_memory
            and endpoint_checks
            and not any(bool(item.get("ok")) for item in endpoint_checks)
        ):
            ok = False
            warnings.append(
                "All configured memory endpoints failed probing in require-memory mode."
            )
        for item in endpoint_checks:
            if not bool(item.get("ok")):
                warnings.append(
                    f"{item.get('name')}: probe failed ({item.get('error') or item.get('fallback_error') or item.get('primary_error') or 'unknown'})"
                )

    return {
        "ok": ok,
        "event": "mcp_doctor",
        "self_test": payload,
        "checks": checks,
        "warnings": warnings,
        "recommendations": recommendations,
        "snapshot_loaded": bool(snapshot_env),
        "snapshot_path": str(snapshot_path),
    }


def collect_runtime_mcp_self_test_payload(
    *,
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
    run_mcp_self_test_fn: Any = run_mcp_self_test,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    snapshot_env, snapshot_path = load_runtime_snapshot(
        root=root,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    payload = run_mcp_self_test_fn(
        root=root,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        env_overrides=snapshot_env if snapshot_env else None,
    )
    memory_state = evaluate_runtime_memory_state(
        payload=payload,
        root=root,
        skills_dir=skills_dir,
        extract_memory_channels_fn=extract_memory_channels_fn,
        memory_channels_disabled_fn=memory_channels_disabled_fn,
        memory_config_recommendations_fn=memory_config_recommendations_fn,
    )
    if memory_state["memory_disabled"] and require_memory:
        raise click.ClickException(
            "Memory providers are disabled; rerun with configured Mem0/OpenMemory env vars."
        )
    return {
        "ok": True,
        "event": "mcp_self_test",
        "payload": payload,
        "warnings": memory_state["warnings"],
        "recommendations": memory_state["recommendations"],
        "snapshot_loaded": bool(snapshot_env),
        "snapshot_path": str(snapshot_path),
    }


def build_runtime_cache_doctor_payload(
    *,
    root: str,
    db_path: str,
    payload_root: str,
    temp_root: str,
) -> dict[str, Any]:
    report = verify_stage_artifact_cache(
        repo_root=root,
        db_path=db_path or None,
        payload_root=payload_root or None,
        temp_root=temp_root or None,
    )
    severe_issue_count = int(report.get("severe_issue_count", 0) or 0)
    warning_issue_count = int(report.get("warning_issue_count", 0) or 0)
    return {
        "ok": severe_issue_count == 0,
        "event": "runtime_doctor_cache",
        "summary": {
            "severe_issue_count": severe_issue_count,
            "warning_issue_count": warning_issue_count,
        },
        **report,
    }


def build_runtime_cache_vacuum_payload(
    *,
    root: str,
    db_path: str,
    payload_root: str,
    temp_root: str,
    apply: bool,
) -> dict[str, Any]:
    result = vacuum_stage_artifact_cache(
        repo_root=root,
        db_path=db_path or None,
        payload_root=payload_root or None,
        temp_root=temp_root or None,
        apply=apply,
    )
    return {
        "ok": bool(result.get("ok", False)),
        "event": "runtime_cache_vacuum",
        **result,
    }


def build_runtime_doctor_payload(
    *,
    root: str,
    config_file: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
    current_path: str,
    last_known_good_path: str,
    stats_db_path: str,
    cache_db_path: str,
    payload_root: str,
    temp_root: str,
) -> dict[str, Any]:
    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
    )
    resolved = bundle["resolved"]
    runtime_stats = load_runtime_stats_summary(
        db_path=stats_db_path,
        home_path=os.environ.get("HOME")
        or os.environ.get("USERPROFILE")
        or Path.home(),
    )
    cache_report = verify_stage_artifact_cache(
        repo_root=root,
        db_path=cache_db_path or None,
        payload_root=payload_root or None,
        temp_root=temp_root or None,
    )
    effective_skills_dir = resolve_effective_runtime_skills_dir(
        resolved.snapshot,
        skills_dir=skills_dir,
    )
    integration = collect_runtime_mcp_doctor_payload(
        root=root,
        skills_dir=effective_skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        require_memory=require_memory,
        probe_endpoints=probe_endpoints,
    )
    plugins_payload = (
        resolved.snapshot.get("plan", {}).get("plugins", {})
        if isinstance(resolved.snapshot.get("plan"), dict)
        and isinstance(resolved.snapshot.get("plan", {}).get("plugins"), dict)
        else {}
    )
    return {
        "ok": bool(integration.get("ok")) and bool(cache_report.get("ok")),
        "event": "runtime_doctor",
        "settings": build_runtime_settings_payload(bundle),
        "stats": runtime_stats,
        "cache": cache_report,
        "integration": {
            **integration,
            "plugin_policy": {
                "remote_slot_policy_mode": plugins_payload.get("remote_slot_policy_mode"),
                "remote_slot_allowlist": plugins_payload.get("remote_slot_allowlist"),
            },
        },
    }


def collect_runtime_status_payload(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    db_path: str,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    return {
        "ok": True,
        "event": "runtime_status",
        **build_runtime_status_snapshot(
            root=root,
            bundle=bundle,
            db_path=db_path,
            extract_memory_channels_fn=extract_memory_channels_fn,
            memory_channels_disabled_fn=memory_channels_disabled_fn,
            memory_config_recommendations_fn=memory_config_recommendations_fn,
        ),
    }


def build_runtime_status_snapshot(
    *,
    root: str,
    bundle: dict[str, Any],
    db_path: str,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
) -> dict[str, Any]:
    resolved = bundle["resolved"]
    skills_dir = resolve_effective_runtime_skills_dir(resolved.snapshot)
    memory_state = evaluate_runtime_memory_state(
        payload=resolved.snapshot.get("mcp", {})
        if isinstance(resolved.snapshot.get("mcp"), dict)
        else {},
        root=root,
        skills_dir=skills_dir,
        extract_memory_channels_fn=extract_memory_channels_fn,
        memory_channels_disabled_fn=memory_channels_disabled_fn,
        memory_config_recommendations_fn=memory_config_recommendations_fn,
    )
    runtime_stats = load_runtime_stats_summary(
        db_path=db_path,
        home_path=os.environ.get("HOME")
        or os.environ.get("USERPROFILE")
        or Path.home(),
    )
    return build_runtime_status_payload(
        root=root,
        settings=resolved.snapshot,
        fingerprint=resolved.fingerprint,
        selected_profile=bundle["selected_profile"],
        stats_tags=resolved.metadata.get("stats_tags", {}),
        snapshot_loaded=bool(bundle["snapshot_env"]),
        snapshot_path=bundle["snapshot_path"],
        memory_state=memory_state,
        runtime_stats=runtime_stats,
    )


def execute_codex_mcp_setup_plan(
    *,
    setup_plan: dict[str, Any],
    python_executable: str,
    run_subprocess_fn: Any,
    list2cmdline_fn: Any = subprocess.list2cmdline,
    write_snapshot_fn: Any,
    run_mcp_self_test_fn: Any,
    self_test_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    normalized_name = str(setup_plan["normalized_name"])
    normalized_root = str(setup_plan["normalized_root"])
    normalized_skills = str(setup_plan["normalized_skills"])
    env_items = list(setup_plan["env_items"])
    remove_cmd = list(setup_plan["remove_cmd"])
    add_cmd = list(setup_plan["add_cmd"])
    self_test_env = dict(setup_plan["self_test_env"])
    result: dict[str, Any] = dict(setup_plan["result"])
    result["commands"] = {
        "remove": list2cmdline_fn(remove_cmd),
        "add": list2cmdline_fn(add_cmd),
    }

    if not bool(result.get("apply")):
        return result

    if bool(result.get("replace")):
        run_subprocess_fn(remove_cmd, capture_output=True, text=True, check=False)

    add_process = run_subprocess_fn(add_cmd, capture_output=True, text=True, check=False)
    if add_process.returncode != 0:
        raise click.ClickException(
            "Failed to add Codex MCP server: "
            + str(add_process.stderr or add_process.stdout or "").strip()
        )

    snapshot_path = write_snapshot_fn(
        root=normalized_root,
        mcp_name=normalized_name,
        env_items=env_items,
    )
    result["snapshot_path"] = str(snapshot_path)

    if bool(result.get("verify")):
        get_cmd = [str(remove_cmd[0]), "mcp", "get", normalized_name]
        get_process = run_subprocess_fn(
            get_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        result["verify_get"] = {
            "ok": get_process.returncode == 0,
            "stdout": str(get_process.stdout or "").strip(),
            "stderr": str(get_process.stderr or "").strip(),
        }
        if get_process.returncode != 0:
            raise click.ClickException(
                "Added MCP server but verification failed: "
                + str(get_process.stderr or get_process.stdout or "").strip()
            )

        result["verify_self_test"] = run_mcp_self_test_fn(
            root=normalized_root,
            skills_dir=normalized_skills,
            python_executable=python_executable,
            timeout_seconds=float(self_test_timeout_seconds),
            env_overrides=self_test_env,
        )

    return result


def _resolve_codex_mcp_setup_identity(
    *,
    name: str,
    root: str,
    skills_dir: str,
    config_pack: str,
    user_id: str,
    resolve_cli_path_fn: Any,
    env_get_fn: Any,
) -> dict[str, str]:
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
    return {
        "normalized_name": normalized_name,
        "normalized_root": normalized_root,
        "normalized_skills": normalized_skills,
        "normalized_config_pack": normalized_config_pack,
        "resolved_user_id": resolved_user_id,
    }


def _build_codex_mcp_env_items(
    *,
    normalized_root: str,
    normalized_skills: str,
    normalized_config_pack: str,
    enable_memory: bool,
    memory_primary: str,
    memory_secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    resolved_user_id: str,
    app: str,
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
) -> list[str]:
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
    return env_items


def _build_codex_mcp_self_test_env(
    *,
    normalized_root: str,
    normalized_skills: str,
    normalized_config_pack: str,
    enable_memory: bool,
    memory_primary: str,
    memory_secondary: str,
    mcp_base_url: str,
    rest_base_url: str,
    resolved_user_id: str,
    app: str,
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
) -> dict[str, str]:
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
        self_test_env.update(
            {
                "ACE_LITE_MEMORY_PRIMARY": str(memory_primary).strip().lower()
                or "mcp",
                "ACE_LITE_MEMORY_SECONDARY": str(memory_secondary).strip().lower()
                or "rest",
                "ACE_LITE_MCP_BASE_URL": str(mcp_base_url).strip()
                or "http://localhost:8765",
                "ACE_LITE_REST_BASE_URL": str(rest_base_url).strip()
                or "http://localhost:8765",
                "ACE_LITE_USER_ID": resolved_user_id,
                "ACE_LITE_APP": str(app).strip() or "ace-lite",
            }
        )
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
    return self_test_env


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
    identity = _resolve_codex_mcp_setup_identity(
        name=name,
        root=root,
        skills_dir=skills_dir,
        config_pack=config_pack,
        user_id=user_id,
        resolve_cli_path_fn=resolve_cli_path_fn,
        env_get_fn=env_get_fn,
    )
    normalized_name = identity["normalized_name"]
    normalized_root = identity["normalized_root"]
    normalized_skills = identity["normalized_skills"]
    normalized_config_pack = identity["normalized_config_pack"]
    resolved_user_id = identity["resolved_user_id"]
    env_items = _build_codex_mcp_env_items(
        normalized_root=normalized_root,
        normalized_skills=normalized_skills,
        normalized_config_pack=normalized_config_pack,
        enable_memory=enable_memory,
        memory_primary=memory_primary,
        memory_secondary=memory_secondary,
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        resolved_user_id=resolved_user_id,
        app=app,
        enable_embeddings=enable_embeddings,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_index_path=embedding_index_path,
        embedding_rerank_pool=embedding_rerank_pool,
        embedding_lexical_weight=embedding_lexical_weight,
        embedding_semantic_weight=embedding_semantic_weight,
        embedding_min_similarity=embedding_min_similarity,
        embedding_fail_open=embedding_fail_open,
        ollama_base_url=ollama_base_url,
    )

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

    self_test_env = _build_codex_mcp_self_test_env(
        normalized_root=normalized_root,
        normalized_skills=normalized_skills,
        normalized_config_pack=normalized_config_pack,
        enable_memory=enable_memory,
        memory_primary=memory_primary,
        memory_secondary=memory_secondary,
        mcp_base_url=mcp_base_url,
        rest_base_url=rest_base_url,
        resolved_user_id=resolved_user_id,
        app=app,
        enable_embeddings=enable_embeddings,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_index_path=embedding_index_path,
        embedding_rerank_pool=embedding_rerank_pool,
        embedding_lexical_weight=embedding_lexical_weight,
        embedding_semantic_weight=embedding_semantic_weight,
        embedding_min_similarity=embedding_min_similarity,
        embedding_fail_open=embedding_fail_open,
        ollama_base_url=ollama_base_url,
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


def _resolve_runtime_status_sections(settings: dict[str, Any]) -> RuntimeStatusSections:
    plan = settings.get("plan", {}) if isinstance(settings.get("plan"), dict) else {}
    mcp = settings.get("mcp", {}) if isinstance(settings.get("mcp"), dict) else {}
    return RuntimeStatusSections(
        mcp=mcp,
        plan_index=plan.get("index", {}) if isinstance(plan.get("index"), dict) else {},
        plan_embeddings=(
            plan.get("embeddings", {})
            if isinstance(plan.get("embeddings"), dict)
            else {}
        ),
        plan_replay=(
            plan.get("plan_replay_cache", {})
            if isinstance(plan.get("plan_replay_cache"), dict)
            else {}
        ),
        plan_trace=plan.get("trace", {}) if isinstance(plan.get("trace"), dict) else {},
        plan_lsp=plan.get("lsp", {}) if isinstance(plan.get("lsp"), dict) else {},
        plan_skills=(
            plan.get("skills", {}) if isinstance(plan.get("skills"), dict) else {}
        ),
        plan_plugins=(
            plan.get("plugins", {}) if isinstance(plan.get("plugins"), dict) else {}
        ),
        plan_cochange=(
            plan.get("cochange", {}) if isinstance(plan.get("cochange"), dict) else {}
        ),
    )


def _build_runtime_status_cache_paths(
    *,
    root_path: Path,
    sections: RuntimeStatusSections,
    runtime_stats: dict[str, Any],
) -> dict[str, str | None]:
    return {
        "index": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_index.get("cache_path"),
        ),
        "embeddings": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_embeddings.get("index_path"),
        ),
        "plan_replay_cache": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_replay.get("cache_path"),
        ),
        "trace_export": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_trace.get("export_path"),
        )
        if bool(sections.plan_trace.get("export_enabled"))
        else None,
        "memory_notes": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.mcp.get("notes_path"),
        ),
        "cochange": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_cochange.get("cache_path"),
        ),
        "runtime_stats_db": str(Path(runtime_stats.get("db_path", "")).resolve()),
        "skills_dir": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_skills.get("dir"),
        ),
    }


def _build_runtime_service_health(
    *,
    cache_paths: dict[str, str | None],
    sections: RuntimeStatusSections,
    memory_state: dict[str, Any],
    runtime_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    skills_dir_path = (
        Path(cache_paths["skills_dir"])
        if isinstance(cache_paths["skills_dir"], str)
        else None
    )
    lsp_commands = sections.plan_lsp.get("commands")
    lsp_xref_commands = sections.plan_lsp.get("xref_commands")
    lsp_has_commands = bool(lsp_commands) or bool(lsp_xref_commands)
    return [
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
            "status": "ok" if bool(sections.mcp.get("embedding_enabled")) else "disabled",
            "provider": sections.mcp.get("embedding_provider"),
            "model": sections.mcp.get("embedding_model"),
            "index_path": cache_paths["embeddings"],
        },
        {
            "name": "plugins",
            "status": (
                "ok" if bool(sections.plan_plugins.get("enabled", True)) else "disabled"
            ),
            "remote_slot_policy_mode": sections.plan_plugins.get(
                "remote_slot_policy_mode"
            ),
        },
        {
            "name": "lsp",
            "status": (
                "disabled"
                if not bool(sections.plan_lsp.get("enabled"))
                else ("ok" if lsp_has_commands else "degraded")
            ),
            "enabled": bool(sections.plan_lsp.get("enabled")),
            "commands_configured": lsp_has_commands,
            "reason": "enabled_without_commands"
            if bool(sections.plan_lsp.get("enabled")) and not lsp_has_commands
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
                sections.plan_skills.get("precomputed_routing_enabled")
            ),
            "reason": ""
            if skills_dir_path is not None and skills_dir_path.exists()
            else "skills_dir_missing",
        },
        {
            "name": "trace_export",
            "status": (
                "ok"
                if bool(
                    sections.plan_trace.get("export_enabled")
                    or sections.plan_trace.get("otlp_enabled")
                )
                else "disabled"
            ),
            "export_enabled": bool(sections.plan_trace.get("export_enabled")),
            "otlp_enabled": bool(sections.plan_trace.get("otlp_enabled")),
            "export_path": cache_paths["trace_export"],
            "otlp_endpoint": sections.plan_trace.get("otlp_endpoint"),
        },
        {
            "name": "plan_replay_cache",
            "status": "ok" if bool(sections.plan_replay.get("enabled")) else "disabled",
            "enabled": bool(sections.plan_replay.get("enabled")),
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


def _build_runtime_degraded_services(
    *,
    service_health: list[dict[str, Any]],
    runtime_stats: dict[str, Any],
) -> list[dict[str, Any]]:
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
    if not isinstance(latest_session, dict):
        return degraded_services
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
    return degraded_services


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
    sections = _resolve_runtime_status_sections(settings)
    cache_paths = _build_runtime_status_cache_paths(
        root_path=root_path,
        sections=sections,
        runtime_stats=runtime_stats,
    )
    service_health = _build_runtime_service_health(
        cache_paths=cache_paths,
        sections=sections,
        memory_state=memory_state,
        runtime_stats=runtime_stats,
    )
    degraded_services = _build_runtime_degraded_services(
        service_health=service_health,
        runtime_stats=runtime_stats,
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


def _build_runtime_command_domain_registry() -> dict[str, RuntimeCommandDomainDescriptor]:
    descriptors = (
        RuntimeCommandDomainDescriptor(
            name="settings",
            handlers=(
                "resolve_runtime_settings_bundle",
                "build_runtime_settings_payload",
                "collect_runtime_settings_show_payload",
            ),
        ),
        RuntimeCommandDomainDescriptor(
            name="doctor",
            handlers=(
                "collect_runtime_mcp_doctor_payload",
                "collect_runtime_mcp_self_test_payload",
                "build_runtime_cache_doctor_payload",
                "build_runtime_cache_vacuum_payload",
                "build_runtime_doctor_payload",
            ),
        ),
        RuntimeCommandDomainDescriptor(
            name="status",
            handlers=(
                "collect_runtime_status_payload",
                "build_runtime_status_snapshot",
                "build_runtime_status_payload",
                "load_runtime_stats_summary",
                "load_latest_runtime_stats_match",
            ),
        ),
        RuntimeCommandDomainDescriptor(
            name="setup",
            handlers=(
                "build_codex_mcp_setup_plan",
                "execute_codex_mcp_setup_plan",
            ),
        ),
    )
    return {descriptor.name: descriptor for descriptor in descriptors}


RUNTIME_COMMAND_DOMAIN_REGISTRY = MappingProxyType(
    _build_runtime_command_domain_registry()
)


def iter_runtime_command_domains() -> tuple[RuntimeCommandDomainDescriptor, ...]:
    return tuple(RUNTIME_COMMAND_DOMAIN_REGISTRY.values())


__all__ = [
    "build_codex_mcp_setup_plan",
    "build_runtime_doctor_payload",
    "build_runtime_settings_payload",
    "build_runtime_status_snapshot",
    "collect_runtime_settings_show_payload",
    "collect_runtime_mcp_self_test_payload",
    "collect_runtime_status_payload",
    "DEFAULT_RUNTIME_STATS_DB_PATH",
    "evaluate_runtime_memory_state",
    "build_runtime_status_payload",
    "iter_runtime_command_domains",
    "load_latest_runtime_stats_match",
    "load_runtime_snapshot",
    "load_runtime_stats_summary",
    "resolve_runtime_settings_bundle",
    "RUNTIME_COMMAND_DOMAIN_REGISTRY",
    "resolve_user_runtime_stats_path",
]
