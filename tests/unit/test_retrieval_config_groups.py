from __future__ import annotations

import click

from ace_lite.cli_app.config.retrieval import resolve_retrieval_and_lsp_config
from ace_lite.config_models import validate_cli_config


def _resolve_retrieval(**config: object) -> dict[str, object]:
    ctx = click.Context(click.Command("unit"))
    return resolve_retrieval_and_lsp_config(
        ctx=ctx,
        config=config,
        namespace="plan",
        retrieval_preset="none",
        adaptive_router_enabled=False,
        adaptive_router_mode="observe",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_v1",
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        embedding_enabled=False,
        embedding_provider="hash",
        embedding_model="hash-v1",
        embedding_dimension=256,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        languages="python",
        index_cache_path="context-map/index.json",
        index_incremental=True,
        conventions_files=(),
        plugins_enabled=True,
        remote_slot_policy_mode="strict",
        remote_slot_allowlist="",
        repomap_enabled=True,
        repomap_top_k=8,
        repomap_neighbor_limit=20,
        repomap_budget_tokens=800,
        repomap_ranking_profile="graph",
        repomap_signal_weights=None,
        lsp_enabled=False,
        lsp_top_n=5,
        lsp_cmds=(),
        lsp_xref_enabled=False,
        lsp_xref_top_n=3,
        lsp_time_budget_ms=1500,
        lsp_xref_cmds=(),
    )


def test_validate_cli_config_accepts_grouped_plugin_repomap_and_lsp_fields() -> None:
    payload = validate_cli_config(
        {
            "plan": {
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
                    "top_k": 5,
                    "neighbor_limit": 7,
                    "budget_tokens": 333,
                    "ranking_profile": "graph",
                    "signal_weights": {
                        "base": 0.7,
                        "graph": 0.2,
                        "import_depth": 0.1,
                    },
                },
                "lsp": {
                    "enabled": True,
                    "top_n": 6,
                    "commands": {"python": ["pylsp"]},
                    "xref_enabled": True,
                    "xref_top_n": 4,
                    "time_budget_ms": 900,
                    "xref_commands": {"python": ["pyright-langserver"]},
                },
            }
        }
    )

    assert payload["plan"]["plugins"] == {
        "enabled": False,
        "remote_slot_policy_mode": "warn",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }
    assert payload["plan"]["repomap"] == {
        "enabled": False,
        "top_k": 5,
        "neighbor_limit": 7,
        "budget_tokens": 333,
        "ranking_profile": "graph",
        "signal_weights": {
            "base": 0.7,
            "graph": 0.2,
            "import_depth": 0.1,
        },
    }
    assert payload["plan"]["lsp"] == {
        "enabled": True,
        "top_n": 6,
        "commands": {"python": ["pylsp"]},
        "xref_enabled": True,
        "xref_top_n": 4,
        "time_budget_ms": 900,
        "xref_commands": {"python": ["pyright-langserver"]},
    }


