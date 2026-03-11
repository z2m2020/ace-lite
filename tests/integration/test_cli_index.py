from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ace_lite.cli import cli


def _write_sample_repo(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")


def test_cli_index_outputs_json_summary(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    out_json = tmp_path / "context-map" / "index.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "index",
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
    summary = json.loads(result.output)
    assert summary["ok"] is True
    assert Path(summary["output"]).exists()
    assert isinstance(summary.get("file_count"), int)
    assert summary.get("indexing_resilience") is None
    assert isinstance(summary.get("index_cache"), dict)
    assert summary["index_cache"].get("cache_hit") is False


def test_cli_index_batch_mode_includes_resilience_stats(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    out_json = tmp_path / "context-map" / "index.batch.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "index",
            "--root",
            str(tmp_path),
            "--languages",
            "python",
            "--output",
            str(out_json),
            "--batch-mode",
            "--batch-size",
            "1",
            "--resume-state",
            "context-map/index.resume.test.json",
        ],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    assert result.exit_code == 0
    summary = json.loads(result.output)
    assert summary["ok"] is True
    assert Path(summary["output"]).exists()
    resilience = summary.get("indexing_resilience")
    assert isinstance(resilience, dict)
    assert resilience.get("enabled") is True
