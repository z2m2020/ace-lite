from __future__ import annotations

from click.testing import CliRunner

from ace_lite.cli import cli


def test_plan_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["plan", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/PLAN_GUIDE.md" in result.output
    assert "docs/guides/RETRIEVAL_PROFILES.md" in result.output


def test_plan_quick_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["plan-quick", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/PLAN_QUICK.md" in result.output


def test_index_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["index", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/INDEXING.md" in result.output


def test_doctor_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["doctor", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/DIAGNOSTICS.md" in result.output


def test_repomap_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["repomap", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/REPOMAP.md" in result.output


def test_benchmark_run_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["benchmark", "run", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/BENCHMARK.md" in result.output


def test_demo_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["demo", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/DEMO.md" in result.output


def test_memory_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["memory", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/MEMORY.md" in result.output


def test_feedback_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["feedback", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/FEEDBACK.md" in result.output


def test_profile_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["profile", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/PROFILE.md" in result.output


def test_workspace_help_includes_docs_links() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["workspace", "--help"])

    assert result.exit_code == 0
    assert "See also:" in result.output
    assert "docs/guides/GETTING_STARTED.md" in result.output
    assert "docs/guides/WORKSPACE.md" in result.output
