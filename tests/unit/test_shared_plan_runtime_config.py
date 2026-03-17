from __future__ import annotations

import pytest

from ace_lite.config_models import validate_cli_config
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.shared_plan_runtime_config import (
    normalize_container_tag,
    resolve_embedding_index_path,
    resolve_embedding_model,
    resolve_embedding_provider,
    resolve_memory_auto_tag_mode,
    resolve_memory_gate_mode,
    resolve_memory_notes_mode,
    resolve_plan_replay_cache_path,
    resolve_ranking_profile,
    resolve_scip_provider,
    resolve_tokenizer_model,
    resolve_trace_export_path,
    resolve_trace_otlp_endpoint,
    resolve_trace_otlp_timeout_seconds,
)


def test_shared_plan_runtime_config_helpers_support_validate_and_runtime_modes() -> None:
    assert normalize_container_tag("  repo/demo  ") == "repo/demo"
    assert normalize_container_tag("   ") is None

    assert resolve_memory_auto_tag_mode("USER") == "user"
    assert resolve_memory_auto_tag_mode("invalid") is None
    with pytest.raises(ValueError, match="memory.namespace.auto_tag_mode"):
        resolve_memory_auto_tag_mode(
            "invalid",
            field_name="memory.namespace.auto_tag_mode",
        )

    assert resolve_memory_gate_mode("NEVER", default="auto") == "never"
    assert resolve_memory_gate_mode("invalid", default="auto") == "auto"
    with pytest.raises(ValueError, match="memory.gate.mode"):
        resolve_memory_gate_mode("invalid", field_name="memory.gate.mode")

    assert resolve_memory_notes_mode("PREFER_LOCAL", default="supplement") == "prefer_local"
    assert resolve_memory_notes_mode("invalid", default="supplement") == "supplement"
    with pytest.raises(ValueError, match="memory.notes.mode"):
        resolve_memory_notes_mode("invalid", field_name="memory.notes.mode")

    assert resolve_ranking_profile("GRAPH", default="graph") == "graph"
    assert resolve_ranking_profile("invalid", default="graph") == "graph"
    with pytest.raises(ValueError, match="repomap.ranking_profile"):
        resolve_ranking_profile("invalid", field_name="repomap.ranking_profile")

    assert resolve_embedding_provider(" OLLAMA ", default="hash") == "ollama"
    assert resolve_embedding_provider("custom-provider", default="hash") == "custom-provider"
    assert resolve_embedding_provider(" ", default="hash") == "hash"
    with pytest.raises(ValueError, match="embedding_provider"):
        resolve_embedding_provider("invalid", field_name="embedding_provider")

    assert resolve_embedding_model(" hash-v2 ") == "hash-v2"
    assert resolve_embedding_model(" ") == "hash-v1"
    assert (
        resolve_embedding_index_path(" context-map/embeddings/custom-index.json ")
        == "context-map/embeddings/custom-index.json"
    )
    assert resolve_embedding_index_path(" ") == "context-map/embeddings/index.json"
    assert resolve_tokenizer_model(" gpt-4.1-mini ") == "gpt-4.1-mini"
    assert resolve_tokenizer_model(" ") == "gpt-4o-mini"
    assert (
        resolve_trace_export_path(" context-map/traces/custom.jsonl ")
        == "context-map/traces/custom.jsonl"
    )
    assert resolve_trace_export_path(" ") == "context-map/traces/stage_spans.jsonl"
    assert resolve_trace_otlp_endpoint(" http://collector:4318/v1/traces ") == "http://collector:4318/v1/traces"
    assert resolve_trace_otlp_endpoint(None) == ""
    assert resolve_trace_otlp_timeout_seconds("0") == 0.1
    assert resolve_trace_otlp_timeout_seconds("bad") == 1.5
    assert (
        resolve_plan_replay_cache_path(" custom/plan-replay/cache.json ")
        == "custom/plan-replay/cache.json"
    )
    assert resolve_plan_replay_cache_path(" ") == "context-map/plan-replay/cache.json"

    assert resolve_scip_provider("SCIP_LITE", field_name="scip.provider") == "scip_lite"
    assert resolve_scip_provider(None, default="auto", field_name="scip.provider") == "auto"
    with pytest.raises(ValueError, match="scip.provider"):
        resolve_scip_provider("invalid", field_name="scip.provider")


