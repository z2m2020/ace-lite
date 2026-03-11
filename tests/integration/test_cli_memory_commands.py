from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_memory_store_search_and_wipe(tmp_path: Path) -> None:
    runner = CliRunner()
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"

    store_a = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "store",
            "Fix auth fallback logic",
            "--namespace",
            "repo:a",
            "--tag",
            "kind=bugfix",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert store_a.exit_code == 0

    store_b = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "store",
            "Refactor benchmark report formatting",
            "--namespace",
            "repo:b",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert store_b.exit_code == 0

    search_a = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "fix auth",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert search_a.exit_code == 0
    search_a_payload = json.loads(search_a.output)
    assert search_a_payload["count"] == 1
    assert search_a_payload["items"][0]["namespace"] == "repo:a"

    wipe_a = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "wipe",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert wipe_a.exit_code == 0
    wipe_a_payload = json.loads(wipe_a.output)
    assert wipe_a_payload["removed_count"] == 1

    search_all = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "refactor",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert search_all.exit_code == 0
    search_all_payload = json.loads(search_all.output)
    assert search_all_payload["count"] == 1
    assert search_all_payload["items"][0]["namespace"] == "repo:b"


def test_cli_memory_vacuum_prunes_expired_notes_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(
        "\n".join(
            [
                '{"text":"stale","namespace":"repo:a","captured_at":"2020-01-01T00:00:00+00:00"}',
                '{"text":"fresh","namespace":"repo:a","captured_at":"2099-01-01T00:00:00+00:00"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "vacuum",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
            "--ttl-days",
            "90",
            "--max-age-days",
            "365",
        ],
        env=_cli_env(tmp_path),
    )
    assert first.exit_code == 0
    first_payload = json.loads(first.output)
    assert first_payload["removed_count"] == 1

    second = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "vacuum",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
            "--ttl-days",
            "90",
            "--max-age-days",
            "365",
        ],
        env=_cli_env(tmp_path),
    )
    assert second.exit_code == 0
    second_payload = json.loads(second.output)
    assert second_payload["removed_count"] == 0

    search = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "fresh",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert search.exit_code == 0
    search_payload = json.loads(search.output)
    assert search_payload["count"] == 1
    assert search_payload["items"][0]["text"] == "fresh"
