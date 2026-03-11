from __future__ import annotations

from pathlib import Path
from typing import Any


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


__all__ = [
    "build_codex_mcp_setup_plan",
    "evaluate_runtime_memory_state",
    "load_runtime_snapshot",
]
