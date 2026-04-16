"""Skill manifest discovery and section loading.

Skills are markdown documents with YAML frontmatter. This module loads skill
metadata, scores skills against a query context, and extracts relevant sections
by heading.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ace_lite.skills_catalog import build_skill_catalog_markdown
from ace_lite.token_estimator import estimate_tokens
from ace_lite.utils import to_int, to_lower_list, to_string_list

_ERROR_KEYWORD_BLOCKLIST = {
    "benchmark",
    "cleanup",
    "context",
    "freeze",
    "handoff",
    "implement",
    "plan",
    "planning",
    "refactor",
    "release",
    "rename",
    "review",
    "scope",
}

_SUSPICIOUS_METADATA_CODEPOINTS = {
    0x59AB,
    0x59E3,
    0x5A34,
    0x6D60,
    0x6FB6,
    0x7035,
    0x934A,
    0x9352,
    0x935A,
    0x9363,
    0x9365,
    0x93B7,
    0x93CB,
    0x940F,
    0x95C1,
}
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", flags=re.MULTILINE)


def build_skill_manifest(skills_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(skills_dir)
    if not root.exists() or not root.is_dir():
        return []

    manifest: list[dict[str, Any]] = []
    for skill_file in sorted(root.rglob("*.md")):
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        metadata, body = _split_frontmatter(text)
        default_sections = to_string_list(
            metadata.get("default_sections") or metadata.get("sections")
        )
        token_estimate = to_int(metadata.get("token_estimate"), default=None)
        needs_body_scan = token_estimate is None or not default_sections
        # Record which frontmatter fields are missing BEFORE backfill so that
        # lint_skill_manifest() can report accurate issues.
        missing_frontmatter: list[str] = []
        if token_estimate is None:
            missing_frontmatter.append("token_estimate")
        if not default_sections:
            missing_frontmatter.append("default_sections")
        declared_frontmatter_keys = {str(key).strip() for key in metadata}
        if not declared_frontmatter_keys.intersection({"error_keywords", "errors", "triggers"}):
            missing_frontmatter.append("error_keywords")
        headings = _extract_headings(body) if needs_body_scan else []
        if token_estimate is None:
            token_estimate = _estimate_skill_token_estimate(
                markdown_body=body,
                default_sections=default_sections,
            )
        entry = {
            "name": str(metadata.get("name") or skill_file.stem),
            "path": str(skill_file.resolve()),
            "description": str(metadata.get("description") or ""),
            "intents": to_lower_list(metadata.get("intents") or metadata.get("intent")),
            "modules": to_lower_list(metadata.get("modules") or metadata.get("module")),
            "error_keywords": to_lower_list(
                metadata.get("error_keywords") or metadata.get("errors") or metadata.get("triggers")
            ),
            "topics": to_lower_list(metadata.get("topics")),
            "default_sections": default_sections,
            "priority": to_int(metadata.get("priority"), default=0),
            "token_estimate": token_estimate,
            "headings": headings,
            "manifest_load_mode": "body_scan" if needs_body_scan else "metadata_only",
            "_missing_frontmatter": missing_frontmatter,
            "_declared_frontmatter_keys": sorted(declared_frontmatter_keys),
        }
        manifest.append(entry)

    manifest.sort(key=lambda item: (-int(item.get("priority") or 0), item.get("name", "")))
    return manifest


def select_skills(
    query_ctx: dict[str, Any],
    manifest: list[dict[str, Any]],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    intent = str(query_ctx.get("intent") or "").lower().strip()
    module = str(query_ctx.get("module") or "").lower().strip()
    query_text = str(query_ctx.get("query") or "").lower()
    query_keyword_text = _normalize_keyword_phrase(query_text)
    query_tokens = _tokenize(query_text)
    query_token_set = set(query_tokens)
    error_keywords = to_lower_list(query_ctx.get("error_keywords") or [])

    scored: list[dict[str, Any]] = []
    for entry in manifest:
        score = 0
        matched: list[str] = []
        signal_count = 0

        intents = to_lower_list(entry.get("intents") or [])
        modules = to_lower_list(entry.get("modules") or [])
        errors = to_lower_list(entry.get("error_keywords") or [])
        topics = to_lower_list(entry.get("topics") or [])
        module_terms = _expand_terms(modules)
        topic_terms = _expand_terms(topics)
        name_tokens = _tokenize(str(entry.get("name") or "").replace("-", " "))
        description_tokens = _tokenize(str(entry.get("description") or ""))

        if intent and any(intent == item for item in intents):
            score += 3
            matched.append(f"intent:{intent}")

        if module and _matches_module_hint(module, modules):
            score += 2
            matched.append(f"module:{module}")
            signal_count += 1

        matched_errors = {
            _normalize_keyword_phrase(keyword)
            for keyword in error_keywords
            if keyword and any(_matches_error_keyword(keyword, item) for item in errors)
        }
        matched_errors.update(
            _normalize_keyword_phrase(item)
            for item in errors
            if item and _query_mentions_keyword(query_keyword_text, item)
        )
        for keyword in sorted(item for item in matched_errors if item):
            score += 4
            matched.append(f"error:{keyword}")
            signal_count += 1

        query_module_hits = sum(1 for token in query_token_set if token in module_terms)
        if query_module_hits:
            score += min(query_module_hits, 2)
            matched.append(f"query_modules:{query_module_hits}")
            signal_count += 1

        module_phrase_hits = _count_phrase_matches(query_keyword_text, modules)
        if module_phrase_hits:
            score += min(module_phrase_hits, 2)
            matched.append(f"query_module_phrases:{module_phrase_hits}")
            signal_count += 1

        topic_hits = sum(1 for token in query_token_set if token in topic_terms)
        if topic_hits:
            score += min(topic_hits, 3)
            matched.append(f"query_topics:{topic_hits}")
            signal_count += 1

        topic_phrase_hits = _count_phrase_matches(query_keyword_text, topics)
        if topic_phrase_hits:
            score += min(topic_phrase_hits, 3)
            matched.append(f"query_topic_phrases:{topic_phrase_hits}")
            signal_count += 1

        name_hits = sum(1 for token in query_token_set if token in name_tokens)
        if name_hits:
            score += min(name_hits, 2)
            matched.append(f"name_tokens:{name_hits}")
            signal_count += 1

        description_hits = sum(1 for token in query_token_set if token in description_tokens)
        if description_hits >= 2:
            score += min(description_hits, 2)
            matched.append(f"description_tokens:{description_hits}")
            signal_count += 1

        if signal_count > 0:
            ranked = dict(entry)
            ranked["score"] = score
            ranked["matched"] = matched
            ranked["matched_count"] = len(set(matched))
            ranked["signal_count"] = signal_count
            scored.append(ranked)

    scored.sort(
        key=lambda item: (
            -int(item.get("score") or 0),
            -int(item.get("matched_count") or 0),
            -int(item.get("priority") or 0),
            int(item.get("token_estimate") or 10**9),
            item.get("name", ""),
        )
    )
    return scored[: max(top_n, 0)]


def lint_skill_manifest(manifest: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues = _lint_manifest_duplicates(manifest)
    for entry in manifest:
        issues.extend(_lint_skill_entry(entry))
    return issues


def _lint_manifest_duplicates(manifest: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen_names: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    for entry in manifest:
        name = str(entry.get("name") or "").strip()
        path = str(entry.get("path") or "").strip()
        if name:
            existing_path = seen_names.get(name)
            if existing_path is not None:
                issues.append(
                    {
                        "name": name,
                        "path": path,
                        "field": "name",
                        "keyword": name,
                        "message": (
                            "skill manifest name must be unique; "
                            f"duplicate detected with {existing_path or '(unknown path)'}"
                        ),
                    }
                )
            else:
                seen_names[name] = path
        if path:
            existing_name = seen_paths.get(path)
            if existing_name is not None:
                issues.append(
                    {
                        "name": name or "(unknown)",
                        "path": path,
                        "field": "path",
                        "keyword": path,
                        "message": (
                            "skill manifest path must be unique; "
                            f"duplicate detected with {existing_name or '(unknown name)'}"
                        ),
                    }
                )
            else:
                seen_paths[path] = name
    return issues


def load_sections(
    skill_path: str | Path, headings: list[str] | tuple[str, ...] | None = None
) -> dict[str, str]:
    path = Path(skill_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="replace")
    _, body = _split_frontmatter(text)
    if not headings:
        sections = _extract_sections(body)
        if not sections:
            plain = body.strip()
            return {"Document": plain} if plain else {}
        return sections

    return _extract_selected_sections(markdown_body=body, headings=headings)


def build_skill_catalog(manifest: list[dict[str, Any]]) -> str:
    return build_skill_catalog_markdown(manifest)


def _split_frontmatter(markdown_text: str) -> tuple[dict[str, Any], str]:
    markdown_text = markdown_text.lstrip("\ufeff")
    if not markdown_text.startswith("---"):
        return {}, markdown_text

    lines = markdown_text.splitlines()
    if not lines:
        return {}, markdown_text

    if lines[0].strip() != "---":
        return {}, markdown_text

    end_index = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = idx
            break

    if end_index is None:
        return {}, markdown_text

    yaml_text = "\n".join(lines[1:end_index]).strip()
    body = "\n".join(lines[end_index + 1 :])
    if not yaml_text:
        return {}, body

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return {}, body

    return data if isinstance(data, dict) else {}, body


def _extract_headings(markdown_body: str) -> list[str]:
    return [match.group(2).strip() for match in _HEADING_PATTERN.finditer(markdown_body)]


def _extract_sections(markdown_body: str) -> dict[str, str]:
    matches = list(_HEADING_PATTERN.finditer(markdown_body))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_body)
        content = markdown_body[start:end].strip()
        sections[title] = content
    return sections


def _extract_selected_sections(
    *,
    markdown_body: str,
    headings: list[str] | tuple[str, ...],
) -> dict[str, str]:
    normalized_headings = [str(heading).strip() for heading in headings if str(heading).strip()]
    if not normalized_headings:
        return {}

    target_keys = {heading.lower() for heading in normalized_headings}
    matches = list(_HEADING_PATTERN.finditer(markdown_body))
    if not matches:
        return {}

    matched_sections: dict[str, tuple[str, str]] = {}
    for idx, match in enumerate(matches):
        title = match.group(2).strip()
        normalized_title = title.lower()
        if normalized_title not in target_keys:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_body)
        matched_sections[normalized_title] = (title, markdown_body[start:end].strip())

    selected: dict[str, str] = {}
    for heading in normalized_headings:
        matched = matched_sections.get(heading.lower())
        if matched is None:
            continue
        title, content = matched
        selected[title] = content
    return selected


def _extract_first_sections(
    *,
    markdown_body: str,
    limit: int,
) -> dict[str, str]:
    matches = list(_HEADING_PATTERN.finditer(markdown_body))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for idx, match in enumerate(matches[: max(1, int(limit))]):
        title = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_body)
        sections[title] = markdown_body[start:end].strip()
    return sections


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9_]+", text.lower()) if len(token) >= 3]


def _estimate_skill_token_estimate(*, markdown_body: str, default_sections: list[str]) -> int:
    sections = (
        _extract_selected_sections(
            markdown_body=markdown_body,
            headings=default_sections,
        )
        if default_sections
        else _extract_first_sections(markdown_body=markdown_body, limit=2)
    )
    if sections:
        text = "\n\n".join(f"## {title}\n{content}".strip() for title, content in sections.items())
        return int(estimate_tokens(text))

    plain = markdown_body.strip()
    return int(estimate_tokens(plain)) if plain else 1


def _select_sections_by_heading(
    *, sections: dict[str, str], headings: list[str] | tuple[str, ...]
) -> dict[str, str]:
    lowered = {key.lower(): key for key in sections}
    selected: dict[str, str] = {}
    for heading in headings:
        key = lowered.get(str(heading).lower())
        if key:
            selected[key] = sections[key]
    return selected


def _expand_terms(values: list[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        lowered = str(value).lower().strip()
        if not lowered:
            continue
        terms.add(lowered)
        terms.update(_tokenize(lowered))
    return terms


def _matches_error_keyword(query_keyword: str, skill_keyword: str) -> bool:
    return _normalize_keyword_phrase(query_keyword) == _normalize_keyword_phrase(skill_keyword)


def _lint_routing_metadata_overlap(entry: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    name = str(entry.get("name") or "").strip() or "(unknown)"
    path = str(entry.get("path") or "").strip()
    intents = _collect_exact_terms(to_string_list(entry.get("intents") or []))
    modules = _collect_exact_terms(to_string_list(entry.get("modules") or []))
    overlap_terms = sorted(intents & modules)
    if len(overlap_terms) < 2:
        return issues
    for term in overlap_terms:
        issues.append(
            {
                "name": name,
                "path": path,
                "field": "routing_metadata",
                "keyword": term,
                "message": (
                    "routing metadata overlaps too much across intents/modules; "
                    f"term '{term}' appears in both fields and reduces discriminative power"
                ),
            }
        )
    return issues


def _lint_skill_entry(entry: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    error_keywords = _collect_exact_terms(entry.get("error_keywords") or [])
    overlap_terms = (
        _collect_exact_terms(entry.get("intents") or [])
        | _collect_exact_terms(entry.get("modules") or [])
        | _collect_exact_terms(entry.get("topics") or [])
    )
    name = str(entry.get("name") or "").strip() or "(unknown)"
    path = str(entry.get("path") or "").strip()

    # Frontmatter completeness: token_estimate and default_sections should be
    # declared explicitly so build_skill_manifest() never falls back to a
    # body-scan path.  We check _missing_frontmatter which is recorded BEFORE
    # build_skill_manifest() backfills computed values.
    missing = entry.get("_missing_frontmatter") or []
    for field_name in missing:
        issues.append(
            {
                "name": name,
                "path": path,
                "field": field_name,
                "keyword": "",
                "message": f"missing {field_name} in frontmatter; causes body-scan fallback",
            }
        )

    if not str(entry.get("description") or "").strip():
        issues.append(
            {
                "name": name,
                "path": path,
                "field": "description",
                "keyword": "",
                "message": (
                    "description must be a non-empty frontmatter field; "
                    "empty descriptions degrade metadata-only routing and catalog discoverability"
                ),
            }
        )

    metadata_fields = (
        ("name", [entry.get("name") or ""]),
        ("description", [entry.get("description") or ""]),
        ("intents", entry.get("intents") or []),
        ("modules", entry.get("modules") or []),
        ("topics", entry.get("topics") or []),
        ("error_keywords", entry.get("error_keywords") or []),
    )
    for field_name, values in metadata_fields:
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            if _looks_like_mojibake_metadata(text):
                issues.append(
                    {
                        "name": name,
                        "path": path,
                        "field": field_name,
                        "keyword": text,
                        "message": "suspicious mojibake-like metadata term; normalize to valid UTF-8 text",
                    }
                )

    for keyword in sorted(error_keywords):
        if keyword in _ERROR_KEYWORD_BLOCKLIST:
            issues.append(
                {
                    "name": name,
                    "path": path,
                    "field": "error_keywords",
                    "keyword": keyword,
                    "message": "workflow labels belong in intents/topics, not error_keywords",
                }
            )
        if keyword in overlap_terms:
            issues.append(
                {
                    "name": name,
                    "path": path,
                    "field": "error_keywords",
                    "keyword": keyword,
                    "message": "do not duplicate the same term across error_keywords and intents/modules/topics",
                }
            )
    issues.extend(_lint_routing_metadata_overlap(entry))
    issues.extend(_lint_default_sections(entry))
    issues.extend(_lint_token_estimate(entry))
    return issues


def _lint_default_sections(entry: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    name = str(entry.get("name") or "").strip() or "(unknown)"
    path = str(entry.get("path") or "").strip()
    default_sections = [
        str(item).strip() for item in (entry.get("default_sections") or []) if str(item).strip()
    ]
    if not path or not default_sections:
        return issues

    markdown_body = _read_skill_body(path)
    if not markdown_body:
        return issues

    headings = {heading.lower() for heading in _extract_headings(markdown_body)}
    for section_name in default_sections:
        if section_name.lower() not in headings:
            issues.append(
                {
                    "name": name,
                    "path": path,
                    "field": "default_sections",
                    "keyword": section_name,
                    "message": "default_sections references a heading that does not exist in the markdown body",
                }
            )
    return issues


def _lint_token_estimate(entry: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if "token_estimate" in (entry.get("_missing_frontmatter") or []):
        return issues

    name = str(entry.get("name") or "").strip() or "(unknown)"
    path = str(entry.get("path") or "").strip()
    if not path:
        return issues

    markdown_body = _read_skill_body(path)
    if not markdown_body:
        return issues

    declared = to_int(entry.get("token_estimate"), default=None)
    if declared is None:
        return issues
    if declared <= 0:
        return [
            {
                "name": name,
                "path": path,
                "field": "token_estimate",
                "keyword": str(declared),
                "message": "token_estimate must be a positive integer",
            }
        ]

    estimated = _estimate_skill_token_estimate(
        markdown_body=markdown_body,
        default_sections=to_string_list(entry.get("default_sections") or []),
    )
    if estimated < 32:
        return issues

    lower_bound = max(8, estimated // 8)
    upper_bound = max(estimated * 8, 256)
    if declared < lower_bound or declared > upper_bound:
        issues.append(
            {
                "name": name,
                "path": path,
                "field": "token_estimate",
                "keyword": str(declared),
                "message": (
                    "token_estimate looks suspicious relative to the current markdown body; "
                    f"declared={declared}, estimated≈{estimated}"
                ),
            }
        )
        issues[-1]["message"] = (
            "token_estimate looks suspicious relative to the current markdown body; "
            f"declared={declared}, estimated={estimated}"
        )
    return issues


def _read_skill_body(path: str) -> str:
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return ""
    text = candidate.read_text(encoding="utf-8", errors="replace")
    _, body = _split_frontmatter(text)
    return body


def _looks_like_mojibake_metadata(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return any(ord(char) in _SUSPICIOUS_METADATA_CODEPOINTS for char in text)


def _matches_module_hint(module_hint: str, modules: list[str]) -> bool:
    normalized = str(module_hint).lower().strip()
    if not normalized:
        return False

    candidates = {normalized}
    candidates.update(token for token in re.split(r"[^a-z0-9_]+", normalized) if len(token) >= 3)
    for item in modules:
        lowered = str(item).lower().strip()
        if not lowered:
            continue
        for candidate in candidates:
            if candidate == lowered or candidate in lowered or lowered in candidate:
                return True
    return False


def _normalize_keyword_phrase(value: str) -> str:
    normalized = str(value).lower().strip()
    if not normalized:
        return ""
    normalized = re.sub(r"[\s_-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _collect_exact_terms(values: list[str] | tuple[str, ...]) -> set[str]:
    return {
        normalized
        for normalized in (
            _normalize_keyword_phrase(str(value)) for value in values if str(value).strip()
        )
        if normalized
    }


def _query_mentions_keyword(query_text: str, keyword: str) -> bool:
    normalized = _normalize_keyword_phrase(keyword)
    if not normalized:
        return False
    if normalized.isdigit():
        return normalized in query_text
    if re.fullmatch(r"[a-z0-9_]+", normalized):
        pattern = rf"(?<![a-z0-9_]){re.escape(normalized)}(?![a-z0-9_])"
        return re.search(pattern, query_text) is not None
    return normalized in query_text


def _count_phrase_matches(query_text: str, values: list[str] | tuple[str, ...]) -> int:
    matched = {
        normalized
        for normalized in (
            _normalize_keyword_phrase(str(value)) for value in values if str(value).strip()
        )
        if normalized
        and not re.fullmatch(r"[a-z0-9_]+", normalized)
        and _query_mentions_keyword(query_text, normalized)
    }
    return len(matched)


__all__ = [
    "build_skill_catalog",
    "build_skill_manifest",
    "lint_skill_manifest",
    "load_sections",
    "select_skills",
]
