from __future__ import annotations

from click.testing import CliRunner

from ace_lite.cli_app.app import cli


def test_cli_skills_catalog_renders_manifest_markdown(tmp_path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "sample-skill.md").write_text(
        "\n".join(
            [
                "---",
                "name: sample-skill",
                "description: Sample skill for catalog testing.",
                "intents: [research]",
                "modules: [docs]",
                "topics: [catalog]",
                "default_sections: [Workflow]",
                "token_estimate: 123",
                "---",
                "# Workflow",
                "Use this skill when testing catalog output.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["skills", "catalog", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "# ACE-Lite Skill Catalog" in result.output
    assert "## sample-skill" in result.output
    assert "`" + str((skills_dir / "sample-skill.md").resolve()) + "`" in result.output


def test_cli_skills_catalog_handles_missing_directory(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["skills", "catalog", "--root", str(tmp_path), "--skills-dir", "missing-skills"],
    )

    assert result.exit_code == 0
    assert "# ACE-Lite Skill Catalog" in result.output
    assert "_No skills discovered._" in result.output
