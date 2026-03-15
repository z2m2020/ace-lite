"""Click option definitions and CLI parameter coercion helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click

from ace_lite.cli_app.params_normalize import (
    _resolve_retrieval_preset,
    _to_adaptive_router_mode,
    _to_bool,
    _to_candidate_ranker,
    _to_chunk_disclosure,
    _to_chunk_guard_mode,
    _to_csv_languages,
    _to_embedding_provider,
    _to_float,
    _to_float_dict,
    _to_hybrid_fusion_mode,
    _to_int,
    _to_memory_auto_tag_mode,
    _to_memory_gate_mode,
    _to_optional_str,
    _to_remote_slot_policy_mode,
    _to_retrieval_policy,
    _to_sbfl_metric,
    _to_scip_provider,
    _to_slot_allowlist,
    _to_string_list,
    _to_tokenizer_model,
    parse_lsp_command_options,
    parse_lsp_commands_from_config,
)
from ace_lite.cli_app.params_option_groups import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CANDIDATE_RANKER_CHOICES,
    CHUNK_DISCLOSURE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    HYBRID_FUSION_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    MEMORY_STRATEGY_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
    RETRIEVAL_PRESETS,
    RETRIEVAL_PRESET_CHOICES,
    SBFL_METRIC_CHOICES,
    SCIP_PROVIDER_CHOICES,
    build_option_group_decorators,
)
from ace_lite.repomap.ranking import RANKING_PROFILES
from ace_lite.runtime_profiles import RUNTIME_PROFILE_NAMES


def _apply_click_options(
    *options: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = func
        for option in reversed(options):
            wrapped = option(wrapped)
        return wrapped

    return _decorator


def _compose_click_decorators(
    *decorators: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = func
        for decorator in reversed(decorators):
            wrapped = decorator(wrapped)
        return wrapped

    return _decorator


def _with_shared_target_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("target"))(func)


def _with_shared_candidate_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("candidate"))(func)


def _with_shared_index_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("index"))(func)


def _with_shared_embedding_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("embedding"))(func)


def _with_shared_repomap_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("repomap"))(func)


def _with_shared_lsp_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("lsp"))(func)


def _with_shared_memory_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("memory"))(func)


def _with_shared_skills_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("skills"))(func)


def _with_shared_adaptive_router_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("adaptive_router"))(func)


def _with_shared_plan_replay_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("plan_replay"))(func)


def _with_shared_chunk_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("chunk"))(func)


def _with_shared_cochange_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("cochange"))(func)


def _with_shared_policy_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("policy"))(func)


def _with_shared_test_signal_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("test_signal"))(func)


def _with_shared_scip_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("scip"))(func)


def _with_shared_trace_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(*build_option_group_decorators("trace"))(func)


def _with_shared_plan_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _compose_click_decorators(
        _apply_click_options(
            click.option(
                "--runtime-profile",
                default=None,
                type=click.Choice(list(RUNTIME_PROFILE_NAMES), case_sensitive=False),
                help=(
                    "High-level runtime profile to seed retrieval, cache, and budget "
                    "knobs before expert overrides are applied."
                ),
            ),
        ),
        _with_shared_target_options,
        _with_shared_candidate_options,
        _with_shared_index_options,
        _with_shared_embedding_options,
        _with_shared_repomap_options,
        _with_shared_lsp_options,
        _with_shared_memory_options,
        _with_shared_skills_options,
        _with_shared_adaptive_router_options,
        _with_shared_plan_replay_options,
        _with_shared_chunk_options,
        _with_shared_cochange_options,
        _with_shared_policy_options,
        _with_shared_test_signal_options,
        _with_shared_scip_options,
        _with_shared_trace_options,
    )(func)


__all__ = [
    "CANDIDATE_RANKER_CHOICES",
    "CHUNK_DISCLOSURE_CHOICES",
    "CHUNK_GUARD_MODE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "HYBRID_FUSION_CHOICES",
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_STRATEGY_CHOICES",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RETRIEVAL_POLICY_CHOICES",
    "RETRIEVAL_PRESETS",
    "RETRIEVAL_PRESET_CHOICES",
    "SBFL_METRIC_CHOICES",
    "SCIP_PROVIDER_CHOICES",
    "_resolve_retrieval_preset",
    "_to_bool",
    "_to_adaptive_router_mode",
    "_to_candidate_ranker",
    "_to_chunk_disclosure",
    "_to_chunk_guard_mode",
    "_to_csv_languages",
    "_to_embedding_provider",
    "_to_float",
    "_to_float_dict",
    "_to_hybrid_fusion_mode",
    "_to_int",
    "_to_memory_auto_tag_mode",
    "_to_optional_str",
    "_to_remote_slot_policy_mode",
    "_to_retrieval_policy",
    "_to_sbfl_metric",
    "_to_scip_provider",
    "_to_slot_allowlist",
    "_to_string_list",
    "_to_tokenizer_model",
    "_with_shared_plan_options",
    "_with_shared_skills_options",
    "parse_lsp_command_options",
    "parse_lsp_commands_from_config",
]
