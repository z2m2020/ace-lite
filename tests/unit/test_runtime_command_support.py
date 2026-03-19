from __future__ import annotations

import subprocess
from pathlib import Path

from ace_lite.cli_app.runtime_command_support import (
    RUNTIME_COMMAND_DOMAIN_REGISTRY,
    build_codex_mcp_setup_plan,
    build_runtime_status_snapshot,
    collect_runtime_settings_show_payload,
    collect_runtime_status_payload,
    execute_codex_mcp_setup_plan,
    iter_runtime_command_domains,
    load_runtime_dev_feedback_summary,
    load_runtime_preference_capture_summary,
    load_runtime_stats_summary,
    resolve_runtime_settings_bundle,
    resolve_effective_runtime_skills_dir,
)
from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.runtime_settings_store import (
    build_runtime_settings_record,
    persist_runtime_settings_record,
)


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
                {"stage_name": "total", "elapsed_ms": 80.0},
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
    assert payload["fix_count"] == 1
    assert payload["repo_key"] == "repo-alpha"
    assert payload["user_id"] == "bench-user"
    assert payload["profile_key"] == "bugfix"
    assert payload["by_reason_code"][0]["reason_code"] == "memory_fallback"


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
    assert payload["fix_count"] == 0
    assert payload["by_reason_code"][0]["reason_code"] == "memory_fallback"


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
    assert payload["top_pain_summary"]["items"][0]["runtime_event_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["manual_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["open_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["fix_count"] == 1


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


def test_runtime_command_domain_registry_covers_phase1_domains() -> None:
    domains = {descriptor.name: descriptor.handlers for descriptor in iter_runtime_command_domains()}

    assert domains == {
        "settings": (
            "resolve_runtime_settings_bundle",
            "build_runtime_settings_payload",
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

