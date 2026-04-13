from __future__ import annotations

import re
from dataclasses import dataclass

from ace_lite.parsers.base import ImportEntry, ReferenceEntry, SymbolEntry

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_INLINE_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_REF_LINK_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)\s*$")


@dataclass(frozen=True, slots=True)
class _Heading:
    level: int
    title: str
    lineno: int
    heading_path: str


def _normalize_heading_title(text: str) -> str:
    normalized = str(text or "").replace("\t", " ").strip()
    normalized = " ".join(normalized.split())
    return normalized


def _normalize_link_target(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    # Drop optional title part: (./a.md "title")
    text = text.split()[0].strip()
    if text.startswith("<") and text.endswith(">") and len(text) >= 3:
        text = text[1:-1].strip()
    # Common markdown link noise.
    text = text.strip().strip('"').strip("'")
    return text


def parse_markdown(
    *,
    source_text: str,
    relative_path: str,
) -> tuple[list[SymbolEntry], list[ImportEntry], list[ReferenceEntry]]:
    """Parse a Markdown document into a lightweight, deterministic symbol model.

    This parser is dependency-free and intentionally conservative:
    - Extracts headings as hierarchical `section` symbols.
    - Extracts inline and reference-style link targets as `doc_link` references.
    - Skips headings/links inside fenced code blocks.
    """

    lines = str(source_text or "").splitlines()
    total_lines = max(1, len(lines))

    headings: list[_Heading] = []
    references: list[ReferenceEntry] = []
    stack: list[tuple[int, str]] = []
    in_fence = False
    fence_marker = ""

    for idx, raw_line in enumerate(lines, start=1):
        line = str(raw_line or "")

        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue

        if in_fence:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = _normalize_heading_title(heading_match.group(2))
            if title:
                while stack and int(stack[-1][0]) >= int(level):
                    stack.pop()
                stack.append((level, title))
                heading_path = "/".join(item[1] for item in stack if item[1])
                headings.append(
                    _Heading(
                        level=int(level),
                        title=title,
                        lineno=int(idx),
                        heading_path=heading_path,
                    )
                )
            continue

        for match in _INLINE_LINK_RE.finditer(line):
            target = _normalize_link_target(match.group(1))
            if not target:
                continue
            references.append(
                ReferenceEntry(
                    name=target,
                    qualified_name=None,
                    lineno=int(idx),
                    kind="doc_link",
                )
            )

        ref_def = _REF_LINK_DEF_RE.match(line)
        if ref_def:
            target = _normalize_link_target(ref_def.group(1))
            if target:
                references.append(
                    ReferenceEntry(
                        name=target,
                        qualified_name=None,
                        lineno=int(idx),
                        kind="doc_link",
                    )
                )

    symbols: list[SymbolEntry] = []
    if not headings:
        symbols.append(
            SymbolEntry(
                name="Document",
                qualified_name=f"{relative_path}#Document",
                kind="section",
                lineno=1,
                end_lineno=int(total_lines),
            )
        )
        return symbols, [], references

    for i, heading in enumerate(headings):
        end_lineno = int(total_lines)
        for nxt in headings[i + 1 :]:
            if int(nxt.level) <= int(heading.level):
                end_lineno = max(int(heading.lineno), int(nxt.lineno) - 1)
                break

        heading_key = heading.heading_path or heading.title
        qualified = f"{relative_path}#{heading_key}"
        if len(qualified) > 240:
            qualified = qualified[:240]
        symbols.append(
            SymbolEntry(
                name=str(heading.title),
                qualified_name=qualified,
                kind="section",
                lineno=int(heading.lineno),
                end_lineno=int(end_lineno),
            )
        )

    # No imports for markdown.
    imports: list[ImportEntry] = []
    return symbols, imports, references


__all__ = ["parse_markdown"]
