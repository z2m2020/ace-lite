from __future__ import annotations

import json
import subprocess
from pathlib import Path

import click
import pytest

import ace_lite.cli_app.runtime_command_support as runtime_command_support_module
from ace_lite.cli_app.runtime_command_support import (
    RUNTIME_COMMAND_DOMAIN_REGISTRY,
    build_codex_mcp_setup_plan,
    build_runtime_settings_governance_payload,
    build_runtime_status_payload,
    build_runtime_status_snapshot,
    collect_runtime_mcp_self_test_payload,
    collect_runtime_settings_persist_payload,
    collect_runtime_settings_show_payload,
    collect_runtime_status_payload,
    execute_codex_mcp_setup_plan,
    iter_runtime_command_domains,
    load_runtime_dev_feedback_summary,
    load_runtime_preference_capture_summary,
    load_runtime_stats_summary,
    resolve_effective_runtime_skills_dir,
    resolve_runtime_settings_bundle,
)
from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.runtime_settings_store import (
    build_runtime_settings_record,
    load_runtime_settings_record,
    persist_runtime_settings_record,
)
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_store import DurableStatsStore


def _seed_runtime_stats_with_degraded_reason(db_path: Path) -> None:
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-alpha",
            session_id="session-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=80.0,
            started_at="2026-03-19T00:00:00+00:00",
            finished_at="2026-03-19T00:00:01+00:00",
            degraded_reason_codes=("memory_fallback",),
            stage_latencies=(
                {"stage_name": "memory", "elapsed_ms": 20.0},
                {"stage_name": "agent_loop", "elapsed_ms": 12.0},
                {"stage_name": "total", "elapsed_ms": 80.0},
            ),
        )
    )


def _seed_runtime_stats_with_alias_reason(db_path: Path) -> None:
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-alias",
            session_id="session-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=40.0,
            started_at="2026-03-19T00:10:00+00:00",
            finished_at="2026-03-19T00:10:01+00:00",
            degraded_reason_codes=("budget_exceeded",),
            stage_latencies=(
                {"stage_name": "memory", "elapsed_ms": 10.0},
                {"stage_name": "total", "elapsed_ms": 40.0},
            ),
        )
    )


def test_resolve_runtime_settings_bundle_uses_last_known_good_selected_profile(
    tmp_path: Path,
) -> None:
    current_path = tmp_path / "current-settings.json"
    lkg_path = tmp_path / "last-known-good.json"
    valid_payload = build_runtime_settings_record(
        snapshot={"plan": {"retrieval": {"top_k_files": 12}}},
        provenance={"plan": {"retrieval": {"top_k_files": "cli"}}},
        metadata={"selected_profile": "team-default"},
    )
    persist_runtime_settings_record(
        current_path=current_path,
        last_known_good_path=lkg_path,
        payload=valid_payload,
        update_last_known_good=True,
    )
    current_path.write_text('{"schema_version": 1, "snapshot": {"broken": true}}', encoding="utf-8")

    bundle = resolve_runtime_settings_bundle(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(current_path),
        last_known_good_path=str(lkg_path),
    )

    assert bundle["persisted_source"] == "last_known_good"
    assert bundle["selected_profile"] == "team-default"
    assert str(bundle["resolved_current_path"]) == str(current_path)
    assert str(bundle["resolved_lkg_path"]) == str(lkg_path)
    assert bundle["governance"]["governance_state"] == "fallback_to_last_known_good"
    assert bundle["governance"]["current_record"]["status"] == "invalid"
    assert bundle["governance"]["last_known_good_record"]["status"] == "valid"
    assert bundle["governance"]["persist_recommended"] is True


