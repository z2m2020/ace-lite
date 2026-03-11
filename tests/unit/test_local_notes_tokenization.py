from __future__ import annotations

from pathlib import Path

from ace_lite.memory import LocalNotesProvider, NullMemoryProvider


def _write_notes(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    import json

    for row in rows:
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_local_notes_provider_code_aware_tokens_match_camel_case(tmp_path: Path) -> None:
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {"text": "Implement getUserById handler", "namespace": "repo:a"},
            {"text": "Unrelated note about something else", "namespace": "repo:a"},
        ],
    )
    provider = LocalNotesProvider(
        NullMemoryProvider(),
        notes_path=notes_path,
        mode="local_only",
    )

    rows = provider.search_compact("get user id", container_tag="repo:a")
    assert len(rows) == 1
    assert "getUserById" in rows[0].preview


def test_local_notes_provider_code_aware_tokens_match_paths(tmp_path: Path) -> None:
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {"text": "Touched internal/app/api/shutdown/middleware.go", "namespace": "repo:a"},
            {"text": "Touched pkg/contract/erc20/token.go", "namespace": "repo:a"},
        ],
    )
    provider = LocalNotesProvider(
        NullMemoryProvider(),
        notes_path=notes_path,
        mode="local_only",
    )

    rows = provider.search_compact("shutdown middleware", container_tag="repo:a")
    assert len(rows) == 1
    assert "shutdown" in rows[0].preview.lower()

