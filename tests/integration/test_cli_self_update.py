from __future__ import annotations

import json

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.cli_app.commands import self_update as self_update_command_module


def test_cli_self_update_check_emits_planned_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        self_update_command_module.self_update_support,
        "run_self_update",
        lambda **kwargs: {
            "ok": True,
            "event": "self_update_plan",
            "check_only": kwargs["check"],
            "install_mode": "installed_package",
            "commands": [{"display": "python -m pip install -U ace-lite-engine"}],
        },
    )

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["self-update", "--check"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["event"] == "self_update_plan"
    assert payload["check_only"] is True
    assert payload["commands"][0]["display"] == "python -m pip install -U ace-lite-engine"
