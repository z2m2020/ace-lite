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


def _runtime_identity(
    *,
    stale: bool = False,
    source_root: str = "F:/deployed/ace-lite-engine-open-20260311",
    pyproject_path: str = "F:/deployed/ace-lite-engine-open-20260311/pyproject.toml",
    module_path: str = "F:/deployed/ace-lite-engine-open-20260311/src/ace_lite/mcp_server/service.py",
) -> RuntimeIdentityPayload:
    return build_runtime_identity_payload(
        pid=42,
        parent_pid=7,
        process_started_at="2026-03-26T00:00:00+00:00",
        process_uptime_seconds=12.5,
        current_working_directory="F:/deployed/ace-lite-engine-open-20260311",
        python_executable="C:/Python/python.exe",
        command_line=["python", "-m", "ace_lite.mcp_server", "--transport", "stdio"],
        source_root=source_root,
        pyproject_path=pyproject_path,
        module_path=module_path,
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
    assert payload["runtime_identity"]["parent_pid"] == 7
    assert payload["runtime_identity"]["command_line"] == [
        "python",
        "-m",
        "ace_lite.mcp_server",
        "--transport",
        "stdio",
    ]
    assert payload["stdio_session_health"] == {
        "scope": "live_process",
        "transport": "stdio",
        "status": "ok",
        "reason_codes": [],
        "restart_recommended": False,
        "active_request_count": 0,
        "current_request_runtime_ms": 0.0,
        "message": "No stale-process or stuck-request signal detected for the current MCP process.",
    }
    assert payload["settings_governance"] == {}
    assert payload["staleness_warning"] is None
    assert payload["runtime_sync_warning"] is None
    assert payload["repo_identity"]["repo_id"] == tmp_path.name
    assert payload["repo_identity"]["worktree_name"] == tmp_path.name
    assert payload["timestamp"] == "2026-03-14T00:00:00+00:00"


def test_build_health_payload_exposes_canonical_repo_identity_for_worktree(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_root = repo_root / "tabiapp-backend_worktree_aeon_v2"
    skills_dir = worktree_root / "skills"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)
    config = AceLiteMcpConfig.from_env(
        default_root=worktree_root,
        default_skills_dir=skills_dir,
    )

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.90",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(),
        now_iso_fn=lambda: "2026-03-14T00:00:00+00:00",
    )

    assert payload["default_repo"] == "tabiapp-backend"
    assert payload["repo_identity"] == {
        "repo_id": "tabiapp-backend",
        "repo_label": "tabiapp-backend",
        "requested_repo": "tabiapp-backend",
        "source": "explicit_repo",
        "root_path": str(worktree_root.resolve()),
        "git_root": str(repo_root.resolve()),
        "git_root_name": "tabiapp-backend",
        "worktree_name": "tabiapp-backend_worktree_aeon_v2",
        "uses_git_root_name": True,
    }


