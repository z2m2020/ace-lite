from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ace_lite.cli import cli
from ace_lite.feedback_store import SelectionFeedbackStore


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def _seed_repo(root: Path) -> Path:
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "alpha.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "beta.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )
    (root / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )
    cases_path = root / "benchmark" / "cases" / "feedback.yaml"
    cases_path.write_text(
        "cases:\n  - case_id: feedback-01\n    query: validate token\n    expected_keys: [beta]\n    top_k: 1\n",
        encoding="utf-8",
    )
    return cases_path


def test_cli_benchmark_feedback_on_off_slice(tmp_path: Path) -> None:
    cases_path = _seed_repo(tmp_path)
    output_off = tmp_path / "artifacts" / "benchmark" / "feedback-off"
    output_on = tmp_path / "artifacts" / "benchmark" / "feedback-on"

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
            "none",
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

    profile_path = tmp_path / "profile.json"
    SelectionFeedbackStore(profile_path=profile_path, max_entries=8).record(
        query="validate token",
        repo="demo",
        selected_path="src/app/beta.py",
        position=1,
        captured_at="2026-02-14T00:00:00+00:00",
    )
    (tmp_path / ".ace-lite.yml").write_text(
        f"""
benchmark:
  memory:
    feedback:
      enabled: true
      path: {profile_path.as_posix()}
      boost_per_select: 0.8
      max_boost: 0.8
      decay_days: 60.0
""".lstrip(),
        encoding="utf-8",
    )

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
            "--languages",
            "python",
            "--candidate-ranker",
            "heuristic",
            "--min-candidate-score",
            "0",
            "--top-k-files",
            "1",
            "--memory-primary",
            "none",
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

