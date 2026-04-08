from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

import pytest

import ace_lite.mcp_server.service as mcp_service_module
from ace_lite.mcp_server import AceLiteMcpConfig, AceLiteMcpService
from ace_lite.mcp_server.server import build_mcp_server
from ace_lite.mcp_server.server_tool_registration import (
    MCP_REGISTERED_TOOL_NAMES,
    MCP_TOOL_DESCRIPTIONS,
)
from ace_lite.mcp_server.service_retrieval_graph_view_handlers import (
    handle_retrieval_graph_view_request,
)
from ace_lite.memory_long_term.contracts import build_long_term_fact_contract_v1
from ace_lite.memory_long_term.store import LongTermMemoryStore
from ace_lite.retrieval_graph_view import RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION


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


def _minimal_retrieval_plan() -> dict[str, object]:
    return {
        "query": "implement adder",
        "repo": "mini-calc",
        "root": "/tmp/mini-calc",
        "candidate_files": [
            {"path": "src/adder.py", "score": 9.0},
            {"path": "tests/test_adder.py", "score": 3.0},
        ],
        "candidate_chunks": [
            {
                "path": "src/adder.py",
                "qualified_name": "add",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 3,
                "score": 9.0,
            },
            {
                "path": "src/adder.py",
                "qualified_name": "subtract",
                "kind": "function",
                "lineno": 5,
                "end_lineno": 7,
                "score": 7.5,
            },
            {
                "path": "tests/test_adder.py",
                "qualified_name": "test_add",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 5,
                "score": 3.0,
            },
        ],
        "index": {"candidate_files": []},
        "repomap": {"focused_files": ["src/adder.py", "tests/test_adder.py"]},
        "subgraph_payload": {
            "enabled": True,
            "reason": "ok",
            "seed_paths": ["src/adder.py"],
            "edge_counts": {"cochange_edges": 2},
        },
    }


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
    assert payload["runtime_identity"]["pid"] > 0
    assert payload["runtime_identity"]["process_started_at"]
    assert payload["runtime_identity"]["module_path"].endswith("service.py")
    assert payload["staleness_warning"] is None
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
    assert tools["ace_plan"].parameters["properties"]["plugins_enabled"]["default"] is False
    assert tools["ace_plan_quick"].parameters["required"] == ["query"]
    assert tools["ace_index"].parameters["properties"]["resume"]["default"] is False
    assert (
        tools["ace_memory_store"].parameters["properties"]["tags"]["anyOf"][0]["type"] == "object"
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


def test_mcp_service_health_surfaces_stale_runtime_warning(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service._startup_head_snapshot = {
        "enabled": True,
        "reason": "ok",
        "head_commit": "old123",
        "head_ref": "main",
    }
    service._collect_runtime_head_snapshot = lambda: {
        "enabled": True,
        "reason": "ok",
        "head_commit": "new456",
        "head_ref": "main",
    }

    payload = service.health()

    assert payload["runtime_identity"]["stale_process_suspected"] is True
    assert payload["staleness_warning"]["reason"] == "git_head_changed_since_start"
    assert payload["staleness_warning"]["startup_head_commit"] == "old123"
    assert payload["staleness_warning"]["current_head_commit"] == "new456"
    assert any("Runtime code appears stale" in item for item in payload["warnings"])


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


def test_mcp_service_memory_graph_view_reads_long_term_graph(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    db_path = tmp_path / "context-map" / "long_term_memory.db"
    store = LongTermMemoryStore(db_path=db_path)
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-2",
            fact_type="repo_policy",
            subject="reuse_checkout_or_skip",
            predicate="recommended_for",
            object_value="runtime.validation.git",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:43:00+08:00",
            valid_from="2026-03-19T09:43:00+08:00",
            derived_from_observation_id="obs-2",
        )
    )

    payload = service.memory_graph_view(
        fact_handle="fact-1",
        max_hops=2,
        limit=8,
        root=str(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == "ltm_graph_view_v1"
    assert payload["focus"]["handle"] == "fact-1"
    assert payload["summary"]["triple_count"] == 2
    assert payload["edges"][0]["fact_handle"] == "fact-1"


def test_handle_retrieval_graph_view_request_empty_payload_returns_not_ok() -> None:
    payload = handle_retrieval_graph_view_request(
        plan_payload={},
        limit=50,
        max_hops=1,
        repo="mini-calc",
        root="/tmp/mini-calc",
        query="implement adder",
    )

    assert payload["ok"] is False
    assert payload["schema_version"] == RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION
    assert payload["nodes"] == []


def test_handle_retrieval_graph_view_request_minimal_payload_returns_nodes() -> None:
    payload = handle_retrieval_graph_view_request(
        plan_payload=_minimal_retrieval_plan(),
        limit=50,
        max_hops=1,
        repo="mini-calc",
        root="/tmp/mini-calc",
        query="implement adder",
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION
    assert payload["summary"]["node_count"] == len(payload["nodes"])
    assert {node["id"] for node in payload["nodes"]} >= {"src/adder.py"}


def test_handle_retrieval_graph_view_request_respects_limit() -> None:
    payload = handle_retrieval_graph_view_request(
        plan_payload=_minimal_retrieval_plan(),
        limit=5,
        max_hops=1,
        repo="mini-calc",
        root="/tmp/mini-calc",
        query="implement adder",
    )

    assert payload["summary"]["limit"] == 5
    assert payload["summary"]["node_count"] <= 5


def test_handle_retrieval_graph_view_request_respects_max_hops() -> None:
    payload = handle_retrieval_graph_view_request(
        plan_payload=_minimal_retrieval_plan(),
        limit=50,
        max_hops=2,
        repo="mini-calc",
        root="/tmp/mini-calc",
        query="implement adder",
    )

    assert payload["scope"]["max_hops"] == 2
    assert payload["summary"]["max_hops"] == 2


def test_mcp_service_retrieval_graph_view_runs_plan_under_mocked_tracking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _make_service(tmp_path)
    captured_plan_kwargs: dict[str, object] = {}
    captured_tool_names: list[str] = []

    def _fake_run_tracked(tool_name, operation):
        captured_tool_names.append(tool_name)
        return operation()

    def _fake_plan(**kwargs):
        captured_plan_kwargs.update(kwargs)
        return {"ok": True, "plan": _minimal_retrieval_plan()}

    monkeypatch.setattr(service, "_run_tracked", _fake_run_tracked)
    monkeypatch.setattr(service, "plan", _fake_plan)

    payload = service.retrieval_graph_view(
        query="implement adder",
        repo="mini-calc",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        memory_primary="none",
        memory_secondary="none",
        limit=5,
        max_hops=2,
    )

    assert captured_tool_names == ["ace_retrieval_graph_view"]
    assert captured_plan_kwargs["include_full_payload"] is True
    assert payload["ok"] is True
    assert payload["scope"]["limit"] == 5
    assert payload["scope"]["max_hops"] == 2


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
    assert result["output_json"] == str((tmp_path / "context-map" / "repo_map.json").resolve())
    assert result["output_md"] == str((tmp_path / "context-map" / "repo_map.md").resolve())
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
        user_id="svc-user",
        profile_key="bugfix",
        root=str(tmp_path),
        profile_path="context-map/profile.json",
        position=1,
        max_entries=8,
    )
    assert recorded["ok"] is True
    assert Path(recorded["profile_path"]).exists()
    assert recorded["recorded"]["event"]["selected_path"] == "src/sample.py"
    assert recorded["recorded"]["event"]["user_id"] == "svc-user"
    assert recorded["recorded"]["event"]["profile_key"] == "bugfix"
    health_after_record = service.health()
    assert health_after_record["request_stats"]["last_request_tool"] == "ace_feedback_record"

    stats = service.feedback_stats(
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
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
    assert stats_payload["user_id_filter"] == "svc-user"
    assert stats_payload["profile_key_filter"] == "bugfix"
    health_after_stats = service.health()
    assert health_after_stats["request_stats"]["last_request_tool"] == "ace_feedback_stats"


def test_mcp_service_feedback_record_falls_back_to_config_user_id(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    base_service = _make_service(tmp_path)
    service = AceLiteMcpService(
        config=replace(base_service.config, user_id="default-mcp-user"),
    )
    selected = tmp_path / "src" / "sample.py"

    recorded = service.feedback_record(
        query="runtime status profile alignment",
        selected_path=str(selected),
        repo="demo-repo",
        root=str(tmp_path),
        profile_path="context-map/profile.json",
        position=1,
        max_entries=8,
    )

    assert recorded["ok"] is True
    assert recorded["recorded"]["event"]["user_id"] == "default-mcp-user"


def test_mcp_service_issue_report_record_and_list(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)
    selected = tmp_path / "src" / "sample.py"

    recorded = service.issue_report_record(
        title="validation payload missing selected path",
        query="validation missing selected path",
        actual_behavior="selected path missing from validation payload",
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
        root=str(tmp_path),
        category="validation",
        severity="high",
        status="open",
        expected_behavior="selected path should be included",
        repro_steps=["run ace_plan", "inspect output"],
        selected_path=str(selected),
        plan_payload_ref="run-123",
        attachments=["artifact://validation.json"],
        occurred_at="2026-03-19T00:00:00+00:00",
    )

    listed = service.issue_report_list(
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
        root=str(tmp_path),
        status="open",
        category="validation",
        severity="high",
        limit=10,
    )

    assert recorded["ok"] is True
    assert recorded["report"]["selected_path"] == "src/sample.py"
    assert listed["ok"] is True
    assert listed["count"] == 1
    assert listed["reports"][0]["plan_payload_ref"] == "run-123"


def test_mcp_service_issue_report_export_case_and_apply_fix(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)
    selected = tmp_path / "src" / "sample.py"
    issue_store_path = tmp_path / "context-map" / "issue_reports.db"
    dev_feedback_path = tmp_path / "context-map" / "dev_feedback.db"

    recorded = service.issue_report_record(
        title="validation payload missing selected path",
        query="validation missing selected path",
        actual_behavior="selected path missing from validation payload",
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
        root=str(tmp_path),
        category="validation",
        severity="high",
        status="open",
        expected_behavior="selected path should be included",
        repro_steps=["run ace_plan", "inspect output"],
        selected_path=str(selected),
        plan_payload_ref="run-123",
        attachments=["artifact://validation.json"],
        occurred_at="2026-03-19T00:00:00+00:00",
        issue_id="iss_demo1234",
    )
    fix = service.dev_fix_record(
        reason_code="memory_fallback",
        repo="demo-repo",
        resolution_note="patched validation payload",
        store_path=str(dev_feedback_path),
        user_id="svc-user",
        profile_key="bugfix",
        issue_id="iss_demo1234",
        query="validation missing selected path",
        selected_path="src/sample.py",
        created_at="2026-03-19T00:05:00+00:00",
        fix_id="devf_demo1234",
    )
    exported = service.issue_report_export_case(
        issue_id="iss_demo1234",
        root=str(tmp_path),
        store_path=str(issue_store_path),
        output_path="benchmark/cases/feedback_issue_reports.yaml",
    )
    resolved = service.issue_report_apply_fix(
        issue_id="iss_demo1234",
        fix_id="devf_demo1234",
        root=str(tmp_path),
        issue_store_path=str(issue_store_path),
        dev_feedback_path=str(dev_feedback_path),
    )

    assert recorded["ok"] is True
    assert fix["ok"] is True
    assert exported["ok"] is True
    assert exported["case"]["case_id"] == "issue-report-iss-demo1234"
    assert Path(exported["output_path"]).exists() is True
    assert resolved["ok"] is True
    assert resolved["report"]["status"] == "resolved"
    assert resolved["report"]["resolution_note"] == "patched validation payload"


def test_mcp_service_dev_feedback_round_trip(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    store_path = tmp_path / "context-map" / "dev_feedback.db"

    recorded_issue = service.dev_issue_record(
        title="git fallback slows augment",
        reason_code="memory_fallback",
        repo="demo-repo",
        store_path=str(store_path),
        user_id="svc-user",
        profile_key="bugfix",
        query="augment latency",
        selected_path="src/sample.py",
        related_invocation_id="inv-123",
        notes="seen in runtime doctor",
        status="open",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:01:00+00:00",
        issue_id="dev-issue-1",
    )
    recorded_fix = service.dev_fix_record(
        reason_code="memory_fallback",
        repo="demo-repo",
        resolution_note="added cache warming",
        store_path=str(store_path),
        user_id="svc-user",
        profile_key="bugfix",
        issue_id="dev-issue-1",
        query="augment latency",
        selected_path="src/sample.py",
        related_invocation_id="inv-123",
        created_at="2026-03-19T00:02:00+00:00",
        fix_id="dev-fix-1",
    )
    summary = service.dev_feedback_summary(
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
        store_path=str(store_path),
    )

    assert recorded_issue["ok"] is True
    assert recorded_issue["issue"]["issue_id"] == "dev-issue-1"
    assert recorded_fix["ok"] is True
    assert recorded_fix["fix"]["fix_id"] == "dev-fix-1"
    assert summary["ok"] is True
    assert summary["summary"]["issue_count"] == 1
    assert summary["summary"]["open_issue_count"] == 1
    assert summary["summary"]["fix_count"] == 1
    assert summary["summary"]["by_reason_code"][0]["reason_code"] == "memory_fallback"


def test_mcp_service_dev_feedback_record_fix_and_summary(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    service = _make_service(tmp_path)

    recorded_issue = service.dev_issue_record(
        title="Memory fallback while planning",
        reason_code="memory_fallback",
        repo="demo-repo",
        store_path=str(tmp_path / "context-map" / "dev-feedback.db"),
        user_id="svc-user",
        profile_key="bugfix",
        query="why did memory fallback",
        selected_path="src/sample.py",
        related_invocation_id="inv-123",
        notes="first report",
        status="open",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:00:00+00:00",
        issue_id="devi_memory_fallback",
    )
    recorded_fix = service.dev_fix_record(
        reason_code="memory_fallback",
        repo="demo-repo",
        resolution_note="added fallback diagnostics",
        store_path=str(tmp_path / "context-map" / "dev-feedback.db"),
        user_id="svc-user",
        profile_key="bugfix",
        issue_id="devi_memory_fallback",
        query="why did memory fallback",
        selected_path="src/sample.py",
        related_invocation_id="inv-123",
        created_at="2026-03-19T00:05:00+00:00",
        fix_id="devf_memory_fallback",
    )
    summary = service.dev_feedback_summary(
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
        store_path=str(tmp_path / "context-map" / "dev-feedback.db"),
    )

    assert recorded_issue["ok"] is True
    assert recorded_issue["issue"]["reason_code"] == "memory_fallback"
    assert recorded_fix["ok"] is True
    assert recorded_fix["fix"]["issue_id"] == "devi_memory_fallback"
    assert summary["ok"] is True
    assert summary["summary"]["issue_count"] == 1
    assert summary["summary"]["fix_count"] == 1
    assert summary["summary"]["by_reason_code"][0]["reason_code"] == "memory_fallback"
    health_after = service.health()
    assert health_after["request_stats"]["last_request_tool"] == "ace_dev_feedback_summary"


def test_mcp_service_dev_issue_from_runtime_round_trip(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    long_term:\n"
            "      enabled: true\n"
            "      write_enabled: true\n"
            "      path: context-map/long_term_memory.db\n"
        ),
        encoding="utf-8",
    )
    service = _make_service(tmp_path)
    stats_db_path = tmp_path / "context-map" / "runtime-stats.db"
    store_path = tmp_path / "context-map" / "dev-feedback.db"

    from ace_lite.runtime_stats import RuntimeInvocationStats
    from ace_lite.runtime_stats_store import DurableStatsStore

    DurableStatsStore(db_path=stats_db_path).record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-runtime-1",
            session_id="sess-1",
            repo_key="demo-repo",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=21.0,
            started_at="2026-03-19T00:00:00+00:00",
            finished_at="2026-03-19T00:00:01+00:00",
            degraded_reason_codes=("memory_fallback",),
        )
    )

    recorded_issue = service.dev_issue_from_runtime(
        invocation_id="inv-runtime-1",
        stats_db_path=str(stats_db_path),
        store_path=str(store_path),
        notes="confirmed from MCP",
        user_id="svc-user",
        issue_id="devi_runtime_1",
    )

    assert recorded_issue["ok"] is True
    assert recorded_issue["issue"]["issue_id"] == "devi_runtime_1"
    assert recorded_issue["issue"]["repo"] == "demo-repo"
    assert recorded_issue["issue"]["reason_code"] == "memory_fallback"
    assert recorded_issue["invocation"]["invocation_id"] == "inv-runtime-1"
    assert recorded_issue["long_term_capture"]["ok"] is True
    assert recorded_issue["long_term_capture"]["stage"] == "dev_issue"


def test_mcp_service_dev_issue_apply_fix_updates_summary(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    long_term:\n"
            "      enabled: true\n"
            "      write_enabled: true\n"
            "      path: context-map/long_term_memory.db\n"
        ),
        encoding="utf-8",
    )
    service = _make_service(tmp_path)
    store_path = tmp_path / "context-map" / "dev-feedback.db"

    service.dev_issue_record(
        title="Memory fallback while planning",
        reason_code="memory_fallback",
        repo="demo-repo",
        store_path=str(store_path),
        user_id="svc-user",
        profile_key="bugfix",
        status="open",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:00:00+00:00",
        issue_id="devi_memory_fallback",
    )
    service.dev_fix_record(
        reason_code="memory_fallback",
        repo="demo-repo",
        resolution_note="added cache warming",
        store_path=str(store_path),
        user_id="svc-user",
        profile_key="bugfix",
        issue_id="devi_memory_fallback",
        created_at="2026-03-19T00:05:00+00:00",
        fix_id="devf_memory_fallback",
    )

    resolved = service.dev_issue_apply_fix(
        issue_id="devi_memory_fallback",
        fix_id="devf_memory_fallback",
        store_path=str(store_path),
        status="fixed",
    )
    summary = service.dev_feedback_summary(
        repo="demo-repo",
        user_id="svc-user",
        profile_key="bugfix",
        store_path=str(store_path),
    )

    assert resolved["ok"] is True
    assert resolved["issue"]["status"] == "fixed"
    assert resolved["long_term_capture"]["ok"] is True
    assert resolved["long_term_capture"]["stage"] == "dev_issue_resolution"
    assert summary["summary"]["issue_count"] == 1
    assert summary["summary"]["open_issue_count"] == 0


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


def test_mcp_service_plan_summary_surfaces_contract_versions(tmp_path: Path, monkeypatch) -> None:
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
    docs_dir = tmp_path / "docs" / "planning"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "2026-03-26_status.md").write_text("Current status\n", encoding="utf-8")
    service = _make_service(tmp_path)

    result = service.plan_quick(
        query="sync docs update latest status",
        repo="demo-repo",
        root=str(tmp_path),
        languages="python,markdown",
        top_k_files=3,
        repomap_top_k=8,
        include_rows=True,
    )

    assert result["ok"] is True
    assert result["source_plan_steps"] == 3
    assert isinstance(result["candidate_files"], list)
    assert result["candidate_files"]
    assert isinstance(result["retrieval_policy_profile"], str)
    assert result["retrieval_policy_profile"]
    assert (
        result["retrieval_policy_observability"]["selected"] == result["retrieval_policy_profile"]
    )
    assert isinstance(result["candidate_domain_summary"], dict)
    assert isinstance(result["suggested_query_refinements"], list)
    assert result["suggested_query_refinements"]
    assert isinstance(result.get("rows"), list)
    assert result["total_ms"] >= 0.0


def test_mcp_service_plan_timeout_returns_structured_fallback(tmp_path: Path, monkeypatch) -> None:
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


def test_mcp_service_plan_defaults_plugins_disabled(tmp_path: Path, monkeypatch) -> None:
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