def test_build_health_payload_exposes_canonical_repo_identity_for_actual_git_worktree(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_root = tmp_path / "tabiapp-backend_worktree_aeon_v2"
    skills_dir = worktree_root / "skills"
    common_git_dir = repo_root / ".git"
    worktree_git_dir = common_git_dir / "worktrees" / "tabiapp-backend_worktree_aeon_v2"
    worktree_git_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)
    (worktree_root / ".git").write_text(
        f"gitdir: {worktree_git_dir}\n",
        encoding="utf-8",
    )
    config = AceLiteMcpConfig.from_env(
        default_root=worktree_root,
        default_skills_dir=skills_dir,
    )

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.90",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(),
        now_iso_fn=lambda: "2026-03-14T00:00:00+00:00",
    )

    assert payload["default_repo"] == "tabiapp-backend"
    assert payload["repo_identity"] == {
        "repo_id": "tabiapp-backend",
        "repo_label": "tabiapp-backend",
        "requested_repo": "tabiapp-backend",
        "source": "explicit_repo",
        "root_path": str(worktree_root.resolve()),
        "git_root": str(repo_root.resolve()),
        "git_root_name": "tabiapp-backend",
        "worktree_name": "tabiapp-backend_worktree_aeon_v2",
        "uses_git_root_name": True,
    }


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
    assert payload["recommendations"] == ["C:/Python/python.exe -m pip install -e .[dev]"]
    assert payload["version_info"]["reason_code"] == "install_drift"
    assert payload["version_info"]["sync_state"] == "install_drift"
    assert payload["version_info"]["runtime_version_info"] == {
        "sync_state": "install_drift",
        "reason_code": "install_drift",
        "runtime_loaded_version": "0.3.44",
        "source_tree_version": "0.3.44",
        "installed_metadata_version": "0.3.39",
        "install_mode": "unknown",
        "install_source_root": "",
        "runtime_source_root": "F:/deployed/ace-lite-engine-open-20260311",
        "runtime_pyproject_path": "F:/deployed/ace-lite-engine-open-20260311/pyproject.toml",
        "runtime_module_path": "F:/deployed/ace-lite-engine-open-20260311/src/ace_lite/mcp_server/service.py",
        "stale_process_suspected": False,
        "mismatch_facts": [],
        "repair_steps": ["C:/Python/python.exe -m pip install -e .[dev]"],
        "修复步骤": ["C:/Python/python.exe -m pip install -e .[dev]"],
    }
    assert payload["version_info"]["install_drift_guidance"] == {
        "triggered": True,
        "reason_code": "install_drift",
        "message": "Installed package metadata does not match pyproject.toml. Reinstall the editable package to resync entry points and metadata.",
        "pyproject_version": "0.3.44",
        "installed_version": "0.3.39",
        "sync_state": "install_drift",
        "runtime_source_root": "F:/deployed/ace-lite-engine-open-20260311",
        "repair_steps": ["C:/Python/python.exe -m pip install -e .[dev]"],
        "修复步骤": ["C:/Python/python.exe -m pip install -e .[dev]"],
    }
    assert payload["runtime_sync_warning"] == {
        "triggered": True,
        "sync_state": "install_drift",
        "reason_code": "install_drift",
        "message": "Installed metadata and source-tree version are out of sync for this runtime. Refresh the local install before trusting version-sensitive diagnostics.",
        "runtime_loaded_version": "0.3.44",
        "source_tree_version": "0.3.44",
        "installed_metadata_version": "0.3.39",
        "mismatch_facts": [],
        "repair_steps": ["C:/Python/python.exe -m pip install -e .[dev]"],
        "修复步骤": ["C:/Python/python.exe -m pip install -e .[dev]"],
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
        version="0.3.82",
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
    assert payload["stdio_session_health"]["status"] == "warning"
    assert payload["stdio_session_health"]["reason_codes"] == ["stale_process"]
    assert payload["runtime_sync_warning"] == {
        "triggered": True,
        "sync_state": "stale_process",
        "reason_code": "stale_process",
        "message": "The long-lived stdio MCP process loaded an older source tree than the current checkout. Restart it before continuing.",
        "runtime_loaded_version": "0.3.82",
        "source_tree_version": None,
        "installed_metadata_version": None,
        "mismatch_facts": [],
        "repair_steps": [
            "Restart the long-lived stdio MCP process so it reloads the current checkout.",
            "C:/Python/python.exe -m pip install -U ace-lite-engine",
        ],
        "修复步骤": [
            "Restart the long-lived stdio MCP process so it reloads the current checkout.",
            "C:/Python/python.exe -m pip install -U ace-lite-engine",
        ],
    }


def test_build_health_payload_marks_runtime_source_root_mismatch_for_restart(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    config = replace(config, memory_primary="rest", memory_secondary="none")

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.90",
        version_info={
            "drifted": False,
            "reason_code": "ok",
            "install_mode": "editable",
            "source_root": "F:/deployed/ace-lite",
            "dist_name": "ace-lite-engine",
        },
        runtime_identity=_runtime_identity(
            source_root="C:/Python/Lib/site-packages/ace_lite/mcp_server",
            pyproject_path="",
            module_path="C:/Python/Lib/site-packages/ace_lite/mcp_server/service.py",
        ),
        now_iso_fn=lambda: "2026-03-26T00:00:00+00:00",
    )

    runtime_info = payload["version_info"]["runtime_version_info"]
    assert runtime_info["sync_state"] == "mixed_mode"
    assert runtime_info["mismatch_facts"] == [
        "runtime_pyproject_missing",
        "runtime_source_root_mismatch",
    ]
    assert runtime_info["repair_steps"][0] == (
        "Restart the long-lived stdio MCP process so it reloads the current checkout."
    )
    assert payload["stdio_session_health"]["status"] == "warning"
    assert payload["stdio_session_health"]["reason_codes"] == ["runtime_sync_mismatch"]
    assert payload["stdio_session_health"]["restart_recommended"] is True
    assert payload["runtime_sync_warning"] == {
        "triggered": True,
        "sync_state": "mixed_mode",
        "reason_code": "mixed_mode",
        "message": "The live MCP process is not loading the editable source tree declared by the current install. Restart it before trusting plan or health results.",
        "runtime_loaded_version": "0.3.90",
        "source_tree_version": None,
        "installed_metadata_version": None,
        "mismatch_facts": [
            "runtime_pyproject_missing",
            "runtime_source_root_mismatch",
        ],
        "repair_steps": [
            "Restart the long-lived stdio MCP process so it reloads the current checkout.",
            "C:/Python/python.exe -m pip install -e .[dev]",
        ],
        "修复步骤": [
            "Restart the long-lived stdio MCP process so it reloads the current checkout.",
            "C:/Python/python.exe -m pip install -e .[dev]",
        ],
    }


def test_build_health_payload_includes_runtime_fingerprint_observability(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _make_config(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "ace_lite.mcp_server.service_health.build_git_fast_fingerprint",
        lambda **kwargs: captured.setdefault("kwargs", kwargs) or {"fingerprint": "unused"},
    )
    monkeypatch.setattr(
        "ace_lite.mcp_server.service_health.build_git_fast_fingerprint_observability",
        lambda _value: {
            "fingerprint": "fp-runtime",
            "trust_class": "exact",
            "strategy": "git_head_dirty_settings",
            "head_commit": "abc123",
            "head_ref": "main",
            "settings_fingerprint": "settings-1",
            "dirty_path_count": 2,
            "dirty_paths_sample": ["src/a.py"],
            "elapsed_ms": 12.5,
            "timed_out": False,
            "fallback_reason": "",
            "git_available": True,
            "worktree_available": True,
        },
    )

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.90",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(),
        settings_governance={"resolved_fingerprint": "settings-1"},
        now_iso_fn=lambda: "2026-03-26T00:00:00+00:00",
    )

    assert captured["kwargs"] == {
        "repo_root": str(tmp_path.resolve()),
        "settings_fingerprint": "settings-1",
        "latency_budget_ms": 50.0,
    }
    assert payload["runtime_fingerprint"] == {
        "source": "default_root",
        "root_path": str(tmp_path.resolve()),
        "runtime_source_root": "F:/deployed/ace-lite-engine-open-20260311",
        "runtime_source_matches_default_root": False,
        "fingerprint": "fp-runtime",
        "trust_class": "exact",
        "strategy": "git_head_dirty_settings",
        "head_commit": "abc123",
        "head_ref": "main",
        "settings_fingerprint": "settings-1",
        "dirty_path_count": 2,
        "dirty_paths_sample": ["src/a.py"],
        "elapsed_ms": 12.5,
        "timed_out": False,
        "fallback_reason": "",
        "git_available": True,
        "worktree_available": True,
    }


def test_build_health_payload_adds_long_running_request_warning(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)

    payload = build_health_response_payload(
        config=config,
        request_stats={
            "active_request_count": 1,
            "current_request_runtime_ms": 30500.0,
            "recent_requests": [],
        },
        version="0.3.82",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(),
        now_iso_fn=lambda: "2026-03-26T00:00:00+00:00",
    )

    assert any("running for over 30s" in item for item in payload["warnings"])
    assert any(
        "Inspect health.request_stats.recent_requests" in item
        for item in payload["recommendations"]
    )
    assert payload["stdio_session_health"]["reason_codes"] == ["long_running_request"]
    assert payload["stdio_session_health"]["restart_recommended"] is True


def test_build_health_payload_surfaces_config_consistency_warnings(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)

    payload = build_health_response_payload(
        config=config,
        request_stats={"active_request_count": 0},
        version="0.3.82",
        version_info={"drifted": False},
        runtime_identity=_runtime_identity(),
        settings_governance={
            "config_consistency_state": "warning",
            "config_warning_count": 1,
            "config_warning_codes": ["CFG-TRACE-001"],
            "config_warnings": [
                {
                    "code": "CFG-TRACE-001",
                    "path": "plan.trace.otlp_enabled",
                    "severity": "warning",
                    "message": "trace.export_enabled=false so OTLP export stays disabled even though otlp_enabled=true",
                }
            ],
        },
        now_iso_fn=lambda: "2026-03-26T00:00:00+00:00",
    )

    assert payload["settings_governance"]["config_warning_codes"] == ["CFG-TRACE-001"]
    assert any("Config consistency warning (CFG-TRACE-001)" in item for item in payload["warnings"])
    assert any(
        "health.settings_governance.config_warnings" in item
        for item in payload["recommendations"]
    )
