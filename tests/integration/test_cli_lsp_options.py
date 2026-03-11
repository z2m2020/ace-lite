from __future__ import annotations

import click
import pytest

from ace_lite.cli import parse_lsp_command_options, parse_lsp_commands_from_config


def test_parse_lsp_command_options() -> None:
    mapping = parse_lsp_command_options(("python=pyright --outputjson", "go=gopls check"))

    assert mapping["python"] == ["pyright", "--outputjson"]
    assert mapping["go"] == ["gopls", "check"]


def test_parse_lsp_command_options_invalid() -> None:
    with pytest.raises(click.BadParameter):
        parse_lsp_command_options(("python",))


def test_parse_lsp_commands_from_config_mapping() -> None:
    mapping = parse_lsp_commands_from_config(
        {
            "python": "pyright --outputjson",
            "go": ["gopls", "check"],
        }
    )

    assert mapping["python"] == ["pyright", "--outputjson"]
    assert mapping["go"] == ["gopls", "check"]