def test_collect_runtime_mcp_self_test_payload_merges_health_warnings() -> None:
    payload = collect_runtime_mcp_self_test_payload(
        root="repo",
        skills_dir="skills",
        python_executable="python",
        timeout_seconds=5.0,
        mcp_name="ace-lite",
        use_snapshot=False,
        require_memory=False,
        extract_memory_channels_fn=lambda payload: (
            payload.get("memory_primary", "none"),
            payload.get("memory_secondary", "none"),
        ),
        memory_channels_disabled_fn=lambda primary, secondary: primary == "none"
        and secondary == "none",
        memory_config_recommendations_fn=lambda root, skills_dir: ["configure-memory"],
        run_mcp_self_test_fn=lambda **kwargs: {
            "ok": True,
            "memory_primary": "rest",
            "memory_secondary": "none",
            "warnings": ["Runtime code appears stale"],
            "recommendations": ["Restart the stdio MCP server/session after git pull or pip install -e updates."],
            "runtime_identity": {"stale_process_suspected": True},
            "stdio_session_health": {
                "scope": "self_test_probe",
                "transport": "stdio(default)",
                "status": "warning",
                "reason_codes": ["stale_process"],
                "restart_recommended": True,
                "active_request_count": 0,
                "current_request_runtime_ms": 0.0,
                "message": "Current MCP process appears stale and should be restarted.",
            },
        },
        snapshot_path_fn=lambda **kwargs: Path("snapshot.json"),
        load_snapshot_fn=lambda **kwargs: ({}, Path("snapshot.json")),
    )

    assert payload["ok"] is True
    assert "Runtime code appears stale" in payload["warnings"]
    assert any("Restart the stdio MCP server/session" in item for item in payload["recommendations"])
    assert payload["session_summary"]["status"] == "warning"
    assert payload["session_summary"]["scope"] == "self_test_probe"
    assert payload["session_summary"]["message"]


def test_collect_runtime_mcp_doctor_payload_merges_self_test_warnings(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_command_support_module,
        "run_mcp_self_test",
        lambda **kwargs: {
            "ok": True,
            "memory_primary": "rest",
            "memory_secondary": "none",
            "warnings": ["Runtime code appears stale"],
            "recommendations": ["Restart the stdio MCP server/session after git pull or pip install -e updates."],
            "runtime_identity": {"stale_process_suspected": True},
            "stdio_session_health": {
                "scope": "self_test_probe",
                "transport": "stdio(default)",
                "status": "warning",
                "reason_codes": ["stale_process"],
                "restart_recommended": True,
                "active_request_count": 0,
                "current_request_runtime_ms": 0.0,
                "message": "Current MCP process appears stale and should be restarted.",
            },
        },
    )

    payload = runtime_command_support_module.collect_runtime_mcp_doctor_payload(
        root="repo",
        skills_dir="skills",
        python_executable="python",
        timeout_seconds=5.0,
        mcp_name="ace-lite",
        use_snapshot=False,
        require_memory=False,
        probe_endpoints=False,
    )

    assert payload["ok"] is True
    assert payload["self_test"]["runtime_identity"]["stale_process_suspected"] is True
    assert payload["checks"][1]["name"] == "session_health"
    assert payload["checks"][1]["ok"] is False
    assert payload["session_summary"]["status"] == "warning"
    assert "Runtime code appears stale" in payload["warnings"]
    assert any("Restart the stdio MCP server/session" in item for item in payload["recommendations"])


def test_collect_runtime_settings_show_payload_matches_bundle_snapshot(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )

    bundle = resolve_runtime_settings_bundle(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(tmp_path / "current.json"),
        last_known_good_path=str(tmp_path / "lkg.json"),
    )
    payload = collect_runtime_settings_show_payload(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(tmp_path / "current.json"),
        last_known_good_path=str(tmp_path / "lkg.json"),
    )

    resolved = bundle["resolved"]
    assert payload["ok"] is True
    assert payload["event"] == "runtime_settings_show"
    assert payload["settings"] == resolved.snapshot
    assert payload["provenance"] == resolved.provenance
    assert payload["fingerprint"] == resolved.fingerprint
    assert payload["selected_profile"] == bundle["selected_profile"]
    assert payload["persisted_source"] == bundle["persisted_source"]
    assert payload["stats_tags"] == resolved.metadata.get("stats_tags", {})
    assert payload["metadata"] == resolved.metadata
    assert payload["governance"] == bundle["governance"]


