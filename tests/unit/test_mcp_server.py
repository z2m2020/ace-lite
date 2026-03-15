from __future__ import annotations

import json
import time
from dataclasses import replace
from threading import Event, Thread
from pathlib import Path

import pytest

import ace_lite.mcp_server.service as mcp_service_module
from ace_lite.mcp_server import AceLiteMcpConfig, AceLiteMcpService
from ace_lite.mcp_server.server import build_mcp_server
from ace_lite.mcp_server.server_tool_registration import (
    MCP_REGISTERED_TOOL_NAMES,
    MCP_TOOL_DESCRIPTIONS,
)


def _make_service(tmp_path: Path) -> AceLiteMcpService:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    config = AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=skills_dir,
    )
    return AceLiteMcpService(config=config)


def _write_sample_repo(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "sample.py").write_text(
        (
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
            "\n"
            "class Counter:\n"
            "    def inc(self, value: int) -> int:\n"
            "        return value + 1\n"
        ),
        encoding="utf-8",
    )


def test_mcp_service_health_reports_defaults(tmp_path: Path) -> None:
    service = _make_service(tmp_path)

    payload = service.health()

    assert payload["ok"] is True
    assert payload["server_name"] == "ACE-Lite MCP Server"
    assert payload["default_root"] == str(tmp_path.resolve())
    assert payload["default_skills_dir"] == str((tmp_path / "skills").resolve())
    assert payload["memory_ready"] is False
    assert isinstance(payload.get("warnings"), list)
    assert payload["warnings"]
    assert payload["mcp_base_url"] == "http://localhost:8765"
    assert payload["embedding_enabled"] is False
    assert payload["embedding_provider"] == "hash"
    assert payload["embedding_model"] == "hash-v1"
    assert payload["embedding_dimension"] == 256
    assert payload["ollama_base_url"] == "http://localhost:11434"
    assert isinstance(payload["plan_timeout_seconds"], float)
    assert payload["request_stats"]["active_request_count"] == 0
    assert payload["request_stats"]["total_request_count"] == 0


def test_build_mcp_server_registers_expected_tool_names(tmp_path: Path) -> None:
    config = AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=tmp_path / "skills",
    )
    server = build_mcp_server(config=config)

    assert set(server._tool_manager._tools.keys()) == set(MCP_REGISTERED_TOOL_NAMES)


def test_build_mcp_server_exposes_stable_tool_metadata_and_schema(tmp_path: Path) -> None:
    config = AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=tmp_path / "skills",
    )
    server = build_mcp_server(config=config)
    tools = server._tool_manager._tools

    for name, description in MCP_TOOL_DESCRIPTIONS.items():
        assert tools[name].description == description

    assert tools["ace_plan"].parameters["required"] == ["query"]
    assert tools["ace_plan_quick"].parameters["required"] == ["query"]
    assert tools["ace_index"].parameters["properties"]["resume"]["default"] is False
    assert (
        tools["ace_memory_store"].parameters["properties"]["tags"]["anyOf"][0]["type"]
        == "object"
    )


def test_mcp_service_health_surfaces_request_stats(tmp_path: Path, monkeypatch) -> None:
    service = _make_service(tmp_path)
    notes_path = tmp_path / "context-map" / "memory_notes.test.jsonl"
    started = Event()
    release = Event()

    original_store = mcp_service_module.handle_memory_store

    def _blocking_store(**kwargs):
        started.set()
        release.wait(timeout=2.0)
        return original_store(**kwargs)

    monkeypatch.setattr(mcp_service_module, "handle_memory_store", _blocking_store)

    worker = Thread(
        target=service.memory_store,
        kwargs={
            "text": "long request",
            "namespace": "bench",
            "notes_path": str(notes_path),
        },
    )
    worker.start()
    assert started.wait(timeout=1.0) is True

    payload = service.health()
    assert payload["request_stats"]["active_request_count"] == 1
    assert payload["request_stats"]["total_request_count"] == 1
    assert payload["request_stats"]["last_request_tool"] == "ace_memory_store"
    assert payload["request_stats"]["last_request_started_at"]

    release.set()
    worker.join(timeout=2.0)
    assert worker.is_alive() is False

    payload_after = service.health()
    assert payload_after["request_stats"]["active_request_count"] == 0
    assert payload_after["request_stats"]["total_request_count"] == 1
    assert payload_after["request_stats"]["last_request_finished_at"]
    assert payload_after["request_stats"]["last_request_elapsed_ms"] >= 0.0


