from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_memory_search_includes_guardrail_fields(tmp_path: Path) -> None:
    runner = CliRunner()
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(
        '{"text":"refresh token fallback","namespace":"auth","captured_at":"2020-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "latest update refresh",
            "--namespace",
            "auth",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert isinstance(payload["disclaimer"], str)
    assert payload["disclaimer"]
    assert payload["recency_alert"] is not None
    assert payload["recency_alert"]["triggered"] is True
    assert payload["staleness_warning"] is not None
    assert payload["staleness_warning"]["triggered"] is True
