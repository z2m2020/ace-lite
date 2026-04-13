from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

from ace_lite.chunk_cache_contract import build_chunk_cache_contract
from ace_lite.parsers.languages import (
    detect_language,
    normalize_languages,
    supported_extensions,
)
from ace_lite.parsers.treesitter_engine import TreeSitterEngine

DEFAULT_EXCLUDE_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
    ".idea",
    ".vscode",
    "node_modules",
    "artifacts",
}

ACEIGNORE_FILENAME = ".aceignore"


def classify_tier(*, path: str, language: str) -> str:
    """Classify a source file as first-party or dependency."""
    normalized = str(path or "").strip().replace("\\", "/").lstrip("./")
    if normalized.startswith("node_modules/"):
        return "dependency"
    if (
        str(language or "").strip().lower() == "solidity"
        and normalized.startswith("lib/")
    ):
        return "dependency"
    return "first_party"


def _default_exclude_dirs(*, enabled_languages: tuple[str, ...]) -> set[str]:
    excluded = set(DEFAULT_EXCLUDE_DIRS)
    # Solidity projects commonly vendor dependency contracts under node_modules/.
    # We keep dependency code available for deep repo analysis, but later gate
    # collection inside node_modules to `.sol` only (see `_iter_source_files`).
    if "solidity" in set(enabled_languages):
        excluded.discard("node_modules")
    return excluded


def discover_source_files(
    root_dir: str | Path,
    *,
    include_globs: Iterable[str] | None = None,
    exclude_dirs: Iterable[str] | None = None,
    languages: Iterable[str] | None = None,
) -> tuple[Path, tuple[str, ...], list[Path]]:
    """Discover indexable source files under ``root_dir`` deterministically.

    Returns:
        (root_path, enabled_languages, files)

    The returned file list is sorted by repo-relative POSIX path so that callers
    can safely checkpoint/resume work while preserving deterministic ordering.
    """

    root_path = _validate_root_dir(root_dir)
    enabled_languages = normalize_languages(
        tuple(languages) if languages is not None else None
    )
    suffixes = supported_extensions(enabled_languages)
    aceignore_patterns = _load_aceignore_patterns(root_path=root_path)

    excluded = _default_exclude_dirs(enabled_languages=enabled_languages)
    if exclude_dirs:
        excluded.update(str(item) for item in exclude_dirs)

    files = _iter_source_files(
        root_path=root_path,
        include_globs=include_globs,
        excluded_dirs=excluded,
        suffixes=suffixes,
        aceignore_patterns=aceignore_patterns,
    )
    return root_path, enabled_languages, files


