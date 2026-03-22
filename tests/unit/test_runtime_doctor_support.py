from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app import runtime_doctor_support
from ace_lite.cli_app import runtime_command_support
from ace_lite.cli_app import runtime_settings_support
from ace_lite.cli_app.runtime_command_support import (
    build_runtime_cache_doctor_payload,
    build_runtime_cache_vacuum_payload,
    build_runtime_doctor_payload,
    build_runtime_git_doctor_payload,
    build_runtime_version_sync_payload,
)
from ace_lite.runtime_stats_schema import RUNTIME_STATS_DOCTOR_EVENT_CLASS
from ace_lite.runtime_stats_store import DurableStatsStore


def test_runtime_doctor_support_facade_reexports_doctor_helpers() -> None:
    assert build_runtime_cache_doctor_payload is runtime_doctor_support.build_runtime_cache_doctor_payload
    assert build_runtime_cache_vacuum_payload is runtime_doctor_support.build_runtime_cache_vacuum_payload
    assert build_runtime_doctor_payload is runtime_doctor_support.build_runtime_doctor_payload
    assert build_runtime_git_doctor_payload is runtime_doctor_support.build_runtime_git_doctor_payload
    assert build_runtime_version_sync_payload is runtime_doctor_support.build_runtime_version_sync_payload


def test_build_runtime_git_doctor_payload_accepts_non_git_repo(tmp_path: Path) -> None:
    payload = runtime_doctor_support.build_runtime_git_doctor_payload(
        root=str(tmp_path),
        timeout_seconds=1.0,
    )

    assert payload["ok"] is True
    assert payload["enabled"] is False
    assert payload["reason"] == "not_git_repo"


def test_build_runtime_git_doctor_payload_classifies_git_launch_failure(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    payload = runtime_doctor_support.build_runtime_git_doctor_payload(
        root=str(tmp_path),
        timeout_seconds=1.0,
        find_git_root_fn=lambda root: Path(root),
        collect_git_head_snapshot_fn=lambda **kwargs: {
            "enabled": True,
            "reason": "error",
            "error": "error launching git:",
            "head_commit": "",
            "head_ref": "",
        },
        collect_git_worktree_summary_fn=lambda **kwargs: {
            "enabled": True,
            "reason": "error",
            "error": "error launching git:",
            "changed_count": 0,
            "entries": [],
        },
    )

    assert payload["ok"] is False
    assert payload["issue_type"] == "git_unavailable"
    assert payload["git_available"] is False
    assert payload["recommendations"]


def test_build_runtime_version_sync_payload_detects_install_drift() -> None:
    payload = runtime_doctor_support.build_runtime_version_sync_payload(
        get_version_info_fn=lambda **kwargs: {
            "dist_name": "ace-lite-engine",
            "version": "0.3.51",
            "source": "pyproject",
            "pyproject_version": "0.3.51",
            "installed_version": "0.3.44",
            "drifted": True,
        }
    )

    assert payload["ok"] is False
    assert payload["reason"] == "install_drift"
    assert payload["recommendations"]


def test_collect_runtime_doctor_degraded_reason_codes_normalizes_doctor_failures() -> None:
    payload = runtime_doctor_support._collect_runtime_doctor_degraded_reason_codes(
        cache_report={"severe_issue_count": 2},
        git_payload={"issue_type": "git_unavailable"},
        version_sync={"reason": "install_drift"},
    )

    assert payload == [
        "stage_artifact_cache_corrupt",
        "git_unavailable",
        "install_drift",
    ]


def test_build_runtime_doctor_payload_exposes_canonical_doctor_reason_codes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_settings_support,
        "resolve_runtime_settings_bundle",
        lambda **kwargs: {
            "resolved": type("Resolved", (), {"snapshot": {"plan": {"plugins": {}}}})()
        },
    )
    monkeypatch.setattr(
        runtime_settings_support,
        "resolve_effective_runtime_skills_dir",
        lambda snapshot, skills_dir: skills_dir,
    )
    monkeypatch.setattr(
        runtime_settings_support,
        "build_runtime_settings_payload",
        lambda bundle: {"settings": {}, "fingerprint": "fp-doctor"},
    )
    monkeypatch.setattr(
        runtime_command_support,
        "collect_runtime_mcp_doctor_payload",
        lambda **kwargs: {"ok": True, "event": "mcp_doctor"},
    )
    monkeypatch.setattr(
        runtime_doctor_support,
        "load_runtime_stats_summary",
        lambda **kwargs: {"latest_match": None, "summary": {}},
    )
    monkeypatch.setattr(
        runtime_doctor_support,
        "verify_stage_artifact_cache",
        lambda **kwargs: {"ok": False, "severe_issue_count": 1, "warning_issue_count": 0},
    )
    monkeypatch.setattr(
        runtime_doctor_support,
        "build_runtime_git_doctor_payload",
        lambda **kwargs: {"ok": False, "issue_type": "git_unavailable"},
    )
    monkeypatch.setattr(
        runtime_doctor_support,
        "build_runtime_version_sync_payload",
        lambda **kwargs: {"ok": False, "reason": "install_drift"},
    )

    payload = runtime_doctor_support.build_runtime_doctor_payload(
        root="F:/repo",
        config_file=".ace-lite.yml",
        skills_dir="skills",
        python_executable="python",
        timeout_seconds=1.0,
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        require_memory=False,
        probe_endpoints=False,
        current_path="current.json",
        last_known_good_path="last-good.json",
        stats_db_path="runtime-state.db",
        user_id="",
        cache_db_path="cache.db",
        payload_root="payload-root",
        temp_root="temp-root",
    )

    assert payload["ok"] is False
    assert payload["degraded_reason_codes"] == [
        "stage_artifact_cache_corrupt",
        "git_unavailable",
        "install_drift",
    ]


def test_persist_runtime_doctor_invocation_records_degraded_event(tmp_path: Path) -> None:
    stats_db_path = tmp_path / "runtime-stats.db"

    payload = runtime_doctor_support.persist_runtime_doctor_invocation(
        root=str(tmp_path),
        payload={
            "degraded_reason_codes": ["git_unavailable", "install_drift"],
            "settings": {"fingerprint": "fp-doctor"},
        },
        stats_db_path=str(stats_db_path),
        profile_key="bugfix",
    )

    assert payload["recorded"] is True
    assert payload["event_class"] == RUNTIME_STATS_DOCTOR_EVENT_CLASS
    stored = DurableStatsStore(db_path=stats_db_path).read_invocation(
        invocation_id=payload["invocation_id"]
    )
    assert stored is not None
    assert stored.status == "degraded"
    assert stored.profile_key == "bugfix"
    assert stored.event_class == RUNTIME_STATS_DOCTOR_EVENT_CLASS
    assert stored.settings_fingerprint == "fp-doctor"
    assert stored.degraded_reason_codes == ("git_unavailable", "install_drift")


def test_persist_runtime_doctor_invocation_skips_when_payload_has_no_reasons(
    tmp_path: Path,
) -> None:
    payload = runtime_doctor_support.persist_runtime_doctor_invocation(
        root=str(tmp_path),
        payload={"degraded_reason_codes": []},
        stats_db_path=str(tmp_path / "runtime-stats.db"),
        profile_key="",
    )

    assert payload["recorded"] is False
    assert payload["reason"] == "no_degraded_reasons"
