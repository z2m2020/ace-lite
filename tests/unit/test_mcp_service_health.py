from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.service_health import (
    RuntimeIdentityPayload,
    build_health_response_payload,
    build_runtime_identity_payload,
)


def _make_config(tmp_path: Path) -> AceLiteMcpConfig:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=skills_dir,
    )


def _runtime_identity(*, stale: bool = False) -> RuntimeIdentityPayload:
    return build_runtime_identity_payload(
        pid=42,
        process_started_at="2026-03-26T00:00:00+00:00",
        process_uptime_seconds=12.5,
        source_root="F:/deployed/ace-lite-engine-open-20260311",
        pyproject_path="F:/deployed/ace-lite-engine-open-20260311/pyproject.toml",
        module_path="F:/deployed/ace-lite-engine-open-20260311/src/ace_lite/mcp_server/service.py",
        startup_head_snapshot={
            "enabled": True,
            "reason": "ok",
            "head_commit": "old123",
            "head_ref": "main",
        },
        current_head_snapshot={
            "enabled": True,
            "reason": "ok",
            "head_commit": "new456" if stale else "old123",
            "head_ref": "main",
        },
    )


def test_build_health_payload_reports_memory_disabled_recommendations(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.44",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(),
        now_iso_fn=lambda: "2026-03-14T00:00:00+00:00",
    )

    assert payload["ok"] is True
    assert payload["memory_primary"] == "none"
    assert payload["memory_secondary"] == "none"
    assert payload["memory_ready"] is False
    assert payload["warnings"]
    assert payload["recommendations"] == [
        "Set ACE_LITE_MEMORY_PRIMARY=mcp",
        "Set ACE_LITE_MEMORY_SECONDARY=rest",
        "Set ACE_LITE_MCP_BASE_URL / ACE_LITE_REST_BASE_URL to your OpenMemory endpoint",
    ]
    assert payload["runtime_identity"]["pid"] == 42
    assert payload["staleness_warning"] is None
    assert payload["timestamp"] == "2026-03-14T00:00:00+00:00"


def test_build_health_payload_surfaces_version_drift_warning(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    config = replace(config, memory_primary="rest", memory_secondary="none")

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 1},
        version="0.3.44",
        version_info={
            "drifted": True,
            "pyproject_version": "0.3.44",
            "installed_version": "0.3.39",
            "dist_name": "ace-lite-engine",
        },
        runtime_identity=_runtime_identity(),
        now_iso_fn=lambda: "2026-03-14T00:00:01+00:00",
    )

    assert payload["memory_ready"] is True
    assert payload["warnings"]
    assert "Version drift detected" in payload["warnings"][0]
    assert payload["recommendations"] == ["python -m pip install -e .[dev]"]
    assert payload["version_info"]["reason_code"] == "install_drift"
    assert payload["version_info"]["install_drift_guidance"] == {
        "triggered": True,
        "reason_code": "install_drift",
        "message": "Installed package metadata does not match pyproject.toml. Reinstall the editable package to resync entry points and metadata.",
        "pyproject_version": "0.3.44",
        "installed_version": "0.3.39",
        "repair_steps": ["python -m pip install -e .[dev]"],
        "修复步骤": ["python -m pip install -e .[dev]"],
    }
    assert payload["request_stats"]["active_request_count"] == 1


def test_build_runtime_identity_payload_detects_stale_process() -> None:
    payload = _runtime_identity(stale=True)

    assert payload["head_changed_since_start"] is True
    assert payload["stale_process_suspected"] is True
    assert payload["stale_reason"] == "git_head_changed_since_start"
    assert payload["startup_head_commit"] == "old123"
    assert payload["current_head_commit"] == "new456"


def test_build_health_payload_adds_structured_stale_process_warning(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    config = replace(config, memory_primary="rest", memory_secondary="none")

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.64",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(stale=True),
        now_iso_fn=lambda: "2026-03-26T00:00:00+00:00",
    )

    assert payload["runtime_identity"]["stale_process_suspected"] is True
    assert payload["staleness_warning"] == {
        "triggered": True,
        "stale_reason": "git_head_changed_since_start",
        "reason": "git_head_changed_since_start",
        "reason_code": "stale_process",
        "message": "The source tree visible to this process changed after startup. Restart the long-lived stdio MCP process to load the latest code.",
        "startup_head_commit": "old123",
        "current_head_commit": "new456",
        "repair_steps": [
            "Restart the long-lived stdio MCP process so it reloads the current checkout.",
        ],
        "修复步骤": [
            "Restart the long-lived stdio MCP process so it reloads the current checkout.",
        ],
    }
    assert any("Runtime code appears stale" in item for item in payload["warnings"])
    assert any(
        "Restart the stdio MCP server/session" in item for item in payload["recommendations"]
    )
