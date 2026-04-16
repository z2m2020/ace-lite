"""Stable cross-interface contract helpers for skill discovery surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.skills import build_skill_catalog, build_skill_manifest


def build_skills_catalog_contract(*, root_path: Path, skills_path: Path) -> dict[str, Any]:
    manifest = build_skill_manifest(skills_path)
    return {
        "ok": True,
        "root": str(root_path.resolve()),
        "skills_dir": str(skills_path.resolve()),
        "skill_count": len(manifest),
        "markdown": build_skill_catalog(manifest),
    }


__all__ = ["build_skills_catalog_contract"]
