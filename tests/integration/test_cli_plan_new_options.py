"""Integration tests for plan command new options (--quick, --dry-run)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ace_lite.cli_app.app import cli


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repository structure."""
    # Create a minimal git repo
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Create minimal index.json
    context_map = tmp_path / "context-map"
    context_map.mkdir()

    index_file = context_map / "index.json"
    index_file.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "src/main.py",
                        "language": "python",
                        "symbols": [{"name": "main", "kind": "function"}],
                    }
                ]
            }
        )
    )

    return tmp_path


class TestPlanQuickCommand:
    """Tests for plan-quick command."""

    def test_plan_quick_help(self, cli_runner):
        """Test plan-quick command help output."""
        result = cli_runner.invoke(cli, ["plan-quick", "--help"])
        assert result.exit_code == 0
        assert "plan-quick" in result.output.lower()
        assert "--query" in result.output
        assert "--top-k" in result.output

    def test_plan_quick_missing_query(self, cli_runner, sample_repo):
        """Test plan-quick fails without --query."""
        result = cli_runner.invoke(cli, ["plan-quick", "--root", str(sample_repo)])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

    def test_plan_quick_invalid_top_k(self, cli_runner, sample_repo):
        """Test plan-quick rejects invalid --top-k values."""
        result = cli_runner.invoke(
            cli, ["plan-quick", "--root", str(sample_repo), "--query=test", "--top-k", "0"]
        )
        assert result.exit_code != 0

    def test_plan_quick_invalid_top_k_too_high(self, cli_runner, sample_repo):
        """Test plan-quick rejects --top-k > 100."""
        result = cli_runner.invoke(
            cli, ["plan-quick", "--root", str(sample_repo), "--query=test", "--top-k", "200"]
        )
        assert result.exit_code != 0


class TestPlanDryRunCommand:
    """Tests for plan --dry-run option."""

    def test_plan_dry_run_help(self, cli_runner):
        """Test plan command help shows --dry-run option."""
        result = cli_runner.invoke(cli, ["plan", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_plan_dry_run_missing_query(self, cli_runner, sample_repo):
        """Test plan --dry-run fails without --query."""
        result = cli_runner.invoke(
            cli, ["plan", "--dry-run", "--root", str(sample_repo), "--repo=test"]
        )
        assert result.exit_code != 0

    def test_plan_dry_run_missing_repo(self, cli_runner, sample_repo):
        """Test plan --dry-run fails without --repo."""
        result = cli_runner.invoke(
            cli, ["plan", "--dry-run", "--root", str(sample_repo), "--query=test"]
        )
        assert result.exit_code != 0


class TestPlanQuickOption:
    """Tests for plan --quick option."""

    def test_plan_quick_help(self, cli_runner):
        """Test plan command help shows --quick option."""
        result = cli_runner.invoke(cli, ["plan", "--help"])
        assert result.exit_code == 0
        assert "--quick" in result.output

    def test_plan_quick_option_in_help(self, cli_runner):
        """Test plan --quick appears in help text."""
        result = cli_runner.invoke(cli, ["plan", "--help"])
        assert "skip memory/skill stages" in result.output.lower()
