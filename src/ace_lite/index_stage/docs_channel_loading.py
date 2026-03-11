"""Loading and cache-shaping helpers for docs-channel sections."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path, PurePath
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def normalize_token_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, count in value.items():
        token = str(key or "").strip().lower()
        if len(token) < 2:
            continue
        try:
            parsed = int(count or 0)
        except (TypeError, ValueError):
            continue
        if parsed <= 0:
            continue
        normalized[token] = parsed
    return normalized


def collect_docs_paths(*, root: Path, max_files: int) -> list[Path]:
    collected: list[Path] = []
    docs_root = root / "docs"
    if docs_root.exists():
        for path in sorted(docs_root.rglob("*.md")):
            if path.is_file():
                collected.append(path)
                if len(collected) >= max_files:
                    return collected

    for candidate in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md", "SECURITY.md"):
        path = root / candidate
        if path.exists() and path.is_file() and path not in collected:
            collected.append(path)
            if len(collected) >= max_files:
                break

    return collected


def docs_fingerprint(*, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        digest.update(path.as_posix().encode("utf-8", "ignore"))
        digest.update(str(int(stat.st_mtime_ns)).encode("utf-8", "ignore"))
        digest.update(str(int(stat.st_size)).encode("utf-8", "ignore"))
        digest.update(b"|")
    return digest.hexdigest()


def parse_markdown_sections(
    *,
    path: str,
    text: str,
    max_section_chars: int,
) -> list[dict[str, Any]]:
    lines = str(text or "").splitlines()
    if not lines:
        return []

    sections: list[dict[str, Any]] = []
    heading_stack: list[tuple[int, str]] = []

    current_heading = PurePath(path).name
    current_heading_path = current_heading
    current_start = 1
    current_body: list[str] = []

    def flush(end_line: int) -> None:
        nonlocal current_body
        body = "\n".join(current_body).strip()
        if len(body) > max_section_chars:
            body = body[: max_section_chars].rstrip()
        heading = str(current_heading or PurePath(path).name).strip()
        if not heading:
            heading = PurePath(path).name
        heading_path = str(current_heading_path or heading).strip()
        if not heading_path:
            heading_path = heading
        sections.append(
            build_section_payload(
                path=path,
                heading=heading,
                heading_path=heading_path,
                body=body,
                line_start=max(1, int(current_start)),
                line_end=max(int(current_start), int(end_line)),
            )
        )
        current_body = []

    for lineno, raw_line in enumerate(lines, start=1):
        line = str(raw_line or "")
        match = _HEADING_RE.match(line)
        if not match:
            current_body.append(line)
            continue

        if lineno > current_start or current_body:
            flush(lineno - 1)

        level = len(match.group(1))
        heading_text = str(match.group(2) or "").strip()
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, heading_text))

        current_heading = heading_text or current_heading
        current_heading_path = (
            " > ".join(item[1] for item in heading_stack if item[1]) or current_heading
        )
        current_start = lineno
        current_body = []

    flush(len(lines))
    return sections


def build_section_payload(
    *,
    path: str,
    heading: str,
    heading_path: str,
    body: str,
    line_start: int,
    line_end: int,
) -> dict[str, Any]:
    heading_tokens = token_counts(heading)
    heading_path_tokens = token_counts(heading_path)
    body_tokens = token_counts(body)

    weighted_len = (
        sum(heading_tokens.values()) * 3
        + sum(heading_path_tokens.values()) * 2
        + sum(body_tokens.values())
    )
    return {
        "path": path,
        "heading": heading,
        "heading_path": heading_path,
        "body": body,
        "line_start": max(1, int(line_start)),
        "line_end": max(int(line_start), int(line_end)),
        "heading_tokens": heading_tokens,
        "heading_path_tokens": heading_path_tokens,
        "body_tokens": body_tokens,
        "weighted_len": max(1, int(weighted_len)),
    }


def serialize_section_for_cache(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(section.get("path", "")),
        "heading": str(section.get("heading", "")),
        "heading_path": str(section.get("heading_path", "")),
        "body": str(section.get("body", "")),
        "line_start": max(1, int(section.get("line_start", 1) or 1)),
        "line_end": max(1, int(section.get("line_end", 1) or 1)),
        "heading_tokens": dict(section.get("heading_tokens", {})),
        "heading_path_tokens": dict(section.get("heading_path_tokens", {})),
        "body_tokens": dict(section.get("body_tokens", {})),
        "weighted_len": max(1, int(section.get("weighted_len", 1) or 1)),
    }


def normalize_cached_section(item: dict[str, Any]) -> dict[str, Any] | None:
    path = str(item.get("path", "")).strip()
    heading = str(item.get("heading", "")).strip()
    heading_path = str(item.get("heading_path", "")).strip()
    if not path:
        return None
    if not heading:
        heading = PurePath(path).name
    if not heading_path:
        heading_path = heading

    heading_tokens = normalize_token_mapping(item.get("heading_tokens"))
    heading_path_tokens = normalize_token_mapping(item.get("heading_path_tokens"))
    body_tokens = normalize_token_mapping(item.get("body_tokens"))
    weighted_len = max(1, int(item.get("weighted_len", 1) or 1))
    line_start = max(1, int(item.get("line_start", 1) or 1))
    line_end = max(line_start, int(item.get("line_end", line_start) or line_start))

    return {
        "path": path,
        "heading": heading,
        "heading_path": heading_path,
        "body": str(item.get("body", "")),
        "line_start": line_start,
        "line_end": line_end,
        "heading_tokens": Counter(heading_tokens),
        "heading_path_tokens": Counter(heading_path_tokens),
        "body_tokens": Counter(body_tokens),
        "weighted_len": weighted_len,
    }


def token_counts(text: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for token in _TOKEN_RE.findall(str(text or "").lower()):
        if len(token) < 2:
            continue
        counter[token] += 1
    return counter


__all__ = [
    "build_section_payload",
    "collect_docs_paths",
    "docs_fingerprint",
    "normalize_cached_section",
    "normalize_token_mapping",
    "parse_markdown_sections",
    "serialize_section_for_cache",
    "token_counts",
]
