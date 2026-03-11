from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class RuleEntry:
    path: str
    sha256: str
    name: str
    description: str
    globs: list[str]
    priority: int
    always_load: bool
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "name": self.name,
            "description": self.description,
            "globs": list(self.globs),
            "priority": int(self.priority),
            "always_load": bool(self.always_load),
            "content": self.content,
        }


def load_rules(
    *,
    root_dir: str | Path,
    rules_dir: str | Path = ".ace-lite/rules",
    previous_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(root_dir)
    target_dir = Path(rules_dir)
    if not target_dir.is_absolute():
        target_dir = root / target_dir

    if not target_dir.exists() or not target_dir.is_dir():
        return {
            "count": 0,
            "rules": [],
            "combined_text": "",
            "cache_hit": False,
            "file_hashes": {},
        }

    entries: list[RuleEntry] = []
    file_hashes: dict[str, str] = {}

    for path in sorted(target_dir.glob("*.md"), key=lambda item: item.as_posix()):
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        metadata, body = _parse_front_matter(text)

        name = str(metadata.get("name") or path.stem).strip() or path.stem
        description = str(metadata.get("description") or "").strip()
        globs = _normalize_globs(metadata.get("globs"))
        priority = _to_int(metadata.get("priority"), default=0)
        always_load = bool(metadata.get("always_load", False))
        sha256 = hashlib.sha256(raw).hexdigest()

        entry = RuleEntry(
            path=str(path.resolve()),
            sha256=sha256,
            name=name,
            description=description,
            globs=globs,
            priority=priority,
            always_load=always_load,
            content=body.strip(),
        )
        entries.append(entry)
        file_hashes[entry.path] = entry.sha256

    ordered = sorted(
        entries,
        key=lambda item: (-int(item.priority), str(item.name), str(item.path)),
    )
    combined_sections: list[str] = []
    for entry in ordered:
        if not entry.content:
            continue
        combined_sections.append(f"## Rule: {entry.name}\n{entry.content}")

    normalized_previous = {
        str(path): str(sha) for path, sha in (previous_hashes or {}).items()
    }
    cache_hit = bool(normalized_previous) and normalized_previous == file_hashes

    return {
        "count": len(ordered),
        "rules": [entry.to_dict() for entry in ordered],
        "combined_text": "\n\n".join(combined_sections).strip(),
        "cache_hit": cache_hit,
        "file_hashes": file_hashes,
    }


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    content = str(text or "")
    lines = content.splitlines(keepends=True)
    if not lines:
        return {}, content
    if lines[0].strip() != "---":
        return {}, content

    closing_index = -1
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index <= 0:
        return {}, content

    raw_front_matter = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :])

    try:
        payload = yaml.safe_load(raw_front_matter)
    except Exception:
        payload = {}

    return (payload if isinstance(payload, dict) else {}), body


def _normalize_globs(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else ["**/*"]

    if isinstance(value, (list, tuple)):
        output: list[str] = []
        for item in value:
            glob = str(item).strip()
            if glob and glob not in output:
                output.append(glob)
        return output or ["**/*"]

    return ["**/*"]


def _to_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


__all__ = ["RuleEntry", "load_rules"]
