from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

import ace_lite.cli as cli_module


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_retrieval_preset_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  top_k_files: 11
  min_candidate_score: 7
  candidate_relative_threshold: 0.33
  candidate_ranker: bm25_lite
  repomap_signal_weights:
    base: 0.6
    graph: 0.3
    import_depth: 0.1
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.clear()
        captured["retrieval_config"] = kwargs["retrieval_config"]
        captured["repomap_config"] = kwargs["repomap_config"]
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    base_args = [
        "plan",
        "--query",
        "q",
        "--repo",
        "demo",
        "--root",
        str(tmp_path),
        "--languages",
        "python",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
    ]

    result = runner.invoke(cli_module.cli, base_args, env=_cli_env(tmp_path))
    assert result.exit_code == 0
    assert captured["retrieval_config"]["top_k_files"] == 11
    assert captured["retrieval_config"]["min_candidate_score"] == 7
    assert captured["retrieval_config"]["candidate_relative_threshold"] == pytest.approx(
        0.33
    )
    assert captured["retrieval_config"]["candidate_ranker"] == "bm25_lite"
    assert captured["repomap_config"]["signal_weights"] == {
        "base": 0.6,
        "graph": 0.3,
        "import_depth": 0.1,
    }

    result = runner.invoke(
        cli_module.cli,
        [*base_args, "--retrieval-preset", "precision-v1"],
        env=_cli_env(tmp_path),
    )
    assert result.exit_code == 0
    assert captured["retrieval_config"]["top_k_files"] == 4
    assert captured["retrieval_config"]["min_candidate_score"] == 2
    assert captured["retrieval_config"]["candidate_relative_threshold"] == pytest.approx(
        0.55
    )
    assert captured["retrieval_config"]["candidate_ranker"] == "heuristic"
    assert captured["repomap_config"]["signal_weights"] == {
        "base": 0.75,
        "graph": 0.2,
        "import_depth": 0.05,
    }

    explicit_weights = {"base": 0.1, "graph": 0.2, "import_depth": 0.3}
    result = runner.invoke(
        cli_module.cli,
        [
            *base_args,
            "--retrieval-preset",
            "precision-v1",
            "--top-k-files",
            "99",
            "--min-candidate-score",
            "13",
            "--candidate-relative-threshold",
            "0.9",
            "--candidate-ranker",
            "hybrid_re2",
            "--repomap-signal-weights",
            json.dumps(explicit_weights),
        ],
        env=_cli_env(tmp_path),
    )
    assert result.exit_code == 0
    assert captured["retrieval_config"]["top_k_files"] == 99
    assert captured["retrieval_config"]["min_candidate_score"] == 13
    assert captured["retrieval_config"]["candidate_relative_threshold"] == pytest.approx(
        0.9
    )
    assert captured["retrieval_config"]["candidate_ranker"] == "hybrid_re2"
    assert captured["repomap_config"]["signal_weights"] == explicit_weights



def test_cli_reads_scip_provider_and_fallback_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  scip_provider: xref_json
  scip_generate_fallback: false
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured["scip_provider"] = kwargs["scip_provider"]
        captured["scip_generate_fallback"] = kwargs["scip_generate_fallback"]
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

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
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["scip_provider"] == "xref_json"
    assert captured["scip_generate_fallback"] is False


def test_cli_reads_embedding_config_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  embeddings:
    enabled: true
    provider: hash
    model: hash-v2
    dimension: 384
    index_path: context-map/embeddings/custom.json
    rerank_pool: 12
    lexical_weight: 0.6
    semantic_weight: 0.4
    min_similarity: 0.05
    fail_open: false
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        for key in (
            "embedding_enabled",
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
            "embedding_index_path",
            "embedding_rerank_pool",
            "embedding_lexical_weight",
            "embedding_semantic_weight",
            "embedding_min_similarity",
            "embedding_fail_open",
        ):
            captured[key] = kwargs[key]
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

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
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured == {
        "embedding_enabled": True,
        "embedding_provider": "hash",
        "embedding_model": "hash-v2",
        "embedding_dimension": 384,
        "embedding_index_path": "context-map/embeddings/custom.json",
        "embedding_rerank_pool": 12,
        "embedding_lexical_weight": 0.6,
        "embedding_semantic_weight": 0.4,
        "embedding_min_similarity": 0.05,
        "embedding_fail_open": False,
    }


def test_cli_accepts_doc_intent_retrieval_policy_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured["retrieval_policy"] = kwargs["retrieval_policy"]
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "explain the indexing architecture",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--languages",
            "python",
            "--retrieval-policy",
            "doc_intent",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["retrieval_policy"] == "doc_intent"


def test_cli_reads_deterministic_refine_flag_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  deterministic_refine_enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured["deterministic_refine_enabled"] = kwargs["retrieval_config"][
            "deterministic_refine_enabled"
        ]
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

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
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["deterministic_refine_enabled"] is False
