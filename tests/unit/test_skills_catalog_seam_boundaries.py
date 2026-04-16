from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_skills_catalog_uses_render_support_seam() -> None:
    text = (REPO_ROOT / "src" / "ace_lite" / "skills.py").read_text(encoding="utf-8")

    assert "from ace_lite.skills_catalog import build_skill_catalog_markdown" in text
    assert "return build_skill_catalog_markdown(manifest)" in text
    forbidden_tokens = (
        '"# ACE-Lite Skill Catalog"',
        '"Discovered Markdown skills with routing metadata and default load surface."',
        'lines.extend(["", f"## {name}"])',
    )
    for token in forbidden_tokens:
        assert token not in text
