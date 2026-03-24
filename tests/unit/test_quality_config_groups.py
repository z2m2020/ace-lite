from __future__ import annotations

import click

from ace_lite.cli_app.config.quality import resolve_quality_config
from ace_lite.config_models import validate_cli_config


def _resolve_quality(**config: object) -> dict[str, object]:
    ctx = click.Context(click.Command("unit"))
    return resolve_quality_config(
        ctx=ctx,
        config=config,
        namespace="plan",
        chunk_top_k=24,
        chunk_per_file_limit=3,
        chunk_disclosure="refs",
        chunk_signature=False,
        chunk_snippet_max_lines=18,
        chunk_snippet_max_chars=1200,
        chunk_token_budget=1200,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.20,
        chunk_diversity_symbol_family_penalty=0.30,
        chunk_diversity_kind_penalty=0.10,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
        cochange_enabled=True,
        cochange_cache_path="context-map/cochange.json",
        cochange_lookback_commits=400,
        cochange_half_life_days=60.0,
        cochange_top_neighbors=12,
        cochange_boost_weight=1.5,
        retrieval_policy="auto",
        policy_version="v1",
        junit_xml=None,
        coverage_json=None,
        sbfl_json=None,
        sbfl_metric="ochiai",
        scip_enabled=False,
        scip_index_path="context-map/scip/index.json",
        scip_provider="auto",
        scip_generate_fallback=True,
        trace_export_enabled=False,
        trace_export_path="context-map/traces/stage_spans.jsonl",
        trace_otlp_enabled=False,
        trace_otlp_endpoint="",
        trace_otlp_timeout_seconds=1.5,
    )


def test_validate_cli_config_accepts_grouped_chunk_fields() -> None:
    payload = validate_cli_config(
        {
            "plan": {
                "chunk": {
                    "top_k": 7,
                    "per_file_limit": 2,
                    "disclosure": "signature",
                    "signature": True,
                    "token_budget": 640,
                    "snippet": {
                        "max_lines": 9,
                        "max_chars": 420,
                    },
                    "topological_shield": {
                        "enabled": True,
                        "mode": "report_only",
                        "max_attenuation": 0.6,
                        "shared_parent_attenuation": 0.2,
                        "adjacency_attenuation": 0.5,
                    },
                    "guard": {
                        "mode": "report_only",
                    },
                }
            }
        }
    )

    assert payload["plan"]["chunk"] == {
        "top_k": 7,
        "per_file_limit": 2,
        "disclosure": "signature",
        "signature": True,
        "snippet": {
            "max_lines": 9,
            "max_chars": 420,
        },
        "token_budget": 640,
        "topological_shield": {
            "enabled": True,
            "mode": "report_only",
            "max_attenuation": 0.6,
            "shared_parent_attenuation": 0.2,
            "adjacency_attenuation": 0.5,
        },
        "guard": {
            "mode": "report_only",
        },
    }


def test_resolve_quality_config_reads_grouped_chunk_fields_and_emits_grouped_payload() -> None:
    resolved = _resolve_quality(
        plan={
            "chunk": {
                "top_k": 5,
                "per_file_limit": 2,
                "disclosure": "signature",
                "signature": True,
                "token_budget": 700,
                "snippet": {
                    "max_lines": 11,
                    "max_chars": 333,
                },
                "topological_shield": {
                    "enabled": True,
                    "mode": "report_only",
                    "max_attenuation": 0.65,
                    "shared_parent_attenuation": 0.25,
                    "adjacency_attenuation": 0.55,
                },
                "guard": {
                    "enabled": True,
                    "mode": "report_only",
                    "lambda_penalty": 1.25,
                    "min_pool": 2,
                    "max_pool": 6,
                    "min_marginal_utility": 0.1,
                    "compatibility_min_overlap": 0.6,
                },
            }
        }
    )

    assert resolved["chunk_top_k"] == 5
    assert resolved["chunk_per_file_limit"] == 2
    assert resolved["chunk_disclosure"] == "signature"
    assert resolved["chunk_signature"] is True
    assert resolved["chunk_token_budget"] == 700
    assert resolved["chunk_snippet_max_lines"] == 11
    assert resolved["chunk_snippet_max_chars"] == 333
    assert resolved["chunk_guard_enabled"] is True
    assert resolved["chunk_guard_mode"] == "report_only"

    assert resolved["chunk"] == {
        "top_k": 5,
        "per_file_limit": 2,
        "disclosure": "signature",
        "signature": True,
        "snippet": {
            "max_lines": 11,
            "max_chars": 333,
        },
        "token_budget": 700,
        "topological_shield": {
            "enabled": True,
            "mode": "report_only",
            "max_attenuation": 0.65,
            "shared_parent_attenuation": 0.25,
            "adjacency_attenuation": 0.55,
        },
        "guard": {
            "enabled": True,
            "mode": "report_only",
            "lambda_penalty": 1.25,
            "min_pool": 2,
            "max_pool": 6,
            "min_marginal_utility": 0.1,
            "compatibility_min_overlap": 0.6,
        },
        "file_prior_weight": 0.35,
        "path_match": 1.0,
        "module_match": 0.8,
        "symbol_exact": 2.5,
        "symbol_partial": 1.4,
        "signature_match": 0.5,
        "reference_factor": 0.3,
        "reference_cap": 2.5,
    }


def test_validate_cli_config_accepts_year2_skeleton_disclosure_choice() -> None:
    payload = validate_cli_config(
        {
            "plan": {
                "chunk": {
                    "disclosure": "skeleton_light",
                }
            }
        }
    )

    assert payload["plan"]["chunk"]["disclosure"] == "skeleton_light"


