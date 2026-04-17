from __future__ import annotations

from pathlib import Path

import yaml

from ace_lite.runtime_settings import RuntimeSettingsManager
from ace_lite.runtime_settings_store import (
    DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH,
    DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH,
    build_runtime_settings_record,
    inspect_runtime_settings_record,
    load_runtime_settings_record,
    load_runtime_settings_with_fallback,
    persist_runtime_settings_record,
    resolve_user_runtime_settings_last_known_good_path,
    resolve_user_runtime_settings_path,
    runtime_settings_paths_collide,
    write_runtime_settings_record,
)


def test_runtime_settings_manager_resolves_plan_sources(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "home"
    repo_root = tmp_path / "repo"
    cwd_dir = repo_root / "workspace"

    fake_home.mkdir(parents=True, exist_ok=True)
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    (fake_home / ".ace-lite.yml").write_text(
        yaml.safe_dump({"plan": {"top_k_files": 1, "plugins_enabled": False}}, sort_keys=False),
        encoding="utf-8",
    )
    (repo_root / ".ace-lite.yml").write_text(
        yaml.safe_dump(
            {"plan": {"retrieval": {"top_k_files": 2}, "plugins_enabled": True}}, sort_keys=False
        ),
        encoding="utf-8",
    )
    (cwd_dir / ".ace-lite.yml").write_text(
        yaml.safe_dump(
            {"plan": {"retrieval": {"top_k_files": 3}, "chunk": {"top_k": 11}}}, sort_keys=False
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    manager = RuntimeSettingsManager()
    snapshot = manager.resolve(
        root=repo_root,
        cwd=cwd_dir,
        plan_cli_overrides={"top_k_files": 6},
        plan_retrieval_preset={"top_k_files": 4, "min_candidate_score": 7},
        plan_config_pack_overrides={"top_k_files": 5, "memory_profile_enabled": True},
    )

    assert snapshot.snapshot["plan"]["retrieval"]["top_k_files"] == 6
    assert snapshot.provenance["plan"]["retrieval"]["top_k_files"] == "cli"
    assert snapshot.snapshot["plan"]["retrieval"]["min_candidate_score"] == 7
    assert snapshot.provenance["plan"]["retrieval"]["min_candidate_score"] == "retrieval_preset"
    assert snapshot.snapshot["plan"]["memory"]["profile"]["enabled"] is True
    assert snapshot.provenance["plan"]["memory"]["profile"]["enabled"] == "config_pack"
    assert snapshot.snapshot["plan"]["chunking"]["top_k"] == 11
    assert snapshot.provenance["plan"]["chunking"]["top_k"] == "cwd_config"
    assert snapshot.snapshot["plan"]["plugins"]["enabled"] is True
    assert snapshot.provenance["plan"]["plugins"]["enabled"] == "repo_config"
    assert snapshot.snapshot["plan"]["trace"]["export_enabled"] is False
    assert snapshot.provenance["plan"]["trace"]["export_enabled"] == "default"
    assert snapshot.metadata["loaded_files"]
    assert snapshot.fingerprint


def test_runtime_settings_manager_resolves_runtime_and_mcp_sources(
    tmp_path: Path, monkeypatch
) -> None:
    fake_home = tmp_path / "home"
    repo_root = tmp_path / "repo"
    cwd_dir = repo_root / "workspace"

    fake_home.mkdir(parents=True, exist_ok=True)
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    (repo_root / ".ace-lite.yml").write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "scheduler": {
                        "enabled": True,
                        "heartbeat": {"enabled": True},
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (cwd_dir / ".ace-lite.yml").write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "scheduler": {
                        "heartbeat": {"interval_seconds": 15},
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    manager = RuntimeSettingsManager()
    snapshot = manager.resolve(
        root=repo_root,
        cwd=cwd_dir,
        mcp_snapshot_env={"ACE_LITE_MEMORY_PRIMARY": "rest"},
        mcp_env={"ACE_LITE_MEMORY_PRIMARY": "mcp", "USER": "fallback-user"},
        mcp_explicit_overrides={"default_root": str(repo_root)},
    )

    assert snapshot.snapshot["runtime"]["scheduler"]["enabled"] is True
    assert snapshot.provenance["runtime"]["scheduler"]["enabled"] == "repo_config"
    assert snapshot.snapshot["runtime"]["scheduler"]["heartbeat"]["interval_seconds"] == 15.0
    assert (
        snapshot.provenance["runtime"]["scheduler"]["heartbeat"]["interval_seconds"] == "cwd_config"
    )
    assert snapshot.snapshot["mcp"]["default_root"] == str(repo_root.resolve())
    assert snapshot.provenance["mcp"]["default_root"] == "explicit_override"
    assert snapshot.snapshot["mcp"]["memory_primary"] == "mcp"
    assert snapshot.provenance["mcp"]["memory_primary"] == "env"
    assert snapshot.snapshot["mcp"]["user_id"] == "fallback-user"
    assert snapshot.provenance["mcp"]["user_id"] == "identity_fallback"


def test_runtime_settings_manager_uses_git_root_name_for_default_repo(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_dir = repo_root / "tabiapp-backend_worktree_aeon_v2"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    worktree_dir.mkdir(parents=True, exist_ok=True)

    snapshot = RuntimeSettingsManager().resolve(
        root=worktree_dir,
        cwd=worktree_dir,
        mcp_explicit_overrides={"default_root": str(worktree_dir)},
    )

    assert snapshot.snapshot["mcp"]["default_repo"] == "tabiapp-backend"
    assert snapshot.provenance["mcp"]["default_repo"] == "git_root_name"


def test_runtime_settings_manager_uses_tuned_default_skills_token_budget(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    cwd_dir = repo_root / "workspace"
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    manager = RuntimeSettingsManager()
    snapshot = manager.resolve(root=repo_root, cwd=cwd_dir)

    assert snapshot.snapshot["plan"]["skills"]["token_budget"] == 1400
    assert snapshot.provenance["plan"]["skills"]["token_budget"] == "default"


def test_runtime_settings_manager_applies_runtime_profile_and_exposes_stats_tags(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_home = tmp_path / "home"
    repo_root = tmp_path / "repo"
    cwd_dir = repo_root / "workspace"

    fake_home.mkdir(parents=True, exist_ok=True)
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    snapshot = RuntimeSettingsManager().resolve(
        root=repo_root,
        cwd=cwd_dir,
    )

    assert snapshot.snapshot["plan"]["retrieval"]["retrieval_policy"] == "bugfix_test"
    assert snapshot.snapshot["plan"]["plan_replay_cache"]["enabled"] is True
    assert snapshot.snapshot["plan"]["retrieval"]["top_k_files"] == 10
    assert snapshot.provenance["plan"]["retrieval"]["retrieval_policy"] == "runtime_profile"
    assert snapshot.metadata["selected_profile"] == "bugfix"
    assert snapshot.metadata["selected_profile_source"] == "repo_config"
    assert snapshot.metadata["stats_tags"]["profile_key"] == "bugfix"
    assert snapshot.metadata["stats_tags"]["settings_fingerprint"] == snapshot.fingerprint


def test_runtime_settings_manager_resolves_scoring_overlay_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_home = tmp_path / "home"
    repo_root = tmp_path / "repo"
    cwd_dir = repo_root / "workspace"

    fake_home.mkdir(parents=True, exist_ok=True)
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    (repo_root / ".ace-lite.yml").write_text(
        yaml.safe_dump(
            {
                "plan": {
                    "retrieval": {
                        "bm25_k1": 1.7,
                        "heur_path_exact": 4.5,
                    },
                    "chunk": {
                        "file_prior_weight": 0.55,
                    },
                    "scip": {
                        "base_weight": 0.9,
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (cwd_dir / ".ace-lite.yml").write_text(
        yaml.safe_dump(
            {
                "plan": {
                    "retrieval": {
                        "hybrid_re2_shortlist_min": 20,
                    },
                    "chunk": {
                        "reference_cap": 3.5,
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    snapshot = RuntimeSettingsManager().resolve(root=repo_root, cwd=cwd_dir)

    assert snapshot.snapshot["plan"]["retrieval"]["bm25_k1"] == 1.7
    assert snapshot.provenance["plan"]["retrieval"]["bm25_k1"] == "repo_config"
    assert snapshot.snapshot["plan"]["retrieval"]["heur_path_exact"] == 4.5
    assert snapshot.provenance["plan"]["retrieval"]["heur_path_exact"] == "repo_config"
    assert snapshot.snapshot["plan"]["retrieval"]["hybrid_re2_shortlist_min"] == 20
    assert snapshot.provenance["plan"]["retrieval"]["hybrid_re2_shortlist_min"] == "cwd_config"
    assert snapshot.snapshot["plan"]["chunking"]["file_prior_weight"] == 0.55
    assert snapshot.provenance["plan"]["chunking"]["file_prior_weight"] == "repo_config"
    assert snapshot.snapshot["plan"]["chunking"]["reference_cap"] == 3.5
    assert snapshot.provenance["plan"]["chunking"]["reference_cap"] == "cwd_config"
    assert snapshot.snapshot["plan"]["scip"]["base_weight"] == 0.9
    assert snapshot.provenance["plan"]["scip"]["base_weight"] == "repo_config"


def test_runtime_settings_store_round_trip(tmp_path: Path) -> None:
    payload = build_runtime_settings_record(
        snapshot={"plan": {"retrieval": {"top_k_files": 8}}},
        provenance={"plan": {"retrieval": {"top_k_files": "default"}}},
        metadata={"root": str(tmp_path)},
    )
    target = tmp_path / "context-map" / "runtime-settings.json"
    write_runtime_settings_record(path=target, payload=payload)

    loaded = load_runtime_settings_record(target)

    assert loaded is not None
    assert loaded["snapshot"]["plan"]["retrieval"]["top_k_files"] == 8
    assert loaded["fingerprint"] == payload["fingerprint"]


def test_runtime_settings_store_paths_and_last_known_good_fallback(tmp_path: Path) -> None:
    current_path = resolve_user_runtime_settings_path(home_path=tmp_path)
    lkg_path = resolve_user_runtime_settings_last_known_good_path(home_path=tmp_path)

    expected_current_suffix = Path(DEFAULT_RUNTIME_SETTINGS_CURRENT_PATH.replace("~/", ""))
    expected_lkg_suffix = Path(DEFAULT_RUNTIME_SETTINGS_LAST_KNOWN_GOOD_PATH.replace("~/", ""))

    assert (
        current_path.parts[-len(expected_current_suffix.parts) :] == expected_current_suffix.parts
    )
    assert lkg_path.parts[-len(expected_lkg_suffix.parts) :] == expected_lkg_suffix.parts

    valid_payload = build_runtime_settings_record(
        snapshot={"plan": {"retrieval": {"top_k_files": 12}}},
        provenance={"plan": {"retrieval": {"top_k_files": "cli"}}},
        metadata={"root": str(tmp_path)},
    )
    persist_runtime_settings_record(
        current_path=current_path,
        last_known_good_path=lkg_path,
        payload=valid_payload,
        update_last_known_good=True,
    )

    current_path.write_text('{"schema_version": 1, "snapshot": {"broken": true}}', encoding="utf-8")

    loaded, source = load_runtime_settings_with_fallback(
        current_path=current_path,
        last_known_good_path=lkg_path,
    )

    assert source == "last_known_good"
    assert loaded is not None
    assert loaded["snapshot"]["plan"]["retrieval"]["top_k_files"] == 12

    current_summary = inspect_runtime_settings_record(current_path)
    lkg_summary = inspect_runtime_settings_record(lkg_path)

    assert current_summary["status"] == "invalid"
    assert current_summary["valid"] is False
    assert lkg_summary["status"] == "valid"
    assert lkg_summary["valid"] is True
    assert lkg_summary["fingerprint"] == valid_payload["fingerprint"]


def test_runtime_settings_paths_collide_detects_aliasing_slots(tmp_path: Path) -> None:
    shared = tmp_path / "runtime-settings.json"
    distinct = tmp_path / "last-known-good.json"

    assert (
        runtime_settings_paths_collide(
            current_path=shared,
            last_known_good_path=shared,
        )
        is True
    )
    assert (
        runtime_settings_paths_collide(
            current_path=shared,
            last_known_good_path=distinct,
        )
        is False
    )
