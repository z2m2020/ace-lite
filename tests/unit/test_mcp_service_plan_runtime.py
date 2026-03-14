from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.plan_request import resolve_plan_request_options
from ace_lite.mcp_server.service_plan_runtime import (
    build_mcp_plan_memory_provider_kwargs,
    execute_mcp_plan_payload,
)


def _make_config(tmp_path: Path) -> AceLiteMcpConfig:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=skills_dir,
    )


def test_build_mcp_plan_memory_provider_kwargs_uses_service_defaults(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    options = resolve_plan_request_options(
        config=config,
        top_k_files=8,
        min_candidate_score=2,
        retrieval_policy="auto",
        lsp_enabled=False,
        plugins_enabled=False,
        config_pack_overrides={"memory_notes_enabled": False},
    )

    payload = build_mcp_plan_memory_provider_kwargs(
        config=config,
        root_path=tmp_path,
        options=options,
        memory_primary=" MCP ",
        memory_secondary=" ",
    )

    assert payload["primary"] == "mcp"
    assert payload["secondary"] == "none"
    assert payload["memory_strategy"] == "hybrid"
    assert payload["memory_hybrid_limit"] == 20
    assert payload["memory_cache_enabled"] is True
    assert payload["memory_cache_path"] == str(tmp_path / "context-map" / "memory_cache.jsonl")
    assert payload["memory_cache_ttl_seconds"] == 604800
    assert payload["memory_cache_max_entries"] == 5000
    assert payload["memory_notes_enabled"] is False
    assert payload["mcp_base_url"] == config.mcp_base_url
    assert payload["rest_base_url"] == config.rest_base_url


def test_execute_mcp_plan_payload_wires_provider_and_run_plan(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    options = resolve_plan_request_options(
        config=config,
        top_k_files=5,
        min_candidate_score=1,
        retrieval_policy="feature",
        lsp_enabled=True,
        plugins_enabled=True,
        config_pack_overrides={
            "embedding_enabled": True,
            "embedding_provider": "ollama",
            "policy_version": "v2",
        },
    )
    captured_memory: dict[str, Any] = {}
    captured_run_plan: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> str:
        captured_memory.update(kwargs)
        return "memory-provider"

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured_run_plan.update(kwargs)
        return {"ok": True, "source_plan": {"steps": []}}

    result = execute_mcp_plan_payload(
        create_memory_provider_fn=fake_create_memory_provider,
        run_plan_fn=fake_run_plan,
        config=config,
        normalized_query="query",
        resolved_repo="demo-repo",
        root_path=tmp_path,
        skills_path=tmp_path / "skills",
        time_range="30d",
        start_date="2026-03-01",
        end_date="2026-03-14",
        memory_primary="none",
        memory_secondary="rest",
        options=options,
    )

    assert result["ok"] is True
    assert captured_memory["primary"] == "none"
    assert captured_memory["secondary"] == "rest"
    assert captured_run_plan["query"] == "query"
    assert captured_run_plan["repo"] == "demo-repo"
    assert captured_run_plan["root"] == str(tmp_path)
    assert captured_run_plan["skills_dir"] == str(tmp_path / "skills")
    assert captured_run_plan["time_range"] == "30d"
    assert captured_run_plan["start_date"] == "2026-03-01"
    assert captured_run_plan["end_date"] == "2026-03-14"
    assert captured_run_plan["memory_provider"] == "memory-provider"
    assert captured_run_plan["top_k_files"] == 5
    assert captured_run_plan["min_candidate_score"] == 1
    assert captured_run_plan["retrieval_policy"] == "feature"
    assert captured_run_plan["lsp_enabled"] is True
    assert captured_run_plan["plugins_enabled"] is True
    assert captured_run_plan["embedding_enabled"] is True
    assert captured_run_plan["embedding_provider"] == "ollama"
    assert captured_run_plan["policy_version"] == "v2"
