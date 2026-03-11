from __future__ import annotations

import hashlib
from pathlib import Path

from ace_lite.conventions import load_conventions


def test_load_conventions_defaults(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    conventions = tmp_path / "CONVENTIONS.md"
    agents.write_text("Agent guidance\n", encoding="utf-8")
    conventions.write_text("Coding conventions\n", encoding="utf-8")

    payload = load_conventions(root_dir=tmp_path)

    assert payload["count"] == 2
    assert len(payload["loaded_files"]) == 2
    assert "Agent guidance" in payload["combined_text"]
    assert "Coding conventions" in payload["combined_text"]


def test_load_conventions_custom_files_and_hash(tmp_path: Path) -> None:
    custom = tmp_path / "RULES.md"
    custom.write_text("Always add tests\n", encoding="utf-8")

    payload = load_conventions(root_dir=tmp_path, files=["RULES.md"])

    assert payload["count"] == 1
    entry = payload["loaded_files"][0]
    assert entry["path"] == str(custom.resolve())
    assert entry["sha256"] == hashlib.sha256(custom.read_bytes()).hexdigest()


def test_load_conventions_includes_rules_directory(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("Agent guidance\n", encoding="utf-8")

    rules_dir = tmp_path / ".ace-lite" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "python.md").write_text(
        "\n".join(
            [
                "---",
                "name: Python Style",
                "priority: 7",
                "always_load: true",
                "globs:",
                "  - \"src/**/*.py\"",
                "---",
                "Prefer typed public functions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = load_conventions(root_dir=tmp_path)
    assert payload["count"] == 1
    assert payload["rules_count"] == 1
    assert "Prefer typed public functions." in payload["combined_text"]
    assert payload["rules"][0]["name"] == "Python Style"
    assert payload["rules"][0]["priority"] == 7

    payload_cached = load_conventions(
        root_dir=tmp_path,
        previous_hashes=payload["file_hashes"],
    )
    assert payload_cached["cache_hit"] is True


def test_load_conventions_auto_discovers_copilot_prompt_files(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    conventions = tmp_path / "CONVENTIONS.md"
    agents.write_text("Agent guidance\n", encoding="utf-8")
    conventions.write_text("Coding conventions\n", encoding="utf-8")

    copilot = tmp_path / ".github" / "copilot-instructions.md"
    copilot.parent.mkdir(parents=True, exist_ok=True)
    copilot.write_text("Copilot instructions\n", encoding="utf-8")

    prompts_dir = tmp_path / ".github" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_b = prompts_dir / "b.md"
    prompt_a = prompts_dir / "a.md"
    prompt_c = prompts_dir / "sub" / "c.md"
    prompt_c.parent.mkdir(parents=True, exist_ok=True)
    prompt_b.write_text("Prompt B\n", encoding="utf-8")
    prompt_a.write_text("Prompt A\n", encoding="utf-8")
    prompt_c.write_text("Prompt C\n", encoding="utf-8")

    payload = load_conventions(root_dir=tmp_path)

    loaded_paths = [item.get("path") for item in payload.get("loaded_files", [])]
    assert loaded_paths[:2] == [str(agents.resolve()), str(conventions.resolve())]
    assert loaded_paths[2:] == [
        str(copilot.resolve()),
        str(prompt_a.resolve()),
        str(prompt_b.resolve()),
        str(prompt_c.resolve()),
    ]
    assert "Copilot instructions" in payload["combined_text"]
    assert "Prompt A" in payload["combined_text"]
