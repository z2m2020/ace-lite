from ace_lite.cli_app import orchestrator_factory_misc_payloads
from ace_lite.cli_app.orchestrator_factory_support import (
    build_cochange_payload,
    build_embeddings_payload,
    build_index_payload,
    build_lsp_payload,
    build_plan_replay_cache_payload,
    build_plugins_payload,
    build_repomap_payload,
    build_scip_payload,
    build_skills_payload,
    build_tests_payload,
    build_tokenizer_payload,
    build_trace_payload,
)


def test_orchestrator_factory_support_reexports_misc_payload_builders() -> None:
    assert build_skills_payload is orchestrator_factory_misc_payloads.build_skills_payload
    assert build_index_payload is orchestrator_factory_misc_payloads.build_index_payload
    assert build_repomap_payload is orchestrator_factory_misc_payloads.build_repomap_payload
    assert build_lsp_payload is orchestrator_factory_misc_payloads.build_lsp_payload
    assert build_plugins_payload is orchestrator_factory_misc_payloads.build_plugins_payload
    assert build_embeddings_payload is orchestrator_factory_misc_payloads.build_embeddings_payload
    assert build_tokenizer_payload is orchestrator_factory_misc_payloads.build_tokenizer_payload
    assert build_cochange_payload is orchestrator_factory_misc_payloads.build_cochange_payload
    assert build_trace_payload is orchestrator_factory_misc_payloads.build_trace_payload
    assert (
        build_plan_replay_cache_payload
        is orchestrator_factory_misc_payloads.build_plan_replay_cache_payload
    )
    assert build_tests_payload is orchestrator_factory_misc_payloads.build_tests_payload
    assert build_scip_payload is orchestrator_factory_misc_payloads.build_scip_payload


def test_build_skills_payload_uses_tuned_default_budget() -> None:
    payload = orchestrator_factory_misc_payloads.build_skills_payload(
        skills_group={},
        skills_dir="skills",
        precomputed_routing_enabled=True,
    )

    assert payload["token_budget"] == 1400
