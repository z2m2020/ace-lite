from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app.runtime_status_config_support import (
    RuntimeStatusSections,
    build_runtime_status_cache_paths,
    resolve_runtime_feedback_path_from_settings,
    resolve_runtime_status_repo_relative_path,
    resolve_runtime_status_sections,
)


def test_runtime_status_config_support_resolves_feedback_path_from_preferred_scopes() -> None:
    assert (
        resolve_runtime_feedback_path_from_settings(
            {"memory": {"feedback": {"path": "top-level/profile.json"}}}
        )
        == "top-level/profile.json"
    )
    assert (
        resolve_runtime_feedback_path_from_settings(
            {"plan": {"memory": {"feedback": {"path": "plan/profile.json"}}}}
        )
        == "plan/profile.json"
    )
    assert (
        resolve_runtime_feedback_path_from_settings(
            {"benchmark": {"memory": {"feedback": {"path": "bench/profile.json"}}}}
        )
        == "bench/profile.json"
    )
    assert resolve_runtime_feedback_path_from_settings({}) is None


def test_runtime_status_config_support_resolves_sections_and_cache_paths(
    tmp_path: Path,
) -> None:
    settings = {
        "mcp": {"notes_path": "context-map/memory_notes.jsonl"},
        "plan": {
            "index": {"cache_path": "context-map/index.json"},
            "embeddings": {"index_path": "context-map/embeddings/index.json"},
            "plan_replay_cache": {"cache_path": ".ace-lite/plan-replay.json"},
            "trace": {"export_enabled": True, "export_path": "tmp/trace.json"},
            "skills": {"dir": "skills"},
            "plugins": {"enabled": True},
            "cochange": {"cache_path": "context-map/cochange.json"},
        },
    }

    sections = resolve_runtime_status_sections(settings)

    assert isinstance(sections, RuntimeStatusSections)
    assert sections.plan_plugins == {"enabled": True}
    assert sections.plan_lsp == {}

    cache_paths = build_runtime_status_cache_paths(
        root_path=tmp_path,
        sections=sections,
        runtime_stats={"db_path": tmp_path / ".ace-lite" / "runtime_state.db"},
    )

    assert cache_paths["index"] == str((tmp_path / "context-map/index.json").resolve())
    assert cache_paths["embeddings"] == str(
        (tmp_path / "context-map/embeddings/index.json").resolve()
    )
    assert cache_paths["plan_replay_cache"] == str(
        (tmp_path / ".ace-lite/plan-replay.json").resolve()
    )
    assert cache_paths["trace_export"] == str((tmp_path / "tmp/trace.json").resolve())
    assert cache_paths["memory_notes"] == str(
        (tmp_path / "context-map/memory_notes.jsonl").resolve()
    )
    assert cache_paths["cochange"] == str(
        (tmp_path / "context-map/cochange.json").resolve()
    )
    assert cache_paths["skills_dir"] == str((tmp_path / "skills").resolve())
    assert cache_paths["runtime_stats_db"] == str(
        (tmp_path / ".ace-lite/runtime_state.db").resolve()
    )


def test_runtime_status_config_support_normalizes_repo_relative_paths(
    tmp_path: Path,
) -> None:
    assert resolve_runtime_status_repo_relative_path(root=tmp_path, configured_path="  ") is None
    assert resolve_runtime_status_repo_relative_path(root=tmp_path, configured_path=None) is None
    assert resolve_runtime_status_repo_relative_path(
        root=tmp_path,
        configured_path="context-map/index.json",
    ) == str((tmp_path / "context-map/index.json").resolve())


def test_runtime_status_config_support_expands_user_home_paths(tmp_path: Path) -> None:
    configured_path = "~/runtime-feedback/profile.json"

    expected = str(Path(configured_path).expanduser().resolve())

    assert (
        resolve_runtime_status_repo_relative_path(
            root=tmp_path,
            configured_path=configured_path,
        )
        == expected
    )
