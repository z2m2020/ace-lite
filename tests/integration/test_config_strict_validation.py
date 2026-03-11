from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.memory import NullMemoryProvider


def _seed_root(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_plan_rejects_unknown_config_keys(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  unknown_key: 123
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "Invalid .ace-lite.yml configuration" in result.output
    assert "plan.unknown_key" in result.output


def test_cli_plan_accepts_team_sync_placeholder_config(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
team:
  sync:
    enabled: false
    backend: none
    endpoint: null
    namespace_scope: repo
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_plan_accepts_embeddings_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  embeddings:
    enabled: true
    provider: hash
    model: hash-v1
    dimension: 128
    index_path: context-map/embeddings/index.json
    rerank_pool: 10
    lexical_weight: 0.7
    semantic_weight: 0.3
    min_similarity: 0.0
    fail_open: true
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_plan_accepts_bge_embeddings_provider(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  embeddings:
    enabled: true
    provider: bge_m3
    model: BAAI/bge-m3
    dimension: 1024
    index_path: context-map/embeddings/index.json
    rerank_pool: 10
    lexical_weight: 0.5
    semantic_weight: 0.5
    min_similarity: 0.1
    fail_open: true
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_plan_accepts_doc_intent_retrieval_policy_in_config(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  retrieval_policy: doc_intent
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_plan_accepts_grouped_index_and_quality_signal_config(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  index:
    languages:
      - python
      - go
    cache_path: context-map/custom-index.json
    incremental: false
    conventions_files:
      - STYLE.md
  cochange:
    enabled: false
    cache_path: context-map/cochange/custom.json
    lookback_commits: 128
    half_life_days: 14.0
    top_neighbors: 6
    boost_weight: 0.75
  tests:
    junit_xml: artifacts/junit.xml
    coverage_json: artifacts/coverage.json
    sbfl:
      json_path: artifacts/sbfl.json
      metric: dstar
  scip:
    enabled: true
    index_path: context-map/scip/custom-index.json
    provider: scip_lite
    generate_fallback: false
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0


def test_cli_plan_rejects_unknown_grouped_nested_config_keys(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  tests:
    sbfl:
      metric: ochiai
      unexpected: true
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "Invalid .ace-lite.yml configuration" in result.output
    assert "plan.tests.sbfl.unexpected" in result.output
