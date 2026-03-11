from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ace_lite.cli import cli


def test_cli_repomap_build(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    out_json = tmp_path / "context-map" / "repo_map.json"
    out_md = tmp_path / "context-map" / "repo_map.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "repomap",
            "build",
            "--root",
            str(tmp_path),
            "--languages",
            "python",
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
            "--budget-tokens",
            "200",
            "--top-k",
            "10",
            "--ranking-profile",
            "graph",
        ],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    assert result.exit_code == 0
    outputs = json.loads(result.output)
    assert Path(outputs["repo_map_json"]).exists()
    assert Path(outputs["repo_map_md"]).exists()

    payload = json.loads(Path(outputs["repo_map_json"]).read_text(encoding="utf-8"))
    assert payload["ranking_profile"] == "graph"


def test_cli_repomap_build_accepts_graph_seeded_profile(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    out_json = tmp_path / "context-map" / "repo_map.seeded.json"
    out_md = tmp_path / "context-map" / "repo_map.seeded.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "repomap",
            "build",
            "--root",
            str(tmp_path),
            "--languages",
            "python",
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
            "--budget-tokens",
            "200",
            "--top-k",
            "10",
            "--ranking-profile",
            "graph_seeded",
        ],
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    assert result.exit_code == 0
    outputs = json.loads(result.output)
    payload = json.loads(Path(outputs["repo_map_json"]).read_text(encoding="utf-8"))
    assert payload["ranking_profile"] == "graph_seeded"
