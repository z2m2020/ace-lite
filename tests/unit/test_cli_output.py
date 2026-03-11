from __future__ import annotations

from typing import Any

import click
import pytest

from ace_lite.cli_app.output import echo_json


def test_echo_json_falls_back_to_ascii(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_echo(message: str, **kwargs: Any) -> None:
        calls.append(str(message))
        if len(calls) == 1:
            raise UnicodeEncodeError("gbk", "\ufeff", 0, 1, "illegal multibyte")

    monkeypatch.setattr(click, "echo", fake_echo)

    echo_json({"marker": "\ufeff"})

    assert len(calls) == 2
    assert "\ufeff" in calls[0]
    assert "\\ufeff" in calls[1]


def test_echo_json_no_fallback_when_stdout_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_echo(message: str, **kwargs: Any) -> None:
        calls.append(str(message))

    monkeypatch.setattr(click, "echo", fake_echo)

    echo_json({"ok": True})

    assert calls
    assert len(calls) == 1