def test_validate_cli_config_accepts_grouped_embeddings_fields() -> None:
    payload = validate_cli_config(
        {
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
                }
            }
        }
    )

    assert payload["plan"]["embeddings"] == {
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


def test_validate_cli_config_accepts_grouped_index_fields() -> None:
    payload = validate_cli_config(
        {
            "plan": {
                "index": {
                    "languages": ["python", "go"],
                    "cache_path": "context-map/custom-index.json",
                    "incremental": False,
                    "conventions_files": ["STYLE.md", "docs/CONVENTIONS.md"],
                }
            }
        }
    )

    assert payload["plan"]["index"] == {
        "languages": ["python", "go"],
        "cache_path": "context-map/custom-index.json",
        "incremental": False,
        "conventions_files": ["STYLE.md", "docs/CONVENTIONS.md"],
    }


def test_resolve_retrieval_config_reads_grouped_plugin_repomap_and_lsp_fields() -> None:
    resolved = _resolve_retrieval(
        plan={
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
                "top_k": 5,
                "neighbor_limit": 7,
                "budget_tokens": 333,
                "ranking_profile": "graph",
                "signal_weights": {
                    "base": 0.7,
                    "graph": 0.2,
                    "import_depth": 0.1,
                },
            },
            "lsp": {
                "enabled": True,
                "top_n": 6,
                "commands": {"python": ["pylsp"]},
                "xref_enabled": True,
                "xref_top_n": 4,
                "time_budget_ms": 900,
                "xref_commands": {"python": ["pyright-langserver"]},
            },
        }
    )

    assert resolved["plugins_enabled"] is False
    assert resolved["remote_slot_policy_mode"] == "warn"
    assert resolved["remote_slot_allowlist"] == [
        "observability.mcp_plugins",
        "source_plan.writeback_template",
    ]
    assert resolved["plugins"] == {
        "enabled": False,
        "remote_slot_policy_mode": "warn",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }
    assert resolved["repomap_enabled"] is False
    assert resolved["repomap_top_k"] == 5
    assert resolved["repomap_neighbor_limit"] == 7
    assert resolved["repomap_budget_tokens"] == 333
    assert resolved["repomap_ranking_profile"] == "graph"
    assert resolved["repomap_signal_weights"] == {
        "base": 0.7,
        "graph": 0.2,
        "import_depth": 0.1,
    }
    assert resolved["repomap"] == {
        "enabled": False,
        "top_k": 5,
        "neighbor_limit": 7,
        "budget_tokens": 333,
        "ranking_profile": "graph",
        "signal_weights": {
            "base": 0.7,
            "graph": 0.2,
            "import_depth": 0.1,
        },
    }
    assert resolved["lsp_enabled"] is True
    assert resolved["lsp_top_n"] == 6
    assert resolved["lsp_commands"] == {"python": ["pylsp"]}
    assert resolved["lsp_xref_enabled"] is True
    assert resolved["lsp_xref_top_n"] == 4
    assert resolved["lsp_time_budget_ms"] == 900
    assert resolved["lsp_xref_commands"] == {
        "python": ["pyright-langserver"]
    }
    assert resolved["lsp"] == {
        "enabled": True,
        "top_n": 6,
        "commands": {"python": ["pylsp"]},
        "xref_enabled": True,
        "xref_top_n": 4,
        "time_budget_ms": 900,
        "xref_commands": {"python": ["pyright-langserver"]},
    }


def test_resolve_retrieval_config_emits_grouped_embeddings_and_index_payloads() -> None:
    resolved = _resolve_retrieval(
        plan={
            "languages": ["python", "go"],
            "index_cache_path": "context-map/custom-index.json",
            "index_incremental": False,
            "conventions_files": ["STYLE.md", "docs/CONVENTIONS.md"],
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
        }
    )

    assert resolved["embedding_enabled"] is True
    assert resolved["embedding_provider"] == "ollama"
    assert resolved["embedding_model"] == "bge-m3"
    assert resolved["embedding_dimension"] == 1024
    assert resolved["embedding_index_path"] == "context-map/embeddings/custom.json"
    assert resolved["embedding_rerank_pool"] == 32
    assert resolved["embedding_lexical_weight"] == 0.55
    assert resolved["embedding_semantic_weight"] == 0.45
    assert resolved["embedding_min_similarity"] == 0.1
    assert resolved["embedding_fail_open"] is False
    assert resolved["embeddings"] == {
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
    assert resolved["languages"] == "python,go"
    assert resolved["index_cache_path"] == "context-map/custom-index.json"
    assert resolved["index_incremental"] is False
    assert resolved["conventions_files"] == ("STYLE.md", "docs/CONVENTIONS.md")
    assert resolved["index"] == {
        "languages": ["python", "go"],
        "cache_path": "context-map/custom-index.json",
        "incremental": False,
        "conventions_files": ["STYLE.md", "docs/CONVENTIONS.md"],
    }


def test_resolve_retrieval_config_grouped_index_matches_flat_compatibility() -> None:
    flat = _resolve_retrieval(
        plan={
            "languages": ["python", "go"],
            "index_cache_path": "context-map/custom-index.json",
            "index_incremental": False,
            "conventions_files": ["STYLE.md", "docs/CONVENTIONS.md"],
        }
    )
    grouped = _resolve_retrieval(
        plan={
            "index": {
                "languages": ["python", "go"],
                "cache_path": "context-map/custom-index.json",
                "incremental": False,
                "conventions_files": ["STYLE.md", "docs/CONVENTIONS.md"],
            }
        }
    )

    for key in (
        "languages",
        "index_cache_path",
        "index_incremental",
        "conventions_files",
        "index",
    ):
        assert grouped[key] == flat[key]
