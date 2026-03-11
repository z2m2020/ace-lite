from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.rules import load_rules

DEFAULT_CONVENTION_FILES: tuple[str, ...] = ("AGENTS.md", "CONVENTIONS.md")
DEFAULT_COPILOT_INSTRUCTIONS = ".github/copilot-instructions.md"
DEFAULT_COPILOT_PROMPTS_DIR = ".github/prompts"


@dataclass(slots=True)
class ConventionEntry:
    path: str
    sha256: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "content": self.content,
        }


def load_conventions(
    *,
    root_dir: str | Path,
    files: list[str] | tuple[str, ...] | None = None,
    previous_hashes: Mapping[str, str] | None = None,
    include_rules: bool = True,
    include_prompt_files: bool = True,
    rules_dir: str | Path = ".ace-lite/rules",
) -> dict[str, Any]:
    root = Path(root_dir)
    targets = list(files) if files else list(DEFAULT_CONVENTION_FILES)
    if include_prompt_files:
        for relative in _discover_prompt_files(root=root):
            if relative not in targets:
                targets.append(relative)

    loaded: list[ConventionEntry] = []
    for relative in targets:
        path = root / relative
        if not path.exists() or not path.is_file():
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        loaded.append(
            ConventionEntry(
                path=str(path.resolve()),
                sha256=hashlib.sha256(raw).hexdigest(),
                content=text,
            )
        )

    combined_parts = [
        item.content for item in loaded if isinstance(item.content, str) and item.content.strip()
    ]
    file_hashes = {item.path: item.sha256 for item in loaded}

    rules_payload: dict[str, Any] = {
        "count": 0,
        "rules": [],
        "combined_text": "",
        "file_hashes": {},
    }
    if include_rules:
        rules_payload = load_rules(
            root_dir=root,
            rules_dir=rules_dir,
            previous_hashes=previous_hashes if isinstance(previous_hashes, Mapping) else None,
        )
        rules_text = str(rules_payload.get("combined_text") or "").strip()
        if rules_text:
            combined_parts.append(rules_text)
        rules_hashes = rules_payload.get("file_hashes")
        if isinstance(rules_hashes, dict):
            for path, sha in rules_hashes.items():
                file_hashes[str(path)] = str(sha)

    combined_text = "\n\n".join(part for part in combined_parts if str(part).strip())
    normalized_previous = {str(path): str(sha) for path, sha in (previous_hashes or {}).items()}
    cache_hit = bool(normalized_previous) and normalized_previous == file_hashes
    return {
        "loaded_files": [item.to_dict() for item in loaded],
        "count": len(loaded),
        "rules": rules_payload.get("rules", []),
        "rules_count": int(rules_payload.get("count", 0) or 0),
        "combined_text": combined_text,
        "cache_hit": cache_hit,
        "file_hashes": file_hashes,
    }


def _discover_prompt_files(*, root: Path) -> list[str]:
    discovered: list[str] = []

    instructions = root / DEFAULT_COPILOT_INSTRUCTIONS
    if instructions.exists() and instructions.is_file():
        try:
            discovered.append(instructions.relative_to(root).as_posix())
        except ValueError:
            discovered.append(str(instructions))

    prompts_dir = root / DEFAULT_COPILOT_PROMPTS_DIR
    if not prompts_dir.exists() or not prompts_dir.is_dir():
        return discovered

    for path in sorted(prompts_dir.rglob("*.md"), key=lambda item: item.as_posix()):
        if not path.exists() or not path.is_file():
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = str(path)
        if relative and relative not in discovered:
            discovered.append(relative)

    return discovered


__all__ = ["DEFAULT_CONVENTION_FILES", "load_conventions"]
