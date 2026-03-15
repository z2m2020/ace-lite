from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.service_health import build_health_response_payload


def _make_config(tmp_path: Path) -> AceLiteMcpConfig:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=skills_dir,
    )


def test_build_health_payload_reports_memory_disabled_recommendations(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.42",
        version_info={"drifted": False},
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
    assert payload["timestamp"] == "2026-03-14T00:00:00+00:00"


def test_build_health_payload_surfaces_version_drift_warning(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    config = replace(config, memory_primary="rest", memory_secondary="none")

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 1},
        version="0.3.42",
        version_info={
            "drifted": True,
            "pyproject_version": "0.3.42",
            "installed_version": "0.3.39",
            "dist_name": "ace-lite-engine",
        },
        now_iso_fn=lambda: "2026-03-14T00:00:01+00:00",
    )

    assert payload["memory_ready"] is True
    assert payload["warnings"]
    assert "Version drift detected" in payload["warnings"][0]
    assert payload["recommendations"] == []
    assert payload["request_stats"]["active_request_count"] == 1
