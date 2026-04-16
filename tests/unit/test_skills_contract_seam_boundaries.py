from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cli_and_mcp_use_shared_skills_catalog_contract_seam() -> None:
    cli_text = (REPO_ROOT / "src" / "ace_lite" / "cli_app" / "commands" / "skills.py").read_text(
        encoding="utf-8"
    )
    mcp_text = (REPO_ROOT / "src" / "ace_lite" / "mcp_server" / "service.py").read_text(
        encoding="utf-8"
    )

    assert "from ace_lite.skills_contract import build_skills_catalog_contract" in cli_text
    assert "build_skills_catalog_contract(" in cli_text
    assert "from ace_lite.skills_contract import build_skills_catalog_contract" in mcp_text
    assert "build_skills_catalog_contract(root_path=root_path, skills_path=skills_path)" in mcp_text

    forbidden_cli_tokens = (
        "build_skill_manifest(",
        "build_skill_catalog(manifest)",
    )
    for token in forbidden_cli_tokens:
        assert token not in cli_text