def test_validate_cli_config_accepts_grouped_trace_fields() -> None:
    payload = validate_cli_config(
        {
            "plan": {
                "trace": {
                    "export_enabled": True,
                    "export_path": "context-map/traces/config-trace.jsonl",
                    "otlp_enabled": True,
                    "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
                    "otlp_timeout_seconds": 3.0,
                }
            }
        }
    )

    assert payload["plan"]["trace"] == {
        "export_enabled": True,
        "export_path": "context-map/traces/config-trace.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
        "otlp_timeout_seconds": 3.0,
    }


def test_resolve_quality_config_reads_grouped_trace_fields_and_emits_grouped_payload() -> None:
    resolved = _resolve_quality(
        plan={
            "trace": {
                "export_enabled": True,
                "export_path": "context-map/traces/config-trace.jsonl",
                "otlp_enabled": True,
                "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
                "otlp_timeout_seconds": 3.0,
            }
        }
    )

    assert resolved["trace_export_enabled"] is True
    assert resolved["trace_export_path"] == "context-map/traces/config-trace.jsonl"
    assert resolved["trace_otlp_enabled"] is True
    assert resolved["trace_otlp_endpoint"] == "file://context-map/traces/trace-otlp.json"
    assert resolved["trace_otlp_timeout_seconds"] == 3.0
    assert resolved["trace"] == {
        "export_enabled": True,
        "export_path": "context-map/traces/config-trace.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
        "otlp_timeout_seconds": 3.0,
    }


def test_validate_cli_config_accepts_grouped_cochange_tests_and_scip_fields() -> None:
    payload = validate_cli_config(
        {
            "plan": {
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
    )

    assert payload["plan"]["cochange"] == {
        "enabled": False,
        "cache_path": "context-map/cochange/custom.json",
        "lookback_commits": 128,
        "half_life_days": 14.0,
        "top_neighbors": 6,
        "boost_weight": 0.75,
    }
    assert payload["plan"]["tests"] == {
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl": {
            "json_path": "artifacts/sbfl.json",
            "metric": "dstar",
        },
    }
    assert payload["plan"]["scip"] == {
        "enabled": True,
        "index_path": "context-map/scip/custom-index.json",
        "provider": "scip_lite",
        "generate_fallback": False,
    }


def test_resolve_quality_config_emits_grouped_cochange_tests_and_scip_payloads() -> None:
    resolved = _resolve_quality(
        plan={
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
    )

    assert resolved["cochange_enabled"] is False
    assert resolved["cochange_cache_path"] == "context-map/cochange/custom.json"
    assert resolved["cochange_lookback_commits"] == 128
    assert resolved["cochange_half_life_days"] == 14.0
    assert resolved["cochange_top_neighbors"] == 6
    assert resolved["cochange_boost_weight"] == 0.75
    assert resolved["cochange"] == {
        "enabled": False,
        "cache_path": "context-map/cochange/custom.json",
        "lookback_commits": 128,
        "half_life_days": 14.0,
        "top_neighbors": 6,
        "boost_weight": 0.75,
    }
    assert resolved["junit_xml"] == "artifacts/junit.xml"
    assert resolved["coverage_json"] == "artifacts/coverage.json"
    assert resolved["sbfl_json"] == "artifacts/sbfl.json"
    assert resolved["sbfl_metric"] == "dstar"
    assert resolved["tests"] == {
        "junit_xml": "artifacts/junit.xml",
        "coverage_json": "artifacts/coverage.json",
        "sbfl_json": "artifacts/sbfl.json",
        "sbfl_metric": "dstar",
    }
    assert resolved["scip_enabled"] is True
    assert resolved["scip_index_path"] == "context-map/scip/custom-index.json"
    assert resolved["scip_provider"] == "scip_lite"
    assert resolved["scip_generate_fallback"] is False
    assert resolved["scip"] == {
        "enabled": True,
        "index_path": "context-map/scip/custom-index.json",
        "provider": "scip_lite",
        "generate_fallback": False,
        "base_weight": 0.5,
    }


def test_resolve_quality_config_grouped_quality_signals_match_flat_compatibility() -> None:
    flat = _resolve_quality(
        plan={
            "cochange_enabled": False,
            "cochange_cache_path": "context-map/cochange/custom.json",
            "cochange_lookback_commits": 128,
            "cochange_half_life_days": 14.0,
            "cochange_top_neighbors": 6,
            "cochange_boost_weight": 0.75,
            "junit_xml": "artifacts/junit.xml",
            "coverage_json": "artifacts/coverage.json",
            "sbfl": {
                "json_path": "artifacts/sbfl.json",
                "metric": "dstar",
            },
            "scip_enabled": True,
            "scip_index_path": "context-map/scip/custom-index.json",
            "scip_provider": "scip_lite",
            "scip_generate_fallback": False,
        }
    )
    grouped = _resolve_quality(
        plan={
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
    )

    for key in (
        "cochange_enabled",
        "cochange_cache_path",
        "cochange_lookback_commits",
        "cochange_half_life_days",
        "cochange_top_neighbors",
        "cochange_boost_weight",
        "cochange",
        "junit_xml",
        "coverage_json",
        "sbfl_json",
        "sbfl_metric",
        "tests",
        "scip_enabled",
        "scip_index_path",
        "scip_provider",
        "scip_generate_fallback",
        "scip",
    ):
        assert grouped[key] == flat[key]