def test_build_runtime_settings_governance_payload_reports_current_and_lkg_state(
    tmp_path: Path,
) -> None:
    current_path = tmp_path / "current-settings.json"
    lkg_path = tmp_path / "last-known-good.json"
    valid_payload = build_runtime_settings_record(
        snapshot={"plan": {"retrieval": {"top_k_files": 12}}},
        provenance={"plan": {"retrieval": {"top_k_files": "cli"}}},
        metadata={"selected_profile": "team-default"},
    )
    persist_runtime_settings_record(
        current_path=current_path,
        last_known_good_path=lkg_path,
        payload=valid_payload,
        update_last_known_good=True,
    )
    current_path.write_text(
        '{"schema_version": 1, "snapshot": {"broken": true}}',
        encoding="utf-8",
    )

    bundle = resolve_runtime_settings_bundle(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(current_path),
        last_known_good_path=str(lkg_path),
    )
    governance = build_runtime_settings_governance_payload(bundle)

    assert governance["persisted_source"] == "last_known_good"
    assert governance["current_record_valid"] is False
    assert governance["last_known_good_record_valid"] is True
    assert governance["resolved_matches_current"] is False
    assert governance["persisted_selected_profile"] == "team-default"


def test_collect_runtime_settings_persist_payload_writes_current_and_lkg(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  retrieval:\n    top_k_files: 9\n",
        encoding="utf-8",
    )
    current_path = tmp_path / "current-settings.json"
    lkg_path = tmp_path / "last-known-good.json"

    payload = collect_runtime_settings_persist_payload(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(current_path),
        last_known_good_path=str(lkg_path),
        update_last_known_good=True,
    )
    current_record = load_runtime_settings_record(current_path)
    lkg_record = load_runtime_settings_record(lkg_path)

    assert payload["ok"] is True
    assert payload["event"] == "runtime_settings_persist"
    assert payload["persisted_path"] == str(current_path)
    assert payload["last_known_good_updated"] is True
    assert payload["governance"]["persisted_source"] == "current"
    assert payload["governance"]["resolved_matches_current"] is True
    assert payload["governance"]["resolved_matches_last_known_good"] is True
    assert current_record is not None
    assert lkg_record is not None
    assert current_record["fingerprint"] == payload["fingerprint"]
    assert lkg_record["fingerprint"] == payload["fingerprint"]
    assert json.loads(current_path.read_text(encoding="utf-8"))["fingerprint"] == payload["fingerprint"]


def test_resolve_effective_runtime_skills_dir_prefers_explicit_override() -> None:
    settings = {"plan": {"skills": {"dir": "repo-skills"}}}

    assert (
        resolve_effective_runtime_skills_dir(settings, skills_dir="cli-skills")
        == "cli-skills"
    )
    assert resolve_effective_runtime_skills_dir(settings) == "repo-skills"
    assert resolve_effective_runtime_skills_dir({}) == "skills"


def test_build_runtime_status_snapshot_matches_collect_payload(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  retrieval:\n"
            "    top_k_files: 7\n"
        ),
        encoding="utf-8",
    )

    bundle = resolve_runtime_settings_bundle(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(tmp_path / "current.json"),
        last_known_good_path=str(tmp_path / "lkg.json"),
    )
    expected_snapshot = build_runtime_status_snapshot(
        root=str(tmp_path),
        bundle=bundle,
        db_path=str(tmp_path / "runtime-state.db"),
        extract_memory_channels_fn=lambda payload: (
            payload.get("memory_primary", "none"),
            payload.get("memory_secondary", "none"),
        ),
        memory_channels_disabled_fn=lambda primary, secondary: primary == "none"
        and secondary == "none",
        memory_config_recommendations_fn=lambda root, skills_dir: [
            f"configure-memory:{Path(root).name}:{Path(skills_dir).name}"
        ],
    )
    payload = collect_runtime_status_payload(
        root=str(tmp_path),
        config_file=".ace-lite.yml",
        mcp_name="ace-lite",
        runtime_profile=None,
        use_snapshot=False,
        current_path=str(tmp_path / "current.json"),
        last_known_good_path=str(tmp_path / "lkg.json"),
        db_path=str(tmp_path / "runtime-state.db"),
        extract_memory_channels_fn=lambda payload: (
            payload.get("memory_primary", "none"),
            payload.get("memory_secondary", "none"),
        ),
        memory_channels_disabled_fn=lambda primary, secondary: primary == "none"
        and secondary == "none",
        memory_config_recommendations_fn=lambda root, skills_dir: [
            f"configure-memory:{Path(root).name}:{Path(skills_dir).name}"
        ],
    )

    assert payload["ok"] is True
    assert payload["event"] == "runtime_status"
    assert {key: value for key, value in payload.items() if key not in {"ok", "event"}} == (
        expected_snapshot
    )
    assert payload["settings_governance"] == bundle["governance"]
    assert payload["settings_governance"]["resolved_fingerprint"] == bundle["resolved"].fingerprint


