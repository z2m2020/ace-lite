from __future__ import annotations

from click.testing import CliRunner

from ace_lite.cli import cli
from ace_lite.version import get_version


def test_cli_version_option() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert get_version() in result.output

