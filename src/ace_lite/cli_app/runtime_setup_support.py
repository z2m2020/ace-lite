from __future__ import annotations

import subprocess
from typing import Any

import click


def _format_setup_error(operation: str, detail: str) -> str:
    normalized_operation = str(operation or "").strip() or "runtime_setup"
    normalized_detail = str(detail or "").strip() or "unknown error"
    return f"Runtime setup failed during {normalized_operation}: {normalized_detail}"


def _require_non_empty_setup_value(*, field_name: str, value: str, operation: str) -> str:
    normalized = str(value or "").strip()
    if normalized:
        return normalized
    raise click.ClickException(
        _format_setup_error(operation, f"{field_name} must not be empty")
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
            _format_setup_error(
                "add_mcp_server",
                str(add_process.stderr or add_process.stdout or "").strip(),
            )
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
                _format_setup_error(
                    "verify_mcp_server",
                    str(get_process.stderr or get_process.stdout or "").strip(),
                )
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
    normalized_codex_executable = _require_non_empty_setup_value(
        field_name="codex_executable",
        value=str(codex_executable),
        operation="normalize_inputs",
    )
    normalized_python_executable = _require_non_empty_setup_value(
        field_name="python_executable",
        value=str(python_executable),
        operation="normalize_inputs",
    )
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
    normalized_root = _require_non_empty_setup_value(
        field_name="root",
        value=identity["normalized_root"],
        operation="normalize_inputs",
    )
    normalized_skills = _require_non_empty_setup_value(
        field_name="skills_dir",
        value=identity["normalized_skills"],
        operation="normalize_inputs",
    )
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

    remove_cmd = [normalized_codex_executable, "mcp", "remove", normalized_name]
    add_cmd: list[str] = [normalized_codex_executable, "mcp", "add", normalized_name]
    for item in env_items:
        add_cmd.extend(["--env", item])
    add_cmd.extend(
        [
            "--",
            normalized_python_executable,
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


__all__ = [
    "build_codex_mcp_setup_plan",
    "execute_codex_mcp_setup_plan",
]
