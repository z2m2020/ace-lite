from __future__ import annotations

import json
from pathlib import Path

from ace_lite.memory.local_notes import append_capture_note


def test_append_capture_note_ignores_invalid_json_and_prunes_expired(tmp_path: Path) -> None:
    notes_path = tmp_path / "memory_notes.jsonl"
    notes_path.write_text(
        "\n".join(
            [
                "{not-json}",
                '{"query":"old issue","repo":"demo","captured_at":"2020-01-01T00:00:00+00:00"}',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    captured_items, pruned = append_capture_note(
        notes_path=notes_path,
        query="please fix bug in auth stage",
        repo="demo",
        namespace="team-alpha",
        matched_keywords=["fix", "bug"],
        expiry_enabled=True,
        ttl_days=90,
        max_age_days=365,
    )

    assert captured_items == 1
    assert pruned == 1

    rows = [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["repo"] == "demo"
    assert payload["namespace"] == "team-alpha"
    assert "fix" in payload["matched_keywords"]