def test_mcp_service_index_writes_output(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    result = service.index(
        root=str(tmp_path),
        languages="python",
        output="context-map/index.test.json",
    )

    assert result["ok"] is True
    output_path = Path(result["output"])
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert isinstance(payload.get("files"), dict)
    assert result["file_count"] >= 1


def test_mcp_service_repomap_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    result = service.repomap_build(
        root=str(tmp_path),
        languages="python",
        budget_tokens=400,
        top_k=10,
        ranking_profile="graph",
        output_json="context-map/repomap.test.json",
        output_md="context-map/repomap.test.md",
    )

    assert result["ok"] is True
    assert Path(result["output_json"]).exists()
    assert Path(result["output_md"]).exists()
    assert result["selected_count"] >= 0


def test_mcp_service_repomap_uses_default_output_paths(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    result = service.repomap_build(
        root=str(tmp_path),
        languages="python",
    )

    assert result["ok"] is True
    assert result["output_json"] == str(
        (tmp_path / "context-map" / "repo_map.json").resolve()
    )
    assert result["output_md"] == str(
        (tmp_path / "context-map" / "repo_map.md").resolve()
    )
    assert Path(result["output_json"]).exists()
    assert Path(result["output_md"]).exists()


def test_mcp_service_memory_store_search_and_wipe(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    notes_path = tmp_path / "context-map" / "memory_notes.test.jsonl"

    stored = service.memory_store(
        text="OAuth refresh token fails with 401.",
        namespace="auth",
        tags={"type": "bugfix"},
        notes_path=str(notes_path),
    )
    assert stored["ok"] is True

    searched = service.memory_search(
        query="refresh token",
        limit=5,
        namespace="auth",
        notes_path=str(notes_path),
    )
    assert searched["ok"] is True
    assert searched["count"] == 1
    assert searched["items"][0]["namespace"] == "auth"

    wiped = service.memory_wipe(namespace="auth", notes_path=str(notes_path))
    assert wiped["ok"] is True
    assert wiped["removed_count"] == 1

    after = service.memory_search(
        query="refresh token",
        limit=5,
        namespace="auth",
        notes_path=str(notes_path),
    )
    assert after["count"] == 0


def test_mcp_service_feedback_record_and_stats(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)
    selected = tmp_path / "src" / "sample.py"

    recorded = service.feedback_record(
        query="openmemory 405 dimension mismatch",
        selected_path=str(selected),
        repo="demo-repo",
        root=str(tmp_path),
        profile_path="context-map/profile.json",
        position=1,
        max_entries=8,
    )
    assert recorded["ok"] is True
    assert Path(recorded["profile_path"]).exists()
    assert recorded["recorded"]["event"]["selected_path"] == "src/sample.py"
    health_after_record = service.health()
    assert health_after_record["request_stats"]["last_request_tool"] == "ace_feedback_record"

    stats = service.feedback_stats(
        repo="demo-repo",
        root=str(tmp_path),
        profile_path="context-map/profile.json",
        query="openmemory 405",
        top_n=5,
        max_entries=8,
    )
    assert stats["ok"] is True
    stats_payload = stats["stats"]
    assert stats_payload["matched_event_count"] == 1
    assert stats_payload["unique_paths"] == 1
    health_after_stats = service.health()
    assert health_after_stats["request_stats"]["last_request_tool"] == "ace_feedback_stats"


def test_mcp_service_plan_smoke_returns_summary(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    result = service.plan(
        query="add unit test for counter increment",
        repo="demo-repo",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        memory_primary="none",
        memory_secondary="none",
        top_k_files=4,
        min_candidate_score=0,
        include_full_payload=False,
    )

    assert result["ok"] is True
    assert result["query"] == "add unit test for counter increment"
    assert isinstance(result["source_plan_steps"], int)
    assert isinstance(result["candidate_files"], int)
    assert "plan" not in result


def test_mcp_service_plan_summary_surfaces_contract_versions(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    def _fake_run_plan(**kwargs):
        return {
            "index": {
                "chunk_contract": {
                    "schema_version": "y2-freeze-v1",
                },
                "subgraph_payload": {
                    "payload_version": "subgraph_payload_v1",
                    "taxonomy_version": "subgraph_edge_taxonomy_v1",
                },
            },
            "source_plan": {
                "steps": [],
                "chunk_contract": {
                    "schema_version": "y2-freeze-v1",
                },
                "subgraph_payload": {
                    "payload_version": "subgraph_payload_v1",
                    "taxonomy_version": "subgraph_edge_taxonomy_v1",
                },
                "prompt_rendering_boundary": {
                    "boundary_version": "prompt_rendering_boundary_v1",
                },
            },
            "observability": {"total_ms": 1.0},
        }

    monkeypatch.setattr(mcp_service_module, "run_plan", _fake_run_plan)

    result = service.plan(
        query="summary contract",
        repo="demo-repo",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        memory_primary="none",
        memory_secondary="none",
        include_full_payload=False,
    )

    assert result["ok"] is True
    assert result["index_chunk_contract_version"] == "y2-freeze-v1"
    assert result["source_plan_chunk_contract_version"] == "y2-freeze-v1"
    assert result["prompt_rendering_boundary_version"] == "prompt_rendering_boundary_v1"
    assert result["index_subgraph_payload_version"] == "subgraph_payload_v1"
    assert result["source_plan_subgraph_payload_version"] == "subgraph_payload_v1"
    assert result["subgraph_taxonomy_version"] == "subgraph_edge_taxonomy_v1"


def test_mcp_service_health_reports_memory_ready_when_enabled(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    config = AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=skills_dir,
    )
    config = replace(config, memory_primary="rest", memory_secondary="none")
    service = AceLiteMcpService(config=config)

    payload = service.health()

    assert payload["memory_primary"] == "rest"
    assert payload["memory_secondary"] == "none"
    assert payload["memory_ready"] is True
    assert "Memory providers are disabled" not in " ".join(payload["warnings"])


def test_mcp_service_plan_config_pack_overrides_defaults(tmp_path: Path, monkeypatch) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)
    config_pack_path = tmp_path / "pack.json"
    config_pack_path.write_text(
        json.dumps(
            {
                "schema_version": "ace-lite-config-pack-v1",
                "name": "mcp-pack",
                "overrides": {
                    "top_k_files": 3,
                    "min_candidate_score": 0,
                    "candidate_ranker": "bm25_lite",
                    "policy_version": "v2",
                    "embedding_enabled": True,
                    "embedding_provider": "ollama",
                    "embedding_model": "nomic-embed-text",
                    "embedding_dimension": 768,
                    "embedding_rerank_pool": 12,
                    "embedding_lexical_weight": 0.55,
                    "embedding_semantic_weight": 0.45,
                    "embedding_min_similarity": 0.05,
                    "embedding_fail_open": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_run_plan(**kwargs):
        captured.update(kwargs)
        return {
            "source_plan": {"steps": []},
            "observability": {"total_ms": 1.0},
        }

    monkeypatch.setattr(mcp_service_module, "run_plan", _fake_run_plan)

    result = service.plan(
        query="config pack smoke",
        repo="demo-repo",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        memory_primary="none",
        memory_secondary="none",
        include_full_payload=False,
        config_pack=str(config_pack_path),
    )

    assert result["ok"] is True
    assert captured.get("top_k_files") == 3
    assert captured.get("min_candidate_score") == 0
    assert captured.get("candidate_ranker") == "bm25_lite"
    assert captured.get("policy_version") == "v2"
    assert captured.get("embedding_enabled") is True
    assert captured.get("embedding_provider") == "ollama"
    assert captured.get("embedding_model") == "nomic-embed-text"
    assert captured.get("embedding_dimension") == 768
    assert captured.get("embedding_rerank_pool") == 12
    assert captured.get("embedding_lexical_weight") == pytest.approx(0.55)
    assert captured.get("embedding_semantic_weight") == pytest.approx(0.45)
    assert captured.get("embedding_min_similarity") == pytest.approx(0.05)
    assert captured.get("embedding_fail_open") is False


def test_mcp_service_plan_config_pack_respects_explicit_args(tmp_path: Path, monkeypatch) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)
    config_pack_path = tmp_path / "pack.json"
    config_pack_path.write_text(
        json.dumps(
            {
                "schema_version": "ace-lite-config-pack-v1",
                "name": "mcp-pack",
                "overrides": {"top_k_files": 2, "min_candidate_score": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_run_plan(**kwargs):
        captured.update(kwargs)
        return {
            "source_plan": {"steps": []},
            "observability": {"total_ms": 1.0},
        }

    monkeypatch.setattr(mcp_service_module, "run_plan", _fake_run_plan)

    result = service.plan(
        query="explicit args win",
        repo="demo-repo",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        memory_primary="none",
        memory_secondary="none",
        include_full_payload=False,
        config_pack=str(config_pack_path),
        top_k_files=5,
        min_candidate_score=4,
    )

    assert result["ok"] is True
    assert captured.get("top_k_files") == 5
    assert captured.get("min_candidate_score") == 4


def test_mcp_service_plan_quick_returns_candidate_files(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    result = service.plan_quick(
        query="counter increment",
        repo="demo-repo",
        root=str(tmp_path),
        languages="python",
        top_k_files=3,
        repomap_top_k=8,
        include_rows=True,
    )

    assert result["ok"] is True
    assert result["source_plan_steps"] == 3
    assert isinstance(result["candidate_files"], list)
    assert result["candidate_files"]
    assert isinstance(result.get("rows"), list)
    assert result["total_ms"] >= 0.0


def test_mcp_service_plan_timeout_returns_structured_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    def _slow_run_plan_payload(*args, **kwargs):
        time.sleep(1.2)
        return {"source_plan": {"steps": []}, "observability": {"total_ms": 0}}

    def _fake_plan_quick(**kwargs):
        return {
            "ok": True,
            "candidate_files": ["src/sample.py", "tests/test_sample.py"],
            "steps": ["Inspect candidate files."],
        }

    monkeypatch.setattr(service, "_run_plan_payload", _slow_run_plan_payload)
    monkeypatch.setattr(service, "plan_quick", _fake_plan_quick)

    result = service.plan(
        query="timeout case",
        repo="demo-repo",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        include_full_payload=False,
        timeout_seconds=1.0,
    )

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["reason"] == "ace_plan_timeout"
    assert result["fallback_mode"] == "plan_quick"
    assert result["candidate_files"] == 2
    assert result["candidate_file_paths"] == ["src/sample.py", "tests/test_sample.py"]
    assert result["source_plan_steps"] == 1
    assert isinstance(result.get("recommendations"), list)


def test_mcp_service_plan_defaults_plugins_disabled(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)
    captured: dict[str, object] = {}

    def _fake_run_plan(**kwargs):
        captured.update(kwargs)
        return {
            "source_plan": {"steps": []},
            "observability": {"total_ms": 1.0},
        }

    monkeypatch.setattr(mcp_service_module, "run_plan", _fake_run_plan)

    result = service.plan(
        query="default plugin guard",
        repo="demo-repo",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        include_full_payload=False,
        timeout_seconds=5.0,
    )

    assert result["ok"] is True
    assert captured.get("plugins_enabled") is False