def build_index(
    root_dir: str | Path,
    include_globs: Iterable[str] | None = None,
    exclude_dirs: Iterable[str] | None = None,
    languages: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a full source index for supported languages under ``root_dir``."""
    root_path, enabled_languages, file_paths = discover_source_files(
        root_dir,
        include_globs=include_globs,
        exclude_dirs=exclude_dirs,
        languages=languages,
    )
    engine = TreeSitterEngine(enabled_languages)
    files: dict[str, dict[str, Any]] = {}

    for file_path in file_paths:
        entry = engine.parse_file(file_path, root_path)
        if entry is None:
            continue
        entry["tier"] = classify_tier(
            path=str(entry.get("path") or ""),
            language=str(entry.get("language") or ""),
        )
        files[entry["path"]] = entry

    return finalize_index_payload(
        {
            "root_dir": str(root_path),
            "files": files,
            "parser": {
                "engine": "tree-sitter",
                "version": engine.parser_version,
            },
            "configured_languages": list(enabled_languages),
        }
    )


def update_index(
    existing_index: dict[str, Any],
    root_dir: str | Path,
    changed_files: Iterable[str | Path],
    languages: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Apply incremental updates for changed files."""
    root_path = _validate_root_dir(root_dir)
    enabled_languages = normalize_languages(
        tuple(languages) if languages is not None else None
    )
    excluded_dirs = _default_exclude_dirs(enabled_languages=enabled_languages)
    suffixes = supported_extensions(enabled_languages)
    aceignore_patterns = _load_aceignore_patterns(root_path=root_path)

    engine = TreeSitterEngine(enabled_languages)
    # Shallow copy: top-level dict + "files" dict are new objects.
    # Individual file entries are shared references with existing_index,
    # which is safe because update_index only replaces entries at the key
    # level (never mutates an existing entry in-place).
    index = dict(existing_index or {})
    index["files"] = dict(index.get("files") or {})
    index["root_dir"] = str(root_path)
    index["parser"] = {
        "engine": "tree-sitter",
        "version": engine.parser_version,
    }
    index["configured_languages"] = list(enabled_languages)

    files = index.get("files")
    if not isinstance(files, dict):
        files = {}
        index["files"] = files

    for changed_file in changed_files:
        relative_path = _normalize_changed_path(changed_file, root_path)
        if relative_path is None:
            continue

        if any(part in excluded_dirs for part in relative_path.parts[:-1]):
            files.pop(relative_path.as_posix(), None)
            continue

        key = relative_path.as_posix()
        if aceignore_patterns and _is_aceignored(
            relative_posix_path=key,
            patterns=aceignore_patterns,
        ):
            files.pop(key, None)
            continue
        absolute_path = root_path / relative_path
        language = detect_language(relative_path)
        in_node_modules = "node_modules" in relative_path.parts[:-1]
        effective_suffixes = {".sol"} if in_node_modules and ".sol" in suffixes else suffixes

        if (
            not absolute_path.exists()
            or not absolute_path.is_file()
            or absolute_path.suffix.lower() not in effective_suffixes
            or language is None
        ):
            files.pop(key, None)
            continue

        fingerprint = _file_fingerprint(path=absolute_path)
        cached_entry = files.get(key)
        if fingerprint is not None and isinstance(cached_entry, dict):
            try:
                cached_mtime_ns = int(cached_entry.get("mtime_ns", -1) or -1)
                cached_size_bytes = int(cached_entry.get("size_bytes", -1) or -1)
            except (TypeError, ValueError):
                cached_mtime_ns = -1
                cached_size_bytes = -1
            if cached_mtime_ns == fingerprint[0] and cached_size_bytes == fingerprint[1]:
                continue

        entry = engine.parse_file(absolute_path, root_path)
        if entry is None:
            files.pop(key, None)
            continue

        entry["tier"] = classify_tier(
            path=key,
            language=str(entry.get("language") or ""),
        )
        files[key] = entry

    return finalize_index_payload(index)


def _file_fingerprint(*, path: Path) -> tuple[int, int] | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None

    mtime_ns = getattr(stat_result, "st_mtime_ns", None)
    if not isinstance(mtime_ns, int):
        mtime_seconds = float(getattr(stat_result, "st_mtime", 0.0) or 0.0)
        mtime_ns = int(mtime_seconds * 1_000_000_000)
    size_bytes = int(getattr(stat_result, "st_size", 0) or 0)
    return max(0, int(mtime_ns)), max(0, int(size_bytes))


def _validate_root_dir(root_dir: str | Path) -> Path:
    root_path = Path(root_dir).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"root_dir must be an existing directory: {root_dir}")
    return root_path


def _iter_source_files(
    *,
    root_path: Path,
    include_globs: Iterable[str] | None,
    excluded_dirs: set[str],
    suffixes: set[str],
    aceignore_patterns: list[str],
) -> list[Path]:
    if include_globs:
        candidates: set[Path] = set()
        for pattern in include_globs:
            for path in root_path.glob(pattern):
                candidates.add(path)

        collected: list[Path] = []
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in suffixes:
                continue

            resolved = path.resolve()
            try:
                parent_parts = resolved.relative_to(root_path).parts[:-1]
            except ValueError:
                continue

            if any(part in excluded_dirs for part in parent_parts):
                continue

            relative = resolved.relative_to(root_path).as_posix()
            if aceignore_patterns and _is_aceignored(
                relative_posix_path=relative,
                patterns=aceignore_patterns,
            ):
                continue
            collected.append(resolved)

        collected.sort(key=lambda value: value.relative_to(root_path).as_posix())
        return collected

    collected = []
    for current_root, dir_names, file_names in os.walk(root_path, topdown=True):
        dir_names[:] = [name for name in dir_names if name not in excluded_dirs]
        base_path = Path(current_root)
        try:
            rel_parts = base_path.relative_to(root_path).parts
        except ValueError:
            rel_parts = ()
        in_node_modules = "node_modules" in rel_parts
        effective_suffixes = {".sol"} if in_node_modules and ".sol" in suffixes else suffixes

        for file_name in file_names:
            candidate = base_path / file_name
            if candidate.suffix.lower() not in effective_suffixes:
                continue

            resolved = candidate.resolve()
            try:
                relative = resolved.relative_to(root_path).as_posix()
            except ValueError:
                continue

            if aceignore_patterns and _is_aceignored(
                relative_posix_path=relative,
                patterns=aceignore_patterns,
            ):
                continue
            collected.append(resolved)

    collected.sort(key=lambda value: value.relative_to(root_path).as_posix())
    return collected


