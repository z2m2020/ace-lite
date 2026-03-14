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
