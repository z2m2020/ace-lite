from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from ace_lite.cli import cli


def _load_last_json_line(output: str) -> dict[str, object]:
    lines = [line for line in output.splitlines() if line.strip()]
    return json.loads(lines[-1])


def _write_sample_repo(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")


def test_cli_plan_dry_run_progress_invokes_progress_helpers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_sample_repo(tmp_path)
    progress_calls: list[tuple[str, str]] = []

    import ace_lite.cli_app.commands.plan as plan_command

    fake_stderr = SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(plan_command, "sys", SimpleNamespace(stderr=fake_stderr))
    monkeypatch.setattr(
        plan_command,
        "echo_progress",
        lambda message: progress_calls.append(("progress", message)),
    )
    monkeypatch.setattr(
        plan_command,
        "echo_done",
        lambda message=None: progress_calls.append(("done", message or "")),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--dry-run",
            "--progress",
            "--root",
            str(tmp_path),
            "--repo",
            "demo",
            "--query",
            "test progress",
        ],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    assert result.exit_code == 0
    payload = _load_last_json_line(result.output)
    assert payload["ok"] is True
    assert payload["event"] == "plan_dry_run"
    assert ("done", "Dry run completed") in progress_calls


def test_cli_index_progress_invokes_progress_helpers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_sample_repo(tmp_path)
    out_json = tmp_path / "context-map" / "index.json"
    progress_calls: list[tuple[str, str]] = []

    import ace_lite.cli_app.commands.index as index_command

    fake_stderr = SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(index_command, "sys", SimpleNamespace(stderr=fake_stderr))
    monkeypatch.setattr(
        index_command,
        "echo_progress",
        lambda message: progress_calls.append(("progress", message)),
    )
    monkeypatch.setattr(
        index_command,
        "echo_done",
        lambda message=None: progress_calls.append(("done", message or "")),
    )
    monkeypatch.setattr(
        index_command,
        "clear_progress",
        lambda: progress_calls.append(("clear", "")),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "index",
            "--progress",
            "--root",
            str(tmp_path),
            "--languages",
            "python",
            "--output",
            str(out_json),
        ],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    assert result.exit_code == 0
    payload = _load_last_json_line(result.output)
    assert payload["ok"] is True
    assert Path(payload["output"]).exists()
    assert any(kind == "progress" for kind, _ in progress_calls)
    assert any(
        kind == "done" and message.startswith("Index built (")
        for kind, message in progress_calls
    )
