from __future__ import annotations

from pathlib import Path

from ace_lite.skills import build_skill_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_skills_guide_lists_catalog_commands_and_all_repo_skills() -> None:
    guide_path = REPO_ROOT / "docs" / "guides" / "SKILLS.md"
    guide_text = guide_path.read_text(encoding="utf-8")

    assert "ace-lite skills catalog --root . --skills-dir skills" in guide_text
    assert "PYTHONPATH=src python3 -m ace_lite.cli skills catalog --root . --skills-dir skills" in guide_text
    assert "## Which Skill First" in guide_text
    assert "## Typical Combinations" in guide_text

    manifest = build_skill_manifest(REPO_ROOT / "skills")
    assert manifest
    for entry in manifest:
        skill_name = str(entry["name"])
        assert skill_name in guide_text, f"skills guide is missing routing guidance for {skill_name}"
