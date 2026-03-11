from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_profile_show_add_and_wipe(tmp_path: Path) -> None:
    runner = CliRunner()
    profile_path = tmp_path / "profile.json"

    show_empty = runner.invoke(
        cli_module.cli,
        ["profile", "show", "--profile-path", str(profile_path)],
        env=_cli_env(tmp_path),
    )
    assert show_empty.exit_code == 0
    empty_payload = json.loads(show_empty.output)
    assert empty_payload["facts"] == []

    add_fact = runner.invoke(
        cli_module.cli,
        [
            "profile",
            "add-fact",
            "prefer small deterministic patches",
            "--confidence",
            "0.8",
            "--profile-path",
            str(profile_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert add_fact.exit_code == 0

    show_after_add = runner.invoke(
        cli_module.cli,
        ["profile", "show", "--profile-path", str(profile_path)],
        env=_cli_env(tmp_path),
    )
    assert show_after_add.exit_code == 0
    after_add_payload = json.loads(show_after_add.output)
    assert len(after_add_payload["facts"]) == 1
    assert after_add_payload["facts"][0]["text"] == "prefer small deterministic patches"

    wipe = runner.invoke(
        cli_module.cli,
        ["profile", "wipe", "--profile-path", str(profile_path)],
        env=_cli_env(tmp_path),
    )
    assert wipe.exit_code == 0
    wipe_payload = json.loads(wipe.output)
    assert wipe_payload["ok"] is True

    show_after_wipe = runner.invoke(
        cli_module.cli,
        ["profile", "show", "--profile-path", str(profile_path)],
        env=_cli_env(tmp_path),
    )
    assert show_after_wipe.exit_code == 0
    after_wipe_payload = json.loads(show_after_wipe.output)
    assert after_wipe_payload["facts"] == []


def test_cli_profile_vacuum_prunes_expired_entries(tmp_path: Path) -> None:
    runner = CliRunner()
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        """{
  "version": 1,
  "facts": [
    {
      "text": "stale fact",
      "confidence": 0.7,
      "importance_score": 0.7,
      "use_count": 0,
      "last_used_at": "2020-01-01T00:00:00+00:00",
      "updated_at": "2020-01-01T00:00:00+00:00",
      "source": "manual",
      "metadata": {}
    },
    {
      "text": "fresh fact",
      "confidence": 0.8,
      "importance_score": 0.8,
      "use_count": 0,
      "last_used_at": "2099-01-01T00:00:00+00:00",
      "updated_at": "2099-01-01T00:00:00+00:00",
      "source": "manual",
      "metadata": {}
    }
  ],
  "preferences": {},
  "recent_contexts": []
}
""",
        encoding="utf-8",
    )

    first = runner.invoke(
        cli_module.cli,
        [
            "profile",
            "vacuum",
            "--profile-path",
            str(profile_path),
            "--ttl-days",
            "90",
            "--max-age-days",
            "365",
        ],
        env=_cli_env(tmp_path),
    )
    assert first.exit_code == 0
    first_payload = json.loads(first.output)
    assert first_payload["removed_facts"] == 1

    second = runner.invoke(
        cli_module.cli,
        [
            "profile",
            "vacuum",
            "--profile-path",
            str(profile_path),
            "--ttl-days",
            "90",
            "--max-age-days",
            "365",
        ],
        env=_cli_env(tmp_path),
    )
    assert second.exit_code == 0
    second_payload = json.loads(second.output)
    assert second_payload["removed_facts"] == 0

    show_payload = json.loads(
        runner.invoke(
            cli_module.cli,
            ["profile", "show", "--profile-path", str(profile_path)],
            env=_cli_env(tmp_path),
        ).output
    )
    assert [fact["text"] for fact in show_payload["facts"]] == ["fresh fact"]
