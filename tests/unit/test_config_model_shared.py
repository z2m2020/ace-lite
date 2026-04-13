from __future__ import annotations

import re

import pytest

from ace_lite.config_model_shared import (
    normalize_adaptive_router_mode,
    normalize_candidate_ranker,
    normalize_chunk_guard_mode,
    normalize_embedding_provider,
    normalize_memory_disclosure_mode,
    normalize_memory_gate_mode,
    normalize_memory_notes_mode,
    normalize_memory_strategy,
    normalize_memory_timezone_mode,
    normalize_ranking_profile,
    normalize_retrieval_policy,
    normalize_topological_shield_mode,
    validate_adaptive_router_mode,
    validate_chunk_disclosure,
    validate_chunk_guard_mode,
    validate_memory_auto_tag_mode,
    validate_memory_gate_mode,
    validate_memory_notes_mode,
    validate_memory_timezone_mode,
    validate_ranking_profile,
    validate_remote_slot_policy_mode,
    validate_retrieval_policy,
    validate_scip_provider,
    validate_topological_shield_mode,
)


def test_normalize_memory_helpers_fall_back_to_defaults() -> None:
    assert normalize_memory_disclosure_mode("invalid", default="compact") == "compact"
    assert normalize_memory_strategy("invalid", default="hybrid") == "hybrid"
    assert normalize_memory_gate_mode("invalid", default="auto") == "auto"
    assert normalize_memory_notes_mode("invalid", default="supplement") == "supplement"
    assert normalize_memory_timezone_mode("invalid", default="utc") == "utc"


def test_normalize_candidate_ranker_helper_preserves_valid_values() -> None:
    assert normalize_candidate_ranker(" rrf_hybrid ", default="heuristic") == "rrf_hybrid"
    assert normalize_candidate_ranker("invalid", default="heuristic") == "heuristic"
    assert normalize_embedding_provider(" OLLAMA ", default="hash") == "ollama"
    assert normalize_embedding_provider("invalid", default="hash") == "hash"
    assert normalize_ranking_profile(" Graph_Seeded ", default="graph") == "graph_seeded"
    assert normalize_ranking_profile("invalid", default="graph") == "graph"
    assert normalize_retrieval_policy(" DOC_INTENT ", default="auto") == "doc_intent"
    assert normalize_retrieval_policy("invalid", default="auto") == "auto"
    assert normalize_adaptive_router_mode(" shadow ", default="observe") == "shadow"
    assert normalize_chunk_guard_mode("invalid", default="off") == "off"
    assert normalize_topological_shield_mode("report_only", default="off") == "report_only"


def test_validate_shared_choice_helpers_preserve_error_shape() -> None:
    assert validate_scip_provider("scip", field_name="scip_provider") == "scip"

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported chunk_disclosure: invalid. Expected one of:"),
    ):
        validate_chunk_disclosure("invalid", field_name="chunk_disclosure")

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported repomap.ranking_profile: invalid. Expected one of:"),
    ):
        validate_ranking_profile("invalid", field_name="repomap.ranking_profile")

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported scip_provider: invalid. Expected one of:"),
    ):
        validate_scip_provider("invalid", field_name="scip_provider")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Unsupported plugins.remote_slot_policy_mode: invalid. Expected one of:"
        ),
    ):
        validate_remote_slot_policy_mode(
            "invalid",
            field_name="plugins.remote_slot_policy_mode",
        )

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported retrieval_policy: invalid. Expected one of:"),
    ):
        validate_retrieval_policy("invalid", field_name="retrieval_policy")

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported adaptive_router.mode: invalid. Expected one of:"),
    ):
        validate_adaptive_router_mode("invalid", field_name="adaptive_router.mode")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Unsupported memory.namespace.auto_tag_mode: invalid. Expected one of:"
        ),
    ):
        validate_memory_auto_tag_mode("invalid", field_name="memory.namespace.auto_tag_mode")

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported memory.gate.mode: invalid. Expected one of:"),
    ):
        validate_memory_gate_mode("invalid", field_name="memory.gate.mode")

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported memory.notes.mode: invalid. Expected one of:"),
    ):
        validate_memory_notes_mode("invalid", field_name="memory.notes.mode")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Unsupported memory.temporal.timezone_mode: invalid. Expected one of:"
        ),
    ):
        validate_memory_timezone_mode("invalid", field_name="memory.temporal.timezone_mode")

    with pytest.raises(
        ValueError,
        match=re.escape("Unsupported chunk.guard.mode: invalid. Expected one of:"),
    ):
        validate_chunk_guard_mode("invalid", field_name="chunk.guard.mode")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Unsupported chunk.topological_shield.mode: invalid. Expected one of:"
        ),
    ):
        validate_topological_shield_mode("invalid", field_name="chunk.topological_shield.mode")
