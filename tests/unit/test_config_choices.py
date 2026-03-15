from __future__ import annotations

import ace_lite.cli_app.params_option_groups as params_option_groups
import ace_lite.config_choices as config_choices
import ace_lite.config_models as config_models
import ace_lite.index_stage.chunk_guard as chunk_guard
import ace_lite.orchestrator_config as orchestrator_config


def test_shared_config_choices_are_single_sourced() -> None:
    assert (
        config_models.RETRIEVAL_POLICY_CHOICES
        is config_choices.RETRIEVAL_POLICY_CHOICES
    )
    assert (
        params_option_groups.RETRIEVAL_POLICY_CHOICES
        is config_choices.RETRIEVAL_POLICY_CHOICES
    )
    assert (
        config_models.ADAPTIVE_ROUTER_MODE_CHOICES
        is config_choices.ADAPTIVE_ROUTER_MODE_CHOICES
    )
    assert (
        params_option_groups.ADAPTIVE_ROUTER_MODE_CHOICES
        is config_choices.ADAPTIVE_ROUTER_MODE_CHOICES
    )
    assert (
        config_models.CHUNK_GUARD_MODE_CHOICES
        is config_choices.CHUNK_GUARD_MODE_CHOICES
    )
    assert chunk_guard.CHUNK_GUARD_MODE_CHOICES is config_choices.CHUNK_GUARD_MODE_CHOICES
    assert (
        config_models.MEMORY_AUTO_TAG_MODE_CHOICES
        is config_choices.MEMORY_AUTO_TAG_MODE_CHOICES
    )
    assert (
        config_models.MEMORY_GATE_MODE_CHOICES
        is config_choices.MEMORY_GATE_MODE_CHOICES
    )
    assert (
        params_option_groups.MEMORY_GATE_MODE_CHOICES
        is config_choices.MEMORY_GATE_MODE_CHOICES
    )
    assert (
        orchestrator_config.MEMORY_NOTES_MODE_CHOICES
        is config_choices.MEMORY_NOTES_MODE_CHOICES
    )
    assert (
        config_models.MEMORY_TIMEZONE_MODE_CHOICES
        is config_choices.MEMORY_TIMEZONE_MODE_CHOICES
    )
    assert (
        config_models.REMOTE_SLOT_POLICY_CHOICES
        is config_choices.REMOTE_SLOT_POLICY_CHOICES
    )
    assert (
        params_option_groups.REMOTE_SLOT_POLICY_CHOICES
        is config_choices.REMOTE_SLOT_POLICY_CHOICES
    )
    assert (
        config_models.EMBEDDING_PROVIDER_CHOICES
        is config_choices.EMBEDDING_PROVIDER_CHOICES
    )
    assert (
        params_option_groups.EMBEDDING_PROVIDER_CHOICES
        is config_choices.EMBEDDING_PROVIDER_CHOICES
    )


def test_option_group_registry_covers_shared_descriptor_families() -> None:
    groups = {
        descriptor.name: descriptor.option_descriptors
        for descriptor in params_option_groups.iter_option_group_descriptors()
    }

    assert groups["memory"] is params_option_groups.SHARED_MEMORY_OPTION_DESCRIPTORS
    assert groups["skills"] is params_option_groups.SHARED_SKILLS_OPTION_DESCRIPTORS
    assert groups["target"] is params_option_groups.SHARED_TARGET_OPTION_DESCRIPTORS
    assert (
        groups["adaptive_router"]
        is params_option_groups.SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS
    )
    assert (
        groups["plan_replay"]
        is params_option_groups.SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS
    )
    assert groups["chunk"] is params_option_groups.SHARED_CHUNK_OPTION_DESCRIPTORS
    assert groups["candidate"] is params_option_groups.SHARED_CANDIDATE_OPTION_DESCRIPTORS
    assert groups["embedding"] is params_option_groups.SHARED_EMBEDDING_OPTION_DESCRIPTORS
    assert groups["index"] is params_option_groups.SHARED_INDEX_OPTION_DESCRIPTORS
    assert groups["lsp"] is params_option_groups.SHARED_LSP_OPTION_DESCRIPTORS
    assert groups["cochange"] is params_option_groups.SHARED_COCHANGE_OPTION_DESCRIPTORS
    assert groups["policy"] is params_option_groups.SHARED_POLICY_OPTION_DESCRIPTORS
    assert groups["repomap"] is params_option_groups.SHARED_REPOMAP_OPTION_DESCRIPTORS
    assert (
        groups["test_signal"]
        is params_option_groups.SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS
    )
    assert groups["scip"] is params_option_groups.SHARED_SCIP_OPTION_DESCRIPTORS
    assert groups["trace"] is params_option_groups.SHARED_TRACE_OPTION_DESCRIPTORS
    assert set(params_option_groups.OPTION_GROUP_REGISTRY) == set(groups)


def test_build_option_group_decorators_matches_descriptor_count() -> None:
    decorators = params_option_groups.build_option_group_decorators("candidate")

    assert len(decorators) == len(params_option_groups.SHARED_CANDIDATE_OPTION_DESCRIPTORS)
    assert len(params_option_groups.build_option_group_decorators("target")) == len(
        params_option_groups.SHARED_TARGET_OPTION_DESCRIPTORS
    )
    assert len(params_option_groups.build_option_group_decorators("index")) == len(
        params_option_groups.SHARED_INDEX_OPTION_DESCRIPTORS
    )
    assert len(params_option_groups.build_option_group_decorators("repomap")) == len(
        params_option_groups.SHARED_REPOMAP_OPTION_DESCRIPTORS
    )
