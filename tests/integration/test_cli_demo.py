from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ace_lite.cli import cli


def test_cli_demo_seeds_repo_and_runs_plan(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo-repo"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["demo", "--output", str(output_dir)],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert Path(payload["demo_root"]).exists()
    assert (output_dir / "app" / "shutdown" / "allowlist.py").exists()
    assert "plan" in payload
