from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app.runtime_status_config_support import RuntimeStatusSections
from ace_lite.cli_app.runtime_status_health_support import (
    build_runtime_degraded_services,
    build_runtime_service_health,
)


def test_runtime_status_health_support_builds_service_health_and_degraded_services(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    sections = RuntimeStatusSections(
        mcp={
            "embedding_enabled": True,
            "embedding_provider": "ollama",
            "embedding_model": "embed-model",
        },
        plan_index={},
        plan_embeddings={},
        plan_replay={"enabled": True},
        plan_trace={"export_enabled": True, "export_path": "tmp/trace.json"},
        plan_lsp={"enabled": True},
        plan_skills={"dir": str(skills_dir), "precomputed_routing_enabled": True},
        plan_plugins={"enabled": True, "remote_slot_policy_mode": "allowlist"},
        plan_cochange={},
    )
    runtime_stats = {
        "db_path": str(tmp_path / ".ace-lite" / "runtime_state.db"),
        "latest_match": {"session_id": "session-alpha"},
        "preference_capture_summary": {"event_count": 2, "store_path": "pref.db"},
        "summary": {
            "session": {
                "degraded_states": [
                    {"reason_code": "budget_exceeded"},
                ]
            }
        },
    }
    cache_paths = {
        "embeddings": str(tmp_path / "context-map/embeddings/index.json"),
        "trace_export": str(tmp_path / "tmp/trace.json"),
        "plan_replay_cache": str(tmp_path / ".ace-lite/plan-replay.json"),
        "skills_dir": str(skills_dir),
    }

    service_health = build_runtime_service_health(
        cache_paths=cache_paths,
        sections=sections,
        memory_state={
            "memory_disabled": True,
            "primary": "none",
            "secondary": "none",
            "warnings": ["memory disabled"],
            "recommendations": ["configure memory"],
        },
        runtime_stats=runtime_stats,
        version_sync={
            "ok": False,
            "reason_code": "install_drift",
            "sync_state": "install_drift",
            "version": "0.3.90",
            "source_tree_version": "0.3.90",
            "installed_metadata_version": "0.3.89",
            "recommendations": ["repair install"],
            "repair_steps": ["python -m pip install -e .[dev]"],
        },
    )
    degraded_services = build_runtime_degraded_services(
        service_health=service_health,
        runtime_stats=runtime_stats,
    )

    service_map = {item["name"]: item for item in service_health}
    assert service_map["memory"]["status"] == "disabled"
    assert service_map["embeddings"]["status"] == "ok"
    assert service_map["lsp"]["status"] == "degraded"
    assert service_map["skills"]["status"] == "ok"
    assert service_map["plan_replay_cache"]["status"] == "ok"
    assert service_map["preference_capture"]["event_count"] == 2
    assert service_map["runtime_sync"]["status"] == "degraded"
    assert service_map["runtime_sync"]["reason"] == "install_drift"
    assert service_map["runtime_sync"]["sync_state"] == "install_drift"

    assert any(
        item["name"] == "lsp"
        and item["reason"] == "enabled_without_commands"
        and item["source"] == "service_health"
        for item in degraded_services
    )
    assert any(
        item["name"] == "runtime_sync"
        and item["reason"] == "install_drift"
        and item["source"] == "service_health"
        for item in degraded_services
    )
    assert any(
        item["name"] == "runtime"
        and item["reason"] == "latency_budget_exceeded"
        and item["capture_class"] == "budget"
        and item["source"] == "latest_runtime_stats"
        for item in degraded_services
    )
