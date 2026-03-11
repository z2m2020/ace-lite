from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ace_lite.cli import cli


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def _seed_repo(root: Path) -> Path:
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)
    (root / "context-map").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "legacy_validator.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "modern_validator.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )
    (root / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    notes_path = root / "context-map" / "memory_notes.jsonl"
    notes_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "text": "validate token legacy_validator",
                        "repo": "demo",
                        "captured_at": "2026-01-01T00:00:00+00:00",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "source": "local_notes",
                    }
                ),
                json.dumps(
                    {
                        "text": "validate modern_validator token",
                        "repo": "demo",
                        "captured_at": "2026-02-14T00:00:00+00:00",
                        "created_at": "2026-02-14T00:00:00+00:00",
                        "source": "local_notes",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (root / ".ace-lite.yml").write_text(
        f"""
benchmark:
  memory:
    notes:
      enabled: true
      path: {notes_path.as_posix()}
      mode: local_only
      expiry_enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "temporal.yaml"
    cases_path.write_text(
        "cases:\n  - case_id: temporal-01\n    query: validate token\n    expected_keys: [modern_validator]\n    top_k: 1\n",
        encoding="utf-8",
    )
    return cases_path


def test_cli_benchmark_temporal_start_end_filters_memory_notes(tmp_path: Path) -> None:
    cases_path = _seed_repo(tmp_path)
    output_off = tmp_path / "artifacts" / "benchmark" / "temporal-off"
    output_on = tmp_path / "artifacts" / "benchmark" / "temporal-on"

    runner = CliRunner()
    off = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(cases_path),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--candidate-ranker",
            "heuristic",
            "--min-candidate-score",
            "0",
            "--top-k-files",
            "1",
            "--memory-primary",
            "rest",
            "--memory-secondary",
            "none",
            "--no-repomap",
            "--no-plugins",
            "--no-lsp",
            "--no-lsp-xref",
            "--no-cochange",
            "--no-scip",
            "--no-trace-export",
            "--no-trace-otlp",
            "--no-include-plans",
            "--no-include-case-details",
            "--output",
            str(output_off),
        ],
        env=_cli_env(tmp_path),
    )
    assert off.exit_code == 0
    off_payload = json.loads((output_off / "results.json").read_text(encoding="utf-8"))

    on = runner.invoke(
        cli,
        [
            "benchmark",
            "run",
            "--cases",
            str(cases_path),
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--start-date",
            "2026-02-10",
            "--end-date",
            "2026-02-15",
            "--languages",
            "python",
            "--candidate-ranker",
            "heuristic",
            "--min-candidate-score",
            "0",
            "--top-k-files",
            "1",
            "--memory-primary",
            "rest",
            "--memory-secondary",
            "none",
            "--no-repomap",
            "--no-plugins",
            "--no-lsp",
            "--no-lsp-xref",
            "--no-cochange",
            "--no-scip",
            "--no-trace-export",
            "--no-trace-otlp",
            "--no-include-plans",
            "--no-include-case-details",
            "--output",
            str(output_on),
        ],
        env=_cli_env(tmp_path),
    )
    assert on.exit_code == 0
    on_payload = json.loads((output_on / "results.json").read_text(encoding="utf-8"))

    assert float(off_payload["metrics"]["precision_at_k"]) < float(
        on_payload["metrics"]["precision_at_k"]
    )
    assert float(off_payload["metrics"]["noise_rate"]) > float(on_payload["metrics"]["noise_rate"])

