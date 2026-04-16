"""Skill catalog rendering helpers."""

from __future__ import annotations

from typing import Any

from ace_lite.utils import to_int, to_lower_list, to_string_list


def build_skill_catalog_markdown(manifest: list[dict[str, Any]]) -> str:
    """Render a human-facing markdown catalog from manifest metadata only."""

    lines = [
        "# ACE-Lite Skill Catalog",
        "",
        "Discovered Markdown skills with routing metadata and default load surface.",
    ]
    if not manifest:
        return "\n".join([*lines, "", "_No skills discovered._", ""])

    for entry in manifest:
        name = str(entry.get("name") or "").strip() or "unnamed-skill"
        path = str(entry.get("path") or "").strip()
        description = str(entry.get("description") or "").strip()
        intents = to_lower_list(entry.get("intents") or [])
        modules = to_lower_list(entry.get("modules") or [])
        topics = to_lower_list(entry.get("topics") or [])
        default_sections = to_string_list(entry.get("default_sections") or [])
        priority = to_int(entry.get("priority"), default=0)
        token_estimate = to_int(entry.get("token_estimate"), default=0)
        normalized_token_estimate = int(token_estimate or 0)

        lines.extend(["", f"## {name}"])
        if path:
            lines.append(f"- **Path:** `{path}`")
        if description:
            lines.append(f"- **Description:** {description}")
        if intents:
            lines.append(f"- **Intents:** {', '.join(intents)}")
        if modules:
            lines.append(f"- **Modules:** {', '.join(modules)}")
        if topics:
            lines.append(f"- **Topics:** {', '.join(topics)}")
        if default_sections:
            lines.append(f"- **Default sections:** {', '.join(default_sections)}")
        lines.append(f"- **Priority:** {priority}")
        if normalized_token_estimate > 0:
            lines.append(f"- **Token estimate:** {normalized_token_estimate}")

    lines.append("")
    return "\n".join(lines)


__all__ = ["build_skill_catalog_markdown"]