def test_load_runtime_preference_capture_summary_reads_durable_feedback_store(
    tmp_path: Path,
) -> None:
    feedback_path = tmp_path / "profile.json"
    SelectionFeedbackStore(profile_path=feedback_path, max_entries=8).record(
        query="runtime summary",
        repo="repo-alpha",
        profile_key="bugfix",
        selected_path="src/app.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )

    payload = load_runtime_preference_capture_summary(
        feedback_path=feedback_path,
        repo_key="repo-alpha",
        profile_key="bugfix",
    )

    assert payload["event_count"] == 1
    assert payload["distinct_target_path_count"] == 1
    assert payload["store_path"].endswith("preference_capture.db")
    assert payload["profile_key"] == "bugfix"


def test_load_runtime_preference_capture_summary_applies_user_id_filter(
    tmp_path: Path,
) -> None:
    feedback_path = tmp_path / "profile.json"
    store = SelectionFeedbackStore(profile_path=feedback_path, max_entries=8)
    store.record(
        query="runtime summary bench",
        repo="repo-alpha",
        user_id="bench-user",
        selected_path="src/app.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="runtime summary other",
        repo="repo-alpha",
        user_id="other-user",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )

    payload = load_runtime_preference_capture_summary(
        feedback_path=feedback_path,
        repo_key="repo-alpha",
        user_id="bench-user",
    )

    assert payload["event_count"] == 1
    assert payload["distinct_target_path_count"] == 1
    assert payload["user_id"] == "bench-user"


def test_load_runtime_dev_feedback_summary_applies_repo_user_and_profile_filters(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / ".ace-lite" / "dev_feedback.db"
    store = DevFeedbackStore(db_path=store_path)
    store.record_issue(
        {
            "title": "augment fallback",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:01:00+00:00",
        }
    )
    store.record_fix(
        {
            "issue_id": "devi_known",
            "reason_code": "memory_fallback",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "resolution_note": "added cache warming",
            "created_at": "2026-03-19T00:02:00+00:00",
        }
    )
    store.record_issue(
        {
            "title": "other profile issue",
            "reason_code": "trace_export_failed",
            "status": "open",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "docs",
            "created_at": "2026-03-19T00:03:00+00:00",
            "updated_at": "2026-03-19T00:04:00+00:00",
        }
    )

    payload = load_runtime_dev_feedback_summary(
        dev_feedback_path=store_path,
        repo_key="repo-alpha",
        user_id="bench-user",
        profile_key="bugfix",
    )

    assert payload["issue_count"] == 1
    assert payload["open_issue_count"] == 1
    assert payload["resolved_issue_count"] == 0
    assert payload["fix_count"] == 1
    assert payload["linked_fix_issue_count"] == 1
    assert payload["dev_issue_to_fix_rate"] == 1.0
    assert payload["issue_time_to_fix_case_count"] == 0
    assert payload["issue_time_to_fix_hours_mean"] == 0.0
    assert payload["repo_key"] == "repo-alpha"
    assert payload["user_id"] == "bench-user"
    assert payload["profile_key"] == "bugfix"
    assert payload["by_reason_code"][0]["reason_code"] == "memory_fallback"
    assert payload["by_reason_code"][0]["reason_family"] == "memory"
    assert payload["by_reason_code"][0]["capture_class"] == "fallback"
    assert payload["by_reason_code"][0]["dev_issue_to_fix_rate"] == 1.0


def test_load_runtime_dev_feedback_summary_applies_scope_filters(tmp_path: Path) -> None:
    store = DevFeedbackStore(db_path=tmp_path / ".ace-lite" / "dev_feedback.db")
    store.record_issue(
        {
            "issue_id": "devi_a",
            "title": "Memory fallback",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    store.record_issue(
        {
            "issue_id": "devi_b",
            "title": "Docs drift",
            "reason_code": "docs_drift",
            "status": "open",
            "repo": "repo-alpha",
            "user_id": "other-user",
            "profile_key": "docs",
            "created_at": "2026-03-19T00:01:00+00:00",
            "updated_at": "2026-03-19T00:01:00+00:00",
        }
    )

    payload = load_runtime_dev_feedback_summary(
        dev_feedback_path=store.db_path,
        repo_key="repo-alpha",
        user_id="bench-user",
        profile_key="bugfix",
    )

    assert payload["repo_key"] == "repo-alpha"
    assert payload["user_id"] == "bench-user"
    assert payload["profile_key"] == "bugfix"
    assert payload["issue_count"] == 1
    assert payload["open_issue_count"] == 1
    assert payload["resolved_issue_count"] == 0
    assert payload["fix_count"] == 0
    assert payload["linked_fix_issue_count"] == 0
    assert payload["dev_issue_to_fix_rate"] == 0.0
    assert payload["by_reason_code"][0]["reason_code"] == "memory_fallback"
    assert payload["by_reason_code"][0]["reason_family"] == "memory"


def test_load_runtime_stats_summary_includes_dev_feedback_and_top_pain_summary(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_with_degraded_reason(db_path)
    dev_feedback_store = DevFeedbackStore(db_path=tmp_path / ".ace-lite" / "dev_feedback.db")
    dev_feedback_store.record_issue(
        {
            "issue_id": "devi_memory_fallback",
            "title": "Memory fallback",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    dev_feedback_store.record_fix(
        {
            "fix_id": "devf_memory_fallback",
            "issue_id": "devi_memory_fallback",
            "reason_code": "memory_fallback",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "resolution_note": "added fallback diagnostics",
            "created_at": "2026-03-19T00:05:00+00:00",
        }
    )

    payload = load_runtime_stats_summary(
        db_path=db_path,
        repo_key="repo-alpha",
        user_id="bench-user",
        profile_key="bugfix",
        home_path=tmp_path,
    )

    assert payload["dev_feedback_summary"]["issue_count"] == 1
    assert payload["dev_feedback_summary"]["fix_count"] == 1
    assert payload["top_pain_summary"]["count"] == 1
    assert payload["top_pain_summary"]["items"][0]["reason_code"] == "memory_fallback"
    assert payload["top_pain_summary"]["items"][0]["reason_family"] == "memory"
    assert payload["top_pain_summary"]["items"][0]["capture_class"] == "fallback"
    assert payload["top_pain_summary"]["items"][0]["runtime_event_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["manual_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["open_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["resolved_issue_count"] == 0
    assert payload["top_pain_summary"]["items"][0]["fix_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["linked_fix_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["dev_issue_to_fix_rate"] == 1.0
    assert payload["top_pain_summary"]["items"][0]["issue_time_to_fix_case_count"] == 0
    assert payload["top_pain_summary"]["items"][0]["issue_time_to_fix_hours_mean"] == 0.0
    assert payload["memory_health_summary"]["scope_kind"] == "repo_profile"
    assert payload["memory_health_summary"]["reason_count"] == 1
    assert payload["memory_health_summary"]["runtime_event_count"] == 1
    assert payload["memory_health_summary"]["issue_count"] == 1
    assert payload["memory_health_summary"]["open_issue_count"] == 1
    assert payload["memory_health_summary"]["resolved_issue_count"] == 0
    assert payload["memory_health_summary"]["fix_count"] == 1
    assert payload["memory_health_summary"]["linked_fix_issue_count"] == 1
    assert payload["memory_health_summary"]["resolution_rate"] == 1.0
    assert payload["memory_health_summary"]["dev_issue_to_fix_rate"] == 1.0
    assert payload["memory_health_summary"]["open_issue_rate"] == 1.0
    assert payload["memory_health_summary"]["issue_time_to_fix_case_count"] == 0
    assert payload["memory_health_summary"]["issue_time_to_fix_hours_mean"] == 0.0
    assert payload["memory_health_summary"]["memory_stage_latency_ms_avg"] == 20.0
    assert payload["memory_health_summary"]["reasons"][0]["reason_code"] == "memory_fallback"
    assert payload["memory_health_summary"]["reasons"][0]["reason_family"] == "memory"
    assert payload["memory_health_summary"]["reasons"][0]["linked_fix_issue_count"] == 1


def test_load_runtime_stats_summary_excludes_synthetic_doctor_sessions_from_scope_summaries(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_with_degraded_reason(db_path)
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-doctor",
            session_id="runtime-doctor::repo-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=0.0,
            started_at="2026-03-19T00:10:00+00:00",
            finished_at="2026-03-19T00:10:00+00:00",
            degraded_reason_codes=("git_unavailable",),
        )
    )

    payload = load_runtime_stats_summary(
        db_path=db_path,
        repo_key="repo-alpha",
        profile_key="bugfix",
        home_path=tmp_path,
    )

    assert payload["latest_match"]["session_id"] == "session-alpha"
    assert payload["summary"]["all_time"]["counters"]["invocation_count"] == 1
    assert payload["summary"]["repo"]["counters"]["invocation_count"] == 1
    assert payload["summary"]["profile"]["counters"]["invocation_count"] == 1
    assert payload["summary"]["repo_profile"]["counters"]["invocation_count"] == 1
    assert payload["top_pain_summary"]["count"] == 1
    assert payload["top_pain_summary"]["items"][0]["reason_code"] == "memory_fallback"
    assert payload["memory_health_summary"]["reason_count"] == 1


def test_load_runtime_stats_summary_canonicalizes_runtime_reason_aliases_in_top_pain_summary(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_with_alias_reason(db_path)

    payload = load_runtime_stats_summary(
        db_path=db_path,
        repo_key="repo-alpha",
        profile_key="bugfix",
        home_path=tmp_path,
    )

    assert payload["top_pain_summary"]["count"] == 1
    assert payload["top_pain_summary"]["items"][0]["reason_code"] == (
        "latency_budget_exceeded"
    )
    assert payload["top_pain_summary"]["items"][0]["reason_family"] == "runtime"
    assert payload["top_pain_summary"]["items"][0]["capture_class"] == "budget"
    assert payload["top_pain_summary"]["items"][0]["runtime_event_count"] == 1
    assert payload["next_cycle_input_summary"]["primary_stream"] == "budget"
    assert payload["next_cycle_input_summary"]["priorities"][0]["reason_code"] == (
        "latency_budget_exceeded"
    )
    assert payload["next_cycle_input_summary"]["priorities"][0]["action_hint"]


def test_load_runtime_stats_summary_exposes_agent_loop_control_plane_readiness(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_with_degraded_reason(db_path)

    payload = load_runtime_stats_summary(
        db_path=db_path,
        repo_key="repo-alpha",
        profile_key="bugfix",
        home_path=tmp_path,
    )

    summary = payload["agent_loop_control_plane_summary"]
    assert summary["scope_kind"] == "repo_profile"
    assert summary["source_plan_retry_supported"] is True
    assert summary["rerun_policy_supported"] is True
    assert summary["observed_stage"] is True
    assert summary["agent_loop_stage_latency_ms_avg"] == 12.0
    assert summary["preferred_execution_scope"] == "post_source_runtime"
    assert summary["source_plan_retry_rerun_stages"] == ["source_plan", "validation"]


def test_build_runtime_status_payload_canonicalizes_runtime_reason_aliases_in_degraded_services(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_with_alias_reason(db_path)
    runtime_stats = load_runtime_stats_summary(
        db_path=db_path,
        repo_key="repo-alpha",
        profile_key="bugfix",
        home_path=tmp_path,
    )

    payload = build_runtime_status_payload(
        root=str(tmp_path),
        settings={},
        fingerprint="fingerprint",
        selected_profile="bugfix",
        stats_tags={},
        snapshot_loaded=False,
        snapshot_path="",
        memory_state={
            "memory_disabled": True,
            "primary": "none",
            "secondary": "none",
            "warnings": [],
            "recommendations": [],
        },
        runtime_stats=runtime_stats,
    )

    assert any(
        item["name"] == "runtime"
        and item["reason"] == "latency_budget_exceeded"
        and item.get("capture_class") == "budget"
        and item["source"] == "latest_runtime_stats"
        for item in payload["degraded_services"]
    )
    assert payload["next_cycle_input"]["primary_stream"] == "budget"
    assert payload["latest_runtime"]["next_cycle_input_summary"]["priorities"][0][
        "reason_code"
    ] == "latency_budget_exceeded"
    assert payload["latest_runtime"]["agent_loop_control_plane_summary"] == runtime_stats[
        "agent_loop_control_plane_summary"
    ]


def test_execute_codex_mcp_setup_plan_dry_run_does_not_run_commands() -> None:
    setup_plan = build_codex_mcp_setup_plan(
        name="ace-lite",
        root="repo",
        skills_dir="skills",
        codex_executable="codex",
        python_executable="python",
        enable_memory=False,
        memory_primary="rest",
        memory_secondary="none",
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        user_id="",
        app="ace-lite",
        config_pack="",
        enable_embeddings=False,
        embedding_provider="ollama",
        embedding_model="model",
        embedding_dimension=2560,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_rerank_pool=16,
        embedding_lexical_weight=0.55,
        embedding_semantic_weight=0.45,
        embedding_min_similarity=0.05,
        embedding_fail_open=True,
        ollama_base_url="http://localhost:11434",
        replace=True,
        apply=False,
        verify=True,
        resolve_cli_path_fn=lambda value: str(value),
        env_get_fn=lambda key, default="": default,
    )
    calls: list[list[str]] = []

    result = execute_codex_mcp_setup_plan(
        setup_plan=setup_plan,
        python_executable="python",
        run_subprocess_fn=lambda *args, **kwargs: calls.append(list(args[0])),
        write_snapshot_fn=lambda **kwargs: Path("snapshot.json"),
        run_mcp_self_test_fn=lambda **kwargs: {"ok": True},
    )

    assert result["event"] == "setup_codex_mcp"
    assert "commands" in result
    assert calls == []


def test_execute_codex_mcp_setup_plan_apply_and_verify(tmp_path: Path) -> None:
    setup_plan = build_codex_mcp_setup_plan(
        name="ace-lite",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        codex_executable="codex",
        python_executable="python",
        enable_memory=True,
        memory_primary="rest",
        memory_secondary="none",
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        user_id="snapshot-user",
        app="ace-lite",
        config_pack="",
        enable_embeddings=False,
        embedding_provider="ollama",
        embedding_model="model",
        embedding_dimension=2560,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_rerank_pool=16,
        embedding_lexical_weight=0.55,
        embedding_semantic_weight=0.45,
        embedding_min_similarity=0.05,
        embedding_fail_open=True,
        ollama_base_url="http://localhost:11434",
        replace=True,
        apply=True,
        verify=True,
        resolve_cli_path_fn=lambda value: str(Path(value)),
        env_get_fn=lambda key, default="": default,
    )
    commands: list[list[str]] = []

    def _fake_run(command, capture_output, text, check=False, env=None, timeout=None):
        _ = (capture_output, text, check, env, timeout)
        commands.append(list(command))
        if command[:3] == ["codex", "mcp", "get"]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="ace-lite\n  enabled: true\n",
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

    result = execute_codex_mcp_setup_plan(
        setup_plan=setup_plan,
        python_executable="python",
        run_subprocess_fn=_fake_run,
        write_snapshot_fn=lambda **kwargs: tmp_path / "snapshot.json",
        run_mcp_self_test_fn=lambda **kwargs: {
            "ok": True,
            "memory_primary": "rest",
            "memory_secondary": "none",
        },
    )

    assert result["event"] == "setup_codex_mcp"
    assert Path(result["snapshot_path"]) == (tmp_path / "snapshot.json")
    assert result["verify_get"]["ok"] is True
    assert result["verify_self_test"]["ok"] is True
    assert commands[0][:3] == ["codex", "mcp", "remove"]
    assert commands[1][:3] == ["codex", "mcp", "add"]
    assert commands[2][:3] == ["codex", "mcp", "get"]


def test_build_codex_mcp_setup_plan_rejects_empty_codex_executable() -> None:
    with pytest.raises(click.ClickException) as exc_info:
        build_codex_mcp_setup_plan(
            name="ace-lite",
            root="repo",
            skills_dir="skills",
            codex_executable="",
            python_executable="python",
            enable_memory=False,
            memory_primary="rest",
            memory_secondary="none",
            mcp_base_url="http://localhost:8765",
            rest_base_url="http://localhost:8765",
            user_id="",
            app="ace-lite",
            config_pack="",
            enable_embeddings=False,
            embedding_provider="ollama",
            embedding_model="model",
            embedding_dimension=2560,
            embedding_index_path="context-map/embeddings/index.json",
            embedding_rerank_pool=16,
            embedding_lexical_weight=0.55,
            embedding_semantic_weight=0.45,
            embedding_min_similarity=0.05,
            embedding_fail_open=True,
            ollama_base_url="http://localhost:11434",
            replace=True,
            apply=False,
            verify=True,
            resolve_cli_path_fn=lambda value: str(value),
            env_get_fn=lambda key, default="": default,
        )
    assert "normalize_inputs" in str(exc_info.value)
    assert "codex_executable must not be empty" in str(exc_info.value)


def test_build_codex_mcp_setup_plan_rejects_empty_python_executable() -> None:
    with pytest.raises(click.ClickException) as exc_info:
        build_codex_mcp_setup_plan(
            name="ace-lite",
            root="repo",
            skills_dir="skills",
            codex_executable="codex",
            python_executable="",
            enable_memory=False,
            memory_primary="rest",
            memory_secondary="none",
            mcp_base_url="http://localhost:8765",
            rest_base_url="http://localhost:8765",
            user_id="",
            app="ace-lite",
            config_pack="",
            enable_embeddings=False,
            embedding_provider="ollama",
            embedding_model="model",
            embedding_dimension=2560,
            embedding_index_path="context-map/embeddings/index.json",
            embedding_rerank_pool=16,
            embedding_lexical_weight=0.55,
            embedding_semantic_weight=0.45,
            embedding_min_similarity=0.05,
            embedding_fail_open=True,
            ollama_base_url="http://localhost:11434",
            replace=True,
            apply=False,
            verify=True,
            resolve_cli_path_fn=lambda value: str(value),
            env_get_fn=lambda key, default="": default,
        )
    assert "normalize_inputs" in str(exc_info.value)
    assert "python_executable must not be empty" in str(exc_info.value)


def test_execute_codex_mcp_setup_plan_formats_add_failure_message(tmp_path: Path) -> None:
    setup_plan = build_codex_mcp_setup_plan(
        name="ace-lite",
        root=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        codex_executable="codex",
        python_executable="python",
        enable_memory=False,
        memory_primary="rest",
        memory_secondary="none",
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        user_id="snapshot-user",
        app="ace-lite",
        config_pack="",
        enable_embeddings=False,
        embedding_provider="ollama",
        embedding_model="model",
        embedding_dimension=2560,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_rerank_pool=16,
        embedding_lexical_weight=0.55,
        embedding_semantic_weight=0.45,
        embedding_min_similarity=0.05,
        embedding_fail_open=True,
        ollama_base_url="http://localhost:11434",
        replace=False,
        apply=True,
        verify=False,
        resolve_cli_path_fn=lambda value: str(Path(value)),
        env_get_fn=lambda key, default="": default,
    )

    def _fail_run(command, capture_output, text, check=False, env=None, timeout=None):
        _ = (capture_output, text, check, env, timeout)
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="codex add failed",
        )

    with pytest.raises(click.ClickException) as exc_info:
        execute_codex_mcp_setup_plan(
            setup_plan=setup_plan,
            python_executable="python",
            run_subprocess_fn=_fail_run,
            write_snapshot_fn=lambda **kwargs: tmp_path / "snapshot.json",
            run_mcp_self_test_fn=lambda **kwargs: {"ok": True},
        )

    assert "Runtime setup failed during add_mcp_server" in str(exc_info.value)
    assert "codex add failed" in str(exc_info.value)


def test_runtime_command_domain_registry_covers_phase1_domains() -> None:
    domains = {descriptor.name: descriptor.handlers for descriptor in iter_runtime_command_domains()}

    assert domains == {
        "settings": (
            "resolve_runtime_settings_bundle",
            "build_runtime_settings_governance_payload",
            "build_runtime_settings_payload",
            "collect_runtime_settings_persist_payload",
            "collect_runtime_settings_show_payload",
        ),
        "doctor": (
            "collect_runtime_mcp_doctor_payload",
            "collect_runtime_mcp_self_test_payload",
            "build_runtime_cache_doctor_payload",
            "build_runtime_cache_vacuum_payload",
            "build_runtime_git_doctor_payload",
            "build_runtime_version_sync_payload",
            "build_runtime_doctor_payload",
        ),
        "status": (
            "collect_runtime_status_payload",
            "build_runtime_status_snapshot",
            "build_runtime_status_payload",
            "load_runtime_stats_summary",
            "load_latest_runtime_stats_match",
        ),
        "setup": (
            "build_codex_mcp_setup_plan",
            "execute_codex_mcp_setup_plan",
        ),
    }
    assert set(RUNTIME_COMMAND_DOMAIN_REGISTRY) == set(domains)