def test_shared_plan_runtime_config_aligns_cli_and_runtime_memory_sections() -> None:
    memory_payload = {
        "namespace": {
            "container_tag": " repo/demo ",
            "auto_tag_mode": "USER",
        },
        "gate": {
            "enabled": True,
            "mode": "NEVER",
        },
        "notes": {
            "enabled": True,
            "mode": "PREFER_LOCAL",
        },
    }
    repomap_payload = {"ranking_profile": "GRAPH"}
    scip_payload = {"provider": "AUTO"}
    embeddings_payload = {
        "provider": "OLLAMA",
        "model": " hash-v2 ",
        "index_path": " context-map/embeddings/custom-index.json ",
    }
    tokenizer_payload = {"model": " gpt-4.1-mini "}
    trace_payload = {
        "export_path": " context-map/traces/custom.jsonl ",
        "otlp_endpoint": " http://collector:4318/v1/traces ",
        "otlp_timeout_seconds": "0",
    }
    plan_replay_cache_payload = {
        "enabled": True,
        "cache_path": " custom/plan-replay/cache.json ",
    }

    cli_validated = validate_cli_config(
        {
            "plan": {
                "memory": memory_payload,
                "repomap": repomap_payload,
                "scip": scip_payload,
                "embeddings": embeddings_payload,
                "tokenizer": tokenizer_payload,
                "trace": trace_payload,
                "plan_replay_cache": plan_replay_cache_payload,
            }
        }
    )
    runtime = OrchestratorConfig(
        memory=memory_payload,
        repomap=repomap_payload,
        scip=scip_payload,
        embeddings=embeddings_payload,
        tokenizer=tokenizer_payload,
        trace=trace_payload,
        plan_replay_cache=plan_replay_cache_payload,
    )

    assert cli_validated["plan"]["memory"]["namespace"]["container_tag"] == "repo/demo"
    assert cli_validated["plan"]["memory"]["namespace"]["auto_tag_mode"] == "user"
    assert cli_validated["plan"]["memory"]["gate"]["mode"] == "never"
    assert cli_validated["plan"]["memory"]["notes"]["mode"] == "prefer_local"
    assert cli_validated["plan"]["repomap"]["ranking_profile"] == "graph"
    assert cli_validated["plan"]["scip"]["provider"] == "auto"
    assert cli_validated["plan"]["embeddings"]["provider"] == "ollama"
    assert cli_validated["plan"]["embeddings"]["model"] == "hash-v2"
    assert (
        cli_validated["plan"]["embeddings"]["index_path"]
        == "context-map/embeddings/custom-index.json"
    )
    assert cli_validated["plan"]["tokenizer"]["model"] == "gpt-4.1-mini"
    assert cli_validated["plan"]["trace"]["export_path"] == "context-map/traces/custom.jsonl"
    assert (
        cli_validated["plan"]["trace"]["otlp_endpoint"]
        == "http://collector:4318/v1/traces"
    )
    assert cli_validated["plan"]["trace"]["otlp_timeout_seconds"] == 0.1
    assert cli_validated["plan"]["plan_replay_cache"]["cache_path"] == "custom/plan-replay/cache.json"
    assert runtime.memory.namespace.container_tag == "repo/demo"
    assert runtime.memory.namespace.auto_tag_mode == "user"
    assert runtime.memory.gate.mode == "never"
    assert runtime.memory.notes.mode == "prefer_local"
    assert runtime.repomap.ranking_profile == "graph"
    assert runtime.scip.provider == "auto"
    assert runtime.embeddings.provider == "ollama"
    assert runtime.embeddings.model == "hash-v2"
    assert str(runtime.embeddings.index_path) == "context-map/embeddings/custom-index.json"
    assert runtime.tokenizer.model == "gpt-4.1-mini"
    assert str(runtime.trace.export_path) == "context-map/traces/custom.jsonl"
    assert runtime.trace.otlp_endpoint == "http://collector:4318/v1/traces"
    assert runtime.trace.otlp_timeout_seconds == 0.1
    assert (
        str(runtime.plan_replay_cache.cache_path)
        == "custom/plan-replay/cache.json"
    )


def test_shared_plan_runtime_config_aligns_flat_cli_aliases_with_runtime_defaults() -> None:
    cli_validated = validate_cli_config(
        {
            "plan": {
                "embedding_provider": " OLLAMA ",
                "embedding_model": " ",
                "embedding_index_path": " ",
                "tokenizer_model": " ",
                "trace_export_path": " ",
                "trace_otlp_endpoint": " ",
                "trace_otlp_timeout_seconds": "0",
                "plan_replay_cache_path": " ",
            }
        }
    )
    runtime = OrchestratorConfig(
        embeddings={"provider": " OLLAMA ", "model": " ", "index_path": " "},
        tokenizer={"model": " "},
        trace={"export_path": " ", "otlp_endpoint": " ", "otlp_timeout_seconds": "0"},
        plan_replay_cache={"cache_path": " "},
    )

    assert cli_validated["plan"]["embedding_provider"] == "ollama"
    assert cli_validated["plan"]["embedding_model"] == "hash-v1"
    assert cli_validated["plan"]["embedding_index_path"] == "context-map/embeddings/index.json"
    assert cli_validated["plan"]["tokenizer_model"] == "gpt-4o-mini"
    assert cli_validated["plan"]["trace_export_path"] == "context-map/traces/stage_spans.jsonl"
    assert cli_validated["plan"]["trace_otlp_endpoint"] == ""
    assert cli_validated["plan"]["trace_otlp_timeout_seconds"] == 0.1
    assert cli_validated["plan"]["plan_replay_cache_path"] == "context-map/plan-replay/cache.json"
    assert runtime.embeddings.provider == "ollama"
    assert runtime.embeddings.model == "hash-v1"
    assert str(runtime.embeddings.index_path) == "context-map/embeddings/index.json"
    assert runtime.tokenizer.model == "gpt-4o-mini"
    assert str(runtime.trace.export_path) == "context-map/traces/stage_spans.jsonl"
    assert runtime.trace.otlp_endpoint == ""
    assert runtime.trace.otlp_timeout_seconds == 0.1
    assert str(runtime.plan_replay_cache.cache_path) == "context-map/plan-replay/cache.json"