def _load_aceignore_patterns(*, root_path: Path) -> list[str]:
    path = root_path / ACEIGNORE_FILENAME
    if not path.exists() or not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    patterns: list[str] = []
    for line in text.splitlines():
        raw = str(line or "").strip()
        if not raw or raw.startswith("#"):
            continue
        normalized = raw.replace("\\", "/")
        if normalized and normalized not in patterns:
            patterns.append(normalized)
    return patterns


def _aceignore_match(*, relative_posix_path: str, pattern: str) -> bool:
    normalized_path = str(relative_posix_path or "").strip().replace("\\", "/")
    while normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]
    if not normalized_path:
        return False

    normalized_pattern = str(pattern or "").strip().replace("\\", "/")
    while normalized_pattern.startswith("./"):
        normalized_pattern = normalized_pattern[2:]
    while normalized_pattern.startswith("/"):
        normalized_pattern = normalized_pattern[1:]
    if not normalized_pattern:
        return False

    if normalized_pattern.endswith("/"):
        prefix = normalized_pattern.rstrip("/")
        if not prefix:
            return False
        return normalized_path == prefix or normalized_path.startswith(prefix + "/")

    if "/" in normalized_pattern:
        return fnmatchcase(normalized_path, normalized_pattern)

    name = PurePosixPath(normalized_path).name
    return fnmatchcase(name, normalized_pattern)


def _is_aceignored(*, relative_posix_path: str, patterns: list[str]) -> bool:
    ignored = False
    for raw in patterns:
        candidate = str(raw or "").strip()
        if not candidate or candidate.startswith("#"):
            continue
        negated = candidate.startswith("!")
        if negated:
            candidate = candidate[1:].strip()
        if not candidate:
            continue
        if _aceignore_match(relative_posix_path=relative_posix_path, pattern=candidate):
            ignored = not negated
    return ignored


def _normalize_changed_path(changed_file: str | Path, root_path: Path) -> Path | None:
    candidate = Path(changed_file)
    if not candidate.is_absolute():
        candidate = root_path / candidate

    try:
        return candidate.resolve().relative_to(root_path)
    except (OSError, ValueError):
        return None


def _finalize_index(index: dict[str, Any]) -> dict[str, Any]:
    files = index.get("files")
    if not isinstance(files, dict):
        files = {}
        index["files"] = files

    for entry in files.values():
        if not isinstance(entry, dict):
            continue
        references = entry.get("references")
        if not isinstance(references, list):
            entry["references"] = []

    languages: set[str] = set()
    for entry in files.values():
        if not isinstance(entry, dict):
            continue
        language = entry.get("language")
        if isinstance(language, str) and language:
            languages.add(language)
    languages_covered = sorted(languages)

    index["file_count"] = len(files)
    index["languages_covered"] = languages_covered
    index["chunk_cache_contract"] = build_chunk_cache_contract(files)
    index["indexed_at"] = datetime.now(timezone.utc).isoformat()
    return index


def finalize_index_payload(index: dict[str, Any]) -> dict[str, Any]:
    """Finalize a distilled index payload with derived metadata fields."""

    return _finalize_index(index)


__all__ = [
    "build_index",
    "discover_source_files",
    "finalize_index_payload",
    "update_index",
]
