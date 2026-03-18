from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.mcp_server.service_feedback_handlers import (
    handle_feedback_record_request,
    handle_feedback_stats_request,
    resolve_feedback_profile_path,
)


def test_resolve_feedback_profile_path_resolves_relative_under_root(
    tmp_path: Path,
) -> None:
    profile = resolve_feedback_profile_path(
        root_path=tmp_path,
        profile_path="context-map/profile.json",
    )

    assert profile == (tmp_path / "context-map" / "profile.json").resolve()


def test_handle_feedback_record_and_stats_round_trip(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    selected = src_dir / "sample.py"
    selected.write_text("print('ok')\n", encoding="utf-8")

    recorded = handle_feedback_record_request(
        query="openmemory 405 dimension mismatch",
        selected_path=str(selected),
        repo="demo-repo",
        user_id="mcp-user",
        profile_key="bugfix",
        root_path=tmp_path,
        default_repo="default-repo",
        profile_path="context-map/profile.json",
        position=1,
        max_entries=8,
    )

    assert recorded["ok"] is True
    assert Path(recorded["profile_path"]).exists()
    assert recorded["store_path"] == recorded["profile_path"]
    assert recorded["configured_path"] == str(
        (tmp_path / "context-map" / "profile.json").resolve()
    )
    assert recorded["recorded"]["event"]["selected_path"] == "src/sample.py"
    assert recorded["recorded"]["event"]["user_id"] == "mcp-user"
    assert recorded["recorded"]["event"]["profile_key"] == "bugfix"

    stats = handle_feedback_stats_request(
        repo="demo-repo",
        user_id="mcp-user",
        profile_key="bugfix",
        root_path=tmp_path,
        default_repo="default-repo",
        profile_path="context-map/profile.json",
        query="openmemory 405",
        boost_per_select=0.15,
        max_boost=0.6,
        decay_days=60.0,
        top_n=5,
        max_entries=8,
    )

    assert stats["ok"] is True
    assert stats["store_path"] == stats["profile_path"]
    assert stats["configured_path"] == str(
        (tmp_path / "context-map" / "profile.json").resolve()
    )
    assert stats["stats"]["matched_event_count"] == 1
    assert stats["stats"]["unique_paths"] == 1
    assert stats["stats"]["user_id_filter"] == "mcp-user"
    assert stats["stats"]["profile_key_filter"] == "bugfix"


def test_handle_feedback_record_requires_query_and_selected_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="query cannot be empty"):
        handle_feedback_record_request(
            query=" ",
            selected_path="x.py",
            repo=None,
            user_id=None,
            profile_key=None,
            root_path=tmp_path,
            default_repo="default-repo",
            profile_path=None,
            position=None,
            max_entries=8,
        )

    with pytest.raises(ValueError, match="selected_path cannot be empty"):
        handle_feedback_record_request(
            query="query",
            selected_path=" ",
            repo=None,
            user_id=None,
            profile_key=None,
            root_path=tmp_path,
            default_repo="default-repo",
            profile_path=None,
            position=None,
            max_entries=8,
        )


def test_resolve_feedback_profile_path_uses_default_profile_when_missing(
    tmp_path: Path,
) -> None:
    profile = resolve_feedback_profile_path(
        root_path=tmp_path,
        profile_path=None,
    )

    assert profile.name == "profile.json"
    assert ".ace-lite" in str(profile)


def test_handle_feedback_stats_without_query_skips_query_term_extraction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"extract_terms": False}

    def fail_extract_terms(*args, **kwargs):
        called["extract_terms"] = True
        raise AssertionError("extract_terms should not be called when query is empty")

    monkeypatch.setattr(
        "ace_lite.mcp_server.service_feedback_handlers.extract_terms",
        fail_extract_terms,
    )

    stats = handle_feedback_stats_request(
        repo=None,
        user_id=None,
        profile_key=None,
        root_path=tmp_path,
        default_repo="default-repo",
        profile_path="context-map/profile.json",
        query=" ",
        boost_per_select=0.15,
        max_boost=0.6,
        decay_days=60.0,
        top_n=5,
        max_entries=8,
    )

    assert stats["ok"] is True
    assert called["extract_terms"] is False
