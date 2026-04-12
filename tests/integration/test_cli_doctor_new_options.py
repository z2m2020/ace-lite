"""Integration tests for doctor command new options (--fast, --output-format)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from ace_lite.cli_app.app import cli


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestDoctorNewOptions:
    """Tests for doctor command new options."""

    def test_doctor_help_shows_fast_option(self, cli_runner):
        """Test doctor --help shows --fast option."""
        result = cli_runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "--fast" in result.output
        assert "--no-fast" in result.output

    def test_doctor_help_shows_output_format_option(self, cli_runner):
        """Test doctor --help shows --output-format option."""
        result = cli_runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "--output-format" in result.output
        assert "[json|table]" in result.output

    def test_doctor_fast_option_in_help_text(self, cli_runner):
        """Test --fast option description in help."""
        result = cli_runner.invoke(cli, ["doctor", "--help"])
        assert "Fast mode" in result.output
        # Check for probe-related text (case insensitive)
        assert "self-test" in result.output.lower() or "probe" in result.output.lower()

    def test_doctor_output_format_in_help_text(self, cli_runner):
        """Test --output-format option description in help."""
        result = cli_runner.invoke(cli, ["doctor", "--help"])
        assert "Output format" in result.output
        assert "json" in result.output.lower()
        assert "table" in result.output.lower()

    def test_doctor_invalid_output_format(self, cli_runner):
        """Test doctor rejects invalid --output-format value."""
        result = cli_runner.invoke(
            cli, ["doctor", "--root=.", "--output-format", "invalid"]
        )
        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_doctor_valid_output_format_json(self, cli_runner):
        """Test doctor accepts --output-format=json (even if checks fail)."""
        # This should accept the option even if the actual check might fail
        result = cli_runner.invoke(
            cli, ["doctor", "--root=.", "--output-format", "json"]
        )
        # Exit code might be non-zero due to actual checks, but option parsing should succeed
        # We're testing that the option is accepted
        assert "--output-format" in str(result.exception) or result.exit_code in [0, 1]

    def test_doctor_valid_output_format_table(self, cli_runner):
        """Test doctor accepts --output-format=table."""
        # This should accept the option even if the actual check might fail
        result = cli_runner.invoke(
            cli, ["doctor", "--root=.", "--output-format", "table"]
        )
        # Exit code might be non-zero due to actual checks, but option parsing should succeed
        assert "--output-format" in str(result.exception) or result.exit_code in [0, 1]

    def test_doctor_output_format_case_insensitive(self, cli_runner):
        """Test --output-format is case insensitive."""
        result_lower = cli_runner.invoke(
            cli, ["doctor", "--root=.", "--output-format", "TABLE"]
        )
        # Should accept case-insensitive value
        assert "--output-format" in str(result_lower.exception) or result_lower.exit_code in [
            0,
            1,
        ]


class TestDoctorExamples:
    """Tests for doctor command examples in help."""

    def test_doctor_help_shows_command_name(self, cli_runner):
        """Test doctor help shows command name."""
        result = cli_runner.invoke(cli, ["doctor", "--help"])
        # Should show the command in usage
        assert "doctor" in result.output.lower()

    def test_doctor_help_shows_fast_option(self, cli_runner):
        """Test doctor help shows --fast option."""
        result = cli_runner.invoke(cli, ["doctor", "--help"])
        # The help should show --fast option
        assert "--fast" in result.output
