from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from ace_lite.cli import cli
from ace_lite.config import load_layered_config


def test_load_layered_config_precedence(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "home"
    repo_root = tmp_path / "repo"
    cwd_dir = repo_root / "workspace"

    fake_home.mkdir(parents=True, exist_ok=True)
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    (fake_home / ".ace-lite.yml").write_text("top_k_files: 1\n", encoding="utf-8")
    (repo_root / ".ace-lite.yml").write_text("top_k_files: 2\n", encoding="utf-8")
    (cwd_dir / ".ace-lite.yml").write_text("top_k_files: 3\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.chdir(cwd_dir)

    config = load_layered_config(root_dir=repo_root, cwd=cwd_dir)

    assert config["top_k_files"] == 3
    assert len(config["_meta"]["loaded_files"]) == 3


def test_load_layered_config_ignores_foreign_cwd_override(
    tmp_path: Path, monkeypatch
) -> None:
    fake_home = tmp_path / "home"
    target_root = tmp_path / "target-repo"
    foreign_repo = tmp_path / "foreign-repo"
    foreign_cwd = foreign_repo / "workspace"

    fake_home.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    foreign_cwd.mkdir(parents=True, exist_ok=True)
    (target_root / ".git").mkdir(parents=True, exist_ok=True)
    (foreign_repo / ".git").mkdir(parents=True, exist_ok=True)

    (fake_home / ".ace-lite.yml").write_text("top_k_files: 1\n", encoding="utf-8")
    (target_root / ".ace-lite.yml").write_text("top_k_files: 2\n", encoding="utf-8")
    (foreign_cwd / ".ace-lite.yml").write_text("top_k_files: 9\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.chdir(foreign_cwd)

    config = load_layered_config(root_dir=target_root, cwd=foreign_cwd)

    assert config["top_k_files"] == 2
    assert str(foreign_cwd / ".ace-lite.yml") not in config["_meta"]["loaded_files"]


def test_load_layered_config_uses_requested_root_even_inside_parent_git_repo(
    tmp_path: Path, monkeypatch
) -> None:
    fake_home = tmp_path / "home"
    parent_repo = tmp_path / "parent-repo"
    target_root = parent_repo / "nested-target"

    fake_home.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    (parent_repo / ".git").mkdir(parents=True, exist_ok=True)

    (fake_home / ".ace-lite.yml").write_text("top_k_files: 1\n", encoding="utf-8")
    (target_root / ".ace-lite.yml").write_text("top_k_files: 4\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.chdir(parent_repo)

    config = load_layered_config(root_dir=target_root, cwd=parent_repo)

    assert config["top_k_files"] == 4
    assert str(target_root / ".ace-lite.yml") in config["_meta"]["loaded_files"]


def test_cli_plan_uses_repo_config_for_defaults(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text("---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n", encoding="utf-8")

    config_payload = {
        "plan": {
            "top_k_files": 1,
            "languages": ["python"],
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
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
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["index"]["candidate_files"]) == 1


def test_cli_plan_uses_grouped_retrieval_config_for_defaults(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    for name in ("auth.py", "auth_helpers.py", "tokens.py", "routes.py"):
        (tmp_path / "src" / name).write_text(
            f"def {name.replace('.py', '')}_helper():\n    return 1\n",
            encoding="utf-8",
        )
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "languages": ["python"],
            "retrieval": {
                "top_k_files": 1,
                "candidate_ranker": "bm25_lite",
                "hybrid_re2_fusion_mode": "rrf",
            },
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "auth helper",
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
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["index"]["candidate_files"]) == 1
    assert payload["index"]["candidate_ranking"]["requested"] == "bm25_lite"


def test_cli_plan_passes_grouped_chunking_config_to_run_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "languages": ["python"],
            "chunk": {
                "top_k": 5,
                "per_file_limit": 2,
                "signature": True,
                "token_budget": 700,
                "snippet": {"max_lines": 9, "max_chars": 320},
                "topological_shield": {
                    "enabled": True,
                    "mode": "report_only",
                    "max_attenuation": 0.6,
                    "shared_parent_attenuation": 0.2,
                    "adjacency_attenuation": 0.5,
                },
                "guard": {"mode": "report_only"},
            },
            "tokenizer": {
                "model": "gpt-4.1-mini",
            },
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_plan(**kwargs):
        captured["chunking_config"] = kwargs["chunking_config"]
        captured["tokenizer_config"] = kwargs["tokenizer_config"]
        return {"ok": True}

    monkeypatch.setattr("ace_lite.cli.run_plan", fake_run_plan)
    monkeypatch.setattr(
        "ace_lite.cli.create_memory_provider",
        lambda **kwargs: None,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
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
    )

    assert result.exit_code == 0
    assert captured["chunking_config"] == {
        "top_k": 5,
        "per_file_limit": 2,
        "disclosure": "refs",
        "signature": True,
        "file_prior_weight": 0.35,
        "path_match": 1.0,
        "module_match": 0.8,
        "symbol_exact": 2.5,
        "symbol_partial": 1.4,
        "signature_match": 0.5,
        "reference_factor": 0.3,
        "reference_cap": 2.5,
        "snippet": {"max_lines": 9, "max_chars": 320},
        "token_budget": 700,
        "topological_shield": {
            "enabled": True,
            "mode": "report_only",
            "max_attenuation": 0.6,
            "shared_parent_attenuation": 0.2,
            "adjacency_attenuation": 0.5,
        },
        "guard": {
            "enabled": True,
            "mode": "report_only",
            "lambda_penalty": 0.8,
            "min_pool": 4,
            "max_pool": 32,
            "min_marginal_utility": 0.0,
            "compatibility_min_overlap": 0.3,
        },
    }
    assert captured["tokenizer_config"] == {"model": "gpt-4.1-mini"}


def test_cli_plan_passes_grouped_retrieval_router_and_auxiliary_config_to_run_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "embeddings": {
                "enabled": True,
                "provider": "ollama",
                "model": "bge-m3",
                "dimension": 1024,
                "index_path": "context-map/embeddings/custom.json",
                "rerank_pool": 32,
                "lexical_weight": 0.55,
                "semantic_weight": 0.45,
                "min_similarity": 0.1,
                "fail_open": False,
            },
            "retrieval": {
                "top_k_files": 2,
                "min_candidate_score": 4,
                "candidate_relative_threshold": 0.25,
                "candidate_ranker": "bm25_lite",
                "exact_search_enabled": True,
                "deterministic_refine_enabled": False,
                "exact_search_time_budget_ms": 90,
                "exact_search_max_paths": 7,
                "hybrid_re2_fusion_mode": "rrf",
                "hybrid_re2_rrf_k": 75,
                "hybrid_re2_bm25_weight": 0.4,
                "hybrid_re2_heuristic_weight": 0.35,
                "hybrid_re2_coverage_weight": 0.25,
                "hybrid_re2_combined_scale": 1.2,
            },
            "adaptive_router": {
                "enabled": True,
                "mode": "shadow",
                "model_path": "custom/router/model.json",
                "state_path": "custom/router/state.json",
                "arm_set": "retrieval_policy_shadow",
                "online_bandit": {"enabled": True, "experiment_enabled": True},
            },
            "plugins": {
                "enabled": False,
                "remote_slot_policy_mode": "warn",
                "remote_slot_allowlist": [
                    "observability.mcp_plugins",
                    "source_plan.writeback_template",
                ],
            },
                "repomap": {
                    "enabled": False,
                    "top_k": 4,
                    "neighbor_limit": 11,
                    "budget_tokens": 420,
                    "ranking_profile": "graph_seeded",
                    "signal_weights": {"imports": 1.5, "cochange": 0.75},
                },
            "lsp": {
                "enabled": True,
                "top_n": 9,
                "commands": {"python": ["pylsp"]},
                "xref_enabled": True,
                "xref_top_n": 6,
                "time_budget_ms": 2200,
                "xref_commands": {"python": ["pylsp-xref"]},
            },
            "skills": {
                "precomputed_routing_enabled": False,
            },
            "index": {
                "languages": ["python"],
                "cache_path": "context-map/custom-index.json",
                "incremental": False,
                "conventions_files": ["STYLE.md"],
            },
            "cochange": {
                "enabled": False,
                "cache_path": "context-map/cochange/custom.json",
                "lookback_commits": 128,
                "half_life_days": 14.0,
                "top_neighbors": 6,
                "boost_weight": 0.75,
            },
            "tests": {
                "junit_xml": "artifacts/junit.xml",
                "coverage_json": "artifacts/coverage.json",
                "sbfl": {
                    "json_path": "artifacts/sbfl.json",
                    "metric": "dstar",
                },
            },
            "scip": {
                "enabled": True,
                "index_path": "context-map/scip/custom-index.json",
                "provider": "scip_lite",
                "generate_fallback": False,
            },
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_plan(**kwargs):
        captured["skills_config"] = kwargs["skills_config"]
        captured["index_config"] = kwargs["index_config"]
        captured["embeddings_config"] = kwargs["embeddings_config"]
        captured["retrieval_config"] = kwargs["retrieval_config"]
        captured["adaptive_router_config"] = kwargs["adaptive_router_config"]
        captured["plugins_config"] = kwargs["plugins_config"]
        captured["repomap_config"] = kwargs["repomap_config"]
        captured["lsp_config"] = kwargs["lsp_config"]
        captured["cochange_config"] = kwargs["cochange_config"]
        captured["tests_config"] = kwargs["tests_config"]
        captured["scip_config"] = kwargs["scip_config"]
        return {"ok": True}

    monkeypatch.setattr("ace_lite.cli.run_plan", fake_run_plan)
    monkeypatch.setattr(
        "ace_lite.cli.create_memory_provider",
        lambda **kwargs: None,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
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
    )

    assert result.exit_code == 0
    assert captured["skills_config"] == {
        "dir": str(tmp_path / "skills"),
        "precomputed_routing_enabled": False,
    }
    assert captured["index_config"] == {
        "languages": ["python"],
        "cache_path": "context-map/custom-index.json",
        "incremental": False,
        "conventions_files": ["STYLE.md"],
    }
    assert captured["embeddings_config"] == {
        "enabled": True,
        "provider": "ollama",
        "model": "bge-m3",
        "dimension": 1024,
        "index_path": "context-map/embeddings/custom.json",
        "rerank_pool": 32,
        "lexical_weight": 0.55,
        "semantic_weight": 0.45,
        "min_similarity": 0.1,
        "fail_open": False,
    }
    assert captured["adaptive_router_config"] == {
        "enabled": True,
        "mode": "shadow",
        "model_path": "custom/router/model.json",
        "state_path": "custom/router/state.json",
        "arm_set": "retrieval_policy_shadow",
        "online_bandit": {"enabled": True, "experiment_enabled": True},
    }
    assert captured["plugins_config"] == {
        "enabled": False,
        "remote_slot_policy_mode": "warn",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }
    assert captured["repomap_config"] == {
        "enabled": False,
        "top_k": 4,
        "neighbor_limit": 11,
        "budget_tokens": 420,
        "ranking_profile": "graph_seeded",
        "signal_weights": {"imports": 1.5, "cochange": 0.75},
    }
    assert captured["lsp_config"] == {
        "enabled": True,
        "top_n": 9,
        "commands": {"python": ["pylsp"]},
        "xref_enabled": True,
        "xref_top_n": 6,
        "time_budget_ms": 2200,
        "xref_commands": {"python": ["pylsp-xref"]},
    }
    assert captured["cochange_config"] == {
        "enabled": False,
        "cache_path": "context-map/cochange/custom.json",
        "lookback_commits": 128,
        "half_life_days": 14.0,
        "top_neighbors": 6,
        "boost_weight": 0.75,
    }
    assert captured["tests_config"] == {
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl_json": "artifacts/sbfl.json",
        "sbfl_metric": "dstar",
    }
    assert captured["scip_config"] == {
        "enabled": True,
        "index_path": "context-map/scip/custom-index.json",
        "provider": "scip_lite",
        "generate_fallback": False,
        "base_weight": 0.5,
    }
    retrieval_config = captured["retrieval_config"]
    assert retrieval_config["top_k_files"] == 2
    assert retrieval_config["min_candidate_score"] == 4
    assert retrieval_config["candidate_relative_threshold"] == 0.25
    assert retrieval_config["candidate_ranker"] == "bm25_lite"
    assert retrieval_config["exact_search_enabled"] is True
    assert retrieval_config["deterministic_refine_enabled"] is False
    assert retrieval_config["exact_search_time_budget_ms"] == 90
    assert retrieval_config["exact_search_max_paths"] == 7
    assert retrieval_config["hybrid_re2_fusion_mode"] == "rrf"
    assert retrieval_config["hybrid_re2_rrf_k"] == 75
    assert retrieval_config["hybrid_re2_bm25_weight"] == 0.4
    assert retrieval_config["hybrid_re2_heuristic_weight"] == 0.35
    assert retrieval_config["hybrid_re2_coverage_weight"] == 0.25
    assert retrieval_config["hybrid_re2_combined_scale"] == 1.2
    assert retrieval_config["adaptive_router"] == {
        "enabled": True,
        "mode": "shadow",
        "model_path": "custom/router/model.json",
        "state_path": "custom/router/state.json",
        "arm_set": "retrieval_policy_shadow",
        "online_bandit": {"enabled": True, "experiment_enabled": True},
    }
    assert retrieval_config["bm25_k1"] == 1.2
    assert retrieval_config["bm25_b"] == 0.75
    assert retrieval_config["bm25_score_scale"] == 4.0
    assert retrieval_config["bm25_path_prior_factor"] == 0.1
    assert retrieval_config["bm25_shortlist_min"] == 16
    assert retrieval_config["bm25_shortlist_factor"] == 6
    assert retrieval_config["hybrid_re2_shortlist_min"] == 12
    assert retrieval_config["hybrid_re2_shortlist_factor"] == 4
    assert retrieval_config["heur_path_exact"] == 3.0
    assert retrieval_config["heur_content_cap"] == 1.0


def test_cli_plan_uses_repo_config_for_precomputed_skills_routing(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "languages": ["python"],
            "skills": {"precomputed_routing_enabled": True},
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
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
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["skills"]["routing_source"] == "precomputed"


def test_cli_plan_uses_repo_config_for_plan_replay_cache(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "languages": ["python"],
            "plan_replay_cache": {
                "enabled": True,
                "cache_path": "custom/plan-replay/cache.json",
            },
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    runner = CliRunner()
    command = [
        "plan",
        "--query",
        "implement helper",
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
    ]

    first = runner.invoke(cli, command)
    second = runner.invoke(cli, command)

    assert first.exit_code == 0
    assert second.exit_code == 0
    first_payload = json.loads(first.output)
    second_payload = json.loads(second.output)

    assert first_payload["observability"]["plan_replay_cache"]["enabled"] is True
    assert first_payload["observability"]["plan_replay_cache"]["hit"] is False
    assert second_payload["observability"]["plan_replay_cache"]["hit"] is True
    assert Path(
        second_payload["observability"]["plan_replay_cache"]["cache_path"]
    ) == (tmp_path / "custom" / "plan-replay" / "cache.json")


def test_cli_plan_passes_grouped_plan_replay_cache_config_to_run_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "languages": ["python"],
            "plan_replay_cache": {
                "enabled": True,
                "cache_path": "custom/plan-replay/cache.json",
            },
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_plan(**kwargs):
        captured["plan_replay_cache_config"] = kwargs["plan_replay_cache_config"]
        return {"ok": True}

    monkeypatch.setattr("ace_lite.cli.run_plan", fake_run_plan)
    monkeypatch.setattr(
        "ace_lite.cli.create_memory_provider",
        lambda **kwargs: None,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
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
    )

    assert result.exit_code == 0
    assert captured["plan_replay_cache_config"] == {
        "enabled": True,
        "cache_path": "custom/plan-replay/cache.json",
    }


def test_cli_plan_uses_repo_config_for_adaptive_router_observability(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "custom" / "router").mkdir(parents=True, exist_ok=True)

    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )
    (tmp_path / "custom" / "router" / "model.json").write_text(
        json.dumps(
            {
                "arm_set": "retrieval_policy_shadow",
                "policy_arms": {
                    "feature": {"arm_id": "feature_graph", "confidence": 0.88}
                },
            }
        ),
        encoding="utf-8",
    )

    config_payload = {
        "plan": {
            "languages": ["python"],
            "adaptive_router": {
                "enabled": True,
                "mode": "shadow",
                "model_path": "custom/router/model.json",
                "state_path": "custom/router/state.json",
                "arm_set": "retrieval_policy_shadow",
                "online_bandit": {"enabled": True},
            },
        }
    }
    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
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
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    router = payload["index"]["adaptive_router"]
    assert router["enabled"] is True
    assert router["mode"] == "shadow"
    assert router["model_path"] == "custom/router/model.json"
    assert router["state_path"] == "custom/router/state.json"
    assert router["arm_set"] == "retrieval_policy_shadow"
    assert router["arm_id"] == "feature"
    assert router["shadow_arm_id"] == "feature_graph"
    assert router["shadow_confidence"] == 0.88
    assert router["online_bandit"]["requested"] is True
    assert router["online_bandit"]["experiment_enabled"] is False
    assert router["online_bandit"]["eligible"] is True
    assert router["online_bandit"]["active"] is False
    assert router["online_bandit"]["is_exploration"] is False
    assert router["online_bandit"]["fallback_applied"] is True
    assert router["online_bandit"]["fallback_reason"] == "experiment_mode_disabled"
    assert router["online_bandit"]["reason"] == "experiment_mode_required"


def test_cli_plan_config_pack_overrides_repo_config(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    (tmp_path / ".ace-lite.yml").write_text(
        yaml.safe_dump({"plan": {"top_k_files": 1, "languages": ["python"]}}, sort_keys=False),
        encoding="utf-8",
    )
    config_pack_path = tmp_path / "pack.json"
    config_pack_path.write_text(
        json.dumps(
            {
                "schema_version": "ace-lite-config-pack-v1",
                "name": "test-pack",
                "overrides": {"top_k_files": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--config-pack",
            str(config_pack_path),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["index"]["candidate_files"]) == 2


def test_cli_plan_config_pack_is_overridden_by_explicit_cli_args(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "src" / name).write_text(
            f"def {name.replace('.py','')}():\n    return 1\n",
            encoding="utf-8",
        )
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )
    config_pack_path = tmp_path / "pack.json"
    config_pack_path.write_text(
        json.dumps(
            {
                "schema_version": "ace-lite-config-pack-v1",
                "name": "test-pack",
                "overrides": {"top_k_files": 3},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--config-pack",
            str(config_pack_path),
            "--top-k-files",
            "1",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["index"]["candidate_files"]) == 1


def test_cli_plan_config_pack_overrides_retrieval_preset(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    for idx in range(6):
        (tmp_path / "src" / f"f{idx}.py").write_text(
            f"def f{idx}():\n    return {idx}\n",
            encoding="utf-8",
        )
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )
    config_pack_path = tmp_path / "pack.json"
    config_pack_path.write_text(
        json.dumps(
            {
                "schema_version": "ace-lite-config-pack-v1",
                "name": "test-pack",
                "overrides": {"top_k_files": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--query",
            "implement helper",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--retrieval-preset",
            "precision-v1",
            "--config-pack",
            str(config_pack_path),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["index"]["candidate_files"]) == 2
