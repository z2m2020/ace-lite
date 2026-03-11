"""Cache helpers for docs-channel section and glossary loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

Section = dict[str, Any]
SectionCache = dict[tuple[str, int, int], tuple[str, list[Section]]]
RepoGlossaryCache = dict[tuple[str, int], tuple[str, list[str]]]


def load_sections(
    *,
    root: Path,
    max_files: int,
    max_section_chars: int,
    section_cache: SectionCache,
    sections_cache_path: str,
    collect_docs_paths: Callable[..., list[Path]],
    docs_fingerprint: Callable[..., str],
    parse_markdown_sections: Callable[..., list[Section]],
    load_sections_from_disk_cache: Callable[..., list[Section] | None],
    store_sections_to_disk_cache: Callable[..., bool],
) -> tuple[list[Section], str, bool, str, bool, str]:
    docs_paths = collect_docs_paths(root=root, max_files=max_files)
    fingerprint = docs_fingerprint(paths=docs_paths)
    cache_key = (str(root.resolve()), max_files, max_section_chars)
    cache_path = resolve_sections_cache_path(
        root=root,
        relative_cache_path=sections_cache_path,
    )
    cache_path_value = str(cache_path.as_posix())

    cached = section_cache.get(cache_key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1], fingerprint, True, "memory", False, cache_path_value

    disk_cached = load_sections_from_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=fingerprint,
        max_files=max_files,
        max_section_chars=max_section_chars,
    )
    if disk_cached is not None:
        section_cache[cache_key] = (fingerprint, disk_cached)
        return disk_cached, fingerprint, True, "disk", False, cache_path_value

    sections: list[Section] = []
    for path in docs_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_path = path.relative_to(root).as_posix()
        sections.extend(
            parse_markdown_sections(
                path=rel_path,
                text=text,
                max_section_chars=max_section_chars,
            )
        )

    cache_store_written = store_sections_to_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=fingerprint,
        max_files=max_files,
        max_section_chars=max_section_chars,
        sections=sections,
    )
    section_cache[cache_key] = (fingerprint, sections)
    return (
        sections,
        fingerprint,
        False,
        "none",
        bool(cache_store_written),
        cache_path_value,
    )


def resolve_sections_cache_path(*, root: Path, relative_cache_path: str) -> Path:
    return root / relative_cache_path


def resolve_repo_glossary_cache_path(*, root: Path, relative_cache_path: str) -> Path:
    return root / relative_cache_path


def load_repo_glossary(
    *,
    root: Path,
    docs_fingerprint: str,
    sections: list[Section],
    repo_glossary_cache: RepoGlossaryCache,
    glossary_cache_path: str,
    load_repo_glossary_from_disk_cache: Callable[..., list[str] | None],
    store_repo_glossary_to_disk_cache: Callable[..., bool],
    build_repo_glossary: Callable[..., list[str]],
    max_terms: int = 128,
) -> tuple[list[str], bool, str, bool, str]:
    cache_key = (str(root.resolve()), int(max_terms))
    cache_path = resolve_repo_glossary_cache_path(
        root=root,
        relative_cache_path=glossary_cache_path,
    )
    cache_path_value = str(cache_path.as_posix())

    cached = repo_glossary_cache.get(cache_key)
    if cached is not None and str(cached[0]) == str(docs_fingerprint):
        return list(cached[1]), True, "memory", False, cache_path_value

    disk_cached = load_repo_glossary_from_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=docs_fingerprint,
        max_terms=max_terms,
    )
    if disk_cached is not None:
        repo_glossary_cache[cache_key] = (str(docs_fingerprint), list(disk_cached))
        return list(disk_cached), True, "disk", False, cache_path_value

    glossary = build_repo_glossary(sections=sections, max_terms=max_terms)
    cache_store_written = store_repo_glossary_to_disk_cache(
        cache_path=cache_path,
        docs_fingerprint=docs_fingerprint,
        max_terms=max_terms,
        glossary=glossary,
    )
    repo_glossary_cache[cache_key] = (str(docs_fingerprint), list(glossary))
    return list(glossary), False, "none", bool(cache_store_written), cache_path_value


def load_repo_glossary_from_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_terms: int,
    schema_version: str,
    is_glossary_token: Callable[[str], bool],
) -> list[str] | None:
    if not cache_path.exists() or not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("schema_version") or "") != schema_version:
        return None
    if str(payload.get("docs_fingerprint") or "") != str(docs_fingerprint):
        return None
    if int(payload.get("max_terms", -1) or -1) != int(max_terms):
        return None
    glossary_raw = payload.get("glossary")
    if not isinstance(glossary_raw, list):
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for item in glossary_raw:
        token = str(item or "").strip().lower()
        if not is_glossary_token(token) or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
        if len(normalized) >= int(max_terms):
            break
    return normalized


def store_repo_glossary_to_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_terms: int,
    glossary: list[str],
    schema_version: str,
    is_glossary_token: Callable[[str], bool],
) -> bool:
    payload = {
        "schema_version": schema_version,
        "docs_fingerprint": str(docs_fingerprint or ""),
        "max_terms": int(max_terms),
        "glossary": [
            normalized
            for token in glossary
            for normalized in [str(token or "").strip().lower()]
            if is_glossary_token(normalized)
        ],
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def load_sections_from_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_files: int,
    max_section_chars: int,
    schema_version: str,
    normalize_cached_section: Callable[[dict[str, Any]], Section | None],
) -> list[Section] | None:
    if not cache_path.exists() or not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("schema_version") or "") != schema_version:
        return None
    if str(payload.get("docs_fingerprint") or "") != str(docs_fingerprint):
        return None
    if int(payload.get("max_files", -1) or -1) != int(max_files):
        return None
    if int(payload.get("max_section_chars", -1) or -1) != int(max_section_chars):
        return None

    sections_raw = payload.get("sections")
    if not isinstance(sections_raw, list):
        return None

    sections: list[Section] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            continue
        normalized = normalize_cached_section(item)
        if normalized is None:
            continue
        sections.append(normalized)
    return sections


def store_sections_to_disk_cache(
    *,
    cache_path: Path,
    docs_fingerprint: str,
    max_files: int,
    max_section_chars: int,
    sections: list[Section],
    schema_version: str,
    serialize_section_for_cache: Callable[[Section], dict[str, Any]],
) -> bool:
    payload = {
        "schema_version": schema_version,
        "docs_fingerprint": str(docs_fingerprint or ""),
        "max_files": int(max_files),
        "max_section_chars": int(max_section_chars),
        "sections": [
            serialize_section_for_cache(item)
            for item in sections
            if isinstance(item, dict)
        ],
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False
