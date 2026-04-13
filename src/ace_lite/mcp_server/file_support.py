from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

_NOTES_WRITE_LOCK = Lock()


def resolve_root(*, root: str | None, default_root: Path) -> Path:
    if root is None or not str(root).strip():
        resolved = default_root
    else:
        candidate = Path(str(root)).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (Path.cwd() / candidate).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"root does not exist or is not directory: {resolved}")
    return resolved


def resolve_skills_dir(
    *,
    root_path: Path,
    skills_dir: str | None,
    default_skills_dir: Path,
) -> Path:
    if skills_dir is None or not str(skills_dir).strip():
        return default_skills_dir
    candidate = Path(str(skills_dir)).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_path / candidate).resolve()


def resolve_config_pack_path(
    *,
    root_path: Path,
    config_pack: str | None,
    default_config_pack: str | None,
) -> str | None:
    configured = str(config_pack or default_config_pack or "").strip()
    if not configured:
        return None
    candidate = Path(configured).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    return str((root_path / candidate).resolve())


def resolve_output_path(*, root_path: Path, output: str | None, default: str) -> Path:
    target = Path(output or default).expanduser()
    if target.is_absolute():
        return target.resolve()
    return (root_path / target).resolve()


def resolve_notes_path(*, notes_path: str | None, default_notes_path: Path) -> Path:
    value = Path(notes_path).expanduser() if notes_path else default_notes_path
    if value.is_absolute():
        return value.resolve()
    return (Path.cwd() / value).resolve()


def load_notes(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def save_notes(path: Path, rows: list[dict[str, Any]]) -> None:
    with _NOTES_WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        path.write_text((content + "\n") if content else "", encoding="utf-8")


def append_note(path: Path, row: dict[str, Any]) -> None:
    with _NOTES_WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


__all__ = [
    "append_note",
    "load_notes",
    "resolve_config_pack_path",
    "resolve_notes_path",
    "resolve_output_path",
    "resolve_root",
    "resolve_skills_dir",
    "save_notes",
]
